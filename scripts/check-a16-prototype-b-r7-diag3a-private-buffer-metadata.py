#!/usr/bin/env python3
"""Fail-closed static and built checks for the r7-diag3a transparency correction."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/candidates/a16-prototype-b-r7-diag3a-private-buffer-metadata.json"
CANDIDATE = ROOT / "out/candidates/a16-prototype-b-r7-diag3a-private-buffer-metadata"
OVERLAY = ROOT / "configs/aosp/architecture-ceiling-a16/diagnostics/r7-hevc-diag3a-private-buffer-metadata"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest().upper()


def fail(message: str) -> None:
    raise RuntimeError(message)


def strong_undefined(path: Path) -> set[str]:
    output = subprocess.check_output(
        ["nm", "-D", "--undefined-only", "--format=posix", str(path)], text=True
    )
    return {
        fields[0].split("@", 1)[0]
        for line in output.splitlines()
        if len(fields := line.split()) >= 2 and fields[1] == "U"
    }


def verify_evidence(root: Path) -> None:
    sums = root / "SHA256SUMS"
    if not sums.is_file() or root.resolve().is_relative_to(ROOT.resolve()):
        fail("diag3 physical evidence is unavailable or inside the repository")
    for line in sums.read_text(encoding="utf-8").splitlines():
        if line.strip():
            expected, relative = line.split(maxsplit=1)
            path = root / relative.lstrip("* ")
            if not path.is_file() or digest(path) != expected.upper():
                fail(f"diag3 physical evidence changed: {relative}")


def main() -> None:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    if cfg["id"] != "a16-prototype-b-r7-diag3a-private-buffer-metadata":
        fail("wrong diag3a candidate ID")
    if cfg["governance"]["gate3"] != "HOLD" or cfg["governance"]["r8_authorized"] is not False:
        fail("Gate 3/r8 governance changed")
    patch_files = sorted((OVERLAY / "patches").glob("*.patch"))
    if len(patch_files) != 1:
        fail("diag3a must have exactly one patch")
    patch = patch_files[0].read_text(encoding="utf-8")
    changed = [line[6:] for line in patch.splitlines() if line.startswith("+++ b/")]
    if changed != ["media/libstagefright/UBOXR7Diag3PrivateHandle.h"]:
        fail(f"diag3a source delta expanded: {changed}")
    required = ("__builtin_mul_overflow", "wrapped_hash", "hash = wrapped_hash")
    forbidden = (
        "no_sanitize", "LOCAL_SANITIZE", "sanitize: {", "mOutputFormat->setRect",
        "native_window_set_usage", "PROT_WRITE", "eglGetError()", "glGetError()",
    )
    if any(item not in patch for item in required) or any(item in patch for item in forbidden):
        fail("diag3a patch is not the exact sanitizer-transparent FNV correction")
    for path in (
        ROOT / "configs/aosp/architecture-ceiling-a16/patches",
        ROOT / "configs/aosp/architecture-ceiling-a16/diagnostics/r7-hevc-diag1",
        ROOT / "configs/aosp/architecture-ceiling-a16/diagnostics/r7-hevc-diag1a",
        ROOT / "configs/aosp/architecture-ceiling-a16/diagnostics/r7-hevc-diag2-hevc-crop",
        ROOT / "configs/aosp/architecture-ceiling-a16/diagnostics/r7-hevc-diag3-private-buffer-metadata",
    ):
        if path.exists() and any(
            b"UBOX_R7_DIAG3A" in item.read_bytes() for item in path.rglob("*") if item.is_file()
        ):
            fail(f"diag3a contaminated a lower/canonical overlay: {path}")
    verify_evidence(Path(cfg["physical_evidence"]["path"]))

    fnv = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check-a16-prototype-b-r7-diag3a-fnv.py")],
        cwd=ROOT, text=True, capture_output=True, check=True,
    )
    if "PASS_DIAG3A_FNV64_EQUIVALENCE_AND_UBSAN_TRANSPARENCY" not in fnv.stdout:
        fail("FNV/UBSan host proof did not pass")

    if not CANDIDATE.exists():
        print("PASS_DIAG3A_STATIC_AND_FNV_ONLY")
        return
    image = CANDIDATE / f"x12-{cfg['id']}.img"
    build = json.loads((CANDIDATE / "build-result.json").read_text(encoding="utf-8"))
    audit = json.loads(
        (CANDIDATE / "offline-audit/offline-audit.json").read_text(encoding="utf-8")
    )
    if build["status"] != "OFFLINE_CHECKED" or build["physical_status"] != "NOT_YET_VALIDATED":
        fail("diag3a incorrectly claims physical validation")
    if build["firmware"]["size"] != image.stat().st_size or build["firmware"]["sha256"] != digest(image):
        fail("diag3a image identity changed")
    if audit["compatibility"]["full_vintf_exit"] != 65:
        fail("inherited full-VINTF exit 65 was reclassified")
    preservation = audit["preservation"]
    if preservation["result"] != "PASS_EXACT_ONE_RUNTIME_FILE_DIAGNOSTIC_DELTA_FROM_DIAG3":
        fail("diag3-to-diag3a runtime delta is not exact")
    if preservation["arm32_graphics_sphal_closure"]["gralloc"]["unmatched_count"] != 0:
        fail("ARM32 VNDK31 strong-import closure failed")
    if preservation["graphics_sphal_closure"]["gralloc"]["unmatched_count"] != 0:
        fail("ARM64 VNDK31 strong-import closure failed")

    changed_runtime: list[str] = []
    combined = b""
    for name in ("surfaceflinger", "libstagefright64", "gralloc32", "gralloc64"):
        old = CANDIDATE / f"diag3-{name}"
        new = CANDIDATE / f"diag3a-{name}"
        if digest(old) != digest(new):
            changed_runtime.append(name)
        if strong_undefined(old) != strong_undefined(new):
            fail(f"diag3a changed strong imports: {name}")
        combined += new.read_bytes()
    if changed_runtime != ["libstagefright64"]:
        fail(f"diag3a runtime delta expanded: {changed_runtime}")
    for marker in ("UBOX_R7_DIAG1", "UBOX_R7_DIAG3", *cfg["instrumentation"]["boundaries"]):
        if marker.encode() not in combined:
            fail(f"diag3a lost marker/boundary: {marker}")
    if b"Failed to create a valid texture." not in (CANDIDATE / "diag3a-surfaceflinger").read_bytes():
        fail("original RenderEngine fatal is absent")
    print("PASS_DIAG3A_EXACT_ONE_RUNTIME_FILE_TRANSPARENCY_DELTA")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
