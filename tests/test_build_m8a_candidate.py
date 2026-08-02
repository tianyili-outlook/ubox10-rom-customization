"""Static guardrails for the bounded M8A candidate configuration."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("m8a_builder", REPO / "scripts" / "build-m8a-candidate.py")
assert SPEC and SPEC.loader
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class CandidateConfigTests(unittest.TestCase):
    def test_group_budget_and_no_system_ext_partition(self) -> None:
        cfg = json.loads((REPO / "configs/candidates/m8a-initial-atv-r1.json").read_text(encoding="utf-8"))
        logical = cfg["logical_partitions"]
        self.assertEqual(set(logical), {"system_a", "vendor_a", "product_a", "vendor_dlkm_a"})
        self.assertEqual(sum(logical.values()), 2049544192)
        self.assertEqual(cfg["super"]["group_size"] - sum(logical.values()), 1163292672)
        self.assertEqual(cfg["super"]["device_size"], 3221225472)

    def test_locked_hashes_are_present(self) -> None:
        cfg = json.loads((REPO / "configs/candidates/m8a-initial-atv-r1.json").read_text(encoding="utf-8"))
        self.assertEqual(len(cfg["stock_container_sha256"]), 64)
        self.assertEqual(set(cfg["aosp"]), {"system", "product", "system_ext"})
        self.assertTrue(all(len(item["sha256"]) == 64 for item in cfg["aosp"].values()))

    def test_publication_rewrite_uses_final_artifact_and_canonical_wsl_paths(self) -> None:
        stage = Path(r"C:\candidate\.staging")
        final = Path(r"C:\candidate\final")
        source = {
            str(stage / "artifacts" / "super.img"): {"path": str(stage / "artifacts" / "super.img")},
            str(stage / "inputs" / "aosp" / "system.img"): {"path": str(stage / "inputs" / "aosp" / "system.img")},
        }
        rewritten = builder.rewrite_published_paths(
            source, stage=stage, final=final,
            aosp_wsl_directory="/home/tianyi/ubox10-aosp/out/target/product/ubox10", provenance=True)
        self.assertEqual(rewritten[str(final / "super.img")]["path"], str(final / "super.img"))
        wsl = "wsl:/home/tianyi/ubox10-aosp/out/target/product/ubox10/system.img"
        self.assertEqual(rewritten[wsl]["path"], wsl)

    def test_avb_publication_distinguishes_rebuilt_and_stock_fec(self) -> None:
        self.assertIn("dm-verity enabled; flags 0", builder.AVB_PUBLICATION_SUMMARY)
        self.assertIn("rebuilt system/product omit FEC", builder.AVB_PUBLICATION_SUMMARY)
        self.assertIn("stock vendor/vendor_dlkm retain stock FEC", builder.AVB_PUBLICATION_SUMMARY)


if __name__ == "__main__":
    unittest.main()
