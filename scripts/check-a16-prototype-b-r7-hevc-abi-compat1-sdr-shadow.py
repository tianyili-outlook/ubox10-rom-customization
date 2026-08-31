#!/usr/bin/env python3
"""Fail-closed static and built checks for the compat1 SDR shadow candidate."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/candidates/a16-prototype-b-r7-hevc-abi-compat1-sdr-shadow.json"
CANDIDATE = ROOT / "out/candidates/a16-prototype-b-r7-hevc-abi-compat1-sdr-shadow"
OVERLAY = ROOT / "configs/aosp/architecture-ceiling-a16/diagnostics/r7-hevc-abi-compat1-sdr-shadow"


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
        fail("diag3a physical evidence is unavailable or inside the repository")
    for line in sums.read_text(encoding="utf-8").splitlines():
        if line.strip():
            expected, relative = line.split(maxsplit=1)
            path = root / relative.lstrip("* ")
            if not path.is_file() or digest(path) != expected.upper():
                fail(f"diag3a physical evidence changed: {relative}")


def main() -> None:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    if cfg["id"] != "a16-prototype-b-r7-hevc-abi-compat1-sdr-shadow":
        fail("wrong compat1 candidate ID")
    governance = cfg["governance"]
    if (
        governance["gate3"] != "HOLD"
        or governance["r8_authorized"] is not False
        or governance["development_branch_created"] is not False
    ):
        fail("Gate 3/r8/development-branch governance changed")
    if cfg["compatibility"]["unsupported"] != ["Main10", "HDR", "AFBC", "protected", "4K"]:
        fail("compat1 unsupported-scope guard changed")

    patch_files = sorted((OVERLAY / "patches").glob("*.patch"))
    if len(patch_files) != 1:
        fail("compat1 must have exactly one patch")
    patch = patch_files[0].read_text(encoding="utf-8")
    changed = [line[6:] for line in patch.splitlines() if line.startswith("+++ b/")]
    if changed != [
        "src/gpu/ganesh/gl/AHardwareBufferGL.cpp",
        "src/gpu/ganesh/gl/UBOXR7Compat1Metadata.h",
    ]:
        fail(f"compat1 source delta expanded: {changed}")
    required = (
        "kMetadataSize = 0x6000", "kLegacyAttrOffset = 0x80",
        "kActiveAttrOffset = 23544", "kAttrSize = 56",
        "static_assert(sizeof(LegacyAttrRegion) == kAttrSize)",
        "memcpy(shadow, original, kMetadataSize)",
        "AHARDWAREBUFFER_CREATE_FROM_HANDLE_METHOD_CLONE",
        "mmap(nullptr, metadataSize, PROT_READ, MAP_SHARED, handle->data[1], 0)",
        "metadataStat.st_size != static_cast<off_t>(metadataSize)",
        "shadowStat.st_size != static_cast<off_t>(metadataSize)",
        "ashmem_create_region", "UBOX_R7_COMPAT1", "original_fd2_unchanged=1",
    )
    forbidden = (
        "memset(original", "PROT_READ | PROT_WRITE, MAP_SHARED, handle->data[1]",
        "native_window_set_", "mOutputFormat->setRect", "LOG_ALWAYS_FATAL_IF(false",
        "LOCAL_SANITIZE", "no_sanitize", "OMX.allwinner", "libGLES_mali.so",
    )
    if any(item not in patch for item in required):
        fail("compat1 patch lost an exact translation/ownership requirement")
    if any(item in patch for item in forbidden):
        fail("compat1 patch contains a forbidden semantic change")
    for path in (
        ROOT / "configs/aosp/architecture-ceiling-a16/patches",
        ROOT / "configs/aosp/architecture-ceiling-a16/diagnostics/r7-hevc-diag1",
        ROOT / "configs/aosp/architecture-ceiling-a16/diagnostics/r7-hevc-diag1a",
        ROOT / "configs/aosp/architecture-ceiling-a16/diagnostics/r7-hevc-diag2-hevc-crop",
        ROOT / "configs/aosp/architecture-ceiling-a16/diagnostics/r7-hevc-diag3-private-buffer-metadata",
        ROOT / "configs/aosp/architecture-ceiling-a16/diagnostics/r7-hevc-diag3a-private-buffer-metadata",
    ):
        if path.exists() and any(
            b"UBOX_R7_COMPAT1" in item.read_bytes() for item in path.rglob("*") if item.is_file()
        ):
            fail(f"compat1 contaminated a canonical/lower diagnostic overlay: {path}")
    verify_evidence(Path(cfg["physical_evidence"]["path"]))

    host = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check-a16-prototype-b-r7-compat1-metadata.py")],
        cwd=ROOT, text=True, capture_output=True, check=True,
    )
    if "original_unchanged=PASS" not in host.stdout:
        fail("compat1 host translation proof did not pass")

    if not CANDIDATE.exists():
        print("PASS_COMPAT1_STATIC_TRANSLATION_AND_CANONICAL_ISOLATION_ONLY")
        return
    image = CANDIDATE / f"x12-{cfg['id']}.img"
    build = json.loads((CANDIDATE / "build-result.json").read_text(encoding="utf-8"))
    audit = json.loads((CANDIDATE / "offline-audit/offline-audit.json").read_text(encoding="utf-8"))
    if build["status"] != "OFFLINE_CHECKED" or build["physical_status"] != "NOT_YET_VALIDATED":
        fail("compat1 incorrectly claims physical validation")
    if build["firmware"]["size"] != image.stat().st_size or build["firmware"]["sha256"] != digest(image):
        fail("compat1 image identity changed")
    if audit["compatibility"]["full_vintf_exit"] != 65:
        fail("inherited full-VINTF exit 65 was reclassified")
    preservation = audit["preservation"]
    if preservation["result"] != "PASS_EXACT_ONE_RUNTIME_FILE_EXPERIMENTAL_REPAIR_DELTA_FROM_DIAG3A":
        fail("diag3a-to-compat1 runtime delta is not exact")
    for closure in ("arm32_graphics_sphal_closure", "graphics_sphal_closure"):
        if preservation[closure]["gralloc"]["unmatched_count"] != 0:
            fail(f"{closure} has unmatched strong imports")

    changed_runtime: list[str] = []
    combined = b""
    expected_added = set(cfg["runtime_change"]["added_strong_imports"])
    for name in ("surfaceflinger", "libstagefright64", "gralloc32", "gralloc64"):
        old = CANDIDATE / f"diag3a-{name}"
        new = CANDIDATE / f"compat1-{name}"
        if digest(old) != digest(new):
            changed_runtime.append(name)
        old_imports, new_imports = strong_undefined(old), strong_undefined(new)
        if name == "surfaceflinger":
            if old_imports - new_imports or new_imports - old_imports != expected_added:
                fail("SurfaceFlinger strong-import delta changed")
        elif old_imports != new_imports:
            fail(f"compat1 changed strong imports: {name}")
        combined += new.read_bytes()
    if changed_runtime != ["surfaceflinger"]:
        fail(f"compat1 runtime delta expanded: {changed_runtime}")
    for marker in (
        "UBOX_R7_DIAG1", "UBOX_R7_DIAG3", "UBOX_R7_COMPAT1",
        *cfg["instrumentation"]["diag3_boundaries"],
        *cfg["instrumentation"]["compat1_records"],
    ):
        if marker.encode() not in combined:
            fail(f"compat1 lost marker/boundary: {marker}")
    if b"Failed to create a valid texture." not in (CANDIDATE / "compat1-surfaceflinger").read_bytes():
        fail("original RenderEngine fatal is absent")
    print("PASS_COMPAT1_EXACT_ONE_RUNTIME_FILE_SDR_SHADOW_DELTA")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
