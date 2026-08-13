#!/usr/bin/env python3
"""Build r10 by restoring the exact Test8r2 ARM32 vendor AIDL compatibility pair."""
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
BASE_BUILDER = REPO / "scripts" / "build-m8a-r9-candidate.py"
AUDITOR = REPO / "scripts" / "audit-logical-system-init.py"
DEFAULT_CONFIG = REPO / "configs" / "candidates" / "m8a-initial-atv-r10.json"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load module: " + str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base = load_module(BASE_BUILDER, "m8a_r9_builder")


class BuildR10(base.BuildR9):
    def __init__(self, config: dict[str, object], keep_failed: bool) -> None:
        super().__init__(config, keep_failed)
        self.project_root = REPO.parents[1]
        self.reference: Path | None = None
        self.reference_before: dict[str, object] | None = None
        self.reference_lib_dir: Path | None = None

    def setup(self) -> None:
        super().setup()
        reference = self.config["reference_test8r2"]
        assert isinstance(reference, dict)
        self.reference = self.project_root / str(reference["project_relative"])
        if not self.reference.is_file():
            raise RuntimeError("missing Test8r2 reference candidate: " + str(self.reference))
        self.reference_before = base.record(self.reference)
        if self.reference_before["size"] != reference["size"] or self.reference_before["sha256"] != reference["sha256"]:
            raise RuntimeError("Test8r2 reference candidate identity mismatch")
        self.extract_reference_libraries(reference)

    def extract_reference_libraries(self, reference: dict[str, object]) -> None:
        assert self.reference is not None
        outer = self.stage / "test8r2-source"
        outer.mkdir()
        self.run([
            sys.executable, str(base.TOOLS / "sunxi_image_tool.py"), "extract",
            "-o", str(outer), "-f", "super.fex", str(self.reference),
        ])
        super_image = outer / "super.fex"
        super_record = base.record(super_image)
        if super_record["size"] != reference["super_size"] or super_record["sha256"] != reference["super_sha256"]:
            raise RuntimeError("Test8r2 super identity mismatch")

        auditor = load_module(AUDITOR, "m8a_r10_logical_auditor")
        source = auditor.open_super_source(super_image)
        extracted: list[dict[str, object]] = []
        self.reference_lib_dir = self.stage / "test8r2-libraries"
        self.reference_lib_dir.mkdir()
        try:
            metadata = auditor.parse_lp_metadata(source)
            logical = auditor.LogicalPartitionSource(source, metadata, "system_a")
            ext4 = auditor.Ext4Reader(logical)
            libraries = self.config["compatibility_libraries"]
            assert isinstance(libraries, list)
            for item in libraries:
                assert isinstance(item, dict)
                path = str(item["source_path"]).lstrip("/")
                inode = ext4.lookup(path)
                if inode.mode & 0xF000 != 0x8000 or inode.mode & 0o7777 != 0o644:
                    raise RuntimeError("unexpected Test8r2 library inode: " + path)
                data = ext4.read_inode_data(inode)
                sha256 = hashlib.sha256(data).hexdigest().upper()
                if len(data) != item["size"] or sha256 != item["sha256"]:
                    raise RuntimeError("Test8r2 library identity mismatch: " + path)
                target = self.reference_lib_dir / str(item["name"])
                target.write_bytes(data)
                extracted.append({
                    "name": item["name"],
                    "partition": "system_a",
                    "source_path": item["source_path"],
                    "destination_path": item["destination_path"],
                    "size": len(data),
                    "sha256": sha256,
                    "mode": "0644",
                    "uid": 0,
                    "gid": 0,
                    "selinux": "u:object_r:system_lib_file:s0",
                    "soname": item["soname"],
                    "build_id": item["build_id"],
                })
        finally:
            source.close()
        report = {
            "reference_candidate": self.reference_before,
            "reference_super": super_record,
            "libraries": extracted,
        }
        (self.stage / "compatibility-source.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    def repair_system(self, source: Path) -> Path:
        if self.reference_lib_dir is None:
            raise RuntimeError("reference libraries were not prepared")
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
            self.wsl_path(REPO / "scripts" / "import-m8-test8r2-vendor-aidl-compat.sh"),
            self.wsl_path(system), self.wsl_path(mount_dir), self.wsl_path(self.reference_lib_dir),
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
            raise RuntimeError("signed r10 system_a size mismatch")
        return system

    def validate_system_diff(self, before_image: Path, after_image: Path) -> dict[str, object]:
        before_path = self.inventory_system(before_image, "r8-system")
        after_path = self.inventory_system(after_image, "r9-system")
        before, after = self._manifest_map(before_path), self._manifest_map(after_path)
        libraries = self.config["compatibility_libraries"]
        assert isinstance(libraries, list)
        allowed = {str(item["destination_path"]) for item in libraries if isinstance(item, dict)}
        unexpected: list[str] = []
        for path in sorted(set(before) | set(after)):
            if path in allowed:
                continue
            if before.get(path) != after.get(path):
                unexpected.append(path)
        if unexpected:
            raise RuntimeError("unexpected r10 system filesystem differences: " + ", ".join(unexpected[:16]))

        label = b"u:object_r:system_lib_file:s0\0".hex().upper()
        observed: list[dict[str, object]] = []
        for item in libraries:
            assert isinstance(item, dict)
            path = str(item["destination_path"])
            value = after.get(path)
            expected = {
                "type": "regular", "mode": "0644", "uid": 0, "gid": 0,
                "size": item["size"], "sha256": item["sha256"],
            }
            if value is None or any(value.get(key) != wanted for key, wanted in expected.items()):
                raise RuntimeError("r10 compatibility library metadata mismatch: " + path)
            if value.get("xattrs", {}).get("security.selinux") != label:
                raise RuntimeError("r10 compatibility library SELinux label mismatch: " + path)
            observed.append({"path": path, **expected, "selinux": "u:object_r:system_lib_file:s0"})

        vendor = after.get("/vendor")
        system_vendor = after.get("/system/vendor")
        if vendor is None or vendor.get("type") != "directory":
            raise RuntimeError("r9 canonical /vendor topology was not preserved")
        if system_vendor is None or system_vendor.get("type") != "symlink" or system_vendor.get("target") != "/vendor":
            raise RuntimeError("r9 /system/vendor compatibility link was not preserved")
        result = {
            "base": "m8a-initial-atv-r9",
            "added_files": observed,
            "unexpected_system_differences": unexpected,
            "linkerconfig_inputs_unchanged": True,
            "vintf_and_init_rc_unchanged": True,
            "selinux_policy_files_unchanged": True,
            "canonical_vendor_topology_preserved": True,
        }
        (self.stage / "compatibility-validation.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return result

    def validate_elf(self) -> None:
        logical = self.stage / "validation-logical"
        csv_path = self.stage / "elf-inventory.csv"
        summary = self.stage / "elf-summary.md"
        command = [sys.executable, str(REPO / "scripts" / "inventory-elf.py")]
        for name in ("system_a", "vendor_a", "product_a", "vendor_dlkm_a"):
            command += ["--partition", name.removesuffix("_a") + "=" + str(logical / (name + ".img"))]
        command += ["--csv", str(csv_path), "--summary", str(summary), "--label", self.candidate_id]
        self.run(command)

        with csv_path.open("r", encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        available = {Path(row["path"].split("!", 1)[0]).name for row in rows}
        available.update(row["soname"] for row in rows if row["soname"])
        targets = {
            "/vendor/bin/hw/android.hardware.lights-service": "android.hardware.light-V1-ndk_platform.so",
            "/vendor/bin/hw/android.hardware.rebootescrow-service.default": "android.hardware.rebootescrow-V1-ndk_platform.so",
        }
        result: dict[str, object] = {}
        for path, restored in targets.items():
            row = next((item for item in rows if item["path"] == path), None)
            if row is None:
                raise RuntimeError("missing target HAL from ELF inventory: " + path)
            needed = [item for item in row["needed"].split(";") if item]
            missing = [item for item in needed if item not in available]
            if missing or restored not in needed:
                raise RuntimeError("unresolved target HAL dependency: " + path + " -> " + ",".join(missing))
            result[path] = {"needed": needed, "missing": missing, "restored_dependency": restored}
        report = {
            "consumers": result,
            "namespace_mode": "generated config has no dir.vendor because r9 lacks com.android.vndk.v31; Android 12 linker uses no-config fallback",
            "fallback_search_paths_arm32": ["/system/lib", "/odm/lib", "/vendor/lib"],
            "restored_library_directory": "/system/lib",
            "target_hal_dependencies_resolved": True,
        }
        (self.stage / "linker-namespace-validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    def verify_filesystems(self) -> None:
        for name in ("system_a", "vendor_a", "product_a", "vendor_dlkm_a"):
            image = self.stage / "validation-logical" / (name + ".img")
            self.run(
                ["wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "e2fsck", "-fn", self.wsl_path(image)],
                output=self.stage / (name + "-e2fsck.txt"),
            )

    def finish(self, firmware: Path, super_image: Path, vbmeta_system: Path) -> None:
        assert self.reference is not None and self.reference_before is not None
        if base.record(self.reference) != self.reference_before:
            raise RuntimeError("protected Test8r2 reference candidate changed")
        source_path = self.stage / "compatibility-source.json"
        source_report = json.loads(source_path.read_text(encoding="utf-8"))
        source_report["reference_super"]["path"] = str(self.reference) + "#super.fex"
        source_path.write_text(json.dumps(source_report, indent=2) + "\n", encoding="utf-8")
        shutil.rmtree(self.stage / "test8r2-source")
        shutil.rmtree(self.stage / "test8r2-libraries")
        super().finish(firmware, super_image, vbmeta_system)

        result_path = self.final / "build-result.json"
        result = json.loads(result_path.read_text(encoding="utf-8"))
        result["repair"] = "Restore the exact Test8r2 ARM32 lights and rebootescrow ndk_platform compatibility pair into the r9 system fallback linker search path."
        result["compatibility_source"] = json.loads((self.final / "compatibility-source.json").read_text(encoding="utf-8"))
        result["linker_namespace"] = json.loads((self.final / "linker-namespace-validation.json").read_text(encoding="utf-8"))
        result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        sums = [base.digest(path) + "  " + path.name for path in sorted(self.final.iterdir()) if path.is_file() and path.name != "SHA256SUMS"]
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
    BuildR10(json.loads(args.config.read_text(encoding="utf-8")), args.keep_failed).build()


if __name__ == "__main__":
    main()
