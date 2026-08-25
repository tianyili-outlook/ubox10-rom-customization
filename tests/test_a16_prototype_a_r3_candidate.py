"""Focused guardrails for the Android 16 QPR0 Prototype A r3 candidate."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET


REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "configs/candidates/a16-prototype-a-r3.json"
PATH_A = REPO / "configs/kernel/m8-kernel-5.4.302/path-a-delta.json"
PRESERVATION = REPO / "configs/kernel/m8-kernel-5.4.302/preservation-5.4.302.config"
PATH_A_CONFIG = REPO / "configs/kernel/m8-kernel-5.4.302/path-a-5.4.302.config"
CANDIDATE = REPO / "out/candidates/a16-prototype-a-r3"


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest().upper()


class A16PrototypeAR3ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))

    def test_exact_r7_arm32_product_contract(self) -> None:
        android = self.config["android16"]
        self.assertEqual("a16-prototype-a-r3", self.config["id"])
        self.assertEqual("android-security-16.0.0_r7", android["source_tag"])
        self.assertEqual(
            "ebea28d151539ecf0730b1a4ab92ac33edc17ac9",
            android["manifest_commit"],
        )
        self.assertEqual("BP2A.250805.034", android["build_id"])
        self.assertEqual("bp2a", android["release"])
        product = (
            REPO
            / "configs/aosp/architecture-ceiling-a16/device/ubox/ceiling/ubox10_ceiling_arm.mk"
        ).read_text(encoding="utf-8")
        for fragment in (
            "device/google/atv/products/gsi_tv_base.mk",
            "PRODUCT_SHIPPING_API_LEVEL := 31",
            "PRODUCT_EXTRA_VNDK_VERSIONS := 31",
            "PRODUCT_BUILD_PVMFW_IMAGE := false",
        ):
            self.assertIn(fragment, product)
        lunch = (
            REPO
            / "configs/aosp/architecture-ceiling-a16/device/ubox/ceiling/AndroidProducts.mk"
        ).read_text(encoding="utf-8")
        self.assertIn("ubox10_ceiling_arm-bp2a-userdebug", lunch)

    def test_system_deltas_remain_exactly_bounded(self) -> None:
        matrix_path = (
            REPO
            / "configs/aosp/architecture-ceiling-a16/device/ubox/ceiling/compatibility_matrix.xml"
        )
        root = ET.parse(matrix_path).getroot()
        names = [item.findtext("name") for item in root.findall("hal")]
        self.assertEqual(["vendor.display.config", "vendor.display.output"], names)
        patch = (
            REPO
            / "configs/aosp/architecture-ceiling-a16/patches/0002-sepolicy-defer-fuseblk-label-to-api31-vendor.patch"
        ).read_text(encoding="utf-8")
        added = [line for line in patch.splitlines() if line.startswith("+") and not line.startswith("+++")]
        removed = [line for line in patch.splitlines() if line.startswith("-genfscon ")]
        self.assertEqual([], added)
        self.assertEqual(["-genfscon fuseblk / u:object_r:fuseblk:s0"], removed)

    def test_path_a_is_exactly_the_six_required_additions(self) -> None:
        delta = json.loads(PATH_A.read_text(encoding="utf-8"))
        enabled = {name for name, (_before, after) in delta.items() if after == "y"}
        self.assertEqual(
            {
                "CONFIG_BLK_CGROUP",
                "CONFIG_CPUSETS",
                "CONFIG_PROC_PID_CPUSET",
                "CONFIG_NET_CLS_MATCHALL",
                "CONFIG_NET_ACT_POLICE",
                "CONFIG_NET_ACT_BPF",
            },
            enabled,
        )
        config_text = PATH_A_CONFIG.read_text()
        for forbidden in ("CONFIG_MEMCG", "CONFIG_DEBUG_INFO_BTF", "CONFIG_INCFS_FS"):
            self.assertNotIn(f"{forbidden}=y", config_text)
        self.assertNotEqual(sha256(PRESERVATION), sha256(PATH_A_CONFIG))

    def test_build_and_audit_tools_have_no_physical_action_path(self) -> None:
        sources = "\n".join(
            (REPO / relative).read_text(encoding="utf-8").lower()
            for relative in (
                "scripts/build-a16-prototype-a-r3-candidate.py",
                "scripts/audit-a16-prototype-a-r3.py",
                "scripts/audit-m8-kernel-54302-path-a.py",
            )
        )
        for forbidden in (
            "fastboot flash", "adb reboot", "phoenixcard", "sunxi-fel",
            "shutdown -h", "systemctl poweroff",
        ):
            self.assertNotIn(forbidden, sources)
        self.assertIn("--treblelize", sources)
        self.assertIn('"flash_authorized": false', sources)

    def test_local_offline_checked_candidate_when_present(self) -> None:
        result_path = CANDIDATE / "build-result.json"
        audit_path = CANDIDATE / "offline-audit/offline-audit.json"
        if not result_path.is_file() or not audit_path.is_file():
            self.skipTest("ignored local a16-prototype-a-r3 candidate is absent")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        expected = self.config["expected_result"]
        self.assertEqual("OFFLINE_CHECKED", result["status"])
        self.assertEqual(expected["decision"], result["decision"])
        self.assertFalse(result["physical_device_actions_performed"])
        self.assertFalse(result["flash_authorized"])
        self.assertEqual(
            "UNBLOCKED_AWAITING_EXPLICIT_PHYSICAL_VALIDATION_DECISION",
            result["gate2"],
        )
        for label, relative in (
            ("firmware", "x12-a16-prototype-a-r3.img"),
            ("system", "system_a.img"),
            ("boot", "boot.fex"),
            ("vendor_dlkm", "vendor_dlkm_a.img"),
            ("super", "super.fex"),
            ("vbmeta_system", "vbmeta_system.fex"),
        ):
            path = CANDIDATE / relative
            self.assertEqual(expected[label]["size"], path.stat().st_size)
            self.assertEqual(expected[label]["sha256"], sha256(path))
        self.assertEqual(expected["offline_audit"]["sha256"], sha256(audit_path))
        self.assertEqual(
            "INCOMPATIBLE_EXPECTED_INHERITED_NFS_EXCEPTION_ONLY",
            audit["compatibility"]["full_vintf"],
        )
        self.assertEqual(65, audit["compatibility"]["full_vintf_exit"])
        self.assertEqual(0, audit["elf_abi"]["aarch64_userspace_consumers"])
        self.assertEqual("none", audit["elf_abi"]["secondary_architecture"])
        self.assertEqual("zygote32", audit["elf_abi"]["zygote"])
        self.assertEqual("path-a", audit["kernel"]["config_contract"])
        self.assertEqual(
            "PASS_PATH_A_R5_HARDWARE_AND_FMAC_CONTRACT",
            audit["kernel"]["hardware_and_fmac_addendum"]["result"],
        )
        self.assertEqual(44, result["outer"]["preserved_payload_count"])
        self.assertTrue(result["outer"]["all_other_payload_bytes_exact"])
        self.assertTrue(result["super"]["bytes_outside_system_and_vendor_dlkm_extents_exact"])


if __name__ == "__main__":
    unittest.main()
