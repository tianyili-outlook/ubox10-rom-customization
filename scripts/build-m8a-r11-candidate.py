#!/usr/bin/env python3
"""Build r11 by adding one real Android TV HOME Launcher to the r10 system composition."""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import time


REPO = Path(__file__).resolve().parents[1]
BASE_BUILDER = REPO / "scripts" / "build-m8a-r10-candidate.py"
AUDITOR = REPO / "scripts" / "audit-logical-system-init.py"
DEFAULT_CONFIG = REPO / "configs" / "candidates" / "m8a-initial-atv-r11.json"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load module: " + str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


r10 = load_module(BASE_BUILDER, "m8a_r10_builder")


class BuildR11(r10.BuildR10):
    def __init__(self, config: dict[str, object], keep_failed: bool) -> None:
        super().__init__(config, keep_failed)
        self.launcher_source: Path | None = None
        self.launcher_before: dict[str, object] | None = None

    def setup(self) -> None:
        # r10 is the byte-locked base. Do not rerun the r10 compatibility import.
        r10.base.BuildR9.setup(self)
        launcher = self.config["launcher"]
        reference = self.config["test8r2_reference"]
        assert isinstance(launcher, dict) and isinstance(reference, dict)
        self.launcher_source = self.project_root / str(launcher["source_project_relative"])
        if not self.launcher_source.is_file():
            raise RuntimeError("missing Projectivy source APK: " + str(self.launcher_source))
        self.launcher_before = r10.base.record(self.launcher_source)
        if self.launcher_before["size"] != launcher["size"] or self.launcher_before["sha256"] != launcher["sha256"]:
            raise RuntimeError("Projectivy source identity mismatch")

        test8_result_path = self.project_root / str(reference["build_result_project_relative"])
        test8_result = json.loads(test8_result_path.read_text(encoding="utf-8"))
        firmware = test8_result["firmware"]
        properties = test8_result["system_properties"]
        injections = test8_result["system_app_injections"]
        if firmware["sha256"] != reference["firmware_sha256"]:
            raise RuntimeError("Test8r2 reference identity mismatch")
        if properties.get("ro.sw.defaultlauncher_package") != reference["default_launcher_package"]:
            raise RuntimeError("Test8r2 default Launcher package mismatch")
        if properties.get("ro.sw.defaultlauncher_class") != reference["default_launcher_class"]:
            raise RuntimeError("Test8r2 default Launcher class mismatch")
        if not any(item.get("sha256") == launcher["sha256"] and item.get("destination") == launcher["destination_path"] for item in injections):
            raise RuntimeError("Test8r2 Projectivy injection record mismatch")
        report = {
            "composition_source": "Pinned system app input in the r11 candidate builder; current ubox10.mk inherits atv_product.mk but not aosp_tv_arm.mk, so no Launcher module enters PRODUCT_PACKAGES.",
            "source_apk": self.launcher_before,
            "test8r2_build_result": str(test8_result_path),
            "test8r2_default_home": {
                "package": reference["default_launcher_package"],
                "activity": reference["default_launcher_class"],
            },
        }
        (self.stage / "launcher-source.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    def repair_system(self, source: Path) -> Path:
        assert self.launcher_source is not None
        system = self.stage / "system_a.img"
        shutil.copyfile(source, system)
        self.run([sys.executable, str(r10.base.TOOLS / "avbtool.py"), "erase_footer", "--image", str(system)])
        work_size = str(self.config["system_work_size"])
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "truncate", "-s", work_size, self.wsl_path(system)])
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "resize2fs", self.wsl_path(system), work_size])
        mount_dir = self.stage / "system-mount"
        mount_dir.mkdir()
        self.run([
            "wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "bash",
            self.wsl_path(REPO / "scripts" / "install-m8-projectivy-launcher.sh"),
            self.wsl_path(system), self.wsl_path(mount_dir), self.wsl_path(self.launcher_source),
        ])
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "resize2fs", "-M", self.wsl_path(system)])
        mount_dir.rmdir()

        avb = self.config["avb"]
        assert isinstance(avb, dict)
        self.run([
            sys.executable, str(r10.base.TOOLS / "avbtool.py"), "add_hashtree_footer",
            "--image", str(system), "--partition_name", "system",
            "--partition_size", str(avb["partition_size"]), "--hash_algorithm", "sha256",
            "--salt", str(avb["salt"]), "--do_not_generate_fec",
            "--prop", "com.ubox10.candidate.id:" + self.candidate_id,
            "--prop", "com.ubox10.avb.fec:none", "--key", str(REPO / str(avb["key_relative"])),
            "--algorithm", "SHA256_RSA2048",
        ])
        if system.stat().st_size != avb["partition_size"]:
            raise RuntimeError("signed r11 system_a size mismatch")
        return system

    @staticmethod
    def _activity_segment(xmltree: str, activity: str) -> str:
        lines = xmltree.splitlines()
        hit = next(index for index, line in enumerate(lines) if activity in line)
        start = hit
        while start >= 0 and "E: activity " not in lines[start]:
            start -= 1
        if start < 0:
            raise RuntimeError("cannot locate Launcher activity start")
        indent = len(lines[start]) - len(lines[start].lstrip())
        end = len(lines)
        for index in range(start + 1, len(lines)):
            line = lines[index]
            if len(line) - len(line.lstrip()) == indent and line.lstrip().startswith("E:"):
                end = index
                break
        return "\n".join(lines[start:end])

    def validate_system_diff(self, before_image: Path, after_image: Path) -> dict[str, object]:
        before_path = self.inventory_system(before_image, "r8-system")
        after_path = self.inventory_system(after_image, "r9-system")
        before, after = self._manifest_map(before_path), self._manifest_map(after_path)
        launcher = self.config["launcher"]
        assert isinstance(launcher, dict)
        target = str(launcher["destination_path"])
        target_dir = str(Path(target).parent).replace("\\", "/")
        allowed = {"/system/app", target_dir, target}
        unexpected = [path for path in sorted(set(before) | set(after)) if path not in allowed and before.get(path) != after.get(path)]
        if unexpected:
            raise RuntimeError("unexpected r11 system filesystem differences: " + ", ".join(unexpected[:16]))
        if before.get(target) is not None or before.get(target_dir) is not None:
            raise RuntimeError("r10 unexpectedly already contains Projectivy Launcher")

        label = b"u:object_r:system_file:s0\0".hex().upper()
        expected_dir = {"type": "directory", "mode": "0755", "uid": 0, "gid": 0}
        expected_apk = {
            "type": "regular", "mode": launcher["mode"], "uid": launcher["uid"], "gid": launcher["gid"],
            "size": launcher["size"], "sha256": launcher["sha256"],
        }
        for path, expected in ((target_dir, expected_dir), (target, expected_apk)):
            actual = after.get(path)
            if actual is None or any(actual.get(key) != value for key, value in expected.items()):
                raise RuntimeError("r11 Launcher metadata mismatch: " + path)
            if actual.get("xattrs", {}).get("security.selinux") != label:
                raise RuntimeError("r11 Launcher SELinux label mismatch: " + path)

        compatibility = self.config["r10_compatibility_libraries"]
        assert isinstance(compatibility, list)
        for item in compatibility:
            assert isinstance(item, dict)
            path = str(item["path"])
            if before.get(path) != after.get(path):
                raise RuntimeError("r10 compatibility library changed: " + path)
            value = after.get(path)
            if value is None or value.get("size") != item["size"] or value.get("sha256") != item["sha256"]:
                raise RuntimeError("r10 compatibility library identity mismatch: " + path)

        vendor = after.get("/vendor")
        system_vendor = after.get("/system/vendor")
        if vendor is None or vendor.get("type") != "directory":
            raise RuntimeError("r10 canonical /vendor topology was not preserved")
        if system_vendor is None or system_vendor.get("type") != "symlink" or system_vendor.get("target") != "/vendor":
            raise RuntimeError("r10 /system/vendor link was not preserved")

        auditor = load_module(AUDITOR, "m8a_r11_logical_auditor")
        source = auditor.RawByteSource(after_image)
        extracted = self.stage / "r11-extracted-ProjectivyLauncher.apk"
        try:
            ext4 = auditor.Ext4Reader(source)
            extracted.write_bytes(ext4.read_inode_data(ext4.lookup(target.lstrip("/"))))
        finally:
            source.close()
        if r10.base.record(extracted)["sha256"] != launcher["sha256"]:
            raise RuntimeError("extracted r11 Launcher identity mismatch")

        badging_path = self.stage / "launcher-aapt2-badging.txt"
        xmltree_path = self.stage / "launcher-aapt2-xmltree.txt"
        aapt2 = "/home/tianyi/ubox10-aosp/out/host/linux-x86/bin/aapt2"
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "--", aapt2, "dump", "badging", self.wsl_path(extracted)], output=badging_path)
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "--", aapt2, "dump", "xmltree", self.wsl_path(extracted), "--file", "AndroidManifest.xml"], output=xmltree_path)
        badging = badging_path.read_text(encoding="utf-8")
        xmltree = xmltree_path.read_text(encoding="utf-8")
        activity = self._activity_segment(xmltree, str(launcher["activity"]))
        required = [
            "package: name='" + str(launcher["package"]) + "'",
            "sdkVersion:'" + str(launcher["min_sdk"]) + "'",
            "targetSdkVersion:'" + str(launcher["target_sdk"]) + "'",
            "uses-feature: name='android.software.leanback'",
        ]
        if any(value not in badging for value in required):
            raise RuntimeError("r11 Launcher badging contract mismatch")
        activity_required = [
            str(launcher["activity"]), "android:exported", "=true", "android.intent.action.MAIN",
            "android.intent.category.HOME", "android.intent.category.DEFAULT", "android.intent.category.LEANBACK_LAUNCHER",
        ]
        if any(value not in activity for value in activity_required):
            raise RuntimeError("r11 Launcher HOME manifest contract mismatch")
        if "android:directBootAware" in activity or "android:sharedUserId" in xmltree:
            raise RuntimeError("unexpected Launcher direct-boot or shared-user contract")
        if any(line.startswith("uses-library:") for line in badging.splitlines()):
            raise RuntimeError("Launcher has a required platform shared library")
        extracted.unlink()

        result = {
            "base": "m8a-initial-atv-r10",
            "added_files": [
                {"path": target_dir, **expected_dir, "selinux": launcher["selinux"]},
                {"path": target, **expected_apk, "selinux": launcher["selinux"]},
            ],
            "manifest": {
                "package": launcher["package"], "activity": launcher["activity"], "exported": True,
                "direct_boot_aware": False, "categories": launcher["categories"],
                "min_sdk": launcher["min_sdk"], "target_sdk": launcher["target_sdk"],
                "tv_feature_required": True, "privileged": False, "shared_user_id": None,
                "required_shared_libraries": [], "optional_shared_libraries": launcher["optional_shared_libraries"],
            },
            "package_manager_scan": {
                "partition": launcher["partition"], "path_class": "system/app", "presigned": True,
                "privapp_allowlist_required": False, "scan_eligible": True,
            },
            "r10_compatibility_libraries_unchanged": True,
            "canonical_vendor_topology_preserved": True,
            "unexpected_system_differences": unexpected,
        }
        (self.stage / "launcher-validation.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return result

    def validate_elf(self) -> None:
        super().validate_elf()
        launcher = self.config["launcher"]
        assert isinstance(launcher, dict)
        with (self.stage / "elf-inventory.csv").open("r", encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        available = {Path(row["path"].split("!", 1)[0]).name for row in rows}
        available.update(row["soname"] for row in rows if row["soname"])
        prefix = str(launcher["destination_path"]) + "!/lib/armeabi-v7a/"
        observed = []
        for name in launcher["native_arm32_libraries"]:
            row = next((item for item in rows if item["path"] == prefix + str(name)), None)
            if row is None or row["class"] != "ELF32" or row["machine"] != "ARM":
                raise RuntimeError("missing ARM32 Projectivy native library: " + str(name))
            needed = [item for item in row["needed"].split(";") if item]
            missing = [item for item in needed if item not in available]
            if missing:
                raise RuntimeError("unresolved Projectivy native dependency: " + str(name) + " -> " + ",".join(missing))
            observed.append({"name": name, "class": row["class"], "machine": row["machine"], "needed": needed, "missing": missing})
        path = self.stage / "launcher-validation.json"
        report = json.loads(path.read_text(encoding="utf-8"))
        report["native_arm32"] = observed
        report["native_dependencies_resolved"] = True
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    def finish(self, firmware: Path, super_image: Path, vbmeta_system: Path) -> None:
        assert self.launcher_source is not None and self.launcher_before is not None
        if r10.base.record(self.launcher_source) != self.launcher_before:
            raise RuntimeError("protected Projectivy source APK changed")
        r10.base.BuildR9.finish(self, firmware, super_image, vbmeta_system)
        result_path = self.final / "build-result.json"
        result = json.loads(result_path.read_text(encoding="utf-8"))
        result["repair"] = "Add exactly one real TV HOME Launcher (pinned Projectivy 4.71) to the reproducible r10 system composition."
        result["launcher_source"] = json.loads((self.final / "launcher-source.json").read_text(encoding="utf-8"))
        result["launcher_validation"] = json.loads((self.final / "launcher-validation.json").read_text(encoding="utf-8"))
        result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        sums = [r10.base.digest(path) + "  " + path.name for path in sorted(self.final.iterdir()) if path.is_file() and path.name != "SHA256SUMS"]
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
            self.validate_elf()
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
    BuildR11(json.loads(args.config.read_text(encoding="utf-8")), args.keep_failed).build()


if __name__ == "__main__":
    main()
