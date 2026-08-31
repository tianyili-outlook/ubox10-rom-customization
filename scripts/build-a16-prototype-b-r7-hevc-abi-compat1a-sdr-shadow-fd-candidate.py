#!/usr/bin/env python3
"""Build compat1a from the exact compat1 image with only the sized-shadow-fd correction."""
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
subprocess.run(
    [sys.executable, str(ROOT / "scripts/build-a16-prototype-b-r7-hevc-abi-compat1-sdr-shadow-candidate.py"),
     "--config", str(ROOT / "configs/candidates/a16-prototype-b-r7-hevc-abi-compat1a-sdr-shadow-fd.json"),
     *sys.argv[1:]],
    check=True,
)
