"""Focused tests for the IMAGEWTY preservation packer."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("preserving_packer", REPO / "tools" / "pack_image_preserving.py")
assert SPEC and SPEC.loader
packer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(packer)


def make_image(path: Path) -> None:
    entries = [("foo.fex", b"abcde"), ("Vfoo.fex", struct.pack("<I", 0x12345678) + b"\0" * 12), ("keep.fex", b"unchanged")]
    start = 1024 + len(entries) * 1024
    headers = []
    payloads = []
    for index, (name, data) in enumerate(entries):
        start = packer.align(start, 1024)
        stored = packer.align(len(data), 16)
        header = bytearray(1024)
        struct.pack_into("<II", header, 0, len(name), 1024)
        header[36:36 + len(name)] = name.encode()
        struct.pack_into("<QQQ", header, 292, stored, len(data), start)
        headers.append(header)
        payloads.append((start, data + b"\0" * (stored - len(data))))
        start += stored
    image_size = packer.align(start, 1024)
    prefix = bytearray((index * 37 + 11) & 0xFF for index in range(1024))
    prefix[:8] = b"IMAGEWTY"
    struct.pack_into("<II", prefix, 8, 0x300, 96)
    struct.pack_into("<I", prefix, 24, image_size)
    struct.pack_into("<I", prefix, 60, len(entries))
    with path.open("wb") as f:
        f.write(prefix)
        for header in headers:
            f.write(header)
        for offset, payload in payloads:
            f.write(b"\0" * (offset - f.tell()))
            f.write(payload)
        f.write(b"\0" * (image_size - f.tell()))


class PackerTests(unittest.TestCase):
    def test_no_replacement_is_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source, output = Path(td) / "source.img", Path(td) / "output.img"
            make_image(source)
            audit = packer.pack(source, output, {})
            self.assertTrue(audit["byte_identical"])
            self.assertEqual(source.read_bytes(), output.read_bytes())

    def test_primary_and_v_companion_change_only_as_required(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source, output, replacement = root / "source.img", root / "output.img", root / "new.bin"
            make_image(source)
            replacement.write_bytes(b"new-primary-payload")
            packer.pack(source, output, {"foo.fex": replacement})
            source_prefix, output_prefix = source.read_bytes()[:1024], output.read_bytes()[:1024]
            differing = {index for index, (old, new) in enumerate(zip(source_prefix, output_prefix)) if old != new}
            self.assertTrue(differing.issubset(set(range(24, 28))))
            self.assertEqual(source_prefix[96:], output_prefix[96:])
            _, old = packer.parse_image(source)
            _, new = packer.parse_image(output)
            old_by_name = {e["filename"]: e for e in old}
            new_by_name = {e["filename"]: e for e in new}
            with output.open("rb") as f:
                f.seek(new_by_name["keep.fex"]["offset"])
                self.assertEqual(f.read(new_by_name["keep.fex"]["stored_len"]), b"unchanged" + b"\0" * 7)
                f.seek(new_by_name["Vfoo.fex"]["offset"])
                expected = struct.pack("<I", packer.word_checksum_path(replacement)) + b"\0" * 12
                self.assertEqual(f.read(16), expected)
            self.assertEqual(new_by_name["Vfoo.fex"]["orig_len"], 4)
            self.assertEqual(new_by_name["Vfoo.fex"]["stored_len"], 16)
            # Non-length header fields are preserved exactly.
            self.assertEqual(old_by_name["keep.fex"]["header"][:292], new_by_name["keep.fex"]["header"][:292])


if __name__ == "__main__":
    unittest.main()
