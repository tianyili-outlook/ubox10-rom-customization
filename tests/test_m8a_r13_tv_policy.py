from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "configs" / "candidates" / "m8a-initial-atv-r13.json"
CANDIDATE = REPO / "out" / "candidates" / "m8a-initial-atv-r13"


class M8AR13TvPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))

    def test_01_scope_and_setup_contract(self) -> None:
        self.assertEqual("m8a-initial-atv-r13", self.config["id"])
        self.assertIn("m8a-initial-atv-r12", self.config["base_candidate_relative"])
        self.assertEqual(
            {
                "global.device_provisioned": 1,
                "secure.user_setup_complete": 1,
                "secure.tv_user_setup_complete": 1,
            },
            self.config["provisioning"]["final_flags"],
        )
        overlay = self.config["power_overlay"]
        self.assertEqual(1, overlay["priority"])
        self.assertEqual(1, overlay["short_press_value"])
        self.assertNotIn("long_press_value", overlay)

    def test_02_no_remote_or_mouse_mutation(self) -> None:
        files = [
            REPO / "scripts" / "build-m8a-r13-candidate.py",
            REPO / "scripts" / "install-m8-r13-tv-policy.sh",
            REPO / "configs" / "candidates" / "m8a-initial-atv-r13-overlay" / "res" / "values" / "config.xml",
        ]
        text = "\n".join(path.read_text(encoding="utf-8") for path in files if path.is_file())
        for forbidden in (
            "customer_ir_ff40.kl", "sunxi-ir-uinput.kl\" \"", "libmultiirservice.so\" \"",
            "saveenv", "setenforce 0", "permissive", "power_button_short_press",
            "MOUSE",
        ):
            self.assertNotIn(forbidden, text)
        overlay_resource = (
            REPO / "configs" / "candidates" / "m8a-initial-atv-r13-overlay" / "res" / "values" / "config.xml"
        ).read_text(encoding="utf-8")
        self.assertNotIn("config_longPressOnPowerBehavior", overlay_resource)

    def test_03_candidate_report_when_built(self) -> None:
        result_path = CANDIDATE / "build-result.json"
        if not result_path.is_file():
            self.skipTest("r13 candidate has not been built")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        firmware = Path(result["firmware"]["path"])
        self.assertTrue(firmware.is_file())
        self.assertEqual(result["firmware"]["size"], firmware.stat().st_size)
        with firmware.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest().upper()
        self.assertEqual(result["firmware"]["sha256"], actual)
        self.assertEqual(
            ["system_a", "super.fex", "Vsuper.fex", "vbmeta_system.fex", "Vvbmeta_system.fex"],
            result["payload_delta"],
        )
        validation = result["tv_policy_validation"]
        self.assertEqual([], validation["unexpected_system_differences"])
        self.assertTrue(validation["frozen_files_unchanged"])
        self.assertTrue(validation["canonical_vendor_topology_preserved"])
        self.assertEqual("SHORT_PRESS_POWER_GO_TO_SLEEP", validation["resolved_power_policy"]["short_press"])
        self.assertEqual(3, validation["resolved_power_policy"]["long_press_value"])
        self.assertEqual(1, validation["provisioning"]["expected_final_flags"]["secure.tv_user_setup_complete"])


if __name__ == "__main__":
    unittest.main()
