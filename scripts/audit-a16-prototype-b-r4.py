#!/usr/bin/env python3
"""Run the full B1 audit plus the B r4 product-scoped ABI-property gate."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys


REPO = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE = REPO / "out/candidates/a16-prototype-b-r4"
DEFAULT_CONFIG = REPO / "configs/candidates/a16-prototype-b-r4.json"
DEFAULT_AOSP = Path("/work/src/ubox10-a16-ceiling")
R3_AUDIT_PATH = REPO / "scripts/audit-a16-prototype-b-r3.py"
SPEC = importlib.util.spec_from_file_location("a16_b_r3_auditor_for_r4", R3_AUDIT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import r3 auditor: {R3_AUDIT_PATH}")
R3_AUDIT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = R3_AUDIT
SPEC.loader.exec_module(R3_AUDIT)


class Auditor(R3_AUDIT.Auditor):
    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__(args)
        self.r3_product_mount = self.mounts / "r3-product"

    @staticmethod
    def resolve(path: str) -> Path:
        value = Path(path)
        return value if value.is_absolute() else REPO / value

    def exact_base(self, name: str) -> Path:
        spec = self.cfg["_continuation"]["base_artifacts"][name]
        path = self.resolve(str(spec["path"]))
        actual = R3_AUDIT.AUDIT.R3.record(path)
        if actual["size"] != spec["size"] or actual["sha256"] != spec["sha256"]:
            raise RuntimeError(f"immutable r3 {name} identity changed: {actual}")
        return path

    def audit_root_mountpoint_delta(self, images: dict[str, Path]) -> dict[str, object]:
        base = self.exact_base("system_a")
        candidate_record = R3_AUDIT.AUDIT.R3.record(images["system"])
        base_record = R3_AUDIT.AUDIT.R3.record(base)
        if (
            candidate_record["size"] != base_record["size"]
            or candidate_record["sha256"] != base_record["sha256"]
        ):
            raise RuntimeError("r4 changed r3 system_a or its root mountpoint fixes")
        expected = {
            "/metadata": {
                "type": "directory", "mode": "0755", "uid": 0, "gid": 0,
                "selinux": "u:object_r:metadata_file:s0",
            },
            "/vendor": {
                "type": "directory", "mode": "0755", "uid": 0, "gid": 2000,
                "selinux": "u:object_r:vendor_file:s0",
            },
        }
        observed = {path: self.inode_contract(images["system"], path) for path in expected}
        if observed != expected:
            raise RuntimeError(f"r4 root mountpoint preservation changed: {observed}")
        return {
            "result": "PASS_BYTE_PRESERVED_FROM_PHYSICALLY_CROSSED_R3",
            "system_a": R3_AUDIT.AUDIT.R3.record(images["system"]),
            "metadata": observed["/metadata"],
            "vendor": observed["/vendor"],
            "fstab_sha256": self.cfg["_continuation"]["root_cause"]["fstab"]["sha256"],
            "first_stage_init_sha256": self.cfg["_continuation"]["root_cause"]["first_stage_init"]["r2_sha256"],
            "physical_provenance": (
                "Exact r3 physically crossed /metadata and /vendor SwitchRoot/first-stage contracts; "
                "r4 preserves signed system_a, boot, vendor_boot and fstab byte-for-byte."
            ),
        }

    def audit_elf(self, images: dict[str, Path]) -> dict[str, object]:
        result = super().audit_elf(images)
        product_prop = subprocess.check_output(
            ["debugfs", "-R", "cat /etc/build.prop", str(images["product"])],
            text=True, stderr=subprocess.DEVNULL,
        )
        expected = self.cfg["_continuation"]["generated_product_property_contract"]["properties"]
        lines = product_prop.splitlines()
        for name, value in expected.items():
            if lines.count(f"{name}={value}") != 1:
                raise RuntimeError(f"final signed product ABI property missing: {name}")
        product32 = expected["ro.product.product.cpu.abilist32"]
        product64 = expected["ro.product.product.cpu.abilist64"]
        derived = product64 + "," + product32
        if derived != expected["ro.product.product.cpu.abilist"]:
            raise RuntimeError("product ABI triplet is not canonical 64-then-32 order")
        result["signed_product_scoped_abi"] = expected
        result["expected_init_global_derivation"] = {
            "source": "product",
            "ro.product.cpu.abilist": derived,
            "ro.product.cpu.abilist32": product32,
            "ro.product.cpu.abilist64": product64,
        }
        result["global_abi_derivation_offline"] = "PASS_EXACT_R7_PRODUCT_PRIORITY"
        return result

    def audit_avb_lp_outer(self, images: dict[str, Path]) -> dict[str, object]:
        result = super().audit_avb_lp_outer(images)
        key = REPO / self.cfg["_continuation"]["avb_product"]["key_relative"]
        # avbtool resolves a hashtree descriptor's partition name beside the
        # image being verified.  lpunpack names this extent product_a.img, so
        # provide the canonical product.img alias instead of weakening AVB
        # verification or renaming the preserved LP output.
        product_view = self.audit / "product-avb-view"
        product_view.mkdir(parents=True, exist_ok=True)
        product_alias = product_view / "product.img"
        if product_alias.exists() or product_alias.is_symlink():
            product_alias.unlink()
        product_alias.symlink_to(images["product"].resolve())
        self.run([
            sys.executable, str(self.avbtool), "verify_image", "--image",
            str(product_alias), "--key", str(key),
        ], output=self.audit / "verify-product.img.log")
        self.run([
            sys.executable, str(self.avbtool), "info_image", "--image", str(images["product"]),
        ], output=self.audit / "info-product.img.txt")
        info = (self.audit / "info-product.img.txt").read_text(encoding="utf-8")
        avb = self.cfg["_continuation"]["avb_product"]
        for fragment in (
            "Algorithm:                SHA256_RSA2048",
            "Rollback Index:           0",
            "Rollback Index Location:  0",
            "Partition Name:        product",
            f"Salt:                  {avb['salt']}",
            "FEC num roots:         0",
            "com.ubox10.candidate.id -> 'a16-prototype-b-r4'",
        ):
            if fragment not in info:
                raise RuntimeError(f"product AVB contract missing: {fragment}")
        for name in ("vbmeta_system", "vbmeta_vendor"):
            expected = self.cfg["_continuation"]["base_artifacts"][name]
            actual = R3_AUDIT.AUDIT.R3.record(self.candidate / f"{name}.fex")
            if actual["size"] != expected["size"] or actual["sha256"] != expected["sha256"]:
                raise RuntimeError(f"r4 changed preserved {name}")
        result["product_avb_hashtree_no_fec"] = "PASS"
        result["product_rollback_index_location"] = "0/0"
        result["vbmeta_system_and_vendor_byte_preserved_from_r3"] = True
        return result

    def audit_preservation(self, images: dict[str, Path]) -> dict[str, object]:
        preserved: dict[str, object] = {}
        mappings = {
            "system_a": images["system"],
            "vendor_a": images["vendor"],
            "vendor_dlkm_a": images["vendor_dlkm"],
            "boot": self.candidate / "boot.fex",
            "vbmeta_system": self.candidate / "vbmeta_system.fex",
            "vbmeta_vendor": self.candidate / "vbmeta_vendor.fex",
        }
        for name, path in mappings.items():
            spec = self.cfg["_continuation"]["base_artifacts"][name]
            actual = R3_AUDIT.AUDIT.R3.record(path)
            if actual["size"] != spec["size"] or actual["sha256"] != spec["sha256"]:
                raise RuntimeError(f"r4 changed forbidden r3 artifact: {name}")
            preserved[name] = actual

        base_product = self.exact_base("product_a")
        self.r3_product_mount.mkdir(parents=True)
        self.run(["sudo", "mount", "-o", "loop,ro,noload", str(base_product),
                  str(self.r3_product_mount)])
        self.mounted.append(self.r3_product_mount)
        before = R3_AUDIT.AUDIT.R4.tree_manifest(self.r3_product_mount)
        after = R3_AUDIT.AUDIT.R4.tree_manifest(self.mounts / "product")
        added_paths = sorted(set(after) - set(before))
        removed_paths = sorted(set(before) - set(after))
        changed_paths = sorted(
            path for path in set(before) & set(after) if before[path] != after[path]
        )
        if added_paths or removed_paths or changed_paths != ["etc/build.prop"]:
            raise RuntimeError(
                f"r4 product tree delta expanded: added={added_paths}, "
                f"removed={removed_paths}, changed={changed_paths}"
            )
        old_prop = (self.r3_product_mount / "etc/build.prop").read_text(encoding="utf-8")
        new_prop = (self.mounts / "product/etc/build.prop").read_text(encoding="utf-8")
        additions = [
            f"{name}={value}" for name, value in
            self.cfg["_continuation"]["generated_product_property_contract"]["properties"].items()
        ]
        if [line for line in new_prop.splitlines() if line not in additions] != old_prop.splitlines():
            raise RuntimeError("r4 product build.prop changed beyond the ABI triplet")
        if [line for line in new_prop.splitlines() if line in additions] != additions:
            raise RuntimeError("r4 product ABI triplet is missing, duplicated or reordered")

        kernel = R3_AUDIT.AUDIT.R3.record(self.candidate / "kernel-evidence/Image")
        expected_kernel = self.r4_config["kernel_build"]["image"]
        if (kernel["size"] != expected_kernel["size"] or
                kernel["sha256"] != expected_kernel["sha256"] or
                self.build_result.get("kernel_rebuilt") is not False):
            raise RuntimeError("r4 changed frozen Path-A kernel")
        rollback = Path(str(self.r4_config["rollback"]["path"]))
        if R3_AUDIT.AUDIT.R3.record(rollback) != self.r4_config["rollback"]:
            raise RuntimeError("rollback image identity changed")

        vendor_before = R3_AUDIT.AUDIT.R4.tree_manifest(self.r4_vendor_mount)
        vendor_after = R3_AUDIT.AUDIT.R4.tree_manifest(self.mounts / "vendor")
        vendor_added = sorted(set(vendor_after) - set(vendor_before))
        vendor_removed = sorted(set(vendor_before) - set(vendor_after))
        vendor_changed = sorted(
            path for path in set(vendor_before) & set(vendor_after)
            if vendor_before[path] != vendor_after[path]
        )
        expected_vendor_added = sorted([
            "lib64", "lib64/egl", "lib64/egl/libGLES_mali.so", "lib64/hw",
            "lib64/hw/android.hardware.graphics.mapper@2.0-impl-2.1.so",
            "lib64/hw/gralloc.apollo.so",
        ])
        if vendor_added != expected_vendor_added or vendor_removed or vendor_changed != ["build.prop"]:
            raise RuntimeError("r4 changed the frozen B1 vendor semantic contract")
        return {
            "byte_preserved_from_r3": preserved,
            "product_tree_delta_from_r3": {
                "added": added_paths, "removed": removed_paths, "changed": changed_paths,
            },
            "product_build_prop_only_added_lines": additions,
            "vendor_b1_tree_delta_from_frozen_arm32_control": {
                "added": vendor_added, "removed": vendor_removed, "changed": vendor_changed,
            },
            "kernel": kernel, "kernel_rebuilt": False,
            "kernel_release": "5.4.302+", "path_a_six_configs": "PRESERVED",
            "vendor_dlkm_module_count": 22, "aic_fmac_contract": "PRESERVED",
            "graphics_providers": "BYTE_PRESERVED_FROM_PHYSICALLY_FAILED_R3",
            "hardware_authority": {
                "Wi-Fi": "UNCHANGED", "Ethernet": "UNCHANGED",
                "audio": "UNCHANGED_KNOWN_R4_CONTROL_P1_DEBT",
                "remote": "UNCHANGED", "HDMI_display": "UNCHANGED",
                "DT_DTBO_TEE_DRM_vendor_boot": "UNCHANGED",
            },
            "rollback": R3_AUDIT.AUDIT.R3.record(rollback),
            "result": "PASS_SINGLE_CAUSE_PRODUCT_ABI_PROPERTY_ONLY",
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
