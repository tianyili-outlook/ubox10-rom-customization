"""Single-cause and preservation locks for Android 16 Prototype B r3."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "configs/candidates/a16-prototype-b-r3.json"
ROOT_AUDIT = REPO / "docs/m8/candidates/a16-prototype-b-r2-root-layout-audit.json"
RESULT = REPO / "docs/m8/candidates/a16-prototype-b-r3-offline-result.json"
PRESERVATION = REPO / "docs/m8/candidates/a16-prototype-b-r3-preservation.json"
CANDIDATE = REPO / "out/candidates/a16-prototype-b-r3/x12-a16-prototype-b-r3.img"
LOCAL_BUILD = REPO / "out/candidates/a16-prototype-b-r3/build-result.json"
LOCAL_AUDIT = REPO / "out/candidates/a16-prototype-b-r3/offline-audit/offline-audit.json"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest().upper()


class A16PrototypeBR3CandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))
        cls.root = json.loads(ROOT_AUDIT.read_text(encoding="utf-8"))
        cls.result = json.loads(RESULT.read_text(encoding="utf-8"))
        cls.preservation = json.loads(PRESERVATION.read_text(encoding="utf-8"))

    def test_exact_root_cause_and_authorization(self) -> None:
        self.assertEqual("a16-prototype-b-r3", self.config["id"])
        self.assertEqual(
            "PROVEN_PROTOTYPE_B_R2_SYSTEM_ROOT_VENDOR_MOUNTPOINT_NON_CANONICAL",
            self.config["root_cause"]["result"],
        )
        self.assertEqual(
            "PROVEN_MISSING_SEPARATE_VENDOR_BOARDCONFIG_CONTRACT",
            self.root["generation_provenance"]["result"],
        )
        self.assertEqual(
            "1d37c4499249b17f143df12cebc5ee9ea3600ce3",
            self.root["android12_source_corroboration"]["system_core_commit"],
        )
        self.assertEqual("PHYSICAL_PASS", self.config["root_cause"]["r2_physical_result"]["metadata_single_cause_fix"])
        self.assertTrue(self.root["decision"]["r3_authorized"])

    def test_r4_r2_vendor_and_peer_contracts(self) -> None:
        vendor = self.root["root_object_comparison"]["/vendor"]
        self.assertEqual("directory", vendor["r4"]["type"])
        self.assertEqual(2000, vendor["r4"]["gid"])
        self.assertEqual("symlink", vendor["r2"]["type"])
        self.assertEqual("/system/vendor", vendor["r2"]["target"])
        for path in ("/product", "/odm", "/system_ext", "/metadata", "/vendor_dlkm", "/oem"):
            item = self.root["root_object_comparison"][path]
            for field in ("type", "target", "mode", "uid", "gid", "selinux"):
                self.assertEqual(item["r4"][field], item["r2"][field], (path, field))
        self.assertEqual(
            ["/oem", "/product", "/system_ext", "/oem/*", "/product/*", "/system_ext/*", "/system/*"],
            self.root["gsi_skip_mount"]["patterns"],
        )

    def test_offline_result_and_exact_tree_delta(self) -> None:
        self.assertEqual("a16-prototype-b-r3", self.result["candidate"])
        self.assertEqual("OFFLINE_CHECKED_READY_FOR_PHYSICAL_VALIDATION", self.result["status"])
        self.assertEqual("NOT_YET_VALIDATED", self.result["physical_status"])
        self.assertFalse(self.result["physical_device_actions_performed"])
        self.assertEqual([], self.result["single_cause_delta"]["tree_added"])
        self.assertEqual([], self.result["single_cause_delta"]["tree_removed"])
        self.assertEqual(["vendor"], self.result["single_cause_delta"]["tree_changed"])
        artifact = self.result["artifacts"]["candidate"]
        self.assertEqual(1641760768, artifact["size"])
        self.assertEqual(
            "7948D1B9AE4DC9E7B61EEF39876145BFCB4E6966FC12BC82925583477E5CB9D2",
            artifact["sha256"],
        )

    def test_offline_gates_are_strict(self) -> None:
        gates = self.result["offline_gates"]
        for name in (
            "filesystem_e2fsck", "system_avb", "vendor_avb", "vbmeta_system",
            "vbmeta_vendor", "lp_geometry", "super_sparse_roundtrip", "imagewty",
            "apex", "vndk31", "linkerconfig", "mali_symbol_closure", "selinux",
            "system_vintf", "kernel", "vendor_dlkm", "aic_fmac", "root_mountpoint",
            "preservation",
        ):
            self.assertIn("PASS", gates[name], name)
        self.assertEqual(65, gates["full_vintf_exit"])
        self.assertEqual(
            "INCOMPATIBLE_EXPECTED_INHERITED_NFS_EXCEPTION_ONLY", gates["full_vintf"]
        )

    def test_preservation_is_relative_to_r2(self) -> None:
        self.assertEqual("PASS", self.preservation["result"])
        self.assertEqual("BYTE_PRESERVED_FROM_R2", self.preservation["logical_partitions"]["vendor_a"])
        self.assertEqual("BYTE_PRESERVED_FROM_R2", self.preservation["logical_partitions"]["product_a"])
        self.assertEqual(4, self.preservation["outer"]["changed_count"])
        self.assertEqual(46, self.preservation["outer"]["preserved_count"])
        self.assertTrue(self.preservation["outer"]["vendor_boot_and_fstab_byte_preserved"])
        self.assertFalse(self.preservation["kernel"]["rebuilt"])
        self.assertEqual(22, self.preservation["kernel"]["vendor_dlkm_modules"])

    def test_local_ignored_artifacts_match_when_present(self) -> None:
        if not CANDIDATE.is_file() or not LOCAL_BUILD.is_file() or not LOCAL_AUDIT.is_file():
            self.skipTest("ignored r3 build/audit artifacts are not present")
        artifact = self.result["artifacts"]["candidate"]
        self.assertEqual(artifact["size"], CANDIDATE.stat().st_size)
        self.assertEqual(artifact["sha256"], digest(CANDIDATE))
        build = json.loads(LOCAL_BUILD.read_text(encoding="utf-8"))
        audit = json.loads(LOCAL_AUDIT.read_text(encoding="utf-8"))
        self.assertEqual("OFFLINE_CHECKED", build["status"])
        self.assertEqual(self.result["decision"], audit["decision"])
        root = audit["root_mountpoint"]
        self.assertEqual("PASS_SINGLE_CAUSE_VENDOR_ROOT_MOUNTPOINT_RESTORED", root["result"])
        self.assertEqual([], root["tree_delta_from_r2"]["added"])
        self.assertEqual([], root["tree_delta_from_r2"]["removed"])
        self.assertEqual(["vendor"], root["tree_delta_from_r2"]["changed"])
        self.assertEqual(root["vendor_contract"]["r4"], root["vendor_contract"]["r3"])


if __name__ == "__main__":
    unittest.main()
