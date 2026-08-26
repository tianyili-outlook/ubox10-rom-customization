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
RESULT = REPO / "docs/m8/candidates/a16-prototype-b-r1-offline-result.json"


def load_checker_module():
    spec = importlib.util.spec_from_file_location("a16_prototype_b_r1_mali_checker", CHECKER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load checker module: {CHECKER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class A16PrototypeBR1PrebuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))
        cls.result = json.loads(RESULT.read_text(encoding="utf-8"))
        cls.checker = load_checker_module()

    def test_candidate_and_frozen_base_identity(self) -> None:
        self.assertEqual("a16-prototype-b-r1", self.config["id"])
        self.assertEqual("a16-prototype-a-r4", self.config["base_candidate"]["id"])
        self.assertEqual(1239746560, self.config["base_candidate"]["size"])
        self.assertEqual(
            "E125DD8FFB9F5B4A7B2B9B86DD8377367409AB00D1B29BE1E719CE25768E2111",
            self.config["base_candidate"]["sha256"],
        )
        self.assertEqual("ubox10_ceiling_arm64-bp2a-userdebug", self.config["android16"]["lunch"])

    def test_final_hold_is_exact_vendor_partition_fit_blocker(self) -> None:
        self.assertEqual("OFFLINE_HOLD_PARTITION_FIT_BLOCKER", self.config["status"])
        self.assertEqual("PASS_EXACT_ARM64_MALI_LOCAL_INTAKE", self.config["prebuild_gate"]["result"])
        self.assertFalse(self.config["prebuild_gate"]["candidate_created"])
        fit = self.config["partition_fit"]
        self.assertEqual("BLOCKER", fit["result"])
        self.assertEqual(117104640, fit["available_filesystem_bytes"])
        self.assertEqual(135270400, fit["minimum_staged_filesystem_bytes"])
        self.assertEqual(18165760, fit["minimum_filesystem_overflow_bytes"])
        self.assertFalse(fit["lp_geometry_changed"])
        self.assertEqual(self.config["status"], self.result["status"])
        self.assertFalse(self.result["build"]["candidate_created"])

    def test_tracked_provider_source_contains_no_binary(self) -> None:
        source = REPO / "configs/aosp/architecture-ceiling-a16/hardware/aw/gpu"
        self.assertTrue((source / "mali-bifrost/gralloc/src/Android.mk").is_file())
        binary_suffixes = {".so", ".a", ".o", ".elf", ".bin"}
        self.assertEqual(
            [],
            [str(path.relative_to(REPO)) for path in source.rglob("*") if path.suffix in binary_suffixes],
        )

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
