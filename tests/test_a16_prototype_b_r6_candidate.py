"""First-fatal and one-file preservation locks for Prototype B r6."""
from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/candidates/a16-prototype-b-r6.json"
PHYSICAL = ROOT / "docs/m8/candidates/a16-prototype-b-r5-physical-result.json"
CAUSE = ROOT / "docs/m8/candidates/a16-prototype-b-r6-boringssl-root-cause-audit.json"
CENSUS = ROOT / "docs/m8/candidates/a16-prototype-b-r6-arm64-service-readiness-census.json"
TEE = ROOT / "docs/m8/candidates/a16-prototype-b-r6-tee-module-read-only-audit.json"
PRNG = ROOT / "docs/m8/candidates/a16-prototype-b-r6-prng-hwrng-read-only-audit.json"


class PrototypeBR6ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
        cls.physical = json.loads(PHYSICAL.read_text(encoding="utf-8"))
        cls.cause = json.loads(CAUSE.read_text(encoding="utf-8"))
        cls.census = json.loads(CENSUS.read_text(encoding="utf-8"))
        cls.tee = json.loads(TEE.read_text(encoding="utf-8"))
        cls.prng = json.loads(PRNG.read_text(encoding="utf-8"))
        cls.builder = (
            ROOT / "scripts/build-a16-prototype-b-r6-candidate.py"
        ).read_text(encoding="utf-8")

    def test_r5_mixed_abi_is_an_immutable_physical_pass(self) -> None:
        abi = self.physical["abi_correction"]
        self.assertEqual("PHYSICAL_PASS", abi["global_mixed_abi"])
        self.assertEqual("arm64-v8a", abi["runtime_values"]["ro.product.cpu.abilist64"])
        self.assertEqual(
            "CLOSED_PHYSICALLY_NO_LONGER_FIRST_BLOCKER",
            abi["old_app_process64_empty_abilist64_blocker"],
        )

    def test_r5_first_fatal_is_missing_executable_not_crypto_failure(self) -> None:
        vendor = self.physical["boringssl_vendor"]
        self.assertEqual(0, vendor["self_test32"]["exit_status"])
        self.assertEqual(
            "FIRST_FATAL_MISSING_EXECUTABLE", vendor["self_test64"]["physical_result"]
        )
        self.assertFalse(self.physical["causal_limits"]["cryptographic_algorithm_self_test_failure_proven"])
        self.assertFalse(self.physical["causal_limits"]["linker_failure_proven"])

    def test_root_cause_uniquely_authorizes_one_file(self) -> None:
        self.assertTrue(self.cause["r6_decision"]["authorized"])
        self.assertEqual(
            ["/vendor/bin/boringssl_self_test64"],
            self.cause["r6_decision"]["allowed_functional_delta"],
        )
        self.assertEqual([], self.cause["dependency_closure"]["direct_new_dependencies_required"])
        self.assertEqual(0, self.cause["canonical_arm64_executable"]["strong_unmatched_count"])

    def test_config_pins_exact_canonical_vendor_binary(self) -> None:
        contract = self.cfg["boringssl64_contract"]
        self.assertEqual(14280, contract["size"])
        self.assertEqual(
            "E8F3B67A7BADC94FE034A74F5C59F085138D5D8E38A27CF3ADEB676AE60C058F",
            contract["sha256"],
        )
        self.assertEqual("ELF64", contract["elf_class"])
        self.assertEqual("AArch64", contract["machine"])
        self.assertFalse(self.cfg["retained_vendor_contract"]["new_vendor_libcrypto_allowed"])
        self.assertIn("vendor_libcrypto", self.cfg["forbidden_changes"])
        self.assertEqual(
            ["/vendor/bin/boringssl_self_test64"],
            self.cfg["elf_census_contract"]["approved_additional_vendor64"],
        )

    def test_builder_fails_closed_on_rc_32_and_libcrypto(self) -> None:
        for lock in (
            "r6 root-cause authorization is not uniquely closed",
            "canonical r7 BoringSSL64 ELF contract changed",
            "r5 unexpectedly contains a standalone vendor libcrypto64",
            "installed vendor BoringSSL64 inode contract changed",
            "r6 changed exact r5 LP metadata or extents",
            "unexpected r6 outer payload delta",
        ):
            self.assertIn(lock, self.builder)
        self.assertIn("ea_get {target} security.selinux", self.builder)
        self.assertIn('vbmeta_vendor = self.make_vbmeta(vendor, "vendor")', self.builder)

    def test_shared_elf_census_allows_only_the_r6_pinned_addition(self) -> None:
        auditor = (ROOT / "scripts/audit-a16-prototype-b-r1.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('continuation.get("elf_census_contract", {})', auditor)
        self.assertIn("approved_additional_vendor64", auditor)
        self.assertIn('row["path"] not in approved_additional_vendor64', auditor)
        self.assertIn('"vendor_aarch64_services": len(approved_additional_vendor64)', auditor)
        self.assertIn('f"ea_get {path} security.selinux"', auditor)
        r6_auditor = (ROOT / "scripts/audit-a16-prototype-b-r6.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("self.r5_vendor_mount.mkdir(parents=True, exist_ok=True)", r6_auditor)

    def test_arm64_census_is_prediction_only(self) -> None:
        self.assertEqual(
            "PREDICTION_ONLY_NO_ADDITIONAL_R6_REMEDIATION_AUTHORIZED",
            self.census["scope"],
        )
        self.assertFalse(self.census["summary"]["additional_r6_fix_authorized"])
        services = {item["service"]: item for item in self.census["services"]}
        self.assertEqual("MISSING_BINARY", services["boringssl_self_test64_vendor"]["offline_readiness"])
        self.assertEqual("READY_OFFLINE", services["boringssl_self_test64"]["offline_readiness"])
        self.assertIn("gralloc", services["surfaceflinger"]["physical_status"].lower())

    def test_tee_and_prng_remain_read_only_nonfatal_audits(self) -> None:
        self.assertEqual(
            "REAL_STALE_INSMOD_PATHS_NON_FATAL_AS_OF_R5_READ_ONLY",
            self.tee["classification"],
        )
        self.assertEqual("y", self.tee["frozen_kernel_config"]["CONFIG_OPTEE"])
        self.assertFalse(self.tee["causal_limits"]["r6_prerequisite"])
        self.assertEqual(
            "REAL_HWRNG_SEEDING_LOSS_NON_FATAL_AS_OF_R5_READ_ONLY_ROOT_CAUSE_NOT_UNIQUE",
            self.prng["classification"],
        )
        self.assertFalse(self.prng["impact"]["r6_prerequisite"])
        self.assertFalse(self.prng["impact"]["kernel_csprng_unavailable_proven"])

    def test_local_candidate_contract_when_present(self) -> None:
        result = ROOT / "docs/m8/candidates/a16-prototype-b-r6-offline-result.json"
        local = ROOT / "out/candidates/a16-prototype-b-r6/build-result.json"
        if not result.is_file() or not local.is_file():
            self.skipTest("r6 offline artifacts are not present yet")
        documented = json.loads(result.read_text(encoding="utf-8"))
        built = json.loads(local.read_text(encoding="utf-8"))
        self.assertEqual("OFFLINE CHECKED / READY FOR PHYSICAL VALIDATION", documented["decision"])
        self.assertEqual("NOT_YET_VALIDATED", documented["physical_status"])
        self.assertEqual("OFFLINE_CHECKED", built["status"])
        self.assertEqual(65, documented["offline_gates"]["full_vintf_exit"])
        self.assertNotEqual("PASS", documented["offline_gates"]["full_vintf"])


if __name__ == "__main__":
    unittest.main()
