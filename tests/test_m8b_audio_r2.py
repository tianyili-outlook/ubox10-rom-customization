from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "configs" / "candidates" / "m8b-audio-r2.json"
PATCH = REPO / "configs" / "aosp" / "m8b-audio-r2-treble-vndk.patch"
FINAL = REPO / "out" / "candidates" / "m8b-audio-r2"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


class M8BAudioR2Test(unittest.TestCase):
    def setUp(self) -> None:
        self.config = json.loads(CONFIG.read_text(encoding="utf-8"))

    def test_single_product_contract_patch(self) -> None:
        text = PATCH.read_text(encoding="utf-8")
        self.assertEqual(digest(PATCH), self.config["aosp_treble_contract"]["source_patch_sha256"])
        self.assertIn("PRODUCT_SHIPPING_API_LEVEL := 31", text)
        self.assertIn("BOARD_VNDK_VERSION := current", text)
        self.assertIn("com.android.vndk.current", text)
        self.assertNotIn("ld.config.txt", text)
        self.assertNotIn("/vendor/lib/libaudioroute.so", text)

    def test_candidate_scope(self) -> None:
        self.assertEqual(self.config["parent_config_relative"], "configs/candidates/m8b-audio-r1.json")
        self.assertEqual(self.config["candidate_contract"]["changed_path"], "/system/build.prop")
        self.assertEqual(self.config["candidate_contract"]["old_line"], "ro.treble.enabled=false")
        self.assertEqual(self.config["candidate_contract"]["new_line"], "ro.treble.enabled=true")

    def test_built_candidate_when_present(self) -> None:
        if not FINAL.exists():
            self.skipTest("candidate not built yet")
        result = json.loads((FINAL / "build-result.json").read_text(encoding="utf-8"))
        validation = result["audio_treble_validation"]
        self.assertTrue(validation["offline_linkerconfig"]["vndk_namespace"])
        self.assertTrue(validation["offline_linkerconfig"]["default_to_vndk_exports_libaudioroute"])
        self.assertFalse(validation["generated_ld_config_patched"])
        self.assertFalse(validation["vendor_libaudioroute_copy"])
        self.assertEqual(
            result["payload_delta"],
            ["system_a", "super.fex", "Vsuper.fex", "vbmeta_system.fex", "Vvbmeta_system.fex"],
        )
        self.assertEqual(result["logical_before"]["vendor_a"]["sha256"], result["logical_after"]["vendor_a"]["sha256"])
        self.assertEqual(result["boot"]["sha256"], "0A9473513B309BA3168242500658F35D96EC40B49CA91E33C1068861F8756678")


if __name__ == "__main__":
    unittest.main()
