"""Single-cause and preservation locks for Android 16 Prototype B r2."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "configs/candidates/a16-prototype-b-r2.json"
RESULT = REPO / "docs/m8/candidates/a16-prototype-b-r2-offline-result.json"
PRESERVATION = REPO / "docs/m8/candidates/a16-prototype-b-r2-preservation.json"
CANDIDATE = REPO / "out/candidates/a16-prototype-b-r2/x12-a16-prototype-b-r2.img"
LOCAL_BUILD = REPO / "out/candidates/a16-prototype-b-r2/build-result.json"
LOCAL_AUDIT = REPO / "out/candidates/a16-prototype-b-r2/offline-audit/offline-audit.json"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest().upper()


class A16PrototypeBR2CandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))
        cls.result = json.loads(RESULT.read_text(encoding="utf-8"))
        cls.preservation = json.loads(PRESERVATION.read_text(encoding="utf-8"))

    def test_exact_single_cause_contract(self) -> None:
        self.assertEqual("a16-prototype-b-r2", self.config["id"])
        self.assertEqual(
            "PROVEN_B1_SYSTEM_ROOT_METADATA_MOVE_TARGET_ABSENT",
            self.config["root_cause"]["result"],
        )
        contract = self.config["root_mountpoint_contract"]
        self.assertEqual("/metadata", contract["path"])
        self.assertEqual("directory", contract["type"])
        self.assertEqual("0755", contract["mode"])
        self.assertEqual(0, contract["uid"])
        self.assertEqual(0, contract["gid"])
        self.assertEqual("u:object_r:metadata_file:s0", contract["selinux"])
        self.assertEqual("/metadata", contract["only_missing_r1_move_destination"])
        self.assertEqual(7, len(contract["required_move_mountpoints"]))
        self.assertEqual(1, len(self.config["allowed_semantic_delta"]))
        self.assertEqual(
            "PROVEN_PRODUCT_BOARDCONFIG_GENERATION_DELTA",
            self.config["root_cause"]["generation_provenance"]["result"],
        )

    def test_offline_result_and_artifact_identity(self) -> None:
        self.assertEqual("a16-prototype-b-r2", self.result["candidate"])
        self.assertEqual(
            "OFFLINE_CHECKED_READY_FOR_PHYSICAL_VALIDATION", self.result["status"]
        )
        self.assertEqual("NOT_YET_VALIDATED", self.result["physical_status"])
        self.assertFalse(self.result["physical_device_actions_performed"])
        self.assertFalse(self.result["flash_authorized"])
        artifact = self.result["artifacts"]["candidate"]
        self.assertEqual(1641756672, artifact["size"])
        self.assertEqual(
            "6FA8D13220DC9367659B5B16798664E906A390820359E72FD16063B84EC48887",
            artifact["sha256"],
        )

    def test_final_tree_delta_is_exactly_one_directory(self) -> None:
        delta = self.result["single_cause_delta"]
        self.assertEqual(["metadata"], delta["tree_added"])
        self.assertEqual([], delta["tree_removed"])
        self.assertEqual([], delta["tree_changed"])
        self.assertTrue(delta["r4_contract_exact"])
        self.assertTrue(delta["other_six_move_mountpoint_contracts_exact"])

    def test_avb_lp_outer_and_vintf_are_strict(self) -> None:
        gates = self.result["offline_gates"]
        for name in (
            "filesystem_e2fsck", "system_avb", "vendor_avb", "vbmeta_system",
            "vbmeta_vendor", "lp_geometry", "super_sparse_roundtrip", "imagewty",
            "apex", "vndk31", "linkerconfig", "mali_symbol_closure", "selinux",
            "system_vintf", "kernel", "vendor_dlkm", "aic_fmac",
            "root_mountpoint", "preservation",
        ):
            self.assertIn("PASS", gates[name], name)
        self.assertEqual(65, gates["full_vintf_exit"])
        self.assertEqual(
            "INCOMPATIBLE_EXPECTED_INHERITED_NFS_EXCEPTION_ONLY",
            gates["full_vintf"],
        )
        self.assertEqual(0, gates["unexpected_vintf_incompatibilities"])

    def test_preservation_is_relative_to_r1(self) -> None:
        preservation = self.preservation
        self.assertEqual("PASS", preservation["result"])
        self.assertEqual("BYTE_PRESERVED_FROM_R1", preservation["logical_partitions"]["vendor_a"])
        self.assertEqual("BYTE_PRESERVED_FROM_R1", preservation["logical_partitions"]["product_a"])
        self.assertEqual(4, preservation["outer"]["changed_count"])
        self.assertEqual(46, preservation["outer"]["preserved_count"])
        self.assertTrue(preservation["outer"]["vendor_boot_and_fstab_byte_preserved"])
        self.assertFalse(preservation["kernel"]["rebuilt"])
        self.assertEqual(22, preservation["kernel"]["vendor_dlkm_modules"])

    def test_local_ignored_artifacts_match_when_present(self) -> None:
        if not CANDIDATE.is_file() or not LOCAL_BUILD.is_file() or not LOCAL_AUDIT.is_file():
            self.skipTest("ignored r2 build/audit artifacts are not present")
        artifact = self.result["artifacts"]["candidate"]
        self.assertEqual(artifact["size"], CANDIDATE.stat().st_size)
        self.assertEqual(artifact["sha256"], digest(CANDIDATE))
        build = json.loads(LOCAL_BUILD.read_text(encoding="utf-8"))
        audit = json.loads(LOCAL_AUDIT.read_text(encoding="utf-8"))
        self.assertEqual("OFFLINE_CHECKED", build["status"])
        self.assertEqual(self.result["decision"], audit["decision"])
        root = audit["root_mountpoint"]
        self.assertEqual(
            "PASS_SINGLE_CAUSE_METADATA_ROOT_MOUNTPOINT_RESTORED", root["result"]
        )
        self.assertEqual(["metadata"], root["tree_delta_from_r1"]["added"])
        self.assertEqual([], root["tree_delta_from_r1"]["removed"])
        self.assertEqual([], root["tree_delta_from_r1"]["changed"])


if __name__ == "__main__":
    unittest.main()
