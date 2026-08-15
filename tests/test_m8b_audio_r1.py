from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "configs" / "candidates" / "m8b-audio-r1.json"
R5 = REPO / "out" / "candidates" / "m8b-rc-core-r5"
CANDIDATE = REPO / "out" / "candidates" / "m8b-audio-r1"


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest().upper()


class M8BAudioR1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))

    def test_01_single_vndk_contract_variable(self) -> None:
        self.assertEqual("m8b-audio-r1", self.config["id"])
        self.assertEqual("configs/candidates/m8b-rc-core-r5.json", self.config["parent_config_relative"])
        self.assertEqual("out/candidates/m8b-rc-core-r5/x12-m8b-rc-core-r5.img", self.config["base_candidate_relative"])
        reference = self.config["reference_vndk"]
        self.assertEqual("/system/apex/com.android.vndk.current", reference["source_path"])
        self.assertEqual(reference["source_path"], reference["destination_path"])
        self.assertEqual("com.android.vndk.v31", reference["runtime_name"])
        self.assertEqual("BB5393CE70CD1A4AD9ED62814339CA3695788532242708B0D46DAED87D603623", reference["libaudioroute"]["sha256"])

    def test_02_import_is_complete_and_does_not_patch_audio_topology(self) -> None:
        builder = (REPO / "scripts" / "build-m8b-audio-r1-candidate.py").read_text(encoding="utf-8")
        installer = (REPO / "scripts" / "import-m8-test8r2-vndk-apex.sh").read_text(encoding="utf-8")
        self.assertIn('cp -a --preserve=all "$source_dir" "$target_dir"', installer)
        self.assertIn("com.android.vndk.current", builder)
        self.assertIn("libaudioroute.so", builder)
        text = (builder + "\n" + installer).lower()
        for forbidden in (
            "audio_mixer_paths.xml",
            "audio_platform_info.xml",
            "/vendor/lib/libaudioroute.so",
            "device tree",
            "machine driver",
        ):
            self.assertNotIn(forbidden, text)

    def test_03_candidate_report_when_built(self) -> None:
        result_path = CANDIDATE / "build-result.json"
        if not result_path.is_file():
            self.skipTest("M8B audio-r1 candidate has not been built")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        r5_result = json.loads((R5 / "build-result.json").read_text(encoding="utf-8"))
        firmware = Path(result["firmware"]["path"])
        self.assertEqual(result["firmware"]["sha256"], digest(firmware))
        self.assertEqual(r5_result["boot"]["sha256"], result["boot"]["sha256"])
        for partition in ("vendor_a", "product_a", "vendor_dlkm_a"):
            self.assertEqual(result["logical_before"][partition]["sha256"], result["logical_after"][partition]["sha256"])
        self.assertEqual(
            ["system_a", "super.fex", "Vsuper.fex", "vbmeta_system.fex", "Vvbmeta_system.fex"],
            result["payload_delta"],
        )

        filesystem = json.loads((CANDIDATE / "audio-vndk-filesystem-validation.json").read_text(encoding="utf-8"))
        self.assertTrue(filesystem["copied_exactly"])
        self.assertEqual(145, filesystem["entries"])
        self.assertEqual([], filesystem["unexpected_system_differences"])
        self.assertEqual(self.config["reference_vndk"]["libaudioroute"]["sha256"], filesystem["libaudioroute"]["sha256"])

        linker = result["audio_vndk_validation"]
        self.assertEqual([], linker["hal"]["missing"])
        self.assertEqual([], linker["libaudioroute"]["missing"])
        self.assertTrue(linker["namespace"]["candidate_restores_identical_linkerconfig_input_apex"])
        self.assertTrue(linker["dependency_closure_resolved"])
        audit = json.loads((CANDIDATE / "outer-payload-audit.json").read_text(encoding="utf-8"))
        actions = {item["filename"]: item["action"] for item in audit["payloads"]}
        self.assertEqual("preserved", actions["boot.fex"])
        self.assertEqual("preserved", actions["vendor_boot.fex"])


if __name__ == "__main__":
    unittest.main()
