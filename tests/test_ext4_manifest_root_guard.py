"""M6b.1 tests for the pure JSON root-hierarchy guard."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPO_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from ubox10_rom.ext4_manifest import assess_root_hierarchy_file  # noqa: E402


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "m6b_root_guard"


class RootHierarchyGuardTests(unittest.TestCase):
    def test_accepts_manifest_that_represents_the_ext4_root(self) -> None:
        result = assess_root_hierarchy_file(FIXTURE_DIR / "official-root-manifest.json")

        self.assertEqual("PASS", result.status)
        self.assertEqual((), result.reason_codes)
        self.assertEqual(("lost+found", "system"), result.observed_direct_child_names)

    def test_rejects_system_subtree_when_presented_as_root(self) -> None:
        result = assess_root_hierarchy_file(FIXTURE_DIR / "system-subtree-as-root-manifest.json")

        self.assertEqual("FAIL", result.status)
        self.assertIn("missing_required_directory:/system", result.reason_codes)
        self.assertIn("missing_required_child:system", result.reason_codes)
        self.assertIn("prohibited_subtree_identity:/system", result.reason_codes)

    def test_invalid_json_is_a_fail_closed_result(self) -> None:
        result = assess_root_hierarchy_file(FIXTURE_DIR / "not-present.json")

        self.assertEqual("FAIL", result.status)
        self.assertEqual(("manifest_load_error:FileNotFoundError",), result.reason_codes)


if __name__ == "__main__":
    unittest.main()
