"""Tests for the source-locked Test9.3 userdata app installer."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "install-userdata-apps.py"
CONFIG = REPO / "configs" / "apps" / "test9.3-userdata-apps.json"
SPEC = importlib.util.spec_from_file_location("userdata_app_installer", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


class UserdataAppInstallerTests(unittest.TestCase):
    def test_real_bundle_has_locked_default_set(self) -> None:
        bundle = installer.load_bundle(CONFIG)
        selected = installer.select_apps(bundle, None)
        self.assertEqual(
            [
                "smarttube-beta",
                "kodi",
                "jellyfin-tv",
                "moonlight",
                "anexplorer-tv",
            ],
            [app["id"] for app in selected],
        )
        self.assertEqual(
            len(bundle["apps"]),
            len({app["package"] for app in bundle["apps"]}),
        )
        for app in bundle["apps"]:
            self.assertEqual(64, len(app["sha256"]))
            self.assertEqual(64, len(app["signer_sha256"]))
            self.assertTrue(app["download_url"].startswith("https://"))

    def test_parse_badging(self) -> None:
        output = """\
package: name='org.example.tv' versionCode='42' versionName='1.2.3'
sdkVersion:'21'
targetSdkVersion:'34'
launchable-activity: name='org.example.tv.MainActivity' label='' icon=''
native-code: 'arm64-v8a' 'armeabi-v7a'
"""
        self.assertEqual(
            {
                "package": "org.example.tv",
                "version_code": 42,
                "version_name": "1.2.3",
                "min_sdk": 21,
                "target_sdk": 34,
                "launch_activity": "org.example.tv.MainActivity",
                "native_abis": ["arm64-v8a", "armeabi-v7a"],
            },
            installer.parse_badging(output),
        )

    def test_parse_signer_normalizes_case(self) -> None:
        digest = "ab" * 32
        output = f"Signer #1 certificate SHA-256 digest: {digest}\n"
        self.assertEqual(digest.upper(), installer.parse_signer(output))

    def test_metadata_mismatch_is_rejected(self) -> None:
        app = installer.load_bundle(CONFIG)["apps"][0]
        metadata = {
            "package": app["package"],
            "version_code": app["version_code"] + 1,
            "version_name": app["version_name"],
            "min_sdk": app["min_sdk"],
            "target_sdk": app["target_sdk"],
            "launch_activity": app["launch_activity"],
            "native_abis": app["native_abis"],
        }
        with self.assertRaisesRegex(installer.InstallError, "version_code mismatch"):
            installer.verify_metadata(app, metadata)

    def test_unknown_selection_is_rejected(self) -> None:
        bundle = installer.load_bundle(CONFIG)
        with self.assertRaisesRegex(installer.InstallError, "unknown app"):
            installer.select_apps(bundle, ["does-not-exist"])

    def test_local_path_escape_is_rejected(self) -> None:
        raw = json.loads(CONFIG.read_text(encoding="utf-8"))
        raw["apps"][0]["local_path"] = "README.md"
        work = REPO / "work"
        work.mkdir(exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            dir=work,
            delete=False,
        ) as handle:
            json.dump(raw, handle)
            temp_path = Path(handle.name)
        self.addCleanup(temp_path.unlink, missing_ok=True)
        with self.assertRaisesRegex(installer.InstallError, "work/preinstall_apks"):
            installer.load_bundle(temp_path)

    def test_local_path_basename_must_match_filename(self) -> None:
        raw = json.loads(CONFIG.read_text(encoding="utf-8"))
        raw["apps"][0]["local_path"] = (
            "work/preinstall_apks/incoming/different-name.apk"
        )
        work = REPO / "work"
        work.mkdir(exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            dir=work,
            delete=False,
        ) as handle:
            json.dump(raw, handle)
            temp_path = Path(handle.name)
        self.addCleanup(temp_path.unlink, missing_ok=True)
        with self.assertRaisesRegex(
            installer.InstallError,
            "basename must equal filename",
        ):
            installer.load_bundle(temp_path)

    def test_duplicate_package_is_rejected(self) -> None:
        raw = json.loads(CONFIG.read_text(encoding="utf-8"))
        duplicate = copy.deepcopy(raw["apps"][0])
        duplicate["id"] = "duplicate-id"
        duplicate["local_path"] = (
            "work/preinstall_apks/incoming/duplicate-does-not-need-to-exist.apk"
        )
        raw["apps"].append(duplicate)
        work = REPO / "work"
        work.mkdir(exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            dir=work,
            delete=False,
        ) as handle:
            json.dump(raw, handle)
            temp_path = Path(handle.name)
        self.addCleanup(temp_path.unlink, missing_ok=True)
        with self.assertRaisesRegex(installer.InstallError, "duplicate package"):
            installer.load_bundle(temp_path)

    def test_installed_version_parser(self) -> None:
        output = """\
Packages:
  Package [org.example.tv] (123):
    versionCode=99 minSdk=21 targetSdk=34
    versionName=4.5.6
"""
        self.assertEqual((99, "4.5.6"), installer.installed_version(output))
        self.assertIsNone(installer.installed_version("Unable to find package"))

    def test_installed_base_apk_prefers_base_split(self) -> None:
        output = """\
package:/data/app/~~abc/org.example-xyz/split_config.en.apk
package:/data/app/~~abc/org.example-xyz/base.apk
"""
        self.assertEqual(
            "/data/app/~~abc/org.example-xyz/base.apk",
            installer.installed_base_apk(output),
        )

    def test_installed_base_apk_rejects_shell_metacharacters(self) -> None:
        with self.assertRaisesRegex(installer.InstallError, "unsafe characters"):
            installer.installed_base_apk(
                "package:/data/app/org.example/base.apk;reboot\n"
            )

    def test_missing_package_path_accepts_pm_exit_one(self) -> None:
        result = installer.subprocess.CompletedProcess(
            args=["adb"], returncode=1, stdout="", stderr=""
        )
        with mock.patch.object(installer, "adb_run", return_value=result):
            self.assertEqual(
                "",
                installer.package_path(
                    Path("adb"), "device", "org.example.missing"
                ),
            )

    def test_guided_play_setup_opens_store_and_records_version(self) -> None:
        completed = installer.subprocess.CompletedProcess(
            args=["adb"], returncode=0, stdout="Status: ok", stderr=""
        )
        prompts: list[str] = []
        with (
            mock.patch.object(installer, "adb_run", return_value=completed) as adb_run,
            mock.patch.object(
                installer,
                "package_path",
                side_effect=["", "package:/data/app/example/base.apk"],
            ),
            mock.patch.object(
                installer,
                "adb_shell",
                return_value="versionCode=2020164765\nversionName=5.1.7\n",
            ),
        ):
            result = installer.guided_play_setup(
                Path("adb"),
                "device",
                input_fn=lambda prompt: prompts.append(prompt),
            )
        self.assertEqual("play-installed", result["status"])
        self.assertEqual("5.1.7", result["version_name"])
        self.assertEqual(2020164765, result["version_code"])
        self.assertEqual(1, len(prompts))
        command = adb_run.call_args.args[2]
        self.assertIn(installer.AIRRECEIVER_LITE_MARKET_URI, command)
        self.assertIn(installer.PLAY_STORE_PACKAGE, command)

    def test_guided_play_setup_skips_store_when_lite_is_installed(self) -> None:
        prompts: list[str] = []
        with (
            mock.patch.object(installer, "adb_run") as adb_run,
            mock.patch.object(
                installer,
                "package_path",
                return_value="package:/data/app/example/base.apk",
            ),
            mock.patch.object(
                installer,
                "adb_shell",
                return_value="versionCode=2020164765\nversionName=5.1.7\n",
            ),
        ):
            result = installer.guided_play_setup(
                Path("adb"),
                "device",
                input_fn=lambda prompt: prompts.append(prompt),
            )
        self.assertEqual("already-installed", result["status"])
        self.assertEqual("5.1.7", result["version_name"])
        self.assertEqual([], prompts)
        adb_run.assert_not_called()

    def test_guided_play_setup_requires_lite_install(self) -> None:
        completed = installer.subprocess.CompletedProcess(
            args=["adb"], returncode=0, stdout="Status: ok", stderr=""
        )
        with (
            mock.patch.object(installer, "adb_run", return_value=completed),
            mock.patch.object(installer, "package_path", side_effect=["", ""]),
        ):
            with self.assertRaisesRegex(
                installer.InstallError,
                "AirReceiverLite is not installed",
            ):
                installer.guided_play_setup(
                    Path("adb"),
                    "device",
                    input_fn=lambda _prompt: None,
                )

    def test_guided_mode_rejects_partial_selection(self) -> None:
        args = installer.parse_args(
            ["--guided-after-flash", "--app", "kodi"]
        )
        with self.assertRaisesRegex(
            installer.InstallError,
            "complete default bundle",
        ):
            installer.validate_args(args)

    def test_download_artifact_is_atomic_and_hash_locked(self) -> None:
        payload = b"locked apk payload"
        app = {
            "id": "example",
            "download_url": "https://example.invalid/example.apk",
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest().upper(),
        }
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        response.geturl.return_value = app["download_url"]
        response.headers = {"Content-Length": str(len(payload))}
        response.read.side_effect = [payload, b""]
        with tempfile.TemporaryDirectory(dir=REPO / "work") as temp_dir:
            destination = Path(temp_dir) / "example.apk"
            with mock.patch.object(installer, "urlopen", return_value=response):
                result = installer.download_artifact(app, destination)
            self.assertEqual("downloaded", result["status"])
            self.assertEqual(payload, destination.read_bytes())
            self.assertEqual([], list(destination.parent.glob("*.part")))

    def test_download_artifact_rejects_hash_mismatch(self) -> None:
        payload = b"unexpected"
        app = {
            "id": "example",
            "download_url": "https://example.invalid/example.apk",
            "bytes": len(payload),
            "sha256": "0" * 64,
        }
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        response.geturl.return_value = app["download_url"]
        response.headers = {"Content-Length": str(len(payload))}
        response.read.side_effect = [payload, b""]
        with tempfile.TemporaryDirectory(dir=REPO / "work") as temp_dir:
            destination = Path(temp_dir) / "example.apk"
            with (
                mock.patch.object(installer, "urlopen", return_value=response),
                self.assertRaisesRegex(
                    installer.InstallError,
                    "does not match the source lock",
                ),
            ):
                installer.download_artifact(app, destination)
            self.assertFalse(destination.exists())
            self.assertEqual([], list(destination.parent.glob("*.part")))


if __name__ == "__main__":
    unittest.main()
