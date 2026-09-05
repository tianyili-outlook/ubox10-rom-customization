#!/usr/bin/env python3
"""Recheck packaged compat1b identity, single-file delta and inherited debt."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "out/candidates/a16-dev-p3a-compat1b-r1"


def require(path, spec):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""): h.update(block)
    if path.stat().st_size != spec["size"] or h.hexdigest().upper() != spec["sha256"].upper():
        raise RuntimeError(f"identity mismatch: {path}")


def main():
    cfg = json.loads((ROOT / "configs/candidates/a16-dev-p3a-compat1b-r1.json").read_text())
    build = json.loads((CANDIDATE / "build-result.json").read_text())
    audit = json.loads((CANDIDATE / "offline-audit/offline-audit.json").read_text())
    if build["status"] != "OFFLINE_CHECKED" or build["physical_status"] != "NOT_YET_VALIDATED":
        raise RuntimeError("offline/physical classification changed")
    require(ROOT / cfg["artifact"]["path"], cfg["artifact"])
    require(CANDIDATE / "compat1b-surfaceflinger", cfg["runtime_change"])
    require(CANDIDATE / "vendor_a.img", cfg["base_artifacts"]["vendor_a"])
    fs = audit["filesystem"]
    if fs["system_tree_delta"] != {"added": [], "removed": [], "changed": ["system/bin/surfaceflinger"]}:
        raise RuntimeError("system semantic delta expanded")
    if fs["vendor_tree_delta"] != {"added": [], "removed": [], "changed": []}:
        raise RuntimeError("vendor semantic delta expanded")
    if fs["semantic_runtime_delta_count"] != 1 or not fs["vendor_byte_identical_to_fbm_r1"]:
        raise RuntimeError("one-runtime-file scope changed")
    if audit["elf"]["namespace_closure"]["unmatched_count"] != 0:
        raise RuntimeError("ELF closure failed")
    if audit["vintf"]["system_exit"] != 0 or audit["vintf"]["full_exit"] != 65:
        raise RuntimeError("VINTF result changed")
    if audit["vintf"]["full"] != "NOT_PASS_INHERITED_CONFIG_NFS_FS_MISMATCH_ONLY":
        raise RuntimeError("inherited full VINTF debt misclassified")
    with tempfile.TemporaryDirectory(prefix="ubox-compat1b-check-") as directory:
        sf = Path(directory) / "surfaceflinger"
        subprocess.run(["debugfs", "-R", f"dump -p /system/bin/surfaceflinger {sf}",
                        str(CANDIDATE / "system_a.img")], check=True, capture_output=True)
        require(sf, cfg["runtime_change"])
    for name, spec in cfg["preserved_runtime"].items():
        require(CANDIDATE / f"preserved-{name}", spec)
        if audit["preserved_runtime"][name]["sha256"] != spec["sha256"]:
            raise RuntimeError(f"prior repair changed: {name}")
    proof = json.loads((CANDIDATE / "surfaceflinger-build-proof.json").read_text())
    if proof["control"]["sha256"].upper() != cfg["runtime_change"]["base_sha256"]:
        raise RuntimeError("compat1a reconstruction control changed")
    if proof["compat1b"]["sha256"].upper() != cfg["runtime_change"]["sha256"]:
        raise RuntimeError("compat1b build proof changed")
    gov = cfg["governance"]
    if (gov["rc_a2"] != "PHYSICAL_PASS_CLOSED" or gov["audio_p1"] != "CLOSED"
            or gov["p2"] != "COMPLETE" or gov["p3b_main10"] != "NOT_AUTHORIZED"
            or gov["r8_authorized"] or gov["r8_built"] or gov["release"]):
        raise RuntimeError("governance changed")
    print("PASS_A16_DEV_P3A_COMPAT1B_R1_EXACT_ONE_RUNTIME_FILE")


if __name__ == "__main__": main()
