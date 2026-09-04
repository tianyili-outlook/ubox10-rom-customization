#!/usr/bin/env python3
"""Apply the exact P3-A RC-A operand correction to the retained ARM32 OMX ELF."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


INPUT_SIZE = 83_780
INPUT_SHA256 = "29F500E3089651C41A4C2A88C1F82B99EE389AF7A83101CE929516018D5CEA87"
OUTPUT_SHA256 = "5FE74A28EB9E083959FDAC9CFDE870FAA2AF4447DADB7776C1E7F4CFC6D1EE8B"
PATCH_FILE_OFFSET = 0xD130
PATCH_VIRTUAL_ADDRESS = 0xE130
ORIGINAL_BYTES = bytes.fromhex("d8 f8 00 00")
PATCHED_BYTES = bytes.fromhex("4f ea 0c 00")
ORIGINAL_INSTRUCTION = "ldr.w r0, [r8]"
PATCHED_INSTRUCTION = "mov.w r0, r12"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def patch_bytes(original: bytes) -> tuple[bytes, list[int]]:
    """Return the exact patched payload and its byte-difference offsets."""
    if len(original) != INPUT_SIZE:
        raise ValueError(f"input size mismatch: {len(original)} != {INPUT_SIZE}")
    actual_sha = digest(original)
    if actual_sha != INPUT_SHA256:
        raise ValueError(f"input SHA256 mismatch: {actual_sha} != {INPUT_SHA256}")
    actual = original[PATCH_FILE_OFFSET:PATCH_FILE_OFFSET + len(ORIGINAL_BYTES)]
    if actual != ORIGINAL_BYTES:
        raise ValueError(
            f"original bytes mismatch at 0x{PATCH_FILE_OFFSET:x}: "
            f"{actual.hex(' ')} != {ORIGINAL_BYTES.hex(' ')}"
        )

    candidate = bytearray(original)
    candidate[PATCH_FILE_OFFSET:PATCH_FILE_OFFSET + len(PATCHED_BYTES)] = PATCHED_BYTES
    patched = bytes(candidate)
    if len(patched) != len(original):
        raise AssertionError("patch changed ELF size")
    changed = [index for index, pair in enumerate(zip(original, patched)) if pair[0] != pair[1]]
    allowed = list(range(PATCH_FILE_OFFSET, PATCH_FILE_OFFSET + len(PATCHED_BYTES)))
    if not changed or any(index not in allowed for index in changed):
        raise AssertionError(f"unexpected changed byte offsets: {changed}")
    actual_output_sha = digest(patched)
    if actual_output_sha != OUTPUT_SHA256:
        raise AssertionError(
            f"output SHA256 mismatch: {actual_output_sha} != {OUTPUT_SHA256}"
        )
    return patched, changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="exact original libOmxVdec.so")
    parser.add_argument("--output", required=True, type=Path, help="new patched ELF; must not exist")
    args = parser.parse_args()

    if args.output.exists():
        raise SystemExit(f"refusing to overwrite existing output: {args.output}")
    original = args.input.read_bytes()
    try:
        patched, changed = patch_bytes(original)
    except (AssertionError, ValueError) as error:
        raise SystemExit(f"refusing patch: {error}") from error

    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with args.output.open("xb") as stream:
            stream.write(patched)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(args.output, args.input.stat().st_mode & 0o777)
    except BaseException:
        # A partial output is not a valid artifact and must never be reused.
        args.output.unlink(missing_ok=True)
        raise

    written = args.output.read_bytes()
    if written != patched or digest(written) != OUTPUT_SHA256:
        args.output.unlink(missing_ok=True)
        raise SystemExit("written output failed exact verification and was removed")

    print(json.dumps({
        "input": str(args.input),
        "input_size": len(original),
        "input_sha256": INPUT_SHA256,
        "output": str(args.output),
        "output_size": len(written),
        "output_sha256": OUTPUT_SHA256,
        "patch_file_offset": PATCH_FILE_OFFSET,
        "patch_virtual_address": PATCH_VIRTUAL_ADDRESS,
        "original_bytes": ORIGINAL_BYTES.hex(" "),
        "patched_bytes": PATCHED_BYTES.hex(" "),
        "original_instruction": ORIGINAL_INSTRUCTION,
        "patched_instruction": PATCHED_INSTRUCTION,
        "changed_byte_offsets": changed,
        "changed_byte_count": len(changed),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
