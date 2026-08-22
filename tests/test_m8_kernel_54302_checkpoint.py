from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import unittest


REPO = Path(__file__).resolve().parents[1]
CONTRACT = REPO / "configs/kernel/m8-kernel-5.4.302"
CANDIDATE_CONFIG = REPO / "configs/candidates/m8-kernel-5.4.302-r1.json"
CANDIDATE = REPO / "out/candidates/m8-kernel-5.4.302-r1"


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest().upper()


class M8Kernel54302CheckpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.checkpoint = json.loads((CONTRACT / "checkpoint.json").read_text())
        cls.conflicts = json.loads((CONTRACT / "conflict-resolutions.json").read_text())
        cls.candidate_config = json.loads(CANDIDATE_CONFIG.read_text())

    def test_lineage_and_conflict_contract(self) -> None:
        lineage = self.checkpoint["lineage"]
        self.assertEqual(
            "9ab7a758149d3c9b721878a0c18b3f9c5d6c93e6",
            lineage["vendor"]["commit"],
        )
        self.assertIsNone(lineage["vendor"]["merge_base_with_upstream_v5_4_125"])
        self.assertEqual(
            "9e3157c56ec7917e6a80ea53a8bd752e0037f2cb",
            lineage["upstream"]["v5_4_302_commit"],
        )
        self.assertTrue(lineage["android_common"]["target_contains_upstream_v5_4_302"])
        self.assertTrue(lineage["integration"]["exact_replay_verified"])
        self.assertEqual(46, self.conflicts["initial_conflict_count"])
        self.assertEqual(
            46,
            len(self.conflicts["upstream_stable_fix_wins"])
            + len(self.conflicts["vendor_implementation_must_be_preserved"])
            + len(self.conflicts["semantic_merge_required"]),
        )

    def test_effective_configs_and_deltas_are_hash_locked(self) -> None:
        for spec in self.checkpoint["effective_configs"].values():
            if not isinstance(spec, dict) or "path" not in spec:
                continue
            path = CONTRACT / spec["path"]
            self.assertEqual(spec["size"], path.stat().st_size)
            self.assertEqual(spec["sha256"].upper(), sha256(path))
        preservation = json.loads((CONTRACT / "preservation-delta.json").read_text())
        path_a = json.loads((CONTRACT / "path-a-delta.json").read_text())
        self.assertEqual(32, len(preservation))
        self.assertEqual(9, len(path_a))
        enabled = {key for key, (_before, after) in path_a.items() if after == "y"}
        self.assertEqual(
            set(self.checkpoint["effective_configs"]["path_a_enabled_requirements"]),
            enabled,
        )

    def test_effective_diffs_are_path_and_timestamp_independent(self) -> None:
        for before, after, tracked in (
            (
                "accepted-5.4.125.config",
                "preservation-5.4.302.config",
                "preservation-effective.diff",
            ),
            (
                "preservation-5.4.302.config",
                "path-a-5.4.302.config",
                "path-a-effective.diff",
            ),
        ):
            completed = subprocess.run(
                (
                    "diff",
                    "-u",
                    "--label",
                    before,
                    "--label",
                    after,
                    str(CONTRACT / before),
                    str(CONTRACT / after),
                ),
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(1, completed.returncode, completed.stderr)
            self.assertEqual((CONTRACT / tracked).read_text(), completed.stdout)
            self.assertNotIn("/work/", completed.stdout)

    def test_reproducibility_scripts_have_no_device_mutation_path(self) -> None:
        sources = "\n".join(
            (REPO / relative).read_text(encoding="utf-8")
            for relative in (
                "scripts/integrate-m8-kernel-54302.sh",
                "scripts/build-m8-kernel-54302.sh",
                "scripts/audit-m8-kernel-54302.py",
                "scripts/build-m8-kernel-54302-candidate.py",
            )
        ).lower()
        for forbidden in (
            "fastboot flash",
            "adb reboot",
            "phoenixcard",
            "sunxi-fel",
            "systemctl poweroff",
        ):
            self.assertNotIn(forbidden, sources)
        self.assertIn('"fec"', sources)
        self.assertIn('"simg2img"', sources)
        self.assertIn("expected_result", sources)

    def test_candidate_contract_and_local_result_when_present(self) -> None:
        config = self.candidate_config
        self.assertEqual("m8-kernel-5.4.302-r1", config["id"])
        self.assertEqual(["boot.fex", "super.fex"], config["container"]["replacements"])
        self.assertEqual(["Vboot.fex", "Vsuper.fex"], config["container"]["companions"])
        self.assertEqual(46, config["container"]["preserved_entries"])
        result_path = CANDIDATE / "build-result.json"
        if not result_path.is_file():
            self.skipTest("ignored local m8-kernel-5.4.302-r1 candidate is absent")
        result = json.loads(result_path.read_text())
        self.assertEqual("OFFLINE_CHECKED", result["status"])
        self.assertEqual("CLOSED", result["gate2"])
        self.assertFalse(result["physical_device_actions_performed"])
        self.assertFalse(result["flash_authorized"])
        self.assertEqual(
            "GO_FOR_SEPARATELY_AUTHORIZED_ANDROID12_KERNEL_ONLY_PHYSICAL_VALIDATION",
            result["decision"],
        )
        for label, relative in (
            ("firmware", "x12-m8-kernel-5.4.302-r1.img"),
            ("boot", "boot.fex"),
            ("super", "super.fex"),
            ("vendor_dlkm", "vendor_dlkm_a.img"),
        ):
            expected = config["expected_result"][label]
            path = CANDIDATE / relative
            self.assertEqual(expected["size"], path.stat().st_size)
            self.assertEqual(expected["sha256"], sha256(path))
        self.assertTrue(result["super"]["sparse_roundtrip_raw_exact"])
        self.assertTrue(result["super"]["system_vendor_product_byte_preserved"])
        self.assertEqual("PASS", result["vendor_dlkm"]["avb_hashtree_fec"])
        self.assertEqual(1, result["vendor_dlkm"]["free_blocks_after_replacement"])
        self.assertEqual(46, result["outer"]["preserved_payload_count"])


if __name__ == "__main__":
    unittest.main()
