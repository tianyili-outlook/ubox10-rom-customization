#!/usr/bin/env python3
"""Verify and install a source-locked APK bundle onto the Test8r2 baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any


REPO = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO / "configs/apps/test9.3-userdata-apps.json"
DEFAULT_ENDPOINT = "192.168.1.5:7896"
HEX64 = re.compile(r"^[0-9A-Fa-f]{64}$")
PACKAGE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+$")
APP_ID = re.compile(r"^[a-z0-9][a-z0-9.-]*$")
KNOWN_ABIS = {"armeabi", "armeabi-v7a", "arm64-v8a", "x86", "x86_64"}

BUNDLE_KEYS = {"schema_version", "bundle_id", "baseline", "apps"}
BASELINE_KEYS = {
    "candidate_id",
    "sdk",
    "required_abis",
    "required_features",
    "forbidden_features",
    "required_packages",
    "forbidden_packages",
    "home_activity",
}
APP_KEYS = {
    "id",
    "role",
    "name",
    "package",
    "version_code",
    "version_name",
    "min_sdk",
    "target_sdk",
    "launch_activity",
    "native_abis",
    "release_url",
    "download_url",
    "published_at",
    "license",
    "license_url",
    "filename",
    "local_path",
    "bytes",
    "sha256",
    "signer_sha256",
    "default_install",
    "source_note",
    "distribution_note",
}


class InstallError(RuntimeError):
    """Expected verification or installation failure."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def repo_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = REPO / path
    return path.resolve()


def require_repo_file(value: str, description: str) -> Path:
    path = repo_path(value)
    try:
        path.relative_to(REPO.resolve())
    except ValueError as exc:
        raise InstallError(f"{description} must be inside the repository: {value}") from exc
    if not path.is_file():
        raise InstallError(f"{description} does not exist: {path}")
    return path


def _string_list(value: Any, field: str, *, allow_empty: bool = True) -> list[str]:
    if (
        not isinstance(value, list)
        or (not allow_empty and not value)
        or any(not isinstance(item, str) or not item for item in value)
        or len(value) != len(set(value))
    ):
        qualifier = "" if allow_empty else " non-empty"
        raise InstallError(f"{field} must be a{qualifier} list of unique strings")
    return value


def _https(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.startswith("https://"):
        raise InstallError(f"{field} must be an https URL")
    return value


def load_bundle(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    resolved = path if path.is_absolute() else REPO / path
    resolved = resolved.resolve()
    try:
        resolved.relative_to(REPO.resolve())
    except ValueError as exc:
        raise InstallError("bundle config must be inside the repository") from exc
    try:
        bundle = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InstallError(f"cannot read bundle config: {resolved}") from exc

    if not isinstance(bundle, dict) or set(bundle) != BUNDLE_KEYS:
        raise InstallError(f"bundle config keys must be exactly {sorted(BUNDLE_KEYS)}")
    if bundle["schema_version"] != 1:
        raise InstallError("unsupported bundle schema_version")
    if not isinstance(bundle["bundle_id"], str) or not APP_ID.fullmatch(bundle["bundle_id"]):
        raise InstallError("bundle_id is not path-safe")

    baseline = bundle["baseline"]
    if not isinstance(baseline, dict) or set(baseline) != BASELINE_KEYS:
        raise InstallError(f"baseline keys must be exactly {sorted(BASELINE_KEYS)}")
    if (
        not isinstance(baseline["candidate_id"], str)
        or not baseline["candidate_id"]
        or type(baseline["sdk"]) is not int
        or baseline["sdk"] < 1
    ):
        raise InstallError("baseline candidate_id or sdk is invalid")
    required_abis = _string_list(
        baseline["required_abis"], "baseline.required_abis", allow_empty=False
    )
    if not set(required_abis).issubset(KNOWN_ABIS):
        raise InstallError("baseline.required_abis contains an unknown ABI")
    for key in (
        "required_features",
        "forbidden_features",
        "required_packages",
        "forbidden_packages",
    ):
        _string_list(baseline[key], f"baseline.{key}")
    for key in ("required_packages", "forbidden_packages"):
        if any(not PACKAGE.fullmatch(value) for value in baseline[key]):
            raise InstallError(f"baseline.{key} contains an invalid package")
    if set(baseline["required_features"]) & set(baseline["forbidden_features"]):
        raise InstallError("a feature cannot be both required and forbidden")
    if set(baseline["required_packages"]) & set(baseline["forbidden_packages"]):
        raise InstallError("a package cannot be both required and forbidden")
    if not isinstance(baseline["home_activity"], str) or "/" not in baseline["home_activity"]:
        raise InstallError("baseline.home_activity is invalid")

    apps = bundle["apps"]
    if not isinstance(apps, list) or not apps:
        raise InstallError("apps must be a non-empty list")
    seen_ids: set[str] = set()
    seen_packages: set[str] = set()
    seen_paths: set[Path] = set()
    apk_root = (REPO / "work/preinstall_apks").resolve()
    for index, app in enumerate(apps):
        prefix = f"apps[{index}]"
        if not isinstance(app, dict) or set(app) != APP_KEYS:
            raise InstallError(f"{prefix} keys must be exactly {sorted(APP_KEYS)}")
        if not isinstance(app["id"], str) or not APP_ID.fullmatch(app["id"]):
            raise InstallError(f"{prefix}.id is invalid")
        if app["id"] in seen_ids:
            raise InstallError(f"duplicate app id: {app['id']}")
        seen_ids.add(app["id"])
        if not isinstance(app["package"], str) or not PACKAGE.fullmatch(app["package"]):
            raise InstallError(f"{prefix}.package is invalid")
        if app["package"] in seen_packages:
            raise InstallError(f"duplicate package: {app['package']}")
        seen_packages.add(app["package"])
        for key in ("role", "name", "version_name", "launch_activity", "published_at"):
            if not isinstance(app[key], str) or not app[key]:
                raise InstallError(f"{prefix}.{key} must be a non-empty string")
        for key in ("version_code", "min_sdk", "target_sdk", "bytes"):
            if type(app[key]) is not int or app[key] < 1:
                raise InstallError(f"{prefix}.{key} must be a positive integer")
        if app["target_sdk"] < app["min_sdk"]:
            raise InstallError(f"{prefix}.target_sdk is below min_sdk")
        native_abis = _string_list(app["native_abis"], f"{prefix}.native_abis")
        if not set(native_abis).issubset(KNOWN_ABIS):
            raise InstallError(f"{prefix}.native_abis contains an unknown ABI")
        for key in ("release_url", "download_url", "license_url"):
            _https(app[key], f"{prefix}.{key}")
        if not isinstance(app["license"], str) or not app["license"]:
            raise InstallError(f"{prefix}.license is invalid")
        if (
            not isinstance(app["filename"], str)
            or Path(app["filename"]).name != app["filename"]
            or not app["filename"].lower().endswith(".apk")
        ):
            raise InstallError(f"{prefix}.filename is invalid")
        local_path = repo_path(app["local_path"])
        try:
            local_path.relative_to(apk_root)
        except (TypeError, ValueError) as exc:
            raise InstallError(
                f"{prefix}.local_path must be under work/preinstall_apks"
            ) from exc
        if local_path.suffix.lower() != ".apk" or local_path in seen_paths:
            raise InstallError(f"{prefix}.local_path is invalid or duplicated")
        seen_paths.add(local_path)
        for key in ("sha256", "signer_sha256"):
            if not isinstance(app[key], str) or not HEX64.fullmatch(app[key]):
                raise InstallError(f"{prefix}.{key} must be a SHA-256 hex digest")
            app[key] = app[key].upper()
        if type(app["default_install"]) is not bool:
            raise InstallError(f"{prefix}.default_install must be boolean")
        for key in ("source_note", "distribution_note"):
            if not isinstance(app[key], str) or not app[key]:
                raise InstallError(f"{prefix}.{key} must be a non-empty string")

    bundle["_config_path"] = resolved
    return bundle


def artifact_path(app: dict[str, Any]) -> Path:
    return repo_path(app["local_path"])


def relative_artifact_path(app: dict[str, Any]) -> str:
    return os.fspath(artifact_path(app).relative_to(REPO.resolve()))


def _candidate_sdk_tools(filename: str) -> list[Path]:
    candidates: list[Path] = []
    for variable in ("ANDROID_SDK_ROOT", "ANDROID_HOME"):
        root = os.environ.get(variable)
        if not root:
            continue
        build_tools = Path(root) / "build-tools"
        if build_tools.is_dir():
            candidates.extend(
                sorted(build_tools.glob(f"*/{filename}"), reverse=True)
            )
    return candidates


def find_tool(
    provided: str | None,
    name: str,
    repo_candidates: list[Path],
    sdk_filename: str | None = None,
) -> Path:
    candidates: list[Path] = []
    if provided:
        candidates.append(repo_path(provided))
    candidates.extend(repo_candidates)
    if sdk_filename:
        candidates.extend(_candidate_sdk_tools(sdk_filename))
    located = shutil.which(name)
    if located:
        candidates.append(Path(located))
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise InstallError(
        f"cannot find {name}; install Android SDK build-tools or pass its path explicitly"
    )


def command_for(tool: Path, args: list[str]) -> list[str]:
    if os.name == "nt" and tool.suffix.lower() in {".bat", ".cmd"}:
        return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", os.fspath(tool), *args]
    return [os.fspath(tool), *args]


def run_command(
    args: list[str],
    *,
    env: dict[str, str] | None = None,
    timeout: int = 120,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            args,
            cwd=REPO,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InstallError(f"command failed to execute: {subprocess.list2cmdline(args)}") from exc
    if check and result.returncode:
        details = (result.stdout + "\n" + result.stderr).strip()
        raise InstallError(
            f"command exited {result.returncode}: {subprocess.list2cmdline(args)}"
            + (f"\n{details}" if details else "")
        )
    return result


def parse_badging(output: str) -> dict[str, Any]:
    patterns = {
        "package": r"^package: name='([^']+)'",
        "version_code": r"^package:.* versionCode='(\d+)'",
        "version_name": r"^package:.* versionName='([^']+)'",
        "min_sdk": r"^sdkVersion:'(\d+)'",
        "target_sdk": r"^targetSdkVersion:'(\d+)'",
        "launch_activity": r"^launchable-activity: name='([^']+)'",
    }
    metadata: dict[str, Any] = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, output, re.MULTILINE)
        if not match:
            raise InstallError(f"aapt badging output is missing {key}")
        metadata[key] = match.group(1)
    for key in ("version_code", "min_sdk", "target_sdk"):
        metadata[key] = int(metadata[key])
    native = re.search(r"^native-code:\s+(.+)$", output, re.MULTILINE)
    metadata["native_abis"] = re.findall(r"'([^']+)'", native.group(1)) if native else []
    return metadata


def parse_signer(output: str) -> str:
    match = re.search(
        r"Signer #1 certificate SHA-256 digest:\s*([0-9A-Fa-f]{64})",
        output,
    )
    if not match:
        raise InstallError("apksigner output is missing the signer SHA-256")
    return match.group(1).upper()


def verify_metadata(app: dict[str, Any], metadata: dict[str, Any]) -> None:
    fields = (
        "package",
        "version_code",
        "version_name",
        "min_sdk",
        "target_sdk",
        "launch_activity",
    )
    for field in fields:
        if metadata[field] != app[field]:
            raise InstallError(
                f"{app['id']}: {field} mismatch: expected {app[field]!r}, "
                f"got {metadata[field]!r}"
            )
    if set(metadata["native_abis"]) != set(app["native_abis"]):
        raise InstallError(
            f"{app['id']}: native ABI mismatch: expected {app['native_abis']}, "
            f"got {metadata['native_abis']}"
        )


def java_environment(java_home: str | None) -> dict[str, str]:
    environment = os.environ.copy()
    candidates: list[Path] = []
    if java_home:
        candidates.append(repo_path(java_home))
    existing = os.environ.get("JAVA_HOME")
    if existing:
        candidates.append(Path(existing))
    candidates.append(
        REPO / "work/remote-service-migration/toolchain/jdk17/jdk-17.0.19+10"
    )
    for candidate in candidates:
        java = candidate / "bin/java.exe" if os.name == "nt" else candidate / "bin/java"
        if java.is_file():
            environment["JAVA_HOME"] = os.fspath(candidate.resolve())
            environment["PATH"] = os.fspath(java.parent.resolve()) + os.pathsep + environment["PATH"]
            return environment
    if shutil.which("java"):
        return environment
    raise InstallError("cannot find Java; pass --java-home for apksigner")


def verify_artifact(
    app: dict[str, Any],
    aapt: Path,
    apksigner: Path,
    signer_env: dict[str, str],
) -> dict[str, Any]:
    path = artifact_path(app)
    if not path.is_file():
        raise InstallError(
            f"{app['id']}: missing local APK {app['local_path']}; "
            f"download it from {app['download_url']}"
        )
    actual_bytes = path.stat().st_size
    if actual_bytes != app["bytes"]:
        raise InstallError(
            f"{app['id']}: byte-size mismatch: expected {app['bytes']}, got {actual_bytes}"
        )
    actual_sha = sha256(path)
    if actual_sha != app["sha256"]:
        raise InstallError(
            f"{app['id']}: SHA-256 mismatch: expected {app['sha256']}, got {actual_sha}"
        )

    relative = relative_artifact_path(app)
    badging_result = run_command(command_for(aapt, ["dump", "badging", relative]))
    metadata = parse_badging(badging_result.stdout + badging_result.stderr)
    verify_metadata(app, metadata)

    signer_result = run_command(
        command_for(apksigner, ["verify", "--verbose", "--print-certs", relative]),
        env=signer_env,
    )
    signer = parse_signer(signer_result.stdout + signer_result.stderr)
    if signer != app["signer_sha256"]:
        raise InstallError(
            f"{app['id']}: signer mismatch: expected {app['signer_sha256']}, got {signer}"
        )
    return {
        "id": app["id"],
        "package": app["package"],
        "version_name": app["version_name"],
        "version_code": app["version_code"],
        "bytes": actual_bytes,
        "sha256": actual_sha,
        "signer_sha256": signer,
        "native_abis": metadata["native_abis"],
        "status": "verified",
    }


def select_apps(bundle: dict[str, Any], requested: list[str] | None) -> list[dict[str, Any]]:
    by_id = {app["id"]: app for app in bundle["apps"]}
    if requested:
        unknown = [app_id for app_id in requested if app_id not in by_id]
        if unknown:
            raise InstallError(f"unknown app id(s): {', '.join(unknown)}")
        if len(requested) != len(set(requested)):
            raise InstallError("--app contains duplicates")
        return [by_id[app_id] for app_id in requested]
    return [app for app in bundle["apps"] if app["default_install"]]


def adb_run(
    adb: Path,
    serial: str,
    args: list[str],
    *,
    timeout: int = 120,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return run_command(
        command_for(adb, ["-s", serial, *args]),
        timeout=timeout,
        check=check,
    )


def adb_shell(adb: Path, serial: str, args: list[str]) -> str:
    return adb_run(adb, serial, ["shell", *args]).stdout.strip()


def package_path(adb: Path, serial: str, package_name: str) -> str:
    result = adb_run(
        adb,
        serial,
        ["shell", "pm", "path", package_name],
        check=False,
    )
    if result.returncode not in {0, 1}:
        details = (result.stdout + "\n" + result.stderr).strip()
        raise InstallError(
            f"cannot query package path for {package_name}"
            + (f": {details}" if details else "")
        )
    return result.stdout.strip()


def verify_baseline(
    adb: Path,
    serial: str,
    baseline: dict[str, Any],
    apps: list[dict[str, Any]],
) -> dict[str, Any]:
    state = adb_run(adb, serial, ["get-state"]).stdout.strip()
    if state != "device":
        raise InstallError(f"ADB device is not ready: {state!r}")
    boot_completed = adb_shell(adb, serial, ["getprop", "sys.boot_completed"])
    if boot_completed != "1":
        raise InstallError(f"device boot is not complete: sys.boot_completed={boot_completed!r}")
    sdk_text = adb_shell(adb, serial, ["getprop", "ro.build.version.sdk"])
    if not sdk_text.isdigit() or int(sdk_text) != baseline["sdk"]:
        raise InstallError(
            f"device SDK mismatch: expected {baseline['sdk']}, got {sdk_text!r}"
        )
    abilist = [
        value
        for value in adb_shell(
            adb, serial, ["getprop", "ro.product.cpu.abilist"]
        ).split(",")
        if value
    ]
    missing_abis = sorted(set(baseline["required_abis"]) - set(abilist))
    if missing_abis:
        raise InstallError(f"device is missing required ABI(s): {', '.join(missing_abis)}")
    for app in apps:
        if app["native_abis"] and not set(app["native_abis"]) & set(abilist):
            raise InstallError(
                f"{app['id']}: no APK native ABI matches device ABI list {abilist}"
            )

    features = {
        line.removeprefix("feature:")
        for line in adb_shell(adb, serial, ["pm", "list", "features"]).splitlines()
        if line.startswith("feature:")
    }
    missing_features = sorted(set(baseline["required_features"]) - features)
    forbidden_features = sorted(set(baseline["forbidden_features"]) & features)
    if missing_features:
        raise InstallError(f"device is missing feature(s): {', '.join(missing_features)}")
    if forbidden_features:
        raise InstallError(
            "device has feature(s) forbidden by the Test8r2 contract: "
            + ", ".join(forbidden_features)
        )

    for package_name in baseline["required_packages"]:
        if not package_path(adb, serial, package_name).startswith("package:"):
            raise InstallError(f"required baseline package is missing: {package_name}")
    for package_name in baseline["forbidden_packages"]:
        if package_path(adb, serial, package_name):
            raise InstallError(f"forbidden baseline package is present: {package_name}")

    home = adb_shell(
        adb,
        serial,
        [
            "cmd",
            "package",
            "resolve-activity",
            "--brief",
            "-a",
            "android.intent.action.MAIN",
            "-c",
            "android.intent.category.HOME",
        ],
    )
    if baseline["home_activity"] not in home:
        raise InstallError(
            f"default HOME mismatch: expected {baseline['home_activity']}, got {home!r}"
        )
    return {
        "serial": serial,
        "state": state,
        "boot_completed": boot_completed,
        "sdk": int(sdk_text),
        "abis": abilist,
        "home_activity": baseline["home_activity"],
        "baseline_candidate": baseline["candidate_id"],
        "status": "verified",
    }


def installed_version(output: str) -> tuple[int, str] | None:
    code = re.search(r"^\s*versionCode=(\d+)", output, re.MULTILINE)
    name = re.search(r"^\s*versionName=([^\r\n]+)", output, re.MULTILINE)
    if not code or not name:
        return None
    return int(code.group(1)), name.group(1).strip()


def installed_base_apk(package_output: str) -> str:
    paths = [
        line.removeprefix("package:").strip()
        for line in package_output.splitlines()
        if line.startswith("package:")
    ]
    if not paths:
        raise InstallError("installed package has no APK path")
    path = next((value for value in paths if value.endswith("/base.apk")), paths[0])
    if not re.fullmatch(r"/[A-Za-z0-9._~+/=-]+", path):
        raise InstallError(f"installed APK path contains unsafe characters: {path!r}")
    return path


def device_apk_sha256(adb: Path, serial: str, package_output: str) -> str:
    path = installed_base_apk(package_output)
    output = adb_shell(adb, serial, ["sha256sum", path])
    match = re.match(r"^([0-9A-Fa-f]{64})(?:\s|$)", output)
    if not match:
        raise InstallError(f"cannot parse device-side APK SHA-256 for {path}: {output!r}")
    return match.group(1).upper()


def install_app(
    adb: Path,
    serial: str,
    app: dict[str, Any],
    *,
    reinstall: bool,
    allow_downgrade: bool,
) -> dict[str, Any]:
    before_output = adb_shell(adb, serial, ["dumpsys", "package", app["package"]])
    before = installed_version(before_output)
    expected = (app["version_code"], app["version_name"])
    if before == expected and not reinstall:
        status = "already-current"
    else:
        if before and before[0] > app["version_code"] and not allow_downgrade:
            raise InstallError(
                f"{app['id']}: installed versionCode {before[0]} is newer than "
                f"locked versionCode {app['version_code']}; use --allow-downgrade explicitly"
            )
        arguments = ["install", "-r"]
        if allow_downgrade:
            arguments.append("-d")
        arguments.append(relative_artifact_path(app))
        result = adb_run(adb, serial, arguments, timeout=300)
        if "Success" not in result.stdout:
            raise InstallError(
                f"{app['id']}: adb install did not report Success: {result.stdout.strip()!r}"
            )
        status = "installed"

    installed_paths = package_path(adb, serial, app["package"])
    if not installed_paths.startswith("package:"):
        raise InstallError(f"{app['id']}: package path is missing after installation")
    after_output = adb_shell(adb, serial, ["dumpsys", "package", app["package"]])
    after = installed_version(after_output)
    if after != expected:
        raise InstallError(
            f"{app['id']}: installed version mismatch after install: "
            f"expected {expected}, got {after}"
        )
    installed_sha = device_apk_sha256(adb, serial, installed_paths)
    if installed_sha != app["sha256"]:
        raise InstallError(
            f"{app['id']}: installed base.apk SHA-256 mismatch: "
            f"expected {app['sha256']}, got {installed_sha}"
        )
    return {
        "id": app["id"],
        "package": app["package"],
        "before": (
            {"version_code": before[0], "version_name": before[1]} if before else None
        ),
        "after": {"version_code": after[0], "version_name": after[1]},
        "installed_sha256": installed_sha,
        "status": status,
    }


def write_report(path_value: str, report: dict[str, Any]) -> Path:
    path = repo_path(path_value)
    try:
        path.relative_to(REPO.resolve())
    except ValueError as exc:
        raise InstallError("--report path must be inside the repository") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=os.fspath(DEFAULT_CONFIG.relative_to(REPO)))
    parser.add_argument("--app", action="append", dest="apps", help="install one app id")
    parser.add_argument("--list", action="store_true", help="list bundle apps and exit")
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="verify local APK metadata, hash, and signer without using ADB",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="verify local APKs and Test8r2 device contract without installing",
    )
    parser.add_argument("--device", default=DEFAULT_ENDPOINT, help="ADB serial or TCP endpoint")
    parser.add_argument(
        "--no-connect",
        action="store_true",
        help="skip adb connect (use for an already attached USB device)",
    )
    parser.add_argument("--adb", help="path to adb")
    parser.add_argument("--aapt", help="path to aapt")
    parser.add_argument("--apksigner", help="path to apksigner")
    parser.add_argument("--java-home", help="JDK home used by apksigner")
    parser.add_argument(
        "--reinstall",
        action="store_true",
        help="run adb install -r even when the locked version is already installed",
    )
    parser.add_argument(
        "--allow-downgrade",
        action="store_true",
        help="allow adb install -d when a newer version is already installed",
    )
    parser.add_argument(
        "--launch",
        metavar="APP_ID",
        help="launch one selected app after successful installation",
    )
    parser.add_argument("--report", help="write a JSON report inside the repository")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    bundle = load_bundle(Path(args.config))
    apps = select_apps(bundle, args.apps)

    if args.list:
        for app in bundle["apps"]:
            marker = "default" if app["default_install"] else "optional"
            print(
                f"{app['id']:<18} {app['version_name']:<10} "
                f"{app['package']:<34} {marker}"
            )
        return 0
    if not apps:
        raise InstallError("no apps selected")
    if args.launch and args.launch not in {app["id"] for app in apps}:
        raise InstallError("--launch APP_ID must also be selected for this run")

    aapt = find_tool(
        args.aapt,
        "aapt",
        [
            REPO
            / "work/remote-service-migration/toolchain/build-tools31/android-12/aapt.exe"
        ],
        "aapt.exe" if os.name == "nt" else "aapt",
    )
    apksigner = find_tool(
        args.apksigner,
        "apksigner",
        [
            REPO
            / "work/remote-service-migration/toolchain/build-tools31/android-12/apksigner.bat"
        ],
        "apksigner.bat" if os.name == "nt" else "apksigner",
    )
    signer_env = java_environment(args.java_home)

    report: dict[str, Any] = {
        "schema_version": 1,
        "bundle_id": bundle["bundle_id"],
        "config": os.fspath(bundle["_config_path"].relative_to(REPO.resolve())),
        "mode": (
            "verify-only"
            if args.verify_only
            else "dry-run"
            if args.dry_run
            else "install"
        ),
        "artifacts": [],
        "device": None,
        "installations": [],
    }
    for app in apps:
        print(f"[verify] {app['id']} {app['version_name']}")
        report["artifacts"].append(
            verify_artifact(app, aapt, apksigner, signer_env)
        )

    if not args.verify_only:
        adb = find_tool(
            args.adb,
            "adb",
            [REPO / "tools/platform-tools/adb.exe"],
        )
        if not args.no_connect and ":" in args.device:
            connection = run_command(command_for(adb, ["connect", args.device]))
            print(f"[adb] {connection.stdout.strip()}")
        print(f"[device] verify {bundle['baseline']['candidate_id']} on {args.device}")
        report["device"] = verify_baseline(
            adb, args.device, bundle["baseline"], apps
        )
        if not args.dry_run:
            for app in apps:
                print(f"[install] {app['id']} {app['version_name']}")
                installation = install_app(
                    adb,
                    args.device,
                    app,
                    reinstall=args.reinstall,
                    allow_downgrade=args.allow_downgrade,
                )
                report["installations"].append(installation)
                print(f"          {installation['status']}")
            if args.launch:
                app = next(item for item in apps if item["id"] == args.launch)
                component = f"{app['package']}/{app['launch_activity']}"
                adb_run(
                    adb,
                    args.device,
                    ["shell", "am", "start", "-W", "-n", component],
                )
                print(f"[launch] {args.launch}")

    if args.report:
        report_path = write_report(args.report, report)
        print(f"[report] {report_path}")
    print(
        f"[done] {len(report['artifacts'])} artifact(s) verified, "
        f"{len(report['installations'])} installation result(s)"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except InstallError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
