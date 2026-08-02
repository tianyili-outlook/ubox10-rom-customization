#!/usr/bin/env python3
"""Focused checks for the M8A r5 keyless top-level vbmeta replacement."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import unittest

REPO = Path(__file__).resolve().parents[1]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))

from pack_image_preserving import word_checksum_path
from sunxi_image_tool import cmd_verify, parse_file_headers, parse_main_header

CHUNK = 8 * 1024 * 1024


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(CHUNK), b""):
            hasher.update(block)
    return hasher.hexdigest().upper()


def region_digest(stream, offset: int, size: int) -> str:
    hasher = hashlib.sha256()
    stream.seek(offset)
    remaining = size
    while remaining:
        block = stream.read(min(CHUNK, remaining))
        if not block:
            raise EOFError("truncated IMAGEWTY payload")
        hasher.update(block)
        remaining -= len(block)
    return hasher.hexdigest().upper()


class TestM8AR5AvbBypass(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.r4 = REPO / "out" / "candidates" / "m8a-initial-atv-r4" / "x12-m8a-initial-atv-r4.img"
        cls.r5_dir = REPO / "out" / "candidates" / "m8a-initial-atv-r5"
        cls.r5 = cls.r5_dir / "x12-m8a-initial-atv-r5.img"
        cls.vbmeta = cls.r5_dir / "vbmeta.img"
        cls.audit = json.loads((cls.r5_dir / "outer-payload-audit.json").read_text(encoding="utf-8"))

    def test_01_base_and_build_identity(self) -> None:
        self.assertEqual(self.r4.stat().st_size, 996952064)
        self.assertEqual(sha256_file(self.r4), "5AFE57DE82B0A42BD3EFB4618375DB896FB0BD7C3C82FF9BD7E817C374C4AAB5")
        result = json.loads((self.r5_dir / "build-result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["firmware"]["size"], self.r5.stat().st_size)
        self.assertEqual(result["firmware"]["sha256"], sha256_file(self.r5))
        self.assertFalse(result["avb"]["private_key_used"])

    def test_02_keyless_vbmeta_header_and_container_payload(self) -> None:
        self.assertEqual(self.vbmeta.stat().st_size, 4096)
        module_spec = importlib.util.spec_from_file_location("m8a_r5_test_avbtool", TOOLS / "avbtool.py")
        self.assertIsNotNone(module_spec)
        self.assertIsNotNone(module_spec.loader)
        avbtool = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(avbtool)
        header = avbtool.AvbVBMetaHeader(self.vbmeta.read_bytes()[:256])
        self.assertEqual(header.algorithm_type, 0)
        self.assertEqual(header.flags, 2)

        with self.r5.open("rb") as stream:
            main = parse_main_header(stream)
            entries = {item["filename"]: item for item in parse_file_headers(stream, main["num_files"])}
            embedded = entries["vbmeta.fex"]
            stream.seek(embedded["offset"])
            self.assertEqual(stream.read(embedded["orig_len"]), self.vbmeta.read_bytes())
            companion = entries["Vvbmeta.fex"]
            stream.seek(companion["offset"])
            stored = struct.unpack("<I", stream.read(4))[0]
        self.assertEqual(stored, word_checksum_path(self.vbmeta))

    def test_03_only_vbmeta_and_companion_changed(self) -> None:
        actions = {item["filename"]: item["action"] for item in self.audit["payloads"]}
        self.assertEqual(len(actions), 50)
        self.assertEqual(actions["vbmeta.fex"], "replacement")
        self.assertEqual(actions["Vvbmeta.fex"], "companion")
        self.assertEqual(sum(action == "preserved" for action in actions.values()), 48)

        with self.r4.open("rb") as old, self.r5.open("rb") as new:
            old_main = parse_main_header(old)
            new_main = parse_main_header(new)
            old_entries = {item["filename"]: item for item in parse_file_headers(old, old_main["num_files"])}
            new_entries = {item["filename"]: item for item in parse_file_headers(new, new_main["num_files"])}
            self.assertEqual(set(old_entries), set(new_entries))
            for name in sorted(set(old_entries) - {"vbmeta.fex", "Vvbmeta.fex"}):
                old_entry = old_entries[name]
                new_entry = new_entries[name]
                self.assertEqual(old_entry["orig_len"], new_entry["orig_len"], name)
                self.assertEqual(old_entry["stored_len"], new_entry["stored_len"], name)
                self.assertEqual(
                    region_digest(old, old_entry["offset"], old_entry["stored_len"]),
                    region_digest(new, new_entry["offset"], new_entry["stored_len"]),
                    name,
                )

    def test_04_imagewty_verification(self) -> None:
        class Args:
            image = str(self.r5)

        cmd_verify(Args())


if __name__ == "__main__":
    unittest.main()
