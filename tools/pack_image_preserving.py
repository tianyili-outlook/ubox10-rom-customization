#!/usr/bin/env python3
"""Preservation-oriented IMAGEWTY v3 repacker.

Unlike the historical repacker, this tool streams unchanged stored payload bytes
from the immutable source container.  It is deliberately narrow: only named
primary payloads may be replaced and their existing ``V`` companions are
regenerated.  A run with no replacements is a byte-for-byte source copy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
from typing import BinaryIO, Iterable


MAGIC = b"IMAGEWTY"
MAIN_HEADER_SIZE = 96
FILE_HEADER_OFFSET = 1024
FILE_HEADER_SIZE = 1024
HEADER_LENGTH_FIELDS = 292
COPY_CHUNK = 8 * 1024 * 1024


def align(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(COPY_CHUNK), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def word_checksum_path(path: Path, length: int | None = None) -> int:
    """Return the IMAGEWTY checksum, treating a final partial word as zero-padded."""
    checksum = 0
    remaining = length
    carry = b""
    with path.open("rb") as stream:
        while remaining is None or remaining:
            wanted = COPY_CHUNK if remaining is None else min(COPY_CHUNK, remaining)
            block = stream.read(wanted)
            if not block:
                break
            if remaining is not None:
                remaining -= len(block)
            block = carry + block
            usable = len(block) - len(block) % 4
            if usable:
                checksum = (checksum + sum(struct.unpack(f"<{usable // 4}I", block[:usable]))) & 0xFFFFFFFF
            carry = block[usable:]
    if carry:
        checksum = (checksum + int.from_bytes(carry.ljust(4, b"\0"), "little")) & 0xFFFFFFFF
    if remaining not in (None, 0):
        raise ValueError(f"short read while checksumming {path}")
    return checksum


def parse_image(path: Path) -> tuple[bytearray, list[dict[str, int | str | bytes]]]:
    with path.open("rb") as stream:
        # The declared 96-byte structure sits within a preservation-critical
        # 1024-byte pre-file-header prefix. Stock images use opaque non-zero
        # bytes in the remainder, so it must not be synthesized as padding.
        prefix = bytearray(stream.read(FILE_HEADER_OFFSET))
        if len(prefix) != FILE_HEADER_OFFSET or prefix[:8] != MAGIC:
            raise ValueError(f"{path} is not an IMAGEWTY v3 image")
        main = prefix[:MAIN_HEADER_SIZE]
        # ``num_files`` is fields[14] of ``<8s22I`` (the magic occupies the
        # first tuple field), i.e. byte 60 rather than byte 52.
        num_files = struct.unpack_from("<I", main, 60)[0]
        if num_files <= 0 or FILE_HEADER_OFFSET + num_files * FILE_HEADER_SIZE > path.stat().st_size:
            raise ValueError(f"invalid IMAGEWTY file count: {num_files}")
        entries: list[dict[str, int | str | bytes]] = []
        for index in range(num_files):
            header_offset = FILE_HEADER_OFFSET + index * FILE_HEADER_SIZE
            stream.seek(header_offset)
            header = bytearray(stream.read(FILE_HEADER_SIZE))
            if len(header) != FILE_HEADER_SIZE:
                raise ValueError(f"truncated header {index}")
            filename = bytes(header[36:292]).split(b"\0", 1)[0].decode("ascii", "strict")
            stored_len, orig_len, offset = struct.unpack_from("<QQQ", header, HEADER_LENGTH_FIELDS)
            if offset + stored_len > path.stat().st_size:
                raise ValueError(f"payload outside source image: {filename}")
            entries.append({"index": index, "filename": filename, "stored_len": stored_len,
                            "orig_len": orig_len, "offset": offset, "header": bytes(header)})
    return prefix, entries


def _copy_range(source: BinaryIO, destination: BinaryIO, offset: int, length: int) -> None:
    source.seek(offset)
    remaining = length
    while remaining:
        block = source.read(min(COPY_CHUNK, remaining))
        if not block:
            raise ValueError("unexpected end of source container")
        destination.write(block)
        remaining -= len(block)


def _item_map(items: Iterable[str], action: str = "replacement") -> dict[str, Path]:
    mapping: dict[str, Path] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"{action} must be NAME=PATH, got {item!r}")
        name, value = item.split("=", 1)
        if not name or name.startswith("V"):
            raise ValueError(f"only primary payloads may be specified in {action}: {name!r}")
        target_path = Path(value).resolve()
        if not target_path.is_file():
            raise ValueError(f"{action} file not found: {target_path}")
        if name in mapping:
            raise ValueError(f"duplicate {action}: {name}")
        mapping[name] = target_path
    return mapping


def _replacement_map(items: Iterable[str]) -> dict[str, Path]:
    return _item_map(items, "replacement")


def pack(source: Path, output: Path, replacements: dict[str, Path],
         additions: dict[str, Path] | None = None, audit_path: Path | None = None) -> dict:
    if additions is None:
        additions = {}
    source = source.resolve()
    output = output.resolve()
    if not source.is_file():
        raise ValueError(f"source container not found: {source}")
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {output}")
    prefix, entries = parse_image(source)
    names = {str(entry["filename"]) for entry in entries}

    unknown = set(replacements) - names
    if unknown:
        raise ValueError(f"replacement name(s) absent from source: {sorted(unknown)}")
    already_present = set(additions) & names
    if already_present:
        raise ValueError(f"addition name(s) already present in source: {sorted(already_present)}")

    companions = {"V" + name for name in replacements if ("V" + name) in names}
    missing_companions = companions - names
    if missing_companions:
        raise ValueError(f"replacement(s) lack required V companion(s): {sorted(missing_companions)}")

    for name in additions:
        base_name = name[:-4] if name.endswith(".fex") else name
        subtype_str = (base_name.upper() + "_FEX").ljust(16, "0")[:16].encode("ascii")
        hdr_primary = bytearray(FILE_HEADER_SIZE)
        struct.pack_into("<II8s16sI", hdr_primary, 0, 256, FILE_HEADER_SIZE, b"RFSFAT16", subtype_str, 0)
        hdr_primary[36:36 + len(name.encode("ascii"))] = name.encode("ascii")

        c_name = "V" + name
        c_subtype_str = ("V" + base_name.upper() + "_FEX").ljust(16, "0")[:16].encode("ascii")
        hdr_companion = bytearray(FILE_HEADER_SIZE)
        struct.pack_into("<II8s16sI", hdr_companion, 0, 256, FILE_HEADER_SIZE, b"RFSFAT16", c_subtype_str, 0)
        hdr_companion[36:36 + len(c_name.encode("ascii"))] = c_name.encode("ascii")

        entries.append({"index": len(entries), "filename": name, "stored_len": 0, "orig_len": 0, "offset": 0,
                        "header": bytes(hdr_primary), "source_offset": None})
        entries.append({"index": len(entries), "filename": c_name, "stored_len": 0, "orig_len": 0, "offset": 0,
                        "header": bytes(hdr_companion), "source_offset": None})
        companions.add(c_name)

    struct.pack_into("<I", prefix, 60, len(entries))

    if not replacements and not additions:
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, output)
        audit = {"source": str(source), "source_sha256": sha256_path(source), "output": str(output),
                 "output_sha256": sha256_path(output), "replacements": [], "additions": [], "byte_identical": True}
        if audit_path:
            audit_path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
        return audit

    payloads: dict[str, dict] = {}
    for entry in entries:
        name = str(entry["filename"])
        if name in replacements or name in additions:
            data_path = replacements[name] if name in replacements else additions[name]
            kind = "replacement" if name in replacements else "addition"
            original_length = data_path.stat().st_size
            stored_length = align(original_length, 16)
            payloads[name] = {"kind": kind, "path": data_path, "orig_len": original_length,
                              "stored_len": stored_length, "checksum": word_checksum_path(data_path)}
        elif name in companions:
            primary = name[1:]
            checksum = payloads[primary]["checksum"]
            payloads[name] = {"kind": "companion", "bytes": struct.pack("<I", checksum) + b"\0" * 12,
                              "orig_len": 4, "stored_len": 16, "checksum": checksum}
        else:
            payloads[name] = {"kind": "preserved", "orig_len": int(entry["orig_len"]),
                              "stored_len": int(entry["stored_len"]), "source_offset": int(entry["offset"])}

    current = FILE_HEADER_OFFSET + len(entries) * FILE_HEADER_SIZE
    for entry in entries:
        current = align(current, 1024)
        payloads[str(entry["filename"])]["offset"] = current
        current += int(payloads[str(entry["filename"])]["stored_len"])
    image_size = align(current, 1024)
    struct.pack_into("<I", prefix, 24, image_size)

    output.parent.mkdir(parents=True, exist_ok=False) if not output.parent.exists() else None
    temp_fd, temp_name = tempfile.mkstemp(prefix=output.name + ".", suffix=".tmp", dir=output.parent)
    os.close(temp_fd)
    temp = Path(temp_name)
    try:
        with source.open("rb") as source_stream, temp.open("wb") as destination:
            destination.write(prefix)
            for entry in entries:
                name = str(entry["filename"])
                header = bytearray(entry["header"])
                payload = payloads[name]
                struct.pack_into("<QQQ", header, HEADER_LENGTH_FIELDS,
                                 int(payload["stored_len"]), int(payload["orig_len"]), int(payload["offset"]))
                destination.write(header)
            for entry in entries:
                name = str(entry["filename"])
                payload = payloads[name]
                target_offset = int(payload["offset"])
                gap = target_offset - destination.tell()
                if gap < 0:
                    raise ValueError(f"overlapping IMAGEWTY payload: {name}")
                destination.write(b"\0" * gap)
                if payload["kind"] == "preserved":
                    _copy_range(source_stream, destination, int(payload["source_offset"]), int(payload["stored_len"]))
                elif payload["kind"] in ("replacement", "addition"):
                    with Path(payload["path"]).open("rb") as replacement:
                        shutil.copyfileobj(replacement, destination, COPY_CHUNK)
                    destination.write(b"\0" * (int(payload["stored_len"]) - int(payload["orig_len"])))
                else:
                    destination.write(payload["bytes"])
            destination.write(b"\0" * (image_size - destination.tell()))
        os.replace(temp, output)
    finally:
        temp.unlink(missing_ok=True)

    audit_entries = []
    for entry in entries:
        name = str(entry["filename"])
        payload = payloads[name]
        audit_entries.append({"filename": name, "action": payload["kind"],
                              "source_offset": entry.get("source_offset") or entry["offset"],
                              "output_offset": payload["offset"], "orig_len": payload["orig_len"],
                              "stored_len": payload["stored_len"]})
    audit = {"source": str(source), "source_sha256": sha256_path(source), "output": str(output),
             "output_sha256": sha256_path(output), "image_size": image_size,
             "replacements": sorted(replacements), "additions": sorted(additions), "payloads": audit_entries}
    if audit_path:
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        audit_path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    return audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--replace", action="append", default=[], metavar="NAME=PATH")
    parser.add_argument("--add", action="append", default=[], metavar="NAME=PATH")
    parser.add_argument("--audit", type=Path)
    args = parser.parse_args()
    audit = pack(args.source, args.output, _item_map(args.replace, "replacement"),
                 _item_map(args.add, "addition"), args.audit)
    print(json.dumps({key: audit[key] for key in ("output", "output_sha256", "replacements", "additions")}, indent=2))


if __name__ == "__main__":
    main()

