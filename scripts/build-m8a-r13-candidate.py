#!/usr/bin/env python3
"""Build r13 by stabilizing TV provisioning and short-press Power policy."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import time
import xml.etree.ElementTree as ET
import zipfile


REPO = Path(__file__).resolve().parents[1]
BASE_BUILDER = REPO / "scripts" / "build-m8a-r12-candidate.py"
AUDITOR = REPO / "scripts" / "audit-logical-system-init.py"
DEFAULT_CONFIG = REPO / "configs" / "candidates" / "m8a-initial-atv-r13.json"
AAPT2 = "/home/tianyi/ubox10-aosp/out/host/linux-x86/bin/aapt2"
ZIPALIGN = "/home/tianyi/ubox10-aosp/prebuilts/build-tools/linux-x86/bin/zipalign"
JAVA = "/home/tianyi/ubox10-aosp/prebuilts/jdk/jdk11/linux-x86/bin/java"
APKSIGNER = "/home/tianyi/ubox10-aosp/prebuilts/sdk/tools/linux/lib/apksigner.jar"
PLATFORM_CERT = "/home/tianyi/ubox10-aosp/build/target/product/security/platform.x509.pem"
PLATFORM_KEY = "/home/tianyi/ubox10-aosp/build/target/product/security/platform.pk8"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load module: " + str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


r12 = load_module(BASE_BUILDER, "m8a_r12_builder")


class BuildR13(r12.BuildR12):
    def __init__(self, config: dict[str, object], keep_failed: bool) -> None:
        super().__init__(config, keep_failed)
        self.provision_reference: Path | None = None
        self.provision_reference_before: dict[str, object] | None = None
        self.provision_source_dir: Path | None = None
        self.overlay_source: Path | None = None
        self.overlay_source_before: dict[str, dict[str, object]] = {}

    @staticmethod
    def _sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest().upper()

    def setup(self) -> None:
        # r12 is byte-locked. Do not replay earlier imports.
        r12.r11.r10.base.BuildR9.setup(self)
        reference = self.config["reference_test8r2"]
        assert isinstance(reference, dict)
        self.provision_reference = self.project_root / str(reference["project_relative"])
        if not self.provision_reference.is_file():
            raise RuntimeError("missing Test8r2 provisioning reference: " + str(self.provision_reference))
        self.provision_reference_before = r12.r11.r10.base.record(self.provision_reference)
        if (
            self.provision_reference_before["size"] != reference["size"]
            or self.provision_reference_before["sha256"] != reference["sha256"]
        ):
            raise RuntimeError("Test8r2 provisioning reference identity mismatch")

        overlay = self.config["power_overlay"]
        assert isinstance(overlay, dict)
        self.overlay_source = REPO / str(overlay["source_relative"])
        source_files = {
            "AndroidManifest.xml": str(overlay["manifest_sha256"]),
            "res/values/config.xml": str(overlay["resource_sha256"]),
        }
        for relative, expected in source_files.items():
            path = self.overlay_source / relative
            value = r12.r11.r10.base.record(path)
            if value["sha256"] != expected:
                raise RuntimeError("r13 overlay source identity mismatch: " + relative)
            self.overlay_source_before[relative] = value

        toolchain = self.config["toolchain"]
        assert isinstance(toolchain, list)
        output = self.stage / "toolchain-sha256.txt"
        self.run(
            ["wsl.exe", "-d", "Ubuntu-24.04", "--", "sha256sum", *[str(item["path"]) for item in toolchain]],
            output=output,
        )
        observed = {line.split()[1]: line.split()[0].upper() for line in output.read_text(encoding="utf-8").splitlines()}
        for item in toolchain:
            assert isinstance(item, dict)
            if observed.get(str(item["path"])) != item["sha256"]:
                raise RuntimeError("r13 toolchain identity mismatch: " + str(item["path"]))
        self.extract_reference_provisioning(reference)

    def extract_reference_provisioning(self, reference: dict[str, object]) -> None:
        assert self.provision_reference is not None and self.provision_reference_before is not None
        outer = self.stage / "test8r2-provision-source"
        outer.mkdir()
        self.run([
            sys.executable,
            str(r12.r11.r10.base.TOOLS / "sunxi_image_tool.py"),
            "extract", "-o", str(outer), "-f", "super.fex", str(self.provision_reference),
        ])
        super_image = outer / "super.fex"
        super_record = r12.r11.r10.base.record(super_image)
        if super_record["size"] != reference["super_size"] or super_record["sha256"] != reference["super_sha256"]:
            raise RuntimeError("Test8r2 provisioning super identity mismatch")

        provisioning = self.config["provisioning"]
        assert isinstance(provisioning, dict)
        self.provision_source_dir = self.stage / "test8r2-provision-files"
        self.provision_source_dir.mkdir()
        auditor = load_module(AUDITOR, "m8a_r13_reference_auditor")
        source = auditor.open_super_source(super_image)
        try:
            metadata = auditor.parse_lp_metadata(source)
            logical = auditor.LogicalPartitionSource(source, metadata, "system_a")
            ext4 = auditor.Ext4Reader(logical)
            specs = (
                ("source_apk_path", "AwTvProvision.apk", "apk_size", "apk_sha256"),
                ("source_allowlist_path", "provision-permissions.xml", "allowlist_size", "allowlist_sha256"),
            )
            extracted: list[dict[str, object]] = []
            for path_key, name, size_key, hash_key in specs:
                source_path = str(provisioning[path_key])
                inode = ext4.lookup(source_path.lstrip("/"))
                if inode.mode & 0xF000 != 0x8000 or inode.mode & 0o7777 != 0o644:
                    raise RuntimeError("unexpected Test8r2 provisioning inode: " + source_path)
                data = ext4.read_inode_data(inode)
                if len(data) != provisioning[size_key] or self._sha256(data) != provisioning[hash_key]:
                    raise RuntimeError("Test8r2 provisioning artifact identity mismatch: " + source_path)
                (self.provision_source_dir / name).write_bytes(data)
                extracted.append({
                    "partition": "system_a", "source_path": source_path,
                    "destination_path": provisioning["destination_apk_path" if name.endswith(".apk") else "destination_allowlist_path"],
                    "size": len(data), "sha256": provisioning[hash_key], "mode": "0644", "uid": 0, "gid": 0,
                    "selinux": "u:object_r:system_file:s0",
                })
        finally:
            source.close()

        apk = self.provision_source_dir / "AwTvProvision.apk"
        with zipfile.ZipFile(apk) as archive:
            dex = archive.read("classes.dex")
        if len(dex) != provisioning["classes_dex_size"] or self._sha256(dex) != provisioning["classes_dex_sha256"]:
            raise RuntimeError("AwTvProvision classes.dex identity mismatch")
        for marker in (
            b"device_provisioned", b"user_setup_complete", b"tv_user_setup_complete",
            b"tmp_provision_set_do", b"Landroid/provider/Settings$Global;",
            b"Landroid/provider/Settings$Secure;", b"setComponentEnabledSetting",
        ):
            if marker not in dex:
                raise RuntimeError("AwTvProvision DEX contract marker missing: " + marker.decode("ascii"))

        permissions = ET.fromstring((self.provision_source_dir / "provision-permissions.xml").read_bytes())
        block = next((item for item in permissions.iter("privapp-permissions") if item.get("package") == provisioning["package"]), None)
        if block is None:
            raise RuntimeError("AwTvProvision privapp allowlist package missing")
        names = {item.get("name") for item in block.findall("permission")}
        required = {
            "android.permission.WRITE_SECURE_SETTINGS",
            "android.permission.DISPATCH_PROVISIONING_MESSAGE",
            "android.permission.MASTER_CLEAR",
        }
        if not required.issubset(names):
            raise RuntimeError("AwTvProvision privapp allowlist incomplete")

        badging = self.stage / "provision-aapt2-badging.txt"
        manifest = self.stage / "provision-aapt2-manifest.txt"
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "--", AAPT2, "dump", "badging", self.wsl_path(apk)], output=badging)
        self.run([
            "wsl.exe", "-d", "Ubuntu-24.04", "--", AAPT2, "dump", "xmltree", self.wsl_path(apk),
            "--file", "AndroidManifest.xml",
        ], output=manifest)
        manifest_text = manifest.read_text(encoding="utf-8")
        manifest_required = (
            str(provisioning["package"]), str(provisioning["activity"]).rsplit(".", 1)[-1], "android:directBootAware", "=true",
            "android.intent.action.MAIN", "android.intent.category.HOME", "android.intent.category.DEFAULT",
            "android.intent.category.SETUP_WIZARD", "android:priority", "=1",
        )
        if any(marker not in manifest_text for marker in manifest_required):
            raise RuntimeError("AwTvProvision manifest contract mismatch")

        report = {
            "reference_candidate": self.provision_reference_before,
            "reference_super": super_record,
            "composition_omission": "ubox10.mk names AwTvProvision, but the current checkout has no vendor/aw module or materialized APK; r12 therefore contains no provisioning package.",
            "artifacts": extracted,
            "package": provisioning["package"],
            "activity": provisioning["activity"],
            "first_home_contract": "direct-boot-aware HOME/DEFAULT/SETUP_WIZARD activity at priority 1",
            "verified_dex_control_flow": [
                "onCreate reads tmp_provision_set_do with default 0",
                "finishSetup writes Global device_provisioned=1",
                "finishSetup writes Secure user_setup_complete=1",
                "finishSetup writes Secure tv_user_setup_complete=1",
                "component disables itself after provisioning so Projectivy remains HOME",
            ],
            "expected_final_flags": provisioning["final_flags"],
            "shell_hack": False,
            "full_setupwizard_added": False,
        }
        (self.stage / "provisioning-source.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def _read_ext4_file(auditor, image: Path, path: str) -> bytes:
        source = auditor.RawByteSource(image)
        try:
            ext4 = auditor.Ext4Reader(source)
            return ext4.read_inode_data(ext4.lookup(path.lstrip("/")))
        finally:
            source.close()

    def build_power_overlay(self, framework_res: Path) -> Path:
        assert self.overlay_source is not None
        compiled = self.stage / "power-overlay-compiled.zip"
        unsigned = self.stage / "power-overlay-unsigned.apk"
        aligned = self.stage / "power-overlay-aligned.apk"
        signed = self.stage / "M8TvPowerPolicyOverlay.apk"
        self.run([
            "wsl.exe", "-d", "Ubuntu-24.04", "--", AAPT2, "compile",
            "--dir", self.wsl_path(self.overlay_source / "res"), "-o", self.wsl_path(compiled),
        ])
        self.run([
            "wsl.exe", "-d", "Ubuntu-24.04", "--", AAPT2, "link", "-o", self.wsl_path(unsigned),
            "-I", self.wsl_path(framework_res), "--manifest", self.wsl_path(self.overlay_source / "AndroidManifest.xml"),
            "--auto-add-overlay", self.wsl_path(compiled),
        ])
        self.run([
            "wsl.exe", "-d", "Ubuntu-24.04", "--", ZIPALIGN, "-f", "4",
            self.wsl_path(unsigned), self.wsl_path(aligned),
        ])
        self.run([
            "wsl.exe", "-d", "Ubuntu-24.04", "--", JAVA, "-jar", APKSIGNER, "sign",
            "--key", PLATFORM_KEY, "--cert", PLATFORM_CERT, "--out", self.wsl_path(signed), self.wsl_path(aligned),
        ])
        self.run([
            "wsl.exe", "-d", "Ubuntu-24.04", "--", JAVA, "-jar", APKSIGNER, "verify",
            "--verbose", "--print-certs", self.wsl_path(signed),
        ], output=self.stage / "power-overlay-signature.txt")
        self.run([
            "wsl.exe", "-d", "Ubuntu-24.04", "--", AAPT2, "dump", "resources", self.wsl_path(signed),
        ], output=self.stage / "power-overlay-resources.txt")
        self.run([
            "wsl.exe", "-d", "Ubuntu-24.04", "--", AAPT2, "dump", "xmltree", self.wsl_path(signed),
            "--file", "AndroidManifest.xml",
        ], output=self.stage / "power-overlay-manifest.txt")

        overlay = self.config["power_overlay"]
        assert isinstance(overlay, dict)
        value = r12.r11.r10.base.record(signed)
        if value["size"] != overlay["expected_apk_size"] or value["sha256"] != overlay["expected_apk_sha256"]:
            raise RuntimeError("r13 power overlay output is not deterministic")
        resources = (self.stage / "power-overlay-resources.txt").read_text(encoding="utf-8")
        manifest = (self.stage / "power-overlay-manifest.txt").read_text(encoding="utf-8")
        signature = (self.stage / "power-overlay-signature.txt").read_text(encoding="utf-8")
        required_resources = ("config_shortPressOnPowerBehavior", "() 1")
        required_manifest = (str(overlay["package"]), "android:priority", "=1", "android:targetPackage", '="android"', "android:isStatic", "=true")
        if any(marker not in resources for marker in required_resources) or any(marker not in manifest for marker in required_manifest):
            raise RuntimeError("r13 power overlay resource or manifest mismatch")
        if "config_longPressOnPowerBehavior" in resources:
            raise RuntimeError("r13 power overlay unexpectedly changes long-press policy")
        if "Verifies" not in signature or "Signer #1 certificate SHA-256 digest: c8a2e9bc" not in signature:
            raise RuntimeError("r13 power overlay platform signature verification failed")
        return signed

    def repair_system(self, source: Path) -> Path:
        if self.provision_source_dir is None:
            raise RuntimeError("provisioning sources were not prepared")
        auditor = load_module(AUDITOR, "m8a_r13_system_auditor")
        framework = self.stage / "framework-res.apk"
        power = self.config["power_overlay"]
        assert isinstance(power, dict)
        framework_data = self._read_ext4_file(auditor, source, str(power["framework_res"]["path"]))
        framework.write_bytes(framework_data)
        framework_record = r12.r11.r10.base.record(framework)
        if framework_record["size"] != power["framework_res"]["size"] or framework_record["sha256"] != power["framework_res"]["sha256"]:
            raise RuntimeError("r12 framework-res identity mismatch")
        overlay = self.build_power_overlay(framework)

        system = self.stage / "system_a.img"
        shutil.copyfile(source, system)
        self.run([sys.executable, str(r12.r11.r10.base.TOOLS / "avbtool.py"), "erase_footer", "--image", str(system)])
        work_size = str(self.config["system_work_size"])
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "truncate", "-s", work_size, self.wsl_path(system)])
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "resize2fs", self.wsl_path(system), work_size])
        mount_dir = self.stage / "system-mount"
        mount_dir.mkdir()
        self.run([
            "wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "bash",
            self.wsl_path(REPO / "scripts" / "install-m8-r13-tv-policy.sh"),
            self.wsl_path(system), self.wsl_path(mount_dir),
            self.wsl_path(self.provision_source_dir / "AwTvProvision.apk"),
            self.wsl_path(self.provision_source_dir / "provision-permissions.xml"),
            self.wsl_path(overlay),
        ])
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "resize2fs", "-M", self.wsl_path(system)])
        mount_dir.rmdir()

        avb = self.config["avb"]
        assert isinstance(avb, dict)
        self.run([
            sys.executable, str(r12.r11.r10.base.TOOLS / "avbtool.py"), "add_hashtree_footer",
            "--image", str(system), "--partition_name", "system",
            "--partition_size", str(avb["partition_size"]), "--hash_algorithm", "sha256",
            "--salt", str(avb["salt"]), "--do_not_generate_fec",
            "--prop", "com.ubox10.candidate.id:" + self.candidate_id,
            "--prop", "com.ubox10.avb.fec:none", "--key", str(REPO / str(avb["key_relative"])),
            "--algorithm", "SHA256_RSA2048",
        ])
        if system.stat().st_size != avb["partition_size"]:
            raise RuntimeError("signed r13 system_a size mismatch")
        return system

    def _dump_apk(self, apk: Path, prefix: str) -> tuple[str, str]:
        resources = self.stage / (prefix + "-resources.txt")
        manifest = self.stage / (prefix + "-manifest.txt")
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "--", AAPT2, "dump", "resources", self.wsl_path(apk)], output=resources)
        self.run([
            "wsl.exe", "-d", "Ubuntu-24.04", "--", AAPT2, "dump", "xmltree", self.wsl_path(apk),
            "--file", "AndroidManifest.xml",
        ], output=manifest)
        return resources.read_text(encoding="utf-8"), manifest.read_text(encoding="utf-8")

    def validate_system_diff(self, before_image: Path, after_image: Path) -> dict[str, object]:
        before_path = self.inventory_system(before_image, "r8-system")
        after_path = self.inventory_system(after_image, "r9-system")
        before, after = self._manifest_map(before_path), self._manifest_map(after_path)
        provisioning = self.config["provisioning"]
        power = self.config["power_overlay"]
        assert isinstance(provisioning, dict) and isinstance(power, dict)
        target_apk = str(provisioning["destination_apk_path"])
        target_allowlist = str(provisioning["destination_allowlist_path"])
        target_overlay = str(power["destination_path"])
        allowed = {
            "/system_ext", "/system_ext/priv-app", "/system_ext/etc/permissions",
            "/system_ext/priv-app/AwTvProvision", target_apk, target_allowlist,
            "/system_ext/overlay", target_overlay,
        }
        unexpected = [path for path in sorted(set(before) | set(after)) if path not in allowed and before.get(path) != after.get(path)]
        if unexpected:
            raise RuntimeError("unexpected r13 system filesystem differences: " + ", ".join(unexpected[:16]))
        if any(before.get(path) is not None for path in (target_apk, target_allowlist, target_overlay)):
            raise RuntimeError("r12 unexpectedly already contains an r13 target")

        label = b"u:object_r:system_file:s0\0".hex().upper()
        contracts = {
            "/system_ext/priv-app/AwTvProvision": {"type": "directory", "mode": "0755", "uid": 0, "gid": 0},
            target_apk: {"type": "regular", "mode": "0644", "uid": 0, "gid": 0, "size": provisioning["apk_size"], "sha256": provisioning["apk_sha256"]},
            target_allowlist: {"type": "regular", "mode": "0644", "uid": 0, "gid": 0, "size": provisioning["allowlist_size"], "sha256": provisioning["allowlist_sha256"]},
            "/system_ext/overlay": {"type": "directory", "mode": "0755", "uid": 0, "gid": 0},
            target_overlay: {"type": "regular", "mode": "0644", "uid": 0, "gid": 0, "size": power["expected_apk_size"], "sha256": power["expected_apk_sha256"]},
        }
        for path, expected in contracts.items():
            actual = after.get(path)
            if actual is None or any(actual.get(key) != wanted for key, wanted in expected.items()):
                raise RuntimeError("r13 installed artifact metadata mismatch: " + path)
            if actual.get("xattrs", {}).get("security.selinux") != label:
                raise RuntimeError("r13 installed artifact SELinux label mismatch: " + path)

        frozen: list[dict[str, object]] = []
        for item in self.config["frozen_files"]:
            assert isinstance(item, dict)
            path = str(item["path"])
            value = after.get(path)
            if before.get(path) != value:
                raise RuntimeError("frozen r12 file changed: " + path)
            if value is None or value.get("size") != item["size"] or value.get("sha256") != item["sha256"]:
                raise RuntimeError("frozen r12 file identity mismatch: " + path)
            frozen.append({"path": path, "size": item["size"], "sha256": item["sha256"]})
        framework_path = str(power["framework_res"]["path"])
        if before.get(framework_path) != after.get(framework_path) or after[framework_path].get("sha256") != power["framework_res"]["sha256"]:
            raise RuntimeError("framework-res changed instead of being overlaid")

        vendor = after.get("/vendor")
        system_vendor = after.get("/system/vendor")
        if vendor is None or vendor.get("type") != "directory":
            raise RuntimeError("canonical /vendor topology changed")
        if system_vendor is None or system_vendor.get("type") != "symlink" or system_vendor.get("target") != "/vendor":
            raise RuntimeError("/system/vendor compatibility link changed")

        auditor = load_module(AUDITOR, "m8a_r13_validation_auditor")
        extracted_dir = self.stage / "r13-policy-extracted"
        extracted_dir.mkdir()
        extracted_apk = extracted_dir / "AwTvProvision.apk"
        extracted_allowlist = extracted_dir / "provision-permissions.xml"
        extracted_overlay = extracted_dir / "M8TvPowerPolicyOverlay.apk"
        extracted_apk.write_bytes(self._read_ext4_file(auditor, after_image, target_apk))
        extracted_allowlist.write_bytes(self._read_ext4_file(auditor, after_image, target_allowlist))
        extracted_overlay.write_bytes(self._read_ext4_file(auditor, after_image, target_overlay))
        for path, expected in (
            (extracted_apk, provisioning["apk_sha256"]),
            (extracted_allowlist, provisioning["allowlist_sha256"]),
            (extracted_overlay, power["expected_apk_sha256"]),
        ):
            if r12.r11.r10.base.digest(path) != expected:
                raise RuntimeError("r13 unpacked artifact identity mismatch: " + path.name)

        manifest = self.stage / "r13-provision-manifest.txt"
        self.run([
            "wsl.exe", "-d", "Ubuntu-24.04", "--", AAPT2, "dump", "xmltree", self.wsl_path(extracted_apk),
            "--file", "AndroidManifest.xml",
        ], output=manifest)
        manifest_text = manifest.read_text(encoding="utf-8")
        if any(marker not in manifest_text for marker in (
            str(provisioning["package"]), str(provisioning["activity"]).rsplit(".", 1)[-1], "android.intent.category.HOME",
            "android.intent.category.SETUP_WIZARD", "android:directBootAware", "=true",
        )):
            raise RuntimeError("unpacked AwTvProvision manifest mismatch")

        logical = self.stage / "validation-logical"
        vendor_apk = extracted_dir / "vendor-framework-rro.apk"
        product_apk = extracted_dir / "product-tv-framework-rro.apk"
        vendor_apk.write_bytes(self._read_ext4_file(auditor, logical / "vendor_a.img", str(power["vendor_rro"]["path"])))
        product_apk.write_bytes(self._read_ext4_file(auditor, logical / "product_a.img", str(power["product_rro"]["path"])))
        for path, spec in ((vendor_apk, power["vendor_rro"]), (product_apk, power["product_rro"])):
            if path.stat().st_size != spec["size"] or r12.r11.r10.base.digest(path) != spec["sha256"]:
                raise RuntimeError("existing power RRO identity changed: " + path.name)
        vendor_resources, vendor_manifest = self._dump_apk(vendor_apk, "vendor-power-rro")
        product_resources, product_manifest = self._dump_apk(product_apk, "product-power-rro")
        overlay_resources, overlay_manifest = self._dump_apk(extracted_overlay, "r13-power-rro")
        if "config_shortPressOnPowerBehavior" not in vendor_resources or "() 0" not in vendor_resources:
            raise RuntimeError("vendor short-press override evidence changed")
        if "config_longPressOnPowerBehavior" not in vendor_resources or "() 3" not in vendor_resources:
            raise RuntimeError("vendor long-press policy evidence changed")
        if "config_longPressOnPowerBehavior" not in product_resources or "() 3" not in product_resources:
            raise RuntimeError("product long-press policy evidence changed")
        if "config_shortPressOnPowerBehavior" not in overlay_resources or "() 1" not in overlay_resources:
            raise RuntimeError("r13 short-press override is missing")
        if "config_longPressOnPowerBehavior" in overlay_resources:
            raise RuntimeError("r13 overlay changes long-press Power")
        for text, priority in ((vendor_manifest, 0), (product_manifest, -1), (overlay_manifest, 1)):
            if "android:priority" not in text or ("=" + str(priority)) not in text:
                raise RuntimeError("static RRO priority mismatch")

        launcher_validation = {
            "preserved_file": frozen[0],
            "r11_manifest_validation_inherited_by_exact_apk_identity": True,
            "resolver_after_provisioning": "com.spocky.projengmenu/.ui.home.MainActivity",
        }
        (self.stage / "launcher-validation.json").write_text(json.dumps(launcher_validation, indent=2) + "\n", encoding="utf-8")
        result = {
            "base": "m8a-initial-atv-r12",
            "added_files": [{"path": path, **value} for path, value in contracts.items()],
            "unexpected_system_differences": unexpected,
            "provisioning": {
                "package": provisioning["package"],
                "first_home_priority": 1,
                "self_disables_after_success": True,
                "expected_final_flags": provisioning["final_flags"],
                "home_after_success": "com.spocky.projengmenu/.ui.home.MainActivity",
            },
            "power_precedence": [
                {"partition": "product", "priority": -1, "long_press_value": 3},
                {"partition": "vendor", "priority": 0, "short_press_value": 0, "long_press_value": 3},
                {"partition": "system_ext", "priority": 1, "short_press_value": 1},
            ],
            "resolved_power_policy": {
                "short_press_value": 1,
                "short_press": "SHORT_PRESS_POWER_GO_TO_SLEEP",
                "long_press_value": 3,
                "long_press": "LONG_PRESS_POWER_SHUT_OFF_NO_CONFIRM",
            },
            "frozen_files": frozen,
            "frozen_files_unchanged": True,
            "remote_stack_unchanged": True,
            "mouse_mode_deferred": True,
            "canonical_vendor_topology_preserved": True,
        }
        (self.stage / "tv-policy-validation.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return result

    def finish(self, firmware: Path, super_image: Path, vbmeta_system: Path) -> None:
        assert self.provision_reference is not None and self.provision_reference_before is not None
        if r12.r11.r10.base.record(self.provision_reference) != self.provision_reference_before:
            raise RuntimeError("protected Test8r2 provisioning reference changed")
        assert self.overlay_source is not None
        for relative, before in self.overlay_source_before.items():
            if r12.r11.r10.base.record(self.overlay_source / relative) != before:
                raise RuntimeError("protected r13 overlay source changed: " + relative)
        source_path = self.stage / "provisioning-source.json"
        source_report = json.loads(source_path.read_text(encoding="utf-8"))
        source_report["reference_super"]["path"] = str(self.provision_reference) + "#super.fex"
        source_path.write_text(json.dumps(source_report, indent=2) + "\n", encoding="utf-8")

        shutil.rmtree(self.stage / "test8r2-provision-source")
        shutil.rmtree(self.stage / "test8r2-provision-files")
        shutil.rmtree(self.stage / "r13-policy-extracted")
        for name in ("framework-res.apk", "power-overlay-compiled.zip", "power-overlay-unsigned.apk", "power-overlay-aligned.apk"):
            (self.stage / name).unlink()
        r12.r11.r10.base.BuildR9.finish(self, firmware, super_image, vbmeta_system)

        result_path = self.final / "build-result.json"
        result = json.loads(result_path.read_text(encoding="utf-8"))
        result["status"] = "OFFLINE CHECKED"
        result["repair"] = "Add exact Test8r2 AwTvProvision plus its allowlist, and a priority-1 static RRO that changes only short-press Power to GO_TO_SLEEP."
        result["provisioning_source"] = json.loads((self.final / "provisioning-source.json").read_text(encoding="utf-8"))
        result["tv_policy_validation"] = json.loads((self.final / "tv-policy-validation.json").read_text(encoding="utf-8"))
        result["power_overlay_apk"] = r12.r11.r10.base.record(self.final / "M8TvPowerPolicyOverlay.apk")
        result["frozen_components_unchanged"] = True
        result["physical_device_actions_performed"] = False
        result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        sums = [
            r12.r11.r10.base.digest(path) + "  " + path.name
            for path in sorted(self.final.iterdir()) if path.is_file() and path.name != "SHA256SUMS"
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
            self.verify_selinux()
            r12.BuildR12.validate_elf(self)
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
    BuildR13(json.loads(args.config.read_text(encoding="utf-8")), args.keep_failed).build()


if __name__ == "__main__":
    main()
