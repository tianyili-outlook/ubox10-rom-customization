#!/usr/bin/env python3
"""Focused offline checks for the r11 real Android TV HOME Launcher candidate."""
from __future__ import annotations

import json
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]


class R11LauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads((REPO / "configs/candidates/m8a-initial-atv-r11.json").read_text(encoding="utf-8"))
        cls.out = REPO / "out/candidates/m8a-initial-atv-r11"

    def test_01_single_variable_contract(self) -> None:
        launcher = self.config["launcher"]
        self.assertEqual(self.config["base_candidate_relative"], "out/candidates/m8a-initial-atv-r10/x12-m8a-initial-atv-r10.img")
        self.assertEqual(launcher["destination_path"], "/system/app/ProjectivyLauncher/ProjectivyLauncher.apk")
        self.assertEqual(launcher["package"], "com.spocky.projengmenu")
        self.assertIn("android.intent.category.HOME", launcher["categories"])
        self.assertIn("android.intent.category.DEFAULT", launcher["categories"])
        self.assertIn("android.intent.category.LEANBACK_LAUNCHER", launcher["categories"])
        self.assertFalse(launcher["privileged"])
        self.assertIsNone(launcher["shared_user_id"])
        self.assertEqual(launcher["required_shared_libraries"], [])

    def test_02_builder_does_not_mix_provisioning_or_hardware_changes(self) -> None:
        builder = (REPO / "scripts/build-m8a-r11-candidate.py").read_text(encoding="utf-8")
        installer = (REPO / "scripts/install-m8-projectivy-launcher.sh").read_text(encoding="utf-8")
        self.assertIn("install-m8-projectivy-launcher.sh", builder)
        self.assertIn("/system/app", installer)
        for forbidden in ("device_provisioned", "user_setup_complete", "SetupWizard", "permissive", "saveenv"):
            self.assertNotIn(forbidden, builder + installer)

    def test_03_local_candidate_report(self) -> None:
        result_path = self.out / "build-result.json"
        if not result_path.is_file():
            self.skipTest("local r11 artifact is not present")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        validation = result["launcher_validation"]
        self.assertEqual(result["base_candidate"]["sha256"], self.config["base_candidate_sha256"])
        self.assertEqual(result["payload_delta"], ["system_a", "super.fex", "Vsuper.fex", "vbmeta_system.fex", "Vvbmeta_system.fex"])
        self.assertTrue(validation["package_manager_scan"]["scan_eligible"])
        self.assertTrue(validation["native_dependencies_resolved"])
        self.assertTrue(validation["r10_compatibility_libraries_unchanged"])
        self.assertTrue(validation["canonical_vendor_topology_preserved"])
        self.assertEqual(validation["unexpected_system_differences"], [])


if __name__ == "__main__":
    unittest.main()
