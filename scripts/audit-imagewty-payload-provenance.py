#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only IMAGEWTY payload provenance audit for UBOX10 boot images.

The tool reads the official and candidate PhoenixCard containers, hashes their
boot/vendor_boot payload ranges, and compares them with the extracted official
files and work-tree candidates.  It never extracts to an existing directory,
never changes either container, and never communicates with a device.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HEADER_MAGIC = b"IMAGEWTY"
MAIN_HEADER_SIZE = 96
FILE_HEADER_OFFSET = 1024
TARGET_ENTRIES = ("boot.fex", "vendor_boot.fex", "super.fex")
WORK_MAPPING = {
    "boot.fex": "work/boot.img",
    "vendor_boot.fex": "work/vendor_boot.img",
    "super.fex": "work/super.img",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def require_file(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_file():
        raise ValueError(f"{label} does not exist or is not a file: {resolved}")
    return resolved


def require_within(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{label} must be below repository root {root}: {resolved}") from exc
    return resolved


def parse_container(path: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Parse only IMAGEWTY metadata; payloads stay in the source container."""
    file_size = path.stat().st_size
    with path.open("rb") as source:
        main = source.read(MAIN_HEADER_SIZE)
        if len(main) != MAIN_HEADER_SIZE:
            raise ValueError(f"Container is shorter than IMAGEWTY main header: {path}")
        magic, header_version, header_size = struct.unpack("<8sII", main[:16])
        if magic != HEADER_MAGIC:
            raise ValueError(f"Unexpected IMAGEWTY magic in {path}: {magic!r}")
        fields = struct.unpack("<8s22I", main)
        main_header = {
            "magic": magic.decode("ascii"),
            "header_version": header_version,
            "header_size": header_size,
            "declared_image_size": fields[5],
            "num_files": fields[14],
            "actual_file_size": file_size,
        }
        entries: dict[str, dict[str, Any]] = {}
        cursor = FILE_HEADER_OFFSET
        for index in range(main_header["num_files"]):
            if cursor + 1024 > file_size:
                raise ValueError(f"Truncated file header {index} in {path}")
            source.seek(cursor)
            header = source.read(1024)
            filename_len, total_header_size = struct.unpack("<II", header[:8])
            if total_header_size < 1024:
                raise ValueError(f"Invalid file header size at entry {index} in {path}")
            filename = header[36:292].decode("ascii", errors="strict").split("\x00", 1)[0]
            stored_len, original_len, offset = struct.unpack("<QQQ", header[292:316])
            if not filename:
                raise ValueError(f"Empty IMAGEWTY filename at entry {index} in {path}")
            if offset + original_len > file_size or offset + stored_len > file_size:
                raise ValueError(f"Payload outside container for {filename} in {path}")
            key = filename.lower()
            if key in entries:
                raise ValueError(f"Duplicate IMAGEWTY filename in {path}: {filename}")
            entries[key] = {
                "index": index,
                "filename": filename,
                "header_offset": cursor,
                "filename_len": filename_len,
                "header_size": total_header_size,
                "maintype": header[8:16].decode("ascii", errors="replace").strip("\x00 "),
                "subtype": header[16:32].decode("ascii", errors="replace").strip("\x00 "),
                "stored_len": stored_len,
                "original_len": original_len,
                "offset": offset,
            }
            cursor += total_header_size
    return main_header, entries


def sha256_range(path: Path, offset: int, length: int) -> str:
    digest = hashlib.sha256()
    remaining = length
    with path.open("rb") as source:
        source.seek(offset)
        while remaining:
            chunk = source.read(min(4 * 1024 * 1024, remaining))
            if not chunk:
                raise ValueError(f"Truncated payload range in {path}")
            digest.update(chunk)
            remaining -= len(chunk)
    return digest.hexdigest().upper()


def imagewty_checksum_range(path: Path, offset: int, length: int) -> int:
    """Reproduce IMAGEWTY's little-endian 32-bit payload checksum."""
    checksum = 0
    remaining = length
    with path.open("rb") as source:
        source.seek(offset)
        while remaining:
            chunk = source.read(min(4 * 1024 * 1024, remaining))
            if not chunk:
                raise ValueError(f"Truncated payload range in {path}")
            remaining -= len(chunk)
            if len(chunk) % 4:
                chunk += b"\x00" * (4 - len(chunk) % 4)
            checksum = (checksum + sum(struct.unpack(f"<{len(chunk) // 4}I", chunk))) & 0xFFFFFFFF
    return checksum


def companion_checksum(
    container: Path, entries: dict[str, dict[str, Any]], entry: dict[str, Any]
) -> dict[str, Any]:
    companion = entries.get(f"v{entry['filename']}".lower())
    if companion is None:
        return {"present": False}
    if companion["original_len"] < 4:
        return {"present": True, "valid": False, "reason": "companion_shorter_than_4_bytes"}
    with container.open("rb") as source:
        source.seek(companion["offset"])
        expected = struct.unpack("<I", source.read(4))[0]
    actual = imagewty_checksum_range(container, entry["offset"], entry["stored_len"])
    return {
        "present": True,
        "companion_filename": companion["filename"],
        "expected_hex": f"0x{expected:08X}",
        "actual_hex": f"0x{actual:08X}",
        "valid": expected == actual,
    }


def payload_report(
    container: Path, entries: dict[str, dict[str, Any]], filename: str
) -> dict[str, Any]:
    entry = entries.get(filename.lower())
    if entry is None:
        raise ValueError(f"Required IMAGEWTY entry {filename} not found in {container}")
    report = dict(entry)
    report["payload_sha256"] = sha256_range(container, entry["offset"], entry["original_len"])
    report["companion_checksum"] = companion_checksum(container, entries, entry)
    return report


def file_report(path: Path) -> dict[str, Any]:
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def compare_payload_to_file(payload: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any]:
    return {
        "same_length": payload["original_len"] == reference["bytes"],
        "same_sha256": payload["payload_sha256"] == reference["sha256"],
    }


def write_manifest(output_dir: Path) -> None:
    lines: list[str] = []
    for path in sorted(output_dir.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS.txt":
            lines.append(f"{sha256_file(path)}  {path}")
    (output_dir / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser(repository_root: Path) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path, help="New report directory below this repository")
    parser.add_argument("--official-container", type=Path, default=repository_root / "x12-1024.img")
    parser.add_argument("--candidate-container", type=Path, default=repository_root / "x12-purified.img")
    parser.add_argument("--official-extracted-dir", type=Path, default=repository_root / "firmware/extracted")
    parser.add_argument("--work-dir", type=Path, default=repository_root / "work")
    parser.add_argument("--packer", type=Path, default=repository_root / "tools/pack_image.py")
    return parser


def main() -> int:
    repository_root = Path(__file__).resolve().parent.parent
    args = build_parser(repository_root).parse_args()
    output_dir = require_within(args.output_dir, repository_root, "output directory")
    if output_dir.exists():
        raise ValueError(f"Refusing to overwrite existing output directory: {output_dir}")

    official_container = require_file(args.official_container, "official container")
    candidate_container = require_file(args.candidate_container, "candidate container")
    official_extracted_dir = require_within(args.official_extracted_dir, repository_root, "official extracted directory")
    work_dir = require_within(args.work_dir, repository_root, "work directory")
    packer = require_file(args.packer, "packer")

    official_header, official_entries = parse_container(official_container)
    candidate_header, candidate_entries = parse_container(candidate_container)
    output_dir.mkdir(parents=True)

    entry_reports: dict[str, Any] = {}
    for filename in TARGET_ENTRIES:
        official_payload = payload_report(official_container, official_entries, filename)
        candidate_payload = payload_report(candidate_container, candidate_entries, filename)
        official_extracted = file_report(require_file(official_extracted_dir / filename, f"official extracted {filename}"))
        work_relative = WORK_MAPPING[filename]
        work_file = file_report(require_file(repository_root / work_relative, f"work candidate {filename}"))
        entry_reports[filename] = {
            "official_container_payload": official_payload,
            "official_extracted_file": official_extracted,
            "candidate_container_payload": candidate_payload,
            "work_candidate_file": work_file,
            "relationships": {
                "official_container_matches_extracted": compare_payload_to_file(official_payload, official_extracted),
                "candidate_container_matches_work": compare_payload_to_file(candidate_payload, work_file),
                "candidate_payload_matches_official_payload": {
                    "same_length": candidate_payload["original_len"] == official_payload["original_len"],
                    "same_sha256": candidate_payload["payload_sha256"] == official_payload["payload_sha256"],
                },
            },
        }

    report: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "safety": {
            "device_commands": "none",
            "serial_io": "none",
            "container_images_modified": False,
            "payloads_extracted": False,
            "output_directory": str(output_dir),
        },
        "inputs": {
            "official_container": file_report(official_container),
            "candidate_container": file_report(candidate_container),
            "packer": file_report(packer),
        },
        "expected_work_mapping": WORK_MAPPING,
        "official_container_header": official_header,
        "candidate_container_header": candidate_header,
        "entries": entry_reports,
        "interpretation_boundary": (
            "Matching a candidate container payload to a work-tree file proves only the local packaging "
            "relationship. It does not prove that the candidate container was flashed or that the device "
            "currently boots that payload."
        ),
    }
    report_path = output_dir / "imagewty-boot-provenance.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_manifest(output_dir)
    print(f"IMAGEWTY provenance audit written to: {output_dir}")
    print(f"Report: {report_path}")
    print("Device commands: none; serial I/O: none; containers modified: false; payloads extracted: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
