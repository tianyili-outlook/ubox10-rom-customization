#!/usr/bin/env python3
"""Inventory ELF files from Android ext4 partitions without extracting them."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from dataclasses import dataclass
import hashlib
import importlib.util
import io
import json
from pathlib import Path, PurePosixPath
import re
import struct
import sys
from typing import Iterable
import zipfile


REPO = Path(__file__).resolve().parents[1]
EXT4_READER_SCRIPT = REPO / "scripts" / "audit-logical-system-init.py"

ELF_MAGIC = b"\x7fELF"
PT_LOAD = 1
PT_DYNAMIC = 2
PT_INTERP = 3
DT_NULL = 0
DT_NEEDED = 1
DT_STRTAB = 5
DT_STRSZ = 10
DT_SONAME = 14

S_IFMT = 0xF000
S_IFREG = 0x8000
S_IFDIR = 0x4000

MACHINE_NAMES = {
    3: "x86",
    8: "MIPS",
    40: "ARM",
    62: "x86-64",
    183: "AArch64",
    243: "RISC-V",
    247: "BPF",
}

ARCHIVE_SUFFIXES = {".apk", ".jar", ".apex", ".capex"}
ELF_SUFFIXES = {".so", ".ko", ".o", ".odex", ".oat"}
SO_PATTERN = re.compile(r"\.so(?:\.|$)", re.IGNORECASE)


class InventoryError(RuntimeError):
    """Raised for malformed inputs or incomplete inventory sources."""


@dataclass(frozen=True)
class ElfRecord:
    partition: str
    path: str
    elf_class: str
    machine: str
    interpreter: str
    soname: str
    needed: tuple[str, ...]


@dataclass(frozen=True)
class PartitionInput:
    name: str
    image: Path
    manifest: Path | None
    source_manifest: Path | None


class MemoryByteSource:
    def __init__(self, data: bytes):
        self._data = data
        self.size = len(data)

    def read_at(self, offset: int, length: int) -> bytes:
        if offset < 0 or length < 0 or offset + length > self.size:
            raise InventoryError(
                f"memory image read out of range: offset={offset}, length={length}, size={self.size}"
            )
        return self._data[offset : offset + length]

    def close(self) -> None:
        return None


_EXT4_MODULE = None


def load_ext4_module():
    global _EXT4_MODULE
    if _EXT4_MODULE is not None:
        return _EXT4_MODULE
    spec = importlib.util.spec_from_file_location("ubox10_ext4_reader", EXT4_READER_SCRIPT)
    if spec is None or spec.loader is None:
        raise InventoryError(f"cannot load ext4 reader: {EXT4_READER_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _EXT4_MODULE = module
    return module


def _unpack_from(fmt: str, data: bytes, offset: int, context: str):
    size = struct.calcsize(fmt)
    if offset < 0 or offset + size > len(data):
        raise InventoryError(f"truncated ELF {context}")
    return struct.unpack_from(fmt, data, offset)


def _read_cstring(data: bytes, offset: int, limit: int, context: str) -> str:
    if offset < 0 or offset >= len(data) or offset >= limit:
        raise InventoryError(f"invalid ELF string offset for {context}: {offset}")
    end = data.find(b"\0", offset, min(limit, len(data)))
    if end < 0:
        raise InventoryError(f"unterminated ELF string for {context}")
    return data[offset:end].decode("utf-8", errors="replace")


def parse_elf(data: bytes, partition: str, path: str) -> ElfRecord:
    if len(data) < 20 or data[:4] != ELF_MAGIC:
        raise InventoryError(f"not a complete ELF file: {path}")

    elf_class_id = data[4]
    byte_order_id = data[5]
    if elf_class_id not in (1, 2):
        raise InventoryError(f"unsupported ELF class {elf_class_id}: {path}")
    if byte_order_id not in (1, 2):
        raise InventoryError(f"unsupported ELF byte order {byte_order_id}: {path}")

    endian = "<" if byte_order_id == 1 else ">"
    if elf_class_id == 1:
        header_fmt = endian + "16sHHIIIIIHHHHHH"
        expected_header_size = 52
        expected_ph_size = 32
        header = _unpack_from(header_fmt, data, 0, "header")
        machine_id = header[2]
        program_offset = header[5]
        program_entry_size = header[9]
        program_count = header[10]
        program_fmt = endian + "IIIIIIII"
        dynamic_fmt = endian + "iI"
    else:
        header_fmt = endian + "16sHHIQQQIHHHHHH"
        expected_header_size = 64
        expected_ph_size = 56
        header = _unpack_from(header_fmt, data, 0, "header")
        machine_id = header[2]
        program_offset = header[5]
        program_entry_size = header[9]
        program_count = header[10]
        program_fmt = endian + "IIQQQQQQ"
        dynamic_fmt = endian + "qQ"

    if len(data) < expected_header_size:
        raise InventoryError(f"truncated ELF header: {path}")
    if program_count and program_entry_size < expected_ph_size:
        raise InventoryError(f"invalid ELF program-header size: {path}")
    if program_count > 4096:
        raise InventoryError(f"unreasonable ELF program-header count: {path}")

    load_segments: list[tuple[int, int, int]] = []
    dynamic_segment: tuple[int, int] | None = None
    interpreter = ""

    for index in range(program_count):
        offset = program_offset + index * program_entry_size
        values = _unpack_from(program_fmt, data, offset, f"program header {index}")
        if elf_class_id == 1:
            segment_type, file_offset, virtual_address, _physical, file_size, _memory_size, _flags, _align = values
        else:
            segment_type, _flags, file_offset, virtual_address, _physical, file_size, _memory_size, _align = values

        if file_offset + file_size > len(data):
            raise InventoryError(f"ELF segment exceeds file: {path}")
        if segment_type == PT_LOAD:
            load_segments.append((virtual_address, file_offset, file_size))
        elif segment_type == PT_DYNAMIC:
            dynamic_segment = (file_offset, file_size)
        elif segment_type == PT_INTERP and file_size:
            raw = data[file_offset : file_offset + file_size]
            interpreter = raw.split(b"\0", 1)[0].decode("utf-8", errors="replace")

    string_address: int | None = None
    string_size: int | None = None
    needed_offsets: list[int] = []
    soname_offset: int | None = None

    if dynamic_segment is not None:
        dynamic_offset, dynamic_size = dynamic_segment
        entry_size = struct.calcsize(dynamic_fmt)
        if dynamic_size % entry_size:
            raise InventoryError(f"misaligned ELF dynamic segment: {path}")
        for offset in range(dynamic_offset, dynamic_offset + dynamic_size, entry_size):
            tag, value = _unpack_from(dynamic_fmt, data, offset, "dynamic entry")
            if tag == DT_NULL:
                break
            if tag == DT_NEEDED:
                needed_offsets.append(value)
            elif tag == DT_STRTAB:
                string_address = value
            elif tag == DT_STRSZ:
                string_size = value
            elif tag == DT_SONAME:
                soname_offset = value

    def virtual_to_file(address: int) -> int:
        for virtual_address, file_offset, file_size in load_segments:
            if virtual_address <= address < virtual_address + file_size:
                return file_offset + address - virtual_address
        if 0 <= address < len(data):
            return address
        raise InventoryError(f"cannot map ELF virtual address 0x{address:X}: {path}")

    needed: tuple[str, ...] = ()
    soname = ""
    if needed_offsets or soname_offset is not None:
        if string_address is None:
            raise InventoryError(f"ELF dynamic strings have no DT_STRTAB: {path}")
        string_offset = virtual_to_file(string_address)
        string_limit = len(data)
        if string_size is not None:
            string_limit = min(len(data), string_offset + string_size)
        values = [
            _read_cstring(data, string_offset + item, string_limit, f"DT_NEEDED in {path}")
            for item in needed_offsets
        ]
        needed = tuple(dict.fromkeys(values))
        if soname_offset is not None:
            soname = _read_cstring(
                data,
                string_offset + soname_offset,
                string_limit,
                f"DT_SONAME in {path}",
            )

    return ElfRecord(
        partition=partition,
        path=path,
        elf_class="ELF32" if elf_class_id == 1 else "ELF64",
        machine=MACHINE_NAMES.get(machine_id, f"EM_{machine_id}"),
        interpreter=interpreter,
        soname=soname,
        needed=needed,
    )


def is_candidate(path: str, mode: int | None = None) -> bool:
    lowered = path.lower()
    suffix = PurePosixPath(lowered).suffix
    if suffix in ELF_SUFFIXES or suffix in ARCHIVE_SUFFIXES:
        return True
    if SO_PATTERN.search(PurePosixPath(lowered).name):
        return True
    return mode is not None and bool(mode & 0o111)


def mounted_path(partition: str, raw_path: str) -> str:
    normalized = "/" + raw_path.lstrip("/")
    if partition == "system":
        return normalized
    prefix = "/" + partition
    if normalized == prefix or normalized.startswith(prefix + "/"):
        return normalized
    return prefix + normalized


def walk_ext4(reader, inode_number: int = 2, prefix: str = "") -> Iterable[tuple[str, object]]:
    seen_directories: set[int] = set()

    def visit(number: int, current: str):
        if number in seen_directories:
            return
        seen_directories.add(number)
        inode = reader.inode(number)
        for name, child_number in sorted(reader.directory(inode).items()):
            if name in (".", ".."):
                continue
            child = reader.inode(child_number)
            child_path = current + "/" + name if current else "/" + name
            file_type = child.mode & S_IFMT
            if file_type == S_IFDIR:
                yield from visit(child_number, child_path)
            elif file_type == S_IFREG:
                yield child_path, child

    yield from visit(inode_number, prefix)


def _scan_apex_payload(
    data: bytes,
    partition: str,
    path: str,
) -> list[ElfRecord]:
    module = load_ext4_module()
    source = MemoryByteSource(data)
    try:
        reader = module.Ext4Reader(source)
        records: list[ElfRecord] = []
        for inner_path, inode in walk_ext4(reader):
            if not is_candidate(inner_path, inode.mode):
                continue
            member_data = reader.read_inode_data(inode)
            output_path = path.rstrip("/") + inner_path
            if member_data.startswith(ELF_MAGIC):
                records.append(parse_elf(member_data, partition, output_path))
            elif PurePosixPath(inner_path.lower()).suffix in ARCHIVE_SUFFIXES:
                records.extend(scan_archive(member_data, partition, output_path))
        return records
    except Exception as exc:
        if isinstance(exc, InventoryError):
            raise
        raise InventoryError(f"cannot scan APEX payload {path}: {exc}") from exc


def scan_archive(data: bytes, partition: str, path: str) -> list[ElfRecord]:
    records: list[ElfRecord] = []
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for member in sorted(archive.infolist(), key=lambda item: item.filename):
                if member.is_dir():
                    continue
                member_name = member.filename.replace("\\", "/").lstrip("/")
                if not member_name or ".." in PurePosixPath(member_name).parts:
                    raise InventoryError(f"invalid archive member path in {path}: {member.filename}")
                member_path = f"{path}!/{member_name}"
                with archive.open(member) as source:
                    prefix = source.read(4)
                    if prefix == ELF_MAGIC:
                        records.append(parse_elf(prefix + source.read(), partition, member_path))
                        continue
                if member_name == "apex_payload.img":
                    records.extend(
                        _scan_apex_payload(
                            archive.read(member),
                            partition,
                            member_path,
                        )
                    )
                elif member_name == "original_apex" or member_name.lower().endswith(".apex"):
                    records.extend(scan_archive(archive.read(member), partition, member_path))
    except zipfile.BadZipFile as exc:
        raise InventoryError(f"invalid ZIP/APK/APEX archive: {path}") from exc
    return records


def load_manifest(path: Path) -> dict[str, dict[str, object]]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InventoryError(f"cannot read manifest {path}: {exc}") from exc
    entries = document.get("entries")
    if not isinstance(entries, list):
        raise InventoryError(f"manifest has no entries array: {path}")
    result: dict[str, dict[str, object]] = {}
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise InventoryError(f"invalid manifest entry: {path}")
        raw_path = "/" + entry["path"].lstrip("/")
        if raw_path in result:
            raise InventoryError(f"duplicate manifest path {raw_path}: {path}")
        result[raw_path] = entry
    return result


def _entry_mode(entry: dict[str, object]) -> int | None:
    value = entry.get("mode_octal")
    if not isinstance(value, str):
        return None
    try:
        return int(value, 8)
    except ValueError as exc:
        raise InventoryError(f"invalid mode_octal: {value}") from exc


def _entry_content_identity(entry: dict[str, object] | None) -> str | None:
    if entry is None:
        return None
    content = entry.get("content")
    if not isinstance(content, dict):
        return None
    value = content.get("sha256")
    return value if isinstance(value, str) else None


def scan_partition(
    item: PartitionInput,
    extras: dict[str, Path],
) -> list[ElfRecord]:
    module = load_ext4_module()
    source = module.open_super_source(item.image)
    try:
        reader = module.Ext4Reader(source)
        records: list[ElfRecord] = []
        consumed_extras: set[str] = set()

        if item.manifest is None:
            candidates = [
                (path, inode, None)
                for path, inode in walk_ext4(reader)
                if is_candidate(path, inode.mode)
            ]
        else:
            target_entries = load_manifest(item.manifest)
            source_entries = (
                load_manifest(item.source_manifest)
                if item.source_manifest is not None
                else target_entries
            )
            candidates = []
            for raw_path, target_entry in sorted(target_entries.items()):
                if target_entry.get("type") != "regular":
                    continue
                mode = _entry_mode(target_entry)
                if not is_candidate(raw_path, mode):
                    continue
                source_entry = source_entries.get(raw_path)
                extra = extras.get(raw_path)
                if item.source_manifest is not None and extra is None:
                    if source_entry is None:
                        raise InventoryError(
                            f"{item.name}:{raw_path} is absent from the source image; provide --extra"
                        )
                    target_identity = _entry_content_identity(target_entry)
                    source_identity = _entry_content_identity(source_entry)
                    if (
                        target_identity is not None
                        and source_identity is not None
                        and target_identity != source_identity
                    ):
                        raise InventoryError(
                            f"{item.name}:{raw_path} differs from the source image; provide --extra"
                        )
                inode = None if extra is not None else reader.lookup(raw_path)
                candidates.append((raw_path, inode, extra))

        for raw_path, inode, extra in candidates:
            if extra is not None:
                data = extra.read_bytes()
                if item.manifest is not None:
                    target_entry = target_entries.get(raw_path)
                    target_identity = _entry_content_identity(target_entry)
                    if (
                        target_identity is not None
                        and hashlib.sha256(data).hexdigest().upper()
                        != target_identity.upper()
                    ):
                        raise InventoryError(
                            f"extra bytes do not match target manifest: {item.name}:{raw_path}"
                        )
                consumed_extras.add(raw_path)
            else:
                data = reader.read_inode_data(inode)
            output_path = mounted_path(item.name, raw_path)
            if data.startswith(ELF_MAGIC):
                records.append(parse_elf(data, item.name, output_path))
            elif PurePosixPath(raw_path.lower()).suffix in ARCHIVE_SUFFIXES:
                records.extend(scan_archive(data, item.name, output_path))

        for raw_path, extra in sorted(extras.items()):
            if raw_path in consumed_extras:
                continue
            data = extra.read_bytes()
            output_path = mounted_path(item.name, raw_path)
            if data.startswith(ELF_MAGIC):
                records.append(parse_elf(data, item.name, output_path))
            elif PurePosixPath(raw_path.lower()).suffix in ARCHIVE_SUFFIXES:
                records.extend(scan_archive(data, item.name, output_path))
            else:
                raise InventoryError(f"extra input is neither ELF nor supported archive: {extra}")
        return records
    except Exception as exc:
        if isinstance(exc, InventoryError):
            raise
        raise InventoryError(f"cannot scan partition {item.name}: {exc}") from exc
    finally:
        source.close()


def write_csv(records: Iterable[ElfRecord], output: Path) -> None:
    ordered = sorted(records, key=lambda item: (item.partition, item.path))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=(
                "partition",
                "path",
                "class",
                "machine",
                "interpreter",
                "soname",
                "needed",
            ),
            lineterminator="\n",
        )
        writer.writeheader()
        for record in ordered:
            writer.writerow(
                {
                    "partition": record.partition,
                    "path": record.path,
                    "class": record.elf_class,
                    "machine": record.machine,
                    "interpreter": record.interpreter,
                    "soname": record.soname,
                    "needed": ";".join(record.needed),
                }
            )


def _is_kernel_module(record: ElfRecord) -> bool:
    direct_path = record.path.split("!/", 1)[0]
    return direct_path.lower().endswith(".ko")


def _is_app_packaged(record: ElfRecord) -> bool:
    lowered = record.path.lower()
    return ".apk!/" in lowered or ".jar!/" in lowered


def _provider_name(record: ElfRecord) -> str:
    if record.soname:
        return record.soname
    return PurePosixPath(record.path.rsplit("!/", 1)[-1]).name


def render_summary(records: Iterable[ElfRecord], label: str = "Test8r2") -> str:
    ordered = sorted(records, key=lambda item: (item.partition, item.path))
    platform = [
        record
        for record in ordered
        if not _is_kernel_module(record) and not _is_app_packaged(record)
    ]
    runtime = [record for record in platform if record.machine != "BPF"]
    packaged = [record for record in ordered if _is_app_packaged(record)]
    kernel = [record for record in ordered if _is_kernel_module(record)]

    partitions = sorted({record.partition for record in ordered})
    lines = [
        f"# {label} ELF 依赖摘要",
        "",
        f"共识别 {len(ordered)} 个 ELF：partition/APEX {len(platform)}、"
        f"APK/JAR 内嵌 {len(packaged)}、Kernel module {len(kernel)}。",
        "",
        "## ABI",
        "",
        "| Partition | ARM32 userspace | AArch64 userspace | Other platform ELF | Packaged ELF | Kernel modules |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for partition in partitions:
        subset = [record for record in ordered if record.partition == partition]
        arm32 = sum(
            1
            for record in subset
            if record in runtime and record.elf_class == "ELF32" and record.machine == "ARM"
        )
        aarch64 = sum(
            1
            for record in subset
            if record in runtime and record.elf_class == "ELF64" and record.machine == "AArch64"
        )
        other_platform = sum(record in platform and record not in runtime for record in subset)
        packaged_count = sum(record in packaged for record in subset)
        kernel_count = sum(record in kernel for record in subset)
        lines.append(
            f"| {partition} | {arm32} | {aarch64} | {other_platform} | "
            f"{packaged_count} | {kernel_count} |"
        )

    stack_patterns = {
        "graphics": ("mali", "gralloc", "hwcomposer", "vulkan", "graphics.mapper"),
        "media": ("omx", "codec", "cedar", "vdecoder", "video.decoder"),
        "Wi-Fi/BT": ("aic", "wifi", "wlan", "bluetooth"),
    }
    lines.extend(
        [
            "",
            "## 关键栈",
            "",
            "| Stack | ARM32 | AArch64 |",
            "|---|---:|---:|",
        ]
    )
    for name, patterns in stack_patterns.items():
        matches = [
            record
            for record in runtime
            if any(pattern in record.path.lower() for pattern in patterns)
        ]
        arm32 = sum(
            record.elf_class == "ELF32" and record.machine == "ARM"
            for record in matches
        )
        aarch64 = sum(
            record.elf_class == "ELF64" and record.machine == "AArch64"
            for record in matches
        )
        lines.append(f"| {name} | {arm32} | {aarch64} |")

    providers: dict[str, set[str]] = defaultdict(set)
    for record in runtime:
        providers[record.elf_class].add(_provider_name(record))

    unresolved: dict[tuple[str, str], set[str]] = defaultdict(set)
    for record in runtime:
        for dependency in record.needed:
            if dependency not in providers[record.elf_class]:
                unresolved[(record.elf_class, dependency)].add(record.path)

    counts = Counter(key[0] for key in unresolved)
    lines.extend(
        [
            "",
            "## 名称级依赖检查",
            "",
            "该检查只比较同 ELF class 的 SONAME/文件名，不代表 linker namespace 已通过。",
            "",
            f"- ELF32 未解析名称：{counts.get('ELF32', 0)}",
            f"- ELF64 未解析名称：{counts.get('ELF64', 0)}",
        ]
    )
    if unresolved:
        lines.extend(
            [
                "",
                "| Class | Missing name | Consumers |",
                "|---|---|---:|",
            ]
        )
        for (elf_class, dependency), consumers in sorted(unresolved.items())[:30]:
            lines.append(f"| {elf_class} | `{dependency}` | {len(consumers)} |")
        if len(unresolved) > 30:
            lines.append(f"| … | 其余 {len(unresolved) - 30} 项见 CSV 后续分析 |  |")

    aarch64_runtime = [
        record
        for record in runtime
        if record.elf_class == "ELF64" and record.machine == "AArch64"
    ]
    lines.extend(
        [
            "",
            "## 决策",
            "",
            (
                "- 发现 AArch64 用户空间 ELF；需逐项判断是否形成可用闭包。"
                if aarch64_runtime
                else "- 未发现 AArch64 用户空间 ELF；当前系统仍是纯 ARM32 用户空间。"
            ),
            "- APK 内嵌的其他 ABI 不等于系统具备对应平台 ABI。",
            "- 下一门禁是 64 位 Mali/Gralloc/Mapper/HWC/Vulkan 完整闭包。",
            "",
        ]
    )
    return "\n".join(lines)


def _parse_assignment(value: str, label: str) -> tuple[str, Path]:
    key, separator, raw_path = value.partition("=")
    if not separator or not key or not raw_path:
        raise InventoryError(f"{label} must use NAME=PATH: {value}")
    path = Path(raw_path).resolve()
    if not path.is_file():
        raise InventoryError(f"{label} input does not exist: {path}")
    return key, path


def _parse_extra(value: str) -> tuple[str, str, Path]:
    identity, separator, raw_file = value.partition("=")
    if not separator or ":" not in identity:
        raise InventoryError(
            f"--extra must use PARTITION:/logical/path=HOST_FILE: {value}"
        )
    partition, raw_path = identity.split(":", 1)
    logical_path = "/" + raw_path.lstrip("/")
    host_file = Path(raw_file).resolve()
    if not partition or not host_file.is_file():
        raise InventoryError(f"invalid --extra input: {value}")
    return partition, logical_path, host_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, fromfile_prefix_chars="@")
    parser.add_argument(
        "--partition",
        action="append",
        required=True,
        metavar="NAME=IMAGE",
        help="Raw or Android-sparse ext4 partition image; repeat per partition",
    )
    parser.add_argument(
        "--manifest",
        action="append",
        default=[],
        metavar="NAME=JSON",
        help="Target semantic manifest used to select current files",
    )
    parser.add_argument(
        "--source-manifest",
        action="append",
        default=[],
        metavar="NAME=JSON",
        help="Manifest matching IMAGE; changed selected files then require --extra",
    )
    parser.add_argument(
        "--extra",
        action="append",
        default=[],
        metavar="PARTITION:/PATH=FILE",
        help="Current file bytes absent from or changed against the source image",
    )
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--label", default="Test8r2")
    return parser


def _output_path(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(REPO)
    except ValueError as exc:
        raise InventoryError(f"output must remain inside repository: {resolved}") from exc
    return resolved


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    partition_paths = dict(
        _parse_assignment(value, "--partition") for value in args.partition
    )
    manifest_paths = dict(
        _parse_assignment(value, "--manifest") for value in args.manifest
    )
    source_manifest_paths = dict(
        _parse_assignment(value, "--source-manifest")
        for value in args.source_manifest
    )
    unknown = (set(manifest_paths) | set(source_manifest_paths)) - set(partition_paths)
    if unknown:
        raise InventoryError(
            f"manifest supplied for unknown partition(s): {', '.join(sorted(unknown))}"
        )

    extras: dict[str, dict[str, Path]] = defaultdict(dict)
    for value in args.extra:
        partition, logical_path, host_file = _parse_extra(value)
        if partition not in partition_paths:
            raise InventoryError(f"extra supplied for unknown partition: {partition}")
        if logical_path in extras[partition]:
            raise InventoryError(f"duplicate extra path: {partition}:{logical_path}")
        extras[partition][logical_path] = host_file

    records: list[ElfRecord] = []
    for name, image in partition_paths.items():
        item = PartitionInput(
            name=name,
            image=image,
            manifest=manifest_paths.get(name),
            source_manifest=source_manifest_paths.get(name),
        )
        partition_records = scan_partition(item, extras.get(name, {}))
        records.extend(partition_records)
        print(f"{name}: {len(partition_records)} ELF")

    unique: dict[tuple[str, str], ElfRecord] = {}
    for record in records:
        key = (record.partition, record.path)
        if key in unique:
            raise InventoryError(f"duplicate ELF output path: {record.partition}:{record.path}")
        unique[key] = record

    csv_output = _output_path(args.csv)
    summary_output = _output_path(args.summary)
    write_csv(unique.values(), csv_output)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.write_text(
        render_summary(unique.values(), label=args.label),
        encoding="utf-8",
        newline="\n",
    )
    print(f"total: {len(unique)} ELF")
    print(f"csv: {csv_output}")
    print(f"summary: {summary_output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except InventoryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
