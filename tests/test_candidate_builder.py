"""Regression tests for candidate configuration and path safety."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "build-candidate-firmware.py"
SPEC = importlib.util.spec_from_file_location("candidate_builder", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class CandidateBuilderTests(unittest.TestCase):
    def test_known_contacts_provider_removal_is_rejected(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "BluetoothPbapService"):
            builder.load_candidate_config(
                REPO / "configs" / "candidates" / "test8-remove-vendor-home-wizard-cast.json"
            )

    def test_test8r2_preserves_contacts_provider(self) -> None:
        config = builder.load_candidate_config(
            REPO / "configs" / "candidates" / "test8r2-restore-contacts-provider.json"
        )
        self.assertNotIn("/system/priv-app/ContactsProvider", config["remove_roots"])

    def test_injected_apk_expected_paths_include_parent(self) -> None:
        config = builder.load_candidate_config(
            REPO / "configs" / "candidates" / "test8r2-restore-contacts-provider.json"
        )
        added = builder.expected_added_paths(config, {"/", "/system", "/system/app"})
        self.assertEqual(
            {
                "/system/app/ProjectivyLauncher",
                "/system/app/ProjectivyLauncher/ProjectivyLauncher.apk",
            },
            added,
        )

    def test_test9a_adds_only_the_leanback_feature_file(self) -> None:
        config = builder.load_candidate_config(
            REPO / "configs" / "candidates" / "test9a-add-leanback-feature.json"
        )
        added = builder.expected_added_paths(
            config,
            {"/", "/system", "/system/app", "/system/etc", "/system/etc/permissions"},
        )
        self.assertEqual(
            {
                "/system/app/ProjectivyLauncher",
                "/system/app/ProjectivyLauncher/ProjectivyLauncher.apk",
                "/system/etc/permissions/android.software.leanback.xml",
            },
            added,
        )
        self.assertEqual([], [
            injection
            for injection in config["system_file_injections"]
            if injection["destination"]
            != "/system/etc/permissions/android.software.leanback.xml"
        ])

    def test_test9b_adds_only_leanback_only_beyond_test9a(self) -> None:
        test9a = builder.load_candidate_config(
            REPO / "configs" / "candidates" / "test9a-add-leanback-feature.json"
        )
        test9b = builder.load_candidate_config(
            REPO / "configs" / "candidates" / "test9b-add-leanback-only-feature.json"
        )
        test9a_destinations = {
            injection["destination"] for injection in test9a["system_file_injections"]
        }
        test9b_destinations = {
            injection["destination"] for injection in test9b["system_file_injections"]
        }
        self.assertEqual(
            {"/system/etc/permissions/android.software.leanback_only.xml"},
            test9b_destinations - test9a_destinations,
        )

    def test_test9w1_is_test8r2_plus_one_preconditioned_driver_patch(self) -> None:
        test8r2 = builder.load_candidate_config(
            REPO / "configs" / "candidates" / "test8r2-restore-contacts-provider.json"
        )
        test9w1 = builder.load_candidate_config(
            REPO / "configs" / "candidates" / "test9w1-disable-aic-ant-div.json"
        )
        self.assertEqual(test8r2["remove_roots"], test9w1["remove_roots"])
        self.assertEqual(test8r2["system_properties"], test9w1["system_properties"])
        self.assertEqual(
            [
                {
                    key: value
                    for key, value in injection.items()
                    if not key.startswith("_")
                }
                for injection in test8r2["system_app_injections"]
            ],
            [
                {
                    key: value
                    for key, value in injection.items()
                    if not key.startswith("_")
                }
                for injection in test9w1["system_app_injections"]
            ],
        )
        self.assertEqual(
            [
                {
                    "path": "/lib/modules/aic8800_fdrv.ko",
                    "source_sha256": (
                        "0D713BDAD88323EF4230248DE56416269035561A3254E155C80F601C5FA5FD44"
                    ),
                    "offset": 0x2949,
                    "before_hex": "01",
                    "after_hex": "00",
                    "result_sha256": (
                        "DB43E76827FC2463A0AB54432B22A83D5045722E9C6C84BBEF96A4E1AFE8505B"
                    ),
                }
            ],
            test9w1["vendor_dlkm_binary_patches"],
        )

    def test_test9r1_is_test8r2_plus_only_the_remote_service_stack(self) -> None:
        test8r2 = builder.load_candidate_config(
            REPO / "configs" / "candidates" / "test8r2-restore-contacts-provider.json"
        )
        test9r1 = builder.load_candidate_config(
            REPO
            / "configs"
            / "candidates"
            / "test9r1-android-tv-remote-service.json"
        )
        self.assertEqual(test8r2["remove_roots"], test9r1["remove_roots"])
        self.assertEqual(test8r2["system_properties"], test9r1["system_properties"])
        self.assertNotIn("vendor_dlkm_binary_patches", test9r1)

        base_apks = {
            injection["destination"] for injection in test8r2["system_app_injections"]
        }
        remote_apks = {
            injection["destination"] for injection in test9r1["system_app_injections"]
        }
        self.assertEqual(
            {
                "/system/priv-app/AndroidTvRemoteService/AndroidTvRemoteService.apk"
            },
            remote_apks - base_apks,
        )

        file_destinations = {
            injection["destination"] for injection in test9r1["system_file_injections"]
        }
        self.assertEqual(
            {
                "/system/etc/permissions/android.software.leanback.xml",
                "/system/etc/permissions/com.android.media.tv.remoteprovider.xml",
                (
                    "/system/etc/permissions/"
                    "privapp-permissions-com.google.android.tv.remote.service.xml"
                ),
                "/system/framework/com.android.media.tv.remoteprovider.jar",
                "/system/overlay/UBOX10TvRemoteConfigOverlay.apk",
            },
            file_destinations,
        )
        self.assertNotIn(
            "/system/etc/permissions/android.software.leanback_only.xml",
            file_destinations,
        )

        added = builder.expected_added_paths(
            test9r1,
            {
                "/",
                "/system",
                "/system/app",
                "/system/priv-app",
                "/system/etc",
                "/system/etc/permissions",
                "/system/framework",
            },
        )
        self.assertEqual(
            {
                "/system/app/ProjectivyLauncher",
                "/system/app/ProjectivyLauncher/ProjectivyLauncher.apk",
                "/system/priv-app/AndroidTvRemoteService",
                (
                    "/system/priv-app/AndroidTvRemoteService/"
                    "AndroidTvRemoteService.apk"
                ),
                "/system/etc/permissions/android.software.leanback.xml",
                "/system/etc/permissions/com.android.media.tv.remoteprovider.xml",
                (
                    "/system/etc/permissions/"
                    "privapp-permissions-com.google.android.tv.remote.service.xml"
                ),
                "/system/framework/com.android.media.tv.remoteprovider.jar",
                "/system/overlay",
                "/system/overlay/UBOX10TvRemoteConfigOverlay.apk",
            },
            added,
        )

    def test_test9r2_changes_only_the_test9r1_rro_scan_path(self) -> None:
        test9r1 = builder.load_candidate_config(
            REPO
            / "configs"
            / "candidates"
            / "test9r1-android-tv-remote-service.json"
        )
        test9r2 = builder.load_candidate_config(
            REPO
            / "configs"
            / "candidates"
            / "test9r2-android-tv-remote-service-rro-path.json"
        )

        self.assertEqual(test9r1["remove_roots"], test9r2["remove_roots"])
        self.assertEqual(test9r1["system_properties"], test9r2["system_properties"])
        self.assertEqual(
            [
                {
                    key: value
                    for key, value in injection.items()
                    if not key.startswith("_")
                }
                for injection in test9r1["system_app_injections"]
            ],
            [
                {
                    key: value
                    for key, value in injection.items()
                    if not key.startswith("_")
                }
                for injection in test9r2["system_app_injections"]
            ],
        )
        self.assertNotIn("vendor_dlkm_binary_patches", test9r2)

        r1_files = {
            injection["source"]: {
                key: value
                for key, value in injection.items()
                if not key.startswith("_")
            }
            for injection in test9r1["system_file_injections"]
        }
        r2_files = {
            injection["source"]: {
                key: value
                for key, value in injection.items()
                if not key.startswith("_")
            }
            for injection in test9r2["system_file_injections"]
        }
        self.assertEqual(set(r1_files), set(r2_files))
        overlay_source = "work/system_injections/UBOX10TvRemoteConfigOverlay.apk"
        for source in sorted(set(r1_files) - {overlay_source}):
            self.assertEqual(r1_files[source], r2_files[source])
        self.assertEqual(
            "/system/overlay/UBOX10TvRemoteConfigOverlay.apk",
            r1_files[overlay_source]["destination"],
        )
        self.assertEqual(
            "/system/system_ext/overlay/UBOX10TvRemoteConfigOverlay.apk",
            r2_files[overlay_source]["destination"],
        )
        self.assertEqual(
            r1_files[overlay_source]["sha256"],
            r2_files[overlay_source]["sha256"],
        )

        added = builder.expected_added_paths(
            test9r2,
            {
                "/",
                "/system",
                "/system/app",
                "/system/priv-app",
                "/system/etc",
                "/system/etc/permissions",
                "/system/framework",
                "/system/system_ext",
            },
        )
        self.assertIn("/system/system_ext/overlay", added)
        self.assertIn(
            "/system/system_ext/overlay/UBOX10TvRemoteConfigOverlay.apk",
            added,
        )
        self.assertNotIn("/system/overlay", added)

    def test_legacy_system_overlay_path_is_historical_test9r1_only(self) -> None:
        source = (
            REPO
            / "configs"
            / "candidates"
            / "test9r2-android-tv-remote-service-rro-path.json"
        )
        config = json.loads(source.read_text(encoding="utf-8"))
        for injection in config["system_file_injections"]:
            if injection["source"].endswith("UBOX10TvRemoteConfigOverlay.apk"):
                injection["destination"] = (
                    "/system/overlay/UBOX10TvRemoteConfigOverlay.apk"
                )
                break
        else:
            self.fail("Test9r2 overlay injection is missing")

        with tempfile.TemporaryDirectory(dir=REPO / "work") as temp_dir:
            path = Path(temp_dir) / "unsafe-rro-path.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "allowed only for historical Test9r1 reproduction",
            ):
                builder.load_candidate_config(path)

    def test_binary_patch_requires_exact_original_bytes(self) -> None:
        patch = {
            "path": "/lib/modules/example.ko",
            "offset": 1,
            "before_hex": "01",
            "after_hex": "00",
        }
        self.assertEqual(b"\xAA\x00\xBB", builder.apply_binary_patch(b"\xAA\x01\xBB", patch))
        with self.assertRaisesRegex(RuntimeError, "precondition failed"):
            builder.apply_binary_patch(b"\xAA\x02\xBB", patch)

    def test_wsl_path_uses_current_windows_workspace(self) -> None:
        path = builder.wsl_path(REPO / "tools" / "avbtool.py")
        self.assertTrue(path.startswith("/mnt/c/"))
        self.assertTrue(path.endswith("/tools/avbtool.py"))

    def test_failed_transaction_removes_staging_and_publishes_nothing(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO / "out") as directory:
            parent = Path(directory)
            final_out = parent / "test-transaction"
            config = {"candidate_id": "test-transaction"}
            with mock.patch.object(
                builder, "build_in_staging", side_effect=RuntimeError("simulated failure")
            ):
                with self.assertRaisesRegex(RuntimeError, "simulated failure"):
                    builder.transactional_build(config, final_out, "/unused")
            self.assertFalse(final_out.exists())
            self.assertEqual([], list(parent.iterdir()))

    @unittest.skipUnless(os.name == "nt", "Windows ACL inheritance test")
    def test_staging_directory_inherits_parent_acl(self) -> None:
        parent = REPO / "out" / "candidates"
        staging = builder.create_staging_directory(parent, "acl-inheritance-test")
        try:
            result = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-Command",
                    f"(Get-Acl -LiteralPath '{staging}').AreAccessRulesProtected",
                ],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=True,
            )
            self.assertEqual("False", result.stdout.strip())
        finally:
            shutil.rmtree(staging)


if __name__ == "__main__":
    unittest.main()
