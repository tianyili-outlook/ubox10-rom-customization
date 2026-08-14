from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "configs" / "candidates" / "m8b-rc-core-r3.json"
R2_CONFIG = REPO / "configs" / "candidates" / "m8b-rc-core-r2.json"
R2 = REPO / "out" / "candidates" / "m8b-rc-core-r2"
R3 = REPO / "out" / "candidates" / "m8b-rc-core-r3"
DEVICE_KL = "Vendor_0001_Product_0001_Version_0100.kl"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest().upper()


class M8BRcCoreR3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))
        cls.r2_config = json.loads(R2_CONFIG.read_text(encoding="utf-8"))

    def test_01_exact_single_variable_and_r2_base(self) -> None:
        self.assertEqual("m8b-rc-core-r3", self.config["id"])
        self.assertEqual("configs/candidates/m8b-rc-core-r2.json", self.config["parent_config_relative"])
        self.assertEqual("out/candidates/m8b-rc-core-r2/x12-m8b-rc-core-r2.img", self.config["base_candidate_relative"])
        self.assertTrue(self.config["reuse_base_boot"])
        self.assertEqual(DEVICE_KL, self.config["device_keylayout_filename"])
        self.assertNotIn("kernel_repeat_patch", self.config)
        for forbidden in ("timeout", "decoder", "dtbo", "power", "settings"):
            self.assertNotIn(forbidden, json.dumps(self.config).lower())

    def test_02_existing_chain_is_parameterized(self) -> None:
        builder = (REPO / "scripts" / "build-m8b-rc-core-r1-candidate.py").read_text(encoding="utf-8")
        installer = (REPO / "scripts" / "install-m8b-rc-core-input.sh").read_text(encoding="utf-8")
        self.assertIn('parent = overlay.get("parent_config_relative")', builder)
        self.assertIn('if self.config.get("reuse_base_boot")', builder)
        self.assertIn('device_keylayout_filename = self.config.get("device_keylayout_filename")', builder)
        self.assertIn("DEVICE_KEYLAYOUT_FILENAME", installer)
        self.assertIn('cmp -s "$kl_target" "$device_target"', installer)
        for forbidden in ("saveenv", "setenforce 0", "permissive"):
            self.assertNotIn(forbidden, builder + installer)

    def test_03_candidate_report_when_built(self) -> None:
        result_path = R3 / "build-result.json"
        if not result_path.is_file():
            self.skipTest("M8B rc-core-r3 candidate has not been built")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        r2_result = json.loads((R2 / "build-result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["firmware"]["sha256"], digest(Path(result["firmware"]["path"])))
        self.assertEqual(r2_result["firmware"]["sha256"], result["base_candidate"]["sha256"])
        self.assertEqual(r2_result["boot"]["sha256"], result["boot"]["sha256"])
        self.assertEqual(self.r2_config["kernel_repeat_patch"], result["kernel_repeat_patch"])
        self.assertEqual(
            ["system_a", "super.fex", "Vsuper.fex", "vbmeta_system.fex", "Vvbmeta_system.fex"],
            result["payload_delta"],
        )
        validation = result["native_input_validation"]
        target = "/system/usr/keylayout/" + DEVICE_KL
        self.assertEqual([target], validation["changed_system_files"])
        self.assertEqual([], validation["unexpected_system_differences"])
        self.assertEqual(target, validation["device_keylayout_path"])
        self.assertTrue(validation["device_keylayout_identical_to_sunxi_ir"])
        self.assertEqual("disabled", validation["multi_ir_init_state"])
        self.assertTrue(result["boot_validation"]["base_boot_reused_byte_for_byte"])
        self.assertEqual(
            "FE23BEEAE10389EA13575CA266AF45797F22BCF9BDBA7037AF6F7A8B3148C5E2",
            result["boot_validation"]["candidate_kernel"]["sha256"],
        )
        audit = json.loads((R3 / "outer-payload-audit.json").read_text(encoding="utf-8"))
        actions = {item["filename"]: item["action"] for item in audit["payloads"]}
        self.assertEqual("preserved", actions["boot.fex"])
        self.assertEqual("preserved", actions["Vboot.fex"])


if __name__ == "__main__":
    unittest.main()
