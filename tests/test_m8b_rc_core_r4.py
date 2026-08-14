from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "configs" / "candidates" / "m8b-rc-core-r4.json"
R3 = REPO / "out" / "candidates" / "m8b-rc-core-r3"
R4 = REPO / "out" / "candidates" / "m8b-rc-core-r4"
DEVICE_KL = "Vendor_0001_Product_0001_Version_0100.kl"
ESSENTIAL = {
    352: "DPAD_CENTER", 103: "DPAD_UP", 108: "DPAD_DOWN", 105: "DPAD_LEFT", 106: "DPAD_RIGHT",
    172: "HOME", 158: "BACK", 115: "VOLUME_UP", 114: "VOLUME_DOWN", 116: "POWER", 171: "SETTINGS",
}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest().upper()


def keylayout(path: Path) -> dict[int, tuple[str, list[str]]]:
    result: dict[int, tuple[str, list[str]]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("key "):
            continue
        fields = line.split()
        result[int(fields[1])] = (fields[2], fields[3:])
    return result


class M8BRcCoreR4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))

    def test_01_exact_parser_contract_and_r3_base(self) -> None:
        self.assertEqual("m8b-rc-core-r4", self.config["id"])
        self.assertEqual("configs/candidates/m8b-rc-core-r3.json", self.config["parent_config_relative"])
        self.assertEqual("out/candidates/m8b-rc-core-r3/x12-m8b-rc-core-r3.img", self.config["base_candidate_relative"])
        parser = self.config["android_keylayout_parser"]
        self.assertEqual({"APPS": "ALL_APPS", "BROWSER": "EXPLORER", "EXPAND": "TV_ZOOM_MODE"}, parser["keycode_conversions"])
        self.assertEqual({"WAKE_DROPPED": "WAKE"}, parser["flag_conversions"])
        self.assertNotIn("kernel", self.config)
        for forbidden in ("rc-main", "decoder", "timeout", "dtbo", "power policy", "projectivy"):
            self.assertNotIn(forbidden, json.dumps(self.config).lower())

    def test_02_existing_r3_chain_is_reused(self) -> None:
        builder = (REPO / "scripts" / "build-m8b-rc-core-r1-candidate.py").read_text(encoding="utf-8")
        converter = (REPO / "scripts" / "convert-m8b-android12-keylayout.py").read_text(encoding="utf-8")
        installer = (REPO / "scripts" / "install-m8b-rc-core-input.sh").read_text(encoding="utf-8")
        self.assertIn("def load_overlay", builder)
        self.assertIn('self.config.get("android_keylayout_parser")', builder)
        self.assertIn("KEYCODES_SEQUENCE", converter)
        self.assertIn("FLAGS_SEQUENCE", converter)
        self.assertIn("complete_parse_audit", converter)
        self.assertIn("DEVICE_KEYLAYOUT_SOURCE", installer)

    def test_03_candidate_report_when_built(self) -> None:
        result_path = R4 / "build-result.json"
        if not result_path.is_file():
            self.skipTest("M8B rc-core-r4 candidate has not been built")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        r3_result = json.loads((R3 / "build-result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["firmware"]["sha256"], digest(Path(result["firmware"]["path"])))
        self.assertEqual(r3_result["firmware"]["sha256"], result["base_candidate"]["sha256"])
        self.assertEqual(r3_result["boot"]["sha256"], result["boot"]["sha256"])
        parser = result["keylayout_parser_validation"]
        self.assertTrue(parser["complete_parse_audit"])
        self.assertEqual(46, parser["parsed_entries"])
        self.assertEqual(["APPS", "BROWSER", "EXPAND"], parser["unsupported_input_keycodes"])
        self.assertEqual(["WAKE_DROPPED"], parser["unsupported_input_flags"])
        self.assertEqual([], parser["omitted_entries"])
        self.assertEqual(11, len(parser["conversions"]))
        final_kl = R4 / "generated-input" / "android12-device.kl"
        mappings = keylayout(final_kl)
        for code, label in ESSENTIAL.items():
            self.assertEqual(label, mappings[code][0])
        self.assertNotIn("WAKE_DROPPED", final_kl.read_text(encoding="utf-8"))
        self.assertEqual(["WAKE"], parser["final_flags"])
        validation = result["native_input_validation"]
        self.assertEqual(["/system/usr/keylayout/" + DEVICE_KL], validation["changed_system_files"])
        self.assertFalse(validation["device_keylayout_identical_to_sunxi_ir"])
        self.assertEqual("disabled", validation["multi_ir_init_state"])
        self.assertEqual(
            "FE23BEEAE10389EA13575CA266AF45797F22BCF9BDBA7037AF6F7A8B3148C5E2",
            result["boot_validation"]["candidate_kernel"]["sha256"],
        )
        self.assertEqual(
            ["system_a", "super.fex", "Vsuper.fex", "vbmeta_system.fex", "Vvbmeta_system.fex"],
            result["payload_delta"],
        )
        audit = json.loads((R4 / "outer-payload-audit.json").read_text(encoding="utf-8"))
        actions = {item["filename"]: item["action"] for item in audit["payloads"]}
        self.assertEqual("preserved", actions["boot.fex"])
        self.assertEqual("preserved", actions["Vboot.fex"])


if __name__ == "__main__":
    unittest.main()
