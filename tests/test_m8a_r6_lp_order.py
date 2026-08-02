#!/usr/bin/env python3
"""Focused validation for r6 LP table-order repair."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

REPO = Path(__file__).resolve().parents[1]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))

from sunxi_image_tool import cmd_verify, parse_file_headers, parse_main_header

CHUNK = 8 * 1024 * 1024
EXPECTED_ORDER = ["system_a", "system_b", "vendor_a", "vendor_b", "product_a", "product_b", "vendor_dlkm_a", "vendor_dlkm_b"]


def sha256_file(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(CHUNK), b""):
            value.update(block)
    return value.hexdigest().upper()


def region_digest(stream, offset: int, size: int) -> str:
    value = hashlib.sha256()
    stream.seek(offset)
    remaining = size
    while remaining:
        block = stream.read(min(CHUNK, remaining))
        if not block:
            raise EOFError("truncated IMAGEWTY payload")
        value.update(block)
        remaining -= len(block)
    return value.hexdigest().upper()


class TestM8AR6LpOrder(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.r5 = REPO / "out" / "candidates" / "m8a-initial-atv-r5" / "x12-m8a-initial-atv-r5.img"
        cls.r6_dir = REPO / "out" / "candidates" / "m8a-initial-atv-r6"
        cls.r6 = cls.r6_dir / "x12-m8a-initial-atv-r6.img"
        cls.super_image = cls.r6_dir / "super.img"
        cls.r1_super = REPO / "out" / "candidates" / "m8a-initial-atv-r1" / "super.img"
        required = (
            cls.r5,
            cls.r6,
            cls.super_image,
            cls.r1_super,
            cls.r6_dir / "build-result.json",
            cls.r6_dir / "outer-payload-audit.json",
        )
        if any(not path.is_file() for path in required):
            raise unittest.SkipTest("local r1/r5/r6 artifacts are not present")

    def test_01_identity_and_lp_order(self) -> None:
        self.assertEqual(sha256_file(self.r5), "B2EE421510BA6D6FE4C224960223DC08A8A8BFD71AD64D092B4FD9BB9E962AF0")
        result = json.loads((self.r6_dir / "build-result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["firmware"]["sha256"], sha256_file(self.r6))

        path = REPO / "scripts" / "audit-logical-system-init.py"
        spec = importlib.util.spec_from_file_location("m8a_r6_lp_parser", path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        source = module.open_super_source(self.super_image)
        try:
            metadata = module.parse_lp_metadata(source)
            self.assertEqual([item.name for item in metadata.partitions], EXPECTED_ORDER)
            self.assertTrue(all(item.attributes == 1 for item in metadata.partitions))
        finally:
            source.close()
        old_source = module.open_super_source(self.r1_super)
        try:
            old_metadata = module.parse_lp_metadata(old_source)
            self.assertEqual(
                [item.name for item in old_metadata.partitions],
                ["system_a", "vendor_a", "product_a", "vendor_dlkm_a", "system_b", "vendor_b", "product_b", "vendor_dlkm_b"],
            )
        finally:
            old_source.close()

    def test_02_only_super_and_companion_changed(self) -> None:
        audit = json.loads((self.r6_dir / "outer-payload-audit.json").read_text(encoding="utf-8"))
        actions = {item["filename"]: item["action"] for item in audit["payloads"]}
        self.assertEqual(len(actions), 50)
        self.assertEqual(actions["super.fex"], "replacement")
        self.assertEqual(actions["Vsuper.fex"], "companion")
        self.assertEqual(sum(action == "preserved" for action in actions.values()), 48)

        with self.r5.open("rb") as old, self.r6.open("rb") as new:
            old_main = parse_main_header(old)
            new_main = parse_main_header(new)
            old_entries = {item["filename"]: item for item in parse_file_headers(old, old_main["num_files"])}
            new_entries = {item["filename"]: item for item in parse_file_headers(new, new_main["num_files"])}
            self.assertEqual(set(old_entries), set(new_entries))
            for name in sorted(set(old_entries) - {"super.fex", "Vsuper.fex"}):
                left = old_entries[name]
                right = new_entries[name]
                self.assertEqual(left["orig_len"], right["orig_len"], name)
                self.assertEqual(left["stored_len"], right["stored_len"], name)
                self.assertEqual(region_digest(old, left["offset"], left["stored_len"]), region_digest(new, right["offset"], right["stored_len"]), name)

    def test_03_imagewty_verification(self) -> None:
        class Args:
            image = str(self.r6)

        cmd_verify(Args())


if __name__ == "__main__":
    unittest.main()
