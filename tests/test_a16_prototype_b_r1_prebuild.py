"""Pre-build guardrails for the bounded Android 16 Prototype B r1 attempt."""
from __future__ import annotations

import json
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "configs/candidates/a16-prototype-b-r1.json"
CHECKER = REPO / "scripts/check-a16-prototype-b-r1-mali.py"
AUDITOR = REPO / "scripts/audit-a16-prototype-b-r1.py"
RESULT = REPO / "docs/m8/candidates/a16-prototype-b-r1-offline-result.json"


def load_checker_module():
    spec = importlib.util.spec_from_file_location("a16_prototype_b_r1_mali_checker", CHECKER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load checker module: {CHECKER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_auditor_module():
    spec = importlib.util.spec_from_file_location("a16_prototype_b_r1_auditor", AUDITOR)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load auditor module: {AUDITOR}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class A16PrototypeBR1PrebuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))
        cls.result = json.loads(RESULT.read_text(encoding="utf-8"))
        cls.checker = load_checker_module()
        cls.auditor = load_auditor_module()

    def test_candidate_and_frozen_base_identity(self) -> None:
        self.assertEqual("a16-prototype-b-r1", self.config["id"])
        self.assertEqual("a16-prototype-a-r4", self.config["base_candidate"]["id"])
        self.assertEqual(1239746560, self.config["base_candidate"]["size"])
        self.assertEqual(
            "E125DD8FFB9F5B4A7B2B9B86DD8377367409AB00D1B29BE1E719CE25768E2111",
            self.config["base_candidate"]["sha256"],
        )
        self.assertEqual("ubox10_ceiling_arm64-bp2a-userdebug", self.config["android16"]["lunch"])
        self.assertEqual(1651167232, self.config["system_build_output"]["size"])
        self.assertEqual(
            "AA376DD3186044B82B1D0AD05415A2DDEFC174BACBCA153E9DF38769DF4E3FBC",
            self.config["system_build_output"]["sha256"],
        )
        self.assertEqual(
            self.config["frozen_r4_lp"]["logical"]["system_a"]["size"],
            self.config["system_build_output"]["size"],
        )
        self.assertEqual(11634, self.config["frozen_r4_offline_audit"]["size"])
        self.assertEqual(
            "4C44694AE23B1D84EB6D842228351AB63AACE6B304C0D6C3917BA79FF24FE765",
            self.config["frozen_r4_offline_audit"]["sha256"],
        )

    def test_exact_144_mib_vendor_geometry_is_bounded(self) -> None:
        self.assertEqual(
            "OFFLINE_CHECKED_READY_FOR_PHYSICAL_VALIDATION", self.config["status"]
        )
        self.assertEqual("PASS_EXACT_ARM64_MALI_LOCAL_INTAKE", self.config["prebuild_gate"]["result"])
        self.assertTrue(self.config["prebuild_gate"]["candidate_created"])
        fit = self.config["partition_fit"]
        self.assertEqual("PASS_BOUNDED_GEOMETRY_CORRECTION", fit["result"])
        self.assertEqual(119066624, fit["frozen_r4_partition_bytes"])
        self.assertEqual(150994944, fit["target_partition_bytes"])
        self.assertEqual(144 * 1024 * 1024, fit["target_partition_bytes"])
        self.assertEqual(31928320, fit["growth_bytes"])
        self.assertEqual([[2048, 3226984]], fit["frozen_extents_sectors"]["system_a"])
        self.assertEqual([[3227648, 3460200]], fit["frozen_extents_sectors"]["vendor_a"])
        self.assertEqual([[3461120, 3993600]], fit["frozen_extents_sectors"]["product_a"])
        self.assertEqual([[3993600, 4006648]], fit["frozen_extents_sectors"]["vendor_dlkm_a"])
        self.assertEqual(
            [[3227648, 3461120], [4007936, 4069376]],
            fit["candidate_extents_sectors"]["vendor_a"],
        )
        for name in ("system_a", "product_a", "vendor_dlkm_a"):
            self.assertEqual(
                fit["frozen_extents_sectors"][name], fit["candidate_extents_sectors"][name]
            )
        for name in ("system_b", "vendor_b", "product_b", "vendor_dlkm_b"):
            self.assertEqual([], fit["frozen_extents_sectors"][name])
            self.assertEqual([], fit["candidate_extents_sectors"][name])
        self.assertEqual(117104640, fit["available_filesystem_bytes"])
        self.assertEqual(135270400, fit["minimum_staged_filesystem_bytes"])
        self.assertEqual(18165760, fit["minimum_filesystem_overflow_bytes"])
        self.assertEqual(3212836864, fit["frozen_sb_a_maximum_bytes"])
        self.assertEqual(1163292672, fit["frozen_sb_a_unallocated_bytes"])
        self.assertEqual(1131364352, fit["target_sb_a_unallocated_bytes"])
        self.assertGreaterEqual(fit["frozen_sb_a_unallocated_bytes"], fit["growth_bytes"])
        self.assertFalse(fit["sb_a_maximum_size_changed"])
        self.assertFalse(fit["other_partition_sizes_or_allocations_changed"])
        self.assertFalse(fit["partition_shrink_allowed"])
        self.assertTrue(fit["lp_geometry_changed"])
        self.assertEqual(self.config["status"], self.result["status"])
        self.assertEqual(
            "OFFLINE CHECKED / READY FOR PHYSICAL VALIDATION", self.result["decision"]
        )
        self.assertEqual(1641752576, self.result["artifacts"]["candidate"]["size"])
        self.assertEqual(
            "796A2D46DB7FCDFF27D53397565ABDDC3D18F2E548A697055CE5E47278E69545",
            self.result["artifacts"]["candidate"]["sha256"],
        )
        self.assertFalse(self.result["physical_device_actions_performed"])

    def test_tracked_provider_source_contains_no_binary(self) -> None:
        source = REPO / "configs/aosp/architecture-ceiling-a16/hardware/aw/gpu"
        self.assertTrue((source / "mali-bifrost/gralloc/src/Android.mk").is_file())
        binary_suffixes = {".so", ".a", ".o", ".elf", ".bin"}
        self.assertEqual(
            [],
            [str(path.relative_to(REPO)) for path in source.rglob("*") if path.suffix in binary_suffixes],
        )

    def test_symbol_parser_accepts_aarch64_ifunc_exports(self) -> None:
        output = """
  24: 0000000000000000 0 FUNC GLOBAL DEFAULT UND memcpy@LIBC (2)
1030: 00000000000d9a44 92 <OS specific>: 10 GLOBAL DEFAULT 15 memcpy@@LIBC
"""
        undefined, exported = self.auditor.parse_dynamic_symbols(output)
        self.assertEqual({"memcpy"}, undefined)
        self.assertEqual({"memcpy"}, exported)

    def test_mixed_board_config_is_durable_and_exact(self) -> None:
        relative = (
            "configs/aosp/architecture-ceiling-a16/device/ubox/"
            "ubox10_ceiling_arm64/BoardConfig.mk"
        )
        item = self.config["tracked_source_inputs"][relative]
        tracked = REPO / relative
        text = tracked.read_text(encoding="utf-8")
        self.assertIn("include device/generic/arm64/BoardConfig.mk", text)
        self.assertIn("TARGET_BOARD_PLATFORM := apollo", text)
        self.assertIn("BOARD_SYSTEMIMAGE_PARTITION_SIZE := 1651167232", text)
        self.assertEqual(
            "42F3A518531CDCA82EDD449C8B9F07C33C44D4C8BDEFF9D2D3E72A0E6463F25C",
            item["sha256"],
        )
        self.assertEqual("device/ubox/ubox10_ceiling_arm64/BoardConfig.mk", item["aosp_relative"])

    def test_arm64_mali_contract_is_exact_and_outside_git(self) -> None:
        mali = self.config["arm64_mali_intake"]
        self.assertEqual(
            "/work/local-proprietary/ubox10/prototype-b-b1/libGLES_mali.so", mali["path"]
        )
        self.assertEqual(18145112, mali["size"])
        self.assertEqual(
            "03333D495E3566C7D85CA2E000DA569A16CE8F022EA25C0EA61950C891D5C7F8",
            mali["sha256"],
        )
        self.assertEqual("ELF64", mali["elf_class"])
        self.assertEqual("AArch64", mali["machine"])
        self.assertEqual("libGLES_mali.so", mali["soname"])
        self.assertEqual("281008657ed1f606be382d076fe69918", mali["build_id"])
        self.assertEqual(297, mali["b0_unique_strong_imports"])
        self.assertEqual(0, mali["b0_unmatched_strong_imports"])
        self.assertFalse(mali["git_tracking_allowed"])

    def test_missing_intake_fails_before_build(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "libGLES_mali.so"
            result = subprocess.run(
                [sys.executable, str(CHECKER), "--path", str(missing)],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        self.assertEqual(2, result.returncode)
        self.assertIn("B1 BUILD BLOCKED — LOCAL ARM64 MALI INTAKE MISSING", result.stderr)
        self.assertIn("required_size=18145112", result.stderr)
        self.assertIn(self.config["arm64_mali_intake"]["sha256"], result.stderr)

    def test_wrong_elf_fails_closed(self) -> None:
        result = subprocess.run(
            [sys.executable, str(CHECKER), "--path", "/bin/true"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(3, result.returncode)
        self.assertIn("B1 BUILD BLOCKED — LOCAL ARM64 MALI INTAKE IDENTITY MISMATCH", result.stderr)

    def test_checker_has_no_download_copy_or_device_path(self) -> None:
        source = CHECKER.read_text(encoding="utf-8").lower()
        for forbidden in (
            "urllib",
            "requests",
            "wget",
            "curl",
            "shutil.copy",
            "adb ",
            "fastboot",
            "phoenixcard",
            "sunxi-fel",
        ):
            self.assertNotIn(forbidden, source)

    def test_bounded_build_and_audit_have_no_physical_or_kernel_action(self) -> None:
        sources = "\n".join(
            (REPO / relative).read_text(encoding="utf-8").lower()
            for relative in (
                "scripts/build-a16-prototype-b-r1-candidate.py",
                "scripts/audit-a16-prototype-b-r1.py",
            )
        )
        for forbidden in (
            "fastboot flash", "adb reboot", "phoenixcard", "sunxi-fel",
            "shutdown -h", "systemctl poweroff", "build_boot(",
            "build_vendor_dlkm(", "make menuconfig", "olddefconfig",
        ):
            self.assertNotIn(forbidden, sources)
        self.assertIn('"kernel_rebuilt": false', sources)
        self.assertIn('"physical_device_actions_performed": false', sources)
        self.assertIn('"flash_authorized": false', sources)

    def test_build_id_parser_accepts_normal_multiline_output(self) -> None:
        notes = "Displaying notes found in: .note.gnu.build-id\n  Build ID: 0123aBcD\n"
        self.assertEqual(
            "0123aBcD",
            self.checker.one(r"\bBuild ID:\s*([0-9a-fA-F]+)", notes, "Build ID"),
        )

    def test_build_id_parser_accepts_readelf_w_single_line_output(self) -> None:
        notes = (
            "  Owner                Data size \tDescription\n"
            "  GNU                  0x00000010\tNT_GNU_BUILD_ID (unique build ID bitstring)"
            "\tBuild ID: 281008657ed1f606be382d076fe69918\n"
        )
        self.assertEqual(
            "281008657ed1f606be382d076fe69918",
            self.checker.one(r"\bBuild ID:\s*([0-9a-fA-F]+)", notes, "Build ID"),
        )

    def test_build_id_parser_still_fails_closed_when_absent(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "missing Build ID in ELF metadata"):
            self.checker.one(
                r"\bBuild ID:\s*([0-9a-fA-F]+)",
                "GNU NT_GNU_ABI_TAG ABI: 0.0.0\n",
                "Build ID",
            )


if __name__ == "__main__":
    unittest.main()
