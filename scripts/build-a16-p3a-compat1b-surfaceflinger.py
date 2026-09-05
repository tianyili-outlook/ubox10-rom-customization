#!/usr/bin/env python3
"""Build only SurfaceFlinger; prove an exact compat1a control before the compat1b build.

The audio-r1-only legacy FMQ projection must not enter the ARM64 graphics build.
Temporarily use the pinned A16 header, then restore the exact audio build input.
No candidate packaging and no device commands.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
OVERLAY = REPO / "configs/aosp/architecture-ceiling-a16/development/p3a-compat1b-r1/prepare.py"
FMQ = "system/libfmq/base/fmq/MQDescriptorBase.h"
FMQ_REV = "674a2103f2bd9bd5505c58e83af3042be2a24adf"
FMQ_A16 = "69d61adc1c0123ce90f9abc6956a7305126b3ee7e970c08d8569b718f7ffaa0b"
CONTROL_SHA = "06c960e672863ad557af921565621997cb9b113ba2290049af91028a405cd0a5"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aosp", type=Path, default=Path("/work/src/ubox10-a16-ceiling"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists(): raise RuntimeError("refusing to overwrite build proof")
    args.output.mkdir(parents=True)
    fmq = args.aosp / FMQ
    original = fmq.read_bytes()
    audio_contract = json.loads((REPO / "configs/aosp/architecture-ceiling-a16/development/audio-r1/source-contract.json").read_text())
    if digest(original) != audio_contract["patched_sha256"][FMQ]:
        raise RuntimeError("unexpected audio-r1 FMQ build input")
    clean = subprocess.check_output(["git", "-C", str(args.aosp / "system/libfmq"),
                                     "show", FMQ_REV + ":base/fmq/MQDescriptorBase.h"])
    if digest(clean) != FMQ_A16: raise RuntimeError("pinned A16 FMQ header mismatch")
    cpp = args.aosp / "external/skia/src/gpu/ganesh/gl/AHardwareBufferGL.cpp"
    patched_cpp = digest(cpp.read_bytes())
    def overlay(action):
        subprocess.run([sys.executable, str(OVERLAY), action, str(args.aosp)], check=True)
    overlay("check")
    sf = args.aosp / "out-ceiling-b1/target/product/ubox10_ceiling_arm64/system/bin/surfaceflinger"
    results = {}
    try:
        fmq.write_bytes(clean)
        overlay("revert")
        for label in ("control", "compat1b"):
            if label == "compat1b": overlay("apply")
            with (args.output / f"{label}-build.log").open("w") as log:
                subprocess.run(["bash", "-c", "export OUT_DIR=out-ceiling-b1; source build/envsetup.sh >/dev/null; "
                                "lunch ubox10_ceiling_arm64-bp2a-userdebug >/dev/null && m -j16 surfaceflinger"],
                               cwd=args.aosp, stdout=log, stderr=subprocess.STDOUT, check=True)
            data = sf.read_bytes()
            results[label] = {"size": len(data), "sha256": digest(data)}
            shutil.copyfile(sf, args.output / f"{label}-surfaceflinger")
            if label == "control" and (digest(data) != CONTROL_SHA or len(data) != 8577592):
                raise RuntimeError("control does not reproduce the physically proven SurfaceFlinger; STOP")
    finally:
        if digest(fmq.read_bytes()) != FMQ_A16:
            raise RuntimeError("FMQ changed during build; refusing blind restore")
        fmq.write_bytes(original)
        if digest(cpp.read_bytes()) != patched_cpp:
            overlay("apply")
    results.update({"fmq_during_build_sha256": FMQ_A16,
                    "fmq_restored_sha256": digest(fmq.read_bytes()),
                    "control_exact_physical_compat1a": True,
                    "target": "surfaceflinger", "source_overlay": str(OVERLAY.parent)})
    (args.output / "build-proof.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__": main()
