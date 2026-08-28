#!/usr/bin/env python3
"""Build B r7 by replacing only the proven ARM64 mapper/gralloc ABI closure."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid


REPO = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO / "configs/candidates/a16-prototype-b-r7.json"
DEFAULT_AOSP = Path("/work/src/ubox10-a16-ceiling")
R6_CONFIG = REPO / "configs/candidates/a16-prototype-b-r6.json"

R6_PATH = REPO / "scripts/build-a16-prototype-b-r6-candidate.py"
R6_SPEC = importlib.util.spec_from_file_location("a16_b_r6_builder_for_r7", R6_PATH)
if R6_SPEC is None or R6_SPEC.loader is None:
    raise RuntimeError(f"cannot import r6 builder: {R6_PATH}")
R6 = importlib.util.module_from_spec(R6_SPEC)
sys.modules[R6_SPEC.name] = R6
R6_SPEC.loader.exec_module(R6)

SHARED = R6.SHARED


def source(path: str) -> Path:
    value = Path(path)
    return value if value.is_absolute() else REPO / value


def dynamic_contract(path: Path) -> dict[str, object]:
    header = subprocess.check_output(["readelf", "-h", str(path)], text=True)
    notes = subprocess.check_output(["readelf", "-W", "-n", str(path)], text=True)
    dynamic = subprocess.check_output(["readelf", "-W", "-d", str(path)], text=True)
    symbols = subprocess.check_output(
        ["nm", "-D", "--undefined-only", "--format=posix", str(path)], text=True
    )
    exports = subprocess.check_output(
        ["nm", "-D", "--defined-only", "--format=posix", str(path)], text=True
    )
    build_id = re.search(r"\bBuild ID:\s*([0-9a-fA-F]+)", notes)
    soname = re.search(r"\(SONAME\).*\[([^]]+)\]", dynamic)
    return {
        "elf64": "Class:                             ELF64" in header,
        "aarch64": "Machine:                           AArch64" in header,
        "build_id": build_id.group(1).lower() if build_id else None,
        "soname": soname.group(1) if soname else None,
        "dt_needed": re.findall(r"\(NEEDED\).*\[([^]]+)\]", dynamic),
        "imports_verbose_abort": "_ZNSt3__122__libcpp_verbose_abortEPKcz" in symbols,
        "exports": exports,
    }


class Builder(R6.Builder):
    def __init__(self, args: argparse.Namespace) -> None:
        base_args = argparse.Namespace(
            config=R6_CONFIG, aosp=args.aosp, keep_failed=args.keep_failed
        )
        super().__init__(base_args)
        raw = json.loads(args.config.read_text(encoding="utf-8"))
        self.args = args
        self.raw_cfg = raw
        self.cfg["id"] = raw["id"]
        self.cfg["status"] = raw["status"]
        self.cfg["base_candidate"] = raw["base_candidate"]
        self.cfg["_continuation"] = raw
        self.candidate_id = str(raw["id"])
        self.final = REPO / "out/candidates" / self.candidate_id
        self.stage = self.final.parent / f".{self.candidate_id}.staging-{uuid.uuid4().hex}"
        self.log = self.stage / "logs/01-commands.log"
        self.base = source(str(raw["base_candidate"]["path"]))
        self.started = time.time()

    def setup(self) -> None:
        if self.final.exists():
            raise RuntimeError(f"refusing to overwrite existing candidate: {self.final}")
        if self.raw_cfg["status"] != "ROOT_CAUSE_PROVEN_SINGLE_CAUSE_R7_AUTHORIZED":
            raise RuntimeError("r7 mapper correction is not authorized")
        self.stage.mkdir(parents=True)
        self.require(self.base, self.raw_cfg["base_candidate"], "immutable physical r6 outer")
        self.require(self.rollback, self.r4["rollback"], "Android 12 rollback")
        for name, spec in self.raw_cfg["base_artifacts"].items():
            self.require(source(str(spec["path"])), spec, f"r6 assembly control {name}")

        physical = json.loads(
            (REPO / self.raw_cfg["root_cause"]["physical_result"]).read_text(
                encoding="utf-8"
            )
        )
        audit = json.loads(
            (REPO / self.raw_cfg["root_cause"]["audit"]).read_text(encoding="utf-8")
        )
        control = json.loads(
            (REPO / self.raw_cfg["root_cause"]["control"]).read_text(encoding="utf-8")
        )
        if (
            not physical["graphics_failure"]["current_unique_primary_blocker"]
            or physical["graphics_failure"]["abort_message"] != "gralloc-mapper is missing"
            or audit["r7_decision"]["authorized"] is not True
            or audit["result"]
            != "PROVEN_ARM64_MAPPER_AND_GRALLOC_VNDK31_LIBCPP_BACKDEPLOY_FAILURE"
            or control["result"] != "PROVEN_SINGLE_ARCHITECTURE_DEPENDENCY_DIFFERENCE"
        ):
            raise RuntimeError("r7 root-cause authorization is not uniquely closed")

        manifest = subprocess.check_output(
            ["git", "-C", str(self.args.aosp / ".repo/manifests"), "rev-parse", "HEAD"],
            text=True,
        ).strip()
        interfaces = subprocess.check_output(
            ["git", "-C", str(self.args.aosp / "hardware/interfaces"), "rev-parse", "HEAD"],
            text=True,
        ).strip()
        source_contract = self.raw_cfg["source_contract"]
        if manifest != source_contract["manifest_commit"]:
            raise RuntimeError(f"exact r7 manifest changed: {manifest}")
        if interfaces != source_contract["hardware_interfaces_commit"]:
            raise RuntimeError(f"exact hardware/interfaces source changed: {interfaces}")
        for key in (
            "mapper_patch", "mapper_android_bp", "mapper_backdeploy_header",
            "gralloc_android_mk", "gralloc_backdeploy_header",
        ):
            spec = source_contract[key]
            path = source(str(spec.get("aosp_path", spec["path"])))
            self.require(path, {"size": path.stat().st_size, "sha256": spec["sha256"]}, key)
            tracked = spec.get("path")
            if tracked and not str(tracked).startswith("/work/"):
                tracked_path = source(str(tracked))
                self.require(
                    tracked_path,
                    {"size": tracked_path.stat().st_size, "sha256": spec["sha256"]},
                    f"tracked {key}",
                )
        patch = source(str(source_contract["mapper_patch"]["path"]))
        done = subprocess.run(
            ["git", "-C", str(self.args.aosp / "hardware/interfaces"), "apply", "--check", "-R", str(patch)],
            check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        if done.returncode != 0:
            raise RuntimeError("tracked mapper back-deploy patch is not exactly applied")

        for name, contract in self.raw_cfg["providers"].items():
            binary = Path(str(contract["source_path"]))
            self.require(binary, contract, f"r7 {name} build output")
            actual = dynamic_contract(binary)
            if (
                not actual["elf64"]
                or not actual["aarch64"]
                or actual["build_id"] != contract["build_id"]
                or actual["soname"] != contract["soname"]
                or actual["dt_needed"] != contract["dt_needed"]
                or actual["imports_verbose_abort"]
                or contract["required_export"] not in actual["exports"]
            ):
                raise RuntimeError(f"r7 {name} ELF/back-deploy contract changed")

        r6 = REPO / "out/candidates/a16-prototype-b-r6"
        shutil.copytree(r6 / "kernel-evidence", self.stage / "kernel-evidence")
        for name in (
            "final-build-variables.txt", "mali-intake.json",
            "active-product-build.prop.r5", "runtime-product-source-audit.json",
            "boringssl_self_test64",
        ):
            shutil.copyfile(r6 / name, self.stage / name)

    def prepare_system(self) -> tuple[Path, dict[str, object]]:
        spec = self.raw_cfg["base_artifacts"]["system_a"]
        original = source(str(spec["path"]))
        system = self.stage / "system_a.img"
        shutil.copyfile(original, system)
        self.require(system, spec, "byte-preserved r6 system_a")
        for path, expected in (
            ("/metadata", self.raw_cfg["root_mountpoint_contract"]["metadata"]),
            ("/vendor", self.raw_cfg["root_mountpoint_contract"]["vendor"]),
        ):
            inode = self.debugfs(system, f"stat {path}", capture=True)
            attrs = self.debugfs(system, f"ea_list {path}", capture=True)
            if (
                "Type: directory" not in inode
                or f"Mode:  {expected['mode']}" not in inode
                or expected["selinux"] not in attrs
            ):
                raise RuntimeError(f"r7 changed crossed root contract: {path}")
        product = self.debugfs(system, "stat /product", capture=True)
        if 'Fast link dest: "/system/product"' not in product:
            raise RuntimeError("r7 changed active embedded-product layout")
        properties = self.debugfs(
            system,
            f"cat {self.raw_cfg['active_product_property_contract']['active_path']}",
            capture=True,
        )
        for key, value in self.raw_cfg["active_product_property_contract"]["properties"].items():
            if f"{key}={value}" not in properties.splitlines():
                raise RuntimeError(f"r7 lost physically proven active ABI source: {key}")
        return system, {
            "base_r6": SHARED.record(original),
            "candidate": SHARED.record(system),
            "byte_preserved_from_r6": True,
            "active_product_global_abi_physical_result": "PASS_PRESERVED",
            "root_metadata_vendor_product_contract": "PASS_PRESERVED",
        }

    def prepare_vendor(self) -> tuple[Path, dict[str, object]]:
        spec = self.raw_cfg["base_artifacts"]["vendor_a"]
        original = source(str(spec["path"]))
        vendor = self.stage / "vendor_a.img"
        shutil.copyfile(original, vendor)
        self.require(vendor, spec, "exact r6 vendor_a")
        self.run([sys.executable, str(self.avbtool), "erase_footer", "--image", str(vendor)])
        if vendor.stat().st_size != self.cfg["avb"]["vendor"]["filesystem_size"]:
            raise RuntimeError("r6 vendor filesystem size changed")
        self.run(["e2fsck", "-fn", str(vendor)])

        retained: dict[str, dict[str, object]] = {}
        for name, lock in self.raw_cfg["retained_vendor_contract"].items():
            dumped = self.stage / f"retained-{name}"
            self.debugfs(vendor, f"dump -p {lock['path']} {dumped}")
            retained[name] = self.require(dumped, lock, f"retained vendor {name}")

        replaced: dict[str, object] = {}
        for name, contract in self.raw_cfg["providers"].items():
            target = str(contract["install_path"])
            old = self.stage / f"r6-{name}.so"
            self.debugfs(vendor, f"dump -p {target} {old}")
            self.debugfs(vendor, f"rm {target}")
            self.debugfs(vendor, f"write {contract['source_path']} {target}")
            for field, value in (
                ("mode", "0100644"), ("uid", "0"), ("gid", "0"),
                ("ctime", contract["times"]), ("atime", contract["times"]),
                ("mtime", contract["times"]), ("crtime", contract["times"]),
            ):
                self.debugfs(vendor, f"set_inode_field {target} {field} {value}")
            self.debugfs(
                vendor, f'ea_set {target} security.selinux "{contract["selinux"]}\\000"'
            )
            new = self.stage / f"r7-{name}.so"
            self.debugfs(vendor, f"dump -p {target} {new}")
            self.require(new, contract, f"installed r7 {name}")
            inode = self.debugfs(vendor, f"stat {target}", capture=True)
            attrs = self.debugfs(vendor, f"ea_list {target}", capture=True)
            if (
                "Mode:  0644" not in inode
                or "User:     0   Group:     0" not in inode
                or contract["selinux"] not in attrs
            ):
                raise RuntimeError(f"installed r7 {name} inode contract changed")
            replaced[name] = {
                "r6": SHARED.record(old),
                "r7": SHARED.record(new),
                "runtime_path": contract["runtime_path"],
            }
        for field in ("ctime", "atime", "mtime", "crtime"):
            self.debugfs(vendor, f"set_inode_field /lib64/hw {field} 0x6a8fff2b")
        self.run(["e2fsck", "-fy", str(vendor)], allowed={0, 1})
        self.run(["e2fsck", "-fn", str(vendor)])

        avb = self.cfg["avb"]["vendor"]
        self.run([
            sys.executable, str(self.avbtool), "add_hashtree_footer",
            "--image", str(vendor), "--partition_name", "vendor",
            "--partition_size", str(avb["partition_size"]),
            "--hash_algorithm", "sha256", "--salt", avb["salt"],
            "--prop", f"com.android.build.vendor.fingerprint:{avb['fingerprint']}",
            "--prop", f"com.android.build.vendor.os_version:{avb['os_version']}",
        ])
        if vendor.stat().st_size != avb["partition_size"]:
            raise RuntimeError("signed r7 vendor partition size changed")
        self.verify_avb_partition(vendor, "vendor", None)
        return vendor, {
            "base_r6": SHARED.record(original),
            "candidate": SHARED.record(vendor),
            "tree_delta": {
                "added": [],
                "removed": [],
                "changed": sorted(
                    str(item["runtime_path"]).removeprefix("/vendor/")
                    for item in self.raw_cfg["providers"].values()
                ),
            },
            "retained": retained,
            "replaced": replaced,
            "sphal_direct_symbol_closure": "PENDING_FULL_OFFLINE_AUDIT",
            "ext4": "PASS",
            "avb_hashtree_fec": "PASS",
        }

    def finish(
        self, firmware: Path, system_audit: dict[str, object],
        vendor_audit: dict[str, object], super_audit: dict[str, object],
        outer_audit: dict[str, object], vbmeta_system: Path, vbmeta_vendor: Path,
    ) -> None:
        super().finish(
            firmware, system_audit, vendor_audit, super_audit, outer_audit,
            vbmeta_system, vbmeta_vendor,
        )
        result_path = self.final / "build-result.json"
        result = json.loads(result_path.read_text(encoding="utf-8"))
        result["source"] = {
            "tag": "android-security-16.0.0_r7",
            "manifest_commit": self.raw_cfg["source_contract"]["manifest_commit"],
            "hardware_interfaces_commit": self.raw_cfg["source_contract"]["hardware_interfaces_commit"],
            "android_system_rebuilt": False,
            "kernel_rebuilt": False,
            "targeted_modules_built": [
                "android.hardware.graphics.mapper@2.0-impl-2.1",
                "gralloc.apollo",
            ],
            "architecture_scope": "ARM64_ONLY_CANDIDATE_PROVIDER_REPLACEMENT",
        }
        result["base_r6"] = result.pop("base_r5")
        result["physical_status"] = "NOT_YET_VALIDATED"
        result_path.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        sums = []
        for path in sorted(self.final.iterdir()):
            if path.is_file() and path.name != "SHA256SUMS":
                sums.append(f"{SHARED.digest(path)}  {path.name}")
        (self.final / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--aosp", type=Path, default=DEFAULT_AOSP)
    parser.add_argument("--keep-failed", action="store_true")
    Builder(parser.parse_args()).execute()


if __name__ == "__main__":
    main()
