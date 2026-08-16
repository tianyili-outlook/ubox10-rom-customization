#!/usr/bin/env python3
"""Build the minimal Google TV Remote v2 receiver on accepted m8b-ime-r1."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import zipfile


REPO = Path(__file__).resolve().parents[1]
IME_BUILDER = REPO / "scripts" / "build-m8b-ime-r1-candidate.py"
DEFAULT_CONFIG = REPO / "configs" / "candidates" / "m8b-remote-r1.json"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load module: " + str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ime = load_module(IME_BUILDER, "m8b_ime_r1_for_remote")
base = ime.base


class BuildM8BRemoteR1(base.BuildR9):
    def __init__(self, config: dict[str, object], keep_failed: bool) -> None:
        super().__init__(config, keep_failed)
        self.aosp_artifacts: dict[str, Path] = {}

    def setup(self) -> None:
        base.BuildR9.setup(self)
        integration = self.config["integration"]
        service = self.config["remote_service"]
        tools = self.config["apk_tools"]
        assert isinstance(integration, dict) and isinstance(service, dict) and isinstance(tools, dict)

        patch = REPO / str(integration["patch_relative"])
        installer = REPO / str(integration["install_script_relative"])
        if not patch.is_file() or base.digest(patch) != integration["patch_sha256"]:
            raise RuntimeError("Remote AOSP integration patch identity mismatch")
        if not installer.is_file() or base.digest(installer) != integration["install_script_sha256"]:
            raise RuntimeError("Remote install script identity mismatch")

        source_root = REPO / str(integration["source_root_relative"])
        source_files = integration["source_files"]
        assert isinstance(source_files, dict)
        for relative, expected in source_files.items():
            path = source_root / str(relative)
            if not path.is_file() or base.digest(path) != expected:
                raise RuntimeError("Remote integration source identity mismatch: " + str(path))

        donor = REPO / str(service["donor_relative"])
        if not donor.is_file() or base.record(donor) != {
            "path": str(donor), "size": service["donor_size"], "sha256": service["donor_sha256"]
        }:
            raise RuntimeError("Google Remote Service donor identity mismatch")

        for key in ("aapt2", "apksigner", "java"):
            path = REPO / str(tools[key + "_relative"])
            if not path.is_file() or base.digest(path) != tools[key + "_sha256"]:
                raise RuntimeError("APK inspection tool identity mismatch: " + key)

        aosp_checks: dict[str, str] = {
            str(integration["aosp_product_config_path"]): str(integration["aosp_product_config_sha256"])
        }
        for relative, expected in source_files.items():
            aosp_checks[str(integration["aosp_remote_root"]) + "/" + str(relative)] = str(expected)
        outputs = integration["aosp_outputs"]
        assert isinstance(outputs, dict)
        for path, spec in outputs.items():
            assert isinstance(spec, dict)
            aosp_checks[str(path)] = str(spec["sha256"])

        hashes = self.stage / "aosp-remote-sha256.txt"
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "--", "sha256sum", *aosp_checks], output=hashes)
        observed = {
            line.split("  ", 1)[1]: line.split()[0].upper()
            for line in hashes.read_text(encoding="utf-8").splitlines()
        }
        for path, expected in aosp_checks.items():
            if observed.get(path) != expected:
                raise RuntimeError("AOSP Remote artifact identity mismatch: " + path)

        copied = self.stage / "aosp-remote-output"
        copied.mkdir()
        for index, (path, spec) in enumerate(outputs.items()):
            assert isinstance(spec, dict)
            target = copied / (str(index) + "-" + Path(str(path)).name)
            self.run(["wsl.exe", "-d", "Ubuntu-24.04", "--", "cp", str(path), self.wsl_path(target)])
            if target.stat().st_size != spec["size"] or base.digest(target) != spec["sha256"]:
                raise RuntimeError("copied AOSP Remote output identity mismatch: " + str(path))
            self.aosp_artifacts[Path(str(path)).name] = target

        self.validate_apks_and_permissions()
        report = {
            "normal_aosp_modules": [
                "AndroidTvRemoteService", "UBOX10TvRemoteConfigOverlay",
                "privapp-permissions-com.google.android.tv.remote.service",
                "default-permissions-com.google.android.tv.remote.service",
            ],
            "aosp_builds": ["systemimage", "systemextimage"],
            "aosp_build_status": "PASS",
            "provider_module_reused_from_accepted_system": True,
            "donor_preserved_byte_for_byte": True,
            "rro_partition": "system_ext",
            "default_runtime_permissions": service["default_runtime_permissions"],
            "broader_bluetooth_default_grants": [],
        }
        (self.stage / "aosp-remote-integration-validation.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )

    def validate_apks_and_permissions(self) -> None:
        service = self.config["remote_service"]
        integration = self.config["integration"]
        tools = self.config["apk_tools"]
        assert isinstance(service, dict) and isinstance(integration, dict) and isinstance(tools, dict)
        aapt2 = REPO / str(tools["aapt2_relative"])
        java = REPO / str(tools["java_relative"])
        apksigner = REPO / str(tools["apksigner_relative"])
        donor = self.aosp_artifacts["AndroidTvRemoteService.apk"]
        rro = self.aosp_artifacts["UBOX10TvRemoteConfigOverlay.apk"]

        donor_badging = self.stage / "remote-service-badging.txt"
        donor_manifest = self.stage / "remote-service-manifest.txt"
        donor_signature = self.stage / "remote-service-signature.txt"
        rro_badging = self.stage / "remote-rro-badging.txt"
        rro_resources = self.stage / "remote-rro-resources.txt"
        rro_manifest = self.stage / "remote-rro-manifest.txt"
        self.run([str(aapt2), "dump", "badging", str(donor)], output=donor_badging)
        self.run([str(aapt2), "dump", "xmltree", "--file", "AndroidManifest.xml", str(donor)], output=donor_manifest)
        self.run([str(java), "-jar", str(apksigner), "verify", "--verbose", "--print-certs", str(donor)], output=donor_signature)
        self.run([str(aapt2), "dump", "badging", str(rro)], output=rro_badging)
        self.run([str(aapt2), "dump", "resources", str(rro)], output=rro_resources)
        self.run([str(aapt2), "dump", "xmltree", "--file", "AndroidManifest.xml", str(rro)], output=rro_manifest)

        badging = donor_badging.read_text(encoding="utf-8", errors="replace")
        manifest = donor_manifest.read_text(encoding="utf-8", errors="replace")
        signature = donor_signature.read_text(encoding="utf-8", errors="replace")
        required_badging = [
            "package: name='com.google.android.tv.remote.service'",
            "versionCode='95855272'", "versionName='5.2.473254133'",
            "sdkVersion:'24'", "targetSdkVersion:'33'",
            "uses-library:'com.android.media.tv.remoteprovider'",
        ]
        required_manifest = [
            "com.google.android.tv.remote.service.RemoteService",
            "com.google.android.tv.remote.service.DiscoveryService",
            "com.google.android.tv.remote.service.ImeBridgeService",
            "com.google.android.tv.remote.service.AtvRemoteProviderService",
            "com.android.media.tv.remoteprovider.TvRemoteProvider",
        ]
        if any(value not in badging for value in required_badging):
            raise RuntimeError("Remote Service package/library contract mismatch")
        if any(value not in manifest for value in required_manifest):
            raise RuntimeError("Remote Service component contract mismatch")
        if service["signer_certificate_sha256"].lower() not in signature.lower() or "Verifies" not in signature:
            raise RuntimeError("Google Remote Service APK signature verification failed")
        with zipfile.ZipFile(donor) as archive:
            native = [name for name in archive.namelist() if name.startswith("lib/")]
        if native:
            raise RuntimeError("unexpected native library in ARM-independent Remote Service donor")

        source_root = REPO / str(integration["source_root_relative"])
        privapp = ET.parse(source_root / "permissions/privapp-permissions-com.google.android.tv.remote.service.xml")
        allowed = sorted(item.attrib["name"] for item in privapp.findall(".//permission"))
        expected_allowed = sorted(str(item) for item in service["requested_privileged_permissions"])
        if allowed != expected_allowed or "android.permission.INJECT_EVENTS" in allowed:
            raise RuntimeError("Remote Service privapp allowlist coverage mismatch")
        for permission in expected_allowed:
            if permission not in manifest:
                raise RuntimeError("allowlisted permission is not requested by donor: " + permission)

        defaults = ET.parse(source_root / "default-permissions/default-permissions-com.google.android.tv.remote.service.xml")
        granted = sorted(item.attrib["name"] for item in defaults.findall(".//permission"))
        if granted != sorted(str(item) for item in service["default_runtime_permissions"]):
            raise RuntimeError("Remote Service default runtime grant is not CONNECT-only")
        if any(item in granted for item in service["explicitly_not_default_granted"]):
            raise RuntimeError("unproven Bluetooth permission was default-granted")

        rro_badging_text = rro_badging.read_text(encoding="utf-8", errors="replace")
        rro_resources_text = rro_resources.read_text(encoding="utf-8", errors="replace")
        rro_manifest_text = rro_manifest.read_text(encoding="utf-8", errors="replace")
        rro_required = [
            "package: name='com.ubox10.overlay.tvremote'",
            "overlay: targetPackage='android' priority='999' isStatic='true'",
        ]
        if any(value not in rro_badging_text for value in rro_required):
            raise RuntimeError("Remote provider RRO package contract mismatch")
        if "string/config_tvRemoteServicePackage" not in rro_resources_text or str(service["provider_config_value"]) not in rro_resources_text:
            raise RuntimeError("Remote provider RRO resource value mismatch")
        if 'android:targetPackage' not in rro_manifest_text or '="android"' not in rro_manifest_text:
            raise RuntimeError("Remote provider RRO target mismatch")

        report = {
            "package": service["package"],
            "version_code": service["version_code"],
            "version_name": service["version_name"],
            "min_sdk": service["min_sdk"],
            "target_sdk": service["target_sdk"],
            "donor_sha256": service["donor_sha256"],
            "signer_certificate_sha256": service["signer_certificate_sha256"],
            "required_shared_library": "com.android.media.tv.remoteprovider",
            "services": required_manifest[:4],
            "requested_privileged_permissions": allowed,
            "signature_only_not_allowlisted": service["signature_only_not_allowlisted"],
            "default_runtime_permissions": granted,
            "not_default_granted": service["explicitly_not_default_granted"],
            "native_libraries": native,
            "rro": {
                "package": service["rro_package"], "target": service["rro_target"],
                "priority": service["rro_priority"],
                "resource": service["provider_config_resource"], "value": service["provider_config_value"],
            },
        }
        (self.stage / "remote-package-contract-validation.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )

    def repair_system(self, source: Path) -> Path:
        system = self.stage / "system_a.img"
        shutil.copyfile(source, system)
        self.run([sys.executable, str(base.TOOLS / "avbtool.py"), "erase_footer", "--image", str(system)])
        work_size = str(self.config["system_work_size"])
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "truncate", "-s", work_size, self.wsl_path(system)])
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "resize2fs", self.wsl_path(system), work_size])
        mount_dir = self.stage / "system-mount"
        mount_dir.mkdir()
        self.run([
            "wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "bash",
            self.wsl_path(REPO / str(self.config["integration"]["install_script_relative"])),
            self.wsl_path(system), self.wsl_path(mount_dir),
            self.wsl_path(self.aosp_artifacts["AndroidTvRemoteService.apk"]),
            self.wsl_path(self.aosp_artifacts["privapp-permissions-com.google.android.tv.remote.service.xml"]),
            self.wsl_path(self.aosp_artifacts["default-permissions-com.google.android.tv.remote.service.xml"]),
            self.wsl_path(self.aosp_artifacts["UBOX10TvRemoteConfigOverlay.apk"]),
        ])
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "resize2fs", "-M", self.wsl_path(system)])
        mount_dir.rmdir()

        avb = self.config["avb"]
        assert isinstance(avb, dict)
        self.run([
            sys.executable, str(base.TOOLS / "avbtool.py"), "add_hashtree_footer",
            "--image", str(system), "--partition_name", "system",
            "--partition_size", str(avb["partition_size"]), "--hash_algorithm", "sha256",
            "--salt", str(avb["salt"]), "--do_not_generate_fec",
            "--prop", "com.ubox10.candidate.id:" + self.candidate_id,
            "--prop", "com.ubox10.avb.fec:none", "--key", str(REPO / str(avb["key_relative"])),
            "--algorithm", "SHA256_RSA2048",
        ])
        if system.stat().st_size != avb["partition_size"]:
            raise RuntimeError("signed m8b-remote-r1 system_a size mismatch")
        return system

    def validate_system_diff(self, before_image: Path, after_image: Path) -> dict[str, object]:
        before = self._manifest_map(self.inventory_system(before_image, "r8-system"))
        after = self._manifest_map(self.inventory_system(after_image, "r9-system"))
        service = self.config["remote_service"]
        provider = self.config["remote_provider"]
        guard = self.config["play_regression_guard"]
        assert isinstance(service, dict) and isinstance(provider, dict) and isinstance(guard, dict)

        allowed = {
            "/system/priv-app",
            "/system/priv-app/AndroidTvRemoteService",
            str(service["destination_apk"]),
            "/system/etc",
            "/system/etc/default-permissions",
            str(service["destination_privapp"]),
            str(service["destination_default_permissions"]),
            str(service["destination_rro"]),
        }
        changed = [path for path in sorted(set(before) | set(after)) if before.get(path) != after.get(path)]
        unexpected = [path for path in changed if path not in allowed]
        if unexpected:
            raise RuntimeError("unexpected m8b-remote-r1 system differences: " + ", ".join(unexpected[:20]))

        new_targets = {
            "/system/priv-app/AndroidTvRemoteService": {"type": "directory", "mode": "0755", "uid": 0, "gid": 0},
            str(service["destination_apk"]): {"type": "regular", "mode": "0644", "uid": 0, "gid": 0, "size": service["donor_size"], "sha256": service["donor_sha256"]},
            "/system/etc/default-permissions": {"type": "directory", "mode": "0755", "uid": 0, "gid": 0},
            str(service["destination_privapp"]): {"type": "regular", "mode": "0644", "uid": 0, "gid": 0, "size": 1417, "sha256": "E46CA371727DF823E07495BE5451EF2E2A1874A7C4E7FE82A41448F966FA23F2"},
            str(service["destination_default_permissions"]): {"type": "regular", "mode": "0644", "uid": 0, "gid": 0, "size": 227, "sha256": "B28DCD3E92FD04E77ADE71F548A949828CBE5C731D608D5CED9F8BBE0955E563"},
            str(service["destination_rro"]): {"type": "regular", "mode": "0644", "uid": 0, "gid": 0, "size": 8542, "sha256": "71D60AA7A38B86269E16D42DF61DBF8FB661D42ACE14929DB7CF0571DDC314A8"},
        }
        label = "753A6F626A6563745F723A73797374656D5F66696C653A733000"
        for path, expected in new_targets.items():
            if before.get(path) is not None:
                raise RuntimeError("accepted baseline already contained Remote target: " + path)
            actual = after.get(path)
            if actual is None or any(actual.get(key) != value for key, value in expected.items()):
                raise RuntimeError("installed Remote target contract mismatch: " + path)
            if actual.get("xattrs", {}).get("security.selinux") != label:
                raise RuntimeError("installed Remote target SELinux label mismatch: " + path)

        frozen = {
            str(provider["accepted_jar_path"]): str(provider["accepted_jar_sha256"]),
            str(provider["accepted_library_xml_path"]): str(provider["accepted_library_xml_sha256"]),
            str(provider["accepted_tv_features_path"]): str(provider["accepted_tv_features_sha256"]),
            "/system/framework/framework-res.apk": str(provider["accepted_framework_res_sha256"]),
        }
        for path, expected_hash in frozen.items():
            if before.get(path) != after.get(path) or after.get(path, {}).get("sha256") != expected_hash:
                raise RuntimeError("accepted ATV framework/feature changed: " + path)
        for path in guard["forbidden_paths"]:
            if str(path).startswith("/system/") and (before.get(str(path)) is not None or after.get(str(path)) is not None):
                raise RuntimeError("unexpected Play/GMS package path: " + str(path))
        if before.get("/system/build.prop") != after.get("/system/build.prop"):
            raise RuntimeError("accepted system properties changed")

        report = {
            "base": "m8b-ime-r1 (DEVICE ACCEPTED / IME PASS)",
            "changed_paths": changed,
            "unexpected_paths": unexpected,
            "added_remote_targets": new_targets,
            "accepted_remoteprovider_and_features_reused_exactly": frozen,
            "system_build_prop_preserved": True,
            "product_partition_preserved_byte_for_byte": True,
            "leanback_ime_preserved_by_exact_product_partition": True,
            "audio_vndk_input_stack_preserved": True,
            "play_gms_packages_added": False,
            "play_compatibility_features_or_properties_changed": False,
        }
        (self.stage / "remote-system-filesystem-validation.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        return report

    def verify_filesystems(self) -> None:
        for name in ("system_a", "vendor_a", "product_a", "vendor_dlkm_a"):
            image = self.stage / "validation-logical" / (name + ".img")
            self.run(
                ["wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "e2fsck", "-fn", self.wsl_path(image)],
                output=self.stage / (name + "-e2fsck.txt"),
            )

    def finish(self, firmware: Path, super_image: Path, vbmeta_system: Path) -> None:
        integration_report = json.loads((self.stage / "aosp-remote-integration-validation.json").read_text(encoding="utf-8"))
        package_report = json.loads((self.stage / "remote-package-contract-validation.json").read_text(encoding="utf-8"))
        filesystem_report = json.loads((self.stage / "remote-system-filesystem-validation.json").read_text(encoding="utf-8"))
        shutil.rmtree(self.stage / "aosp-remote-output")
        base.BuildR9.finish(self, firmware, super_image, vbmeta_system)

        result_path = self.final / "build-result.json"
        result = json.loads(result_path.read_text(encoding="utf-8"))
        result["status"] = "READY TO FLASH"
        result["repair"] = self.config["repair"]
        result["direct_baseline"] = "m8b-ime-r1 (DEVICE ACCEPTED / IME PASS)"
        result["historical_remote_v2"] = self.config["historical_remote_v2"]
        result["remote_provider"] = self.config["remote_provider"]
        result["remote_service"] = self.config["remote_service"]
        result["aosp_integration_validation"] = integration_report
        result["package_contract_validation"] = package_report
        result["filesystem_validation"] = filesystem_report
        result["changed_logical_partitions"] = ["system_a"]
        result["protected_logical_partitions_unchanged"] = ["product_a", "vendor_a", "vendor_dlkm_a"]
        result["leanback_ime_preserved"] = True
        result["boot_kernel_vendor_boot_preserved"] = True
        result["play_store_regression_guard"] = {
            "baseline_play_gms_state": self.config["play_regression_guard"]["baseline_play_gms_state"],
            "play_gms_packages_added": False,
            "feature_identity_changed": False,
            "system_or_product_properties_changed": False,
            "historical_Test9r2_Play_changes_imported": False,
        }
        result["physical_device_actions_performed"] = False
        result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        sums = [
            base.digest(path) + "  " + path.relative_to(self.final).as_posix()
            for path in sorted(self.final.rglob("*")) if path.is_file() and path.name != "SHA256SUMS"
        ]
        (self.final / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")

    def build(self) -> None:
        started = time.time()
        try:
            self.setup()
            source_super, raw_super, source_system, _old_vbmeta = self.extract_r8()
            system = self.repair_system(source_system)
            vbmeta_system = self.make_vbmeta_system(system)
            super_image = self.make_super(raw_super, system)
            validated_system = self.validate_super(source_super, super_image, source_system)
            self.verify_avb(validated_system, vbmeta_system)
            self.verify_filesystems()
            firmware = self.pack(super_image, vbmeta_system)
            self.finish(firmware, super_image, vbmeta_system)
            print("SUCCESS: " + str(self.final) + " in %.1fs" % (time.time() - started))
        except Exception:
            if self.stage.exists() and not self.keep_failed:
                shutil.rmtree(self.stage)
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--keep-failed", action="store_true")
    args = parser.parse_args()
    BuildM8BRemoteR1(ime.audio2.audio1.rc.merged_config(args.config), args.keep_failed).build()


if __name__ == "__main__":
    main()
