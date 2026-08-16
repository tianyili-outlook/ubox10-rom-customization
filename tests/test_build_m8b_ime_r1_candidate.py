import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class M8BImeR1CandidateTest(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "configs/candidates/m8b-ime-r1.json").read_text(encoding="utf-8"))
        self.builder = (ROOT / "scripts/build-m8b-ime-r1-candidate.py").read_text(encoding="utf-8")

    def test_candidate_is_bounded_to_product(self):
        self.assertEqual(self.config["id"], "m8b-ime-r1")
        self.assertEqual(self.config["parent_config_relative"], "configs/candidates/m8b-audio-r2.json")
        self.assertEqual(self.config["container"]["replacements"], ["super.fex"])
        self.assertEqual(self.config["container"]["companions"], ["Vsuper.fex"])
        self.assertIn('["product_a", "super.fex", "Vsuper.fex"]', self.builder)
        self.assertIn('protected non-product logical partition changed', self.builder)

    def test_ime_provenance_and_normal_integration_are_locked(self):
        ime = self.config["ime"]
        self.assertEqual(ime["package"], "com.android.inputmethod.leanback")
        self.assertEqual(ime["source_commit"], "40b72d02ed2af7d1696cd8903682dcfcd963323c")
        self.assertEqual(ime["native_libraries"], 0)
        patch = (ROOT / ime["integration_patch_relative"]).read_text(encoding="utf-8")
        self.assertIn("PRODUCT_PACKAGES", patch)
        self.assertIn("LeanbackIME", patch)
        self.assertIn('normal_product_module_integration', self.builder)

    def test_runtime_property_and_remote_milestone_boundaries(self):
        prepare = (ROOT / "scripts/prepare-m8b-ime-r1-product.sh").read_text(encoding="utf-8")
        self.assertIn('base_root/etc/build.prop', prepare)
        self.assertNotIn("remote.service", self.builder.lower())
        self.assertNotIn("remote.service", json.dumps(self.config).lower())

    def test_built_candidate_when_present(self):
        result_path = ROOT / "out/candidates/m8b-ime-r1/build-result.json"
        if not result_path.is_file():
            self.skipTest("ignored local m8b-ime-r1 candidate is absent")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "OFFLINE CHECKED / DEVICE PERSISTENCE PENDING")
        self.assertEqual(result["payload_delta"], ["product_a", "super.fex", "Vsuper.fex"])
        self.assertEqual(result["protected_partitions_unchanged"], ["system_a", "vendor_a", "vendor_dlkm_a"])
        self.assertEqual(result["firmware"]["sha256"], "B89612D5004BA3D8214F21E22E4BED7BFBA5B2F8FE441F9364315F851F1FE240")
        self.assertEqual(result["product_a"]["sha256"], "6E2D0AF3E80DCCC488D73E1A7F483C96075E9F60588DDB7DCBBC42C64FCD8974")
        self.assertTrue(result["ime_product_validation"]["accepted_product_build_prop_preserved"])
        self.assertEqual(result["ime_product_validation"]["unexpected_paths"], [])
        before, after = result["logical_before"], result["logical_after"]
        for name in ("system_a", "vendor_a", "vendor_dlkm_a"):
            self.assertEqual(before[name]["sha256"], after[name]["sha256"])


if __name__ == "__main__":
    unittest.main()
