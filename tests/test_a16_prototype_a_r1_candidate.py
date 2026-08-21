"""Focused guardrails for the Android 16 Prototype A exact-board candidate."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET


REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "configs/candidates/a16-prototype-a-r1.json"
CANDIDATE = REPO / "out/candidates/a16-prototype-a-r1"
BUILDER_PATH = REPO / "scripts/build-a16-prototype-a-r1-candidate.py"
BUILDER_SPEC = importlib.util.spec_from_file_location("a16_candidate_builder", BUILDER_PATH)
assert BUILDER_SPEC is not None and BUILDER_SPEC.loader is not None
BUILDER = importlib.util.module_from_spec(BUILDER_SPEC)
BUILDER_SPEC.loader.exec_module(BUILDER)


class A16PrototypeAR1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))

    def test_01_scope_and_preservation_contract(self) -> None:
        self.assertEqual("a16-prototype-a-r1", self.config["id"])
        self.assertEqual(
            ["super.fex", "vbmeta_system.fex"], self.config["container"]["replacements"]
        )
        self.assertEqual(
            ["Vsuper.fex", "Vvbmeta_system.fex"], self.config["container"]["companions"]
        )
        self.assertEqual(46, self.config["container"]["preserved_entries"])
        self.assertEqual(1644019200, self.config["avb"]["rollback_index"])
        self.assertEqual(1, self.config["avb"]["rollback_index_location"])
        self.assertEqual("CONFIG_NFS_FS=y", self.config["known_vintf_exception"]["actual"])

    def test_02_integration_inputs_are_bounded(self) -> None:
        matrix = REPO / self.config["integration"]["device_matrix_relative"]
        root = ET.parse(matrix).getroot()
        names = [item.findtext("name") for item in root.findall("hal")]
        self.assertEqual(["vendor.display.config", "vendor.display.output"], names)
        patch = (REPO / self.config["integration"]["sepolicy_patch_relative"]).read_text(
            encoding="utf-8"
        )
        self.assertIn("-genfscon fuseblk / u:object_r:fuseblk:s0", patch)
        builder = (REPO / "scripts/build-a16-prototype-a-r1-candidate.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('linker_target.mkdir()', builder)
        for forbidden in (" fastboot ", " adb ", "phoenixcard", "sunxi-fel"):
            self.assertNotIn(forbidden, builder.lower())

    def test_03_vintf_exception_parser_ignores_informational_hal_paths(self) -> None:
        log = """[INFO] Fetch /vendor/etc/vintf/manifest/vendor.display.config@1.0.xml: OK
\x1b[31mERROR: files are incompatible: Runtime info is incompatible:
For kernel requirements at matrix level 6, Kernel config errors:
    For config CONFIG_NFS_FS, value = y but required n
: Success\x1b[0m
INCOMPATIBLE
"""
        self.assertTrue(BUILDER.is_expected_inherited_nfs_exception(log))
        self.assertFalse(
            BUILDER.is_expected_inherited_nfs_exception(
                log.replace("INCOMPATIBLE\n", "vendor.display.output missing\nINCOMPATIBLE\n")
            )
        )
        self.assertFalse(
            BUILDER.is_expected_inherited_nfs_exception(
                log.replace(
                    ": Success", "    For config CONFIG_USB, value = y but required n\n: Success"
                )
            )
        )

    def test_04_built_candidate_report_when_present(self) -> None:
        result_path = CANDIDATE / "build-result.json"
        if not result_path.exists():
            self.skipTest("ignored local a16-prototype-a-r1 candidate is absent")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        self.assertEqual("OFFLINE_CHECKED_CANDIDATE", result["status"])
        self.assertEqual("CLOSED", result["gate2"])
        self.assertTrue(result["eligible_for_one_uart_first_authorization"])
        self.assertFalse(result["physical_device_actions_performed"])
        self.assertFalse(result["flash_authorized"])
        self.assertEqual("PASS", result["compatibility"]["selinux_split_compile"])
        self.assertEqual("PASS", result["compatibility"]["linkerconfig"])
        self.assertEqual("EXPECTED_INHERITED_EXCEPTION", result["compatibility"]["full_vintf"])
        for logical in result["logical_after"].values():
            self.assertTrue(Path(logical["path"]).is_file())
        self.assertEqual(
            [
                "system_a",
                "super.fex",
                "Vsuper.fex",
                "vbmeta_system.fex",
                "Vvbmeta_system.fex",
            ],
            result["payload_delta"],
        )

        filesystem = json.loads(
            (CANDIDATE / "system-filesystem-diff.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            [
                "/system/etc/selinux/plat_sepolicy.cil",
                "/system/etc/vintf/compatibility_matrix.device.xml",
            ],
            filesystem["changed_paths"],
        )
        outer = json.loads((CANDIDATE / "outer-payload-audit.json").read_text(encoding="utf-8"))
        actions = {item["filename"]: item["action"] for item in outer["payloads"]}
        self.assertEqual(46, sum(value == "preserved" for value in actions.values()))
        self.assertEqual("replacement", actions["super.fex"])
        self.assertEqual("replacement", actions["vbmeta_system.fex"])
        self.assertEqual("companion", actions["Vsuper.fex"])
        self.assertEqual("companion", actions["Vvbmeta_system.fex"])


if __name__ == "__main__":
    unittest.main()
