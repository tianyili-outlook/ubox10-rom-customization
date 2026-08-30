#!/usr/bin/env python3
"""Fail-closed static and built checks for the r7-diag3 metadata diagnostic."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/candidates/a16-prototype-b-r7-diag3-private-buffer-metadata.json"
CANDIDATE = ROOT / "out/candidates/a16-prototype-b-r7-diag3-private-buffer-metadata"
OVERLAY = ROOT / "configs/aosp/architecture-ceiling-a16/diagnostics/r7-hevc-diag3-private-buffer-metadata"
OLD_STAGES = {
    "CODEC_SELECT", "CODEC_OUTPUT", "NATIVE_WINDOW", "GRALLOC_ALLOC",
    "GRALLOC_HANDLE", "AHB_DESC", "RENDERENGINE_MAP", "NATIVE_CLIENT_BUFFER",
    "EGL_CREATE_IMAGE", "GL_GEN_TEXTURE", "GL_BIND_TEXTURE",
    "GL_EGL_IMAGE_TARGET", "BACKEND_TEXTURE",
}


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


def verify_external_evidence() -> None:
    root = Path(
        "/work/evidence/ubox10/r7-diag3-private-buffer-metadata/input/unpacked"
    )
    sums = root / "SHA256SUMS"
    if not sums.is_file() or root.resolve().is_relative_to(ROOT.resolve()):
        fail("diag3 evidence is unavailable or inside the repository")
    for line in sums.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split(maxsplit=1)
        relative = relative.lstrip("* ")
        path = root / relative
        if not path.is_file() or digest(path) != expected.upper():
            fail(f"diag3 evidence identity changed: {relative}")


def main() -> None:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    if cfg["id"] != "a16-prototype-b-r7-diag3-private-buffer-metadata":
        fail("wrong candidate ID")
    governance = cfg["governance"]
    if governance["gate3"] != "HOLD" or governance["r8_authorized"] is not False:
        fail("Gate 3/r8 governance changed")
    if cfg["base_candidate"]["sha256"] != (
        "6F67CAE0B8A445D4597DECE9D684A7099ADF3E4E046D54E635D269C9E9E483EE"
    ):
        fail("diag3 base is not exact diag2")

    patches = sorted((OVERLAY / "patches").glob("*.patch"))
    if len(patches) != 3:
        fail("diag3 must contain exactly three subsystem patches")
    patch_text = "\n".join(path.read_text(encoding="utf-8") for path in patches)
    allowed = {
        "hardware/aw/gpu/mali-bifrost/gralloc/src/mali_gralloc_bufferallocation.cpp",
        "hardware/aw/gpu/mali-bifrost/gralloc/src/mali_gralloc_reference.cpp",
        "hardware/aw/gpu/mali-bifrost/gralloc/src/ubox_r7_diag3_private_handle.h",
        "media/libstagefright/ACodec.cpp",
        "media/libstagefright/include/media/stagefright/ACodec.h",
        "media/libstagefright/UBOXR7Diag3PrivateHandle.h",
        "src/gpu/ganesh/gl/AHardwareBufferGL.cpp",
        "src/gpu/ganesh/gl/UBOXR7Diag3PrivateHandle.h",
    }
    changed = {
        line[6:] for line in patch_text.splitlines()
        if line.startswith("+++ b/")
    }
    if changed != allowed:
        fail(f"diag3 source delta expanded: {sorted(changed)}")
    required = (
        "UBOX_R7_DIAG3", '"ALLOC_INITIAL"', '"REMOTE_IMPORT"',
        '"CODEC_PRE_USE"', '"CODEC_POST_FBD"', '"EGL_PREIMPORT"',
        "PROT_READ, MAP_SHARED", "fstat(", "HANDLE_RAW", "SIDECAR_ATTR",
    )
    if any(text not in patch_text for text in required):
        fail("diag3 observation boundary or read-only sidecar contract is absent")
    forbidden = (
        "PROT_WRITE", "MAP_PRIVATE", "eglGetError()", "glGetError()",
        "native_window_set_usage", "native_window_set_buffers_format",
        "mOutputFormat->setRect", "LOG_ALWAYS_FATAL_IF(false",
    )
    if any(text in patch_text for text in forbidden):
        fail("diag3 patch contains a forbidden semantic operation")

    for path in (
        ROOT / "configs/aosp/architecture-ceiling-a16/patches",
        ROOT / "configs/aosp/architecture-ceiling-a16/diagnostics/r7-hevc-diag1",
        ROOT / "configs/aosp/architecture-ceiling-a16/diagnostics/r7-hevc-diag1a",
        ROOT / "configs/aosp/architecture-ceiling-a16/diagnostics/r7-hevc-diag2-hevc-crop",
    ):
        if path.exists() and any(b"UBOX_R7_DIAG3" in item.read_bytes()
                                 for item in path.rglob("*") if item.is_file()):
            fail(f"diag3 contaminated a lower/canonical overlay: {path}")
    verify_external_evidence()

    if not CANDIDATE.exists():
        print("PASS_DIAG3_PRIVATE_BUFFER_METADATA_STATIC_ONLY")
        return

    image = CANDIDATE / f"x12-{cfg['id']}.img"
    build = json.loads((CANDIDATE / "build-result.json").read_text(encoding="utf-8"))
    audit = json.loads(
        (CANDIDATE / "offline-audit/offline-audit.json").read_text(encoding="utf-8")
    )
    if build["status"] != "OFFLINE_CHECKED" or audit["physical_status"] != "NOT_YET_VALIDATED":
        fail("diag3 incorrectly claims a physical result")
    if build["firmware"]["size"] != image.stat().st_size or build["firmware"]["sha256"] != digest(image):
        fail("diag3 image identity changed")
    if audit["compatibility"]["full_vintf_exit"] != 65:
        fail("inherited full-VINTF exception was reclassified")
    preservation = audit["preservation"]
    if preservation["result"] != "PASS_EXACT_FOUR_RUNTIME_FILE_OBSERVATION_ONLY_DELTA_FROM_DIAG2":
        fail("diag2-to-diag3 runtime delta is not exact")
    if preservation["arm32_graphics_sphal_closure"]["gralloc"]["unmatched_count"] != 0:
        fail("ARM32 VNDK31 strong-import closure failed")
    if preservation["graphics_sphal_closure"]["gralloc"]["unmatched_count"] != 0:
        fail("ARM64 VNDK31 strong-import closure failed")

    joined = b""
    permitted_imports = {
        "surfaceflinger": {"AHardwareBuffer_getNativeHandle"},
        "libstagefright64": {"mmap"},
        "gralloc32": {"__vsnprintf_chk", "fstat"},
        "gralloc64": {"__vsnprintf_chk", "fstat"},
    }
    for name, contract in cfg["runtime_files"].items():
        old = CANDIDATE / f"diag2-{name}"
        new = CANDIDATE / f"diag3-{name}"
        if digest(old) != contract["old_sha256"] or digest(new) != contract["sha256"]:
            fail(f"runtime identity changed: {name}")
        if strong_undefined(old) - strong_undefined(new):
            fail(f"diag3 removed a strong import: {name}")
        if strong_undefined(new) - strong_undefined(old) != permitted_imports[name]:
            fail(f"diag3 added an unexpected strong import: {name}")
        joined += new.read_bytes()
    for stage in OLD_STAGES | set(cfg["instrumentation"]["stages"]):
        if f"stage={stage}".encode() not in joined:
            fail(f"diagnostic stage absent: {stage}")
    if b"Failed to create a valid texture." not in (CANDIDATE / "diag3-surfaceflinger").read_bytes():
        fail("original RenderEngine fatal is absent")
    print("PASS_DIAG3_PRIVATE_BUFFER_METADATA_EXACT_FOUR_RUNTIME_FILE_DELTA")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
