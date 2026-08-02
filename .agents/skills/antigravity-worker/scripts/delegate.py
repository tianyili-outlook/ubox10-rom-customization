#!/usr/bin/env python3
"""Run one bounded UBOX10 task through Antigravity CLI."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import locale
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid
from typing import Any, Sequence


MINIMUM_PYTHON = (3, 10)
DEFAULT_MODEL = "gemini-3.6-flash-high"
DEFAULT_EFFORT = "high"
DEFAULT_TIMEOUT = 900
READ_ONLY_MODES = {"inspect", "review"}
AUTH_MARKERS = (
    "please sign in",
    "not logged in",
    "unauthenticated",
    "authentication required",
    "authentication failed",
)
REQUIRED_COMMAND_ALLOWS = (
    "command(git status)",
    "command(git diff)",
    "command(git show)",
    "command(git log)",
    "command(git rev-parse)",
    "command(python)",
    "command(py)",
)
REQUIRED_PROTECTIVE_DENIES = (
    "command(git push)",
    "command(git commit)",
    "command(git reset)",
    "command(git clean)",
    "command(git checkout --)",
    r"command(git checkout \.)",
    "command(git restore)",
    "command(sudo)",
    "command(runas)",
)
FORBIDDEN_ALLOWS = {
    "command(*)",
    "unsandboxed(*)",
    "unsandboxed(python)",
    "read_file(*)",
    "write_file(*)",
}


class DelegateError(RuntimeError):
    """Expected, user-actionable delegation failure."""


class BridgePreflightError(DelegateError):
    """A bridge invariant failed before the real worker was invoked."""

    def __init__(
        self,
        check: str,
        detail: str,
        *,
        command: Sequence[str] | None = None,
        path: Path | None = None,
        rule: str | None = None,
        stderr: str = "",
        exit_code: int | None = None,
        conversation_id: str | None = None,
    ):
        self.check = check
        self.detail = detail
        self.command = list(command) if command else None
        self.path = str(path) if path else None
        self.rule = rule
        self.stderr = stderr
        self.exit_code = exit_code
        self.conversation_id = conversation_id
        super().__init__(f"{check}: {detail}")


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Delegate one bounded UBOX10 task to Antigravity CLI."
    )
    parser.add_argument("task_file", help="Path to the bounded Markdown task contract")
    parser.add_argument(
        "--mode",
        choices=("inspect", "implement", "validate", "review"),
        required=True,
        help="Worker operating mode",
    )
    parser.add_argument("--conversation-id", help="Continue an existing conversation")
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Timeout in seconds (default: {DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "--output-dir",
        default=".orchestration/antigravity/runs",
        help="Repository-local run directory parent",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Model slug or Gemini family (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--effort",
        choices=("low", "medium", "high"),
        default=DEFAULT_EFFORT,
        help=f"Reasoning effort (default: {DEFAULT_EFFORT})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print resolved paths and command without invoking Antigravity",
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Run the bridge preflight/smoke and do not invoke the real task",
    )
    return parser.parse_args(argv)


def run_process(
    command: Sequence[str],
    *,
    cwd: Path,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    process = subprocess.run(
        list(command),
        cwd=str(cwd),
        capture_output=True,
        text=False,
        timeout=timeout,
        check=False,
        shell=False,
    )

    def decode(value: bytes | str | None) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            fallback = locale.getpreferredencoding(False) or "utf-8"
            return value.decode(fallback, errors="replace")

    return subprocess.CompletedProcess(
        process.args,
        process.returncode,
        decode(process.stdout),
        decode(process.stderr),
    )


def find_repo_root(start: Path) -> Path:
    process = run_process(
        (
            "git",
            "-c",
            f"safe.directory={start}",
            "-C",
            str(start),
            "rev-parse",
            "--show-toplevel",
        ),
        cwd=start,
    )
    if process.returncode != 0:
        raise DelegateError(
            "Unable to locate the Git repository root: " + process.stderr.strip()
        )
    root = Path(process.stdout.strip()).resolve()
    if not (root / ".git").exists():
        raise DelegateError(f"Resolved Git root has no .git entry: {root}")
    return root


def resolve_repository_root() -> Path:
    """Resolve the checkout from the installed delegate, not the caller's cwd."""
    script_checkout = Path(__file__).resolve().parents[4]
    return find_repo_root(script_checkout)


def resolve_inside(root: Path, value: str, label: str) -> Path:
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise DelegateError(f"{label} must remain inside the repository: {candidate}") from exc
    return candidate


def find_agy() -> Path:
    located = shutil.which("agy")
    if located:
        return Path(located).resolve()
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            official = Path(local_app_data) / "agy" / "bin" / "agy.exe"
            if official.is_file():
                return official.resolve()
    raise DelegateError(
        "Antigravity CLI 'agy' is missing. Install it or add its bin directory to PATH."
    )


def antigravity_state_root() -> Path:
    return Path.home() / ".gemini" / "antigravity-cli"


def effective_settings_path() -> Path:
    return antigravity_state_root() / "settings.json"


def saved_project_id() -> str | None:
    path = antigravity_state_root() / "cache" / "default_project_id.txt"
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value or None


def canonical_rule_path(value: str) -> str:
    return value.replace("\\", "/").rstrip("/").casefold()


def permission_target(rule: str) -> tuple[str, str] | None:
    match = re.fullmatch(r"\s*(read_file|write_file)\((.*)\)\s*", rule)
    if not match:
        return None
    return match.group(1), match.group(2).strip().strip('"\'')


def targets_repository(target: str, repository_root: Path) -> bool:
    if target == "*":
        return False
    candidate = Path(target.replace("/", os.sep))
    if not candidate.is_absolute():
        return True
    root_value = canonical_rule_path(str(repository_root))
    target_value = canonical_rule_path(str(candidate))
    return target_value == root_value or target_value.startswith(root_value + "/")


def supplemental_permission_sources(
    project_id: str | None,
) -> list[tuple[Path, dict[str, Any]]]:
    sources: list[tuple[Path, dict[str, Any]]] = []
    global_path = Path.home() / ".gemini" / "config" / "config.json"
    if global_path.is_file():
        try:
            data = json.loads(global_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BridgePreflightError(
                "shared permission JSON parses", f"{global_path}: {exc}", path=global_path
            ) from exc
        grants = data.get("userSettings", {}).get("globalPermissionGrants", {})
        if isinstance(grants, dict):
            sources.append((global_path, grants))
    if project_id:
        project_path = (
            Path.home() / ".gemini" / "config" / "projects" / f"{project_id}.json"
        )
        if project_path.is_file():
            try:
                data = json.loads(project_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise BridgePreflightError(
                    "project permission JSON parses", f"{project_path}: {exc}", path=project_path
                ) from exc
            grants = data.get("permissionGrants", {}).get("permissionGrants", {})
            if isinstance(grants, dict):
                sources.append((project_path, grants))
    return sources


def validate_supplemental_permissions(
    repository_root: Path, project_id: str | None
) -> list[Path]:
    paths: list[Path] = []
    for path, permissions in supplemental_permission_sources(project_id):
        paths.append(path)
        for bucket_name in ("allow", "ask", "deny"):
            rules = permissions.get(bucket_name, [])
            if not isinstance(rules, list):
                raise BridgePreflightError(
                    "permission rules",
                    f"{path}: {bucket_name} must be an array",
                    path=path,
                )
            for rule in rules:
                if not isinstance(rule, str):
                    continue
                parsed = permission_target(rule)
                if parsed and targets_repository(parsed[1], repository_root):
                    raise BridgePreflightError(
                        "repository file permission rule",
                        f"remove {bucket_name} entry {rule!r} from {path}",
                        path=path,
                        rule=rule,
                    )
                if bucket_name == "ask" and rule == "command(*)":
                    raise BridgePreflightError(
                        "ask command(*)",
                        f"remove ask entry 'command(*)' from {path}",
                        path=path,
                        rule=rule,
                    )
                if bucket_name == "allow" and (
                    rule in FORBIDDEN_ALLOWS
                    or rule.startswith("unsandboxed(")
                    or rule.startswith("escalate_admin(")
                ):
                    raise BridgePreflightError(
                        "forbidden allow rule",
                        f"remove allow entry {rule!r} from {path}",
                        path=path,
                        rule=rule,
                    )
    return paths


def load_and_validate_settings(repository_root: Path) -> tuple[Path, dict[str, Any]]:
    path = effective_settings_path()
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BridgePreflightError("settings JSON parses", f"{path}: {exc}") from exc
    if not isinstance(settings, dict):
        raise BridgePreflightError("settings JSON parses", f"{path}: root is not an object")

    if settings.get("toolPermission") != "always-proceed":
        raise BridgePreflightError(
            "toolPermission", f"expected always-proceed in {path}", path=path
        )
    if settings.get("artifactReviewPolicy") != "always-proceed":
        raise BridgePreflightError(
            "artifact review policy", f"expected always-proceed in {path}", path=path
        )
    if settings.get("enableTerminalSandbox", False) is not False:
        raise BridgePreflightError(
            "terminal sandbox", f"enableTerminalSandbox is not false in {path}", path=path
        )
    if settings.get("allowNonWorkspaceAccess", False) is not False:
        raise BridgePreflightError(
            "non-workspace access", f"allowNonWorkspaceAccess is not false in {path}"
        )

    permissions = settings.get("permissions", {})
    if not isinstance(permissions, dict):
        raise BridgePreflightError("permission rules", f"permissions is not an object in {path}")
    allow = permissions.get("allow", [])
    ask = permissions.get("ask", [])
    deny = permissions.get("deny", [])
    if not all(isinstance(value, list) for value in (allow, ask, deny)):
        raise BridgePreflightError("permission rules", f"allow/ask/deny must be arrays in {path}")

    for bucket_name, rules in (("allow", allow), ("ask", ask)):
        for rule in rules:
            if isinstance(rule, str):
                parsed = permission_target(rule)
                if parsed and targets_repository(parsed[1], repository_root):
                    raise BridgePreflightError(
                        "repository file permission rule",
                        f"remove permissions.{bucket_name} entry {rule!r} from {path}",
                    )
    if "command(*)" in ask:
        raise BridgePreflightError(
            "ask command(*)", f"remove permissions.ask entry 'command(*)' from {path}"
        )
    allowed_git_deny_path = canonical_rule_path(str(repository_root / ".git"))
    for rule in deny:
        if not isinstance(rule, str):
            continue
        parsed = permission_target(rule)
        if (
            parsed
            and targets_repository(parsed[1], repository_root)
            and not (
                parsed[0] == "write_file"
                and canonical_rule_path(parsed[1]) == allowed_git_deny_path
            )
        ):
            raise BridgePreflightError(
                "repository file permission rule",
                f"remove granular permissions.deny entry {rule!r} from {path}",
            )
    for rule in FORBIDDEN_ALLOWS:
        if rule in allow:
            raise BridgePreflightError(
                "forbidden allow rule", f"remove permissions.allow entry {rule!r} from {path}"
            )
    for rule in allow:
        if isinstance(rule, str) and (
            rule.startswith("unsandboxed(") or rule.startswith("escalate_admin(")
        ):
            raise BridgePreflightError(
                "unsafe allow rule", f"remove permissions.allow entry {rule!r} from {path}"
            )
    missing_allows = [rule for rule in REQUIRED_COMMAND_ALLOWS if rule not in allow]
    if missing_allows:
        raise BridgePreflightError(
            "sandboxed command allows", f"missing from permissions.allow: {missing_allows}"
        )

    git_deny = f"write_file({repository_root.as_posix()}/.git)"
    required_denies = (git_deny, *REQUIRED_PROTECTIVE_DENIES)
    missing_denies = [rule for rule in required_denies if rule not in deny]
    if missing_denies:
        raise BridgePreflightError(
            "protective deny rules", f"missing from permissions.deny: {missing_denies}"
        )
    return path, settings


def require_subprocess_cwd(repository_root: Path) -> None:
    process = run_process(
        (
            sys.executable,
            "-c",
            "import os,sys; raise SystemExit(0 if os.path.samefile(os.getcwd(), sys.argv[1]) else 3)",
            str(repository_root),
        ),
        cwd=repository_root,
    )
    if process.returncode != 0:
        raise BridgePreflightError(
            "subprocess cwd equals repository root",
            f"expected={repository_root}; comparison_exit_code={process.returncode}; "
            f"stderr={process.stderr.strip()!r}",
        )


def windows_process_is_elevated() -> bool:
    if os.name != "nt":
        return False
    import ctypes
    from ctypes import wintypes

    token_query = 0x0008
    token_elevation_class = 20
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    advapi32.OpenProcessToken.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    advapi32.OpenProcessToken.restype = wintypes.BOOL
    advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.GetTokenInformation.restype = wintypes.BOOL

    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(
        kernel32.GetCurrentProcess(), token_query, ctypes.byref(token)
    ):
        raise BridgePreflightError(
            "process elevation check",
            str(ctypes.WinError(ctypes.get_last_error())),
        )
    try:
        class TokenElevation(ctypes.Structure):
            _fields_ = [("TokenIsElevated", wintypes.DWORD)]

        elevation = TokenElevation()
        returned = wintypes.DWORD()
        if not advapi32.GetTokenInformation(
            token,
            token_elevation_class,
            ctypes.byref(elevation),
            ctypes.sizeof(elevation),
            ctypes.byref(returned),
        ):
            raise BridgePreflightError(
                "process elevation check",
                str(ctypes.WinError(ctypes.get_last_error())),
            )
        return bool(elevation.TokenIsElevated)
    finally:
        kernel32.CloseHandle(token)


def require_non_elevated_process(repository_root: Path) -> bool:
    elevated = windows_process_is_elevated()
    if elevated:
        raise BridgePreflightError(
            "process elevation state",
            "current process has an elevated Administrator token; restart Codex as a normal user",
            path=repository_root,
        )
    return elevated


def require_git_root_matches(repository_root: Path) -> None:
    command = (
        "git",
        "-c",
        f"safe.directory={repository_root}",
        "-C",
        str(repository_root),
        "rev-parse",
        "--show-toplevel",
    )
    process = run_process(command, cwd=repository_root, timeout=30)
    if process.returncode != 0:
        raise BridgePreflightError(
            "Git repository root verification",
            f"git rev-parse failed for {repository_root}",
            command=command,
            path=repository_root,
            stderr=process.stderr.strip(),
            exit_code=process.returncode,
        )
    reported = Path(process.stdout.strip()).resolve()
    if reported != repository_root:
        raise BridgePreflightError(
            "Git repository root verification",
            f"expected={repository_root}; reported={reported}",
            command=command,
            path=reported,
            exit_code=process.returncode,
        )


def require_no_unsupported_cwd(command: Sequence[str], repository_root: Path) -> None:
    if "--cwd" in command:
        raise BridgePreflightError(
            "unsupported argument construction",
            "the installed agy CLI does not support --cwd",
            command=command,
            rule="--cwd",
            path=repository_root,
        )


def agy_version(agy: Path, repository_root: Path) -> str:
    command = (str(agy), "--version")
    process = run_process(command, cwd=repository_root, timeout=30)
    if process.returncode != 0:
        raise BridgePreflightError(
            "Antigravity CLI version",
            f"command failed: {' '.join(command)}",
            command=command,
            path=agy,
            stderr=process.stderr.strip(),
            exit_code=process.returncode,
        )
    value = (process.stdout or process.stderr).strip()
    if not value:
        raise BridgePreflightError(
            "Antigravity CLI version",
            "agy --version returned no version text",
            command=command,
            path=agy,
            stderr=process.stderr.strip(),
            exit_code=process.returncode,
        )
    return value


def effective_model(requested: str, effort: str) -> str:
    requested = requested.strip()
    if not requested:
        raise DelegateError("The model override cannot be empty.")
    tiered = re.fullmatch(r"(.+)-(low|medium|high)", requested)
    if tiered and tiered.group(1).startswith("gemini-"):
        return f"{tiered.group(1)}-{effort}"
    if requested.startswith("gemini-") and not requested.endswith(
        ("-low", "-medium", "-high")
    ):
        return f"{requested}-{effort}"
    return requested


def git_text(root: Path, *arguments: str) -> str:
    process = run_process(
        ("git", "-c", f"safe.directory={root}", *arguments), cwd=root
    )
    if process.returncode != 0:
        raise DelegateError(
            f"Git command failed ({' '.join(arguments)}): {process.stderr.strip()}"
        )
    return process.stdout


def redact(text: str) -> str:
    if not text:
        return ""
    patterns = (
        (r"(?i)(authorization\s*[:=]\s*(?:bearer\s+)?)[^\s\"']+", r"\1[REDACTED]"),
        (r"(?i)(bearer\s+)[A-Za-z0-9._~+\-/=]+", r"\1[REDACTED]"),
        (
            r'(?i)([\"\']?(?:access_token|refresh_token|id_token|api_key|client_secret)[\"\']?\s*[:=]\s*[\"\']?)[^\s,\"\']+',
            r"\1[REDACTED]",
        ),
        (r"\bAIza[0-9A-Za-z_-]{20,}\b", "[REDACTED_GOOGLE_API_KEY]"),
    )
    result = text
    for pattern, replacement in patterns:
        result = re.sub(pattern, replacement, result)
    return result


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")


def write_json(path: Path, content: Any) -> None:
    write_text(path, json.dumps(content, indent=2, ensure_ascii=False) + "\n")


def emit_json(content: Any) -> None:
    """Emit console-safe JSON even when the Windows code page is not UTF-8."""
    print(json.dumps(content, ensure_ascii=True, separators=(",", ":")))


def validate_json(instance: Any, schema: dict[str, Any], location: str = "$") -> list[str]:
    """Validate the deliberately small JSON Schema subset used by this project."""
    errors: list[str] = []
    expected_type = schema.get("type")
    type_map = {
        "object": dict,
        "array": list,
        "string": str,
        "boolean": bool,
        "integer": int,
        "number": (int, float),
        "null": type(None),
    }
    if expected_type in type_map:
        expected = type_map[expected_type]
        valid = isinstance(instance, expected)
        if expected_type in {"integer", "number"} and isinstance(instance, bool):
            valid = False
        if not valid:
            return [f"{location}: expected {expected_type}"]
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{location}: expected constant {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{location}: value is not in {schema['enum']!r}")
    if isinstance(instance, str) and len(instance) < schema.get("minLength", 0):
        errors.append(f"{location}: string is shorter than minLength")
    if isinstance(instance, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                errors.append(f"{location}: missing required property {key!r}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in properties:
                    errors.append(f"{location}: unexpected property {key!r}")
        for key, value in instance.items():
            child_schema = properties.get(key)
            if child_schema:
                errors.extend(validate_json(value, child_schema, f"{location}.{key}"))
    if isinstance(instance, list) and isinstance(schema.get("items"), dict):
        for index, value in enumerate(instance):
            errors.extend(validate_json(value, schema["items"], f"{location}[{index}]"))
    return errors


def parse_json_response(raw: str) -> Any:
    value = raw.strip()
    if value.startswith("```json") and value.endswith("```"):
        value = value[7:-3].strip()
    elif value.startswith("```") and value.endswith("```"):
        value = value[3:-3].strip()
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise DelegateError(f"Antigravity response is not valid JSON: {exc}") from exc


def mode_instruction(mode: str) -> str:
    instructions = {
        "inspect": (
            "This is a strictly read-only investigation. Do not modify repository files, "
            "Git state, or physical devices. Return exact paths and concrete evidence."
        ),
        "implement": (
            "Edit only files explicitly listed under file ownership. Run only approved "
            "commands, preserve source firmware and evidence, and report the complete change set."
        ),
        "validate": (
            "Prefer read-only validation. Create logs or temporary outputs only in approved "
            "locations. Distinguish implementation defects, environment failures, tool "
            "limitations, and device-only checks."
        ),
        "review": (
            "Perform an independent read-only review. Inspect the contract, relevant files, "
            "Git diff, validation evidence, rollback safety, and documentation accuracy. "
            "Lead with concrete findings."
        ),
    }
    return instructions[mode]


def build_command(
    agy: Path,
    *,
    model: str,
    effort: str,
    mode: str,
    conversation_id: str | None,
    timeout: int,
    schema_path: Path,
    prompt: str,
) -> list[str]:
    command = [
        str(agy),
        "--model",
        model,
        "--effort",
        effort,
        "--mode",
        "accept-edits" if mode == "implement" else "plan",
        "--sandbox=false",
        "--disable-slash-commands",
        "--output-format",
        "json",
        "--json-schema",
        str(schema_path),
        "--print-timeout",
        f"{timeout}s",
    ]
    if conversation_id:
        command.extend(("--conversation", conversation_id))
    command.extend(("--print", prompt))
    return command


def compact_command(command: Sequence[str], task_file: Path) -> list[str]:
    safe = list(command)
    if "--print" in safe:
        prompt_index = safe.index("--print") + 1
        safe[prompt_index] = f"<bounded-task:{task_file.name}>"
    return safe


def conversation_from_output(raw: str, fallback: str | None) -> str | None:
    try:
        envelope = json.loads(raw.strip())
    except (json.JSONDecodeError, AttributeError):
        return fallback
    if isinstance(envelope, dict):
        value = envelope.get("conversation_id")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


def conversation_tool_calls(conversation_id: str | None) -> list[dict[str, Any]]:
    if not conversation_id:
        return []
    transcript = (
        antigravity_state_root()
        / "brain"
        / conversation_id
        / ".system_generated"
        / "logs"
        / "transcript_full.jsonl"
    )
    try:
        lines = transcript.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    calls: list[dict[str, Any]] = []
    for line in lines:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        for call in entry.get("tool_calls", []) if isinstance(entry, dict) else []:
            if isinstance(call, dict):
                calls.append(call)
    return calls


def last_inner_command(conversation_id: str | None) -> tuple[str | None, bool | None]:
    for call in reversed(conversation_tool_calls(conversation_id)):
        if call.get("name") != "run_command":
            continue
        arguments = call.get("args", {})
        if not isinstance(arguments, dict):
            continue
        value = arguments.get("CommandLine")
        bypass_value = arguments.get("BypassSandbox", False)
        bypass = bypass_value is True or str(bypass_value).casefold() == "true"
        return (str(value) if value is not None else None), bypass
    return None, None


def blocked_command_details(
    *,
    process: subprocess.CompletedProcess[str],
    outer_command: Sequence[str],
    repository_root: Path,
    conversation_id: str | None,
    project_id: str | None,
) -> dict[str, Any]:
    stderr = redact(process.stderr.strip())
    combined = process.stdout + "\n" + process.stderr
    permission_match = re.search(
        r"(?i)(?:required|requires).*?[\"']([a-z_]+)[\"']\s+permission", combined
    )
    requested_permission = permission_match.group(1) if permission_match else None
    inner_command, bypass_sandbox = last_inner_command(conversation_id)
    if requested_permission is None and bypass_sandbox is not None:
        requested_permission = "unsandboxed" if bypass_sandbox else "command"
    if bypass_sandbox is True or requested_permission == "unsandboxed":
        requested_mode = "unsandboxed"
    elif bypass_sandbox is False or requested_permission == "command":
        requested_mode = "sandboxed"
    else:
        requested_mode = "unknown"
    if requested_permission and inner_command:
        requested_resource = f"{requested_permission}({inner_command})"
    else:
        requested_resource = requested_permission
    return {
        "exact_command": inner_command or " ".join(outer_command),
        "requested_permission_resource": requested_resource,
        "requested_mode": requested_mode,
        "stderr": stderr,
        "exit_code": process.returncode,
        "project_id": project_id,
        "conversation_id": conversation_id,
        "effective_cwd": str(repository_root),
    }


def decode_worker_envelope(
    process: subprocess.CompletedProcess[str], schema: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        envelope = json.loads(process.stdout.strip())
    except json.JSONDecodeError as exc:
        raise DelegateError(f"Antigravity output envelope is invalid JSON: {exc}") from exc
    if not isinstance(envelope, dict):
        raise DelegateError("Antigravity output envelope is not a JSON object.")
    if str(envelope.get("status", "")).upper() != "SUCCESS":
        raise DelegateError(
            "Antigravity reported non-success status: "
            + str(envelope.get("status") or "missing")
        )
    structured = envelope.get("structured_output")
    response = envelope.get("response")
    if isinstance(structured, dict):
        result = structured
    elif isinstance(response, str):
        result = parse_json_response(response)
    elif isinstance(response, dict):
        result = response
    else:
        raise DelegateError("Antigravity structured output and response are missing or invalid.")
    if not isinstance(result, dict):
        raise DelegateError("Structured worker result is not a JSON object.")
    errors = validate_json(result, schema)
    if errors:
        raise DelegateError(
            "Structured result failed local schema validation: " + "; ".join(errors[:10])
        )
    return envelope, result


def run_bridge_preflight(
    *,
    agy: Path,
    repository_root: Path,
    model: str,
    effort: str,
    project_id: str | None,
) -> dict[str, Any]:
    preflight_started = time.monotonic()
    settings_path, settings = load_and_validate_settings(repository_root)
    supplemental_settings = validate_supplemental_permissions(
        repository_root, project_id
    )
    require_git_root_matches(repository_root)
    require_subprocess_cwd(repository_root)
    process_elevated = require_non_elevated_process(repository_root)
    cli_version = agy_version(agy, repository_root)

    git_command = ("git", "status", "--short", "--branch")
    git_before_process = run_process(git_command, cwd=repository_root, timeout=30)
    if git_before_process.returncode != 0:
        raise BridgePreflightError(
            "Git command preflight",
            "git status --short --branch failed",
            command=git_command,
            path=repository_root,
            stderr=git_before_process.stderr.strip(),
            exit_code=git_before_process.returncode,
        )
    git_before = git_before_process.stdout
    branch_process = run_process(
        ("git", "rev-parse", "--abbrev-ref", "HEAD"),
        cwd=repository_root,
        timeout=30,
    )
    if branch_process.returncode != 0:
        raise BridgePreflightError(
            "Git branch preflight",
            "git rev-parse --abbrev-ref HEAD failed",
            command=("git", "rev-parse", "--abbrev-ref", "HEAD"),
            path=repository_root,
            stderr=branch_process.stderr.strip(),
            exit_code=branch_process.returncode,
        )
    branch = branch_process.stdout.strip()

    python_command = ("python", "--version")
    python_process = run_process(python_command, cwd=repository_root, timeout=30)
    if python_process.returncode != 0:
        raise BridgePreflightError(
            "Python command preflight",
            "python --version failed",
            command=python_command,
            path=repository_root,
            stderr=python_process.stderr.strip(),
            exit_code=python_process.returncode,
        )
    python_version = (python_process.stdout or python_process.stderr).strip()

    auth_command = (str(agy), "--sandbox=false", "models")
    require_no_unsupported_cwd(auth_command, repository_root)
    auth = run_process(auth_command, cwd=repository_root, timeout=60)
    if auth.returncode != 0:
        details = blocked_command_details(
            process=auth,
            outer_command=auth_command,
            repository_root=repository_root,
            conversation_id=None,
            project_id=project_id,
        )
        raise BridgePreflightError(
            "Antigravity authentication",
            json.dumps(details, ensure_ascii=False),
            command=auth_command,
            path=agy,
            stderr=auth.stderr.strip(),
            exit_code=auth.returncode,
        )
    available_models = {
        line.strip() for line in auth.stdout.splitlines() if line.strip()
    }
    if model not in available_models:
        raise BridgePreflightError(
            "Antigravity authentication",
            f"authenticated, but required model is unavailable: {model}",
        )

    status_file = repository_root / "docs" / "m8" / "STATUS.md"
    uart_directories = (
        repository_root / "logs" / "device" / "20260801-165049",
        repository_root / "logs" / "device" / "20260801-170033",
    )
    for path in (status_file, *uart_directories):
        if not path.exists():
            raise BridgePreflightError(
                "repository read smoke input", f"missing path: {path}", path=path
            )
    temporary_file = (
        repository_root
        / ".orchestration"
        / "antigravity"
        / "runs"
        / "permission-smoke-test.tmp"
    ).resolve()
    if temporary_file.exists():
        raise BridgePreflightError(
            "temporary run file",
            f"refusing to overwrite existing path: {temporary_file}",
            path=temporary_file,
        )

    try:
        status_text = status_file.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise BridgePreflightError(
            "repository read preflight", str(exc), path=status_file
        ) from exc
    if not status_text.strip():
        raise BridgePreflightError(
            "repository read preflight", "STATUS.md is empty", path=status_file
        )

    uart_entries: dict[str, list[dict[str, Any]]] = {}
    for directory in uart_directories:
        try:
            entries = []
            for item in sorted(directory.iterdir(), key=lambda value: value.name.casefold()):
                entries.append(
                    {
                        "name": item.name,
                        "bytes": item.stat().st_size,
                        "type": "directory" if item.is_dir() else "file",
                    }
                )
        except OSError as exc:
            raise BridgePreflightError(
                "UART directory preflight", str(exc), path=directory
            ) from exc
        uart_entries[directory.relative_to(repository_root).as_posix()] = entries

    marker = "UBOX10 bridge preflight\n"
    created = False
    try:
        write_text(temporary_file, marker)
        created = True
        if temporary_file.read_text(encoding="utf-8") != marker:
            raise BridgePreflightError(
                "temporary write preflight",
                "temporary file content did not round-trip",
                path=temporary_file,
            )
        temporary_file.unlink()
        created = False
    except BridgePreflightError:
        raise
    except (OSError, UnicodeError) as exc:
        raise BridgePreflightError(
            "temporary write preflight", str(exc), path=temporary_file
        ) from exc
    finally:
        if created and temporary_file.exists():
            try:
                temporary_file.unlink()
            except OSError:
                pass

    git_after_process = run_process(git_command, cwd=repository_root, timeout=30)
    if git_after_process.returncode != 0:
        raise BridgePreflightError(
            "Git command post-preflight",
            "git status --short --branch failed after temporary write test",
            command=git_command,
            path=repository_root,
            stderr=git_after_process.stderr.strip(),
            exit_code=git_after_process.returncode,
        )
    if git_after_process.stdout != git_before:
        raise BridgePreflightError(
            "preflight repository state",
            "Git status changed during local bridge preflight",
            command=git_command,
            path=repository_root,
        )
    return {
        "status": "BRIDGE_PREFLIGHT_OK",
        "settings_path": str(settings_path),
        "supplemental_permission_paths": [str(path) for path in supplemental_settings],
        "repository_root": str(repository_root),
        "process_cwd": str(repository_root),
        "process_elevated": process_elevated,
        "agy_path": str(agy),
        "cli_version": cli_version,
        "unsupported_arguments_present": False,
        "terminal_sandbox_enabled": False,
        "tool_permission": settings.get("toolPermission"),
        "allow_non_workspace_access": settings.get("allowNonWorkspaceAccess", False),
        "cli_flags": ["--sandbox=false"],
        "project_id": project_id,
        "conversation_id": None,
        "exit_code": 0,
        "duration_seconds": round(time.monotonic() - preflight_started, 3),
        "effective_model": model,
        "effective_effort": effort,
        "branch": branch,
        "read_smoke": "passed",
        "write_smoke": "passed",
        "command_smoke": "passed",
        "git_command": "git status --short --branch",
        "python_version": python_version,
        "status_read": "passed",
        "uart_directories": uart_entries,
        "temporary_write": "passed",
        "git_state_unchanged": True,
        "permission_rules": settings.get("permissions", {}),
    }


def response_markdown(result: dict[str, Any], conversation_id: str | None) -> str:
    lines = [
        "# Antigravity worker response",
        "",
        f"- Status: {result.get('status', 'unknown')}",
        f"- Task completed: {result.get('task_completed', False)}",
    ]
    if conversation_id:
        lines.append(f"- Conversation ID: `{conversation_id}`")
    lines.extend(
        (
            "",
            "## Summary",
            "",
            str(result.get("summary", "")),
            "",
            "## Recommended next action",
            "",
            str(result.get("recommended_next_action", "")),
            "",
        )
    )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    if sys.version_info < MINIMUM_PYTHON:
        emit_json(
            {"status": "failed", "error": "Python 3.10 or newer is required."}
        )
        return 2

    args = parse_args(argv if argv is not None else sys.argv[1:])
    started = time.monotonic()
    run_dir: Path | None = None
    repository_root: Path | None = None
    task_file: Path | None = None
    stderr_parts: list[str] = []
    raw_stdout = ""
    worker_result: dict[str, Any] | None = None
    antigravity_status: str | None = None
    conversation_id: str | None = args.conversation_id
    token_usage: dict[str, Any] | None = None
    process_exit_code: int | None = None
    git_before = ""
    git_after = ""
    diff_stat = ""
    error: str | None = None
    preflight_failed = False
    preflight_result: dict[str, Any] | None = None
    preflight_conversation_id: str | None = None
    blocked_command: dict[str, Any] | None = None
    command: list[str] = []
    selected_model = effective_model(args.model, args.effort)
    agy: Path | None = None
    schema_path: Path | None = None
    project_id = saved_project_id()
    cli_version: str | None = None
    process_elevated: bool | None = None
    worker_permission_prompt: bool | None = None
    worker_unsandboxed_fallback: bool | None = None
    appcontainer_attempt: bool | None = None
    run_timestamp = dt.datetime.now(dt.timezone.utc).isoformat()

    try:
        if args.timeout <= 0:
            raise DelegateError("Timeout must be a positive number of seconds.")
        repository_root = resolve_repository_root()
        task_file = resolve_inside(repository_root, args.task_file, "Task file")
        if not task_file.is_file():
            raise DelegateError(f"Task file does not exist: {task_file}")
        output_parent = resolve_inside(repository_root, args.output_dir, "Output directory")
        schema_path = (
            Path(__file__).resolve().parents[3]
            / "references"
            / "result-schema.json"
        ).resolve()
        if not schema_path.is_file():
            raise DelegateError(f"Result schema is missing: {schema_path}")
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DelegateError(f"Result schema cannot be loaded: {exc}") from exc
        agy = find_agy()
        process_elevated = require_non_elevated_process(repository_root)
        cli_version = agy_version(agy, repository_root)
        task_text = task_file.read_text(encoding="utf-8")
        prompt = (
            "You are the bounded Antigravity worker for the UBOX10 repository. "
            "Follow the contract exactly, do not expand scope, and report uncertainty "
            "instead of guessing. Return only one JSON object matching the enforced schema.\n\n"
            f"OPERATING MODE: {args.mode}\n{mode_instruction(args.mode)}\n\n"
            "TASK CONTRACT\n\n"
            + task_text
        )
        command = build_command(
            agy,
            model=selected_model,
            effort=args.effort,
            mode=args.mode,
            conversation_id=args.conversation_id,
            timeout=args.timeout,
            schema_path=schema_path,
            prompt=prompt,
        )
        require_no_unsupported_cwd(command, repository_root)

        if args.dry_run:
            emit_json(
                {
                    "status": "dry-run",
                        "repository_root": str(repository_root),
                        "process_cwd": str(repository_root),
                    "task_file": str(task_file),
                    "output_directory": str(output_parent),
                    "agy": str(agy),
                    "cli_version": cli_version,
                    "terminal_sandbox_enabled": False,
                    "process_elevated": process_elevated,
                    "cli_flags": ["--sandbox=false"],
                    "model": selected_model,
                    "effort": args.effort,
                    "mode": args.mode,
                    "command": compact_command(command, task_file),
                }
            )
            return 0

        run_id = (
            dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            + "-"
            + re.sub(r"[^A-Za-z0-9_.-]+", "-", task_file.stem).strip("-")[:48]
            + "-"
            + uuid.uuid4().hex[:8]
        )
        run_dir = output_parent / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        write_text(run_dir / "task.md", redact(task_text))
        git_before = git_text(repository_root, "status", "--short", "--branch")
        write_text(run_dir / "git-status-before.txt", git_before)

        preflight_result = run_bridge_preflight(
            agy=agy,
            repository_root=repository_root,
            model=selected_model,
            effort=args.effort,
            project_id=project_id,
        )
        preflight_conversation_id = preflight_result.get("conversation_id")
        cli_version = preflight_result.get("cli_version")
        process_elevated = preflight_result.get("process_elevated")
        write_json(run_dir / "preflight.json", preflight_result)
        if args.preflight_only:
            process_exit_code = int(preflight_result.get("exit_code", 0))
            worker_result = {
                "status": "success",
                "summary": "The local Windows bridge preflight passed.",
                "task_completed": True,
                "files_read": [],
                "files_changed": [],
                "artifacts_created": [],
                "commands_run": [],
                "validation_results": [
                    {
                        "check": "bridge preflight",
                        "status": "passed",
                        "details": "See preflight.json for the exact checks and smoke evidence.",
                    }
                ],
                "evidence": [str(run_dir / "preflight.json")],
                "unresolved_issues": [],
                "risks": [],
                "assumptions": [],
                "recommended_next_action": "The bridge may invoke one bounded headless worker task.",
                "physical_device_actions_performed": False,
            }
            emit_json(preflight_result)
            return 0

        models_command = (str(agy), "--sandbox=false", "models")
        require_no_unsupported_cwd(models_command, repository_root)
        models_process = run_process(models_command, cwd=repository_root, timeout=60)
        stderr_parts.append(models_process.stderr)
        if models_process.returncode != 0:
            combined = (models_process.stdout + "\n" + models_process.stderr).lower()
            if any(marker in combined for marker in AUTH_MARKERS):
                raise DelegateError(
                    "Antigravity authentication is unavailable. Launch 'agy' interactively and sign in."
                )
            blocked_command = blocked_command_details(
                process=models_process,
                outer_command=models_command,
                repository_root=repository_root,
                conversation_id=None,
                project_id=project_id,
            )
            raise DelegateError(
                "Unable to list Antigravity models: "
                + json.dumps(blocked_command, ensure_ascii=False)
            )
        available_models = {
            line.strip() for line in models_process.stdout.splitlines() if line.strip()
        }
        if selected_model not in available_models:
            raise DelegateError(
                f"Requested model is unavailable: {selected_model}. No fallback was attempted."
            )

        cli_started = time.monotonic()
        try:
            process = run_process(
                command, cwd=repository_root, timeout=args.timeout + 30
            )
        except subprocess.TimeoutExpired as exc:
            if exc.stderr:
                stderr_parts.append(
                    exc.stderr.decode("utf-8", "replace")
                    if isinstance(exc.stderr, bytes)
                    else exc.stderr
                )
            raise DelegateError(
                f"Antigravity exceeded the {args.timeout}-second timeout."
            ) from exc
        cli_duration = time.monotonic() - cli_started
        process_exit_code = process.returncode
        raw_stdout = process.stdout
        stderr_parts.append(process.stderr)
        conversation_id = conversation_from_output(process.stdout, conversation_id)
        combined_process_output = (process.stdout + "\n" + process.stderr).lower()
        if "escalate_admin" in combined_process_output or "auto-denied" in combined_process_output:
            blocked_command = blocked_command_details(
                process=process,
                outer_command=command,
                repository_root=repository_root,
                conversation_id=conversation_id,
                project_id=project_id,
            )
            raise DelegateError(
                "Antigravity Windows profile violation: "
                + json.dumps(blocked_command, ensure_ascii=False)
            )
        if process.returncode != 0:
            combined = (process.stdout + "\n" + process.stderr).lower()
            if any(marker in combined for marker in AUTH_MARKERS):
                raise DelegateError(
                    "Antigravity authentication failed. Launch 'agy' interactively and sign in."
                )
            blocked_command = blocked_command_details(
                process=process,
                outer_command=command,
                repository_root=repository_root,
                conversation_id=conversation_id,
                project_id=project_id,
            )
            raise DelegateError(
                "Antigravity command failed: "
                + json.dumps(blocked_command, ensure_ascii=False)
            )
        try:
            envelope = json.loads(process.stdout.strip())
        except json.JSONDecodeError as exc:
            raise DelegateError(f"Antigravity output envelope is invalid JSON: {exc}") from exc
        if not isinstance(envelope, dict):
            raise DelegateError("Antigravity output envelope is not a JSON object.")
        antigravity_status = str(envelope.get("status", ""))
        conversation_id = envelope.get("conversation_id") or conversation_id
        usage_value = envelope.get("usage")
        token_usage = usage_value if isinstance(usage_value, dict) else None
        if antigravity_status.upper() != "SUCCESS":
            combined = (process.stdout + "\n" + process.stderr).lower()
            if "permission" in combined or "auto-denied" in combined:
                blocked_command = blocked_command_details(
                    process=process,
                    outer_command=command,
                    repository_root=repository_root,
                    conversation_id=conversation_id,
                    project_id=project_id,
                )
                raise DelegateError(
                    "Antigravity permission block: "
                    + json.dumps(blocked_command, ensure_ascii=False)
                )
            raise DelegateError(
                f"Antigravity reported non-success status: {antigravity_status or 'missing'}"
            )
        structured_value = envelope.get("structured_output")
        response_value = envelope.get("response")
        if isinstance(structured_value, dict):
            parsed_response = structured_value
        elif isinstance(response_value, str):
            if not response_value.strip() and "auto-denied" in process.stderr.lower():
                blocked_command = blocked_command_details(
                    process=process,
                    outer_command=command,
                    repository_root=repository_root,
                    conversation_id=conversation_id,
                    project_id=project_id,
                )
                raise DelegateError(
                    "Antigravity headless permission was auto-denied: "
                    + json.dumps(blocked_command, ensure_ascii=False)
                )
            parsed_response = parse_json_response(response_value)
        elif isinstance(response_value, dict):
            parsed_response = response_value
        else:
            raise DelegateError(
                "Antigravity structured output and response are both missing or invalid."
            )
        if not isinstance(parsed_response, dict):
            raise DelegateError("Structured worker result is not a JSON object.")
        if conversation_id:
            reported_id = parsed_response.get("conversation_id")
            if reported_id and reported_id != conversation_id:
                raise DelegateError("Worker and envelope conversation IDs do not match.")
            parsed_response["conversation_id"] = conversation_id
        validation_errors = validate_json(parsed_response, schema)
        if validation_errors:
            raise DelegateError(
                "Structured result failed local schema validation: "
                + "; ".join(validation_errors[:10])
            )
        worker_result = parsed_response
        if worker_result.get("status") != "success" or not worker_result.get(
            "task_completed"
        ):
            raise DelegateError(
                "Worker reported incomplete or failed work: "
                f"status={worker_result.get('status')!r}, "
                f"task_completed={worker_result.get('task_completed')!r}"
            )
        if worker_result.get("physical_device_actions_performed") is not False:
            raise DelegateError("Worker reported a prohibited physical-device action.")

        tool_calls = conversation_tool_calls(conversation_id)
        worker_permission_prompt = any(
            call.get("name") == "ask_permission" for call in tool_calls
        )
        worker_unsandboxed_fallback = any(
            call.get("name") == "run_command"
            and isinstance(call.get("args"), dict)
            and (
                call["args"].get("BypassSandbox") is True
                or str(call["args"].get("BypassSandbox", "")).casefold() == "true"
            )
            for call in tool_calls
        )
        appcontainer_attempt = "escalate_admin" in combined_process_output
        if worker_permission_prompt:
            raise DelegateError("Worker requested an interactive permission in headless mode.")
        if worker_unsandboxed_fallback:
            raise DelegateError("Worker requested an unsandboxed fallback.")

        git_after = git_text(repository_root, "status", "--short", "--branch")
        if args.mode in READ_ONLY_MODES and git_after != git_before:
            raise DelegateError(
                f"Read-only {args.mode} mode changed the repository working-tree state."
            )
        diff_stat = git_text(repository_root, "diff", "--stat", "--", ".")
        staged_stat = git_text(repository_root, "diff", "--cached", "--stat", "--", ".")
        if staged_stat:
            diff_stat += "\nSTAGED CHANGES\n" + staged_stat
        metadata_duration = envelope.get("duration_seconds", cli_duration)
        if isinstance(metadata_duration, (int, float)):
            cli_duration = float(metadata_duration)

    except BridgePreflightError as exc:
        preflight_failed = True
        if exc.check == "process elevation state":
            process_elevated = True
        preflight_conversation_id = exc.conversation_id
        process_exit_code = exc.exit_code
        error = f"{exc.check}: {exc.detail}"
        preflight_result = {
            "status": "BRIDGE_PREFLIGHT_FAILED",
            "check": exc.check,
            "detail": exc.detail,
            "failing_command": exc.command,
            "failing_path": exc.path,
            "failing_rule": exc.rule,
            "stderr": redact(exc.stderr),
            "exit_code": exc.exit_code,
            "repository_root": str(repository_root) if repository_root else None,
            "process_cwd": str(repository_root) if repository_root else None,
            "process_elevated": process_elevated,
            "terminal_sandbox_enabled": False,
            "cli_flags": ["--sandbox=false"],
            "settings_path": str(effective_settings_path()),
            "project_id": project_id,
            "conversation_id": exc.conversation_id or conversation_id,
        }
        if run_dir is not None:
            write_json(run_dir / "preflight.json", preflight_result)
    except (DelegateError, OSError, UnicodeError) as exc:
        error = str(exc)
    finally:
        if run_dir is not None and repository_root is not None:
            try:
                if not git_after:
                    git_after = git_text(
                        repository_root, "status", "--short", "--branch"
                    )
                if not diff_stat:
                    diff_stat = git_text(
                        repository_root, "diff", "--stat", "--", "."
                    )
            except DelegateError as git_exc:
                error = error or str(git_exc)
            if worker_result is not None:
                write_json(run_dir / "result.json", worker_result)
                write_text(
                    run_dir / "response.md",
                    response_markdown(worker_result, conversation_id),
                )
            else:
                write_json(
                    run_dir / "result.json",
                    {"status": "failed", "error": error or "Unknown failure"},
                )
                write_text(
                    run_dir / "response.md",
                    "# Antigravity worker response\n\n"
                    + (error or "No structured response was returned.")
                    + "\n",
                )
            write_text(run_dir / "stderr.log", redact("\n".join(stderr_parts)))
            write_text(run_dir / "stdout.log", redact(raw_stdout))
            write_text(run_dir / "git-status-after.txt", git_after)
            write_text(run_dir / "diff-stat.txt", diff_stat)
            metadata = {
                "started_at": run_timestamp,
                "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "duration_seconds": round(time.monotonic() - started, 3),
                "repository_root": str(repository_root),
                "task_file": str(task_file) if task_file else None,
                "run_directory": str(run_dir),
                "mode": args.mode,
                "requested_model": args.model,
                "effective_model": selected_model,
                "effective_effort": args.effort,
                "output_format": "json",
                "agy_path": str(agy) if agy else None,
                "cli_version": cli_version,
                "terminal_sandbox_enabled": False,
                "process_elevated": process_elevated,
                "cli_flags": [
                    value for value in command[1:] if value.startswith("--")
                ],
                "worker_permission_prompt": worker_permission_prompt,
                "worker_unsandboxed_fallback": worker_unsandboxed_fallback,
                "appcontainer_attempt": appcontainer_attempt,
                "process_exit_code": process_exit_code,
                "antigravity_status": antigravity_status,
                "conversation_id": conversation_id,
                "preflight_conversation_id": preflight_conversation_id,
                "project_id": project_id,
                "token_usage": token_usage,
                "settings_path": str(effective_settings_path()),
                "process_cwd": str(repository_root),
                "preflight": preflight_result,
                "blocked_command": blocked_command,
                "git_state_unchanged": git_before == git_after,
                "command": compact_command(command, task_file)
                if command and task_file
                else [],
                "error": error,
            }
            write_json(run_dir / "metadata.json", metadata)

    summary = {
        "status": "BRIDGE_PREFLIGHT_FAILED"
        if preflight_failed
        else ("failed" if error else "success"),
        "mode": args.mode,
        "model": selected_model,
        "effort": args.effort,
        "conversation_id": conversation_id,
        "total_tokens": token_usage.get("total_tokens") if token_usage else None,
        "run_directory": str(run_dir) if run_dir else None,
    }
    if error:
        summary["error"] = error
    emit_json(summary)
    return 1 if error else 0


if __name__ == "__main__":
    raise SystemExit(main())
