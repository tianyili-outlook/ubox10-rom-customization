"""Regression tests for memory-safe IMAGEWTY checksum calculation."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "tools" / "pack_image.py"
SPEC = importlib.util.spec_from_file_location("imagewty_packer_for_tests", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
packer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(packer)


def reference_checksum(data: bytes) -> int:
    padded = data + b"\0" * (-len(data) % 4)
    return sum(
        int.from_bytes(padded[offset : offset + 4], "little")
        for offset in range(0, len(padded), 4)
    ) & 0xFFFFFFFF


class ImagewtyChecksumTests(unittest.TestCase):
    def test_checksum_matches_reference_for_partial_words(self) -> None:
        for data in (b"", b"\x01", b"\x01\x02", b"\x01\x02\x03", b"\x01\x02\x03\x04"):
            with self.subTest(length=len(data)):
                self.assertEqual(reference_checksum(data), packer.calculate_checksum(data))

    def test_checksum_matches_reference_across_chunks(self) -> None:
        original_chunk_size = packer.CHECKSUM_CHUNK_BYTES
        packer.CHECKSUM_CHUNK_BYTES = 16
        try:
            data = bytes(range(67))
            self.assertEqual(reference_checksum(data), packer.calculate_checksum(data))
        finally:
            packer.CHECKSUM_CHUNK_BYTES = original_chunk_size


if __name__ == "__main__":
    unittest.main()
