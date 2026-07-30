#!/usr/bin/env python3
"""Build a deterministic, source-only M7 GitHub Release bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile


REPO = Path(__file__).resolve().parents[1]
PREFIX = "ubox10-m7/"
REQUIRED_MEMBERS = {
    f"{PREFIX}README.md",
    f"{PREFIX}configs/releases/m7.json",
    f"{PREFIX}configs/candidates/test8r2-restore-contacts-provider.json",
    f"{PREFIX}configs/apps/projectivy-4.71.json",
    f"{PREFIX}configs/apps/test9.3-userdata-apps.json",
    f"{PREFIX}scripts/build-candidate-firmware.py",
    f"{PREFIX}scripts/install-userdata-apps.py",
}
PROHIBITED_SUFFIXES = {".apk", ".aab", ".apks", ".img"}


class ReleasePackageError(RuntimeError):
    """Raised when the release ref or archive violates the M7 contract."""


def run_git(*arguments: str) -> str:
    process = subprocess.run(
        ["git", *arguments],
        cwd=REPO,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if process.returncode != 0:
        detail = process.stderr.strip() or process.stdout.strip()
        raise ReleasePackageError(f"git {' '.join(arguments)} failed: {detail}")
    return process.stdout.strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def validate_archive(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())

    missing = sorted(REQUIRED_MEMBERS - names)
    if missing:
        raise ReleasePackageError(
            "release archive is missing required tracked files: "
            + ", ".join(missing)
        )

    prohibited = sorted(
        name
        for name in names
        if Path(name).suffix.lower() in PROHIBITED_SUFFIXES
    )
    if prohibited:
        raise ReleasePackageError(
            "release archive unexpectedly contains binary distribution files: "
            + ", ".join(prohibited)
        )


def package(ref: str, output_dir: Path) -> tuple[Path, Path, Path]:
    commit = run_git("rev-parse", "--verify", f"{ref}^{{commit}}")
    output_dir.mkdir(parents=True, exist_ok=True)

    asset = output_dir / "ubox10-m7-reproducibility.zip"
    checksum = output_dir / f"{asset.name}.sha256"
    metadata = output_dir / "ubox10-m7-release-metadata.json"

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".ubox10-m7-",
        suffix=".zip",
        dir=output_dir,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    temporary.unlink()

    try:
        run_git(
            "archive",
            "--format=zip",
            f"--prefix={PREFIX}",
            f"--output={temporary}",
            commit,
        )
        validate_archive(temporary)
        os.replace(temporary, asset)
    finally:
        temporary.unlink(missing_ok=True)

    digest = sha256_file(asset)
    checksum.write_text(f"{digest}  {asset.name}\n", encoding="utf-8")
    metadata.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "release_id": "m7",
                "git_ref": ref,
                "commit": commit,
                "asset": asset.name,
                "bytes": asset.stat().st_size,
                "sha256": digest,
                "contains_firmware": False,
                "contains_third_party_apks": False,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return asset, checksum, metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ref",
        default="HEAD",
        help="committed Git ref to archive (default: HEAD)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO / "out" / "releases" / "m7",
        help="release asset directory",
    )
    arguments = parser.parse_args()

    output_dir = arguments.output_dir
    if not output_dir.is_absolute():
        output_dir = REPO / output_dir

    for result in package(arguments.ref, output_dir.resolve()):
        print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
