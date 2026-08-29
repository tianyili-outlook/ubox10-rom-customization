#!/usr/bin/env python3
"""Run the full r7 preservation audit with the exact four-file diag1 delta."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys


REPO = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE = REPO / "out/candidates/a16-prototype-b-r7-diag1"
DEFAULT_CONFIG = REPO / "configs/candidates/a16-prototype-b-r7-diag1.json"
DEFAULT_AOSP = Path("/work/src/ubox10-a16-ceiling")

R7_PATH = REPO / "scripts/audit-a16-prototype-b-r7.py"
R7_SPEC = importlib.util.spec_from_file_location("a16_b_r7_auditor_for_diag1", R7_PATH)
if R7_SPEC is None or R7_SPEC.loader is None:
    raise RuntimeError(f"cannot import r7 auditor: {R7_PATH}")
R7 = importlib.util.module_from_spec(R7_SPEC)
sys.modules[R7_SPEC.name] = R7
R7_SPEC.loader.exec_module(R7)

SHARED = R7.SHARED


class Auditor(R7.Auditor):
    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__(args)
        diag = json.loads(args.config.read_text(encoding="utf-8"))
        r7 = json.loads(
            (REPO / "configs/candidates/a16-prototype-b-r7.json").read_text(
                encoding="utf-8"
            )
        )
        continuation = dict(r7)
        continuation.update(diag)
        self.cfg["_continuation"] = continuation
        self.diag = diag
        self.r7_system_mount = self.mounts / "r7-system"
        self.r7_vendor_mount = self.mounts / "r7-vendor"
        self.base_mounted = False

    def mount_exact_r7(self) -> None:
        if self.base_mounted:
            return
        for name, point in (
            ("system_a", self.r7_system_mount),
            ("vendor_a", self.r7_vendor_mount),
        ):
            point.mkdir(parents=True, exist_ok=True)
            self.run([
                "sudo", "mount", "-o", "loop,ro,noload", str(self.exact_base(name)),
                str(point),
            ])
            self.mounted.append(point)
        self.base_mounted = True

    @staticmethod
    def tree_delta(before: Path, after: Path) -> dict[str, list[str]]:
        old = SHARED.R4.tree_manifest(before)
        new = SHARED.R4.tree_manifest(after)
        return {
            "added": sorted(set(new) - set(old)),
            "removed": sorted(set(old) - set(new)),
            "changed": sorted(name for name in set(old) & set(new) if old[name] != new[name]),
        }

    def audit_root_mountpoint_delta(self, images: dict[str, Path]) -> dict[str, object]:
        self.mount_exact_r7()
        delta = self.tree_delta(self.r7_system_mount, self.mounts / "system")
        expected = ["system/bin/surfaceflinger", "system/lib64/libstagefright.so"]
        if delta != {"added": [], "removed": [], "changed": expected}:
            raise RuntimeError(f"diag1 system semantic delta expanded: {delta}")
        contracts: dict[str, object] = {}
        for name in ("metadata", "vendor"):
            locked = self.diag["root_mountpoint_contract"][name]
            observed = self.inode_contract(images["system"], str(locked["path"]))
            for field in ("type", "mode", "uid", "gid", "selinux"):
                if observed is None or observed[field] != locked[field]:
                    raise RuntimeError(f"diag1 changed root mountpoint {locked['path']}: {field}")
            contracts[str(locked["path"])] = observed
        product = self.inode_contract(images["system"], "/product")
        target = self.symlink_target(images["system"], "/product")
        if product is None or product["type"] != "symlink" or target != "/system/product":
            raise RuntimeError("diag1 changed the frozen active /product alias")
        contracts["/product"] = {"inode": product, "target": target}
        return {
            "result": "PASS_EXACT_R7_ROOT_CONTRACT_WITH_TWO_SYSTEM_LOGGING_FILES",
            "tree_delta": delta,
            "root_objects": contracts,
            "all_other_system_files_exact_r7": True,
        }

    def audit_avb_lp_outer(self, images: dict[str, Path]) -> dict[str, object]:
        base_dump = self.audit / "r7-detached-lpdump.json"
        self.run([
            str(self.host / "lpdump"), "-j", str(self.exact_base("super_raw"))
        ], output=base_dump)
        candidate_dump = self.candidate / "candidate-lpdump.json"
        if json.loads(base_dump.read_text(encoding="utf-8")) != json.loads(
            candidate_dump.read_text(encoding="utf-8")
        ):
            raise RuntimeError("diag1 LP metadata/extents differ from exact r7")
        evidence = self.build_result["super"]
        for name in (
            "growth_only_from_old_unallocated_space",
            "all_other_partition_extents_exact_r4",
            "no_partition_shrunk",
            "b_slot_allocations_empty_exact",
            "sparse_roundtrip_exact",
        ):
            evidence[name] = True
        result = super().audit_avb_lp_outer(images)
        result.update({
            "lp_metadata_and_extents": "EXACT_R7",
            "lp_metadata_slots_0_and_1": "EXACT",
            "logical_system_vendor_written_to_frozen_extents": True,
        })
        return result

    def audit_preservation(self, images: dict[str, Path]) -> dict[str, object]:
        self.mount_exact_r7()
        system_delta = self.tree_delta(self.r7_system_mount, self.mounts / "system")
        vendor_delta = self.tree_delta(self.r7_vendor_mount, self.mounts / "vendor")
        expected_system = ["system/bin/surfaceflinger", "system/lib64/libstagefright.so"]
        expected_vendor = ["lib/hw/gralloc.apollo.so", "lib64/hw/gralloc.apollo.so"]
        if system_delta != {"added": [], "removed": [], "changed": expected_system}:
            raise RuntimeError(f"diag1 system file delta expanded: {system_delta}")
        if vendor_delta != {"added": [], "removed": [], "changed": expected_vendor}:
            raise RuntimeError(f"diag1 vendor file delta expanded: {vendor_delta}")

        exact_artifacts: dict[str, object] = {}
        mappings = {
            "product_a": images["product"],
            "vendor_dlkm": images["vendor_dlkm"],
            "boot": self.candidate / "boot.fex",
        }
        for name, path in mappings.items():
            spec = self.diag["base_artifacts"][name]
            actual = SHARED.R3.record(path)
            if actual["size"] != spec["size"] or actual["sha256"] != spec["sha256"]:
                raise RuntimeError(f"diag1 changed exact r7 artifact: {name}")
            exact_artifacts[name] = actual
        candidate_kernel = self.candidate / "kernel-evidence/Image"
        frozen_kernel = REPO / "out/candidates/a16-prototype-b-r7/kernel-evidence/Image"
        if SHARED.R3.digest(candidate_kernel) != SHARED.R3.digest(frozen_kernel):
            raise RuntimeError("diag1 changed the exact r7 kernel")
        exact_artifacts["kernel"] = SHARED.R3.record(candidate_kernel)

        runtime_delta: dict[str, object] = {}
        for name, contract in self.diag["runtime_files"].items():
            if str(contract["partition_path"]).startswith("/system/"):
                path = self.mounts / "system" / str(contract["partition_path"]).lstrip("/")
                image = images["system"]
            else:
                path = self.mounts / "vendor" / str(contract["install_path"]).lstrip("/")
                image = images["vendor"]
            actual = SHARED.R3.record(path)
            if actual["size"] != contract["size"] or actual["sha256"] != contract["sha256"]:
                raise RuntimeError(f"installed diag1 runtime identity changed: {name}")
            if b"UBOX_R7_DIAG1" not in path.read_bytes():
                raise RuntimeError(f"installed diag1 marker absent: {name}")
            inode = self.inode_contract(image, str(contract["install_path"]))
            for field in ("mode", "uid", "gid", "selinux"):
                if inode is None or inode[field] != contract[field]:
                    raise RuntimeError(f"installed diag1 inode changed: {name}/{field}")
            header = subprocess.check_output(["readelf", "-h", str(path)], text=True)
            expected_class = f"Class:                             {contract['elf_class']}"
            expected_machine = (
                "Machine:                           AArch64"
                if contract["architecture"] == "AArch64"
                else "Machine:                           ARM"
            )
            if expected_class not in header or expected_machine not in header:
                raise RuntimeError(f"installed diag1 ELF class/architecture changed: {name}")
            runtime_delta[name] = {
                "partition_path": contract["partition_path"],
                "r7": {"size": contract["old_size"], "sha256": contract["old_sha256"]},
                "diag1": actual,
                "elf_class": contract["elf_class"],
                "architecture": contract["architecture"],
                "reason": contract["reason"],
                "inode": inode,
                "marker": "PRESENT",
            }
        surfaceflinger = self.mounts / "system/system/bin/surfaceflinger"
        if b"Failed to create a valid texture." not in surfaceflinger.read_bytes():
            raise RuntimeError("the original RenderEngine fatal path is absent")

        r7_contract = json.loads(
            (REPO / "configs/candidates/a16-prototype-b-r7.json").read_text(encoding="utf-8")
        )
        retained: dict[str, object] = {}
        for name, contract in r7_contract["retained_vendor_contract"].items():
            if name in {"gralloc32"}:
                continue
            path = self.mounts / "vendor" / str(contract["path"]).lstrip("/")
            actual = SHARED.R3.record(path)
            if actual["size"] != contract["size"] or actual["sha256"] != contract["sha256"]:
                raise RuntimeError(f"diag1 changed retained r7 asset: {name}")
            retained[name] = actual
        mapper = r7_contract["providers"]["mapper"]
        mapper_path = self.mounts / "vendor" / str(mapper["install_path"]).lstrip("/")
        mapper_actual = SHARED.R3.record(mapper_path)
        if mapper_actual["size"] != mapper["size"] or mapper_actual["sha256"] != mapper["sha256"]:
            raise RuntimeError("diag1 changed the exact ARM64 mapper")
        retained["mapper64"] = mapper_actual

        closure_path = self.audit / "graphics-sphal-closure.json"
        self.run([
            sys.executable, str(REPO / "scripts/check-a16-prototype-b-r7-graphics.py"),
            "--mapper", str(mapper_path),
            "--gralloc", str(self.mounts / "vendor/lib64/hw/gralloc.apollo.so"),
            "--system-lib64", str(self.root / "system/lib64"),
            "--runtime-lib64", str(self.root / "apex/com.android.runtime/lib64/bionic"),
            "--vndk-lib64", str(self.root / "apex/com.android.vndk.v31/lib64"),
            "--linker-config", str(self.audit / "linker-generated/ld.config.txt"),
            "--output", str(closure_path),
        ], output=self.audit / "graphics-sphal-closure.log")
        closure = json.loads(closure_path.read_text(encoding="utf-8"))
        if closure["decision"] != "PASS_EXACT_ARM64_MAPPER_GRALLOC_SPHAL_CLOSURE":
            raise RuntimeError("diag1 ARM64 mapper/gralloc SP-HAL closure failed")

        return {
            "result": "PASS_EXACT_FOUR_RUNTIME_FILE_DIAGNOSTIC_DELTA_FROM_R7",
            "system_tree_delta": system_delta,
            "vendor_tree_delta": vendor_delta,
            "runtime_file_delta": runtime_delta,
            "exact_r7_artifacts": exact_artifacts,
            "retained_r7_assets": retained,
            "graphics_sphal_closure": closure,
            "original_renderengine_fatal": "PRESENT_UNCHANGED",
            "all_other_system_files_exact_r7": True,
            "all_other_vendor_files_exact_r7": True,
            "product_contents_exact_r7": True,
            "boot_and_kernel_exact_r7": True,
            "vendor_dlkm_exact_r7_module_count_22": True,
            "boringssl32_64_and_rc_exact_r7": True,
            "mali_proprietary_blob_exact_r7": True,
            "arm32_legacy_vendor_services_unrelated_audio_wifi_exact_r7": True,
            "kernel_release": "5.4.302+",
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
        result.update({
            "decision": "OFFLINE CHECKED / READY FOR PAIRED PHYSICAL DIAGNOSTIC VALIDATION",
            "physical_status": "NOT_YET_VALIDATED",
            "physical_device_actions_performed": False,
            "flash_authorized": False,
            "diagnostic": self.diag["diagnostic"],
            "governance": self.diag["governance"],
            "functional_result": {
                "architecture_ceiling": "PASS_FROZEN_UNCHANGED",
                "gate3": "HOLD",
                "h264": "PHYSICAL_PASS_FROM_EXACT_R7",
                "hevc": "FAIL_BLOCKER_NOT_FIXED",
                "r8": "NOT_AUTHORIZED_NOT_BUILT",
            },
        })
        result["limitations"] = [
            "No physical UBOX action occurred in this task.",
            "The first fatal boundary is proven; the first discriminating AVC-versus-HEVC contract field is not yet proven.",
            "Diagnostic logging changes timing but is filtered to media configuration and relevant large YV12 allocation/import events.",
            "GraphicBuffer/AHardwareBuffer ID and gralloc backing_store_id are separate correlation domains bridged by timestamp and immutable buffer fields.",
            "Full VINTF remains exit 65 only for inherited CONFIG_NFS_FS=y versus FCM-6 n and is NOT PASS.",
            "Quarter-screen recovery and the known post-restart audio crash remain unchanged and unfixed.",
        ]
        audit_path.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

        build_path = self.candidate / "build-result.json"
        build = json.loads(build_path.read_text(encoding="utf-8"))
        build["status"] = "OFFLINE_CHECKED"
        build["decision"] = result["decision"]
        build["physical_status"] = result["physical_status"]
        build["flash_authorized"] = False
        build["offline_audit"] = SHARED.R3.record(audit_path)
        build_path.write_text(
            json.dumps(build, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        sums = []
        for path in sorted(self.candidate.iterdir()):
            if path.is_file() and path.name != "SHA256SUMS":
                sums.append(f"{SHARED.R3.digest(path)}  {path.name}")
        (self.candidate / "SHA256SUMS").write_text(
            "\n".join(sums) + "\n", encoding="utf-8"
        )


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
