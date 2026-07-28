from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "prepare-candidate-inputs.py"
spec = importlib.util.spec_from_file_location("prepare_candidate_inputs", SCRIPT)
assert spec is not None and spec.loader is not None
prepare = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = prepare
spec.loader.exec_module(prepare)


class PrepareCandidateInputsTests(unittest.TestCase):
    def test_partition_contract_uses_only_canonical_official_inputs(self) -> None:
        self.assertEqual(
            {"system_a", "product_a", "vendor_a", "vendor_dlkm_a"},
            set(prepare.PARTITIONS),
        )
        for partition, entry in prepare.PARTITIONS.items():
            self.assertEqual(f"{partition}.img", entry["output"].name)
            entry["output"].resolve().relative_to((REPO / "out").resolve())
            self.assertRegex(entry["sha256"], r"^[0-9A-F]{64}$")

    def test_official_container_identity_is_locked(self) -> None:
        self.assertEqual(REPO / "x12-1024.img", prepare.OFFICIAL_IMAGE)
        self.assertEqual(64, len(prepare.OFFICIAL_IMAGE_SHA256))
        self.assertEqual(64, len(prepare.OFFICIAL_SUPER_SHA256))

    def test_payload_comparison_rejects_same_size_content_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            container = root / "container.bin"
            matching = root / "matching.bin"
            mismatch = root / "mismatch.bin"
            container.write_bytes(b"prefixPAYLOADsuffix")
            matching.write_bytes(b"PAYLOAD")
            mismatch.write_bytes(b"PAYLOAd")

            self.assertTrue(
                prepare.matches_container_payload(container, matching, 6, 7)
            )
            self.assertFalse(
                prepare.matches_container_payload(container, mismatch, 6, 7)
            )


if __name__ == "__main__":
    unittest.main()
