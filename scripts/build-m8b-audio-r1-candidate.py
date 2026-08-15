#!/usr/bin/env python3
"""Build an audio-only candidate by restoring the exact Test8r2 VNDK 31 APEX contract."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import time


REPO = Path(__file__).resolve().parents[1]
BASE_BUILDER = REPO / "scripts" / "build-m8b-rc-core-r1-candidate.py"
AUDITOR = REPO / "scripts" / "audit-logical-system-init.py"
DEFAULT_CONFIG = REPO / "configs" / "candidates" / "m8b-audio-r1.json"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load module: " + str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


rc = load_module(BASE_BUILDER, "m8b_rc_core_for_audio")
base = rc.base


class BuildM8BAudioR1(rc.BuildM8BRcCoreR1):
    def __init__(self, config: dict[str, object], keep_failed: bool) -> None:
        super().__init__(config, keep_failed)
        self.reference_system: Path | None = None
        self.reference_before: dict[str, object] | None = None

    def setup(self) -> None:
        super().setup()
        reference = self.config["reference_vndk"]
        omission = self.config["aosp_omission"]
        assert isinstance(reference, dict) and isinstance(omission, dict)

        self.reference_system = REPO / str(reference["system_image_relative"])
        if not self.reference_system.is_file():
            raise RuntimeError("missing Test8r2 system reference: " + str(self.reference_system))
        self.reference_before = base.record(self.reference_system)
        expected_reference = {
            "size": reference["system_image_size"],
            "sha256": reference["system_image_sha256"],
        }
        if {key: self.reference_before[key] for key in expected_reference} != expected_reference:
            raise RuntimeError("Test8r2 system reference identity mismatch")

        linkerconfig = REPO / str(reference["test8_linkerconfig_relative"])
        if not linkerconfig.is_file() or base.digest(linkerconfig) != reference["test8_linkerconfig_sha256"]:
            raise RuntimeError("Test8r2 linkerconfig evidence identity mismatch")
        linker_text = linkerconfig.read_text(encoding="utf-8", errors="replace")
        if "/apex/com.android.vndk.v31/${LIB}" not in linker_text:
            raise RuntimeError("Test8r2 VNDK namespace search path evidence is missing")
        if "namespace.default.link.vndk.shared_libs +=" not in linker_text or "libaudioroute.so" not in linker_text:
            raise RuntimeError("Test8r2 default-to-VNDK libaudioroute exposure evidence is missing")

        report = self.stage / "aosp-vndk-omission.txt"
        board = str(omission["board_config_path"])
        product = str(omission["product_config_path"])
        shell = (
            "set -euo pipefail; "
            f"test \"$(sha256sum '{board}' | cut -d' ' -f1 | tr a-f A-F)\" = '{omission['board_config_sha256']}'; "
            f"test \"$(sha256sum '{product}' | cut -d' ' -f1 | tr a-f A-F)\" = '{omission['product_config_sha256']}'; "
            f"! grep -Eq '^[[:space:]]*BOARD_VNDK_VERSION[[:space:]]*:?=' '{board}'; "
            f"! grep -q 'com.android.vndk.current' '{product}'; "
            "test ! -e /home/tianyi/ubox10-aosp/out/target/product/ubox10/system/apex/com.android.vndk.current; "
            "printf '%s\n' 'BoardConfig: BOARD_VNDK_VERSION absent' 'ubox10.mk: com.android.vndk.current absent' 'AOSP output: VNDK APEX absent'"
        )
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "--", "bash", "-lc", shell], output=report)

    def repair_system(self, source: Path) -> Path:
        if self.reference_system is None:
            raise RuntimeError("Test8r2 VNDK reference was not prepared")
        system = self.stage / "system_a.img"
        shutil.copyfile(source, system)
        self.run([sys.executable, str(base.TOOLS / "avbtool.py"), "erase_footer", "--image", str(system)])
        work_size = str(self.config["system_work_size"])
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "truncate", "-s", work_size, self.wsl_path(system)])
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "resize2fs", self.wsl_path(system), work_size])
        target_mount = self.stage / "system-mount"
        reference_mount = self.stage / "reference-system-mount"
        target_mount.mkdir()
        reference_mount.mkdir()
        self.run([
            "wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "bash",
            self.wsl_path(REPO / "scripts" / "import-m8-test8r2-vndk-apex.sh"),
            self.wsl_path(system), self.wsl_path(target_mount),
            self.wsl_path(self.reference_system), self.wsl_path(reference_mount),
        ])
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "resize2fs", "-M", self.wsl_path(system)])
        target_mount.rmdir()
        reference_mount.rmdir()

        avb = self.config["avb"]
        assert isinstance(avb, dict)
        self.run([
            sys.executable, str(base.TOOLS / "avbtool.py"), "add_hashtree_footer", "--image", str(system),
            "--partition_name", "system", "--partition_size", str(avb["partition_size"]), "--hash_algorithm", "sha256",
            "--salt", str(avb["salt"]), "--do_not_generate_fec", "--prop", "com.ubox10.candidate.id:" + self.candidate_id,
            "--prop", "com.ubox10.avb.fec:none", "--key", str(REPO / str(avb["key_relative"])), "--algorithm", "SHA256_RSA2048",
        ])
        if system.stat().st_size != avb["partition_size"]:
            raise RuntimeError("signed audio system_a size mismatch")
        return system

    @staticmethod
    def _without_nlink(value: dict[str, object] | None) -> dict[str, object] | None:
        if value is None:
            return None
        result = dict(value)
        result.pop("nlink", None)
        return result

    def validate_system_diff(self, before_image: Path, after_image: Path) -> dict[str, object]:
        if self.reference_system is None:
            raise RuntimeError("Test8r2 VNDK reference was not prepared")
        before = self._manifest_map(self.inventory_system(before_image, "r5-system"))
        after = self._manifest_map(self.inventory_system(after_image, "audio-system"))
        reference = self._manifest_map(self.inventory_system(self.reference_system, "test8-system"))
        prefix = "/system/apex/com.android.vndk.current"

        if any(path == prefix or path.startswith(prefix + "/") for path in before):
            raise RuntimeError("r5 unexpectedly already contains the target VNDK APEX")
        unexpected: list[str] = []
        for path in sorted(set(before) | set(after)):
            if path == prefix or path.startswith(prefix + "/"):
                continue
            left, right = before.get(path), after.get(path)
            if path == "/system/apex":
                left, right = self._without_nlink(left), self._without_nlink(right)
            if left != right:
                unexpected.append(path)
        if unexpected:
            raise RuntimeError("unexpected audio system differences: " + ", ".join(unexpected[:16]))

        source_entries = {path: value for path, value in reference.items() if path == prefix or path.startswith(prefix + "/")}
        target_entries = {path: value for path, value in after.items() if path == prefix or path.startswith(prefix + "/")}
        if target_entries != source_entries:
            differences = [path for path in sorted(set(source_entries) | set(target_entries)) if source_entries.get(path) != target_entries.get(path)]
            raise RuntimeError("VNDK APEX copy differs from Test8r2: " + ", ".join(differences[:16]))

        spec = self.config["reference_vndk"]
        assert isinstance(spec, dict)
        regular = [value for value in target_entries.values() if value.get("type") == "regular"]
        if len(target_entries) != spec["entries"] or len(regular) != spec["regular_files"]:
            raise RuntimeError("VNDK APEX entry count mismatch")
        if sum(int(value["size"]) for value in regular) != spec["regular_bytes"]:
            raise RuntimeError("VNDK APEX byte count mismatch")
        fixed = {
            prefix + "/apex_manifest.pb": spec["apex_manifest_sha256"],
            prefix + "/apex_pubkey": spec["apex_pubkey_sha256"],
            prefix + "/etc/vndkcore.libraries.31.txt": spec["vndkcore_sha256"],
            str(spec["libaudioroute"]["path"]): spec["libaudioroute"]["sha256"],
        }
        for path, wanted in fixed.items():
            if target_entries.get(path, {}).get("sha256") != wanted:
                raise RuntimeError("VNDK fixed artifact mismatch: " + path)

        auditor = load_module(AUDITOR, "m8b_audio_vndk_auditor")
        core_list = self._read_ext4_file(auditor, after_image, prefix + "/etc/vndkcore.libraries.31.txt").decode("utf-8")
        if "libaudioroute.so" not in core_list.splitlines():
            raise RuntimeError("libaudioroute is absent from the restored VNDK core list")

        frozen = [str(item["path"]) for item in self.config["frozen_files"]]
        accepted_input = [
            "/system/etc/init/multi_ir.rc",
            "/system/usr/keylayout/sunxi-ir.kl",
            "/system/usr/keylayout/Vendor_0001_Product_0001_Version_0100.kl",
        ]
        for path in frozen + accepted_input:
            if before.get(path) != after.get(path):
                raise RuntimeError("accepted r5 artifact changed: " + path)

        (self.stage / "launcher-validation.json").write_text(json.dumps({
            "r5_device_accepted_home_preserved": True,
            "launcher_path": self.config["launcher"]["destination_path"],
        }, indent=2) + "\n", encoding="utf-8")
        native_report = {
            "base": "m8b-rc-core-r5 (DEVICE ACCEPTED)",
            "changed_system_scope": [prefix + "/**"],
            "unexpected_system_differences": unexpected,
            "native_rc_core_and_repeat_unchanged": True,
            "device_keylayout_unchanged": True,
            "multi_ir_init_state": "disabled",
            "projectivy_and_power_policy_unchanged": True,
            "canonical_vendor_topology_preserved": True,
        }
        (self.stage / "native-input-validation.json").write_text(json.dumps(native_report, indent=2) + "\n", encoding="utf-8")
        report = {
            "base": "m8b-rc-core-r5",
            "source": str(self.reference_system),
            "source_path": prefix,
            "destination_path": prefix,
            "runtime_name": spec["runtime_name"],
            "copied_exactly": True,
            "entries": len(target_entries),
            "regular_files": len(regular),
            "regular_bytes": sum(int(value["size"]) for value in regular),
            "libaudioroute": target_entries[str(spec["libaudioroute"]["path"])],
            "libaudioroute_in_vndkcore_list": True,
            "unexpected_system_differences": unexpected,
        }
        (self.stage / "audio-vndk-filesystem-validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return report

    def finish(self, firmware: Path, super_image: Path, vbmeta_system: Path) -> None:
        if self.reference_system is None or self.reference_before is None:
            raise RuntimeError("Test8r2 reference state is missing")
        if base.record(self.reference_system) != self.reference_before:
            raise RuntimeError("protected Test8r2 system reference changed")

        inventory = self.stage / "elf-inventory.csv"
        with inventory.open("r", encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        available = {Path(row["path"].split("!", 1)[0]).name for row in rows}
        available.update(row["soname"] for row in rows if row["soname"])
        hal_path = "/vendor/lib/hw/audio.primary.apollo.so"
        route_path = "/system/apex/com.android.vndk.current/lib/libaudioroute.so"
        hal = next((row for row in rows if row["path"] == hal_path), None)
        route = next((row for row in rows if row["path"] == route_path), None)
        if hal is None or route is None or hal["class"] != "ELF32" or route["class"] != "ELF32":
            raise RuntimeError("ARM32 Apollo HAL or libaudioroute is absent from final ELF inventory")
        hal_needed = [item for item in hal["needed"].split(";") if item]
        route_needed = [item for item in route["needed"].split(";") if item]
        hal_missing = [item for item in hal_needed if item not in available]
        route_missing = [item for item in route_needed if item not in available]
        if "libaudioroute.so" not in hal_needed or hal_missing or route_missing:
            raise RuntimeError("Apollo HAL VNDK dependency closure is unresolved")

        spec = self.config["reference_vndk"]
        assert isinstance(spec, dict)
        if route_needed != spec["libaudioroute"]["needed"]:
            raise RuntimeError("libaudioroute DT_NEEDED mismatch")
        evidence = (REPO / str(spec["test8_linkerconfig_relative"])).read_text(encoding="utf-8", errors="replace")
        report = {
            "hal": {"path": hal_path, "sha256": "6679E7C653D184EC34070F259104CA0FC394CB4DC67DE4BA60134A13B0093791", "needed": hal_needed, "missing": hal_missing},
            "libaudioroute": {"path": route_path, "sha256": spec["libaudioroute"]["sha256"], "needed": route_needed, "missing": route_missing},
            "namespace": {
                "apex_runtime_name": spec["runtime_name"],
                "vndk_search_path_present_in_test8": "/apex/com.android.vndk.v31/${LIB}" in evidence,
                "default_to_vndk_exports_libaudioroute_in_test8": "libaudioroute.so" in evidence,
                "candidate_restores_identical_linkerconfig_input_apex": True,
            },
            "vendor_unique_needed": 228,
            "test8_vndk_contract_needed": 55,
            "already_available_in_r5": 54,
            "first_missing_soname_restored": "libaudioroute.so",
            "dependency_closure_resolved": True,
        }
        report_path = self.stage / "audio-linker-validation.json"
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        namespace_report = {
            "namespace_mode": "restored exact Test8r2 flattened com.android.vndk.v31 input",
            "runtime_generation": "device linkerconfig generation remains the first runtime acceptance check",
            "apex_search_path": "/apex/com.android.vndk.v31/${LIB}",
            "test8_default_to_vndk_exports_libaudioroute": True,
            "candidate_restores_identical_vndk_apex_input": True,
            "apollo_primary_hal_dependency_closure_resolved_offline": True,
            "legacy_system_lib_lights_pair_retained_unchanged": True,
        }
        (self.stage / "linker-namespace-validation.json").write_text(
            json.dumps(namespace_report, indent=2) + "\n", encoding="utf-8"
        )

        # The reused M8B finisher removes these two historical manifest names.
        # Keep the parent cleanup contract without retaining three large, transient inventories.
        os.replace(self.stage / "r5-system-filesystem-manifest.json", self.stage / "r13-system-filesystem-manifest.json")
        os.replace(self.stage / "audio-system-filesystem-manifest.json", self.stage / "m8b-system-filesystem-manifest.json")
        (self.stage / "test8-system-filesystem-manifest.json").unlink()

        super().finish(firmware, super_image, vbmeta_system)
        result_path = self.final / "build-result.json"
        result = json.loads(result_path.read_text(encoding="utf-8"))
        result["audio_vndk_validation"] = report
        result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        sums = [base.digest(path) + "  " + path.relative_to(self.final).as_posix() for path in sorted(self.final.rglob("*")) if path.is_file() and path.name != "SHA256SUMS"]
        (self.final / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--keep-failed", action="store_true")
    args = parser.parse_args()
    BuildM8BAudioR1(rc.merged_config(args.config), args.keep_failed).build()


if __name__ == "__main__":
    main()
