"""Final evidence locks for Android 16 Prototype B r1."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "configs/candidates/a16-prototype-b-r1.json"
RESULT = REPO / "docs/m8/candidates/a16-prototype-b-r1-offline-result.json"
PRESERVATION = REPO / "docs/m8/candidates/a16-prototype-b-r1-preservation.json"
FIRST_STAGE = REPO / "docs/m8/candidates/a16-prototype-b-r1-first-stage-audit.json"
CANDIDATE = REPO / "out/candidates/a16-prototype-b-r1/x12-a16-prototype-b-r1.img"
LOCAL_BUILD_RESULT = REPO / "out/candidates/a16-prototype-b-r1/build-result.json"
LOCAL_AUDIT = REPO / "out/candidates/a16-prototype-b-r1/offline-audit/offline-audit.json"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest().upper()


class A16PrototypeBR1CandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))
        cls.result = json.loads(RESULT.read_text(encoding="utf-8"))
        cls.preservation = json.loads(PRESERVATION.read_text(encoding="utf-8"))
        cls.first_stage = json.loads(FIRST_STAGE.read_text(encoding="utf-8"))

    def test_historical_offline_decision_has_no_physical_claim(self) -> None:
        self.assertEqual("a16-prototype-b-r1", self.result["candidate"])
        self.assertEqual(
            "OFFLINE_CHECKED_READY_FOR_PHYSICAL_VALIDATION", self.result["status"]
        )
        self.assertEqual(
            "OFFLINE CHECKED / READY FOR PHYSICAL VALIDATION", self.result["decision"]
        )
        self.assertEqual("NOT_YET_VALIDATED", self.result["physical_status"])
        self.assertFalse(self.result["physical_device_actions_performed"])
        self.assertFalse(self.result["flash_authorized"])

    def test_current_physical_failure_and_hold_are_locked(self) -> None:
        physical = self.first_stage["physical_result"]
        decision = self.first_stage["root_cause_decision"]
        self.assertEqual("a16-prototype-b-r1", self.first_stage["candidate"])
        self.assertEqual(
            "PHYSICAL_FAIL_SYSTEM_SWITCH_ROOT_METADATA_TARGET_MISSING",
            physical["status"],
        )
        self.assertFalse(physical["accepted"])
        self.assertFalse(physical["raw_uart_capture_present_locally"])
        self.assertIsNone(physical["raw_uart_sha256"])
        self.assertIn("second-stage init", physical["not_reached"])
        self.assertEqual(
            "PROVEN_B1_SYSTEM_ROOT_METADATA_MOVE_TARGET_ABSENT",
            decision["result"],
        )
        self.assertTrue(decision["r2_authorized"])
        self.assertTrue(decision["r2_created"])
        self.assertEqual(
            "ARTIFICIAL_BLOCKER_DIAGNOSTIC_BOOT_LACKED_SLOT_SUFFIX",
            physical["superseded_initial_diagnostic"]["status"],
        )
        roots = self.first_stage["signed_system_root_comparison"]
        self.assertEqual(7, len(roots["move_mountpoints"]))
        self.assertIsNone(roots["move_mountpoints"]["/metadata"]["r1"])
        self.assertEqual(
            "u:object_r:metadata_file:s0",
            roots["move_mountpoints"]["/metadata"]["r4"]["selinux"],
        )
        self.assertEqual("/system/metadata", roots["only_missing_r1_destination"])
        self.assertEqual(
            "PROVEN_PRODUCT_BOARDCONFIG_GENERATION_DELTA",
            roots["generation_provenance"]["result"],
        )

    def test_r4_first_stage_contract_is_exact_in_r1_package(self) -> None:
        comparison = self.first_stage["r4_r1_first_stage_payload_comparison"]
        for name in (
            "boot.fex",
            "Vboot.fex",
            "vendor_boot.fex",
            "Vvendor_boot.fex",
            "vendor_ramdisk",
            "vendor_boot_dtb",
            "sunxi.fex",
            "dtbo.fex",
            "Vdtbo.fex",
        ):
            self.assertTrue(comparison[name]["byte_identical"], name)
        contract = self.first_stage["accepted_first_stage_contract"]
        self.assertEqual(
            "first_stage_ramdisk/fstab.sun50iw9p1", contract["archive_path"]
        )
        self.assertEqual(
            "/fstab.sun50iw9p1",
            contract["runtime_path_after_force_normal_boot_switch_root"],
        )
        self.assertEqual(
            "6C771313A6F9DEDAEFA4061B14FE142F050F4AB13D360FF2F60FB9361277F701",
            contract["sha256"],
        )
        self.assertFalse(contract["r4_system_generated_root_fstab_present"])
        self.assertFalse(contract["r1_system_generated_root_fstab_present"])
        self.assertTrue(contract["r4_vendor_boot_fstab_present"])
        self.assertTrue(contract["r1_vendor_boot_fstab_present"])

    def test_no_first_stage_payload_was_in_r1_outer_delta(self) -> None:
        outer = self.first_stage["outer_integrity"]
        self.assertEqual("PASS_12_PARTITIONS_ZERO_MISMATCH", outer["r4_imagewty"])
        self.assertEqual("PASS_12_PARTITIONS_ZERO_MISMATCH", outer["r1_imagewty"])
        self.assertFalse(outer["first_stage_payload_in_changed_set"])
        self.assertEqual(
            sorted([
                "super.fex", "Vsuper.fex", "vbmeta_system.fex",
                "Vvbmeta_system.fex", "vbmeta_vendor.fex", "Vvbmeta_vendor.fex",
            ]),
            sorted(outer["r1_changed_outer_payloads"]),
        )

    def test_exact_outer_and_logical_artifacts_are_pinned(self) -> None:
        artifacts = self.result["artifacts"]
        self.assertEqual(1641752576, artifacts["candidate"]["size"])
        self.assertEqual(
            "796A2D46DB7FCDFF27D53397565ABDDC3D18F2E548A697055CE5E47278E69545",
            artifacts["candidate"]["sha256"],
        )
        self.assertEqual(1651167232, artifacts["system_a"]["size"])
        self.assertEqual(150994944, artifacts["vendor_a"]["size"])
        self.assertEqual(3221225472, artifacts["super_raw"]["size"])

    def test_storage_growth_is_only_old_sb_a_free_space(self) -> None:
        storage = self.result["storage"]
        self.assertEqual(31928320, storage["vendor_a_growth_bytes"])
        self.assertEqual(
            storage["sb_a_allocated_after_bytes"],
            storage["sb_a_allocated_before_bytes"] + storage["vendor_a_growth_bytes"],
        )
        self.assertEqual(
            storage["sb_a_unallocated_after_bytes"],
            storage["sb_a_unallocated_before_bytes"] - storage["vendor_a_growth_bytes"],
        )
        self.assertTrue(storage["growth_only_from_old_unallocated_space"])
        self.assertEqual(
            [[3227648, 3461120], [4007936, 4069376]],
            storage["candidate_extents_sectors_half_open"]["vendor_a"],
        )
        self.assertTrue(storage["all_b_slot_allocations_empty_exact"])
        self.assertTrue(storage["all_other_partition_extents_exact_r4"])
        self.assertTrue(storage["no_partition_shrunk"])

    def test_mixed_architecture_and_provider_closure(self) -> None:
        architecture = self.result["architecture"]
        self.assertEqual("PASS_MIXED_ARM64_PRIMARY_ARM32_SECONDARY", architecture["result"])
        self.assertEqual("zygote64_32", architecture["zygote"])
        self.assertEqual("arm64-v8a,armeabi-v7a,armeabi", architecture["abi_list"])
        self.assertEqual(3, len(self.result["providers"]))
        self.assertEqual(
            "PASS_297_STRONG_IMPORTS_ZERO_UNMATCHED",
            self.result["offline_gates"]["mali_symbol_closure"],
        )

    def test_all_offline_gates_and_strict_vintf_language(self) -> None:
        gates = self.result["offline_gates"]
        for name in (
            "filesystem_e2fsck", "avb", "lp_super", "imagewty", "elf_name_closure",
            "apex", "vndk31", "linkerconfig", "selinux", "kernel", "vendor_dlkm",
            "aic_fmac", "preservation",
        ):
            self.assertIn("PASS", gates[name])
        self.assertEqual(65, gates["full_vintf_exit"])
        self.assertEqual(
            "INCOMPATIBLE_EXPECTED_INHERITED_NFS_EXCEPTION_ONLY", gates["full_vintf"]
        )
        self.assertEqual(0, gates["unexpected_vintf_incompatibilities"])

    def test_preservation_inventory_is_bounded(self) -> None:
        preservation = self.preservation
        self.assertEqual("PASS", preservation["result"])
        self.assertFalse(preservation["kernel"]["rebuilt"])
        self.assertEqual(22, preservation["kernel"]["vendor_dlkm_modules"])
        self.assertEqual(6, preservation["outer"]["changed_count"])
        self.assertEqual(44, preservation["outer"]["preserved_count"])
        self.assertTrue(preservation["outer"]["all_unlisted_payloads_byte_preserved"])
        self.assertEqual("BYTE_PRESERVED", preservation["logical_partitions"]["product_a"])
        self.assertEqual(
            "BYTE_PRESERVED_22_MODULES",
            preservation["logical_partitions"]["vendor_dlkm_a"],
        )

    def test_local_ignored_candidate_matches_durable_record_when_present(self) -> None:
        if not CANDIDATE.is_file():
            self.skipTest("ignored candidate artifact is not present in this checkout")
        artifact = self.result["artifacts"]["candidate"]
        self.assertEqual(artifact["size"], CANDIDATE.stat().st_size)
        self.assertEqual(artifact["sha256"], digest(CANDIDATE))

    def test_local_audit_matches_final_record_when_present(self) -> None:
        if not LOCAL_BUILD_RESULT.is_file() or not LOCAL_AUDIT.is_file():
            self.skipTest("ignored build/audit evidence is not present in this checkout")
        build = json.loads(LOCAL_BUILD_RESULT.read_text(encoding="utf-8"))
        audit = json.loads(LOCAL_AUDIT.read_text(encoding="utf-8"))
        self.assertEqual("OFFLINE_CHECKED", build["status"])
        self.assertEqual(self.result["decision"], build["decision"])
        self.assertEqual(self.result["decision"], audit["decision"])
        self.assertEqual(
            self.result["artifacts"]["candidate"]["sha256"], build["firmware"]["sha256"]
        )
        self.assertFalse(audit["physical_device_actions_performed"])


if __name__ == "__main__":
    unittest.main()
