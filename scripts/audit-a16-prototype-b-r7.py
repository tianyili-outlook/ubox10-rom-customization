#!/usr/bin/env python3
"""Run full B1 acceptance plus the exact r7 ARM64 mapper/gralloc closure."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys


REPO = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE = REPO / "out/candidates/a16-prototype-b-r7"
DEFAULT_CONFIG = REPO / "configs/candidates/a16-prototype-b-r7.json"
DEFAULT_AOSP = Path("/work/src/ubox10-a16-ceiling")

R6_PATH = REPO / "scripts/audit-a16-prototype-b-r6.py"
R6_SPEC = importlib.util.spec_from_file_location("a16_b_r6_auditor_for_r7", R6_PATH)
if R6_SPEC is None or R6_SPEC.loader is None:
    raise RuntimeError(f"cannot import r6 auditor: {R6_PATH}")
R6 = importlib.util.module_from_spec(R6_SPEC)
sys.modules[R6_SPEC.name] = R6
R6_SPEC.loader.exec_module(R6)

SHARED = R6.SHARED


class Auditor(R6.Auditor):
    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__(args)
        self.r6_vendor_mount = self.mounts / "r6-vendor"

    def audit_root_mountpoint_delta(self, images: dict[str, Path]) -> dict[str, object]:
        result = super().audit_root_mountpoint_delta(images)
        result["result"] = "PASS_R6_SYSTEM_AND_ALL_CROSSED_ROOT_CONTRACTS_BYTE_PRESERVED"
        result["physical_scope"] = (
            "R6 metadata/vendor/product layout and mixed ABI were physically crossed; "
            "r7 preserves them byte-for-byte."
        )
        return result

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
            spec = continuation["base_artifacts"][name]
            actual = SHARED.R3.record(image)
            if actual["size"] != spec["size"] or actual["sha256"] != spec["sha256"]:
                raise RuntimeError(f"r7 changed byte-preserved r6 artifact: {name}")
            preserved[name] = actual

        base_vendor = self.exact_base("vendor_a")
        self.r6_vendor_mount.mkdir(parents=True, exist_ok=True)
        self.run([
            "sudo", "mount", "-o", "loop,ro,noload", str(base_vendor),
            str(self.r6_vendor_mount),
        ])
        self.mounted.append(self.r6_vendor_mount)
        before = SHARED.R4.tree_manifest(self.r6_vendor_mount)
        after = SHARED.R4.tree_manifest(self.mounts / "vendor")
        added = sorted(set(after) - set(before))
        removed = sorted(set(before) - set(after))
        changed = sorted(name for name in set(before) & set(after) if before[name] != after[name])
        expected_changed = sorted([
            "lib64/hw/android.hardware.graphics.mapper@2.0-impl-2.1.so",
            "lib64/hw/gralloc.apollo.so",
        ])
        if added or removed or changed != expected_changed:
            raise RuntimeError(
                f"r7 vendor semantic delta expanded: added={added} removed={removed} changed={changed}"
            )

        providers: dict[str, object] = {}
        for name, contract in continuation["providers"].items():
            path = self.mounts / "vendor" / str(contract["install_path"]).lstrip("/")
            value = SHARED.R3.record(path)
            if value["size"] != contract["size"] or value["sha256"] != contract["sha256"]:
                raise RuntimeError(f"r7 {name} identity changed")
            inode = self.inode_contract(images["vendor"], str(contract["install_path"]))
            for field in ("mode", "uid", "gid", "selinux"):
                if inode is None or inode[field] != contract[field]:
                    raise RuntimeError(f"r7 {name} inode mismatch: {field}")
            dynamic = subprocess.check_output(["readelf", "-W", "-d", str(path)], text=True)
            needed = [
                line.split("[", 1)[1].split("]", 1)[0]
                for line in dynamic.splitlines() if "(NEEDED)" in line
            ]
            if needed != contract["dt_needed"]:
                raise RuntimeError(f"r7 {name} DT_NEEDED changed")
            imports = subprocess.check_output(
                ["nm", "-D", "--undefined-only", str(path)], text=True
            )
            exports = subprocess.check_output(
                ["nm", "-D", "--defined-only", str(path)], text=True
            )
            if (
                "_ZNSt3__122__libcpp_verbose_abortEPKcz" in imports
                or contract["required_export"] not in exports
            ):
                raise RuntimeError(f"r7 {name} back-deploy/export contract changed")
            providers[name] = {"identity": value, "inode": inode, "dt_needed": needed}

        retained: dict[str, object] = {}
        for name, contract in continuation["retained_vendor_contract"].items():
            path = self.mounts / "vendor" / str(contract["path"]).lstrip("/")
            value = SHARED.R3.record(path)
            if value["size"] != contract["size"] or value["sha256"] != contract["sha256"]:
                raise RuntimeError(f"r7 changed retained vendor object: {name}")
            retained[name] = value

        closure_path = self.audit / "graphics-sphal-closure.json"
        self.run([
            sys.executable, str(REPO / "scripts/check-a16-prototype-b-r7-graphics.py"),
            "--mapper", str(self.mounts / "vendor/lib64/hw/android.hardware.graphics.mapper@2.0-impl-2.1.so"),
            "--gralloc", str(self.mounts / "vendor/lib64/hw/gralloc.apollo.so"),
            "--system-lib64", str(self.root / "system/lib64"),
            "--runtime-lib64", str(self.root / "apex/com.android.runtime/lib64/bionic"),
            "--vndk-lib64", str(self.root / "apex/com.android.vndk.v31/lib64"),
            "--linker-config", str(self.audit / "linker-generated/ld.config.txt"),
            "--output", str(closure_path),
        ], output=self.audit / "graphics-sphal-closure.log")
        closure = json.loads(closure_path.read_text(encoding="utf-8"))
        if closure["decision"] != "PASS_EXACT_ARM64_MAPPER_GRALLOC_SPHAL_CLOSURE":
            raise RuntimeError("r7 exact ARM64 mapper/gralloc closure did not pass")

        rollback = Path(str(self.r4_config["rollback"]["path"]))
        if SHARED.R3.record(rollback) != self.r4_config["rollback"]:
            raise RuntimeError("rollback identity changed")
        return {
            "result": "PASS_R7_TWO_FILE_SINGLE_MAPPER_INSTANTIATION_CLOSURE_AND_B1_PRESERVATION",
            "byte_preserved_r6_artifacts": preserved,
            "vendor_tree_added": added,
            "vendor_tree_removed": removed,
            "vendor_tree_changed": changed,
            "arm64_graphics_providers": providers,
            "retained_vendor": retained,
            "sphal_symbol_closure": closure,
            "manifest_transport": "BYTE_PRESERVED_HIDL_2_1_PASSTHROUGH_32_PLUS_64_DEFAULT",
            "mali": "BYTE_PRESERVED_NOT_CURRENT_CAUSAL_DELTA",
            "arm32_mapper_gralloc": "BYTE_PRESERVED_CONTROL",
            "boringssl32_64": "BYTE_PRESERVED_PHYSICAL_R6_GATE",
            "kernel_release": "5.4.302+",
            "path_a_six_configs": "PRESERVED",
            "vendor_dlkm_module_count": 22,
            "aic_fmac_contract": "PRESERVED",
            "hardware_authority": "UNCHANGED",
            "physical_status": "NOT_YET_VALIDATED",
            "rollback": SHARED.R3.record(rollback),
        }

    def finish_b1(
        self,
        images: dict[str, Path],
        apex: dict[str, object],
        compatibility: dict[str, object],
        elf: dict[str, object],
        avb_lp_outer: dict[str, object],
        preservation: dict[str, object],
        root_mountpoint: dict[str, object],
    ) -> None:
        super().finish_b1(
            images, apex, compatibility, elf, avb_lp_outer, preservation,
            root_mountpoint,
        )
        audit_path = self.audit / "offline-audit.json"
        result = json.loads(audit_path.read_text(encoding="utf-8"))
        result["graphics_mapper"] = {
            "root_cause": "PROVEN_R6_VNDK31_LIBCPP_BACKDEPLOY_FAILURE",
            "candidate_closure": "PASS_OFFLINE_ZERO_UNMATCHED_FOR_MAPPER_AND_GRALLOC",
            "runtime_status": "NOT_YET_VALIDATED",
        }
        result["limitations"] = [
            "No physical UBOX action occurred or is authorized by this offline audit.",
            "R6 physically reached both ART runtimes and zygote64 preload; r7 mapper runtime success, stable SurfaceFlinger and system_server remain unproven until physical validation.",
            "Offline mapper/gralloc relocation closure does not prove exact-board buffer allocation, HWC, EGL or Mali runtime.",
            "Offline SELinux compilation does not prove enforcing runtime compatibility.",
            "Full VINTF remains exit 65 only for inherited CONFIG_NFS_FS=y versus FCM-6 n and is NOT PASS.",
            "Known r4 boot-time auto-recovered audio failure remains unchanged and unfixed.",
        ]
        audit_path.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        build_result_path = self.candidate / "build-result.json"
        build_result = json.loads(build_result_path.read_text(encoding="utf-8"))
        build_result["offline_audit"] = SHARED.R3.record(audit_path)
        build_result_path.write_text(
            json.dumps(build_result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        sums = []
        for path in sorted(self.candidate.iterdir()):
            if path.is_file() and path.name != "SHA256SUMS":
                sums.append(f"{SHARED.R3.digest(path)}  {path.name}")
        (self.candidate / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")


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
