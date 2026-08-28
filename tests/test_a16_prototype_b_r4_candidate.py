import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PrototypeBR4ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = json.loads(
            (ROOT / "configs/candidates/a16-prototype-b-r4.json").read_text()
        )
        cls.product = (
            ROOT / "configs/aosp/architecture-ceiling-a16/device/ubox/ceiling/"
            "ubox10_ceiling_arm64.mk"
        ).read_text()
        cls.builder = (ROOT / "scripts/build-a16-prototype-b-r4-candidate.py").read_text()
        cls.auditor = (ROOT / "scripts/audit-a16-prototype-b-r4.py").read_text()
        cls.physical = json.loads(
            (ROOT / "docs/m8/candidates/a16-prototype-b-r3-physical-result.json").read_text()
        )
        cls.cause = json.loads(
            (ROOT / "docs/m8/candidates/a16-prototype-b-r3-abi-root-cause.json").read_text()
        )

    def test_r3_physical_failure_is_immutable_and_precise(self):
        self.assertIn("ZYGOTE64 ABI PROPERTY FAILURE", self.physical["decision"])
        self.assertEqual(self.physical["r3_single_cause_vendor_fix"], "PHYSICAL_PASS")
        self.assertEqual(
            self.physical["zygote64_failure"]["abort_message"],
            "app_process: Unable to determine ABI list from property ro.product.cpu.abilist64.",
        )
        self.assertEqual(
            self.physical["graphics_failure"]["abort_message"], "gralloc-mapper is missing"
        )

    def test_abi_root_cause_matches_all_live_properties(self):
        self.assertTrue(self.cause["causal_evaluation"]["matches_physical_runtime_exactly"])
        self.assertEqual(self.cause["causal_evaluation"]["odm"]["selected"], True)
        self.assertEqual(
            self.cause["causal_evaluation"]["derived_global"]["ro.product.cpu.abilist64"], ""
        )
        self.assertEqual(
            self.cause["r4_authorization"],
            "AUTHORIZED_SINGLE_CAUSE_PRODUCT_SCOPED_ABI_PROPERTY_GENERATION",
        )

    def test_source_delta_is_exact_product_scoped_triplet(self):
        props = self.cfg["generated_product_property_contract"]["properties"]
        self.assertEqual(
            props,
            {
                "ro.product.product.cpu.abilist": "arm64-v8a,armeabi-v7a,armeabi",
                "ro.product.product.cpu.abilist32": "armeabi-v7a,armeabi",
                "ro.product.product.cpu.abilist64": "arm64-v8a",
            },
        )
        for name, value in props.items():
            self.assertEqual(self.product.count(f"{name}={value}"), 1)
        self.assertNotIn("ro.product.cpu.abilist64=", self.product)
        self.assertNotIn("setprop", self.product)

    def test_builder_is_product_only_and_fail_closed(self):
        self.assertIn("generated_lines.count(line) != 1", self.builder)
        self.assertIn("product build.prop delta expanded", self.builder)
        self.assertIn("r4 changed LP metadata/geometry", self.builder)
        self.assertEqual(
            sorted(self.cfg["outer_delta"]["changed_payloads_from_base"]),
            ["Vsuper.fex", "super.fex"],
        )
        for forbidden in ("system_a", "vendor_a", "boot_or_vendor_boot", "Mali_mapper_gralloc"):
            self.assertIn(forbidden, self.cfg["forbidden_changes"])

    def test_auditor_preserves_graphics_and_full_vintf_discipline(self):
        self.assertIn("graphics_providers", self.auditor)
        self.assertIn("BYTE_PRESERVED_FROM_PHYSICALLY_FAILED_R3", self.auditor)
        self.assertIn("product AVB contract missing", self.auditor)
        self.assertIn("global_abi_derivation_offline", self.auditor)

    def test_artifact_contract_when_present(self):
        result_path = ROOT / "docs/m8/candidates/a16-prototype-b-r4-offline-result.json"
        candidate = ROOT / "out/candidates/a16-prototype-b-r4"
        if not result_path.exists() or not candidate.exists():
            self.skipTest("r4 build fixture not present yet")
        result = json.loads(result_path.read_text())
        self.assertEqual(result["decision"], "OFFLINE CHECKED / READY FOR PHYSICAL VALIDATION")
        self.assertEqual(result["physical_status"], "NOT_YET_VALIDATED")
        self.assertNotEqual(result["full_vintf"], "PASS")


if __name__ == "__main__":
    unittest.main()
