#!/usr/bin/env python3
"""Focused regression tests for M8A r2 metadata repair, dlinfo, and package addition."""

import json
import struct
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "scripts"))

from pack_image_preserving import parse_image, pack
from sunxi_image_tool import parse_main_header, parse_file_headers, cmd_verify, calculate_checksum


class TestM8AR2Metadata(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r1_img = REPO / "out" / "candidates" / "m8a-initial-atv-r1" / "x12-m8a-initial-atv-r1.img"
        cls.r2_dir = REPO / "out" / "candidates" / "m8a-initial-atv-r2"
        cls.r2_img = cls.r2_dir / "x12-m8a-initial-atv-r2.img"
        cls.r2_meta_img = cls.r2_dir / "metadata.img"
        missing = [path for path in (cls.r1_img, cls.r2_img, cls.r2_meta_img) if not path.is_file()]
        if missing:
            raise unittest.SkipTest("local r1/r2 artifacts are not present")

    def test_01_r2_candidate_and_metadata_artifact_exist(self):
        self.assertGreater(self.r2_img.stat().st_size, 963391488)
        self.assertEqual(self.r2_meta_img.stat().st_size, 16777216)

    def test_02_sector_math_and_dlinfo_parsing(self):
        # Assert sector offset arithmetic
        dlinfo_sector = 13206528
        card_boot_offset = 40960
        gpt_lba = 13247488
        self.assertEqual(dlinfo_sector + card_boot_offset, gpt_lba)

        with self.r1_img.open("rb") as f:
            main_hdr = parse_main_header(f)
            files = parse_file_headers(f, main_hdr["num_files"])
            dlinfo_file = [e for e in files if e["filename"] == "dlinfo.fex"][0]
            f.seek(dlinfo_file["offset"])
            dlinfo_r1 = f.read(dlinfo_file["orig_len"])

        r1_count = struct.unpack_from("<I", dlinfo_r1, 0x10)[0]
        self.assertEqual(r1_count, 11)

        # First 4 bytes is preserved magic/header word 0x80B15BEB
        r1_magic = struct.unpack_from("<I", dlinfo_r1, 0x0)[0]
        self.assertEqual(r1_magic, 0x80B15BEB)

        with self.r2_img.open("rb") as f:
            main_hdr_r2 = parse_main_header(f)
            files_r2 = parse_file_headers(f, main_hdr_r2["num_files"])
            dlinfo_file_r2 = [e for e in files_r2 if e["filename"] == "dlinfo.fex"][0]
            f.seek(dlinfo_file_r2["offset"])
            dlinfo_r2 = f.read(dlinfo_file_r2["orig_len"])

        r2_count = struct.unpack_from("<I", dlinfo_r2, 0x10)[0]
        self.assertEqual(r2_count, 12)
        self.assertEqual(struct.unpack_from("<I", dlinfo_r2, 0x0)[0], 0x80B15BEB)

        entries = []
        for i in range(12):
            e_bytes = dlinfo_r2[32 + i * 72 : 32 + (i + 1) * 72]
            name = e_bytes[:20].rstrip(b"\0").decode("ascii")
            start_sec, _, sec_cnt = struct.unpack_from("<3I", e_bytes, 20)
            fn1 = e_bytes[32:48].rstrip(b"\0").decode("ascii")
            fn2 = e_bytes[48:64].rstrip(b"\0").decode("ascii")
            entries.append((name, start_sec, sec_cnt, fn1, fn2))

        meta_entry = [e for e in entries if e[0] == "metadata"]
        self.assertEqual(len(meta_entry), 1)
        _, start_sec, sec_cnt, fn1, fn2 = meta_entry[0]
        self.assertEqual(start_sec, dlinfo_sector)
        self.assertEqual(sec_cnt, 32768)
        self.assertEqual(fn1, "METADATA_FEX0000")
        self.assertEqual(fn2, "VMETADATA_FEX000")

    def test_03_all_r1_entries_and_payload_preservation(self):
        with self.r1_img.open("rb") as f1, self.r2_img.open("rb") as f2:
            hdr1 = parse_main_header(f1)
            hdr2 = parse_main_header(f2)
            files1 = parse_file_headers(f1, hdr1["num_files"])
            files2 = parse_file_headers(f2, hdr2["num_files"])

            self.assertEqual(hdr1["num_files"], 46)
            self.assertEqual(hdr2["num_files"], 48)

            r1_map = {f["filename"]: f for f in files1}
            r2_map = {f["filename"]: f for f in files2}

            # All 46 r1 entries must exist in r2
            for name, f1_entry in r1_map.items():
                self.assertIn(name, r2_map, f"r1 entry missing from r2: {name}")

            # misc and sysrecovery must exist
            self.assertIn("misc.fex", r2_map)
            self.assertIn("sysrecovery.fex", r2_map)
            self.assertIn("metadata.fex", r2_map)
            self.assertIn("Vmetadata.fex", r2_map)

            # Check exact byte preservation of all 45 preserved payloads
            preserved_count = 0
            for name, f1_entry in r1_map.items():
                if name == "dlinfo.fex":
                    continue # Replaced
                f2_entry = r2_map[name]
                self.assertEqual(f1_entry["orig_len"], f2_entry["orig_len"])
                self.assertEqual(f1_entry["stored_len"], f2_entry["stored_len"])

                f1.seek(f1_entry["offset"])
                b1 = f1.read(f1_entry["stored_len"])
                f2.seek(f2_entry["offset"])
                b2 = f2.read(f2_entry["stored_len"])

                self.assertEqual(b1, b2, f"preserved payload bytes changed for {name}")
                preserved_count += 1

            self.assertEqual(preserved_count, 45)

            # Check Vmetadata companion checksum
            meta_entry = r2_map["metadata.fex"]
            vmeta_entry = r2_map["Vmetadata.fex"]

            f2.seek(vmeta_entry["offset"])
            v_data = f2.read(4)
            expected_v_chk = struct.unpack("<I", v_data)[0]

            actual_v_chk = calculate_checksum(f2, meta_entry["offset"], meta_entry["stored_len"])
            self.assertEqual(expected_v_chk, actual_v_chk)

        # Run sunxi_image_tool verify programmatic check
        class Args:
            image = str(self.r2_img)

        cmd_verify(Args())


if __name__ == "__main__":
    unittest.main()
