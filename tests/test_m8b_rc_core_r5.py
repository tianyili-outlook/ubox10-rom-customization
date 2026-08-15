from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "configs" / "candidates" / "m8b-rc-core-r5.json"
R4 = REPO / "out" / "candidates" / "m8b-rc-core-r4"
R5 = REPO / "out" / "candidates" / "m8b-rc-core-r5"
DEVICE_KL = "Vendor_0001_Product_0001_Version_0100.kl"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest().upper()


def mappings(path: Path) -> dict[int, tuple[str, tuple[str, ...]]]:
    result: dict[int, tuple[str, tuple[str, ...]]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("key "):
            continue
        fields = line.split()
        result[int(fields[1])] = (fields[2], tuple(fields[3:]))
    return result


class M8BRcCoreR5Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))

    def test_01_single_semantic_variable_and_r4_base(self) -> None:
        self.assertEqual("m8b-rc-core-r5", self.config["id"])
        self.assertEqual("configs/candidates/m8b-rc-core-r4.json", self.config["parent_config_relative"])
        self.assertEqual("out/candidates/m8b-rc-core-r4/x12-m8b-rc-core-r4.img", self.config["base_candidate_relative"])
        self.assertEqual(
            {"171": {"from": "SETTINGS", "to": "MENU"}},
            self.config["android_keylayout_parser"]["linux_keycode_overrides"],
        )
        self.assertNotIn("kernel", self.config)
        serialized = json.dumps(self.config).lower()
        for forbidden in ("rc-main", "decoder", "timeout", "dtbo", "power policy", "projectivy"):
            self.assertNotIn(forbidden, serialized)

    def test_02_existing_chain_verifies_r4_target_before_replace(self) -> None:
        builder = (REPO / "scripts" / "build-m8b-rc-core-r1-candidate.py").read_text(encoding="utf-8")
        converter = (REPO / "scripts" / "convert-m8b-android12-keylayout.py").read_text(encoding="utf-8")
        installer = (REPO / "scripts" / "install-m8b-rc-core-input.sh").read_text(encoding="utf-8")
        self.assertIn('self.config.get("base_device_keylayout_sha256")', builder)
        self.assertIn("linux_keycode_overrides", converter)
        self.assertIn("applied_linux_keycode_overrides", converter)
        self.assertIn("EXISTING_DEVICE_KEYLAYOUT_SHA256", installer)
        self.assertIn("existing device keylayout identity mismatch", installer)

    def test_03_candidate_report_when_built(self) -> None:
        result_path = R5 / "build-result.json"
        if not result_path.is_file():
            self.skipTest("M8B rc-core-r5 candidate has not been built")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        r4_result = json.loads((R4 / "build-result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["firmware"]["sha256"], digest(Path(result["firmware"]["path"])))
        self.assertEqual(r4_result["firmware"]["sha256"], result["base_candidate"]["sha256"])
        self.assertEqual(r4_result["boot"]["sha256"], result["boot"]["sha256"])
        self.assertEqual(r4_result["boot_validation"]["candidate_kernel"]["sha256"], result["boot_validation"]["candidate_kernel"]["sha256"])

        before = mappings(R4 / "generated-input" / "android12-device.kl")
        after = mappings(R5 / "generated-input" / "android12-device.kl")
        changed = {code: (before.get(code), after.get(code)) for code in before | after if before.get(code) != after.get(code)}
        self.assertEqual({171: (("SETTINGS", ("WAKE",)), ("MENU", ("WAKE",)))}, changed)

        parser = result["keylayout_parser_validation"]
        self.assertTrue(parser["complete_parse_audit"])
        self.assertEqual(46, parser["parsed_entries"])
        self.assertEqual(["171"], parser["applied_linux_keycode_overrides"])
        self.assertEqual([], parser["omitted_entries"])
        self.assertNotIn("WAKE_DROPPED", (R5 / "generated-input" / "android12-device.kl").read_text(encoding="utf-8"))
        self.assertEqual(["WAKE"], parser["final_flags"])

        validation = result["native_input_validation"]
        self.assertEqual(["/system/usr/keylayout/" + DEVICE_KL], validation["changed_system_files"])
        self.assertEqual("disabled", validation["multi_ir_init_state"])
        self.assertEqual(
            ["system_a", "super.fex", "Vsuper.fex", "vbmeta_system.fex", "Vvbmeta_system.fex"],
            result["payload_delta"],
        )
        audit = json.loads((R5 / "outer-payload-audit.json").read_text(encoding="utf-8"))
        actions = {item["filename"]: item["action"] for item in audit["payloads"]}
        self.assertEqual("preserved", actions["boot.fex"])
        self.assertEqual("preserved", actions["Vboot.fex"])


if __name__ == "__main__":
    unittest.main()
