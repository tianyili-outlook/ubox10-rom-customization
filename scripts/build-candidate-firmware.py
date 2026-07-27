#!/usr/bin/env python3
"""Build a minimal UBOX10 candidate described by a small JSON config."""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import uuid


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from ubox10_rom.ext4_image import read_manifest  # noqa: E402


OUT: Path
TOOLS = REPO / "tools"
PYTHON = sys.executable

INPUTS = {
    "system": (
        REPO / "out/official-system-a/20260726-r1/system_a.img",
        "B154BFE5DF8AED02C0765E5774B74EACD00F94D102305BEEE3CA2BD0C122BDAF",
    ),
    "product": (
        REPO / "out/official-product-a/20260726-r1/product_a.img",
        "361E798D5744665345C29EF9712D2EA41E0BB461AE906BD8CBE6DA9D99C1068E",
    ),
    "vendor": (
        REPO / "out/official-vendor-a/20260726-r1/vendor_a.img",
        "BB91A8B7ED4AC0145F434F89FD76865EB4311F234AA46D67C8373A7CD5B4929A",
    ),
    "vendor_dlkm": (
        REPO / "out/official-vendor-dlkm-a/20260726-r1/vendor_dlkm_a.img",
        "C589DC0B12E150469F179738F127F36F6321943577453A7DB335AB9E647B8FE5",
    ),
}

VENDOR_DLKM_MANIFEST = (
    REPO / "out/official-vendor-dlkm-a/20260726-r1/manifest.json"
)
VENDOR_DLKM_PARTITION_SIZE = 6680576
VENDOR_DLKM_SALT = (
    "523caf2a432189513d46cde728abaf1825f66e083ba17a9d812baa50d017820b"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def run(
    args: list[str],
    log_name: str,
    timeout_seconds: int = 900,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            args,
            cwd=REPO,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        (OUT / log_name).write_text(
            "$ "
            + subprocess.list2cmdline(args)
            + f"\n\nTIMEOUT after {timeout_seconds} seconds\n\nSTDOUT\n"
            + stdout
            + "\nSTDERR\n"
            + stderr,
            encoding="utf-8",
            newline="\n",
        )
        raise RuntimeError(f"{log_name} timed out after {timeout_seconds} seconds") from exc
    (OUT / log_name).write_text(
        "$ " + subprocess.list2cmdline(args) + "\n\nSTDOUT\n" + result.stdout + "\nSTDERR\n" + result.stderr,
        encoding="utf-8",
        newline="\n",
    )
    if result.returncode:
        raise RuntimeError(f"{log_name} failed with exit code {result.returncode}")
    return result


def wsl_path(path: Path) -> str:
    resolved = str(path.resolve())
    if not re.match(r"^[A-Za-z]:[\\/]", resolved):
        raise RuntimeError(f"cannot convert non-Windows path to WSL path: {path}")
    drive = resolved[0].lower()
    remainder = resolved[2:].replace("\\", "/")
    return f"/mnt/{drive}{remainder}"


def load_packer():
    path = TOOLS / "pack_image.py"
    spec = importlib.util.spec_from_file_location("ubox10_imagewty_packer", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load IMAGEWTY packer")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_candidate_config(path: Path) -> dict:
    resolved = path if path.is_absolute() else REPO / path
    resolved = resolved.resolve()
    try:
        resolved.relative_to(REPO.resolve())
    except ValueError as exc:
        raise RuntimeError("candidate config must be inside the repository") from exc
    config = json.loads(resolved.read_text(encoding="utf-8"))
    required = {"candidate_id", "firmware_filename", "remove_roots"}
    allowed = required | {
        "system_properties",
        "system_app_injections",
        "system_file_injections",
        "vendor_dlkm_binary_patches",
    }
    if not required.issubset(config) or not set(config).issubset(allowed):
        raise RuntimeError(
            f"candidate config keys must include {sorted(required)} "
            f"and may include {sorted(allowed - required)}"
        )
    if not isinstance(config["candidate_id"], str) or not config["candidate_id"]:
        raise RuntimeError("candidate_id must be a non-empty string")
    if Path(config["candidate_id"]).name != config["candidate_id"]:
        raise RuntimeError("candidate_id must be one path-safe name")
    if not isinstance(config["firmware_filename"], str) or not config["firmware_filename"].endswith(".img"):
        raise RuntimeError("firmware_filename must end with .img")
    roots = config["remove_roots"]
    if not isinstance(roots, list) or not roots or len(roots) != len(set(roots)):
        raise RuntimeError("remove_roots must be a non-empty list without duplicates")
    allowed_roots = (
        "/system/app/",
        "/system/priv-app/",
        "/system/system_ext/app/",
        "/system/system_ext/priv-app/",
    )
    known_runtime_dependencies = {
        "/system/priv-app/ContactsProvider": (
            "Android 12 BluetoothPbapService requires the com.android.contacts provider"
        ),
    }
    for root in roots:
        if (
            not isinstance(root, str)
            or not root.startswith(allowed_roots)
            or ".." in root.split("/")
        ):
            raise RuntimeError(f"unsafe removal root: {root!r}")
        if root in known_runtime_dependencies:
            raise RuntimeError(
                f"refusing known incompatible removal {root}: {known_runtime_dependencies[root]}"
            )
    properties = config.get("system_properties", {})
    if not isinstance(properties, dict):
        raise RuntimeError("system_properties must be an object")
    for key, value in properties.items():
        if (
            not isinstance(key, str)
            or not re.fullmatch(r"[A-Za-z0-9._-]+", key)
            or not isinstance(value, str)
            or "\n" in value
            or "\r" in value
        ):
            raise RuntimeError(f"invalid system property override: {key!r}")
    injections = config.get("system_app_injections", [])
    if not isinstance(injections, list):
        raise RuntimeError("system_app_injections must be a list")
    seen_destinations: set[str] = set()
    for injection in injections:
        if not isinstance(injection, dict) or set(injection) != {"source", "destination", "sha256"}:
            raise RuntimeError("each system_app_injection needs source, destination, and sha256")
        source = (REPO / injection["source"]).resolve()
        try:
            source.relative_to((REPO / "work" / "preinstall_apks").resolve())
        except (TypeError, ValueError) as exc:
            raise RuntimeError("injected APK source must be under work/preinstall_apks") from exc
        destination = injection["destination"]
        if (
            not isinstance(destination, str)
            or not re.fullmatch(r"/system/app/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+\.apk", destination)
            or destination in seen_destinations
        ):
            raise RuntimeError(f"unsafe or duplicate system APK destination: {destination!r}")
        expected = injection["sha256"]
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9A-Fa-f]{64}", expected):
            raise RuntimeError(f"invalid injected APK SHA-256: {expected!r}")
        if not source.is_file() or sha256(source) != expected.upper():
            raise RuntimeError(f"injected APK missing or SHA-256 mismatch: {source}")
        injection["_source"] = source
        seen_destinations.add(destination)
    file_injections = config.get("system_file_injections", [])
    if not isinstance(file_injections, list):
        raise RuntimeError("system_file_injections must be a list")
    for injection in file_injections:
        if not isinstance(injection, dict) or set(injection) != {"source", "destination", "sha256"}:
            raise RuntimeError("each system_file_injection needs source, destination, and sha256")
        source = (REPO / injection["source"]).resolve()
        try:
            source.relative_to((REPO / "assets" / "system_files").resolve())
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                "injected system file source must be under assets/system_files"
            ) from exc
        destination = injection["destination"]
        if (
            not isinstance(destination, str)
            or not re.fullmatch(
                r"/system/etc/permissions/[A-Za-z0-9._-]+\.xml",
                destination,
            )
            or destination in seen_destinations
        ):
            raise RuntimeError(f"unsafe or duplicate system file destination: {destination!r}")
        expected = injection["sha256"]
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9A-Fa-f]{64}", expected):
            raise RuntimeError(f"invalid injected system file SHA-256: {expected!r}")
        if not source.is_file() or sha256(source) != expected.upper():
            raise RuntimeError(f"injected system file missing or SHA-256 mismatch: {source}")
        injection["_source"] = source
        seen_destinations.add(destination)

    binary_patches = config.get("vendor_dlkm_binary_patches", [])
    if not isinstance(binary_patches, list):
        raise RuntimeError("vendor_dlkm_binary_patches must be a list")
    official_vendor_dlkm = json.loads(
        VENDOR_DLKM_MANIFEST.read_text(encoding="utf-8")
    )
    official_vendor_dlkm_entries = {
        entry["path"]: entry for entry in official_vendor_dlkm["entries"]
    }
    seen_patch_paths: set[str] = set()
    required_patch_keys = {
        "path",
        "source_sha256",
        "offset",
        "before_hex",
        "after_hex",
        "result_sha256",
    }
    for patch in binary_patches:
        if not isinstance(patch, dict) or set(patch) != required_patch_keys:
            raise RuntimeError(
                "each vendor_dlkm_binary_patch needs path, source_sha256, offset, "
                "before_hex, after_hex, and result_sha256"
            )
        target = patch["path"]
        if (
            not isinstance(target, str)
            or not re.fullmatch(r"/lib/modules/[A-Za-z0-9._-]+\.ko", target)
            or target in seen_patch_paths
        ):
            raise RuntimeError(
                f"unsafe or duplicate vendor_dlkm binary patch path: {target!r}"
            )
        entry = official_vendor_dlkm_entries.get(target)
        if entry is None or entry.get("type") != "regular":
            raise RuntimeError(
                f"vendor_dlkm binary patch target is not an official regular file: {target}"
            )
        source_sha256 = patch["source_sha256"]
        result_sha256 = patch["result_sha256"]
        for label, value in (
            ("source_sha256", source_sha256),
            ("result_sha256", result_sha256),
        ):
            if not isinstance(value, str) or not re.fullmatch(
                r"[0-9A-Fa-f]{64}", value
            ):
                raise RuntimeError(
                    f"invalid vendor_dlkm patch {label}: {value!r}"
                )
        if source_sha256.upper() != entry.get("content", {}).get("sha256"):
            raise RuntimeError(
                f"vendor_dlkm patch source SHA-256 does not match official manifest: {target}"
            )
        if result_sha256.upper() == source_sha256.upper():
            raise RuntimeError(
                f"vendor_dlkm patch result SHA-256 must differ from source: {target}"
            )
        offset = patch["offset"]
        if type(offset) is not int or offset < 0:
            raise RuntimeError(
                f"vendor_dlkm patch offset must be a non-negative integer: {target}"
            )
        before_hex = patch["before_hex"]
        after_hex = patch["after_hex"]
        if (
            not isinstance(before_hex, str)
            or not isinstance(after_hex, str)
            or not re.fullmatch(r"(?:[0-9A-Fa-f]{2}){1,32}", before_hex)
            or not re.fullmatch(r"(?:[0-9A-Fa-f]{2}){1,32}", after_hex)
            or len(before_hex) != len(after_hex)
            or before_hex.lower() == after_hex.lower()
        ):
            raise RuntimeError(
                f"invalid vendor_dlkm before/after byte sequence: {target}"
            )
        patch_length = len(before_hex) // 2
        logical_size = entry.get("content", {}).get("logical_size")
        if not isinstance(logical_size, int) or offset + patch_length > logical_size:
            raise RuntimeError(
                f"vendor_dlkm binary patch exceeds target size: {target}"
            )
        seen_patch_paths.add(target)
    config["_path"] = resolved
    return config


def apply_binary_patch(payload: bytes, patch: dict) -> bytes:
    """Apply one preconditioned in-file patch and return a new immutable payload."""

    offset = patch["offset"]
    before = bytes.fromhex(patch["before_hex"])
    after = bytes.fromhex(patch["after_hex"])
    observed = payload[offset : offset + len(before)]
    if observed != before:
        raise RuntimeError(
            f"vendor_dlkm patch precondition failed for {patch['path']} at "
            f"0x{offset:X}: {observed.hex().upper()} != {before.hex().upper()}"
        )
    modified = bytearray(payload)
    modified[offset : offset + len(after)] = after
    return bytes(modified)


def make_debugfs_commands(
    config: dict,
    build_prop_replacement: Path | None,
    selinux_value_file: Path,
) -> str:
    manifest_path = REPO / "out/official-system-a/20260726-r1/official-system-a-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = {entry["path"]: entry for entry in manifest["entries"]}
    selected: dict[str, dict] = {}
    for root in config["remove_roots"]:
        matches = {
            path: entry
            for path, entry in entries.items()
            if path == root or path.startswith(root + "/")
        }
        if root not in matches or matches[root]["type"] != "directory":
            raise RuntimeError(f"removal root is not an official directory: {root}")
        selected.update(matches)
    non_directories = sorted(
        (path for path, entry in selected.items() if entry["type"] != "directory"),
        key=lambda value: (value.count("/"), value),
        reverse=True,
    )
    directories = sorted(
        (path for path, entry in selected.items() if entry["type"] == "directory"),
        key=lambda value: (value.count("/"), value),
        reverse=True,
    )
    commands = "".join(f"rm {path}\n" for path in non_directories) + "".join(
        f"rmdir {path}\n" for path in directories
    )
    if build_prop_replacement is not None:
        commands += (
            "rm /system/build.prop\n"
            f"write {wsl_path(build_prop_replacement)} /system/build.prop\n"
            "set_inode_field /system/build.prop mode 0100600\n"
            "set_inode_field /system/build.prop uid 0\n"
            "set_inode_field /system/build.prop gid 0\n"
            f"ea_set -f {wsl_path(selinux_value_file)} /system/build.prop security.selinux\n"
        )
    for injection in config.get("system_app_injections", []):
        destination = injection["destination"]
        directory = destination.rsplit("/", 1)[0]
        commands += (
            f"mkdir {directory}\n"
            f"set_inode_field {directory} mode 040755\n"
            f"set_inode_field {directory} uid 0\n"
            f"set_inode_field {directory} gid 0\n"
            f"ea_set -f {wsl_path(selinux_value_file)} {directory} security.selinux\n"
            f"write {wsl_path(injection['_source'])} {destination}\n"
            f"set_inode_field {destination} mode 0100644\n"
            f"set_inode_field {destination} uid 0\n"
            f"set_inode_field {destination} gid 0\n"
            f"ea_set -f {wsl_path(selinux_value_file)} {destination} security.selinux\n"
        )
    for injection in config.get("system_file_injections", []):
        destination = injection["destination"]
        commands += (
            f"write {wsl_path(injection['_source'])} {destination}\n"
            f"set_inode_field {destination} mode 0100644\n"
            f"set_inode_field {destination} uid 0\n"
            f"set_inode_field {destination} gid 0\n"
            f"ea_set -f {wsl_path(selinux_value_file)} {destination} security.selinux\n"
        )
    return commands


def prepare_build_prop_replacement(config: dict, system: Path, e2fs: str) -> Path | None:
    overrides = config.get("system_properties", {})
    if not overrides:
        return None
    original = OUT / "system.build.prop.original"
    modified = OUT / "system.build.prop.modified"
    run(
        [
            "wsl.exe",
            "-d",
            "Ubuntu-24.04",
            "--",
            f"{e2fs}/debugfs",
            "-R",
            f"dump /system/build.prop {wsl_path(original)}",
            wsl_path(system),
        ],
        "02-dump-system-build-prop.log",
    )
    text = original.read_text(encoding="utf-8")
    for key, value in overrides.items():
        pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
        text, count = pattern.subn(f"{key}={value}", text)
        if count != 1:
            raise RuntimeError(f"expected exactly one existing system property {key}, found {count}")
    modified.write_text(text, encoding="utf-8", newline="\n")
    return modified


def apply_vendor_dlkm_binary_patches(
    config: dict,
    vendor_dlkm: Path,
    e2fs: str,
) -> None:
    """Patch allowlisted vendor modules and rebuild a verified no-FEC AVB footer."""

    patches = config.get("vendor_dlkm_binary_patches", [])
    if not patches:
        return

    official_manifest = json.loads(VENDOR_DLKM_MANIFEST.read_text(encoding="utf-8"))
    official_entries = {
        entry["path"]: entry for entry in official_manifest["entries"]
    }
    selinux_value_file = OUT / "security.selinux.vendor_file.bin"
    selinux_value_file.write_bytes(b"u:object_r:vendor_file:s0\0")

    run(
        [
            PYTHON,
            str(TOOLS / "avbtool.py"),
            "erase_footer",
            "--image",
            str(vendor_dlkm),
        ],
        "04a-vendor-dlkm-erase-footer.log",
    )

    commands: list[str] = []
    for index, patch in enumerate(patches, start=1):
        target = patch["path"]
        entry = official_entries[target]
        source = OUT / f"vendor-dlkm-{index}-{Path(target).name}.official"
        modified = OUT / f"vendor-dlkm-{index}-{Path(target).name}.patched"
        run(
            [
                "wsl.exe",
                "-d",
                "Ubuntu-24.04",
                "--",
                f"{e2fs}/debugfs",
                "-R",
                f"dump {target} {wsl_path(source)}",
                wsl_path(vendor_dlkm),
            ],
            f"04b-vendor-dlkm-dump-{index}.log",
        )
        if sha256(source) != patch["source_sha256"].upper():
            raise RuntimeError(
                f"vendor_dlkm patch source SHA-256 mismatch after dump: {target}"
            )
        patched_payload = apply_binary_patch(source.read_bytes(), patch)
        modified.write_bytes(patched_payload)
        if sha256(modified) != patch["result_sha256"].upper():
            raise RuntimeError(
                f"vendor_dlkm patch result SHA-256 mismatch: {target}"
            )

        xattrs = {item["name"]: item for item in entry.get("xattrs", [])}
        selinux_xattr = xattrs.get("security.selinux")
        if (
            set(xattrs) != {"security.selinux"}
            or selinux_xattr is None
            or base64.b64decode(selinux_xattr["value_b64"])
            != b"u:object_r:vendor_file:s0\0"
        ):
            raise RuntimeError(
                f"unsupported vendor_dlkm patch target xattrs: {target}"
            )
        inode_mode = 0o100000 | int(entry["mode_octal"], 8)
        commands.extend(
            [
                f"rm {target}\n",
                f"write {wsl_path(modified)} {target}\n",
                f"set_inode_field {target} mode {inode_mode:07o}\n",
                f"set_inode_field {target} uid {entry['uid']}\n",
                f"set_inode_field {target} gid {entry['gid']}\n",
                (
                    f"ea_set -f {wsl_path(selinux_value_file)} {target} "
                    "security.selinux\n"
                ),
            ]
        )

    command_file = OUT / "vendor-dlkm-debugfs.commands"
    command_file.write_text("".join(commands), encoding="utf-8", newline="\n")
    run(
        [
            "wsl.exe",
            "-d",
            "Ubuntu-24.04",
            "--",
            f"{e2fs}/debugfs",
            "-w",
            "-f",
            wsl_path(command_file),
            wsl_path(vendor_dlkm),
        ],
        "04c-vendor-dlkm-patch.log",
    )
    run(
        [
            "wsl.exe",
            "-d",
            "Ubuntu-24.04",
            "--",
            f"{e2fs}/e2fsck",
            "-fy",
            wsl_path(vendor_dlkm),
        ],
        "04d-vendor-dlkm-e2fsck.log",
    )
    run(
        [
            PYTHON,
            str(TOOLS / "avbtool.py"),
            "add_hashtree_footer",
            "--image",
            str(vendor_dlkm),
            "--partition_size",
            str(VENDOR_DLKM_PARTITION_SIZE),
            "--partition_name",
            "vendor_dlkm",
            "--hash_algorithm",
            "sha256",
            "--salt",
            VENDOR_DLKM_SALT,
            "--algorithm",
            "NONE",
            # The local AVB toolchain has no host `fec` binary. This keeps
            # dm-verity intact and matches the existing modified-system policy.
            "--do_not_generate_fec",
            "--prop",
            (
                "com.android.build.vendor_dlkm.fingerprint:"
                "Unblocktech/apollo_p1/apollo-p1:12/SP1A.211105.004/"
                "hush10241757:userdebug/test-keys"
            ),
            "--prop",
            "com.android.build.vendor_dlkm.os_version:12",
        ],
        "04e-vendor-dlkm-avb-footer.log",
    )


def preflight_wsl(e2fs: str) -> None:
    """Fail before creating a candidate directory if WSL cannot read the toolchain or inputs."""

    checks = [
        ["wsl.exe", "-d", "Ubuntu-24.04", "--", "test", "-x", f"{e2fs}/debugfs"],
        ["wsl.exe", "-d", "Ubuntu-24.04", "--", "test", "-x", f"{e2fs}/e2fsck"],
        ["wsl.exe", "-d", "Ubuntu-24.04", "--", "test", "-r", wsl_path(INPUTS["system"][0])],
        ["wsl.exe", "-d", "Ubuntu-24.04", "--", f"{e2fs}/debugfs", "-V"],
    ]
    for command in checks:
        try:
            result = subprocess.run(
                command,
                cwd=REPO,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                "WSL preflight timed out before candidate creation. "
                "Confirm that Ubuntu-24.04 starts normally."
            ) from exc
        if result.returncode:
            details = (result.stderr or result.stdout).strip()
            if "E_ACCESSDENIED" in details or "access" in details.lower():
                reason = "WSL access was denied by the host or execution sandbox"
            else:
                reason = details or f"exit code {result.returncode}"
            raise RuntimeError(
                "WSL preflight failed before candidate creation: "
                f"{reason}. Verify that Ubuntu-24.04 and the private e2fsprogs toolchain are accessible."
            )


def entry_semantics(entry: dict, *, include_content: bool = True) -> dict:
    value = {
        "type": entry.get("type"),
        "mode_octal": entry.get("mode_octal"),
        "uid": entry.get("uid"),
        "gid": entry.get("gid"),
        "xattrs": entry.get("xattrs", []),
    }
    if entry.get("type") != "directory":
        value["link_count"] = entry.get("link_count")
    if include_content and entry.get("type") == "regular":
        value["content"] = entry.get("content")
    if entry.get("type") == "symlink":
        value["symlink"] = entry.get("symlink")
    return value


def validate_vendor_dlkm_semantics(config: dict, vendor_dlkm: Path) -> dict:
    official = json.loads(VENDOR_DLKM_MANIFEST.read_text(encoding="utf-8"))
    candidate = read_manifest(vendor_dlkm)
    candidate["source"]["path"] = str(
        (
            REPO
            / "out"
            / "candidates"
            / config["candidate_id"]
            / vendor_dlkm.name
        ).resolve()
    )
    (OUT / "vendor-dlkm-manifest.json").write_text(
        json.dumps(candidate, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    official_entries = {entry["path"]: entry for entry in official["entries"]}
    candidate_entries = {entry["path"]: entry for entry in candidate["entries"]}
    if set(candidate_entries) != set(official_entries):
        missing = sorted(set(official_entries) - set(candidate_entries))[:10]
        added = sorted(set(candidate_entries) - set(official_entries))[:10]
        raise RuntimeError(
            "vendor_dlkm path set changed; "
            f"missing={missing}, unexpected_added={added}"
        )

    patches = {
        patch["path"]: patch
        for patch in config.get("vendor_dlkm_binary_patches", [])
    }
    changed_regular_files: list[str] = []
    for path in sorted(official_entries):
        before = official_entries[path]
        after = candidate_entries[path]
        is_patched = path in patches
        if entry_semantics(
            before, include_content=not is_patched
        ) != entry_semantics(after, include_content=not is_patched):
            raise RuntimeError(
                f"unexpected vendor_dlkm common-path semantic change: {path}"
            )
        if before.get("type") == "regular":
            before_sha256 = before.get("content", {}).get("sha256")
            after_sha256 = after.get("content", {}).get("sha256")
            if before_sha256 != after_sha256:
                changed_regular_files.append(path)
        if is_patched:
            expected_sha256 = patches[path]["result_sha256"].upper()
            if (
                after.get("content", {}).get("sha256") != expected_sha256
                or after.get("content", {}).get("logical_size")
                != before.get("content", {}).get("logical_size")
            ):
                raise RuntimeError(
                    f"vendor_dlkm patched content mismatch: {path}"
                )

    if changed_regular_files != sorted(patches):
        raise RuntimeError(
            "unexpected vendor_dlkm regular-file content changes: "
            f"{changed_regular_files}; expected {sorted(patches)}"
        )
    return {
        "changed_regular_files": changed_regular_files,
        "path_count": len(candidate_entries),
    }


def expected_added_paths(config: dict, official_paths: set[str]) -> set[str]:
    expected: set[str] = set()
    for injection in config.get("system_app_injections", []):
        destination = injection["destination"]
        expected.add(destination)
        parent = destination.rsplit("/", 1)[0]
        while parent not in official_paths:
            expected.add(parent)
            parent = parent.rsplit("/", 1)[0]
    for injection in config.get("system_file_injections", []):
        destination = injection["destination"]
        parent = destination.rsplit("/", 1)[0]
        if parent not in official_paths:
            raise RuntimeError(
                f"injected system file parent is not an official directory: {parent}"
            )
        expected.add(destination)
    return expected


def validate_system_semantics(config: dict, system: Path) -> dict:
    official_path = REPO / "out/official-system-a/20260726-r1/official-system-a-manifest.json"
    official = json.loads(official_path.read_text(encoding="utf-8"))
    candidate = read_manifest(system)
    candidate["source"]["path"] = str(
        (REPO / "out" / "candidates" / config["candidate_id"] / system.name).resolve()
    )
    (OUT / "system-manifest.json").write_text(
        json.dumps(candidate, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    official_entries = {entry["path"]: entry for entry in official["entries"]}
    candidate_entries = {entry["path"]: entry for entry in candidate["entries"]}
    expected_removed = {
        path
        for path in official_entries
        if any(path == root or path.startswith(root + "/") for root in config["remove_roots"])
    }
    actual_removed = set(official_entries) - set(candidate_entries)
    expected_added = expected_added_paths(config, set(official_entries))
    actual_added = set(candidate_entries) - set(official_entries)
    if actual_removed != expected_removed:
        missing = sorted(expected_removed - actual_removed)[:10]
        unexpected = sorted(actual_removed - expected_removed)[:10]
        raise RuntimeError(
            f"system semantic removal mismatch; not_removed={missing}, unexpected_removed={unexpected}"
        )
    if actual_added != expected_added:
        missing = sorted(expected_added - actual_added)[:10]
        unexpected = sorted(actual_added - expected_added)[:10]
        raise RuntimeError(
            f"system semantic addition mismatch; not_added={missing}, unexpected_added={unexpected}"
        )

    changed_regular_files: list[str] = []
    for path in sorted(set(official_entries) & set(candidate_entries)):
        before = official_entries[path]
        after = candidate_entries[path]
        include_content = path != "/system/build.prop"
        if entry_semantics(before, include_content=include_content) != entry_semantics(
            after, include_content=include_content
        ):
            raise RuntimeError(f"unexpected common-path semantic change: {path}")
        if (
            before.get("type") == "regular"
            and before.get("content", {}).get("sha256") != after.get("content", {}).get("sha256")
        ):
            changed_regular_files.append(path)
    expected_changed = ["/system/build.prop"] if config.get("system_properties") else []
    if changed_regular_files != expected_changed:
        raise RuntimeError(
            f"unexpected regular-file content changes: {changed_regular_files}; expected {expected_changed}"
        )

    for injection in config.get("system_app_injections", []):
        destination = injection["destination"]
        apk = candidate_entries[destination]
        xattrs = {item["name"]: item for item in apk.get("xattrs", [])}
        if (
            apk.get("mode_octal") != "0644"
            or apk.get("uid") != 0
            or apk.get("gid") != 0
            or apk.get("content", {}).get("sha256") != injection["sha256"].upper()
            or xattrs.get("security.selinux", {}).get("value_b64")
            != "dTpvYmplY3RfcjpzeXN0ZW1fZmlsZTpzMAA="
        ):
            raise RuntimeError(f"injected APK metadata mismatch: {destination}")

    for injection in config.get("system_file_injections", []):
        destination = injection["destination"]
        injected_file = candidate_entries[destination]
        xattrs = {item["name"]: item for item in injected_file.get("xattrs", [])}
        if (
            injected_file.get("mode_octal") != "0644"
            or injected_file.get("uid") != 0
            or injected_file.get("gid") != 0
            or injected_file.get("content", {}).get("sha256") != injection["sha256"].upper()
            or xattrs.get("security.selinux", {}).get("value_b64")
            != "dTpvYmplY3RfcjpzeXN0ZW1fZmlsZTpzMAA="
        ):
            raise RuntimeError(f"injected system file metadata mismatch: {destination}")

    if config.get("system_properties"):
        original = (OUT / "system.build.prop.original").read_text(encoding="utf-8").splitlines()
        modified = (OUT / "system.build.prop.modified").read_text(encoding="utf-8").splitlines()
        if len(original) != len(modified):
            raise RuntimeError("system.build.prop line count changed")
        changed_property_keys: set[str] = set()
        for before, after in zip(original, modified):
            if before == after:
                continue
            if "=" not in before or "=" not in after:
                raise RuntimeError("non-property line changed in system.build.prop")
            before_key = before.split("=", 1)[0]
            after_key, after_value = after.split("=", 1)
            if before_key != after_key or config["system_properties"].get(after_key) != after_value:
                raise RuntimeError(f"unexpected system.build.prop change: {before!r} -> {after!r}")
            changed_property_keys.add(after_key)
        if changed_property_keys != set(config["system_properties"]):
            raise RuntimeError(
                f"system property change set mismatch: {sorted(changed_property_keys)}"
            )

    return {
        "removed_paths": len(actual_removed),
        "added_paths": len(actual_added),
        "changed_regular_files": changed_regular_files,
    }


def validate_candidate(
    config: dict,
    system: Path,
    product: Path,
    vendor: Path,
    vendor_dlkm: Path,
    super_image: Path,
    firmware: Path,
    vbmeta: Path,
    vbmeta_system: Path,
    vbmeta_vendor: Path,
    e2fs: str,
) -> dict:
    run([PYTHON, "-m", "unittest", "discover", "-s", "tests", "-v"], "09-unit-tests.log")
    system_semantic_summary = validate_system_semantics(config, system)
    vendor_dlkm_semantic_summary = validate_vendor_dlkm_semantics(
        config, vendor_dlkm
    )
    run(
        ["wsl.exe", "-d", "Ubuntu-24.04", "--", f"{e2fs}/e2fsck", "-fn", wsl_path(system)],
        "10-e2fsck-readonly.log",
    )
    run(
        [
            "wsl.exe",
            "-d",
            "Ubuntu-24.04",
            "--",
            f"{e2fs}/e2fsck",
            "-fn",
            wsl_path(vendor_dlkm),
        ],
        "10b-vendor-dlkm-e2fsck-readonly.log",
    )

    avb_sources = {
        "vbmeta.img": vbmeta,
        "vbmeta_system.img": vbmeta_system,
        "vbmeta_vendor.img": vbmeta_vendor,
        "system.img": system,
        "vendor.img": vendor,
        "product.img": product,
        "vendor_dlkm.img": vendor_dlkm,
        "boot.img": REPO / "firmware/extracted/boot.fex",
        "vendor_boot.img": REPO / "firmware/extracted/vendor_boot.fex",
        "dtbo.img": REPO / "firmware/extracted/dtbo.fex",
    }
    with tempfile.TemporaryDirectory(prefix=".avb-validation-", dir=OUT) as directory:
        avb_dir = Path(directory)
        for name, source in avb_sources.items():
            os.link(source, avb_dir / name)
        key = wsl_path(TOOLS / "testkey_rsa2048.pem")
        run(
            [
                "wsl.exe",
                "-d",
                "Ubuntu-24.04",
                "--",
                "python3",
                wsl_path(TOOLS / "avbtool.py"),
                "verify_image",
                "--image",
                wsl_path(avb_dir / "vbmeta.img"),
                "--key",
                key,
                "--expected_chain_partition",
                f"vbmeta_system:1:{key}",
                "--expected_chain_partition",
                f"vbmeta_vendor:2:{key}",
                "--follow_chain_partitions",
            ],
            "11-avb-full-chain.log",
        )

    raw_super = OUT / ".super-validation.raw.img"
    try:
        run([str(TOOLS / "simg2img.exe"), str(super_image), str(raw_super)], "12-simg2img.log")
        lp_result = run(
            [str(TOOLS / "lpdumps.exe"), "--json", str(raw_super)],
            "13-lpdumps.log",
        )
        metadata = json.loads(lp_result.stdout.lstrip("\ufeff"))
        expected_partitions = {
            "system_a": 1651167232,
            "vendor_a": 119066624,
            "product_a": 111091712,
            "vendor_dlkm_a": 6680576,
        }
        observed = {
            item["name"]: int(item.get("size", 0))
            for item in metadata.get("partitions", [])
        }
        for name, size in expected_partitions.items():
            if observed.get(name) != size:
                raise RuntimeError(
                    f"super metadata mismatch for {name}: {observed.get(name)} != {size}"
                )
        (OUT / "super-metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    finally:
        raw_super.unlink(missing_ok=True)

    run(
        [PYTHON, str(TOOLS / "sunxi_image_tool.py"), "verify", str(firmware)],
        "14-imagewty-verify.log",
    )
    return {
        "status": "PASS",
        "system_semantics": system_semantic_summary,
        "vendor_dlkm_semantics": vendor_dlkm_semantic_summary,
        "ext4": "PASS",
        "vendor_dlkm_fec": (
            "disabled" if config.get("vendor_dlkm_binary_patches") else "official"
        ),
        "avb_full_chain": "PASS",
        "super_metadata": "PASS",
        "imagewty_checksums": "PASS",
        "unit_tests": "PASS",
    }


def build_in_staging(config: dict, final_out: Path, e2fs: str, staging: Path) -> int:
    global OUT
    OUT = staging

    system = OUT / "system_a.img"
    product = OUT / "product_a.img"
    vendor = OUT / "vendor_a.img"
    vendor_dlkm = OUT / "vendor_dlkm_a.img"
    shutil.copyfile(INPUTS["system"][0], system)
    shutil.copyfile(INPUTS["product"][0], product)
    shutil.copyfile(INPUTS["vendor"][0], vendor)
    shutil.copyfile(INPUTS["vendor_dlkm"][0], vendor_dlkm)

    run([PYTHON, str(TOOLS / "avbtool.py"), "erase_footer", "--image", str(system)], "01-erase-system-footer.log")
    build_prop_replacement = prepare_build_prop_replacement(config, system, e2fs)
    selinux_value_file = OUT / "security.selinux.system_file.bin"
    selinux_value_file.write_bytes(b"u:object_r:system_file:s0\0")
    commands = OUT / "debugfs.commands"
    commands.write_text(
        make_debugfs_commands(config, build_prop_replacement, selinux_value_file),
        encoding="utf-8",
        newline="\n",
    )
    run(
        ["wsl.exe", "-d", "Ubuntu-24.04", "--", f"{e2fs}/debugfs", "-w", "-f", wsl_path(commands), wsl_path(system)],
        "02-debugfs-remove.log",
    )
    run(
        ["wsl.exe", "-d", "Ubuntu-24.04", "--", f"{e2fs}/e2fsck", "-fy", wsl_path(system)],
        "03-e2fsck.log",
    )
    run(
        [
            PYTHON, str(TOOLS / "avbtool.py"), "add_hashtree_footer",
            "--image", str(system),
            "--partition_size", "1651167232",
            "--partition_name", "system",
            "--hash_algorithm", "sha256",
            "--salt", "849ad1a7d5dd18e1e29fdf0526f0b834d754bbe9286407ddcbaf3a18a32d9a26",
            "--do_not_generate_fec",
            "--algorithm", "NONE",
            "--prop", "com.android.build.system.fingerprint:Unblocktech/apollo_p1/apollo-p1:12/SP1A.211105.004/hush10241757:userdebug/test-keys",
            "--prop", "com.android.build.system.os_version:12",
            "--prop", "com.android.build.system.security_patch:2022-02-05",
        ],
        "04-system-avb-footer.log",
    )
    apply_vendor_dlkm_binary_patches(config, vendor_dlkm, e2fs)

    key = TOOLS / "testkey_rsa2048.pem"
    chain_key = "tools/testkey_rsa2048.pem"
    vbmeta_system = OUT / "vbmeta_system.img"
    vbmeta_vendor = OUT / "vbmeta_vendor.img"
    vbmeta = OUT / "vbmeta.img"
    run(
        [
            PYTHON, str(TOOLS / "avbtool.py"), "make_vbmeta_image",
            "--output", str(vbmeta_system), "--key", str(key), "--algorithm", "SHA256_RSA2048",
            "--rollback_index", "1644019200", "--include_descriptors_from_image", str(system),
        ],
        "05-vbmeta-system.log",
    )
    run(
        [
            PYTHON, str(TOOLS / "avbtool.py"), "make_vbmeta_image",
            "--output", str(vbmeta_vendor), "--key", str(key), "--algorithm", "SHA256_RSA2048",
            "--rollback_index", "1644019200", "--include_descriptors_from_image", str(vendor),
        ],
        "06-vbmeta-vendor.log",
    )
    run(
        [
            PYTHON, str(TOOLS / "avbtool.py"), "make_vbmeta_image",
            "--output", str(vbmeta), "--key", str(key), "--algorithm", "SHA256_RSA2048",
            "--rollback_index", "0",
            "--chain_partition", f"vbmeta_system:1:{chain_key}",
            "--chain_partition", f"vbmeta_vendor:2:{chain_key}",
            "--include_descriptors_from_image", str(REPO / "firmware/extracted/boot.fex"),
            "--include_descriptors_from_image", str(REPO / "firmware/extracted/dtbo.fex"),
            "--include_descriptors_from_image", str(REPO / "firmware/extracted/vendor_boot.fex"),
            "--include_descriptors_from_image", str(product),
            "--include_descriptors_from_image", str(vendor_dlkm),
        ],
        "07-vbmeta-main.log",
    )

    super_image = OUT / "super.img"
    run(
        [
            str(TOOLS / "lpmake.exe"),
            "--device-size", "3221225472",
            "--metadata-size", "65536",
            "--metadata-slots", "3",
            "--super-name", "super",
            "--virtual-ab",
            "--alignment", "1048576",
            "--sparse",
            "--group", "sb_a:3212836864",
            "--group", "sb_b:3212836864",
            "--partition", "system_a:readonly:1651167232:sb_a", "--image", f"system_a={system}",
            "--partition", "system_b:readonly:0:sb_b",
            "--partition", "vendor_a:readonly:119066624:sb_a", "--image", f"vendor_a={vendor}",
            "--partition", "vendor_b:readonly:0:sb_b",
            "--partition", "product_a:readonly:111091712:sb_a", "--image", f"product_a={product}",
            "--partition", "product_b:readonly:0:sb_b",
            "--partition", "vendor_dlkm_a:readonly:6680576:sb_a", "--image", f"vendor_dlkm_a={vendor_dlkm}",
            "--partition", "vendor_dlkm_b:readonly:0:sb_b",
            "--output", str(super_image),
        ],
        "08-lpmake.log",
    )

    firmware = OUT / config["firmware_filename"]
    packer = load_packer()
    packer.MANIFEST_PATH = str(REPO / "work/manifest.json")
    packer.EXTRACTED_DIR = str(REPO / "firmware/extracted")
    packer.OUTPUT_IMAGE = str(firmware)
    packer.MODIFIED_FILES = {
        "super.fex": str(super_image),
        "vbmeta.fex": str(vbmeta),
        "vbmeta_system.fex": str(vbmeta_system),
        "vbmeta_vendor.fex": str(vbmeta_vendor),
    }
    old_cwd = Path.cwd()
    try:
        os.chdir(REPO)
        packer.main()
    finally:
        os.chdir(old_cwd)

    validation = validate_candidate(
        config,
        system,
        product,
        vendor,
        vendor_dlkm,
        super_image,
        firmware,
        vbmeta,
        vbmeta_system,
        vbmeta_vendor,
        e2fs,
    )
    firmware_sha256 = sha256(firmware)
    result = {
        "candidate_id": config["candidate_id"],
        "config": str(config["_path"].relative_to(REPO)),
        "remove_roots": config["remove_roots"],
        "system_properties": config.get("system_properties", {}),
        "system_app_injections": [
            {
                "source": injection["source"],
                "destination": injection["destination"],
                "sha256": injection["sha256"].upper(),
            }
            for injection in config.get("system_app_injections", [])
        ],
        "system_file_injections": [
            {
                "source": injection["source"],
                "destination": injection["destination"],
                "sha256": injection["sha256"].upper(),
            }
            for injection in config.get("system_file_injections", [])
        ],
        "vendor_dlkm_binary_patches": [
            {
                "path": patch["path"],
                "source_sha256": patch["source_sha256"].upper(),
                "offset": patch["offset"],
                "before_hex": patch["before_hex"].upper(),
                "after_hex": patch["after_hex"].upper(),
                "result_sha256": patch["result_sha256"].upper(),
            }
            for patch in config.get("vendor_dlkm_binary_patches", [])
        ],
        "firmware": {
            "path": str((final_out / firmware.name).relative_to(REPO)),
            "bytes": firmware.stat().st_size,
            "sha256": firmware_sha256,
        },
        "validation": validation,
    }
    (OUT / "build-result.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    OUT.replace(final_out)
    published_firmware = final_out / firmware.name
    print(f"Candidate: {published_firmware}")
    print(f"SHA-256: {firmware_sha256}")
    print("Validation: PASS")
    return 0


def transactional_build(config: dict, final_out: Path, e2fs: str) -> int:
    """Publish only a fully built and validated candidate; remove failed staging output."""

    staging = create_staging_directory(final_out.parent, config["candidate_id"])
    try:
        return build_in_staging(config, final_out, e2fs, staging)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def create_staging_directory(parent: Path, candidate_id: str) -> Path:
    """Create a unique transaction directory while preserving normal Windows ACL inheritance."""

    for _ in range(100):
        staging = parent / f".{candidate_id}.building-{uuid.uuid4().hex[:8]}"
        try:
            staging.mkdir()
        except FileExistsError:
            continue
        return staging
    raise RuntimeError(f"unable to allocate a unique staging directory below {parent}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    config = load_candidate_config(args.config)
    final_out = REPO / "out" / "candidates" / config["candidate_id"]
    e2fs = "/home/tianyi/ubox10-toolchain/prefix/e2fsprogs-1.47.2-gcc13.3.0/sbin"

    if final_out.exists():
        raise RuntimeError(f"refusing to overwrite existing output: {final_out}")
    if not (REPO / "x12-1024.img").is_file() or not (REPO / "work/manifest.json").is_file():
        raise RuntimeError("official container or IMAGEWTY manifest is missing")
    required_tools = [
        TOOLS / "avbtool.py",
        TOOLS / "lpmake.exe",
        TOOLS / "lpdumps.exe",
        TOOLS / "simg2img.exe",
        TOOLS / "sunxi_image_tool.py",
        TOOLS / "pack_image.py",
        TOOLS / "testkey_rsa2048.pem",
    ]
    missing_tools = [str(path) for path in required_tools if not path.is_file()]
    if missing_tools:
        raise RuntimeError(f"required build tools are missing: {missing_tools}")

    preflight_wsl(e2fs)
    for name, (path, expected) in INPUTS.items():
        if not path.is_file() or sha256(path) != expected:
            raise RuntimeError(f"{name} input missing or SHA-256 mismatch: {path}")

    candidates = final_out.parent
    candidates.mkdir(parents=True, exist_ok=True)
    required_free_bytes = 7 * 1024**3
    available = shutil.disk_usage(candidates).free
    if available < required_free_bytes:
        raise RuntimeError(
            f"insufficient free space for transactional build: {available} bytes available, "
            f"{required_free_bytes} required"
        )
    return transactional_build(config, final_out, e2fs)


if __name__ == "__main__":
    raise SystemExit(main())
