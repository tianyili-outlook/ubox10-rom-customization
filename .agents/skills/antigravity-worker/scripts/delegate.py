#!/usr/bin/env python3
"""CLI-only, contract-gated Antigravity worker launcher."""
from __future__ import annotations

import argparse, datetime as dt, fnmatch, hashlib, json, os, re, shutil, subprocess, tempfile, uuid
from pathlib import Path, PurePosixPath
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[4]
ORCH = ROOT / ".orchestration" / "antigravity"
CONTRACTS, RUNS, CACHE = ORCH / "contracts", ORCH / "runs", ORCH / "runs" / "bridge-session.json"
MODES, READ_ONLY = {"inspect", "implement", "validate", "review"}, {"inspect", "review"}
PROTECTED = (".git/**", "firmware/**", "candidates/**", "logs/device/**", "docs/m8/STATUS.md", "docs/m8/TODO.md", "docs/BUILD.md", "docs/DEVICE_TEST.md")
AUTH_MARKERS = ("not logged into antigravity", "authentication timed out", "failed to get oauth token")

class Error(RuntimeError):
    def __init__(self, status: str, detail: str): self.status, self.detail = status, detail

def emit(value: dict[str, Any]) -> None: print(json.dumps(value, ensure_ascii=True, separators=(",", ":")))
def run(args: Sequence[str], cwd: Path, env: dict[str, str] | None = None, timeout: int = 90):
    process = subprocess.run(list(args), cwd=str(cwd), env=env, shell=False, text=False, capture_output=True, timeout=timeout, check=False)
    decode = lambda value: value.decode("utf-8", errors="replace") if isinstance(value, bytes) else (value or "")
    return subprocess.CompletedProcess(process.args, process.returncode, decode(process.stdout), decode(process.stderr))
def rel(value: str, field: str) -> str:
    path = PurePosixPath(value.replace("\\", "/"))
    if not value or path.is_absolute() or ".." in path.parts or str(path) == ".": raise Error("BRIDGE_CONFIGURATION_FAILED", f"{field}: repository-relative path required")
    return path.as_posix()
def match(path: str, pattern: str) -> bool:
    """Match repository-relative POSIX paths by whole segments, from root."""
    path, pattern = rel(path, "path"), rel(pattern, "pattern")
    path_parts, pattern_parts = path.split("/"), pattern.split("/")
    def visit(path_index: int, pattern_index: int) -> bool:
        if pattern_index == len(pattern_parts): return path_index == len(path_parts)
        token = pattern_parts[pattern_index]
        if token == "**":
            return any(visit(index, pattern_index + 1) for index in range(path_index, len(path_parts) + 1))
        return path_index < len(path_parts) and fnmatch.fnmatchcase(path_parts[path_index], token) and visit(path_index + 1, pattern_index + 1)
    return visit(0, 0)
def inside(root: Path, value: Path, field: str) -> Path:
    value = value.resolve()
    try: value.relative_to(root.resolve())
    except ValueError as exc: raise Error("BRIDGE_CONFIGURATION_FAILED", f"{field}: outside allowed root") from exc
    return value
def agy() -> Path:
    found = shutil.which("agy")
    if found: return Path(found).resolve()
    candidate = Path(os.environ.get("LOCALAPPDATA", "")) / "agy" / "bin" / "agy.exe"
    if candidate.is_file(): return candidate.resolve()
    raise Error("BRIDGE_CONFIGURATION_FAILED", "agy is not on PATH")

def contract(argument: str, requested: str | None) -> tuple[Path, dict[str, Any]]:
    path = Path(argument); path = path if path.is_absolute() else ROOT / path; path = inside(CONTRACTS, path, "contract")
    try: data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc: raise Error("BRIDGE_CONFIGURATION_FAILED", f"contract JSON: {exc}") from exc
    if not isinstance(data, dict) or data.get("version") != 1 or data.get("mode") not in MODES or data.get("mode") != (requested or data.get("mode")): raise Error("BRIDGE_CONFIGURATION_FAILED", "contract version or mode is invalid")
    if not isinstance(data.get("id"), str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,80}", data["id"]): raise Error("BRIDGE_CONFIGURATION_FAILED", "contract id is invalid")
    if not isinstance(data.get("objective"), str) or not data["objective"].strip(): raise Error("BRIDGE_CONFIGURATION_FAILED", "contract objective is required")
    for key in ("read_paths", "writable_paths", "artifact_paths", "protected_paths"):
        if not isinstance(data.get(key, []), list) or not all(isinstance(v, str) for v in data[key]): raise Error("BRIDGE_CONFIGURATION_FAILED", f"contract {key} is invalid")
        data[key] = [rel(v, key) for v in data[key]]
    if not isinstance(data.get("approved_commands", []), list) or not all(isinstance(v, list) and v and all(isinstance(x, str) and x for x in v) for v in data["approved_commands"]): raise Error("BRIDGE_CONFIGURATION_FAILED", "contract approved_commands is invalid")
    if data["mode"] in READ_ONLY and any(not match(v, "tmp/**") for v in data["writable_paths"]): raise Error("BRIDGE_CONFIGURATION_FAILED", "read-only modes may write only tmp/**")
    blocked = [*PROTECTED, *data["protected_paths"]]
    for value in data["writable_paths"]:
        if any(match(value, item) for item in blocked): raise Error("BRIDGE_CONFIGURATION_FAILED", f"protected writable path: {value}")
    for value in data["artifact_paths"]:
        if not any(match(value, item) for item in data["writable_paths"]): raise Error("BRIDGE_CONFIGURATION_FAILED", f"artifact path is not writable: {value}")
    return path, data

def cli_cache(binary: Path) -> dict[str, Any]:
    try: saved = json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): saved = {}
    if saved.get("agy") == str(binary) and saved.get("authenticated") and saved.get("version"): return saved
    version = run((str(binary), "--version"), ROOT, timeout=30)
    if version.returncode: raise Error("BRIDGE_CONFIGURATION_FAILED", "agy --version failed: " + version.stderr.strip())
    # Authentication is determined by this single real CLI call. No login files are read.
    auth = run((str(binary), "--sandbox=false", "models"), ROOT, timeout=60)
    if auth.returncode: raise Error("BRIDGE_AUTH_FAILED", "agy authentication probe failed: " + (auth.stderr.strip() or auth.stdout.strip()))
    saved = {"agy": str(binary), "version": (version.stdout or version.stderr).strip(), "authenticated": True, "checked_at": dt.datetime.now(dt.timezone.utc).isoformat()}
    RUNS.mkdir(parents=True, exist_ok=True); CACHE.write_text(json.dumps(saved, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return saved

def stage(worktree: Path, paths: list[str]) -> None:
    for value in paths:
        source, target = inside(ROOT, ROOT / value, "read_paths"), inside(worktree, worktree / value, "read_paths")
        if not source.exists(): raise Error("BRIDGE_CONFIGURATION_FAILED", f"input missing: {value}")
        if source.is_dir() and not target.exists(): shutil.copytree(source, target)
        elif source.is_file() and not target.exists(): target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, target)

def tree(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob("*") if p.is_file() and ".git" not in p.relative_to(root).parts}
def changes(before: dict[str, str], after: dict[str, str]) -> list[str]: return sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
def violations(paths: list[str], data: dict[str, Any]) -> list[str]:
    blocked = [*PROTECTED, *data["protected_paths"]]; out = []
    for value in paths:
        if any(match(value, item) for item in blocked): out.append("protected:" + value)
        elif not any(match(value, item) for item in data["writable_paths"]): out.append("outside-writable-paths:" + value)
    return out
def prompt(data: dict[str, Any]) -> str:
    return "\n".join(("Run only in this disposable UBOX10 worktree.", "Objective: " + data["objective"], "Read paths: " + json.dumps(data["read_paths"]), "Writable paths: " + json.dumps(data["writable_paths"]), "Artifact paths: " + json.dumps(data["artifact_paths"]), "Protected paths: " + json.dumps([*PROTECTED, *data["protected_paths"]]), "Approved commands: " + json.dumps(data["approved_commands"]), "Do not access paths outside this worktree. Do not commit, push, flash, or apply a patch elsewhere. Return concise JSON; never output chain-of-thought."))
def invocation(binary: Path, data: dict[str, Any], timeout: int) -> list[str]:
    mode = "accept-edits" if data["mode"] in {"implement", "validate"} or data["writable_paths"] else "plan"
    return [str(binary), "--model", data.get("model", "gemini-3.6-flash-high"), "--effort", data.get("effort", "high"), "--mode", mode, "--sandbox=false", "--disable-slash-commands", "--output-format", "json", "--print-timeout", f"{timeout}s", "--print", prompt(data)]
def make_patch(worktree: Path, paths: list[str]) -> str:
    base = run(("git", "diff", "--binary", "--no-ext-diff"), worktree).stdout
    for value in paths:
        file = worktree / value
        if file.exists() and not (ROOT / value).exists(): base += run(("git", "diff", "--no-index", "--binary", "--", "/dev/null", value), worktree).stdout or ""
    return base
def temporary_checkout(holder: tempfile.TemporaryDirectory[str]) -> Path:
    checkout = Path(holder.name) / "checkout"
    cloned = run(("git", "clone", "--no-local", "--quiet", str(ROOT), str(checkout)), ROOT, timeout=120)
    if cloned.returncode: raise Error("BRIDGE_CONFIGURATION_FAILED", "temporary checkout creation failed: " + cloned.stderr.strip())
    return checkout
def git_state() -> str:
    state = run(("git", "status", "--porcelain=v1", "-z"), ROOT)
    if state.returncode: raise Error("BRIDGE_CONFIGURATION_FAILED", "cannot read primary Git state")
    return state.stdout

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("contract"); parser.add_argument("--mode", choices=sorted(MODES)); parser.add_argument("--timeout", type=int, default=900); parser.add_argument("--test-violation", action="store_true"); parser.add_argument("--test-runtime-tmp", action="store_true"); args = parser.parse_args(argv)
    worktree = None; holder = None; run_dir = None; primary_before = git_state(); result: dict[str, Any] = {"status": "BRIDGE_CONFIGURATION_FAILED"}
    try:
        contract_path, data = contract(args.contract, args.mode); binary = agy(); cli = cli_cache(binary)
        run_id = f"{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%SZ}-{data['id']}-{uuid.uuid4().hex[:8]}"; run_dir = RUNS / run_id; run_dir.mkdir(parents=True, exist_ok=False)
        holder = tempfile.TemporaryDirectory(prefix="ubox10-antigravity-cli-"); worktree = temporary_checkout(holder)
        tmp = worktree / "tmp"; tmp.mkdir(exist_ok=True)
        if shutil.disk_usage(worktree).free < 256 * 1024 * 1024: raise Error("BRIDGE_CONFIGURATION_FAILED", "insufficient disk space")
        stage(worktree, data["read_paths"]); before = tree(worktree); environment = os.environ.copy(); environment.update({"TEMP": str(tmp), "TMP": str(tmp), "TMPDIR": str(tmp)})
        if args.test_violation:
            # Deterministic bridge self-test: exercise the same post-run scanner
            # without requiring a live worker or an authentication session.
            (worktree / "contract-violation-sentinel.txt").write_text("sentinel\n", encoding="utf-8")
            process = subprocess.CompletedProcess([], 0, "", "")
        elif args.test_runtime_tmp:
            runtime = tmp / "unleash-repo-schema-v1-codeium-language-server.json"
            runtime.write_text("{}\n", encoding="utf-8")
            process = subprocess.CompletedProcess([], 0, "", "")
        else:
            process = run(invocation(binary, data, args.timeout), worktree, environment, args.timeout + 30)
        after = tree(worktree); touched = changes(before, after); bad = violations(touched, data); patch = make_patch(worktree, touched)
        artifacts = [{"path": p, "sha256": after.get(p), "bytes": (worktree / p).stat().st_size if (worktree / p).exists() else None} for p in touched if any(match(p, v) for v in data["artifact_paths"])]
        runtime_tmp_paths = [p for p in touched if match(p, "tmp/**")]
        (run_dir / "patch.diff").write_text(patch, encoding="utf-8", newline="\n"); (run_dir / "artifacts.json").write_text(json.dumps(artifacts, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        output = (process.stdout + "\n" + process.stderr).lower()
        status = "WORKER_CONTRACT_VIOLATION" if bad else ("BRIDGE_AUTH_FAILED" if process.returncode and any(marker in output for marker in AUTH_MARKERS) else ("TASK_FAILED" if process.returncode else "TASK_COMPLETED"))
        result = {"status": status, "run_id": run_id, "mode": data["mode"], "cli_version": cli["version"], "authenticated": True, "contract": str(contract_path.relative_to(ROOT)).replace("\\", "/"), "worktree": str(worktree), "tmp": str(tmp), "changed_paths": touched, "runtime_tmp_paths": runtime_tmp_paths, "artifacts": artifacts, "patch": str((run_dir / "patch.diff").relative_to(ROOT)).replace("\\", "/"), "error": "; ".join(bad) if bad else (process.stderr.strip() or process.stdout.strip() if process.returncode else None)}
    except Error as exc: result = {"status": exc.status, "error": exc.detail}
    except (OSError, subprocess.TimeoutExpired) as exc: result = {"status": "TASK_FAILED", "error": str(exc)}
    finally:
        if holder is not None: holder.cleanup()
        primary_changed = git_state() != primary_before
        if primary_changed and result.get("status") == "TASK_COMPLETED": result["status"] = "WORKER_CONTRACT_VIOLATION"; result["error"] = "primary working tree changed during worker run"
        if run_dir is not None: result["primary_worktree_changed"] = primary_changed; (run_dir / "result.json").write_text(json.dumps(result, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    emit(result); return 0 if result.get("status") == "TASK_COMPLETED" else 2
if __name__ == "__main__": raise SystemExit(main())
