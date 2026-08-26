"""Focused guardrails for the bounded Android 16 Prototype A r4 candidate."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "configs/candidates/a16-prototype-a-r4.json"
DEVICE = REPO / "configs/aosp/architecture-ceiling-a16/device/ubox/ceiling"
PRODUCT = DEVICE / "ubox10_ceiling_arm.mk"
LAYOUT = DEVICE / "sunxi-ir.kl"
GENERIC = Path("/work/src/ubox10-a16-ceiling/frameworks/base/data/keyboards/Generic.kl")
CANDIDATE = REPO / "out/candidates/a16-prototype-a-r4"


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest().upper()


class A16PrototypeAR4ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))

    def test_identity_and_two_functional_deltas_are_exact(self) -> None:
        self.assertEqual("a16-prototype-a-r4", self.config["id"])
        self.assertEqual("a16-prototype-a-r3", Path(self.config["base_candidate"]["path"]).parent.name)
        self.assertEqual("UBOX10_A16_QPR0_R4", self.config["android16"]["build_number"])
        self.assertEqual(
            [
                "ro.hardware.egl=mali in the source-generated system build.prop; ro.board.platform=apollo remains in accepted vendor",
                "device-specific sunxi-ir.kl equal to r7 Generic.kl except scanCode 352 maps to DPAD_CENTER",
            ],
            self.config["functional_delta"],
        )

    def test_egl_property_is_source_integrated_without_diagnostic_override(self) -> None:
        product = PRODUCT.read_text(encoding="utf-8")
        self.assertEqual(1, product.count("ro.hardware.egl=mali"))
        self.assertNotIn("ro.board.platform=mali", product)
        non_comments = "\n".join(
            line for line in product.splitlines() if not line.lstrip().startswith("#")
        )
        self.assertNotIn("persist.graphics.egl=mali", non_comments)
        self.assertIn(
            "device/ubox/ceiling/sunxi-ir.kl:system/usr/keylayout/sunxi-ir.kl",
            product,
        )
        allowed = [
            line.strip().rstrip("\\").strip()
            for line in product.splitlines()
            if line.strip().startswith("system/usr/keylayout/")
        ]
        self.assertEqual(["system/usr/keylayout/sunxi-ir.kl"], allowed)

    def test_sunxi_layout_is_generic_plus_only_scan_352_dpad_center(self) -> None:
        self.assertTrue(GENERIC.is_file(), f"missing exact r7 Generic.kl: {GENERIC}")
        generic = GENERIC.read_text(encoding="utf-8").splitlines()
        layout = LAYOUT.read_text(encoding="utf-8").splitlines()
        differences = [
            (index, before, after)
            for index, (before, after) in enumerate(zip(generic, layout), start=1)
            if before != after
        ]
        self.assertEqual(len(generic), len(layout))
        self.assertEqual(
            [(311, '# key 352 "KEY_OK"', "key 352   DPAD_CENTER")],
            differences,
        )
        active_352 = [
            line.split() for line in layout
            if line.strip() and not line.lstrip().startswith("#")
            and line.split()[:2] == ["key", "352"]
        ]
        self.assertEqual([["key", "352", "DPAD_CENTER"]], active_352)

    def test_r4_tools_have_no_kernel_build_or_physical_action_path(self) -> None:
        builder = (REPO / "scripts/build-a16-prototype-a-r4-candidate.py").read_text(
            encoding="utf-8"
        )
        auditor = (REPO / "scripts/audit-a16-prototype-a-r4.py").read_text(
            encoding="utf-8"
        )
        lower = (builder + "\n" + auditor).lower()
        self.assertNotIn("self.build_boot(", builder)
        self.assertNotIn("self.build_vendor_dlkm(", builder)
        self.assertIn("self.preserve_boot_and_vendor_dlkm(", builder)
        for forbidden in (
            "fastboot flash", "adb reboot", "phoenixcard", "sunxi-fel",
            "shutdown -h", "systemctl poweroff",
        ):
            self.assertNotIn(forbidden, lower)
        self.assertIn('"physical_device_actions_performed": False', builder)
        self.assertIn('"flash_authorized": False', builder)

    def test_local_offline_checked_candidate_when_present(self) -> None:
        result_path = CANDIDATE / "build-result.json"
        audit_path = CANDIDATE / "offline-audit/offline-audit.json"
        if not result_path.is_file() or not audit_path.is_file():
            self.skipTest("ignored local a16-prototype-a-r4 candidate/audit is absent")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        preservation = json.loads(
            (
                REPO
                / "docs/m8/candidates/a16-prototype-a-r4-preservation.json"
            ).read_text(encoding="utf-8")
        )
        expected = self.config["expected_result"]
        self.assertEqual("OFFLINE_CHECKED", result["status"])
        self.assertEqual("NOT_YET_VALIDATED", result["physical_status"])
        self.assertEqual(
            "NOT_CLOSED_PENDING_R4_PHYSICAL_VALIDATION", result["gate2"]
        )
        self.assertFalse(result["physical_device_actions_performed"])
        self.assertFalse(result["flash_authorized"])
        for label, relative in (
            ("firmware", "x12-a16-prototype-a-r4.img"),
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
        self.assertEqual("mali", audit["bounded_fixes"]["egl"]["ro_hardware_egl"])
        self.assertEqual("apollo", audit["bounded_fixes"]["egl"]["ro_board_platform"])
        self.assertEqual(
            "ABSENT", audit["bounded_fixes"]["egl"]["persist_graphics_egl_default"]
        )
        remote = audit["bounded_fixes"]["remote_ok"]
        self.assertEqual(352, remote["scan_code"])
        self.assertEqual("DPAD_CENTER", remote["android_key_symbol"])
        self.assertEqual(23, remote["android_key_code"])
        self.assertEqual(0, remote["other_keylayout_lines_changed"])
        self.assertEqual(
            "INCOMPATIBLE_EXPECTED_INHERITED_NFS_EXCEPTION_ONLY",
            audit["compatibility"]["full_vintf"],
        )
        self.assertEqual(65, audit["compatibility"]["full_vintf_exit"])
        self.assertFalse(audit["preservation"]["kernel_rebuilt"])
        self.assertFalse(audit["preservation"]["vendor_dlkm_rebuilt"])
        self.assertEqual(22, audit["preservation"]["vendor_dlkm_module_count"])
        self.assertEqual(46, result["outer"]["preserved_payload_count"])
        self.assertEqual(
            ["Vsuper.fex", "Vvbmeta_system.fex", "super.fex", "vbmeta_system.fex"],
            result["outer"]["changed_payloads"],
        )
        self.assertTrue(result["super"]["bytes_outside_system_a_extent_exact"])
        self.assertEqual(expected["firmware"]["sha256"], preservation["candidate"]["sha256"])
        self.assertEqual(2, len(preservation["functional_delta"]))
        self.assertEqual("UNCHANGED_OPEN", preservation["subsystem_status"]["HDMI"])
        self.assertEqual("UNCHANGED_OPEN", preservation["subsystem_status"]["audio"])
        self.assertEqual(
            "NOT_CLOSED_PENDING_R4_PHYSICAL_VALIDATION", preservation["gate2"]
        )


if __name__ == "__main__":
    unittest.main()
