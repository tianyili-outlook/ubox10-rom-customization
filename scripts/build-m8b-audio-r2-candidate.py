#!/usr/bin/env python3
"""Build the Treble/VNDK linker-namespace fix on top of m8b-audio-r1."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys


REPO = Path(__file__).resolve().parents[1]
BASE_BUILDER = REPO / "scripts" / "build-m8b-audio-r1-candidate.py"
AUDITOR = REPO / "scripts" / "audit-logical-system-init.py"
DEFAULT_CONFIG = REPO / "configs" / "candidates" / "m8b-audio-r2.json"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load module: " + str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


audio1 = load_module(BASE_BUILDER, "m8b_audio_r1_for_audio_r2")
base = audio1.base


class BuildM8BAudioR2(audio1.BuildM8BAudioR1):
    def setup(self) -> None:
        # Bypass the r1-only assertion that Treble/VNDK is absent, while retaining
        # every accepted M8B/r13 provenance and protected-component check.
        audio1.rc.BuildM8BRcCoreR1.setup(self)

        reference = self.config["reference_vndk"]
        assert isinstance(reference, dict)
        self.reference_system = REPO / str(reference["system_image_relative"])
        if not self.reference_system.is_file():
            raise RuntimeError("missing Test8r2 system reference: " + str(self.reference_system))
        self.reference_before = base.record(self.reference_system)
        if self.reference_before != {
            "path": str(self.reference_system),
            "size": reference["system_image_size"],
            "sha256": reference["system_image_sha256"],
        }:
            raise RuntimeError("Test8r2 system reference identity mismatch")

        evidence = REPO / str(reference["test8_linkerconfig_relative"])
        if not evidence.is_file() or base.digest(evidence) != reference["test8_linkerconfig_sha256"]:
            raise RuntimeError("Test8r2 linkerconfig evidence identity mismatch")
        evidence_text = evidence.read_text(encoding="utf-8", errors="replace")
        if "/apex/com.android.vndk.v31/${LIB}" not in evidence_text or "libaudioroute.so" not in evidence_text:
            raise RuntimeError("Test8r2 VNDK linker contract evidence is incomplete")

        contract = self.config["aosp_treble_contract"]
        linker = self.config["linkerconfig_validation"]
        assert isinstance(contract, dict) and isinstance(linker, dict)
        patch = REPO / str(contract["source_patch_relative"])
        if not patch.is_file() or base.digest(patch) != contract["source_patch_sha256"]:
            raise RuntimeError("AOSP Treble/VNDK source patch identity mismatch")

        checks = {
            str(contract["board_config_path"]): contract["board_config_sha256"],
            str(contract["product_config_path"]): contract["product_config_sha256"],
            str(contract["soong_variables_path"]): contract["soong_variables_sha256"],
            str(contract["system_image_path"]): contract["system_image_sha256"],
            str(contract["product_image_path"]): contract["product_image_sha256"],
            str(contract["system_ext_image_path"]): contract["system_ext_image_sha256"],
            str(contract["system_build_prop_path"]): contract["system_build_prop_sha256"],
            str(contract["system_linker_config_path"]): contract["system_linker_config_sha256"],
            str(linker["tool_path"]): linker["tool_sha256"],
            str(linker["environment_source_path"]): linker["environment_source_sha256"],
            str(linker["vendor_section_source_path"]): linker["vendor_section_source_sha256"],
            str(linker["vendor_default_source_path"]): linker["vendor_default_source_sha256"],
            str(linker["vndk_namespace_source_path"]): linker["vndk_namespace_source_sha256"],
        }
        hashes = self.stage / "aosp-treble-vndk-sha256.txt"
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "--", "sha256sum", *checks], output=hashes)
        observed = {line.split("  ", 1)[1]: line.split()[0].upper() for line in hashes.read_text(encoding="utf-8").splitlines()}
        for path, expected in checks.items():
            if observed.get(path) != expected:
                raise RuntimeError("AOSP Treble/VNDK artifact identity mismatch: " + path)

        source_report = self.stage / "aosp-treble-vndk-source.txt"
        self.run([
            "wsl.exe", "-d", "Ubuntu-24.04", "--", "bash", "-lc",
            "set -euo pipefail; "
            f"grep -qx 'BOARD_VNDK_VERSION := current' '{contract['board_config_path']}'; "
            f"grep -qx 'PRODUCT_SHIPPING_API_LEVEL := 31' '{contract['product_config_path']}'; "
            f"grep -q 'com.android.vndk.current' '{contract['product_config_path']}'; "
            f"test -d '{contract['vndk_apex_path']}'; "
            f"test -f '{contract['vndk_apex_path']}/lib/libaudioroute.so'; "
            f"grep -qx 'ro.treble.enabled=true' '{contract['system_build_prop_path']}'; "
            "printf '%s\n' 'PRODUCT_SHIPPING_API_LEVEL=31' 'BOARD_VNDK_VERSION=current' "
            "'com.android.vndk.current=installed' 'ro.treble.enabled=true'",
        ], output=source_report)

        soong_copy = self.stage / "soong.variables"
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "--", "cat", str(contract["soong_variables_path"])], output=soong_copy)
        soong = json.loads(soong_copy.read_text(encoding="utf-8"))
        expected = contract["expected"]
        assert isinstance(expected, dict)
        for key in ("DeviceVndkVersion", "ProductVndkVersion", "Treble_linker_namespaces", "Enforce_vintf_manifest", "Platform_vndk_version"):
            if soong.get(key) != expected[key]:
                raise RuntimeError("AOSP Soong Treble/VNDK value mismatch: " + key)
        for relative in contract["build_logs"]:
            log = REPO / str(relative)
            if not log.is_file() or "build completed successfully" not in log.read_text(encoding="utf-8", errors="replace"):
                raise RuntimeError("AOSP prerequisite build did not complete successfully: " + str(log))

        report = {
            "source_patch": base.record(patch),
            "source_assignments": [
                "PRODUCT_SHIPPING_API_LEVEL := 31",
                "BOARD_VNDK_VERSION := current",
                "PRODUCT_PACKAGES += com.android.vndk.current",
            ],
            "soong": {key: soong[key] for key in expected if key != "ro.treble.enabled"},
            "system_build_prop": "ro.treble.enabled=true",
            "vndk_apex_present": True,
            "aosp_builds": ["systemimage", "productimage", "systemextimage", "check-vintf-all"],
            "aosp_build_status": "PASS",
            "selinux_build_status": "PASS",
            "vintf_check_status": "PASS",
        }
        (self.stage / "aosp-treble-vndk-validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

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
            self.wsl_path(REPO / "scripts" / "set-m8b-audio-r2-treble-contract.sh"),
            self.wsl_path(system), self.wsl_path(mount_dir),
        ])
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "resize2fs", "-M", self.wsl_path(system)])
        mount_dir.rmdir()

        avb = self.config["avb"]
        assert isinstance(avb, dict)
        self.run([
            sys.executable, str(base.TOOLS / "avbtool.py"), "add_hashtree_footer", "--image", str(system),
            "--partition_name", "system", "--partition_size", str(avb["partition_size"]), "--hash_algorithm", "sha256",
            "--salt", str(avb["salt"]), "--do_not_generate_fec", "--prop", "com.ubox10.candidate.id:" + self.candidate_id,
            "--prop", "com.ubox10.avb.fec:none", "--key", str(REPO / str(avb["key_relative"])), "--algorithm", "SHA256_RSA2048",
        ])
        return system

    def validate_system_diff(self, before_image: Path, after_image: Path) -> dict[str, object]:
        before = self._manifest_map(self.inventory_system(before_image, "r5-system"))
        after = self._manifest_map(self.inventory_system(after_image, "audio-system"))
        assert self.reference_system is not None
        self.inventory_system(self.reference_system, "test8-system")
        changed_path = str(self.config["candidate_contract"]["changed_path"])
        changed = [path for path in sorted(set(before) | set(after)) if before.get(path) != after.get(path)]
        if changed != [changed_path]:
            raise RuntimeError("unexpected audio-r2 system differences: " + ", ".join(changed))

        before_entry = dict(before[changed_path])
        after_entry = dict(after[changed_path])
        for key in ("size", "sha256"):
            before_entry.pop(key, None)
            after_entry.pop(key, None)
        if before_entry != after_entry:
            raise RuntimeError("system build.prop metadata changed")

        auditor = load_module(AUDITOR, "m8b_audio_r2_auditor")
        old = self._read_ext4_file(auditor, before_image, changed_path)
        new = self._read_ext4_file(auditor, after_image, changed_path)
        contract = self.config["candidate_contract"]
        assert isinstance(contract, dict)
        old_line = str(contract["old_line"]).encode()
        new_line = str(contract["new_line"]).encode()
        if base.digest(before_image) != self.config["logical_partitions"]["system_a"]["sha256"]:
            raise RuntimeError("audio-r1 system input identity changed")
        if before[changed_path]["sha256"] != contract["system_build_prop_before_sha256"]:
            raise RuntimeError("audio-r1 build.prop identity mismatch")
        if old.count(old_line) != 1 or new != old.replace(old_line, new_line) or new.count(new_line) != 1:
            raise RuntimeError("audio-r2 build.prop change is not the single intended property conversion")

        linker_path = "/system/etc/linker.config.pb"
        if before[linker_path] != after[linker_path] or after[linker_path]["sha256"] != contract["system_linker_config_sha256"]:
            raise RuntimeError("system linker.config.pb changed unexpectedly")
        prefix = "/system/apex/com.android.vndk.current"
        for path in sorted(set(before) | set(after)):
            if (path == prefix or path.startswith(prefix + "/")) and before.get(path) != after.get(path):
                raise RuntimeError("audio-r1 exact VNDK APEX changed: " + path)
        for item in self.config["frozen_files"]:
            path = str(item["path"])
            if before.get(path) != after.get(path):
                raise RuntimeError("protected r13 artifact changed: " + path)
        for path in (
            "/system/etc/init/multi_ir.rc", "/system/usr/keylayout/sunxi-ir.kl",
            "/system/usr/keylayout/Vendor_0001_Product_0001_Version_0100.kl",
        ):
            if before.get(path) != after.get(path):
                raise RuntimeError("accepted native input artifact changed: " + path)

        (self.stage / "launcher-validation.json").write_text(json.dumps({
            "r5_device_accepted_home_preserved": True,
            "launcher_path": self.config["launcher"]["destination_path"],
        }, indent=2) + "\n", encoding="utf-8")
        native_report = {
            "base": "m8b-audio-r1 / m8b-rc-core-r5 (DEVICE ACCEPTED input)",
            "changed_system_scope": [changed_path],
            "unexpected_system_differences": [],
            "native_rc_core_and_repeat_unchanged": True,
            "device_keylayout_unchanged": True,
            "multi_ir_init_state": "disabled",
            "projectivy_and_power_policy_unchanged": True,
            "canonical_vendor_topology_preserved": True,
        }
        (self.stage / "native-input-validation.json").write_text(json.dumps(native_report, indent=2) + "\n", encoding="utf-8")
        report = {
            "base": "m8b-audio-r1",
            "changed_files": [changed_path],
            "property_change": {"from": contract["old_line"], "to": contract["new_line"]},
            "metadata_preserved": before_entry,
            "vndk_apex_unchanged": True,
            "system_linker_config_pb_unchanged": True,
            "unexpected_system_differences": [],
        }
        (self.stage / "audio-vndk-filesystem-validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return report

    def finish(self, firmware: Path, super_image: Path, vbmeta_system: Path) -> None:
        linker = self.config["linkerconfig_validation"]
        assert isinstance(linker, dict)
        generated = self.stage / "linkerconfig-offline"
        self.run([
            "wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "bash",
            self.wsl_path(REPO / "scripts" / "validate-m8b-audio-r2-linkerconfig.sh"),
            self.wsl_path(self.stage / "validation-logical" / "system_a.img"),
            self.wsl_path(self.stage / "validation-logical" / "vendor_a.img"),
            self.wsl_path(self.stage / "validation-logical" / "product_a.img"),
            str(linker["tool_path"]), self.wsl_path(generated), str(linker["tool_sha256"]),
        ])
        summary = (generated / "summary.txt").read_text(encoding="utf-8").splitlines()
        if "default->vndk libaudioroute.so=present" not in summary:
            raise RuntimeError("offline linkerconfig did not expose libaudioroute through default->vndk")

        super().finish(firmware, super_image, vbmeta_system)

        result_path = self.final / "build-result.json"
        result = json.loads(result_path.read_text(encoding="utf-8"))
        aosp_report = json.loads((self.final / "aosp-treble-vndk-validation.json").read_text(encoding="utf-8"))
        treble_report = {
            "root_cause": "ro.treble.enabled=false selected legacy linkerconfig despite an active VNDK 31 APEX and stock ro.vndk.version=31",
            "candidate_materialization": "single generated property conversion: ro.treble.enabled=false -> true",
            "aosp_product_contract": aosp_report,
            "offline_linkerconfig": {
                "tool_sha256": linker["tool_sha256"],
                "vendor_section": True,
                "vndk_namespace": True,
                "vndk_search_path": "/apex/com.android.vndk.v31/${LIB}",
                "default_to_vndk_exports_libaudioroute": True,
            },
            "generated_ld_config_sha256": base.digest(self.final / "linkerconfig-offline" / "ld.config.txt"),
            "generated_ld_config_patched": False,
            "vendor_libaudioroute_copy": False,
        }
        (self.final / "linker-namespace-validation.json").write_text(json.dumps(treble_report, indent=2) + "\n", encoding="utf-8")
        result["audio_treble_validation"] = treble_report
        if isinstance(result.get("audio_vndk_validation"), dict):
            result["audio_vndk_validation"]["namespace"] = treble_report["offline_linkerconfig"]
        result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        sums = [base.digest(path) + "  " + path.relative_to(self.final).as_posix() for path in sorted(self.final.rglob("*")) if path.is_file() and path.name != "SHA256SUMS"]
        (self.final / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--keep-failed", action="store_true")
    args = parser.parse_args()
    BuildM8BAudioR2(audio1.rc.merged_config(args.config), args.keep_failed).build()


if __name__ == "__main__":
    main()
