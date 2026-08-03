#!/usr/bin/env python3
"""Focused r7 check: only super changes and system root has /metadata."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
from sunxi_image_tool import cmd_verify


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""): value.update(block)
    return value.hexdigest().upper()


class TestM8AR7MetadataRoot(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.r6 = REPO / "out/candidates/m8a-initial-atv-r6/x12-m8a-initial-atv-r6.img"
        cls.r7dir = REPO / "out/candidates/m8a-initial-atv-r7"
        cls.r7 = cls.r7dir / "x12-m8a-initial-atv-r7.img"
        if not all(path.is_file() for path in (cls.r6, cls.r7, cls.r7dir / "super.img", cls.r7dir / "outer-payload-audit.json")): raise unittest.SkipTest("local r6/r7 artifacts are not present")

    def test_01_metadata_root_and_source_identity(self) -> None:
        result = json.loads((self.r7dir / "system-root-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(result["added"], "/metadata")
        self.assertEqual(result["firmware"]["sha256"], sha256(self.r7))
        spec = importlib.util.spec_from_file_location("r7_audit", REPO / "scripts/audit-logical-system-init.py"); module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
        source = module.open_super_source(self.r7dir / "super.img")
        try:
            metadata = module.parse_lp_metadata(source); system = module.LogicalPartitionSource(source, metadata, "system_a")
            reader = module.Ext4Reader(system)
            self.assertIn("metadata", reader.directory(reader.inode(2)))
        finally: source.close()

    def test_02_outer_and_imagewty(self) -> None:
        actions = {item["filename"]: item["action"] for item in json.loads((self.r7dir / "outer-payload-audit.json").read_text(encoding="utf-8"))["payloads"]}
        self.assertEqual(len(actions), 50); self.assertEqual(actions["super.fex"], "replacement"); self.assertEqual(actions["Vsuper.fex"], "companion"); self.assertEqual(sum(value == "preserved" for value in actions.values()), 48)
        class Args: image = str(self.r7)
        cmd_verify(Args())


if __name__ == "__main__": unittest.main()
