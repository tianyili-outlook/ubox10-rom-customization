#!/usr/bin/env python3
"""Generate and validate an ext4 manifest without invoking e2fsprogs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from ubox10_rom.ext4_image import Ext4Error, read_manifest, validate_fixture_contract  # noqa: E402
from ubox10_rom.ext4_manifest import assess_root_hierarchy  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--contract", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = read_manifest(args.image)
        errors = []
        if args.contract:
            contract = json.loads(args.contract.read_text(encoding="utf-8"))
            errors.extend(validate_fixture_contract(manifest, contract))
        if args.contract or manifest["filesystem"]["volume_label"] == "/":
            root = assess_root_hierarchy(manifest)
            if root.status != "PASS":
                errors.extend(f"root_contract:{item}" for item in root.reason_codes)
    except (OSError, ValueError, json.JSONDecodeError, Ext4Error) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(f"PASS: {args.image}")
    print(f"Manifest: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
