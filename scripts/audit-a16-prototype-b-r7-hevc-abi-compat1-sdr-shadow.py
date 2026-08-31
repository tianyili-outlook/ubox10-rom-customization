#!/usr/bin/env python3
"""Audit compat1 as an exact one-runtime-file repair delta from diag3a."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile


REPO = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE = REPO / "out/candidates/a16-prototype-b-r7-hevc-abi-compat1-sdr-shadow"
DEFAULT_CONFIG = REPO / "configs/candidates/a16-prototype-b-r7-hevc-abi-compat1-sdr-shadow.json"
DEFAULT_AOSP = Path("/work/src/ubox10-a16-ceiling")
DIAG3A_CONFIG = REPO / "configs/candidates/a16-prototype-b-r7-diag3a-private-buffer-metadata.json"
DIAG3A_AUDITOR = REPO / "scripts/audit-a16-prototype-b-r7-diag3a-private-buffer-metadata.py"
SPEC = importlib.util.spec_from_file_location("r7_diag3a_auditor_for_compat1", DIAG3A_AUDITOR)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import diag3a auditor: {DIAG3A_AUDITOR}")
DIAG3A = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = DIAG3A
SPEC.loader.exec_module(DIAG3A)
SHARED = DIAG3A.SHARED
DIAG1 = DIAG3A.DIAG3.DIAG1


def strong_undefined(path: Path) -> set[str]:
    output = subprocess.check_output(
        ["nm", "-D", "--undefined-only", "--format=posix", str(path)], text=True
    )
    return {
        fields[0].split("@", 1)[0]
        for line in output.splitlines()
        if len(fields := line.split()) >= 2 and fields[1] == "U"
    }


class Auditor(DIAG1.Auditor):
    def __init__(self, args: argparse.Namespace) -> None:
        self.compat1 = json.loads(args.config.read_text(encoding="utf-8"))
        self.diag3a_cfg = json.loads(DIAG3A_CONFIG.read_text(encoding="utf-8"))
        diag3_cfg = json.loads(DIAG3A.DIAG3_CONFIG.read_text(encoding="utf-8"))
        self.runtime = DIAG3A.full_runtime(self.diag3a_cfg, diag3_cfg)
        change = self.compat1["runtime_change"]
        self.runtime["surfaceflinger"].update({
            "old_size": change["diag3a_size"],
            "old_sha256": change["diag3a_sha256"],
            "size": change["size"],
            "sha256": change["sha256"],
            "build_id": change["build_id"],
            "reason": change["reason"],
        })
        merged = json.loads(
            (REPO / "configs/candidates/a16-prototype-b-r7-diag1.json").read_text(encoding="utf-8")
        )
        for key in (
            "id", "label", "status", "base_candidate", "base_artifacts",
            "source_contract", "instrumentation", "outer_delta", "governance",
        ):
            merged[key] = self.compat1[key]
        for name, contract in self.runtime.items():
            merged["runtime_files"][name].update(contract)
        merged["milestone"] = "First SDR YV12 Mali metadata ABI compatibility repair experiment"
        merged["diagnostic"] = {
            "classification": "EXPERIMENTAL_REPAIR_NOT_R8_NOT_RELEASE",
            "semantic_change": "MALI_CONSUMER_ONLY_METADATA_SHADOW_FOR_EXACT_SDR_YV12_GATE",
            "base": "EXACT_DIAG3A",
        }
        temporary = tempfile.NamedTemporaryFile(
            mode="w", prefix="ubox-r7-compat1-audit-", suffix=".json", delete=False
        )
        json.dump(merged, temporary, indent=2)
        temporary.write("\n")
        temporary.close()
        self._merged_config = Path(temporary.name)
        base_args = argparse.Namespace(
            candidate=args.candidate,
            config=self._merged_config,
            aosp=args.aosp,
            kernel_evidence=args.kernel_evidence,
            resume=args.resume,
        )
        super().__init__(base_args)

    def audit_root_mountpoint_delta(self, images: dict[str, Path]) -> dict[str, object]:
        self.mount_exact_r7()
        delta = self.tree_delta(self.r7_system_mount, self.mounts / "system")
        expected = {"added": [], "removed": [], "changed": ["system/bin/surfaceflinger"]}
        if delta != expected:
            raise RuntimeError(f"compat1 root/system delta expanded: {delta}")
        contracts: dict[str, object] = {}
        for name in ("metadata", "vendor"):
            locked = self.diag["root_mountpoint_contract"][name]
            observed = self.inode_contract(images["system"], str(locked["path"]))
            for field in ("type", "mode", "uid", "gid", "selinux"):
                if observed is None or observed[field] != locked[field]:
                    raise RuntimeError(f"compat1 changed root mountpoint {locked['path']}: {field}")
            contracts[str(locked["path"])] = observed
        product = self.inode_contract(images["system"], "/product")
        target = self.symlink_target(images["system"], "/product")
        if product is None or product["type"] != "symlink" or target != "/system/product":
            raise RuntimeError("compat1 changed active /product alias")
        contracts["/product"] = {"inode": product, "target": target}
        return {
            "result": "PASS_EXACT_DIAG3A_ROOT_CONTRACT_WITH_ONE_SYSTEM_REPAIR_FILE",
            "tree_delta": delta,
            "root_objects": contracts,
            "all_other_system_files_exact_diag3a": True,
        }

    def audit_avb_lp_outer(self, images: dict[str, Path]) -> dict[str, object]:
        base_dump = self.audit / "diag3a-detached-lpdump.json"
        self.run([str(self.host / "lpdump"), "-j", str(self.exact_base("super_raw"))], output=base_dump)
        candidate_dump = self.candidate / "candidate-lpdump.json"
        if json.loads(base_dump.read_text(encoding="utf-8")) != json.loads(
            candidate_dump.read_text(encoding="utf-8")
        ):
            raise RuntimeError("compat1 LP metadata/extents differ from exact diag3a")
        evidence = self.build_result["super"]
        for name in (
            "growth_only_from_old_unallocated_space", "all_other_partition_extents_exact_r4",
            "no_partition_shrunk", "b_slot_allocations_empty_exact", "sparse_roundtrip_exact",
        ):
            evidence[name] = True
        result = super(DIAG1.Auditor, self).audit_avb_lp_outer(images)
        result.update({
            "lp_metadata_and_extents": "EXACT_DIAG3A",
            "lp_metadata_slots_0_and_1": "EXACT",
            "logical_system_written_to_frozen_extent": True,
        })
        return result

    def run_arm32_closure(self) -> dict[str, object]:
        output = self.audit / "graphics-sphal-closure-arm32.json"
        self.run([
            sys.executable, str(REPO / "scripts/check-a16-prototype-b-r7-graphics.py"),
            "--architecture", "arm32",
            "--mapper", str(self.mounts / "vendor/lib/hw/android.hardware.graphics.mapper@2.0-impl-2.1.so"),
            "--gralloc", str(self.mounts / "vendor/lib/hw/gralloc.apollo.so"),
            "--system-lib", str(self.root / "system/lib"),
            "--runtime-lib", str(self.root / "apex/com.android.runtime/lib/bionic"),
            "--vndk-lib", str(self.root / "apex/com.android.vndk.v31/lib"),
            "--linker-config", str(self.audit / "linker-generated/ld.config.txt"),
            "--output", str(output),
        ], output=self.audit / "graphics-sphal-closure-arm32.log")
        result = json.loads(output.read_text(encoding="utf-8"))
        if result["gralloc"]["unmatched_count"] != 0 or result["gralloc"]["libcpp_verbose_abort_import"]:
            raise RuntimeError("compat1 ARM32 VNDK31 graphics closure failed")
        return result

    def audit_preservation(self, images: dict[str, Path]) -> dict[str, object]:
        self.mount_exact_r7()
        system_delta = self.tree_delta(self.r7_system_mount, self.mounts / "system")
        vendor_delta = self.tree_delta(self.r7_vendor_mount, self.mounts / "vendor")
        if system_delta != {"added": [], "removed": [], "changed": ["system/bin/surfaceflinger"]}:
            raise RuntimeError(f"compat1 system file delta expanded: {system_delta}")
        if vendor_delta != {"added": [], "removed": [], "changed": []}:
            raise RuntimeError(f"compat1 vendor file delta expanded: {vendor_delta}")

        exact: dict[str, object] = {}
        for name, path in (
            ("product_a", images["product"]),
            ("vendor_dlkm", images["vendor_dlkm"]),
            ("boot", self.candidate / "boot.fex"),
        ):
            expected = self.compat1["base_artifacts"][name]
            actual = SHARED.R3.record(path)
            if any(actual[field] != expected[field] for field in ("size", "sha256")):
                raise RuntimeError(f"compat1 changed exact diag3a artifact: {name}")
            exact[name] = actual
        base_kernel = (
            REPO / "out/candidates/a16-prototype-b-r7-diag3a-private-buffer-metadata/kernel-evidence/Image"
        )
        candidate_kernel = self.candidate / "kernel-evidence/Image"
        if SHARED.R3.digest(candidate_kernel) != SHARED.R3.digest(base_kernel):
            raise RuntimeError("compat1 changed kernel evidence")
        exact["kernel"] = SHARED.R3.record(candidate_kernel)

        installed = {
            "surfaceflinger": self.mounts / "system/system/bin/surfaceflinger",
            "libstagefright64": self.mounts / "system/system/lib64/libstagefright.so",
            "gralloc32": self.mounts / "vendor/lib/hw/gralloc.apollo.so",
            "gralloc64": self.mounts / "vendor/lib64/hw/gralloc.apollo.so",
        }
        runtime_delta: dict[str, object] = {}
        combined = b""
        for name, path in installed.items():
            contract = self.runtime[name]
            actual = SHARED.R3.record(path)
            if any(actual[field] != contract[field] for field in ("size", "sha256")):
                raise RuntimeError(f"installed compat1 runtime identity changed: {name}")
            saved = self.candidate / f"compat1-{name}"
            saved_record = SHARED.R3.record(saved)
            if any(saved_record[field] != actual[field] for field in ("size", "sha256")):
                raise RuntimeError(f"saved compat1 runtime differs from signed filesystem: {name}")
            before = self.candidate / f"diag3a-{name}"
            old_contract = DIAG3A.DIAG3.elf_contract(before)
            new_contract = DIAG3A.DIAG3.elf_contract(path)
            for field in ("elf_class", "architecture", "soname", "dt_needed", "strong_exports"):
                if old_contract[field] != new_contract[field]:
                    raise RuntimeError(f"compat1 changed {name} ELF {field}")
            old_imports = strong_undefined(before)
            new_imports = strong_undefined(path)
            if name == "surfaceflinger":
                added = new_imports - old_imports
                removed = old_imports - new_imports
                if removed or added != set(self.compat1["runtime_change"]["added_strong_imports"]):
                    raise RuntimeError(f"compat1 unexpected SurfaceFlinger imports: added={added} removed={removed}")
            elif old_imports != new_imports:
                raise RuntimeError(f"compat1 changed {name} strong imports")
            combined += path.read_bytes()
            runtime_delta[name] = {
                "partition_path": contract["partition_path"],
                "diag3a": SHARED.R3.record(before),
                "compat1": actual,
                "byte_identical": SHARED.R3.digest(before) == actual["sha256"],
                "elf_class": contract["elf_class"],
                "architecture": contract["architecture"],
                "dt_needed_preserved": old_contract["dt_needed"] == new_contract["dt_needed"],
                "strong_exports_preserved": old_contract["strong_exports"] == new_contract["strong_exports"],
            }
        changed = [name for name, value in runtime_delta.items() if not value["byte_identical"]]
        if changed != ["surfaceflinger"]:
            raise RuntimeError(f"compat1 runtime delta is not exactly surfaceflinger: {changed}")
        for boundary in self.compat1["instrumentation"]["diag3_boundaries"]:
            if boundary.encode() not in combined:
                raise RuntimeError(f"compat1 lost diag3 observation boundary: {boundary}")
        for prefix in self.compat1["instrumentation"]["prefixes"]:
            if prefix.encode() not in combined:
                raise RuntimeError(f"compat1 lost instrumentation prefix: {prefix}")
        for marker in self.compat1["instrumentation"]["compat1_records"]:
            if marker.encode() not in installed["surfaceflinger"].read_bytes():
                raise RuntimeError(f"compat1 lost compatibility record: {marker}")
        if b"Failed to create a valid texture." not in installed["surfaceflinger"].read_bytes():
            raise RuntimeError("compat1 removed original RenderEngine fatal")

        arm32 = self.run_arm32_closure()
        arm64_path = self.audit / "graphics-sphal-closure.json"
        self.run([
            sys.executable, str(REPO / "scripts/check-a16-prototype-b-r7-graphics.py"),
            "--mapper", str(self.mounts / "vendor/lib64/hw/android.hardware.graphics.mapper@2.0-impl-2.1.so"),
            "--gralloc", str(installed["gralloc64"]),
            "--system-lib64", str(self.root / "system/lib64"),
            "--runtime-lib64", str(self.root / "apex/com.android.runtime/lib64/bionic"),
            "--vndk-lib64", str(self.root / "apex/com.android.vndk.v31/lib64"),
            "--linker-config", str(self.audit / "linker-generated/ld.config.txt"),
            "--output", str(arm64_path),
        ], output=self.audit / "graphics-sphal-closure.log")
        arm64 = json.loads(arm64_path.read_text(encoding="utf-8"))
        if arm64["decision"] != "PASS_EXACT_ARM64_MAPPER_GRALLOC_SPHAL_CLOSURE":
            raise RuntimeError("compat1 ARM64 graphics closure failed")
        return {
            "result": "PASS_EXACT_ONE_RUNTIME_FILE_EXPERIMENTAL_REPAIR_DELTA_FROM_DIAG3A",
            "system_tree_delta": system_delta,
            "vendor_tree_delta": vendor_delta,
            "runtime_file_comparison": runtime_delta,
            "exact_diag3a_artifacts": exact,
            "arm32_graphics_sphal_closure": arm32,
            "graphics_sphal_closure": arm64,
            "all_five_diag3_boundaries_retained": self.compat1["instrumentation"]["diag3_boundaries"],
            "all_diag1_diag3_compat1_markers_retained": True,
            "original_renderengine_fatal": "PRESENT_UNCHANGED",
            "all_other_system_files_exact_diag3a": True,
            "all_vendor_files_exact_diag3a": True,
            "product_boot_kernel_vendor_dlkm_exact_diag3a": True,
            "mali_omx_cedar_audio_wifi_hwc_display_exact_diag3a": True,
            "kernel_release": "5.4.302+",
            "vendor_dlkm_module_count": 22,
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
        DIAG1.Auditor.finish_b1(
            self, images, apex, compatibility, elf, avb_lp_outer, preservation, root_mountpoint
        )
        audit_path = self.audit / "offline-audit.json"
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        audit.update({
            "decision": "OFFLINE CHECKED / READY FOR PHYSICAL BOOT GATE",
            "physical_status": "NOT_YET_VALIDATED",
            "physical_device_actions_performed": False,
            "flash_authorized": False,
            "candidate_classification": "EXPERIMENTAL_REPAIR_NOT_R8_NOT_RELEASE",
            "compatibility_boundary": {
                "scope": self.compat1["compatibility"]["scope"],
                "consumer": "Skia Ganesh GL immediately before Mali EGL import",
                "translation": "copy active 56-byte attr_region into independent legacy metadata shadow",
                "original_sidecar": "READ_ONLY_BYTE_IDENTICAL",
                "unsupported": self.compat1["compatibility"]["unsupported"],
            },
            "governance": self.compat1["governance"],
            "functional_result": {
                "architecture_ceiling": "PASS_FROZEN_UNCHANGED",
                "gate3": "HOLD",
                "h264": "PHYSICAL_PASS_ON_DIAG3A_AWAITING_COMPAT1_REGRESSION_CONTROL",
                "hevc": "BLOCKED_AWAITING_COMPAT1_SDR_YV12_PHYSICAL_EXPERIMENT",
                "r8": "NOT_AUTHORIZED_NOT_BUILT",
            },
        })
        audit["limitations"] = [
            "Compat1 has not been flashed or physically tested.",
            "AVC must pass first before one SDR YV12 HEVC experiment.",
            "Main10, HDR, AFBC, protected playback and 4K are explicitly outside this candidate.",
            "Full VINTF remains exit 65 for inherited CONFIG_NFS_FS=y versus FCM-6 n and is NOT PASS.",
            "Quarter-screen recovery, audio, SELinux and unrelated platform debt remain unchanged.",
        ]
        audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        build_path = self.candidate / "build-result.json"
        build = json.loads(build_path.read_text(encoding="utf-8"))
        build.update({
            "status": "OFFLINE_CHECKED",
            "decision": audit["decision"],
            "physical_status": "NOT_YET_VALIDATED",
            "flash_authorized": False,
            "offline_audit": SHARED.R3.record(audit_path),
        })
        build_path.write_text(json.dumps(build, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        sums = [
            f"{SHARED.R3.digest(path)}  {path.name}"
            for path in sorted(self.candidate.iterdir())
            if path.is_file() and path.name != "SHA256SUMS"
        ]
        (self.candidate / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")

    def execute(self) -> None:
        try:
            super().execute()
        finally:
            self._merged_config.unlink(missing_ok=True)


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
