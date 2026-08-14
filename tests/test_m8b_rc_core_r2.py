from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "configs" / "candidates" / "m8b-rc-core-r2.json"
PATCH = REPO / "configs" / "candidates" / "m8b-rc-core-r2" / "rc-main-repeat.patch"
CANDIDATE = REPO / "out" / "candidates" / "m8b-rc-core-r2"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest().upper()


class M8BRcCoreR2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))

    def test_01_repeat_patch_is_exact_and_locked(self) -> None:
        self.assertEqual("m8b-rc-core-r2", self.config["id"])
        spec = self.config["kernel_repeat_patch"]
        self.assertEqual(spec["sha256"], digest(PATCH))
        self.assertEqual("drivers/media/rc/rc-main.c", spec["target"])
        text = PATCH.read_text(encoding="utf-8")
        self.assertEqual(0, text.count("!key_repeat"))
        self.assertEqual(1, text.count("#ifdef CONFIG_SUNXI_MULTI_IR_SUPPORT"))
        self.assertEqual(1, text.count("#endif"))
        self.assertIn("@@ -766,0 +767 @@", text)
        self.assertIn("@@ -767,0 +769 @@", text)
        self.assertNotIn("IR_KEYPRESS_TIMEOUT", text)
        self.assertNotIn("ir-nec-decoder", text)

    def test_02_existing_r1_chain_is_parameterized(self) -> None:
        shell = (REPO / "scripts" / "build-m8b-rc-core-kernel.sh").read_text(encoding="utf-8")
        builder = (REPO / "scripts" / "build-m8b-rc-core-r1-candidate.py").read_text(encoding="utf-8")
        self.assertIn("[KERNEL_PATCH]", shell)
        self.assertIn("git -C \"${kernel_src}\" apply --unidiff-zero --check", shell)
        self.assertIn('document.update(json.loads(R1_CONFIG.read_text', builder)
        self.assertIn('command.append(self.wsl_path(REPO / str(patch["relative"])))', builder)
        for forbidden in ("saveenv", "setenforce 0", "permissive", "dtbo.fex="):
            self.assertNotIn(forbidden, shell + builder)

    def test_03_candidate_report_when_built(self) -> None:
        result_path = CANDIDATE / "build-result.json"
        if not result_path.is_file():
            self.skipTest("M8B rc-core-r2 candidate has not been built")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        firmware = Path(result["firmware"]["path"])
        self.assertEqual(result["firmware"]["sha256"], digest(firmware))
        self.assertEqual(self.config["kernel_repeat_patch"], result["kernel_repeat_patch"])
        self.assertEqual(
            ["boot/kernel", "boot.fex", "Vboot.fex", "system_a", "super.fex", "Vsuper.fex", "vbmeta_system.fex", "Vvbmeta_system.fex"],
            result["payload_delta"],
        )
        validation = result["native_input_validation"]
        self.assertEqual([], validation["unexpected_system_differences"])
        self.assertEqual("disabled", validation["multi_ir_init_state"])
        self.assertFalse(validation["uinput_runtime_dependency"])
        self.assertTrue(result["boot_validation"]["stock_ramdisk_unchanged"])
        self.assertTrue(result["boot_validation"]["vendor_boot_unchanged"])
        source_diff = (CANDIDATE / "kernel-build" / "kernel-source.diff").read_text(encoding="utf-8")
        self.assertIn("drivers/media/rc/rc-main.c", source_diff)
        self.assertIn("drivers/media/rc/rc-sunxi-keymaps.c", source_diff)
        self.assertNotIn("ir-nec-decoder", source_diff)


if __name__ == "__main__":
    unittest.main()
