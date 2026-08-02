#!/usr/bin/env python3
"""Focused regression tests for M8A r3 candidate dlinfo CRC repair."""

import struct
import sys
import unittest
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from pack_image_preserving import parse_image
from sunxi_image_tool import parse_main_header, parse_file_headers, cmd_verify


class TestM8AR3DlinfoCRC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r2_img = REPO / "out" / "candidates" / "m8a-initial-atv-r2" / "x12-m8a-initial-atv-r2.img"
        cls.r3_dir = REPO / "out" / "candidates" / "m8a-initial-atv-r3"
        cls.r3_img = cls.r3_dir / "x12-m8a-initial-atv-r3.img"
        cls.r3_meta_img = cls.r3_dir / "metadata.img"

    def test_01_r3_candidate_artifacts_exist(self):
        self.assertTrue(self.r2_img.is_file(), f"r2 image missing: {self.r2_img}")
        self.assertTrue(self.r3_img.is_file(), f"r3 image missing: {self.r3_img}")
        self.assertEqual(self.r3_img.stat().st_size, 980171776)
        self.assertEqual(self.r3_img.stat().st_size, self.r2_img.stat().st_size)
        self.assertTrue(self.r3_meta_img.is_file(), f"r3 metadata.img missing: {self.r3_meta_img}")
        self.assertEqual(self.r3_meta_img.stat().st_size, 16777216)

    def test_02_dlinfo_crc_assertions(self):
        with self.r2_img.open("rb") as f2, self.r3_img.open("rb") as f3:
            hdr2 = parse_main_header(f2)
            hdr3 = parse_main_header(f3)
            files2 = parse_file_headers(f2, hdr2["num_files"])
            files3 = parse_file_headers(f3, hdr3["num_files"])

            dl2_hdr = [e for e in files2 if e["filename"] == "dlinfo.fex"][0]
            dl3_hdr = [e for e in files3 if e["filename"] == "dlinfo.fex"][0]

            f2.seek(dl2_hdr["offset"])
            dl2_bytes = f2.read(dl2_hdr["orig_len"])
            f3.seek(dl3_hdr["offset"])
            dl3_bytes = f3.read(dl3_hdr["orig_len"])

        # r2 stored CRC is stale and computed CRC is 0xd32ef288
        r2_stored_crc = struct.unpack_from("<I", dl2_bytes, 0)[0]
        r2_computed_crc = zlib.crc32(dl2_bytes[4:])
        self.assertEqual(r2_stored_crc, 0x80B15BEB)
        self.assertEqual(r2_computed_crc, 0xD32EF288)

        # r3 stored CRC equals zlib.crc32(r3_dlinfo[4:])
        r3_stored_crc = struct.unpack_from("<I", dl3_bytes, 0)[0]
        r3_computed_crc = zlib.crc32(dl3_bytes[4:])
        self.assertEqual(r3_stored_crc, r3_computed_crc)
        self.assertEqual(r3_stored_crc, 0xD32EF288)

        # r3 dlinfo bytes after offset 4 are identical to r2
        self.assertEqual(dl2_bytes[4:], dl3_bytes[4:])

    def test_03_entries_and_payload_preservation(self):
        with self.r2_img.open("rb") as f2, self.r3_img.open("rb") as f3:
            hdr2 = parse_main_header(f2)
            hdr3 = parse_main_header(f3)
            files2 = parse_file_headers(f2, hdr2["num_files"])
            files3 = parse_file_headers(f3, hdr3["num_files"])

            # r3 and r2 have the same 48 entries, offsets and lengths
            self.assertEqual(hdr2["num_files"], 48)
            self.assertEqual(hdr3["num_files"], 48)

            for i in range(48):
                e2 = files2[i]
                e3 = files3[i]
                self.assertEqual(e2["filename"], e3["filename"])
                self.assertEqual(e2["orig_len"], e3["orig_len"])
                self.assertEqual(e2["stored_len"], e3["stored_len"])
                self.assertEqual(e2["offset"], e3["offset"])

            # all 47 non-dlinfo stored payloads are byte-identical
            non_dlinfo_count = 0
            for e2, e3 in zip(files2, files3):
                if e2["filename"] == "dlinfo.fex":
                    continue
                f2.seek(e2["offset"])
                b2 = f2.read(e2["stored_len"])
                f3.seek(e3["offset"])
                b3 = f3.read(e3["stored_len"])
                self.assertEqual(b2, b3, f"payload changed for {e2['filename']}")
                non_dlinfo_count += 1

            self.assertEqual(non_dlinfo_count, 47)

    def test_04_four_byte_difference_invariant(self):
        # The entire r3 image differs from r2 only at the dlinfo payload's first four byte positions
        with self.r2_img.open("rb") as f2:
            hdr2 = parse_main_header(f2)
            files2 = parse_file_headers(f2, hdr2["num_files"])
            dl2_hdr = [e for e in files2 if e["filename"] == "dlinfo.fex"][0]
            dl_offset = dl2_hdr["offset"]

        chunk_size = 8 * 1024 * 1024
        differing_offsets = []

        with self.r2_img.open("rb") as f2, self.r3_img.open("rb") as f3:
            curr = 0
            while True:
                b2 = f2.read(chunk_size)
                b3 = f3.read(chunk_size)
                if not b2:
                    break
                if b2 != b3:
                    for i in range(len(b2)):
                        if b2[i] != b3[i]:
                            differing_offsets.append(curr + i)
                curr += len(b2)

        self.assertEqual(differing_offsets, list(range(dl_offset, dl_offset + 4)))

    def test_05_imagewty_companion_verification(self):
        # IMAGEWTY partition companion verification passes
        class Args:
            image = str(self.r3_img)

        cmd_verify(Args())


if __name__ == "__main__":
    unittest.main()
