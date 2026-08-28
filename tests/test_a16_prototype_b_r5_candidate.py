"""Runtime product-source and bounded-candidate locks for Prototype B r5."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/candidates/a16-prototype-b-r5.json"
PHYSICAL = ROOT / "docs/m8/candidates/a16-prototype-b-r4-physical-result.json"
SOURCE_AUDIT = ROOT / "docs/m8/candidates/a16-prototype-b-r4-runtime-product-source-audit.json"
CHECK_PATH = ROOT / "scripts/check-a16-prototype-b-runtime-product-source.py"
SPEC = importlib.util.spec_from_file_location("runtime_product_source_test", CHECK_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import checker: {CHECK_PATH}")
CHECK = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CHECK
SPEC.loader.exec_module(CHECK)


class PrototypeBR5ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
        cls.physical = json.loads(PHYSICAL.read_text(encoding="utf-8"))
        cls.audit = json.loads(SOURCE_AUDIT.read_text(encoding="utf-8"))
        cls.builder = (
            ROOT / "scripts/build-a16-prototype-b-r5-candidate.py"
        ).read_text(encoding="utf-8")

    def test_r4_failure_is_immutable_and_precise(self) -> None:
        self.assertEqual("a16-prototype-b-r4", self.physical["candidate"])
        self.assertEqual(
            "PATCHED_INACTIVE_PRODUCT_A_RUNTIME_SOURCE_IS_SYSTEM_EMBEDDED_PRODUCT",
            self.physical["classification"],
        )
        self.assertEqual(
            "/system/product",
            self.physical["runtime_product_layout"]["/product"]["readlink_f"],
        )
        self.assertFalse(
            self.physical["runtime_product_layout"]["logical_product_mapping"]
            ["mounted_as_runtime_product"]
        )
        self.assertEqual(
            "app_process: Unable to determine ABI list from property ro.product.cpu.abilist64.",
            self.physical["zygote64_failure"]["abort_message"],
        )

    def test_root_cause_and_r5_authorization_are_evidence_backed(self) -> None:
        self.assertEqual(
            "PROVEN_PATCHED_INACTIVE_LOGICAL_PRODUCT_A_RUNTIME_SOURCE_IS_EMBEDDED_SYSTEM_PRODUCT",
            self.audit["result"],
        )
        self.assertEqual("system/product", self.audit["build_generation_contract"]["target_copy_out_product"])
        self.assertTrue(self.audit["r5_decision"]["authorized"])
        self.assertEqual(
            "UNIQUE_PROVEN_WRONG_ASSEMBLY_TARGET_INACTIVE_LOGICAL_PRODUCT_A",
            self.audit["r5_decision"]["root_cause"],
        )
        self.assertEqual(
            "THE_PATCHED_PARTITION_AND_FILE_MUST_EQUAL_THE_RUNTIME_RESOLVED_PROPERTY_SOURCE_UNDER_THE_RETAINED_FIRST_STAGE_LAYOUT",
            self.audit["why_r4_offline_audit_missed_runtime_failure"]["missing_invariant"],
        )

    def test_r5_is_single_active_source_delta(self) -> None:
        self.assertEqual("a16-prototype-b-r5", self.cfg["id"])
        self.assertEqual("/system/product/etc/build.prop", self.cfg["active_product_property_contract"]["active_path"])
        self.assertEqual("RESTORE_EXACT_R3_BYTES", self.cfg["inactive_product_contract"]["treatment"])
        self.assertEqual(
            "6E2D0AF3E80DCCC488D73E1A7F483C96075E9F60588DDB7DCBBC42C64FCD8974",
            self.cfg["base_artifacts"]["product_a"]["sha256"],
        )
        self.assertIn("runtime_setprop_or_init_workaround", self.cfg["forbidden_changes"])
        self.assertIn("Mali_mapper_gralloc", self.cfg["forbidden_changes"])
        self.assertIn('cat {contract["active_path"]}', self.builder)
        self.assertNotIn("/etc/init", self.cfg["allowed_semantic_delta"][0])

    def test_dumpvars_parser_and_final_variable_equality(self) -> None:
        text = "\n".join([
            "TARGET_ARCH='arm64'",
            "TARGET_2ND_ARCH='arm'",
            "TARGET_CPU_ABI_LIST='arm64-v8a,armeabi-v7a,armeabi'",
            "TARGET_CPU_ABI_LIST_32_BIT='armeabi-v7a,armeabi'",
            "TARGET_CPU_ABI_LIST_64_BIT='arm64-v8a'",
            "TARGET_COPY_OUT_PRODUCT='system/product'",
            "PRODUCT_OUT='out-ceiling-b1/target/product/ubox10_ceiling_arm64'",
        ])
        variables = CHECK.parse_dumpvars(text)
        expected = CHECK.expected_from_build_variables(
            self.cfg["active_product_property_contract"], variables
        )
        self.assertEqual(
            "arm64-v8a,armeabi-v7a,armeabi",
            expected["ro.product.product.cpu.abilist"],
        )
        with self.assertRaises(RuntimeError):
            CHECK.parse_dumpvars("TARGET_ARCH='arm64'\n")

    def test_runtime_source_checker_fails_closed_on_all_required_invariants(self) -> None:
        checker = CHECK_PATH.read_text(encoding="utf-8")
        for lock in (
            "signed system root /product is not the locked runtime alias",
            "signed skip_mount.cfg no longer removes standalone /product",
            "inactive logical product_a still carries the ABI triplet",
            "configured ABI triplet diverges from final build variables",
            "runtime-active embedded product property source is not canonical",
            "generated product path is not TARGET_OUT_PRODUCT",
        ):
            self.assertIn(lock, checker)

    def test_local_artifact_contract_when_present(self) -> None:
        result = ROOT / "docs/m8/candidates/a16-prototype-b-r5-offline-result.json"
        candidate = ROOT / "out/candidates/a16-prototype-b-r5/build-result.json"
        if not result.is_file() or not candidate.is_file():
            self.skipTest("r5 offline artifacts are not present yet")
        documented = json.loads(result.read_text(encoding="utf-8"))
        local = json.loads(candidate.read_text(encoding="utf-8"))
        self.assertEqual("OFFLINE CHECKED / READY FOR PHYSICAL VALIDATION", documented["decision"])
        self.assertEqual("OFFLINE_CHECKED", local["status"])
        self.assertEqual("NOT_YET_VALIDATED", documented["physical_status"])
        self.assertEqual(65, documented["offline_gates"]["full_vintf_exit"])
        self.assertNotEqual("PASS", documented["offline_gates"]["full_vintf"])


if __name__ == "__main__":
    unittest.main()
