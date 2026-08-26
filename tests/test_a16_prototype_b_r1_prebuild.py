"""Pre-build guardrails for the bounded Android 16 Prototype B r1 attempt."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "configs/candidates/a16-prototype-b-r1.json"
CHECKER = REPO / "scripts/check-a16-prototype-b-r1-mali.py"


class A16PrototypeBR1PrebuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))

    def test_candidate_and_frozen_base_identity(self) -> None:
        self.assertEqual("a16-prototype-b-r1", self.config["id"])
        self.assertEqual("a16-prototype-a-r4", self.config["base_candidate"]["id"])
        self.assertEqual(1239746560, self.config["base_candidate"]["size"])
        self.assertEqual(
            "E125DD8FFB9F5B4A7B2B9B86DD8377367409AB00D1B29BE1E719CE25768E2111",
            self.config["base_candidate"]["sha256"],
        )
        self.assertEqual("ubox10_ceiling_arm64-bp2a-userdebug", self.config["android16"]["lunch"])

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


if __name__ == "__main__":
    unittest.main()
