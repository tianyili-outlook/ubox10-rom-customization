#!/usr/bin/env python3
"""Fail-closed identity gate for the outside-Git Prototype B r1 ARM64 Mali file."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import subprocess
import sys


REPO = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO / "configs/candidates/a16-prototype-b-r1.json"
MISSING = "B1 BUILD BLOCKED — LOCAL ARM64 MALI INTAKE MISSING"
MISMATCH = "B1 BUILD BLOCKED — LOCAL ARM64 MALI INTAKE IDENTITY MISMATCH"


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest().upper()


def readelf(*args: str, path: Path) -> str:
    result = subprocess.run(
        ["readelf", "-W", *args, str(path)],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if result.returncode:
        raise RuntimeError(f"readelf failed with exit {result.returncode}")
    return result.stdout


def one(pattern: str, text: str, label: str) -> str:
    match = re.search(pattern, text, re.MULTILINE)
    if not match:
        raise RuntimeError(f"missing {label} in ELF metadata")
    return match.group(1).strip()


def inspect(path: Path) -> dict[str, object]:
    header = readelf("-h", path=path)
    dynamic = readelf("-d", path=path)
    notes = readelf("-n", path=path)
    return {
        "size": path.stat().st_size,
        "sha256": sha256(path),
        "elf_class": one(r"^\s*Class:\s*(\S+)", header, "ELF class"),
        "machine": one(r"^\s*Machine:\s*(.+)$", header, "ELF machine"),
        "soname": one(r"\(SONAME\).*\[([^]]+)\]", dynamic, "SONAME"),
        "build_id": one(r"\bBuild ID:\s*([0-9a-fA-F]+)", notes, "Build ID").lower(),
        "dt_needed": re.findall(r"\(NEEDED\).*\[([^]]+)\]", dynamic),
    }


def expected_summary(path: Path, expected: dict[str, object]) -> str:
    return "\n".join(
        (
            f"required_path={path}",
            f"required_size={expected['size']}",
            f"required_sha256={expected['sha256']}",
            f"required_elf={expected['elf_class']}/{expected['machine']}",
            f"required_soname={expected['soname']}",
            f"required_build_id={expected['build_id']}",
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--path", type=Path)
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    expected = config["arm64_mali_intake"]
    path = args.path if args.path is not None else Path(str(expected["path"]))
    summary = expected_summary(path, expected)

    if not path.exists():
        print(f"{MISSING}\n{summary}", file=sys.stderr)
        return 2
    if path.is_symlink() or not stat.S_ISREG(path.lstat().st_mode):
        print(f"{MISMATCH}\nreason=not_an_exact_regular_file\n{summary}", file=sys.stderr)
        return 3

    try:
        actual = inspect(path)
    except (OSError, RuntimeError) as error:
        print(f"{MISMATCH}\nreason={error}\n{summary}", file=sys.stderr)
        return 3

    fields = ("size", "sha256", "elf_class", "machine", "soname", "build_id", "dt_needed")
    mismatches = [
        f"{field}: expected={expected[field]!r} actual={actual[field]!r}"
        for field in fields
        if actual[field] != expected[field]
    ]
    if mismatches:
        print(f"{MISMATCH}\n" + "\n".join(mismatches) + f"\n{summary}", file=sys.stderr)
        return 3

    print(
        json.dumps(
            {
                "status": "PASS_EXACT_ARM64_MALI_LOCAL_INTAKE",
                "path": str(path),
                **actual,
                "binary_contents_tracked": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
