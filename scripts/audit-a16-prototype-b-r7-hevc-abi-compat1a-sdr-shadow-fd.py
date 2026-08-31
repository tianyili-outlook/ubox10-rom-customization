#!/usr/bin/env python3
"""Run the full compat1 preservation audit against the compat1a candidate/config."""
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
subprocess.run(
    [sys.executable, str(ROOT / "scripts/audit-a16-prototype-b-r7-hevc-abi-compat1-sdr-shadow.py"),
     "--candidate", str(ROOT / "out/candidates/a16-prototype-b-r7-hevc-abi-compat1a-sdr-shadow-fd"),
     "--config", str(ROOT / "configs/candidates/a16-prototype-b-r7-hevc-abi-compat1a-sdr-shadow-fd.json"),
     *sys.argv[1:]],
    check=True,
)
