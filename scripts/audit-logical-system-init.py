#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only, streaming audit of init/APEXd files in sparse Android super images.

The existing lpunpack.py materializes a .unsparse.img next to a sparse input,
even for --info.  This U3.2-e tool intentionally avoids that behavior.  It
implements just enough Android sparse, liblp and ext4 reading to hash selected
regular files directly from the system_a logical partition.  No partition
image is extracted and no input file is modified.
"""

from __future__ import annotations

import argparse
import bisect
import difflib
import hashlib
import json
import math
import struct
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Android sparse image constants.
SPARSE_MAGIC = 0xED26FF3A
CHUNK_RAW = 0xCAC1
CHUNK_FILL = 0xCAC2
CHUNK_DONT_CARE = 0xCAC3
CHUNK_CRC32 = 0xCAC4

# liblp constants.
LP_PARTITION_RESERVED_BYTES = 4096
LP_METADATA_GEOMETRY_MAGIC = 0x616C4467
LP_METADATA_HEADER_MAGIC = 0x414C5030
LP_SECTOR_SIZE = 512
LP_TARGET_TYPE_LINEAR = 0
LP_TARGET_TYPE_ZERO = 1

# ext4 constants.
EXT4_SUPERBLOCK_OFFSET = 1024
EXT4_SUPERBLOCK_SIZE = 1024
EXT4_SUPER_MAGIC = 0xEF53
EXT4_EXTENTS_FL = 0x00080000
S_IFMT = 0xF000
S_IFREG = 0x8000
S_IFDIR = 0x4000
S_IFLNK = 0xA000
EXTENT_HEADER_MAGIC = 0xF30A

SELECTED_PATHS = (
    "system/bin/init",
    "system/bin/mke2fs",
    "system/bin/e2fsdroid",
    "system/bin/apexd",
    "system/lib/libfs_mgr.so",
    "system/etc/init/apexd.rc",
    "system/etc/init/init.formatdevice.rc",
    "system/etc/init/hw/init.rc",
)
TEXT_PATHS = tuple(path for path in SELECTED_PATHS if path.endswith(".rc"))
ROOT_RELATIVE_PATHS = tuple(path.removeprefix("system/") for path in SELECTED_PATHS)
MAX_TEXT_DIFF_LINES = 400
MAX_DIRECTORY_ENTRIES = 512


class AuditError(RuntimeError):
    """Raised for malformed input or unsupported on-disk data."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def require_file(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_file():
        raise AuditError(f"{label} does not exist or is not a file: {resolved}")
    return resolved


def require_within(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise AuditError(f"{label} must be below repository root {root}: {resolved}") from exc
    return resolved


class ByteSource:
    """Random-access view of an uncompressed super image."""

    path: Path
    size: int

    def read_at(self, offset: int, length: int) -> bytes:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError

    def summary(self) -> dict[str, Any]:
        raise NotImplementedError


class RawByteSource(ByteSource):
    def __init__(self, path: Path):
        self.path = path
        self.size = path.stat().st_size
        self._file = path.open("rb")

    def read_at(self, offset: int, length: int) -> bytes:
        if offset < 0 or length < 0 or offset + length > self.size:
            raise AuditError(f"Raw read is out of range: offset={offset}, length={length}, size={self.size}")
        self._file.seek(offset)
        data = self._file.read(length)
        if len(data) != length:
            raise AuditError(f"Short raw read from {self.path}: expected {length}, got {len(data)}")
        return data

    def close(self) -> None:
        self._file.close()

    def summary(self) -> dict[str, Any]:
        return {"kind": "raw", "virtual_size": self.size}


@dataclass(frozen=True)
class SparseChunk:
    start: int
    end: int
    kind: str
    data_offset: int | None = None
    fill_pattern: bytes | None = None


class SparseByteSource(ByteSource):
    """Streaming random-access view of an Android sparse image.

    DONT_CARE blocks are represented as zeroes, matching the controlled output
    expected from an unsparse conversion.  The audit records whether a read
    actually touched such a block so that this assumption remains visible.
    """

    def __init__(self, path: Path):
        self.path = path
        self._file = path.open("rb")
        self._file_size = path.stat().st_size
        header = self._file.read(28)
        if len(header) != 28:
            raise AuditError(f"Sparse header is truncated: {path}")
        (
            magic,
            major,
            minor,
            file_header_size,
            chunk_header_size,
            block_size,
            total_blocks,
            total_chunks,
            image_checksum,
        ) = struct.unpack("<I4H4I", header)
        if magic != SPARSE_MAGIC:
            raise AuditError(f"Unexpected sparse magic in {path}: 0x{magic:08X}")
        if major != 1:
            raise AuditError(f"Unsupported sparse major version in {path}: {major}")
        if file_header_size < 28 or chunk_header_size < 12 or block_size == 0:
            raise AuditError(f"Invalid sparse header sizes in {path}")
        self._header = {
            "major_version": major,
            "minor_version": minor,
            "file_header_size": file_header_size,
            "chunk_header_size": chunk_header_size,
            "block_size": block_size,
            "total_blocks": total_blocks,
            "total_chunks": total_chunks,
            "image_checksum": f"0x{image_checksum:08X}",
        }
        self._chunks: list[SparseChunk] = []
        self._starts: list[int] = []
        self._dont_care_bytes_read = 0
        self._parse_chunks()
        self.size = total_blocks * block_size

    def _parse_chunks(self) -> None:
        cursor = self._header["file_header_size"]
        output_offset = 0
        for index in range(self._header["total_chunks"]):
            if cursor + self._header["chunk_header_size"] > self._file_size:
                raise AuditError(f"Truncated sparse chunk header {index} in {self.path}")
            self._file.seek(cursor)
            header_data = self._file.read(self._header["chunk_header_size"])
            chunk_type, _reserved, chunk_blocks, total_size = struct.unpack("<2H2I", header_data[:12])
            if total_size < self._header["chunk_header_size"]:
                raise AuditError(f"Invalid sparse chunk size {index} in {self.path}")
            data_size = total_size - self._header["chunk_header_size"]
            data_offset = cursor + self._header["chunk_header_size"]
            if cursor + total_size > self._file_size:
                raise AuditError(f"Sparse chunk {index} exceeds input length in {self.path}")
            output_size = chunk_blocks * self._header["block_size"]
            if chunk_type == CHUNK_RAW:
                if data_size != output_size:
                    raise AuditError(f"RAW sparse chunk {index} has invalid size in {self.path}")
                self._append_chunk(output_offset, output_size, "raw", data_offset=data_offset)
                output_offset += output_size
            elif chunk_type == CHUNK_FILL:
                if data_size != 4:
                    raise AuditError(f"FILL sparse chunk {index} has invalid size in {self.path}")
                self._file.seek(data_offset)
                self._append_chunk(output_offset, output_size, "fill", fill_pattern=self._file.read(4))
                output_offset += output_size
            elif chunk_type == CHUNK_DONT_CARE:
                if data_size != 0:
                    raise AuditError(f"DONT_CARE sparse chunk {index} has unexpected data in {self.path}")
                self._append_chunk(output_offset, output_size, "dont_care")
                output_offset += output_size
            elif chunk_type == CHUNK_CRC32:
                if data_size != 4 or output_size != 0:
                    raise AuditError(f"CRC32 sparse chunk {index} is invalid in {self.path}")
            else:
                raise AuditError(f"Unsupported sparse chunk type 0x{chunk_type:04X} in {self.path}")
            cursor += total_size
        expected_size = self._header["total_blocks"] * self._header["block_size"]
        if output_offset != expected_size:
            raise AuditError(f"Sparse output size mismatch in {self.path}: {output_offset} != {expected_size}")

    def _append_chunk(
        self,
        start: int,
        length: int,
        kind: str,
        *,
        data_offset: int | None = None,
        fill_pattern: bytes | None = None,
    ) -> None:
        if not length:
            return
        self._starts.append(start)
        self._chunks.append(SparseChunk(start, start + length, kind, data_offset, fill_pattern))

    @staticmethod
    def _repeat_fill(pattern: bytes, start: int, length: int) -> bytes:
        offset = start % len(pattern)
        needed = offset + length
        return (pattern * math.ceil(needed / len(pattern)))[offset:needed]

    def read_at(self, offset: int, length: int) -> bytes:
        if offset < 0 or length < 0 or offset + length > self.size:
            raise AuditError(f"Sparse read is out of range: offset={offset}, length={length}, size={self.size}")
        result = bytearray()
        cursor = offset
        end = offset + length
        while cursor < end:
            index = bisect.bisect_right(self._starts, cursor) - 1
            if index < 0:
                raise AuditError(f"Sparse read before first chunk at {cursor}")
            chunk = self._chunks[index]
            if not chunk.start <= cursor < chunk.end:
                raise AuditError(f"Sparse mapping gap at offset {cursor}")
            take = min(end, chunk.end) - cursor
            relative = cursor - chunk.start
            if chunk.kind == "raw":
                assert chunk.data_offset is not None
                self._file.seek(chunk.data_offset + relative)
                data = self._file.read(take)
                if len(data) != take:
                    raise AuditError(f"Short RAW chunk read at {cursor} in {self.path}")
                result.extend(data)
            elif chunk.kind == "fill":
                assert chunk.fill_pattern is not None
                result.extend(self._repeat_fill(chunk.fill_pattern, relative, take))
            elif chunk.kind == "dont_care":
                result.extend(b"\x00" * take)
                self._dont_care_bytes_read += take
            else:  # pragma: no cover - _parse_chunks limits this set.
                raise AuditError(f"Unsupported mapped sparse kind: {chunk.kind}")
            cursor += take
        return bytes(result)

    def close(self) -> None:
        self._file.close()

    def summary(self) -> dict[str, Any]:
        counts: dict[str, int] = {"raw": 0, "fill": 0, "dont_care": 0}
        for chunk in self._chunks:
            counts[chunk.kind] += 1
        return {
            "kind": "android_sparse",
            "virtual_size": self.size,
            "header": self._header,
            "mapped_chunk_counts": counts,
            "dont_care_bytes_read": self._dont_care_bytes_read,
        }


def open_super_source(path: Path) -> ByteSource:
    with path.open("rb") as source:
        magic_data = source.read(4)
    if len(magic_data) != 4:
        raise AuditError(f"Empty or truncated super image: {path}")
    if struct.unpack("<I", magic_data)[0] == SPARSE_MAGIC:
        return SparseByteSource(path)
    return RawByteSource(path)


@dataclass(frozen=True)
class LpExtent:
    num_sectors: int
    target_type: int
    target_data: int
    target_source: int


@dataclass(frozen=True)
class LpPartition:
    name: str
    attributes: int
    first_extent_index: int
    num_extents: int
    group_index: int


@dataclass(frozen=True)
class LpBlockDevice:
    first_logical_sector: int
    alignment: int
    alignment_offset: int
    block_device_size: int
    partition_name: str
    flags: int


@dataclass
class LpMetadata:
    geometry: dict[str, Any]
    header: dict[str, Any]
    partitions: list[LpPartition]
    extents: list[LpExtent]
    block_devices: list[LpBlockDevice]


def sha256_matches(expected: bytes, data: bytes) -> bool:
    return hashlib.sha256(data).digest() == expected


def parse_lp_metadata(source: ByteSource) -> LpMetadata:
    geometry_data = source.read_at(LP_PARTITION_RESERVED_BYTES, 4096)
    if len(geometry_data) < 52:
        raise AuditError("LP geometry is truncated")
    magic, struct_size, checksum, metadata_max_size, slot_count, logical_block_size = struct.unpack(
        "<2I32s3I", geometry_data[:52]
    )
    if magic != LP_METADATA_GEOMETRY_MAGIC:
        raise AuditError(f"Invalid LP geometry magic: 0x{magic:08X}")
    if struct_size < 52 or struct_size > len(geometry_data):
        raise AuditError(f"Invalid LP geometry struct size: {struct_size}")
    geometry_for_checksum = bytearray(geometry_data[:struct_size])
    geometry_for_checksum[8:40] = b"\x00" * 32
    if not sha256_matches(checksum, bytes(geometry_for_checksum)):
        raise AuditError("LP geometry SHA-256 checksum mismatch")
    if metadata_max_size == 0 or metadata_max_size % LP_SECTOR_SIZE or slot_count == 0:
        raise AuditError("Invalid LP metadata geometry values")

    primary_base = LP_PARTITION_RESERVED_BYTES + 2 * 4096
    candidates = [
        ("primary", primary_base),
        ("backup", primary_base + metadata_max_size * slot_count),
    ]
    selected: tuple[dict[str, Any], bytes, bytes] | None = None
    errors: list[str] = []
    for copy_name, offset in candidates:
        try:
            fixed = source.read_at(offset, 80)
            magic_value, major, minor, header_size, header_checksum, tables_size, tables_checksum = struct.unpack(
                "<IHHI32sI32s", fixed
            )
            if magic_value != LP_METADATA_HEADER_MAGIC:
                raise AuditError(f"invalid header magic 0x{magic_value:08X}")
            if header_size < 128 or header_size > metadata_max_size:
                raise AuditError(f"invalid header size {header_size}")
            if tables_size > metadata_max_size - header_size:
                raise AuditError(f"invalid table size {tables_size}")
            full_header = source.read_at(offset, header_size)
            header_for_checksum = bytearray(full_header)
            header_for_checksum[12:44] = b"\x00" * 32
            if not sha256_matches(header_checksum, bytes(header_for_checksum)):
                raise AuditError("header SHA-256 checksum mismatch")
            table_data = source.read_at(offset + header_size, tables_size)
            if not sha256_matches(tables_checksum, table_data):
                raise AuditError("tables SHA-256 checksum mismatch")
            descriptors = [struct.unpack("<3I", full_header[80 + index * 12 : 92 + index * 12]) for index in range(4)]
            for name, (table_offset, count, entry_size) in zip(
                ("partitions", "extents", "groups", "block_devices"), descriptors
            ):
                if entry_size == 0 or table_offset + count * entry_size > tables_size:
                    raise AuditError(f"invalid {name} table descriptor")
            selected = (
                {
                    "copy": copy_name,
                    "offset": offset,
                    "major_version": major,
                    "minor_version": minor,
                    "header_size": header_size,
                    "tables_size": tables_size,
                    "header_sha256_valid": True,
                    "tables_sha256_valid": True,
                    "descriptors": {
                        name: {"offset": values[0], "num_entries": values[1], "entry_size": values[2]}
                        for name, values in zip(("partitions", "extents", "groups", "block_devices"), descriptors)
                    },
                },
                full_header,
                table_data,
            )
            break
        except AuditError as exc:
            errors.append(f"{copy_name}: {exc}")
    if selected is None:
        raise AuditError("No valid LP metadata copy: " + "; ".join(errors))
    header_report, _full_header, tables = selected

    def table_bytes(name: str) -> tuple[int, int, int, bytes]:
        descriptor = header_report["descriptors"][name]
        offset = descriptor["offset"]
        count = descriptor["num_entries"]
        size = descriptor["entry_size"]
        return offset, count, size, tables[offset : offset + count * size]

    _offset, count, size, data = table_bytes("partitions")
    if size < 52:
        raise AuditError("LP partition entry size is too small")
    partitions = [
        LpPartition(
            name=data[index * size : index * size + 36].split(b"\x00", 1)[0].decode("ascii", errors="strict"),
            attributes=struct.unpack_from("<I", data, index * size + 36)[0],
            first_extent_index=struct.unpack_from("<I", data, index * size + 40)[0],
            num_extents=struct.unpack_from("<I", data, index * size + 44)[0],
            group_index=struct.unpack_from("<I", data, index * size + 48)[0],
        )
        for index in range(count)
    ]

    _offset, count, size, data = table_bytes("extents")
    if size < 24:
        raise AuditError("LP extent entry size is too small")
    extents = [
        LpExtent(*struct.unpack_from("<QIQI", data, index * size)) for index in range(count)
    ]

    _offset, count, size, data = table_bytes("block_devices")
    if size < 64:
        raise AuditError("LP block-device entry size is too small")
    block_devices = [
        LpBlockDevice(
            first_logical_sector=struct.unpack_from("<Q", data, index * size)[0],
            alignment=struct.unpack_from("<I", data, index * size + 8)[0],
            alignment_offset=struct.unpack_from("<I", data, index * size + 12)[0],
            block_device_size=struct.unpack_from("<Q", data, index * size + 16)[0],
            partition_name=data[index * size + 24 : index * size + 60]
            .split(b"\x00", 1)[0]
            .decode("ascii", errors="strict"),
            flags=struct.unpack_from("<I", data, index * size + 60)[0],
        )
        for index in range(count)
    ]
    return LpMetadata(
        geometry={
            "struct_size": struct_size,
            "metadata_max_size": metadata_max_size,
            "metadata_slot_count": slot_count,
            "logical_block_size": logical_block_size,
            "sha256_valid": True,
        },
        header=header_report,
        partitions=partitions,
        extents=extents,
        block_devices=block_devices,
    )


@dataclass(frozen=True)
class LogicalExtent:
    start: int
    end: int
    target_type: int
    physical_offset: int | None


class LogicalPartitionSource(ByteSource):
    def __init__(self, source: ByteSource, metadata: LpMetadata, partition_name: str):
        self.path = source.path
        self._source = source
        partition = next((item for item in metadata.partitions if item.name == partition_name), None)
        if partition is None:
            names = ", ".join(item.name for item in metadata.partitions)
            raise AuditError(f"Logical partition {partition_name!r} is absent; available: {names}")
        self.partition_name = partition_name
        self._extents: list[LogicalExtent] = []
        logical_offset = 0
        for number in range(partition.num_extents):
            extent_index = partition.first_extent_index + number
            if extent_index >= len(metadata.extents):
                raise AuditError(f"Partition {partition_name} references invalid extent index {extent_index}")
            extent = metadata.extents[extent_index]
            length = extent.num_sectors * LP_SECTOR_SIZE
            if length == 0:
                continue
            if extent.target_type == LP_TARGET_TYPE_LINEAR:
                if extent.target_source >= len(metadata.block_devices):
                    raise AuditError(f"Partition {partition_name} references invalid block device")
                physical_offset = extent.target_data * LP_SECTOR_SIZE
                if physical_offset + length > source.size:
                    raise AuditError(f"Partition {partition_name} extent exceeds super image")
            elif extent.target_type == LP_TARGET_TYPE_ZERO:
                physical_offset = None
            else:
                raise AuditError(f"Unsupported target type {extent.target_type} in {partition_name}")
            self._extents.append(LogicalExtent(logical_offset, logical_offset + length, extent.target_type, physical_offset))
            logical_offset += length
        if not self._extents:
            raise AuditError(f"Logical partition {partition_name} has no usable extents")
        self._starts = [extent.start for extent in self._extents]
        self.size = logical_offset

    def read_at(self, offset: int, length: int) -> bytes:
        if offset < 0 or length < 0 or offset + length > self.size:
            raise AuditError(f"Logical partition read out of range: {self.partition_name}")
        result = bytearray()
        cursor = offset
        end = offset + length
        while cursor < end:
            index = bisect.bisect_right(self._starts, cursor) - 1
            if index < 0:
                raise AuditError(f"Logical partition mapping gap at {cursor}")
            extent = self._extents[index]
            if not extent.start <= cursor < extent.end:
                raise AuditError(f"Logical partition mapping gap at {cursor}")
            take = min(end, extent.end) - cursor
            if extent.target_type == LP_TARGET_TYPE_ZERO:
                result.extend(b"\x00" * take)
            else:
                assert extent.physical_offset is not None
                result.extend(self._source.read_at(extent.physical_offset + cursor - extent.start, take))
            cursor += take
        return bytes(result)

    def close(self) -> None:
        # The parent source owns the file descriptor.
        return None

    def summary(self) -> dict[str, Any]:
        return {
            "partition": self.partition_name,
            "size": self.size,
            "extents": [
                {
                    "logical_start": item.start,
                    "logical_end": item.end,
                    "target_type": "linear" if item.target_type == LP_TARGET_TYPE_LINEAR else "zero",
                    "physical_offset": item.physical_offset,
                }
                for item in self._extents
            ],
        }


@dataclass(frozen=True)
class Ext4Extent:
    logical_block: int
    physical_block: int
    length_blocks: int
    initialized: bool


@dataclass
class Ext4Inode:
    number: int
    mode: int
    size: int
    flags: int
    block_data: bytes


class Ext4Reader:
    def __init__(self, source: ByteSource):
        self._source = source
        superblock = source.read_at(EXT4_SUPERBLOCK_OFFSET, EXT4_SUPERBLOCK_SIZE)
        magic = struct.unpack_from("<H", superblock, 56)[0]
        if magic != EXT4_SUPER_MAGIC:
            raise AuditError(f"Invalid ext4 magic: 0x{magic:04X}")
        self.inodes_count = struct.unpack_from("<I", superblock, 0)[0]
        self.blocks_count = struct.unpack_from("<I", superblock, 4)[0]
        log_block_size = struct.unpack_from("<I", superblock, 24)[0]
        self.block_size = 1024 << log_block_size
        self.blocks_per_group = struct.unpack_from("<I", superblock, 32)[0]
        self.inodes_per_group = struct.unpack_from("<I", superblock, 40)[0]
        self.inode_size = struct.unpack_from("<H", superblock, 88)[0] or 128
        self.feature_incompat = struct.unpack_from("<I", superblock, 96)[0]
        self.desc_size = struct.unpack_from("<H", superblock, 254)[0] or 32
        if self.block_size not in (1024, 2048, 4096, 8192, 16384, 32768, 65536):
            raise AuditError(f"Unsupported ext4 block size: {self.block_size}")
        if self.inode_size < 128 or self.inode_size > self.block_size or self.inodes_per_group == 0:
            raise AuditError("Invalid ext4 inode geometry")
        if self.desc_size < 32:
            raise AuditError("Invalid ext4 group descriptor size")
        self._gdt_offset = 2 * self.block_size if self.block_size == 1024 else self.block_size
        self._groups_count = math.ceil(self.blocks_count / self.blocks_per_group)
        if self._gdt_offset + self._groups_count * self.desc_size > source.size:
            raise AuditError("Ext4 group descriptor table exceeds logical partition")
        self._superblock_summary = {
            "magic": "0xEF53",
            "block_size": self.block_size,
            "blocks_count": self.blocks_count,
            "inodes_count": self.inodes_count,
            "inodes_per_group": self.inodes_per_group,
            "inode_size": self.inode_size,
            "group_descriptor_size": self.desc_size,
            "feature_incompat": f"0x{self.feature_incompat:08X}",
        }

    def summary(self) -> dict[str, Any]:
        return self._superblock_summary

    def _read_block(self, block_number: int) -> bytes:
        offset = block_number * self.block_size
        return self._source.read_at(offset, self.block_size)

    def inode(self, number: int) -> Ext4Inode:
        if number < 1 or number > self.inodes_count:
            raise AuditError(f"Invalid ext4 inode number: {number}")
        group = (number - 1) // self.inodes_per_group
        group_inode_index = (number - 1) % self.inodes_per_group
        descriptor = self._source.read_at(self._gdt_offset + group * self.desc_size, self.desc_size)
        inode_table_lo = struct.unpack_from("<I", descriptor, 8)[0]
        inode_table_hi = struct.unpack_from("<I", descriptor, 40)[0] if self.desc_size >= 64 else 0
        inode_table = inode_table_lo | (inode_table_hi << 32)
        raw = self._source.read_at(inode_table * self.block_size + group_inode_index * self.inode_size, self.inode_size)
        mode = struct.unpack_from("<H", raw, 0)[0]
        size_lo = struct.unpack_from("<I", raw, 4)[0]
        flags = struct.unpack_from("<I", raw, 32)[0]
        size_hi = struct.unpack_from("<I", raw, 108)[0] if (mode & S_IFMT) == S_IFREG and self.inode_size >= 112 else 0
        return Ext4Inode(number, mode, size_lo | (size_hi << 32), flags, raw[40:100])

    def _extent_leaf(self, data: bytes, expected_depth: int | None = None) -> list[Ext4Extent]:
        if len(data) < 12:
            raise AuditError("Truncated ext4 extent header")
        magic, entries, maximum, depth, _generation = struct.unpack_from("<HHHHI", data, 0)
        if magic != EXTENT_HEADER_MAGIC or entries > maximum:
            raise AuditError("Invalid ext4 extent header")
        if expected_depth is not None and depth != expected_depth:
            raise AuditError("Unexpected ext4 extent-tree depth")
        if depth == 0:
            result: list[Ext4Extent] = []
            for index in range(entries):
                offset = 12 + index * 12
                if offset + 12 > len(data):
                    raise AuditError("Truncated ext4 leaf extent")
                logical_block, raw_length, start_hi, start_lo = struct.unpack_from("<IHHI", data, offset)
                length = raw_length & 0x7FFF
                if length == 0:
                    length = 32768
                result.append(
                    Ext4Extent(logical_block, start_lo | (start_hi << 32), length, not bool(raw_length & 0x8000))
                )
            return result
        result = []
        for index in range(entries):
            offset = 12 + index * 12
            if offset + 12 > len(data):
                raise AuditError("Truncated ext4 index extent")
            _logical_block, leaf_lo, leaf_hi, _unused = struct.unpack_from("<IIHH", data, offset)
            child_block = leaf_lo | (leaf_hi << 32)
            result.extend(self._extent_leaf(self._read_block(child_block), expected_depth=depth - 1))
        return result

    def _inode_extents(self, inode: Ext4Inode) -> list[Ext4Extent]:
        if not inode.flags & EXT4_EXTENTS_FL:
            raise AuditError(f"Inode {inode.number} does not use extents; unsupported by this audit")
        extents = sorted(self._extent_leaf(inode.block_data), key=lambda item: item.logical_block)
        previous_end = 0
        for extent in extents:
            if extent.logical_block < previous_end:
                raise AuditError(f"Overlapping ext4 extents in inode {inode.number}")
            previous_end = extent.logical_block + extent.length_blocks
        return extents

    def read_inode_data(self, inode: Ext4Inode) -> bytes:
        if inode.size == 0:
            return b""
        extents = self._inode_extents(inode)
        output = bytearray()
        logical_block = 0
        remaining = inode.size
        extent_index = 0
        while remaining:
            while extent_index < len(extents) and logical_block >= extents[extent_index].logical_block + extents[extent_index].length_blocks:
                extent_index += 1
            if extent_index == len(extents) or logical_block < extents[extent_index].logical_block:
                block = b"\x00" * self.block_size
            else:
                extent = extents[extent_index]
                physical_block = extent.physical_block + logical_block - extent.logical_block
                block = b"\x00" * self.block_size if not extent.initialized else self._read_block(physical_block)
            take = min(remaining, self.block_size)
            output.extend(block[:take])
            remaining -= take
            logical_block += 1
        return bytes(output)

    def directory(self, inode: Ext4Inode) -> dict[str, int]:
        if inode.mode & S_IFMT != S_IFDIR:
            raise AuditError(f"Inode {inode.number} is not a directory")
        data = self.read_inode_data(inode)
        entries: dict[str, int] = {}
        cursor = 0
        while cursor < len(data):
            if cursor + 8 > len(data):
                raise AuditError(f"Truncated ext4 directory entry in inode {inode.number}")
            child_inode, record_length, name_length, _file_type = struct.unpack_from("<IHBB", data, cursor)
            if record_length < 8 or record_length % 4 or cursor + record_length > len(data) or name_length > record_length - 8:
                raise AuditError(f"Invalid ext4 directory entry in inode {inode.number}")
            if child_inode:
                name = data[cursor + 8 : cursor + 8 + name_length].decode("utf-8", errors="strict")
                entries[name] = child_inode
            cursor += record_length
        return entries

    def lookup(self, path: str) -> Ext4Inode:
        inode = self.inode(2)
        for component in [part for part in path.split("/") if part]:
            entries = self.directory(inode)
            try:
                inode = self.inode(entries[component])
            except KeyError as exc:
                raise FileNotFoundError(path) from exc
        return inode


@dataclass
class FileObservation:
    state: str
    inode: int | None = None
    mode: int | None = None
    bytes: int | None = None
    sha256: str | None = None
    data: bytes | None = None
    error: str | None = None

    def public(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "inode": self.inode,
            "mode": None if self.mode is None else f"0o{self.mode:o}",
            "bytes": self.bytes,
            "sha256": self.sha256,
            "error": self.error,
        }


def observe_file(ext4: Ext4Reader, path: str) -> FileObservation:
    try:
        inode = ext4.lookup(path)
    except FileNotFoundError:
        return FileObservation(state="absent")
    except AuditError as exc:
        return FileObservation(state="error", error=str(exc))
    if inode.mode & S_IFMT != S_IFREG:
        return FileObservation(state="not_regular_file", inode=inode.number, mode=inode.mode, bytes=inode.size)
    try:
        data = ext4.read_inode_data(inode)
    except AuditError as exc:
        return FileObservation(state="error", inode=inode.number, mode=inode.mode, bytes=inode.size, error=str(exc))
    return FileObservation(
        state="present",
        inode=inode.number,
        mode=inode.mode,
        bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest().upper(),
        data=data,
    )


def observe_directory(ext4: Ext4Reader, path: str) -> dict[str, Any]:
    try:
        inode = ext4.lookup(path)
    except FileNotFoundError:
        return {"state": "absent"}
    except AuditError as exc:
        return {"state": "error", "error": str(exc)}
    if inode.mode & S_IFMT != S_IFDIR:
        return {"state": "not_directory", "inode": inode.number, "mode": f"0o{inode.mode:o}"}
    try:
        names = sorted(name for name in ext4.directory(inode) if name not in (".", ".."))
    except AuditError as exc:
        return {"state": "error", "inode": inode.number, "error": str(exc)}
    return {
        "state": "present",
        "inode": inode.number,
        "entries_count": len(names),
        "entries_truncated": len(names) > MAX_DIRECTORY_ENTRIES,
        "entries": names[:MAX_DIRECTORY_ENTRIES],
    }


def text_diff(original: FileObservation, candidate: FileObservation, path: str) -> dict[str, Any]:
    if original.state != "present" or candidate.state != "present":
        return {"available": False, "reason": "file_not_present_in_both"}
    try:
        left = original.data.decode("utf-8").splitlines()
        right = candidate.data.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        return {"available": False, "reason": "not_utf8"}
    lines = list(
        difflib.unified_diff(left, right, fromfile=f"official/{path}", tofile=f"candidate/{path}", lineterm="")
    )
    return {"available": True, "different": bool(lines), "truncated": len(lines) > MAX_TEXT_DIFF_LINES, "lines": lines[:MAX_TEXT_DIFF_LINES]}


def inspect_super(
    path: Path, partition_name: str
) -> tuple[dict[str, Any], dict[str, FileObservation], dict[str, FileObservation]]:
    source = open_super_source(path)
    try:
        metadata = parse_lp_metadata(source)
        logical = LogicalPartitionSource(source, metadata, partition_name)
        ext4 = Ext4Reader(logical)
        observations = {item: observe_file(ext4, item) for item in SELECTED_PATHS}
        root_relative_observations = {item: observe_file(ext4, item) for item in ROOT_RELATIVE_PATHS}
        report = {
            "source": source.summary(),
            "lp_metadata": {
                "geometry": metadata.geometry,
                "header": metadata.header,
                "block_devices": [
                    {
                        "partition_name": item.partition_name,
                        "first_logical_sector": item.first_logical_sector,
                        "block_device_size": item.block_device_size,
                    }
                    for item in metadata.block_devices
                ],
            },
            "logical_partition": logical.summary(),
            "ext4": ext4.summary(),
            "directory_observations": {
                "/": observe_directory(ext4, ""),
                "/system": observe_directory(ext4, "system"),
            },
        }
        # source.summary() must be read after all data reads so DONT_CARE use is current.
        report["source"] = source.summary()
        return report, observations, root_relative_observations
    finally:
        source.close()


def write_manifest(output_dir: Path) -> None:
    lines: list[str] = []
    for path in sorted(output_dir.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS.txt":
            lines.append(f"{sha256_file(path)}  {path}")
    (output_dir / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser(repository_root: Path) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path, help="New evidence directory below this repository")
    parser.add_argument("--official-super", type=Path, default=repository_root / "firmware/extracted/super.fex")
    parser.add_argument("--candidate-super", type=Path, default=repository_root / "work/super.img")
    parser.add_argument("--partition", default="system_a", help="Logical partition to inspect (default: system_a)")
    return parser


def main() -> int:
    repository_root = Path(__file__).resolve().parent.parent
    args = build_parser(repository_root).parse_args()
    output_dir = require_within(args.output_dir, repository_root, "output directory")
    if output_dir.exists():
        raise AuditError(f"Refusing to overwrite existing output directory: {output_dir}")
    official_super = require_file(args.official_super, "official super")
    candidate_super = require_file(args.candidate_super, "candidate super")

    official_report, official_observations, official_root_relative = inspect_super(official_super, args.partition)
    candidate_report, candidate_observations, candidate_root_relative = inspect_super(candidate_super, args.partition)
    file_report = {
        path: {
            "official": official_observations[path].public(),
            "candidate": candidate_observations[path].public(),
            "same_sha256": (
                official_observations[path].state == "present"
                and candidate_observations[path].state == "present"
                and official_observations[path].sha256 == candidate_observations[path].sha256
            ),
        }
        for path in SELECTED_PATHS
    }
    report: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "safety": {
            "device_commands": "none",
            "serial_io": "none",
            "input_images_modified": False,
            "logical_partition_images_extracted": False,
            "output_directory": str(output_dir),
        },
        "inputs": {
            "official_super": {"path": str(official_super), "bytes": official_super.stat().st_size, "sha256": sha256_file(official_super)},
            "candidate_super": {"path": str(candidate_super), "bytes": candidate_super.stat().st_size, "sha256": sha256_file(candidate_super)},
        },
        "partition": args.partition,
        "official": official_report,
        "candidate": candidate_report,
        "files": file_report,
        "root_relative_files": {
            path: {
                "official": official_root_relative[path].public(),
                "candidate": candidate_root_relative[path].public(),
            }
            for path in ROOT_RELATIVE_PATHS
        },
        "text_diffs": {
            path: text_diff(official_observations[path], candidate_observations[path], path) for path in TEXT_PATHS
        },
        "interpretation_boundary": (
            "This report proves local official/candidate logical-system file provenance only. "
            "It does not prove which super image or logical partition is installed on the device."
        ),
    }
    output_dir.mkdir(parents=True)
    report_path = output_dir / "logical-system-init-audit.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_manifest(output_dir)
    print(f"Logical system init audit written to: {output_dir}")
    print(f"Report: {report_path}")
    print("Device commands: none; serial I/O: none; input images modified: false; partition images extracted: false")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AuditError as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(2)
