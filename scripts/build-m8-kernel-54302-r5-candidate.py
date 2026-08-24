#!/usr/bin/env python3
"""Build the r5 FMAC address-contract Android 12 candidate."""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys


REPO = Path(__file__).resolve().parents[1]
R3_BUILDER_PATH = REPO / "scripts/build-m8-kernel-54302-r3-candidate.py"
SPEC = importlib.util.spec_from_file_location("m8_kernel_54302_r3_candidate", R3_BUILDER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import candidate builder: {R3_BUILDER_PATH}")
R3 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = R3
SPEC.loader.exec_module(R3)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path,
        default=REPO / "configs/candidates/m8-kernel-5.4.302-r5.json",
    )
    parser.add_argument("--aosp", type=Path, default=R3.BASE.DEFAULT_AOSP)
    parser.add_argument("--integration-repo", type=Path, default=R3.BASE.DEFAULT_INTEGRATION)
    parser.add_argument("--keep-failed", action="store_true")
    R3.R3Builder(parser.parse_args()).build()


if __name__ == "__main__":
    main()
