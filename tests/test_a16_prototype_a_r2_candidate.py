import hashlib
import json
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "configs/candidates/a16-prototype-a-r2.json"
BUILDER = REPO / "scripts/build-a16-prototype-a-r2-candidate.py"
KERNEL_BUILDER = REPO / "scripts/build-a16-prototype-a-r2-kernel.sh"
CANDIDATE = REPO / "out/candidates/a16-prototype-a-r2"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


class A16PrototypeAR2ContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))

    def test_candidate_is_offline_only_and_changes_boot_only(self) -> None:
        self.assertEqual(self.config["id"], "a16-prototype-a-r2")
        self.assertIn("offline-only", self.config["purpose"])
        self.assertIn("not authorized", self.config["purpose"])
        self.assertEqual(self.config["container"]["replacements"], ["boot.fex"])
        self.assertEqual(self.config["container"]["companions"], ["Vboot.fex"])
        self.assertEqual(self.config["container"]["preserved_entries"], 48)

    def test_kernel_delta_is_minimal_and_memcg_stays_optional(self) -> None:
        self.assertEqual(
            self.config["kernel"]["required_delta"],
            {
                "CONFIG_BLK_CGROUP": "y",
                "CONFIG_CPUSETS": "y",
                "CONFIG_PROC_PID_CPUSET": "y",
            },
        )
        self.assertEqual(self.config["kernel"]["required_preserved"]["CONFIG_MEMCG"], "n")
        script = KERNEL_BUILDER.read_text(encoding="utf-8")
        self.assertIn("--enable BLK_CGROUP", script)
        self.assertIn("--enable CPUSETS", script)
        self.assertIn("unexpected olddefconfig delta", script)

    def test_tracked_kernel_inputs_are_pinned(self) -> None:
        kernel = self.config["kernel"]
        for relative_key, hash_key in (
            ("repeat_patch_relative", "repeat_patch_sha256"),
            ("keymap_relative", "keymap_sha256"),
        ):
            self.assertEqual(sha256(REPO / kernel[relative_key]), kernel[hash_key])
        self.assertEqual(kernel["source_commit"], "9ab7a758149d3c9b721878a0c18b3f9c5d6c93e6")
        self.assertEqual(kernel["toolchain_revision"], "clang-r416183b1")
        self.assertEqual(kernel["host_dependency"]["version"], "3.0.13-0ubuntu3.12")
        self.assertEqual(len(kernel["host_dependency"]["deb_sha256"]), 64)
        self.assertEqual(kernel["host_bc"]["version"], "1.07.1-3ubuntu4")

    def test_builder_contains_no_device_mutation_path(self) -> None:
        source = BUILDER.read_text(encoding="utf-8")
        for forbidden in ("PhoenixCard", "fastboot flash", "adb reboot", "sunxi-fel"):
            self.assertNotIn(forbidden, source)
        self.assertNotIn('["sudo"', source)
        self.assertIn("--resume-stage", source)
        self.assertIn('"gate2": "CLOSED"', source)
        self.assertIn('"flash_authorized": False', source)

    def test_published_candidate_contract_when_present(self) -> None:
        result_path = CANDIDATE / "build-result.json"
        if not result_path.is_file():
            self.skipTest("ignored r2 candidate is not present")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "OFFLINE_CHECKED_CANDIDATE")
        self.assertEqual(result["gate2"], "CLOSED")
        self.assertFalse(result["physical_device_actions_performed"])
        self.assertFalse(result["flash_authorized"])
        self.assertNotIn(".staging-", result_path.read_text(encoding="utf-8"))
        self.assertEqual(
            result["firmware"],
            {
                "path": str(CANDIDATE / "x12-a16-prototype-a-r2.img"),
                "size": 1261038592,
                "sha256": "114DF8677CD6984EB1431377723EDF61C80ACF26C15D8770BAE47DCFE7D1B6D0",
            },
        )
        self.assertEqual(
            result["kernel_delta"], self.config["kernel"]["required_delta"]
        )
        self.assertEqual(result["payload_delta"], ["kernel", "boot.fex", "Vboot.fex"])
        self.assertEqual(result["compatibility"]["full_vintf_exit"], 65)
        self.assertEqual(
            result["compatibility"]["only_exception"],
            self.config["known_vintf_exception"],
        )

        audit = json.loads(
            (CANDIDATE / "outer-payload-audit.json").read_text(encoding="utf-8")
        )
        self.assertEqual(audit["replacements"], ["boot.fex"])
        preserved = [item for item in audit["payloads"] if item["action"] == "preserved"]
        self.assertEqual(len(preserved), 48)
        self.assertEqual(sha256(CANDIDATE / "boot.fex"), result["boot"]["sha256"])
        self.assertEqual(
            sha256(CANDIDATE / "kernel-build/Image"), result["kernel"]["sha256"]
        )


if __name__ == "__main__":
    unittest.main()
