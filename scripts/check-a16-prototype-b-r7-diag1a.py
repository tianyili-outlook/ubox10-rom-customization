#!/usr/bin/env python3
"""Fail-closed source, ELF-closure, marker, and single-delta checks for r7-diag1a."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


REPO = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO / "configs/candidates/a16-prototype-b-r7-diag1a.json"
DEFAULT_CANDIDATE = REPO / "out/candidates/a16-prototype-b-r7-diag1a"
DIAG1_CANDIDATE = REPO / "out/candidates/a16-prototype-b-r7-diag1"
DIAG1_CHECKER = REPO / "scripts/check-a16-prototype-b-r7-diag1.py"
GRAPHICS_CHECKER = REPO / "scripts/check-a16-prototype-b-r7-graphics.py"
PREFIX = b"UBOX_R7_DIAG1"
VERBOSE_ABORT = "_ZNSt3__122__libcpp_verbose_abortEPKcz"


def fail(message: str) -> None:
    raise RuntimeError(message)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest().upper()


def strong_undefined(path: Path) -> set[str]:
    output = subprocess.check_output(
        ["nm", "-D", "--undefined-only", "--format=posix", str(path)], text=True
    )
    return {
        fields[0].split("@", 1)[0]
        for line in output.splitlines()
        if len(fields := line.split()) >= 2 and fields[1] == "U"
    }


def require_record(path: Path, expected: dict[str, object], label: str) -> None:
    if not path.is_file():
        fail(f"{label} is absent: {path}")
    if path.stat().st_size != expected["size"] or digest(path) != expected["sha256"]:
        fail(f"{label} identity changed: {path}")


def source_checks(cfg: dict[str, object]) -> dict[str, object]:
    overlay = REPO / cfg["source_contract"]["boot_compatibility_overlay"]
    patches = sorted((overlay / "patches").glob("*.patch"))
    if [item.name for item in patches] != [
        "0001-gralloc-arm32-vndk31-libcpp-backdeploy.patch"
    ]:
        fail("diag1a must have exactly one boot-compatibility patch")
    patch = patches[0].read_text(encoding="utf-8")
    required = (
        "DIAGNOSTIC ONLY",
        "BOOT-COMPATIBILITY CORRECTION ONLY",
        "NOT AN HEVC REPAIR",
        "LOCAL_CPPFLAGS_32 += -include $(LOCAL_PATH)/vndk31_libcpp_backdeploy.h",
        "#if (defined(__aarch64__) || defined(__arm__)) && !defined(_LIBCPP_VERBOSE_ABORT)",
        "#define _LIBCPP_VERBOSE_ABORT(...) __builtin_abort()",
    )
    for text in required:
        if text not in patch:
            fail(f"diag1a compatibility patch lost reviewed text: {text}")
    changed_paths = {
        line[6:]
        for line in patch.splitlines()
        if line.startswith(("--- a/", "+++ b/"))
    }
    if changed_paths != {
        "hardware/aw/gpu/mali-bifrost/gralloc/src/Android.mk",
        "hardware/aw/gpu/mali-bifrost/gralloc/src/vndk31_libcpp_backdeploy.h",
    }:
        fail(f"diag1a source delta expanded: {sorted(changed_paths)}")
    if any(token in patch for token in (
        "mali_gralloc_bufferallocation.cpp",
        "mali_gralloc_reference.cpp",
        "AHardwareBufferGL.cpp",
        "LOG_ALWAYS_FATAL(",
    )):
        fail("diag1a patch changes diagnostic or fatal-path source")

    canonical = REPO / "configs/aosp/architecture-ceiling-a16/patches"
    for path in canonical.rglob("*"):
        if path.is_file() and b"UBOX_R7_DIAG1A" in path.read_bytes():
            fail(f"canonical r7 patch path contains diag1a: {path}")
    diag1_overlay = REPO / cfg["source_contract"]["overlay"]
    for path in diag1_overlay.rglob("*"):
        if path.is_file() and b"UBOX_R7_DIAG1A" in path.read_bytes():
            fail(f"diag1 instrumentation overlay contains diag1a: {path}")

    builder = (REPO / "scripts/build-a16-prototype-b-r7-diag1a-candidate.py").read_text()
    auditor = (REPO / "scripts/audit-a16-prototype-b-r7-diag1a.py").read_text()
    generic = GRAPHICS_CHECKER.read_text()
    if "self.run_arm32_closure(failed, corrected)" not in builder:
        fail("pre-package ARM32 closure guard is not wired into the builder")
    if "arm32_graphics_sphal_closure" not in auditor:
        fail("mounted-image ARM32 closure guard is not wired into the auditor")
    for text in (
        "undefined - provider_exports",
        'choices=("arm32", "arm64")',
        '"unmatched_strong_imports": unmatched',
    ):
        if text not in generic:
            fail(f"generic strong-import closure implementation changed: {text}")
    return {
        "diag1a_patch_count": 1,
        "source_delta": sorted(changed_paths),
        "canonical_r7_isolated": True,
        "diag1_overlay_isolated": True,
        "generic_strong_import_guard_wired_prepack_and_mounted": True,
    }


def candidate_checks(
    cfg: dict[str, object], candidate: Path
) -> dict[str, object]:
    build = json.loads((candidate / "build-result.json").read_text(encoding="utf-8"))
    audit = json.loads(
        (candidate / "offline-audit/offline-audit.json").read_text(encoding="utf-8")
    )
    if build["decision"] != "OFFLINE CHECKED / READY FOR PHYSICAL BOOT GATE":
        fail("diag1a build decision is not the reviewed offline result")
    if audit["decision"] != "OFFLINE CHECKED / READY FOR PHYSICAL BOOT GATE":
        fail("diag1a audit decision is not the reviewed offline result")
    if audit["physical_status"] != "NOT_YET_VALIDATED":
        fail("diag1a incorrectly claims a physical result")

    failed = candidate / "diag1-gralloc32"
    corrected = candidate / "diag1a-gralloc32"
    require_record(failed, cfg["diag1_delta"]["failed_gralloc32"], "failed diag1 gralloc")
    require_record(corrected, cfg["diag1_delta"]["corrected_gralloc32"], "corrected diag1a gralloc")
    failed_imports = strong_undefined(failed)
    corrected_imports = strong_undefined(corrected)
    if VERBOSE_ABORT not in failed_imports:
        fail("failed diag1 no longer proves its verbose-abort strong import")
    if VERBOSE_ABORT in corrected_imports:
        fail("corrected diag1a retains the unavailable verbose-abort strong import")
    if "abort" not in corrected_imports:
        fail("corrected diag1a does not retain abort semantics")

    closure = audit["preservation"]["arm32_graphics_sphal_closure"]
    before = closure["failed_diag1"]["gralloc"]
    after = closure["corrected_diag1a"]["gralloc"]
    if before["unmatched_strong_imports"] != [VERBOSE_ABORT]:
        fail("failed diag1 mounted closure no longer has the single proven mismatch")
    if after["unmatched_count"] != 0 or after["unmatched_strong_imports"]:
        fail("corrected diag1a has unmatched strong imports")
    if after["libcpp_verbose_abort_import"]:
        fail("corrected mounted gralloc still imports verbose-abort")

    preserved_files = {
        "/system/bin/surfaceflinger": candidate / "diag1a-surfaceflinger",
        "/system/lib64/libstagefright.so": candidate / "diag1a-libstagefright64",
        "/vendor/lib64/hw/gralloc.apollo.so": candidate / "diag1a-gralloc64",
    }
    for name, path in preserved_files.items():
        expected = cfg["diag1_delta"]["preserved_runtime_files"][name]
        if digest(path) != expected:
            fail(f"diag1a changed preserved diagnostic runtime: {name}")
    installed = [*preserved_files.values(), corrected]
    for path in installed:
        if PREFIX not in path.read_bytes():
            fail(f"diag1 diagnostic marker absent: {path.name}")
    strings = "\n".join(
        subprocess.check_output(["strings", str(path)], text=True) for path in installed
    )
    for stage in cfg["diagnostic"]["stages"]:
        if f"stage={stage}" not in strings:
            fail(f"diag1a lost diagnostic stage: {stage}")
    if "Failed to create a valid texture." not in strings:
        fail("diag1a no longer contains the original RenderEngine fatal text")

    preservation = audit["preservation"]
    if preservation["diag1_system_tree_delta"] != {
        "added": [], "removed": [], "changed": []
    }:
        fail("diag1a changed a diag1 system runtime file")
    if preservation["diag1_vendor_tree_delta"] != {
        "added": [], "removed": [], "changed": ["lib/hw/gralloc.apollo.so"]
    }:
        fail("diag1a vendor runtime delta is not exactly one file")
    if build["outer"]["changed_payloads"] != sorted(
        cfg["outer_delta"]["changed_payloads_from_base"]
    ):
        fail("diag1a packaging consequence expanded")

    image = Path(audit["candidate"]["path"])
    if image != candidate / f"x12-{cfg['id']}.img":
        fail("diag1a image path changed")
    require_record(image, audit["candidate"], "diag1a outer image")
    return {
        "failed_diag1_unmatched_strong_imports": before["unmatched_strong_imports"],
        "corrected_diag1a_unmatched_strong_imports": after["unmatched_strong_imports"],
        "runtime_delta_from_diag1": ["/vendor/lib/hw/gralloc.apollo.so"],
        "preserved_diag1_runtime_files": sorted(preserved_files),
        "diagnostic_stages_retained": cfg["diagnostic"]["stages"],
        "fatal_path_retained": True,
        "image": audit["candidate"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    if cfg["id"] != "a16-prototype-b-r7-diag1a":
        fail("wrong diag1a config")
    if cfg["base_candidate"]["id"] != "a16-prototype-b-r7-diag1":
        fail("diag1a is not based on exact failed diag1")
    governance = cfg["governance"]
    if governance["gate3"] != "HOLD" or governance["r8_authorized"] is not False:
        fail("diag1a changed Gate 3 or r8 governance")

    completed = subprocess.run(
        [sys.executable, str(DIAG1_CHECKER), "--candidate", str(DIAG1_CANDIDATE)],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode or "PASS_DIAGNOSTIC_ONLY_STATIC_ISOLATION" not in completed.stdout:
        fail("inherited diag1 static isolation failed: " + completed.stdout + completed.stderr)

    result: dict[str, object] = {
        "schema": 1,
        "candidate": cfg["id"],
        "decision": "PASS_DIAG1A_BOOT_COMPATIBILITY_SINGLE_DELTA",
        "source": source_checks(cfg),
        "inherited_diag1_static_isolation": "PASS",
        "hevc_repair_added": False,
        "r8": "NOT_AUTHORIZED_NOT_BUILT",
    }
    if args.candidate.is_dir():
        result["built_candidate"] = candidate_checks(cfg, args.candidate)
    else:
        result["built_candidate"] = "NOT_CHECKED_CANDIDATE_ABSENT"
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(result["decision"])


if __name__ == "__main__":
    main()
