#!/usr/bin/env python3
"""Fail-closed static and built checks for r7-diag2 HEVC crop diagnostic."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/candidates/a16-prototype-b-r7-diag2-hevc-crop.json"
CANDIDATE = ROOT / "out/candidates/a16-prototype-b-r7-diag2-hevc-crop"
OVERLAY = ROOT / "configs/aosp/architecture-ceiling-a16/diagnostics/r7-hevc-diag2-hevc-crop"
STAGES = {
    "CODEC_SELECT", "CODEC_OUTPUT", "NATIVE_WINDOW", "GRALLOC_ALLOC",
    "GRALLOC_HANDLE", "AHB_DESC", "RENDERENGINE_MAP", "NATIVE_CLIENT_BUFFER",
    "EGL_CREATE_IMAGE", "GL_GEN_TEXTURE", "GL_BIND_TEXTURE",
    "GL_EGL_IMAGE_TARGET", "BACKEND_TEXTURE",
}


def digest(path: Path) -> str:
    import hashlib
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


def main() -> None:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    if cfg["id"] != "a16-prototype-b-r7-diag2-hevc-crop":
        fail("wrong candidate ID")
    governance = cfg["governance"]
    if governance["gate3"] != "HOLD" or governance["r8_authorized"] is not False:
        fail("Gate 3/r8 governance changed")
    if cfg["semantic_delta"]["allocation_dimensions_unchanged"] != "1920x1088":
        fail("coded/allocation dimensions are not locked")

    patches = list((OVERLAY / "patches").glob("*.patch"))
    if len(patches) != 1:
        fail("diag2 must contain exactly one patch")
    patch = patches[0].read_text(encoding="utf-8")
    if patch.count("--- a/") != 1 or "media/libstagefright/ACodec.cpp" not in patch:
        fail("diag2 patch expanded beyond ACodec.cpp")
    required = (
        'mComponentName == "OMX.allwinner.video.decoder.hevc"',
        "baseWidth == 1920 && baseHeight == 1080",
        "outputWidth == 1920 && outputHeight == 1088",
        "baseColorFormat == HAL_PIXEL_FORMAT_YV12",
        "outputColorFormat == HAL_PIXEL_FORMAT_YV12",
        "outputCropRight == 1919 && outputCropBottom == 1087",
        'mOutputFormat->setRect("crop", baseCropLeft, baseCropTop,',
    )
    if any(text not in patch for text in required):
        fail("exact crop guard or assignment changed")
    if patch.count('mOutputFormat->setRect("crop"') != 1:
        fail("diag2 patch has more than one semantic assignment")
    forbidden = (
        "native_window_set_usage", "native_window_set_buffers_format",
        "eglCreateImageKHR", "LOG_ALWAYS_FATAL", "AFBC", "HWC2",
        "GRALLOC_USAGE", "OMX_SetParameter",
    )
    if any(text in patch for text in forbidden):
        fail("diag2 patch touches a forbidden semantic boundary")

    evidence = Path("/work/evidence/ubox10/r7-diag2-hevc-crop").resolve()
    if evidence.is_relative_to(ROOT.resolve()):
        fail("read-only physical evidence is inside the repository")

    if not CANDIDATE.exists():
        print("PASS_DIAG2_HEVC_CROP_STATIC_ONLY")
        return
    image = CANDIDATE / f"x12-{cfg['id']}.img"
    build = json.loads((CANDIDATE / "build-result.json").read_text(encoding="utf-8"))
    audit = json.loads(
        (CANDIDATE / "offline-audit/offline-audit.json").read_text(encoding="utf-8")
    )
    if build["status"] != "OFFLINE_CHECKED" or audit["physical_status"] != "NOT_YET_VALIDATED":
        fail("candidate incorrectly claims a physical result")
    if build["firmware"]["size"] != image.stat().st_size or build["firmware"]["sha256"] != digest(image):
        fail("candidate image identity changed")
    if audit["compatibility"]["full_vintf_exit"] != 65:
        fail("full VINTF inherited failure was reclassified")
    if audit["preservation"]["diag1a_system_tree_delta"] != {
        "added": [], "removed": [], "changed": ["system/lib64/libstagefright.so"]
    }:
        fail("diag1a-to-diag2 semantic delta expanded")
    if audit["preservation"]["diag1a_vendor_tree_delta"] != {
        "added": [], "removed": [], "changed": []
    }:
        fail("diag2 changed vendor")

    old = CANDIDATE / "diag1a-libstagefright64"
    new = CANDIDATE / "diag2-libstagefright64"
    if strong_undefined(old) != strong_undefined(new):
        fail("libstagefright undefined strong import set changed")
    runtime_files = [
        new, CANDIDATE / "diag2-surfaceflinger", CANDIDATE / "diag2-gralloc32",
        CANDIDATE / "diag2-gralloc64",
    ]
    joined = b"".join(path.read_bytes() for path in runtime_files)
    missing = sorted(stage for stage in STAGES
                     if f"stage={stage}".encode() not in joined)
    if missing:
        fail(f"diag2 lost diagnostic stages: {missing}")
    if b"Failed to create a valid texture." not in (CANDIDATE / "diag2-surfaceflinger").read_bytes():
        fail("original fatal path is absent")
    for path, record in cfg["preserved_runtime"].items():
        candidate_name = {
            "/system/bin/surfaceflinger": "diag2-surfaceflinger",
            "/vendor/lib/hw/gralloc.apollo.so": "diag2-gralloc32",
            "/vendor/lib64/hw/gralloc.apollo.so": "diag2-gralloc64",
        }[path]
        actual = CANDIDATE / candidate_name
        if actual.stat().st_size != record["size"] or digest(actual) != record["sha256"]:
            fail(f"preserved runtime changed: {path}")
    print("PASS_DIAG2_HEVC_CROP_SINGLE_RUNTIME_FILE_DELTA")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
