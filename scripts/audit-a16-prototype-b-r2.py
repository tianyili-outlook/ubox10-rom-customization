#!/usr/bin/env python3
"""Run the full B1 audit plus the B r2 single-directory root-delta gate."""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys


REPO = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE = REPO / "out/candidates/a16-prototype-b-r2"
DEFAULT_CONFIG = REPO / "configs/candidates/a16-prototype-b-r2.json"
DEFAULT_AOSP = Path("/work/src/ubox10-a16-ceiling")

AUDIT_PATH = REPO / "scripts/audit-a16-prototype-b-r1.py"
AUDIT_SPEC = importlib.util.spec_from_file_location("a16_b_shared_auditor", AUDIT_PATH)
if AUDIT_SPEC is None or AUDIT_SPEC.loader is None:
    raise RuntimeError(f"cannot import shared Prototype B auditor: {AUDIT_PATH}")
AUDIT = importlib.util.module_from_spec(AUDIT_SPEC)
sys.modules[AUDIT_SPEC.name] = AUDIT
AUDIT_SPEC.loader.exec_module(AUDIT)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--aosp", type=Path, default=DEFAULT_AOSP)
    parser.add_argument("--kernel-evidence", type=Path)
    parser.add_argument("--resume", action="store_true")
    AUDIT.Auditor(parser.parse_args()).execute()


if __name__ == "__main__":
    main()
