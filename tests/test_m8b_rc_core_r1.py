from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "configs" / "candidates" / "m8b-rc-core-r1.json"
MAP = REPO / "configs" / "candidates" / "m8b-rc-core-r1" / "ff40-map.json"
DISABLED_RC = REPO / "configs" / "candidates" / "m8b-rc-core-r1" / "multi_ir.rc"
CANDIDATE = REPO / "out" / "candidates" / "m8b-rc-core-r1"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest().upper()


class M8BRcCoreR1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))
        cls.mapping = json.loads(MAP.read_text(encoding="utf-8"))

    def test_01_exact_map_and_single_variable(self) -> None:
        self.assertEqual("m8b-rc-core-r1", self.config["id"])
        self.assertIn("m8a-initial-atv-r13", self.config["base_candidate_relative"])
        self.assertEqual(self.config["mapping"]["sha256"], digest(MAP))
        self.assertEqual(49, len(self.mapping["entries"]))
        native = [item for item in self.mapping["entries"] if item.get("include_in_rc_map", True)]
        inert = [item for item in self.mapping["entries"] if not item.get("include_in_rc_map", True)]
        self.assertEqual(48, len(native))
        self.assertEqual([84], [item["scan"] for item in inert])
        self.assertEqual("MOUSE", inert[0]["android"])
        self.assertEqual(
            {11: "KEY_UP", 13: "KEY_OK", 26: "KEY_HOMEPAGE", 66: "KEY_BACK", 77: "KEY_POWER"},
            {item["scan"]: item["linux_symbol"] for item in native if item["scan"] in {11, 13, 26, 66, 77}},
        )

    def test_02_native_runtime_contract(self) -> None:
        rc = DISABLED_RC.read_text(encoding="utf-8")
        kernel_builder = (REPO / "scripts" / "build-m8b-rc-core-kernel.sh").read_text(encoding="utf-8")
        candidate_builder = (REPO / "scripts" / "build-m8b-rc-core-r1-candidate.py").read_text(encoding="utf-8")
        self.assertIn("\n        disabled\n", rc)
        self.assertIn("--disable SUNXI_MULTI_IR_SUPPORT", kernel_builder)
        self.assertIn("build_id = self.candidate_id", candidate_builder)
        for forbidden in ("saveenv", "setenforce 0", "permissive", "dtbo.fex="):
            self.assertNotIn(forbidden, kernel_builder + candidate_builder)

    def test_03_candidate_report_when_built(self) -> None:
        result_path = CANDIDATE / "build-result.json"
        if not result_path.is_file():
            self.skipTest("M8B rc-core-r1 candidate has not been built")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        firmware = Path(result["firmware"]["path"])
        self.assertTrue(firmware.is_file())
        self.assertEqual(result["firmware"]["size"], firmware.stat().st_size)
        self.assertEqual(result["firmware"]["sha256"], digest(firmware))
        self.assertEqual(
            ["boot/kernel", "boot.fex", "Vboot.fex", "system_a", "super.fex", "Vsuper.fex", "vbmeta_system.fex", "Vvbmeta_system.fex"],
            result["payload_delta"],
        )
        self.assertTrue(result["boot_validation"]["stock_ramdisk_unchanged"])
        self.assertTrue(result["boot_validation"]["vendor_boot_unchanged"])
        self.assertFalse(result["boot_validation"]["dts_dtbo_changed"])
        validation = result["native_input_validation"]
        self.assertEqual([], validation["unexpected_system_differences"])
        self.assertEqual("disabled", validation["multi_ir_init_state"])
        self.assertFalse(validation["uinput_runtime_dependency"])
        self.assertEqual("intentionally dropped/inert", validation["mouse_mode"])
        self.assertEqual(5, len(validation["legacy_artifacts_retained_inert"]))


if __name__ == "__main__":
    unittest.main()
