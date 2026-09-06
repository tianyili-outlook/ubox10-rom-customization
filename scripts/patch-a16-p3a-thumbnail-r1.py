#!/usr/bin/env python3
"""Exact retained OMX ELF: choose linear internal storage only for 4K CPU I420.

Adds an isolated RX trampoline; original allocated sections keep their VAs and
bytes except the one branch replacing the AFBC config store. GNU Build ID is
retained provenance, not the patched identity. No candidate/device operations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile

INPUT_SIZE = 83780
INPUT_SHA256 = "5fe74a28eb9e083959fdac9cfde870faa2af4447dadb7776c1e7f4cfc6d1ee8b"
HOOK_VA = 0xd068
HOOK_OFFSET = 0xc068
HOOK_ORIGINAL = bytes.fromhex("c5 f8 c0 60")
INSERT_OFFSET = 0x12f00
STUB_VA = 0x13f00
PAGE = 0x1000
HOOK_PATCHED = bytes.fromhex("06 f0 4a bf")
STUB_SHA256 = "ef8c98452315150861e2e9de6bb99e6347fca3464699c527c26e7664bcb9dc81"
OUTPUT_SHA256 = "4916c492dd6b7f1ca8948d2b14394baeeacd1e01cc8c0a7af616975d19551b0f"
DEFAULT_TOOLS = Path("/work/src/ubox10-a16-ceiling/prebuilts/clang/host/linux-x86/clang-r547379/bin")

# Exact setters/consumers: native +58b0, secure +58a4, zero-copy +58bc;
# __anUpdateColorFormat writes both output port color fields +ac/+d0.
# Profile/bitdepth is not established pre-InitializeVideoDecoder: this guard
# expresses a linear CPU output contract, NOT Main10/HDR support authorization.
ASSEMBLY = r"""
.syntax unified
.arch armv7-a
.thumb
.section .hook,"ax",%progbits
b.w thumbnail_linear
.section .thumbnail,"ax",%progbits
.thumb_func
thumbnail_linear:
    str.w r6, [r5, #0xc0]
    push {r2, r3}
    mrs r2, apsr
    push {r2, r3}
    cmp.w r0, #0x116
    bne finished
    ldr r2, [r4, #0xc]
    cmp.w r2, #3840
    bne finished
    ldr r2, [r4, #0x10]
    cmp.w r2, #2160
    bne finished
    movw r3, #0x58a4
    add r3, r4
    ldr r2, [r3]
    cbnz r2, finished
    ldr r2, [r3, #0xc]
    cbnz r2, finished
    ldr r2, [r3, #0x18]
    cbnz r2, finished
    ldr r3, [r3, #0x28]
    cbz r3, finished
    ldr.w r2, [r3, #0xac]
    cmp r2, #0x13
    bne finished
    ldr.w r2, [r3, #0xd0]
    cmp r2, #0x13
    bne finished
    movs r2, #0
    str.w r2, [r5, #0xc0]
finished:
    pop {r2, r3}
    msr apsr_nzcvq, r2
    pop {r2, r3}
    b.w resume_original
"""


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sections(data: bytes) -> tuple[list[list[int]], int]:
    offset = struct.unpack_from("<I", data, 32)[0]
    count = struct.unpack_from("<H", data, 48)[0]
    return [list(struct.unpack_from("<10I", data, offset + i * 40)) for i in range(count)], offset


def assemble(tools: Path) -> tuple[bytes, bytes, str]:
    """Assemble/link fixed-address Thumb code; no hand-derived branch encoding."""
    with tempfile.TemporaryDirectory(prefix="ubox-thumbnail-assemble-") as root:
        work = Path(root)
        (work / "patch.s").write_text(ASSEMBLY)
        (work / "link.ld").write_text(
            "resume_original = 0xd06c; SECTIONS { . = 0xd068; .hook : { *(.hook) } "
            ". = 0x13f00; .thumbnail : { *(.thumbnail) } "
            "/DISCARD/ : { *(.ARM.attributes) *(.comment) } }")
        subprocess.run([str(tools / "clang"), "--target=armv7a-linux-androideabi31",
                        "-c", str(work / "patch.s"), "-o", str(work / "patch.o")], check=True)
        subprocess.run([str(tools / "ld.lld"), "-e", "0xd069", "-T", str(work / "link.ld"),
                        str(work / "patch.o"), "-o", str(work / "patch.elf")], check=True)
        data = (work / "patch.elf").read_bytes()
        sh, _ = sections(data)
        names = sh[struct.unpack_from("<H", data, 50)[0]]
        strings = data[names[4]:names[4] + names[5]]
        payload = {}
        for entry in sh:
            name = strings[entry[0]:].split(b"\0", 1)[0].decode()
            if name in (".hook", ".thumbnail"):
                payload[name] = data[entry[4]:entry[4] + entry[5]]
        dis = subprocess.check_output([str(tools / "llvm-objdump"), "-d", "--triple=thumbv7a-linux-android",
                                       str(work / "patch.elf")], text=True)
        if len(payload[".hook"]) != 4 or len(payload[".thumbnail"]) > PAGE:
            raise ValueError("unexpected assembled patch size")
        return payload[".hook"], payload[".thumbnail"], dis


def patch_bytes(original: bytes, hook: bytes, stub: bytes) -> tuple[bytes, dict]:
    if len(original) != INPUT_SIZE or sha(original) != INPUT_SHA256:
        raise ValueError("exact source size/SHA mismatch")
    if original[HOOK_OFFSET:HOOK_OFFSET + 4] != HOOK_ORIGINAL:
        raise ValueError("original AFBC instruction mismatch")
    if len(hook) != 4 or not 0 < len(stub) <= PAGE:
        raise ValueError("invalid assembled code sizes")
    if hook != HOOK_PATCHED or sha(stub) != STUB_SHA256:
        raise ValueError("assembled instruction identity mismatch")
    sh, old_shoff = sections(original)
    phoff = struct.unpack_from("<I", original, 28)[0]
    phnum = struct.unpack_from("<H", original, 44)[0]
    if (phoff, phnum, len(sh)) != (52, 10, 25):
        raise ValueError("unexpected ELF tables")
    patched = bytearray(original[:INSERT_OFFSET] + stub + bytes(PAGE - len(stub)) + original[INSERT_OFFSET:])
    patched[HOOK_OFFSET:HOOK_OFFSET + 4] = hook
    for i in range(phnum):
        p = list(struct.unpack_from("<8I", original, phoff + 32 * i))
        if i == 2:
            if p[:7] != [1, 0x66c0, 0x76c0, 0x76c0, 0xc840, 0xc840, 5]:
                raise ValueError("RX segment changed")
            p[4] += PAGE
            p[5] += PAGE
        elif p[1] >= INSERT_OFFSET:
            p[1] += PAGE
        struct.pack_into("<8I", patched, phoff + 32 * i, *p)
    for entry in sh:
        if entry[4] >= INSERT_OFFSET:
            entry[4] += PAGE
    shstridx = struct.unpack_from("<H", original, 50)[0]
    old_strings = sh[shstridx]
    strings = bytes(patched[old_strings[4]:old_strings[4] + old_strings[5]])
    nameoff = len(strings)
    strings += b".ubox_thumbnail_linear\0"
    sh[shstridx][4] = len(patched)
    sh[shstridx][5] = len(strings)
    patched += strings
    patched += bytes((-len(patched)) % 4)
    sh.append([nameoff, 1, 6, STUB_VA, INSERT_OFFSET, len(stub), 0, 0, 4, 0])
    new_shoff = len(patched)
    for entry in sh:
        patched += struct.pack("<10I", *entry)
    struct.pack_into("<I", patched, 32, new_shoff)
    struct.pack_into("<H", patched, 48, len(sh))
    result = bytes(patched)
    if sha(result) != OUTPUT_SHA256:
        raise ValueError("deterministic output identity mismatch")
    # Verify every original allocated section content and VA (only hook differs).
    original_sh, _ = sections(original)
    for i, old in enumerate(original_sh):
        if not old[2] & 2:
            continue
        new = sh[i]
        if (old[3], old[5], old[2]) != (new[3], new[5], new[2]):
            raise AssertionError("original allocated section layout changed")
        expected = bytearray(original[old[4]:old[4] + old[5]])
        if old[4] <= HOOK_OFFSET < old[4] + old[5]:
            pos = HOOK_OFFSET - old[4]
            expected[pos:pos + 4] = hook
        if result[new[4]:new[4] + new[5]] != expected:
            raise AssertionError("unrelated original section bytes changed")
    return result, {"input_sha256": INPUT_SHA256, "output_sha256": sha(result),
                    "input_size": len(original), "output_size": len(result),
                    "hook_file_offset": HOOK_OFFSET, "hook_va": HOOK_VA,
                    "original_hook": HOOK_ORIGINAL.hex(), "replacement_hook": hook.hex(),
                    "stub_va": STUB_VA, "stub_file_offset": INSERT_OFFSET,
                    "stub_size": len(stub), "stub_sha256": sha(stub),
                    "inserted_page_bytes": PAGE, "old_section_table_offset": old_shoff,
                    "new_section_table_offset": new_shoff,
                    "original_allocated_sections_preserved_except_hook": True,
                    "build_id_note_retained_provenance_only": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--tools", default=DEFAULT_TOOLS, type=Path)
    parser.add_argument("--proof-dir", type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.input.resolve() == args.output.resolve():
        raise SystemExit("refuse overwriting any existing ELF")
    hook, stub, disassembly = assemble(args.tools)
    result, proof = patch_bytes(args.input.read_bytes(), hook, stub)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as stream:
        stream.write(result)
    args.output.chmod(args.input.stat().st_mode & 0o777)
    if args.output.read_bytes() != result:
        raise SystemExit("output verification failed")
    if args.proof_dir:
        args.proof_dir.mkdir(parents=True, exist_ok=True)
        (args.proof_dir / "patch-disassembly.txt").write_text(disassembly)
        (args.proof_dir / "patch-proof.json").write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps(proof, indent=2))


if __name__ == "__main__":
    main()
