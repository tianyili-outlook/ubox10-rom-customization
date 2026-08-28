#!/usr/bin/env python3
"""Run the full B1 audit plus the r6 one-file vendor BoringSSL64 gate."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys


REPO = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE = REPO / "out/candidates/a16-prototype-b-r6"
DEFAULT_CONFIG = REPO / "configs/candidates/a16-prototype-b-r6.json"
DEFAULT_AOSP = Path("/work/src/ubox10-a16-ceiling")

R5_PATH = REPO / "scripts/audit-a16-prototype-b-r5.py"
R5_SPEC = importlib.util.spec_from_file_location("a16_b_r5_auditor_for_r6", R5_PATH)
if R5_SPEC is None or R5_SPEC.loader is None:
    raise RuntimeError(f"cannot import r5 auditor: {R5_PATH}")
R5 = importlib.util.module_from_spec(R5_SPEC)
sys.modules[R5_SPEC.name] = R5
R5_SPEC.loader.exec_module(R5)

SHARED = R5.R3.AUDIT


class Auditor(R5.Auditor):
    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__(args)
        self.r5_vendor_mount = self.mounts / "r5-vendor"

    def audit_root_mountpoint_delta(self, images: dict[str, Path]) -> dict[str, object]:
        base = self.exact_base("system_a")
        self.r1_system_mount.mkdir(parents=True)
        self.run(["sudo", "mount", "-o", "loop,ro,noload", str(base), str(self.r1_system_mount)])
        self.mounted.append(self.r1_system_mount)
        before = SHARED.R4.tree_manifest(self.r1_system_mount)
        after = SHARED.R4.tree_manifest(self.mounts / "system")
        if before != after:
            added = sorted(set(after) - set(before))
            removed = sorted(set(before) - set(after))
            changed = sorted(name for name in set(before) & set(after) if before[name] != after[name])
            raise RuntimeError(
                f"r6 changed byte-preserved r5 system tree: added={added} "
                f"removed={removed} changed={changed}"
            )
        continuation = self.cfg["_continuation"]
        objects: dict[str, object] = {}
        for key in ("metadata", "vendor"):
            expected = continuation["root_mountpoint_contract"][key]
            observed = self.inode_contract(images["system"], expected["path"])
            for field in ("type", "mode", "uid", "gid", "selinux"):
                if observed is None or observed[field] != expected[field]:
                    raise RuntimeError(f"r6 changed crossed root object: {expected['path']}")
            objects[expected["path"]] = observed
        product = self.inode_contract(images["system"], "/product")
        target = self.symlink_target(images["system"], "/product")
        if product is None or product["type"] != "symlink" or target != "/system/product":
            raise RuntimeError("r6 changed the active embedded-product root layout")
        objects["/product"] = {"inode": product, "target": target}
        return {
            "result": "PASS_R5_SYSTEM_AND_CROSSED_ROOT_CONTRACT_BYTE_PRESERVED",
            "base_r5_system": SHARED.R3.record(base),
            "candidate_system": SHARED.R3.record(images["system"]),
            "tree_delta": {"added": [], "removed": [], "changed": []},
            "root_objects": objects,
            "active_product_global_abi": "PHYSICAL_PASS_FROM_R5_PRESERVED_OFFLINE",
        }

    def audit_preservation(self, images: dict[str, Path]) -> dict[str, object]:
        continuation = self.cfg["_continuation"]
        preserved: dict[str, object] = {}
        for name, image in (
            ("system_a", images["system"]),
            ("product_a", images["product"]),
            ("vendor_dlkm", images["vendor_dlkm"]),
            ("boot", self.candidate / "boot.fex"),
            ("vbmeta_system", self.candidate / "vbmeta_system.fex"),
        ):
            key = "vendor_dlkm" if name == "vendor_dlkm" else name
            spec = continuation["base_artifacts"][key]
            actual = SHARED.R3.record(image)
            if actual["size"] != spec["size"] or actual["sha256"] != spec["sha256"]:
                raise RuntimeError(f"r6 changed byte-preserved r5 artifact: {name}")
            preserved[name] = actual

        base_vendor = self.exact_base("vendor_a")
        self.r5_vendor_mount.mkdir(parents=True, exist_ok=True)
        self.run([
            "sudo", "mount", "-o", "loop,ro,noload", str(base_vendor),
            str(self.r5_vendor_mount),
        ])
        self.mounted.append(self.r5_vendor_mount)
        before = SHARED.R4.tree_manifest(self.r5_vendor_mount)
        after = SHARED.R4.tree_manifest(self.mounts / "vendor")
        added = sorted(set(after) - set(before))
        removed = sorted(set(before) - set(after))
        changed = sorted(name for name in set(before) & set(after) if before[name] != after[name])
        if added != ["bin/boringssl_self_test64"] or removed or changed:
            raise RuntimeError(
                f"r6 vendor semantic delta expanded: added={added} removed={removed} changed={changed}"
            )

        contract = continuation["boringssl64_contract"]
        binary = self.mounts / "vendor/bin/boringssl_self_test64"
        actual = SHARED.R3.record(binary)
        if actual["size"] != contract["size"] or actual["sha256"] != contract["sha256"]:
            raise RuntimeError("r6 vendor BoringSSL64 identity changed")
        inode = self.inode_contract(images["vendor"], "/bin/boringssl_self_test64")
        for field in ("mode", "uid", "gid", "selinux"):
            if inode is None or inode[field] != contract[field]:
                raise RuntimeError(f"r6 BoringSSL64 inode mismatch: {field}")
        header = subprocess.check_output(["readelf", "-h", str(binary)], text=True)
        notes = subprocess.check_output(["readelf", "-W", "-n", str(binary)], text=True)
        program = subprocess.check_output(["readelf", "-W", "-l", str(binary)], text=True)
        dynamic = subprocess.check_output(["readelf", "-W", "-d", str(binary)], text=True)
        needed = [
            line.split("[", 1)[1].split("]", 1)[0]
            for line in dynamic.splitlines() if "(NEEDED)" in line
        ]
        if (
            "Class:                             ELF64" not in header
            or "Machine:                           AArch64" not in header
            or f"Build ID: {contract['build_id']}" not in notes
            or f"Requesting program interpreter: {contract['interpreter']}" not in program
            or needed != contract["dt_needed"]
        ):
            raise RuntimeError("r6 installed BoringSSL64 ELF contract changed")

        provider_paths = [
            self.root / "apex/com.android.vndk.v31/lib64/libcrypto.so",
            self.root / "apex/com.android.vndk.v31/lib64/libc++.so",
            self.root / "apex/com.android.runtime/lib64/bionic/libc.so",
            self.root / "apex/com.android.runtime/lib64/bionic/libm.so",
            self.root / "apex/com.android.runtime/lib64/bionic/libdl.so",
        ]
        undefined, _ = SHARED.dynamic_symbols(binary)
        exported: set[str] = set()
        for provider in provider_paths:
            _, values = SHARED.dynamic_symbols(provider)
            exported.update(values)
        unmatched = sorted(undefined - exported)
        if len(undefined) != 2 or unmatched:
            raise RuntimeError(f"r6 BoringSSL64 strong symbol closure failed: {unmatched}")
        if (self.mounts / "vendor/lib64/libcrypto.so").exists():
            raise RuntimeError("r6 added forbidden standalone vendor libcrypto64")

        retained: dict[str, object] = {}
        for name, lock in continuation["retained_vendor_contract"].items():
            if not isinstance(lock, dict) or "path" not in lock:
                continue
            path = self.mounts / "vendor" / str(lock["path"]).lstrip("/")
            value = SHARED.R3.record(path)
            if value["size"] != lock["size"] or value["sha256"] != lock["sha256"]:
                raise RuntimeError(f"r6 changed retained vendor {name}")
            retained[name] = value

        graphics_locks = {
            "lib64/egl/libGLES_mali.so": "03333D495E3566C7D85CA2E000DA569A16CE8F022EA25C0EA61950C891D5C7F8",
            "lib64/hw/android.hardware.graphics.mapper@2.0-impl-2.1.so": "83A236476CB24DE2514159534A267334A4C8D7BC957497CD25C70C93F757762D",
            "lib64/hw/gralloc.apollo.so": "842BA5157989B6BCBF7DC800DC5323FAC9BEF37D914FA56A25A4656B97692E1F",
        }
        graphics: dict[str, object] = {}
        for relative, expected in graphics_locks.items():
            value = SHARED.R3.record(self.mounts / "vendor" / relative)
            if value["sha256"] != expected:
                raise RuntimeError(f"r6 changed graphics provider: {relative}")
            graphics[relative] = value

        rollback = Path(str(self.r4_config["rollback"]["path"]))
        if SHARED.R3.record(rollback) != self.r4_config["rollback"]:
            raise RuntimeError("rollback identity changed")
        return {
            "result": "PASS_R6_SINGLE_VENDOR_BORINGSSL64_FILE_AND_B1_PRESERVATION",
            "byte_preserved_r5_artifacts": preserved,
            "vendor_tree_added": added,
            "vendor_tree_removed": removed,
            "vendor_tree_changed": changed,
            "boringssl_self_test64": actual,
            "boringssl_self_test64_inode": inode,
            "dt_needed": needed,
            "strong_undefined_count": len(undefined),
            "strong_unmatched_count": len(unmatched),
            "provider_paths": [str(path) for path in provider_paths],
            "new_vendor_libcrypto": False,
            "retained_vendor": retained,
            "arm64_graphics_providers": graphics,
            "kernel_release": "5.4.302+",
            "path_a_six_configs": "PRESERVED",
            "vendor_dlkm_module_count": 22,
            "aic_fmac_contract": "PRESERVED",
            "hardware_authority": "UNCHANGED",
            "graphics_runtime_status": "UNCHANGED_INDEPENDENT_PHYSICAL_FAIL_NOT_FIXED_IN_R6",
            "rollback": SHARED.R3.record(rollback),
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--aosp", type=Path, default=DEFAULT_AOSP)
    parser.add_argument("--kernel-evidence", type=Path)
    parser.add_argument("--resume", action="store_true")
    Auditor(parser.parse_args()).execute()


if __name__ == "__main__":
    main()
