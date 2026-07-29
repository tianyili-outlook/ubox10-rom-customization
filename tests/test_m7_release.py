"""Validate the machine-readable M7 release composition."""

from __future__ import annotations

import json
from pathlib import Path
import re
import unittest


REPO = Path(__file__).resolve().parents[1]
RELEASE_PATH = REPO / "configs" / "releases" / "m7.json"
HEX64 = re.compile(r"^[0-9A-F]{64}$")


class M7ReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.release = json.loads(RELEASE_PATH.read_text(encoding="utf-8"))

    def test_release_shape_and_identity(self) -> None:
        self.assertEqual(
            {
                "schema_version",
                "release_id",
                "status",
                "completed_at",
                "target",
                "firmware",
                "userdata",
                "documentation",
                "distribution",
            },
            set(self.release),
        )
        self.assertEqual(1, self.release["schema_version"])
        self.assertEqual("m7", self.release["release_id"])
        self.assertEqual("stable", self.release["status"])
        self.assertEqual("2026-07-29", self.release["completed_at"])
        self.assertEqual(31, self.release["target"]["android_sdk"])
        self.assertEqual("armeabi-v7a", self.release["target"]["primary_abi"])

    def test_firmware_matches_candidate_and_projectivy_lock(self) -> None:
        firmware = self.release["firmware"]
        candidate_path = REPO / firmware["config"]
        candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
        self.assertEqual(firmware["candidate_id"], candidate["candidate_id"])
        self.assertEqual(
            Path(firmware["image"]).name,
            candidate["firmware_filename"],
        )
        self.assertEqual(2005954560, firmware["bytes"])
        self.assertRegex(firmware["sha256"], HEX64)
        self.assertEqual(
            "6A52F3388E9ABF6AFA8A701CFD7198FE6C0090F16531F6E3BD3949E760892EC8",
            firmware["sha256"],
        )

        self.assertEqual(1, len(firmware["system_app_source_locks"]))
        source_lock = json.loads(
            (REPO / firmware["system_app_source_locks"][0]).read_text(
                encoding="utf-8"
            )
        )
        injections = candidate["system_app_injections"]
        self.assertEqual(1, len(injections))
        self.assertEqual(source_lock["local_path"], injections[0]["source"])
        self.assertEqual(source_lock["sha256"], injections[0]["sha256"])

        official = firmware["official_source"]
        self.assertEqual("x12-1024.img", official["image"])
        self.assertEqual(2018890752, official["bytes"])
        self.assertRegex(official["sha256"], HEX64)
        self.assertEqual(
            "371A653604618E8B78786F279EA6F64E5D1028B430C9B41F330B08456A264065",
            official["sha256"],
        )

    def test_userdata_matches_bundle_and_guided_installer(self) -> None:
        userdata = self.release["userdata"]
        bundle = json.loads(
            (REPO / userdata["config"]).read_text(encoding="utf-8")
        )
        self.assertEqual(userdata["bundle_id"], bundle["bundle_id"])
        self.assertEqual(
            self.release["firmware"]["candidate_id"],
            bundle["baseline"]["candidate_id"],
        )
        self.assertEqual(
            ["com.softmedia.receiver.lite"],
            userdata["play_managed_packages"],
        )
        self.assertIn("--guided-after-flash", userdata["guided_command"])
        self.assertIn("<TV_IP>:7896", userdata["guided_command"])
        self.assertTrue((REPO / userdata["installer"]).is_file())
        for app in bundle["apps"]:
            self.assertTrue(app["download_url"].startswith("https://"))
            self.assertEqual(app["filename"], Path(app["local_path"]).name)
            self.assertRegex(app["sha256"], HEX64)
            self.assertRegex(app["signer_sha256"], HEX64)

    def test_release_documents_exist_and_binaries_are_not_claimed(self) -> None:
        for path in self.release["documentation"].values():
            self.assertTrue((REPO / path).is_file(), path)
        distribution = self.release["distribution"]
        self.assertIs(False, distribution["firmware_in_git"])
        self.assertIs(False, distribution["third_party_apks_in_git"])


if __name__ == "__main__":
    unittest.main()
