from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/candidates/m8b-remote-r1.json"
FINAL = ROOT / "out/candidates/m8b-remote-r1"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


class M8BRemoteR1CandidateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = json.loads(CONFIG.read_text(encoding="utf-8"))
        self.integration = self.config["integration"]
        self.service = self.config["remote_service"]
        self.source_root = ROOT / self.integration["source_root_relative"]

    def test_direct_accepted_baseline_and_payload_scope(self) -> None:
        self.assertEqual(self.config["id"], "m8b-remote-r1")
        self.assertEqual(self.config["parent_config_relative"], "configs/candidates/m8b-ime-r1.json")
        self.assertEqual(
            self.config["base_candidate_sha256"],
            "B89612D5004BA3D8214F21E22E4BED7BFBA5B2F8FE441F9364315F851F1FE240",
        )
        self.assertEqual(self.config["container"]["replacements"], ["super.fex", "vbmeta_system.fex"])
        self.assertEqual(self.config["container"]["companions"], ["Vsuper.fex", "Vvbmeta_system.fex"])

    def test_aosp_integration_sources_are_hash_locked_and_no_donor_is_tracked(self) -> None:
        patch = ROOT / self.integration["patch_relative"]
        installer = ROOT / self.integration["install_script_relative"]
        self.assertEqual(digest(patch), self.integration["patch_sha256"])
        self.assertEqual(digest(installer), self.integration["install_script_sha256"])
        for relative, expected in self.integration["source_files"].items():
            self.assertEqual(digest(self.source_root / relative), expected)
        self.assertFalse((self.source_root / "AndroidTvRemoteService.apk").exists())
        blueprint = (self.source_root / "Android.bp").read_text(encoding="utf-8")
        self.assertIn('android_app_import {', blueprint)
        self.assertIn('runtime_resource_overlay {', blueprint)
        self.assertIn('system_ext_specific: true', blueprint)
        self.assertIn('privileged: true', blueprint)

    def test_permission_contract_is_connect_only(self) -> None:
        privapp = ET.parse(
            self.source_root / "permissions/privapp-permissions-com.google.android.tv.remote.service.xml"
        )
        allowed = sorted(item.attrib["name"] for item in privapp.findall(".//permission"))
        self.assertEqual(allowed, sorted(self.service["requested_privileged_permissions"]))
        self.assertNotIn("android.permission.INJECT_EVENTS", allowed)

        defaults = ET.parse(
            self.source_root
            / "default-permissions/default-permissions-com.google.android.tv.remote.service.xml"
        )
        granted = [item.attrib["name"] for item in defaults.findall(".//permission")]
        self.assertEqual(granted, ["android.permission.BLUETOOTH_CONNECT"])
        self.assertNotIn("android.permission.BLUETOOTH_SCAN", granted)
        self.assertNotIn("android.permission.BLUETOOTH_ADVERTISE", granted)

    def test_historical_provenance_and_play_boundary(self) -> None:
        history = self.config["historical_remote_v2"]
        self.assertEqual(history["implementation_commit"], "a8cd9629d4049161022099e6566024c28074a979")
        self.assertEqual(history["device_result_commit"], "1e4fa199413df6f74fe24f7c5edde9bc69c34c0a")
        self.assertEqual(history["ports"], [6466, 6467])
        self.assertEqual(history["mdns_service"], "_androidtvremote2._tcp")
        self.assertEqual(self.config["play_regression_guard"]["baseline_play_gms_state"], "No Play Store or GMS app directories in accepted system/product inventory")

    def test_built_candidate_when_present(self) -> None:
        if not FINAL.exists():
            self.skipTest("ignored local m8b-remote-r1 candidate is absent")
        result = json.loads((FINAL / "build-result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "READY TO FLASH")
        self.assertEqual(result["firmware"]["sha256"], "F3B09E5565AC4ED4E5EE326D392622E7B036A8519B8444B966E77CC4751B814A")
        self.assertEqual(result["changed_logical_partitions"], ["system_a"])
        self.assertEqual(result["protected_logical_partitions_unchanged"], ["product_a", "vendor_a", "vendor_dlkm_a"])
        self.assertEqual(result["filesystem_validation"]["unexpected_paths"], [])
        self.assertTrue(result["leanback_ime_preserved"])
        self.assertFalse(result["play_store_regression_guard"]["historical_Test9r2_Play_changes_imported"])
        for name in ("vendor_a", "product_a", "vendor_dlkm_a"):
            self.assertEqual(result["logical_before"][name]["sha256"], result["logical_after"][name]["sha256"])


if __name__ == "__main__":
    unittest.main()
