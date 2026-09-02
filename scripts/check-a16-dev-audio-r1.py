#!/usr/bin/env python3
"""Focused fail-closed checker for a16-dev-audio-r1."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys


REPO = Path(__file__).resolve().parents[1]
AOSP = Path("/work/src/ubox10-a16-ceiling")
CANDIDATE = REPO / "out/candidates/a16-dev-audio-r1"
CONFIG = REPO / "configs/candidates/a16-dev-audio-r1.json"
AUDIT = CANDIDATE / "offline-audit/offline-audit.json"
DEVICE = AOSP / "hardware/interfaces/audio/core/all-versions/default/Device.cpp"


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest().upper()


def require_record(path: Path, spec: dict[str, object]) -> None:
    if path.stat().st_size != spec["size"] or digest(path) != spec["sha256"]:
        fail(f"identity mismatch: {path}")


def main() -> None:
    cfg = json.loads(CONFIG.read_text())
    audit = json.loads(AUDIT.read_text())
    build = json.loads((CANDIDATE / "build-result.json").read_text())
    require_record(
        CANDIDATE / "x12-a16-dev-audio-r1.img",
        {"size": 1641830400, "sha256": "270B5D822AB3BB13D8EDCD9BE374DA1D6ED512D6D60063E123046C23B8AF9D62"},
    )
    require_record(CANDIDATE / "compat1a-audio-impl.so", cfg["runtime_change"]["baseline"])
    require_record(CANDIDATE / "audio-r1-audio-impl.so", cfg["runtime_change"]["candidate"])
    if build["status"] != "OFFLINE_CHECKED" or audit["physical_status"] != "NOT_YET_VALIDATED":
        fail("candidate status is not offline-checked/physically unvalidated")
    if audit["filesystem"]["vendor_tree_delta"] != {
        "added": [], "removed": [], "changed": ["lib/hw/android.hardware.audio@7.0-impl.so"]
    }:
        fail("runtime semantic delta expanded")
    if not audit["filesystem"]["system_byte_identical_to_compat1a"]:
        fail("compat1a system image changed")
    if audit["vintf"] != {
        "actual": "CONFIG_NFS_FS=y",
        "full": "NOT_PASS_INHERITED_CONFIG_NFS_FS_MISMATCH_ONLY",
        "full_exit": 65,
        "required": "CONFIG_NFS_FS=n",
        "system": "PASS",
        "system_exit": 0,
    }:
        fail("VINTF classification changed")
    closure = audit["runtime_delta"]["namespace_closure"]
    if closure["unmatched_count"] != 0 or closure["libcpp_verbose_abort_import"]:
        fail("ARM32 vendor/VNDK31 namespace closure failed")
    if not audit["runtime_delta"]["dt_needed_preserved"]:
        fail("DT_NEEDED changed")
    if not audit["runtime_delta"]["required_hidl_exports_preserved"]:
        fail("required HIDL exports changed")
    if audit["runtime_delta"]["legacy_fallback_for_malformed_v7"]:
        fail("malformed-v7 legacy fallback was introduced")

    source = DEVICE.read_text()
    helper = source.index("Return<void> Device::getAudioPortImpl")
    start = source.index("#if MAJOR_VERSION <= 6", helper)
    body = source[start:source.index("Return<Result> Device::setAudioPortConfig", start)]
    guard = "if (mDevice->get_audio_port_v7 == nullptr)"
    callback = "_hidl_cb(Result::NOT_SUPPORTED, port);"
    valid = "getAudioPortImpl(port, _hidl_cb, mDevice->get_audio_port_v7"
    legacy = "getAudioPortImpl(port, _hidl_cb, mDevice->get_audio_port,"
    for marker in (guard, callback, valid, legacy):
        if marker not in body:
            fail(f"source guard contract missing: {marker}")
    if not body.index(guard) < body.index(valid) < body.rindex(legacy):
        fail("source guard or existing valid/legacy ordering changed")
    null_block = body[body.index(guard):body.index(valid)]
    if "get_audio_port," in null_block:
        fail("null v7 guard falls back to legacy callback")
    if digest(DEVICE) != cfg["source_contract"]["device_cpp_post_sha256"]:
        fail("patched Device.cpp hash changed")

    disassembly = (CANDIDATE / "offline-audit/audio-getAudioPort-disassembly.txt").read_text()
    for marker in ("ldr.w\tr0, [r0, #0xa4]", "cbz\tr0", "movs\tr1, #0x4"):
        if marker not in disassembly:
            fail(f"null-safe disassembly marker missing: {marker}")
    surfaceflinger = cfg["preserved_runtime"]["surfaceflinger"]
    require_record(CANDIDATE / "compat1a-surfaceflinger", surfaceflinger)
    if cfg["governance"]["r8_authorized"] or cfg["governance"]["r8_built"]:
        fail("r8 governance changed")
    print("PASS_A16_DEV_AUDIO_R1_EXACT_ONE_RUNTIME_FILE_NULL_V7_GUARD")


if __name__ == "__main__":
    main()
