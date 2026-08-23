from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "configs/candidates/m8-kernel-5.4.302-r2.json"
PATCH = REPO / "configs/kernel/m8-kernel-5.4.302/aic8800d-sdio-50mhz.patch"
CANDIDATE = REPO / "out/candidates/m8-kernel-5.4.302-r2"


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest().upper()


class M8Kernel54302R2CandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))

    def test_experiment_is_one_aic_bsp_clock_constant(self) -> None:
        config = self.config
        self.assertEqual("m8-kernel-5.4.302-r2", config["id"])
        self.assertEqual(70_000_000, config["experiment"]["source_before_hz"])
        self.assertEqual(50_000_000, config["experiment"]["source_after_hz"])
        self.assertEqual(["aic8800_bsp.ko"], config["experiment"]["candidate_changed_modules"])
        self.assertEqual(config["experiment"]["patch_sha256"], sha256(PATCH))
        patch = PATCH.read_text(encoding="utf-8")
        self.assertEqual(1, patch.count("-#define FEATURE_SDIO_CLOCK          70000000"))
        self.assertEqual(1, patch.count("+#define FEATURE_SDIO_CLOCK          50000000"))

    def test_outer_contract_preserves_r1_boot_and_non_super_payloads(self) -> None:
        config = self.config
        self.assertEqual(["super.fex"], config["container"]["replacements"])
        self.assertEqual(["Vsuper.fex"], config["container"]["companions"])
        self.assertEqual(48, config["container"]["preserved_entries"])
        self.assertEqual(config["expected_result"]["boot"], config["r1_preserved"]["boot"])
        self.assertIn("m8-kernel-5.4.302-r1", config["base_candidate"]["path"])

    def test_reproducibility_scripts_have_no_device_mutation_path(self) -> None:
        sources = "\n".join(
            (REPO / relative).read_text(encoding="utf-8").lower()
            for relative in (
                "scripts/build-m8-kernel-54302.sh",
                "scripts/audit-m8-kernel-54302-r2.py",
                "scripts/build-m8-kernel-54302-r2-candidate.py",
            )
        )
        for forbidden in (
            "fastboot flash",
            "adb reboot",
            "phoenixcard",
            "sunxi-fel",
            "systemctl poweroff",
        ):
            self.assertNotIn(forbidden, sources)

    def test_local_candidate_when_present(self) -> None:
        result_path = CANDIDATE / "build-result.json"
        if not result_path.is_file():
            self.skipTest("ignored local m8-kernel-5.4.302-r2 candidate is absent")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        self.assertEqual("OFFLINE_CHECKED_DIAGNOSTIC", result["status"])
        self.assertEqual("AWAIT_SEPARATELY_AUTHORIZED_PHYSICAL_WIFI_VALIDATION", result["decision"])
        self.assertEqual("CLOSED", result["gate2"])
        self.assertFalse(result["physical_device_actions_performed"])
        self.assertFalse(result["flash_authorized"])
        self.assertEqual(["aic8800_bsp.ko"], result["experiment"]["candidate_changed_modules"])
        self.assertTrue(result["outer"]["r1_boot_payload_exact"])
        self.assertEqual(["Vsuper.fex", "super.fex"], result["outer"]["changed_payloads"])
        self.assertEqual(48, result["outer"]["preserved_payload_count"])
        self.assertTrue(result["super"]["system_vendor_product_byte_preserved"])
        self.assertEqual("PASS", result["vendor_dlkm"]["avb_hashtree_fec"])
        for label, relative in (
            ("firmware", "x12-m8-kernel-5.4.302-r2.img"),
            ("boot", "boot.fex"),
            ("super", "super.fex"),
            ("vendor_dlkm", "vendor_dlkm_a.img"),
        ):
            expected = self.config["expected_result"][label]
            path = CANDIDATE / relative
            self.assertEqual(expected["size"], path.stat().st_size)
            self.assertEqual(expected["sha256"], sha256(path))


if __name__ == "__main__":
    unittest.main()
