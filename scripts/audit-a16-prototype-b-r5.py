#!/usr/bin/env python3
"""Run the full B1 audit plus the r5 active product-source gate."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys


REPO = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE = REPO / "out/candidates/a16-prototype-b-r5"
DEFAULT_CONFIG = REPO / "configs/candidates/a16-prototype-b-r5.json"
DEFAULT_AOSP = Path("/work/src/ubox10-a16-ceiling")

R3_PATH = REPO / "scripts/audit-a16-prototype-b-r3.py"
R3_SPEC = importlib.util.spec_from_file_location("a16_b_r3_auditor_for_r5", R3_PATH)
if R3_SPEC is None or R3_SPEC.loader is None:
    raise RuntimeError(f"cannot import r3 auditor: {R3_PATH}")
R3 = importlib.util.module_from_spec(R3_SPEC)
sys.modules[R3_SPEC.name] = R3
R3_SPEC.loader.exec_module(R3)

CHECK_PATH = REPO / "scripts/check-a16-prototype-b-runtime-product-source.py"
CHECK_SPEC = importlib.util.spec_from_file_location("a16_b_runtime_product_audit", CHECK_PATH)
if CHECK_SPEC is None or CHECK_SPEC.loader is None:
    raise RuntimeError(f"cannot import runtime product checker: {CHECK_PATH}")
CHECK = importlib.util.module_from_spec(CHECK_SPEC)
sys.modules[CHECK_SPEC.name] = CHECK
CHECK_SPEC.loader.exec_module(CHECK)


class Auditor(R3.Auditor):
    @staticmethod
    def resolve(path: str) -> Path:
        value = Path(path)
        return value if value.is_absolute() else REPO / value

    def exact_base(self, name: str) -> Path:
        spec = self.cfg["_continuation"]["base_artifacts"][name]
        path = self.resolve(str(spec["path"]))
        actual = R3.AUDIT.R3.record(path)
        if actual["size"] != spec["size"] or actual["sha256"] != spec["sha256"]:
            raise RuntimeError(f"r5 assembly control changed: {name}={actual}")
        return path

    def audit_root_mountpoint_delta(self, images: dict[str, Path]) -> dict[str, object]:
        base = self.exact_base("system_a")
        self.r1_system_mount.mkdir(parents=True)
        self.run(["sudo", "mount", "-o", "loop,ro,noload", str(base), str(self.r1_system_mount)])
        self.mounted.append(self.r1_system_mount)
        before = R3.AUDIT.R4.tree_manifest(self.r1_system_mount)
        after = R3.AUDIT.R4.tree_manifest(self.mounts / "system")
        added = sorted(set(after) - set(before))
        removed = sorted(set(before) - set(after))
        changed = sorted(name for name in set(before) & set(after) if before[name] != after[name])
        expected_changed = ["system/product/etc/build.prop"]
        if added or removed or changed != expected_changed:
            raise RuntimeError(
                f"r5 signed system tree delta expanded: added={added}, removed={removed}, "
                f"changed={changed}"
            )

        expected = self.cfg["_continuation"]["root_mountpoint_contract"]
        observed_metadata = self.inode_contract(images["system"], "/metadata")
        observed_vendor = self.inode_contract(images["system"], "/vendor")
        product = self.inode_contract(images["system"], "/product")
        product_target = self.symlink_target(images["system"], "/product")
        for observed, locked in (
            (observed_metadata, expected["metadata"]),
            (observed_vendor, expected["vendor"]),
        ):
            for key in ("type", "mode", "uid", "gid", "selinux"):
                if observed is None or observed[key] != locked[key]:
                    raise RuntimeError(f"r5 changed physically crossed root contract: {locked['path']}")
        if product is None or product["type"] != "symlink" or product_target != "/system/product":
            raise RuntimeError("r5 changed the proven runtime /product alias")

        skip_path = self.cfg["_continuation"]["skip_mount_contract"]["path"]
        skip = self.file_text(images["system"], skip_path)
        if "/product" not in skip.splitlines():
            raise RuntimeError("r5 no longer skips standalone logical product mount")
        return {
            "result": "PASS_SINGLE_ACTIVE_PRODUCT_PROPERTY_SOURCE_ONLY",
            "base_system": R3.AUDIT.R3.record(base),
            "candidate_system": R3.AUDIT.R3.record(images["system"]),
            "tree_delta": {"added": added, "removed": removed, "changed": changed},
            "metadata": observed_metadata,
            "vendor": observed_vendor,
            "root_product": product,
            "root_product_target": product_target,
            "runtime_active_property_path": "/system/product/etc/build.prop",
            "skip_mount_path": skip_path,
            "skip_mount_product": "PRESENT",
            "physical_scope": "OFFLINE_ONLY_R5_NOT_YET_PHYSICALLY_VALIDATED",
        }

    def audit_elf(self, images: dict[str, Path]) -> dict[str, object]:
        result = super().audit_elf(images)
        dumpvars = self.candidate / "final-build-variables.txt"
        active = CHECK.audit(
            self.args.config, self.args.aosp, images["system"], images["product"],
            dumpvars.read_text(encoding="utf-8"),
        )
        result["active_runtime_product_source"] = active
        result["global_abi_derivation_offline"] = (
            "PASS_EXACT_R7_ACTIVE_PRODUCT_PRIORITY_NOT_A_PHYSICAL_RUNTIME_RESULT"
        )
        return result

    def audit_avb_lp_outer(self, images: dict[str, Path]) -> dict[str, object]:
        result = super().audit_avb_lp_outer(images)
        product = R3.AUDIT.R3.record(images["product"])
        expected = self.cfg["_continuation"]["base_artifacts"]["product_a"]
        if product["size"] != expected["size"] or product["sha256"] != expected["sha256"]:
            raise RuntimeError("r5 did not restore exact r3 inactive logical product_a")
        result["inactive_product_a_restored_exact_r3"] = product
        result["inactive_product_a_runtime_role"] = "SKIPPED_BY_SIGNED_GSI_SKIP_MOUNT"
        return result

    def audit_preservation(self, images: dict[str, Path]) -> dict[str, object]:
        result = super().audit_preservation(images)
        for name, path in (
            ("vendor_a", images["vendor"]),
            ("vendor_dlkm", images["vendor_dlkm"]),
            ("boot", self.candidate / "boot.fex"),
        ):
            spec = self.cfg["_continuation"]["base_artifacts"][name]
            actual = R3.AUDIT.R3.record(path)
            if actual["size"] != spec["size"] or actual["sha256"] != spec["sha256"]:
                raise RuntimeError(f"r5 changed preserved {name}")

        provider_paths = {
            "Mali": "lib64/egl/libGLES_mali.so",
            "mapper": "lib64/hw/android.hardware.graphics.mapper@2.0-impl-2.1.so",
            "gralloc": "lib64/hw/gralloc.apollo.so",
        }
        expected_hashes = {
            "Mali": "03333D495E3566C7D85CA2E000DA569A16CE8F022EA25C0EA61950C891D5C7F8",
            "mapper": "83A236476CB24DE2514159534A267334A4C8D7BC957497CD25C70C93F757762D",
            "gralloc": "842BA5157989B6BCBF7DC800DC5323FAC9BEF37D914FA56A25A4656B97692E1F",
        }
        providers: dict[str, object] = {}
        for name, relative in provider_paths.items():
            path = self.mounts / "vendor" / relative
            value = R3.AUDIT.R3.record(path)
            if value["sha256"] != expected_hashes[name]:
                raise RuntimeError(f"r5 changed ARM64 graphics provider: {name}")
            providers[name] = value
        result["arm64_graphics_providers"] = providers
        result["graphics_runtime_status"] = "UNCHANGED_INDEPENDENT_PHYSICAL_FAIL_NOT_FIXED_IN_R5"
        result["active_system_tree_delta"] = ["system/product/etc/build.prop"]
        result["inactive_product_a"] = "EXACT_R3_BYTES_NO_ABI_TRIPLET"
        result["result"] = "PASS_R5_SINGLE_ACTIVE_SOURCE_DELTA_AND_B1_PRESERVATION"
        return result


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
