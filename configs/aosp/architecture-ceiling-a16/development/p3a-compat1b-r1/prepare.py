#!/usr/bin/env python3
"""Strict reversible overlay on the exact compat1a Skia source; no build/device action."""
from pathlib import Path
import argparse
import hashlib
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
BEFORE = "328cc3f7e68616e1b19522d5b9047fb2fa6cabc71c1dc28dcf33c02a7691c1d3"
AFTER = "923dc75891b570b8a1edb360d222d44682175b5da6e9e67f0efb9c7e8db3dbaf"
HEADER = "1665b512d6ff7e23af7f1d759f5960889ad7aa2c0861ede9bb0ec58adbde24bd"
SHARED = "98228a9599eedfcd6c073124c31a48e105e3360e7c62ed05c4c77d2300951294"

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "apply", "revert"))
    parser.add_argument("aosp", type=Path, nargs="?", default=Path("/work/src/ubox10-a16-ceiling"))
    args = parser.parse_args()
    skia = args.aosp / "external/skia"
    revision = subprocess.check_output(["git", "-C", str(skia), "rev-parse", "HEAD"], text=True).strip()
    if revision != "4c18a9680d52c2cd5e35cfef2f548635a445fafe":
        raise RuntimeError("unexpected pinned Skia revision")
    cpp = skia / "src/gpu/ganesh/gl/AHardwareBufferGL.cpp"
    header = cpp.with_name("UBOXP3Compat1b.h")
    if digest(cpp.with_name("UBOXR7Compat1Metadata.h")) != SHARED or digest(HERE / header.name) != HEADER:
        raise RuntimeError("shared translation or overlay header changed")
    def state():
        if digest(cpp) == AFTER and digest(header) == HEADER: return "PATCHED"
        if digest(cpp) == BEFORE and not header.exists(): return "COMPAT1A"
        raise RuntimeError("unexpected source; refusing overwrite")
    current = state()
    if args.action == "apply":
        if current != "COMPAT1A": raise RuntimeError("source is not exact compat1a")
        subprocess.run(["git", "-C", str(skia), "apply", "--unidiff-zero", "--check", str(HERE / "compat1b.patch")], check=True)
        subprocess.run(["git", "-C", str(skia), "apply", "--unidiff-zero", str(HERE / "compat1b.patch")], check=True)
        shutil.copyfile(HERE / header.name, header)
        if state() != "PATCHED": raise RuntimeError("patch verification failed")
    elif args.action == "revert":
        if current != "PATCHED": raise RuntimeError("source is not exact compat1b")
        subprocess.run(["git", "-C", str(skia), "apply", "--unidiff-zero", "--reverse", "--check", str(HERE / "compat1b.patch")], check=True)
        subprocess.run(["git", "-C", str(skia), "apply", "--unidiff-zero", "--reverse", str(HERE / "compat1b.patch")], check=True)
        header.unlink()  # Only the exact validated overlay-owned header.
        if state() != "COMPAT1A": raise RuntimeError("revert verification failed")
    print("UBOX_P3_COMPAT1B source state: " + state())

if __name__ == "__main__": main()
