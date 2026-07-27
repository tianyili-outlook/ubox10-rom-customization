#!/usr/bin/env python3
"""Stream one logical partition from sparse super into a new raw image."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


REPO = Path(__file__).resolve().parents[1]
AUDITOR = REPO / "scripts" / "audit-logical-system-init.py"
OFFICIAL_SUPER_SHA256 = "BE6FAAA476D5DD17F9E6578ED8A48DA351C9D7C7EFD2C9AEBD65788F42A7F479"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def load_auditor():
    spec = importlib.util.spec_from_file_location("ubox10_logical_auditor", AUDITOR)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load logical partition reader")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--super", type=Path, default=REPO / "firmware" / "extracted" / "super.fex")
    parser.add_argument("--partition", default="system_a")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    source_path = args.super.resolve()
    output_dir = args.output_dir.resolve()
    if source_path != (REPO / "firmware" / "extracted" / "super.fex").resolve():
        raise RuntimeError(f"unexpected official super path: {source_path}")
    if sha256_file(source_path) != OFFICIAL_SUPER_SHA256:
        raise RuntimeError("official super SHA-256 mismatch")
    output_dir.relative_to((REPO / "out").resolve())
    if output_dir.exists():
        raise RuntimeError(f"refusing to overwrite: {output_dir}")
    output_dir.mkdir(parents=True)

    module = load_auditor()
    source = module.open_super_source(source_path)
    try:
        metadata = module.parse_lp_metadata(source)
        logical = module.LogicalPartitionSource(source, metadata, args.partition)
        output = output_dir / f"{args.partition}.img"
        digest = hashlib.sha256()
        with output.open("xb") as target:
            offset = 0
            while offset < logical.size:
                data = logical.read_at(offset, min(4 * 1024 * 1024, logical.size - offset))
                target.write(data)
                digest.update(data)
                offset += len(data)
        report = {
            "source": str(source_path),
            "source_sha256": OFFICIAL_SUPER_SHA256,
            "partition": args.partition,
            "bytes": logical.size,
            "output": str(output),
            "output_sha256": digest.hexdigest().upper(),
        }
        (output_dir / "extraction.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
        )
        print(json.dumps(report, indent=2, ensure_ascii=False))
    finally:
        source.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
