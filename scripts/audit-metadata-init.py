#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only U3.2 audit for the UBOX10 metadata/init boot path.

This tool never opens a serial port, never invokes fastboot/PhoenixCard, and
never changes an input image. It unpacks copies into a new directory below the
repository's logs/ tree and writes a JSON evidence report plus SHA-256 manifest.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import struct
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SELECTED_BOOT_PATHS = (
    "prop.default",
    "init.recovery.sun50iw9p1.rc",
    "system/bin/init",
    "system/bin/mke2fs",
    "system/bin/e2fsdroid",
    "system/bin/apexd",
    "system/lib/libfs_mgr.so",
    "system/etc/init/hw/init.rc",
    "system/etc/init/apexd.rc",
    "system/etc/init/init.formatdevice.rc",
)

SELECTED_VENDOR_BOOT_PATHS = (
    "init.recovery.sun50iw9p1.rc",
    "first_stage_ramdisk/fstab.sun50iw9p1",
    "system/etc/recovery.fstab",
)

TEXT_DIFF_PATHS = (
    "prop.default",
    "init.recovery.sun50iw9p1.rc",
    "system/etc/init/hw/init.rc",
    "first_stage_ramdisk/fstab.sun50iw9p1",
    "system/etc/recovery.fstab",
)

MAX_TEXT_DIFF_LINES = 400


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
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


def parse_header_info(output: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in output.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip()
    return result


def unpack_image(
    repository_root: Path,
    image_path: Path,
    destination: Path,
) -> tuple[dict[str, str], Path]:
    tool = require_file(repository_root / "tools" / "unpack_bootimg.py", "unpack_bootimg.py")
    result = subprocess.run(
        [sys.executable, str(tool), "--boot_img", str(image_path), "--out", str(destination), "--format", "info"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    info = parse_header_info(result.stdout)
    ramdisk_name = "vendor_ramdisk" if info.get("boot magic") == "VNDRBOOT" else "ramdisk"
    ramdisk = require_file(destination / ramdisk_name, f"{image_path.name} {ramdisk_name}")
    return info, ramdisk


def decompress_lz4_raw_block(compressed: bytes, maximum_size: int) -> bytes:
    """Decode one raw LZ4 block without a third-party Python dependency.

    The vendor's legacy ramdisk container is not an LZ4 frame.  It starts with
    a four-byte magic, then contains little-endian compressed-block lengths
    followed by standard raw LZ4 blocks.  This decoder is deliberately
    decompression-only and bounds the output to the known 8 MiB block limit.
    """
    output = bytearray()
    cursor = 0
    input_size = len(compressed)

    def read_extended_length(initial: int) -> int:
        nonlocal cursor
        length = initial
        if initial != 15:
            return length
        while True:
            if cursor >= input_size:
                raise ValueError("Truncated LZ4 extended length")
            extension = compressed[cursor]
            cursor += 1
            length += extension
            if extension != 255:
                return length

    while cursor < input_size:
        token = compressed[cursor]
        cursor += 1
        literal_length = read_extended_length(token >> 4)
        literal_end = cursor + literal_length
        if literal_end > input_size:
            raise ValueError("Truncated LZ4 literal sequence")
        output.extend(compressed[cursor:literal_end])
        cursor = literal_end
        if len(output) > maximum_size:
            raise ValueError(f"LZ4 output exceeds {maximum_size} bytes")

        # The final LZ4 sequence may consist only of literals.
        if cursor == input_size:
            break

        if cursor + 2 > input_size:
            raise ValueError("Truncated LZ4 match offset")
        offset = compressed[cursor] | (compressed[cursor + 1] << 8)
        cursor += 2
        if offset == 0 or offset > len(output):
            raise ValueError(f"Invalid LZ4 match offset: {offset}")

        match_length = read_extended_length(token & 0x0F) + 4
        target_size = len(output) + match_length
        if target_size > maximum_size:
            raise ValueError(f"LZ4 output exceeds {maximum_size} bytes")
        # LZ4 permits overlapping matches, so append one byte at a time.
        while len(output) < target_size:
            output.append(output[-offset])

    return bytes(output)


def decompress_legacy_lz4_ramdisk(ramdisk: Path) -> bytes:
    data = ramdisk.read_bytes()
    if data[:4] != b"\x02\x21\x4c\x18":
        raise ValueError(f"Unexpected legacy LZ4 magic in {ramdisk}: {data[:4].hex()}")
    output = bytearray()
    cursor = 4
    block_limit = 8 * 1024 * 1024
    while cursor < len(data):
        if cursor + 4 > len(data):
            raise ValueError(f"Truncated legacy LZ4 block length in {ramdisk}")
        compressed_size = struct.unpack_from("<I", data, cursor)[0]
        cursor += 4
        if compressed_size == 0:
            break
        block_end = cursor + compressed_size
        if block_end > len(data):
            raise ValueError(f"Truncated legacy LZ4 block in {ramdisk}")
        output.extend(decompress_lz4_raw_block(data[cursor:block_end], block_limit))
        cursor = block_end
    if cursor != len(data):
        raise ValueError(f"Unexpected trailing bytes in legacy LZ4 ramdisk: {ramdisk}")
    return bytes(output)


def align_to_4(value: int) -> int:
    return (value + 3) & ~3


def parse_newc_cpio(data: bytes) -> list[dict[str, Any]]:
    """Parse the read-only newc CPIO archive carried by the ramdisk."""
    entries: list[dict[str, Any]] = []
    cursor = 0
    while cursor < len(data):
        if cursor + 110 > len(data):
            raise ValueError("Truncated CPIO header")
        if data[cursor : cursor + 6] != b"070701":
            raise ValueError(f"Unexpected CPIO magic at offset {cursor}: {data[cursor:cursor + 6]!r}")
        fields_raw = data[cursor + 6 : cursor + 110]
        fields = [int(fields_raw[index : index + 8], 16) for index in range(0, 104, 8)]
        filesize = fields[6]
        namesize = fields[11]
        name_start = cursor + 110
        name_end = name_start + namesize
        if namesize == 0 or name_end > len(data):
            raise ValueError("Invalid CPIO filename length")
        filename = data[name_start:name_end].split(b"\x00", 1)[0].decode("utf-8", errors="strict")
        data_start = align_to_4(name_end)
        data_end = data_start + filesize
        if data_end > len(data):
            raise ValueError(f"Truncated CPIO payload for {filename}")
        entries.append({"filename": filename, "fields": fields, "file_data": data[data_start:data_end]})
        cursor = align_to_4(data_end)
        if filename == "TRAILER!!!":
            return entries
    raise ValueError("CPIO archive lacks TRAILER!!! entry")


def parse_cpio_entries(ramdisk: Path) -> dict[str, dict[str, Any]]:
    entries = parse_newc_cpio(decompress_legacy_lz4_ramdisk(ramdisk))
    result: dict[str, dict[str, Any]] = {}
    for entry in entries:
        filename = entry.get("filename")
        if not filename or filename == "TRAILER!!!":
            continue
        data = entry["file_data"]
        result[filename] = {
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest().upper(),
            "mode": entry["fields"][1],
            "data": data,
        }
    return result


def selected_entry_report(
    original: dict[str, dict[str, Any]],
    candidate: dict[str, dict[str, Any]],
    paths: tuple[str, ...],
) -> dict[str, Any]:
    report: dict[str, Any] = {}
    for path in paths:
        left = original.get(path)
        right = candidate.get(path)
        if left is None and right is None:
            state = "absent_in_both"
        elif left is None:
            state = "only_candidate"
        elif right is None:
            state = "only_original"
        elif left["sha256"] == right["sha256"] and left["mode"] == right["mode"]:
            state = "identical"
        else:
            state = "different"
        report[path] = {
            "state": state,
            "original": None if left is None else {key: left[key] for key in ("size", "sha256", "mode")},
            "candidate": None if right is None else {key: right[key] for key in ("size", "sha256", "mode")},
        }
    return report


def text_diff_report(
    original: dict[str, dict[str, Any]],
    candidate: dict[str, dict[str, Any]],
    paths: tuple[str, ...],
) -> dict[str, Any]:
    """Return bounded unified diffs for small, reviewable configuration files."""
    report: dict[str, Any] = {}
    for path in paths:
        left = original.get(path)
        right = candidate.get(path)
        if left is None or right is None:
            continue
        try:
            original_lines = left["data"].decode("utf-8").splitlines()
            candidate_lines = right["data"].decode("utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        diff_lines = list(
            difflib.unified_diff(
                original_lines,
                candidate_lines,
                fromfile=f"original/{path}",
                tofile=f"candidate/{path}",
                lineterm="",
            )
        )
        report[path] = {
            "different": bool(diff_lines),
            "truncated": len(diff_lines) > MAX_TEXT_DIFF_LINES,
            "lines": diff_lines[:MAX_TEXT_DIFF_LINES],
        }
    return report


def text_lines(entry: dict[str, Any] | None, patterns: tuple[str, ...]) -> list[str]:
    if entry is None:
        return []
    text = entry["data"].decode("utf-8", errors="replace")
    needle = re.compile("|".join(re.escape(pattern) for pattern in patterns), re.IGNORECASE)
    return [line for line in text.splitlines() if needle.search(line)]


def all_rc_reboot_targets(entries: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    for path, entry in sorted(entries.items()):
        if not path.endswith(".rc"):
            continue
        for line in text_lines(entry, ("reboot_on_failure",)):
            found.append({"path": path, "line": line.strip()})
    return found


def parse_gpt_metadata(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    header_offset = 512
    if data[header_offset : header_offset + 8] != b"EFI PART":
        raise ValueError(f"Unexpected GPT signature in {path}")
    entry_lba = struct.unpack_from("<Q", data, header_offset + 72)[0]
    entry_count = struct.unpack_from("<I", data, header_offset + 80)[0]
    entry_size = struct.unpack_from("<I", data, header_offset + 84)[0]
    for index in range(entry_count):
        offset = entry_lba * 512 + index * entry_size
        if offset + entry_size > len(data):
            break
        if not any(data[offset : offset + 16]):
            continue
        name = data[offset + 56 : offset + 128].decode("utf-16-le").rstrip("\x00")
        if name != "metadata":
            continue
        first_lba = struct.unpack_from("<Q", data, offset + 32)[0]
        last_lba = struct.unpack_from("<Q", data, offset + 40)[0]
        sectors = last_lba - first_lba + 1
        return {
            "index": index + 1,
            "name": name,
            "first_lba": first_lba,
            "last_lba": last_lba,
            "sectors": sectors,
            "bytes": sectors * 512,
        }
    raise ValueError(f"metadata partition not found in GPT: {path}")


def parse_sys_partition_metadata(path: Path) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    current: dict[str, str] = {}
    for raw_line in lines:
        line = raw_line.strip()
        if line == "[partition]":
            current = {}
            continue
        match = re.match(r"(\w+)\s*=\s*(.+)$", line)
        if not match:
            continue
        current[match.group(1)] = match.group(2).strip()
        if current.get("name") == "metadata" and "size" in current:
            return current
    raise ValueError(f"metadata partition not found in {path}")


def fstab_metadata_lines(entries: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    output: dict[str, list[str]] = {}
    for path, entry in sorted(entries.items()):
        if "fstab" not in path:
            continue
        lines = text_lines(entry, ("/metadata", "metadata"))
        if lines:
            output[path] = lines
    return output


def binary_markers(entry: dict[str, Any] | None, needles: tuple[bytes, ...]) -> dict[str, bool]:
    if entry is None:
        return {needle.decode("ascii"): False for needle in needles}
    data = entry["data"]
    return {needle.decode("ascii"): needle in data for needle in needles}


def binary_marker_report(entry: dict[str, Any] | None, needles: tuple[bytes, ...]) -> dict[str, Any]:
    return {"present": entry is not None, "markers": binary_markers(entry, needles)}


def extract_packer_mapping(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    keys = re.findall(r'^\s*"([^"]+\.fex)"\s*:', text, flags=re.MULTILINE)
    return {
        "sha256": sha256_file(path),
        "modified_file_keys": keys,
        "mentions_metadata": "metadata" in text.lower(),
    }


def write_sha256_manifest(output_dir: Path) -> None:
    lines = []
    for path in sorted(output_dir.rglob("*")):
        if not path.is_file() or path.name == "SHA256SUMS.txt":
            continue
        lines.append(f"{sha256_file(path)}  {path}")
    (output_dir / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser(repository_root: Path) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path, help="New output directory under this repository")
    parser.add_argument("--original-boot", type=Path, default=repository_root / "firmware/extracted/boot.fex")
    parser.add_argument("--original-vendor-boot", type=Path, default=repository_root / "firmware/extracted/vendor_boot.fex")
    parser.add_argument("--candidate-boot", type=Path, default=repository_root / "work/boot.img")
    parser.add_argument("--candidate-vendor-boot", type=Path, default=repository_root / "work/vendor_boot.img")
    parser.add_argument("--gpt", type=Path, default=repository_root / "firmware/extracted/sunxi_gpt.fex")
    parser.add_argument("--sys-partition", type=Path, default=repository_root / "firmware/extracted/sys_partition.fex")
    parser.add_argument("--packer", type=Path, default=repository_root / "tools/pack_image.py")
    return parser


def main() -> int:
    repository_root = Path(__file__).resolve().parent.parent
    args = build_parser(repository_root).parse_args()
    output_dir = require_within(args.output_dir, repository_root, "output directory")
    if output_dir.exists():
        raise ValueError(f"Refusing to overwrite existing output directory: {output_dir}")

    inputs = {
        "original_boot": require_file(args.original_boot, "original boot"),
        "original_vendor_boot": require_file(args.original_vendor_boot, "original vendor_boot"),
        "candidate_boot": require_file(args.candidate_boot, "candidate boot"),
        "candidate_vendor_boot": require_file(args.candidate_vendor_boot, "candidate vendor_boot"),
        "gpt": require_file(args.gpt, "GPT"),
        "sys_partition": require_file(args.sys_partition, "sys_partition"),
        "packer": require_file(args.packer, "packer"),
    }

    output_dir.mkdir(parents=True)
    unpack_root = output_dir / "unpacked"
    unpack_root.mkdir()

    original_boot_info, original_boot_ramdisk = unpack_image(
        repository_root, inputs["original_boot"], unpack_root / "original_boot"
    )
    original_vendor_info, original_vendor_ramdisk = unpack_image(
        repository_root, inputs["original_vendor_boot"], unpack_root / "original_vendor_boot"
    )
    candidate_boot_info, candidate_boot_ramdisk = unpack_image(
        repository_root, inputs["candidate_boot"], unpack_root / "candidate_boot"
    )
    candidate_vendor_info, candidate_vendor_ramdisk = unpack_image(
        repository_root, inputs["candidate_vendor_boot"], unpack_root / "candidate_vendor_boot"
    )

    original_boot_entries = parse_cpio_entries(original_boot_ramdisk)
    candidate_boot_entries = parse_cpio_entries(candidate_boot_ramdisk)
    original_vendor_entries = parse_cpio_entries(original_vendor_ramdisk)
    candidate_vendor_entries = parse_cpio_entries(candidate_vendor_ramdisk)

    report: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "safety": {
            "device_commands": "none",
            "serial_io": "none",
            "input_images_modified": False,
            "output_directory": str(output_dir),
        },
        "inputs": {
            label: {"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size}
            for label, path in inputs.items()
        },
        "boot_headers": {
            "original_boot": original_boot_info,
            "candidate_boot": candidate_boot_info,
            "original_vendor_boot": original_vendor_info,
            "candidate_vendor_boot": candidate_vendor_info,
        },
        "metadata_partition": {
            "gpt": parse_gpt_metadata(inputs["gpt"]),
            "sys_partition": parse_sys_partition_metadata(inputs["sys_partition"]),
            "packer": extract_packer_mapping(inputs["packer"]),
        },
        "boot_ramdisk_diff": selected_entry_report(
            original_boot_entries, candidate_boot_entries, SELECTED_BOOT_PATHS
        ),
        "vendor_boot_ramdisk_diff": selected_entry_report(
            original_vendor_entries, candidate_vendor_entries, SELECTED_VENDOR_BOOT_PATHS
        ),
        "text_diffs": {
            "boot_ramdisk": text_diff_report(
                original_boot_entries, candidate_boot_entries, TEXT_DIFF_PATHS
            ),
            "vendor_boot_ramdisk": text_diff_report(
                original_vendor_entries, candidate_vendor_entries, TEXT_DIFF_PATHS
            ),
        },
        "metadata_fstab_lines": {
            "original_vendor_boot": fstab_metadata_lines(original_vendor_entries),
            "candidate_vendor_boot": fstab_metadata_lines(candidate_vendor_entries),
        },
        "candidate_boot_binary_markers": {
            "init": binary_marker_report(
                candidate_boot_entries.get("system/bin/init"),
                (b"InitFatalReboot", b"formattable", b"/metadata"),
            ),
            "libfs_mgr": binary_marker_report(
                candidate_boot_entries.get("system/lib/libfs_mgr.so"),
                (b"fs_mgr_do_format", b"/system/bin/mke2fs", b"/system/bin/e2fsdroid"),
            ),
            "apexd": binary_marker_report(
                candidate_boot_entries.get("system/bin/apexd"),
                (b"--bootstrap", b"/metadata/apex/sessions"),
            ),
        },
        "candidate_boot_rc_reboot_on_failure": all_rc_reboot_targets(candidate_boot_entries),
        "original_boot_rc_reboot_on_failure": all_rc_reboot_targets(original_boot_entries),
    }

    report_path = output_dir / "metadata-init-audit.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_sha256_manifest(output_dir)
    print(f"Metadata/init audit written to: {output_dir}")
    print(f"Report: {report_path}")
    print("Device commands: none; serial I/O: none; input images modified: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
