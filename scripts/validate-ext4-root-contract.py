#!/usr/bin/env python3
"""Validate an M6b.0 ext4 root-hierarchy JSON manifest without side effects."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPO_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from ubox10_rom.ext4_manifest import assess_root_hierarchy_file  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read one M6b.0 JSON manifest and validate its root-hierarchy "
            "contract. This tool never opens firmware images or hardware."
        )
    )
    parser.add_argument("--manifest", type=Path, required=True, help="Input JSON manifest")
    args = parser.parse_args()

    result = assess_root_hierarchy_file(args.manifest)
    print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result.status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
