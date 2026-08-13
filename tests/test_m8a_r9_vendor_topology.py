#!/usr/bin/env python3
"""Focused checks for the r9 canonical vendor mount-point candidate."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
from sunxi_image_tool import cmd_verify


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest().upper()


class TestM8AR9VendorTopology(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads((REPO / "configs/candidates/m8a-initial-atv-r9.json").read_text(encoding="utf-8"))
        cls.out = REPO / "out/candidates/m8a-initial-atv-r9"
        cls.image = cls.out / "x12-m8a-initial-atv-r9.img"

    def test_01_build_source_repairs_vendor_direction(self) -> None:
        common = (REPO / "scripts/build-m8a-candidate.py").read_text(encoding="utf-8")
        repair = (REPO / "scripts/fix-m8-system-vendor-topology.sh").read_text(encoding="utf-8")
        self.assertIn("fix-m8-system-vendor-topology.sh", common)
        self.assertIn("ln -s /vendor", repair)
        self.assertIn("expected /vendor source symlink", repair)

    def test_02_artifact_identity_and_topology(self) -> None:
        if not self.image.is_file():
            self.skipTest("local r9 artifact is not present")
        result = json.loads((self.out / "build-result.json").read_text(encoding="utf-8"))
        topology = json.loads((self.out / "topology-validation.json").read_text(encoding="utf-8"))
        self.assertEqual(result["firmware"]["sha256"], digest(self.image))
        self.assertEqual(result["base_candidate"]["sha256"], self.config["base_candidate_sha256"])
        self.assertEqual(topology["r9"]["/vendor"]["lstat"]["type"], "directory")
        self.assertEqual(topology["r9"]["/vendor"]["realpath"], "/vendor")
        self.assertEqual(topology["r9"]["/system/vendor"]["readlink"], "/vendor")
        self.assertEqual(topology["unexpected_system_differences"], [])
        for name in ("vendor_a", "product_a", "vendor_dlkm_a"):
            self.assertEqual(result["logical_before"][name]["sha256"], result["logical_after"][name]["sha256"])

    def test_03_only_expected_outer_payloads_changed(self) -> None:
        if not self.image.is_file():
            self.skipTest("local r9 artifact is not present")
        actions = {item["filename"]: item["action"] for item in json.loads((self.out / "outer-payload-audit.json").read_text(encoding="utf-8"))["payloads"]}
        self.assertEqual({name for name, action in actions.items() if action == "replacement"}, {"super.fex", "vbmeta_system.fex"})
        self.assertEqual({name for name, action in actions.items() if action == "companion"}, {"Vsuper.fex", "Vvbmeta_system.fex"})
        self.assertEqual(sum(action == "preserved" for action in actions.values()), 46)

    def test_04_imagewty_checksums(self) -> None:
        if not self.image.is_file():
            self.skipTest("local r9 artifact is not present")
        class Args:
            image = str(self.image)
        cmd_verify(Args())


if __name__ == "__main__":
    unittest.main()
