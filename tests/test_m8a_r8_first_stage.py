#!/usr/bin/env python3
"""Focused validation for r8 first-stage UART-console candidate."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
from sunxi_image_tool import cmd_verify, parse_file_headers, parse_main_header


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""): value.update(block)
    return value.hexdigest().upper()


class TestM8AR8FirstStage(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.r7 = REPO / "out/candidates/m8a-initial-atv-r7/x12-m8a-initial-atv-r7.img"
        cls.r8dir = REPO / "out/candidates/m8a-initial-atv-r8"; cls.r8 = cls.r8dir / "x12-m8a-initial-atv-r8.img"
        if not all(path.is_file() for path in (cls.r7, cls.r8, cls.r8dir / "build-result.json", cls.r8dir / "outer-payload-audit.json")): raise unittest.SkipTest("local r7/r8 artifacts are not present")

    def test_01_identity_and_cmdline(self) -> None:
        self.assertEqual(digest(self.r7), "3098E1B238B60A39A8D93AAD3BF80EE6295338F99BD021F2A8C452168E6A370B")
        result = json.loads((self.r8dir / "build-result.json").read_text(encoding="utf-8")); self.assertEqual(result["firmware"]["sha256"], digest(self.r8))
        console = json.loads((self.r8dir / "boot-console.json").read_text(encoding="utf-8"))
        self.assertEqual(console["old_cmdline"], ""); self.assertEqual(console["new_cmdline"], "console=ttyS0,115200n8 ignore_loglevel")

    def test_02_only_boot_and_companion_changed(self) -> None:
        actions = {item["filename"]: item["action"] for item in json.loads((self.r8dir / "outer-payload-audit.json").read_text(encoding="utf-8"))["payloads"]}
        self.assertEqual(len(actions), 50); self.assertEqual(actions["boot.fex"], "replacement"); self.assertEqual(actions["Vboot.fex"], "companion"); self.assertEqual(sum(value == "preserved" for value in actions.values()), 48)

    def test_03_imagewty(self) -> None:
        class Args: image = str(self.r8)
        cmd_verify(Args())


if __name__ == "__main__": unittest.main()
