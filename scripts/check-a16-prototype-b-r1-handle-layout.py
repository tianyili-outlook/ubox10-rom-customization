#!/usr/bin/env python3
"""Fail-closed ARM32/ARM64 private_handle_t layout gate for Prototype B r1."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


PRIVATE_FIELDS = (
    "share_fd", "share_attr_fd", "metadata_fd", "magic", "flags", "width",
    "height", "req_format", "format", "producer_usage", "usage",
    "consumer_usage", "internal_format", "stride", "byte_stride",
    "internalWidth", "internalHeight", "alloc_format", "plane_info", "size",
    "layer_count", "base", "padding", "aw_buf_id", "backing_store_id",
    "backing_store_size", "cpu_read", "cpu_write", "allocating_pid",
    "remote_pid", "ref_count", "attr_base", "padding3", "ion_metadata_size",
    "ion_metadata_flag", "yuv_info", "fd", "offset", "padding4", "min_pgsz",
    "aw_byte_align",
)
PLANE_FIELDS = ("offset", "byte_stride", "alloc_width", "alloc_height")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_layout(output: str, record: str) -> tuple[str, dict[str, int], int, int]:
    lines = output.splitlines()
    start = next(
        (index for index, line in enumerate(lines) if re.search(rf"\| struct {re.escape(record)}$", line)),
        None,
    )
    if start is None:
        raise RuntimeError(f"compiler did not emit layout for {record}")
    block: list[str] = []
    size = alignment = None
    for line in lines[start:]:
        if re.match(r"^\s*\d+\s*\|", line) or re.match(r"^\s*\|", line):
            block.append(line.rstrip())
        match = re.search(r"\[sizeof=(\d+),.*align=(\d+),", line)
        if match:
            size, alignment = map(int, match.groups())
        if "nvalign=" in line:
            break
    if size is None or alignment is None:
        raise RuntimeError(f"compiler did not emit size/alignment for {record}")

    names = PRIVATE_FIELDS if record == "private_handle_t" else PLANE_FIELDS
    offsets: dict[str, int] = {}
    for line in block:
        offset_match = re.match(r"^\s*(\d+)\s*\|", line)
        if not offset_match:
            continue
        for name in names:
            if re.search(rf"\b{re.escape(name)}$", line):
                offsets[name] = int(offset_match.group(1))
    missing = sorted(set(names) - offsets.keys())
    if missing:
        raise RuntimeError(f"layout omitted fields for {record}: {', '.join(missing)}")
    normalized = "\n".join(re.sub(r"^\s+", "", line) for line in block)
    return normalized, offsets, size, alignment


def compile_layout(source: Path, abi: str) -> dict[str, object]:
    clang = source / "prebuilts/clang/host/linux-x86/clang-r547379/bin/clang++"
    asm = "asm-arm64" if abi == "arm64" else "asm-arm"
    target = "aarch64-linux-android10000" if abi == "arm64" else "armv7a-linux-androideabi10000"
    command = [
        str(clang), "-target", target, "-std=gnu++20", "-nostdlibinc",
        "-Ihardware/aw/gpu/include", "-Ihardware/aw/gpu/mali-bifrost/gralloc/src",
        "-Isystem/core/libcutils/include", "-Ibionic/libc/include",
        "-isystem", f"bionic/libc/kernel/uapi/{asm}",
        "-isystem", "bionic/libc/kernel/uapi",
        "-isystem", "bionic/libc/kernel/android/scsi",
        "-isystem", "bionic/libc/kernel/android/uapi",
        "-Xclang", "-fdump-record-layouts-complete", "-fsyntax-only", "-x", "c++", "-",
    ]
    if abi == "arm":
        command[3:3] = ["-march=armv7-a"]
    probe = r'''
#include "mali_gralloc_buffer.h"
static_assert(sizeof(uint32_t) == 4);
static_assert(sizeof(uint64_t) == 8);
static_assert(sizeof(native_handle) == 12);
static_assert(sizeof(plane_info_t) == 16);
static_assert(sizeof(private_handle_t) == 232);
static_assert(alignof(private_handle_t) == 8);
static_assert(private_handle_t::sNumFds == 2);
static_assert(private_handle_t::sMagic == 0x3141592);
static_assert(NUM_INTS_IN_PRIVATE_HANDLE == 53);
'''
    expected_off_t = 8 if abi == "arm64" else 4
    probe += f"static_assert(sizeof(off_t) == {expected_off_t});\n"
    result = subprocess.run(
        command, cwd=source, input=probe, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False,
    )
    if result.returncode:
        raise RuntimeError(f"{abi} layout compile failed:\n{result.stdout}")
    private_raw, private_offsets, private_size, private_align = extract_layout(
        result.stdout, "private_handle_t"
    )
    plane_raw, plane_offsets, plane_size, plane_align = extract_layout(result.stdout, "plane_info")
    return {
        "target": target,
        "pointer_size": 8 if abi == "arm64" else 4,
        "off_t_size": expected_off_t,
        "native_handle_size": 12,
        "private_handle": {
            "size": private_size,
            "alignment": private_align,
            "numFds": 2,
            "numInts": 53,
            "magic_hex": "0x03141592",
            "field_offsets": private_offsets,
            "compiler_layout": private_raw,
        },
        "plane_info": {
            "size": plane_size,
            "alignment": plane_align,
            "field_offsets": plane_offsets,
            "compiler_layout": plane_raw,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("/work/src/ubox10-a16-ceiling"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    header = args.source / "hardware/aw/gpu/mali-bifrost/gralloc/src/mali_gralloc_buffer.h"
    if not header.is_file():
        raise SystemExit(f"missing gralloc handle header: {header}")

    arm64 = compile_layout(args.source, "arm64")
    arm = compile_layout(args.source, "arm")
    comparable = ("private_handle", "plane_info")
    for key in comparable:
        for field in ("size", "alignment", "field_offsets", "compiler_layout"):
            if arm64[key][field] != arm[key][field]:
                raise SystemExit(f"CROSS-BITNESS HANDLE LAYOUT FAIL: {key}.{field} differs")
    report = {
        "schema_version": 1,
        "candidate": "a16-prototype-b-r1",
        "status": "CROSS-BITNESS HANDLE LAYOUT OFFLINE PASS",
        "source_header": str(header),
        "source_header_sha256": sha256(header),
        "fixed_width_contract": {"uint32_t": 4, "uint64_t": 8},
        "arm64": arm64,
        "arm32": arm,
        "conclusion": (
            "The compiler-derived serialized native_handle payload, every transported "
            "field offset, size, alignment, numFds, numInts, and magic are identical. "
            "Pointer and off_t unions remain 8-byte slots in both ABIs. Exact-board "
            "runtime import remains a physical B1 gate."
        ),
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print("CROSS-BITNESS HANDLE LAYOUT OFFLINE PASS")
    print(f"header_sha256={report['source_header_sha256']}")
    print("private_handle_t=size:232 align:8 numFds:2 numInts:53 magic:0x03141592")
    print("plane_info_t=size:16 align:4")
    return 0


if __name__ == "__main__":
    sys.exit(main())
