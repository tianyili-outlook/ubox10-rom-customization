#!/usr/bin/env python3
"""Focused regression tests for M8A r4 candidate media_data integration."""

import hashlib
import struct
import sys
import unittest
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from pack_image_preserving import parse_image, word_checksum_path
from sunxi_image_tool import parse_main_header, parse_file_headers, cmd_verify


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


class TestM8AR4MediaData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r3_dir = REPO / "out" / "candidates" / "m8a-initial-atv-r3"
        cls.r3_img = cls.r3_dir / "x12-m8a-initial-atv-r3.img"
        cls.r3_meta_img = cls.r3_dir / "metadata.img"

        cls.r4_dir = REPO / "out" / "candidates" / "m8a-initial-atv-r4"
        cls.r4_img = cls.r4_dir / "x12-m8a-initial-atv-r4.img"
        cls.r4_media_img = cls.r4_dir / "media_data.img"
        cls.r4_meta_img = cls.r4_dir / "metadata.img"

    def test_01_r4_candidate_artifacts_exist(self):
        self.assertTrue(self.r3_img.is_file(), f"r3 image missing: {self.r3_img}")
        self.assertEqual(self.r3_img.stat().st_size, 980171776)
        self.assertEqual(sha256_file(self.r3_img), "B8130EE221AC3B020FC972CA04531064F26E9068EDCE20D3BBACACBF83F16234")

        self.assertTrue(self.r4_img.is_file(), f"r4 image missing: {self.r4_img}")
        self.assertEqual(self.r4_img.stat().st_size, 996952064)

        self.assertTrue(self.r4_media_img.is_file(), f"r4 media_data.img missing: {self.r4_media_img}")
        self.assertEqual(self.r4_media_img.stat().st_size, 16777216)

        self.assertTrue(self.r4_meta_img.is_file(), f"r4 metadata.img missing: {self.r4_meta_img}")
        self.assertEqual(self.r4_meta_img.stat().st_size, 16777216)
        self.assertEqual(self.r4_meta_img.read_bytes(), self.r3_meta_img.read_bytes())

    def test_02_dlinfo_structure_count_crc_and_descriptors(self):
        with self.r3_img.open("rb") as f3, self.r4_img.open("rb") as f4:
            hdr3 = parse_main_header(f3)
            hdr4 = parse_main_header(f4)
            files3 = parse_file_headers(f3, hdr3["num_files"])
            files4 = parse_file_headers(f4, hdr4["num_files"])

            dl3_hdr = [e for e in files3 if e["filename"] == "dlinfo.fex"][0]
            dl4_hdr = [e for e in files4 if e["filename"] == "dlinfo.fex"][0]

            f3.seek(dl3_hdr["offset"])
            dl3_bytes = f3.read(dl3_hdr["orig_len"])
            f4.seek(dl4_hdr["offset"])
            dl4_bytes = f4.read(dl4_hdr["orig_len"])

        # r3 dlinfo count = 12, CRC valid
        r3_count = struct.unpack_from("<I", dl3_bytes, 0x10)[0]
        self.assertEqual(r3_count, 12)
        r3_stored_crc = struct.unpack_from("<I", dl3_bytes, 0)[0]
        self.assertEqual(r3_stored_crc, zlib.crc32(dl3_bytes[4:]))

        # r4 dlinfo count = 13, CRC valid
        r4_count = struct.unpack_from("<I", dl4_bytes, 0x10)[0]
        self.assertEqual(r4_count, 13)
        r4_stored_crc = struct.unpack_from("<I", dl4_bytes, 0)[0]
        r4_calc_crc = zlib.crc32(dl4_bytes[4:])
        self.assertEqual(r4_stored_crc, r4_calc_crc)

        # parse descriptors in r4 dlinfo
        descriptors = []
        for i in range(r4_count):
            e_bytes = dl4_bytes[32 + i * 72 : 32 + (i + 1) * 72]
            name = e_bytes[:20].decode("ascii", errors="ignore").rstrip("\x00")
            start_sec, high32, sec_cnt = struct.unpack_from("<3I", e_bytes, 20)
            fn1 = e_bytes[32:48].decode("ascii", errors="ignore").rstrip("\x00")
            fn2 = e_bytes[48:64].decode("ascii", errors="ignore").rstrip("\x00")
            tail = struct.unpack_from("<2I", e_bytes, 64)
            descriptors.append({
                "name": name,
                "start_sec": start_sec,
                "sec_cnt": sec_cnt,
                "fn1": fn1,
                "fn2": fn2,
                "tail": tail
            })

        # Descriptors must be sorted by start_sec
        start_secs = [d["start_sec"] for d in descriptors]
        self.assertEqual(start_secs, sorted(start_secs))

        # 13th descriptor (last sorted descriptor) is media_data
        media_desc = [d for d in descriptors if d["name"] == "media_data"][0]
        self.assertEqual(media_desc["start_sec"], 13280256)
        self.assertEqual(media_desc["sec_cnt"], 32768)
        self.assertEqual(media_desc["fn1"], "MEDIA_DATA_FEX00")
        self.assertEqual(media_desc["fn2"], "VMEDIA_DATA_FEX0")
        self.assertEqual(media_desc["tail"], (0, 1))

        # All 12 descriptors prior to media_data in r4 match r3 dlinfo
        r3_descriptors = []
        for i in range(r3_count):
            e_bytes = dl3_bytes[32 + i * 72 : 32 + (i + 1) * 72]
            name = e_bytes[:20].decode("ascii", errors="ignore").rstrip("\x00")
            start_sec, high32, sec_cnt = struct.unpack_from("<3I", e_bytes, 20)
            fn1 = e_bytes[32:48].decode("ascii", errors="ignore").rstrip("\x00")
            fn2 = e_bytes[48:64].decode("ascii", errors="ignore").rstrip("\x00")
            tail = struct.unpack_from("<2I", e_bytes, 64)
            r3_descriptors.append({
                "name": name, "start_sec": start_sec, "sec_cnt": sec_cnt,
                "fn1": fn1, "fn2": fn2, "tail": tail
            })

        r4_non_media = [d for d in descriptors if d["name"] != "media_data"]
        self.assertEqual(r3_descriptors, r4_non_media)

    def test_03_vfat_signature_and_embedded_media_data(self):
        # 16 MiB VFAT signature check on media_data.img
        data = self.r4_media_img.read_bytes()
        self.assertEqual(len(data), 16777216)
        # Boot sector signature 0xAA55 at offset 510
        self.assertEqual(data[510:512], b"\x55\xaa")
        # System ID / OEM Name starting at offset 3 contains FAT signature
        self.assertTrue(b"FAT" in data[:512] or b"mkfs" in data[:512])

        # Read embedded media_data.fex and Vmedia_data.fex from r4 image
        with self.r4_img.open("rb") as f4:
            hdr4 = parse_main_header(f4)
            files4 = parse_file_headers(f4, hdr4["num_files"])

            media_hdr = [e for e in files4 if e["filename"] == "media_data.fex"][0]
            vmedia_hdr = [e for e in files4 if e["filename"] == "Vmedia_data.fex"][0]

            f4.seek(media_hdr["offset"])
            embedded_media_bytes = f4.read(media_hdr["orig_len"])

            f4.seek(vmedia_hdr["offset"])
            embedded_vmedia_bytes = f4.read(vmedia_hdr["orig_len"])

        self.assertEqual(embedded_media_bytes, data)

        # Vmedia_data companion contains 4-byte word checksum of media_data
        expected_chksum = word_checksum_path(self.r4_media_img)
        stored_chksum = struct.unpack("<I", embedded_vmedia_bytes[:4])[0]
        self.assertEqual(stored_chksum, expected_chksum)

    def test_04_r3_preservation_and_payload_invariants(self):
        with self.r3_img.open("rb") as f3, self.r4_img.open("rb") as f4:
            hdr3 = parse_main_header(f3)
            hdr4 = parse_main_header(f4)
            files3 = parse_file_headers(f3, hdr3["num_files"])
            files4 = parse_file_headers(f4, hdr4["num_files"])

            self.assertEqual(hdr3["num_files"], 48)
            self.assertEqual(hdr4["num_files"], 50)

            # 47 non-dlinfo r3 entries remain byte-identical in r4
            r3_map = {e["filename"]: e for e in files3}
            r4_map = {e["filename"]: e for e in files4}

            non_dlinfo_count = 0
            for name, e3 in r3_map.items():
                if name == "dlinfo.fex":
                    continue
                self.assertIn(name, r4_map, f"missing entry {name} in r4")
                e4 = r4_map[name]
                self.assertEqual(e3["orig_len"], e4["orig_len"])
                self.assertEqual(e3["stored_len"], e4["stored_len"])

                f3.seek(e3["offset"])
                b3 = f3.read(e3["stored_len"])
                f4.seek(e4["offset"])
                b4 = f4.read(e4["stored_len"])
                self.assertEqual(b3, b4, f"payload changed for {name}")
                non_dlinfo_count += 1

            self.assertEqual(non_dlinfo_count, 47)

            # Metadata/Vmetadata entries remain byte-identical
            f3.seek(r3_map["metadata.fex"]["offset"])
            meta_b3 = f3.read(r3_map["metadata.fex"]["stored_len"])
            f4.seek(r4_map["metadata.fex"]["offset"])
            meta_b4 = f4.read(r4_map["metadata.fex"]["stored_len"])
            self.assertEqual(meta_b3, meta_b4)

            # Only dlinfo plus media_data/Vmedia_data are new/changed entries
            new_or_changed = set(r4_map.keys()) - (set(r3_map.keys()) - {"dlinfo.fex"})
            self.assertEqual(new_or_changed, {"dlinfo.fex", "media_data.fex", "Vmedia_data.fex"})

    def test_05_imagewty_companion_verification(self):
        class Args:
            image = str(self.r4_img)

        cmd_verify(Args())


if __name__ == "__main__":
    unittest.main()
