from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from tools.pack_image_preserving import parse_image


REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "configs/candidates/m8-kernel-5.4.302-r5.json"
PATCH = REPO / "configs/kernel/m8-kernel-5.4.302/aic8800d-fmac-address-contract.patch"
R4 = REPO / "out/candidates/m8-kernel-5.4.302-r4"
R5 = REPO / "out/candidates/m8-kernel-5.4.302-r5"


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest().upper()


def outer_hashes(path: Path) -> dict[str, str]:
    _prefix, entries = parse_image(path)
    result = {}
    with path.open("rb") as stream:
        for entry in entries:
            stream.seek(int(entry["offset"]))
            remaining = int(entry["stored_len"])
            value = hashlib.sha256()
            while remaining:
                block = stream.read(min(8 * 1024 * 1024, remaining))
                if not block:
                    raise RuntimeError(f"truncated payload: {entry['filename']}")
                value.update(block)
                remaining -= len(block)
            result[str(entry["filename"])] = value.hexdigest().upper()
    return result


class M8Kernel54302R5CandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))

    def test_contract_patch_is_exactly_one_guard_change(self) -> None:
        patch = PATCH.read_text(encoding="utf-8")
        added = [line[1:] for line in patch.splitlines() if line.startswith("+") and not line.startswith("+++")]
        removed = [line[1:] for line in patch.splitlines() if line.startswith("-") and not line.startswith("---")]
        self.assertEqual(["#ifdef AICWF_SDIO_SUPPORT"], added)
        self.assertEqual(["#ifdef CONFIG_AIC_INTF_SDIO"], removed)
        self.assertEqual(self.config["experiment"]["contract_patch_sha256"], sha256(PATCH))
        self.assertEqual(70_000_000, self.config["experiment"]["functional_sdio_clock_hz"])
        self.assertEqual(["aic8800_bsp.ko"], self.config["experiment"]["candidate_changed_modules"])

    def test_no_physical_device_mutation_path(self) -> None:
        sources = "\n".join(
            (REPO / relative).read_text(encoding="utf-8").lower()
            for relative in (
                "scripts/build-m8-kernel-54302.sh",
                "scripts/audit-m8-kernel-54302-r5.py",
                "scripts/build-m8-kernel-54302-r5-candidate.py",
            )
        )
        for forbidden in ("fastboot flash", "adb reboot", "phoenixcard", "sunxi-fel"):
            self.assertNotIn(forbidden, sources)

    def test_local_candidate_when_present(self) -> None:
        result_path = R5 / "build-result.json"
        if not result_path.is_file():
            self.skipTest("ignored local m8-kernel-5.4.302-r5 candidate is absent")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        self.assertEqual("OFFLINE_CHECKED_CONTRACT_CORRECTION", result["status"])
        self.assertEqual("PHYSICAL_VALIDATION_REQUIRED", result["decision"])
        self.assertEqual("CLOSED", result["gate2"])
        self.assertFalse(result["physical_device_actions_performed"])
        self.assertFalse(result["flash_authorized"])
        self.assertTrue(result["not_a_fix"])
        self.assertEqual("PASS", result["vendor_dlkm"]["avb_hashtree_fec"])
        self.assertEqual("PASS", result["vendor_dlkm"]["e2fsck"])
        self.assertTrue(result["super"]["metadata_geometry_exact"])
        self.assertTrue(result["super"]["sparse_roundtrip_raw_exact"])
        self.assertTrue(result["super"]["system_vendor_product_byte_preserved"])
        self.assertEqual("PASS", result["outer"]["imagewty_verify"])
        self.assertEqual(["Vsuper.fex", "super.fex"], result["outer"]["changed_payloads"])
        for label, relative in (
            ("firmware", "x12-m8-kernel-5.4.302-r5.img"),
            ("boot", "boot.fex"),
            ("super", "super.fex"),
            ("vendor_dlkm", "vendor_dlkm_a.img"),
        ):
            expected = self.config["expected_result"][label]
            path = R5 / relative
            self.assertEqual(expected["size"], path.stat().st_size)
            self.assertEqual(expected["sha256"], sha256(path))

    def test_final_r5_preservation_and_elf_audit(self) -> None:
        if not (R4 / "build-result.json").is_file() or not (R5 / "build-result.json").is_file():
            self.skipTest("ignored local r4/r5 candidates are absent")
        r5_result = json.loads((R5 / "build-result.json").read_text(encoding="utf-8"))
        audit_path = Path(str(self.config["experiment"]["single_variable_audit"]))
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        self.assertEqual("PASS_R5_FMAC_ADDRESS_CONTRACT_ONLY", audit["result"])
        packaged = audit["final_elf_address_contract"]["packaged_r5"]
        self.assertEqual("0x00120000", packaged["proved"]["fmac_upload_destination"])
        self.assertEqual("0x00120180", packaged["proved"]["patch_read_address"])
        self.assertEqual("0x00120000", packaged["proved"]["start_app_bootaddr"])
        self.assertTrue(audit["final_elf_address_contract"]["r5_matches_working_contract"])
        self.assertTrue(audit["r4_trace_and_timeout_cccr_instrumentation_present"])
        self.assertTrue(audit["other_21_modules_byte_identical"])
        self.assertTrue(audit["firmware_preservation"]["exact_firmware_byte_identical"])

        r4_modules = {path.name: sha256(path) for path in (R4 / "candidate-vendor-dlkm-root/lib/modules").glob("*.ko")}
        r5_modules = {path.name: sha256(path) for path in (R5 / "candidate-vendor-dlkm-root/lib/modules").glob("*.ko")}
        self.assertEqual(set(r4_modules), set(r5_modules))
        self.assertEqual(["aic8800_bsp.ko"], sorted(name for name in r4_modules if r4_modules[name] != r5_modules[name]))

        r4_outer = outer_hashes(R4 / "x12-m8-kernel-5.4.302-r4.img")
        r5_outer = outer_hashes(R5 / "x12-m8-kernel-5.4.302-r5.img")
        self.assertEqual(["Vsuper.fex", "super.fex"], sorted(name for name in r4_outer if r4_outer[name] != r5_outer[name]))
        self.assertEqual(48, sum(r4_outer[name] == r5_outer[name] for name in r4_outer))
        self.assertEqual(sha256(R4 / "boot.fex"), sha256(R5 / "boot.fex"))
        self.assertEqual(
            sha256(R4 / "candidate-boot-unpacked/kernel"),
            sha256(R5 / "candidate-boot-unpacked/kernel"),
        )
        self.assertEqual(
            sha256(R4 / "candidate-boot-unpacked/ramdisk"),
            sha256(R5 / "candidate-boot-unpacked/ramdisk"),
        )
        for name in ("system_a.img", "vendor_a.img", "product_a.img"):
            self.assertEqual(
                sha256(R4 / "candidate-logical" / name),
                sha256(R5 / "candidate-logical" / name),
            )
        self.assertEqual(
            self.config["r1_preserved"]["image"]["sha256"],
            r5_result["boot"]["kernel_after"]["sha256"],
        )
        rollback = Path(str(self.config["rollback"]["path"]))
        self.assertEqual(self.config["rollback"]["sha256"], sha256(rollback))


if __name__ == "__main__":
    unittest.main()
