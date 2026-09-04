#!/usr/bin/env python3
"""Focused fail-closed checker for the a16-dev-p3a-omx-r1 candidate."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


REPO = Path(__file__).resolve().parents[1]
CANDIDATE = REPO / "out/candidates/a16-dev-p3a-omx-r1"
CONFIG = REPO / "configs/candidates/a16-dev-p3a-omx-r1.json"


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest().upper()


def require(path: Path, spec: dict[str, object]) -> None:
    if not path.is_file() or path.stat().st_size != spec["size"] or digest(path) != spec["sha256"]:
        fail(f"identity mismatch: {path}")


def main() -> None:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    build = json.loads((CANDIDATE / "build-result.json").read_text(encoding="utf-8"))
    audit = json.loads((CANDIDATE / "offline-audit/offline-audit.json").read_text(encoding="utf-8"))
    if build["status"] != "OFFLINE_CHECKED" or build["physical_status"] != "NOT_YET_VALIDATED":
        fail("candidate is not offline-checked and physically unvalidated")
    require(CANDIDATE / "x12-a16-dev-p3a-omx-r1.img", build["firmware"])
    require(CANDIDATE / "libOmxVdec.audio-r1.so", cfg["runtime_change"]["baseline"])
    require(CANDIDATE / "libOmxVdec.p3a-omx-r1.so", cfg["runtime_change"]["candidate"])

    expected_delta = {"added": [], "removed": [], "changed": ["lib/libOmxVdec.so"]}
    if audit["filesystem"]["vendor_tree_delta"] != expected_delta:
        fail("runtime semantic delta expanded")
    if audit["filesystem"]["semantic_runtime_delta_count"] != 1:
        fail("semantic runtime delta count changed")
    if not audit["filesystem"]["system_byte_identical_to_audio_r1"]:
        fail("audio-r1 system/compat1a SurfaceFlinger lineage changed")
    if audit["elf"]["changed_byte_count"] != 3:
        fail("ELF byte delta is not exact")
    if audit["elf"]["changed_byte_offsets"] != [0xD130, 0xD131, 0xD132]:
        fail("ELF changed offsets are not exact")
    if not audit["elf"]["all_bytes_outside_patch_range_identical"]:
        fail("bytes outside the patch range changed")
    if audit["elf"]["build_id_note"] != "RETAINED_ORIGINAL_NOT_CANONICAL_PATCH_IDENTITY":
        fail("retained Build ID classification changed")
    if audit["disassembly"] != "PASS_PEEK_R12_SELECTED_REQUEST_FBD_RETURN_UNCHANGED":
        fail("patched lifecycle disassembly proof failed")
    if audit["vintf"]["system_exit"] != 0 or audit["vintf"]["full_exit"] != 65:
        fail("VINTF result changed")
    if audit["vintf"]["full"] != "NOT_PASS_INHERITED_CONFIG_NFS_FS_MISMATCH_ONLY":
        fail("full VINTF was misclassified")

    for name, spec in cfg["preserved_runtime"].items():
        require(CANDIDATE / f"preserved-{name}", spec)
        audited = audit["preserved_runtime"][name]
        if audited["sha256"] != spec["sha256"] or audited["size"] != spec["size"]:
            fail(f"preserved runtime changed: {name}")

    with tempfile.TemporaryDirectory(prefix="ubox-p3a-omx-check-", dir="/work/tmp") as directory:
        extracted = Path(directory) / "libOmxVdec.so"
        subprocess.run(
            ["debugfs", "-R", f"dump -p /lib/libOmxVdec.so {extracted}",
             str(CANDIDATE / "candidate-logical/vendor_a.img")],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        require(extracted, cfg["runtime_change"]["candidate"])

    gov = audit["governance"]
    if (
        gov["rc_a"] != "PATCH_IMPLEMENTED_OFFLINE_CANDIDATE_BUILT_PHYSICAL_VALIDATION_PENDING"
        or gov["rc_b"] != "DEFERRED_EXPECTED_NEXT_BOUNDARY"
        or gov["p3b_main10"] != "NOT_AUTHORIZED"
        or gov["r8"] != "NOT_AUTHORIZED_NOT_BUILT"
    ):
        fail("candidate governance changed")
    print("PASS_A16_DEV_P3A_OMX_R1_EXACT_ONE_RUNTIME_FILE")


if __name__ == "__main__":
    main()
