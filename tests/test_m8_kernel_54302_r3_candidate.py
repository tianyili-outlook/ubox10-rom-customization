from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "configs/candidates/m8-kernel-5.4.302-r3.json"
PATCH = REPO / "configs/kernel/m8-kernel-5.4.302/aic8800d-startapp-trace.patch"
CANDIDATE = REPO / "out/candidates/m8-kernel-5.4.302-r3"


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest().upper()


class M8Kernel54302R3CandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))
        cls.patch = PATCH.read_text(encoding="utf-8")
        cls.added = "\n".join(
            line[1:] for line in cls.patch.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        )

    def test_patch_is_startapp_gated_observability_only(self) -> None:
        self.assertEqual("m8-kernel-5.4.302-r3", self.config["id"])
        self.assertEqual(70_000_000, self.config["experiment"]["functional_sdio_clock_hz"])
        self.assertEqual(self.config["experiment"]["patch_sha256"], sha256(PATCH))
        self.assertNotIn("476", self.added)
        self.assertEqual(1, self.added.count("AIC_STARTAPP_TRACE:"))
        self.assertIn("WRITE_ONCE(trace->token, cmd->tkn)", self.added)
        self.assertIn("cmd->id == DBG_START_APP_REQ", self.added)
        self.assertIn("cmd->reqid == DBG_START_APP_CFM", self.added)
        self.assertIn("atomic_set(&aicdev->startapp_trace.tx_cmd53_state, 1)", self.added)
        self.assertIn("atomic_set(&aicdev->startapp_trace.tx_cmd53_state, 2)", self.added)
        self.assertIn("irq_after_tx_return_count", self.added)
        self.assertIn("rx_after_tx_return_count", self.added)
        for forbidden in (
            "FEATURE_SDIO_CLOCK          50000000",
            "msleep(", "udelay(", "mdelay(", "schedule_timeout(",
            "wait_for_completion_timeout", "CMD_TX_TIMEOUT", "RWNX_CMD_TIMEOUT_MS",
            "sdio_claim_host", "sdio_release_host", "sdio_writesb", "sdio_readsb",
        ):
            self.assertNotIn(forbidden, self.added)

    def test_candidate_contract_preserves_physical_r1(self) -> None:
        config = self.config
        self.assertEqual(["aic8800_bsp.ko"], config["experiment"]["candidate_changed_modules"])
        self.assertEqual(["super.fex"], config["container"]["replacements"])
        self.assertEqual(["Vsuper.fex"], config["container"]["companions"])
        self.assertEqual(48, config["container"]["preserved_entries"])
        self.assertIn("m8-kernel-5.4.302-r1", config["base_candidate"]["path"])
        self.assertEqual(
            "9B781ABEA51DEF9AE1FEBB9011CFA630AC267C794FBA0E066674F0EAE2509DCC",
            config["r1_preserved"]["image"]["sha256"],
        )

    def test_reproducibility_scripts_have_no_device_mutation_path(self) -> None:
        sources = "\n".join(
            (REPO / relative).read_text(encoding="utf-8").lower()
            for relative in (
                "scripts/build-m8-kernel-54302.sh",
                "scripts/audit-m8-kernel-54302-r3.py",
                "scripts/build-m8-kernel-54302-r3-candidate.py",
            )
        )
        for forbidden in (
            "fastboot flash", "adb reboot", "phoenixcard", "sunxi-fel",
            "systemctl poweroff",
        ):
            self.assertNotIn(forbidden, sources)

    def test_local_candidate_when_present(self) -> None:
        result_path = CANDIDATE / "build-result.json"
        if not result_path.is_file():
            self.skipTest("ignored local m8-kernel-5.4.302-r3 candidate is absent")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        self.assertEqual("OFFLINE_CHECKED_INSTRUMENTATION_ONLY", result["status"])
        self.assertEqual("AWAIT_SEPARATE_EXPLICIT_PHYSICAL_AUTHORIZATION", result["decision"])
        self.assertEqual("CLOSED", result["gate2"])
        self.assertTrue(result["not_a_fix"])
        self.assertFalse(result["physical_device_actions_performed"])
        self.assertFalse(result["flash_authorized"])
        self.assertEqual(["aic8800_bsp.ko"], result["experiment"]["candidate_changed_modules"])
        self.assertTrue(result["outer"]["r1_boot_payload_exact"])
        self.assertEqual(["Vsuper.fex", "super.fex"], result["outer"]["changed_payloads"])
        self.assertEqual(48, result["outer"]["preserved_payload_count"])
        self.assertTrue(result["super"]["system_vendor_product_byte_preserved"])
        self.assertEqual("PASS", result["vendor_dlkm"]["avb_hashtree_fec"])
        for label, relative in (
            ("firmware", "x12-m8-kernel-5.4.302-r3.img"),
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
