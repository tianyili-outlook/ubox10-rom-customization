from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "configs" / "candidates" / "m8a-initial-atv-r12.json"
CANDIDATE = REPO / "out" / "candidates" / "m8a-initial-atv-r12"


class M8AR12RemoteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))

    def test_01_single_variable_and_base(self) -> None:
        self.assertEqual("m8a-initial-atv-r12", self.config["id"])
        self.assertIn("m8a-initial-atv-r11", self.config["base_candidate_relative"])
        destinations = {item["destination_path"] for item in self.config["remote_artifacts"]}
        self.assertEqual(
            {
                "/system/bin/multi_ir",
                "/system/etc/init/multi_ir.rc",
                "/system/usr/keylayout/customer_ir_ff40.kl",
                "/system/usr/keylayout/sunxi-ir.kl",
                "/system/usr/keylayout/sunxi-ir-uinput.kl",
                "/system/lib/libmultiirservice.so",
                "/system/lib/libinput.so",
            },
            destinations,
        )
        self.assertEqual(84, self.config["mouse_contract"]["toggle_scancode_decimal"])
        self.assertEqual("ff4054", self.config["mouse_contract"]["raw_msc_scan"])

    def test_02_no_unrelated_hardware_or_ui_mutation(self) -> None:
        builder = (REPO / "scripts" / "build-m8a-r12-candidate.py").read_text(encoding="utf-8")
        installer = (REPO / "scripts" / "install-m8-test8r2-remote-stack.sh").read_text(encoding="utf-8")
        text = builder + installer
        for forbidden in (
            "saveenv", "setenforce 0", "permissive multi_ir", "vendor_boot", "dtbo",
            "ProjectivyLauncher.apk\" \"", "device_provisioned", "user_setup_complete",
        ):
            self.assertNotIn(forbidden, text)
        self.assertNotIn("libmultiir_jni.so", installer)
        self.assertNotIn("virtual-remote.kl", installer)
        self.assertNotIn("customer_ir_4040.kl", installer)

    def test_03_candidate_report_when_built(self) -> None:
        result_path = CANDIDATE / "build-result.json"
        if not result_path.is_file():
            self.skipTest("r12 candidate has not been built")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        firmware = Path(result["firmware"]["path"])
        self.assertTrue(firmware.is_file())
        self.assertEqual(result["firmware"]["size"], firmware.stat().st_size)
        self.assertEqual(result["firmware"]["sha256"], hashlib.sha256(firmware.read_bytes()).hexdigest().upper())
        self.assertEqual(
            ["system_a", "super.fex", "Vsuper.fex", "vbmeta_system.fex", "Vvbmeta_system.fex"],
            result["payload_delta"],
        )
        validation = result["remote_validation"]
        self.assertEqual([], validation["unexpected_system_differences"])
        self.assertTrue(validation["projectivy_unchanged"])
        self.assertTrue(validation["r10_compatibility_libraries_unchanged"])
        self.assertTrue(result["remote_elf_validation"]["all_dt_needed_resolved"])
        self.assertTrue(result["selinux_validation"]["split_policy_compile"]["passed"])


if __name__ == "__main__":
    unittest.main()
