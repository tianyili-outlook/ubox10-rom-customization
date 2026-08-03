"""Focused contract-path tests for the CLI bridge."""

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / ".agents" / "skills" / "antigravity-worker" / "scripts" / "delegate.py"
SPEC = importlib.util.spec_from_file_location("antigravity_delegate", MODULE_PATH)
assert SPEC and SPEC.loader
DELEGATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DELEGATE)


class RootedGlobTests(unittest.TestCase):
    def test_root_candidates_tree_matches(self):
        self.assertTrue(DELEGATE.match("candidates/test/file.txt", "candidates/**"))

    def test_nested_candidates_do_not_match_root_rule(self):
        self.assertFalse(DELEGATE.match("configs/candidates/file.txt", "candidates/**"))
        self.assertFalse(DELEGATE.match("out/candidates/file.txt", "candidates/**"))

    def test_nested_candidates_need_explicit_authorization(self):
        self.assertTrue(DELEGATE.match("configs/candidates/file.txt", "configs/candidates/**"))
        self.assertTrue(DELEGATE.match("out/candidates/file.txt", "out/candidates/**"))

    def test_out_of_scope_write_is_a_violation(self):
        contract = {"protected_paths": [], "writable_paths": ["tmp/**"]}
        self.assertEqual(DELEGATE.violations(["configs/candidates/file.txt"], contract), ["outside-writable-paths:configs/candidates/file.txt"])

    def test_tmp_runtime_file_is_not_a_violation(self):
        contract = {"protected_paths": [], "writable_paths": ["tmp/**"]}
        self.assertEqual(DELEGATE.violations(["tmp/unleash-repo-schema-v1-codeium-language-server.json"], contract), [])

    def test_temporary_clone_does_not_register_primary_worktree(self):
        before = subprocess.run(["git", "worktree", "list", "--porcelain"], cwd=ROOT, text=False, capture_output=True, check=True).stdout
        with tempfile.TemporaryDirectory(prefix="ubox10-bridge-test-") as directory:
            checkout = DELEGATE.temporary_checkout(type("Holder", (), {"name": directory})())
            self.assertTrue((checkout / ".git").exists())
        after = subprocess.run(["git", "worktree", "list", "--porcelain"], cwd=ROOT, text=False, capture_output=True, check=True).stdout
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
