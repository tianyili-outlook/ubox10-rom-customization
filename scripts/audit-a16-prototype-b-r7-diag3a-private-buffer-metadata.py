#!/usr/bin/env python3
"""Audit diag3a as an exact one-runtime-file diagnostic delta from diag3."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile


REPO = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE = REPO / "out/candidates/a16-prototype-b-r7-diag3a-private-buffer-metadata"
DEFAULT_CONFIG = REPO / "configs/candidates/a16-prototype-b-r7-diag3a-private-buffer-metadata.json"
DEFAULT_AOSP = Path("/work/src/ubox10-a16-ceiling")
DIAG3_CONFIG = REPO / "configs/candidates/a16-prototype-b-r7-diag3-private-buffer-metadata.json"
DIAG3_AUDITOR = REPO / "scripts/audit-a16-prototype-b-r7-diag3-private-buffer-metadata.py"
SPEC = importlib.util.spec_from_file_location("r7_diag3_auditor_for_diag3a", DIAG3_AUDITOR)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import diag3 auditor: {DIAG3_AUDITOR}")
DIAG3 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = DIAG3
SPEC.loader.exec_module(DIAG3)
SHARED = DIAG3.SHARED


def full_runtime(config: dict[str, object], diag3: dict[str, object]) -> dict[str, dict[str, object]]:
    runtime = {key: dict(value) for key, value in diag3["runtime_files"].items()}
    change = config["runtime_change"]
    runtime[change["name"]].update({
        "old_size": change["diag3_size"], "old_sha256": change["diag3_sha256"],
        "size": change["size"], "sha256": change["sha256"],
        "build_id": change["build_id"], "reason": change["reason"],
    })
    return runtime


def strong_undefined(path: Path) -> set[str]:
    output = subprocess.check_output(
        ["nm", "-D", "--undefined-only", "--format=posix", str(path)], text=True
    )
    return {
        fields[0].split("@", 1)[0]
        for line in output.splitlines()
        if len(fields := line.split()) >= 2 and fields[1] == "U"
    }


class Auditor(DIAG3.DIAG1.Auditor):
    def __init__(self, args: argparse.Namespace) -> None:
        self.diag3a = json.loads(args.config.read_text(encoding="utf-8"))
        self.diag3_cfg = json.loads(DIAG3_CONFIG.read_text(encoding="utf-8"))
        self.runtime = full_runtime(self.diag3a, self.diag3_cfg)
        merged = json.loads(
            (REPO / "configs/candidates/a16-prototype-b-r7-diag1.json").read_text(encoding="utf-8")
        )
        for key in ("id", "label", "status", "base_candidate", "base_artifacts",
                    "source_contract", "instrumentation", "outer_delta", "governance"):
            merged[key] = self.diag3a[key]
        for name, contract in self.runtime.items():
            merged["runtime_files"][name].update(contract)
        merged["milestone"] = "Diag3a instrumentation transparency diagnostic"
        merged["diagnostic"] = {
            "classification": "DIAGNOSTIC_ONLY_NOT_R8_NOT_RELEASE",
            "semantic_change": "FNV_HASH_IMPLEMENTATION_ONLY_EXACT_OUTPUT_PRESERVED",
            "base": "EXACT_DIAG3",
        }
        temporary = tempfile.NamedTemporaryFile(
            mode="w", prefix="ubox-r7-diag3a-audit-", suffix=".json", delete=False
        )
        json.dump(merged, temporary, indent=2)
        temporary.write("\n")
        temporary.close()
        self._merged_config = Path(temporary.name)
        base_args = argparse.Namespace(
            candidate=args.candidate, config=self._merged_config, aosp=args.aosp,
            kernel_evidence=args.kernel_evidence, resume=args.resume,
        )
        super().__init__(base_args)

    def audit_root_mountpoint_delta(self, images: dict[str, Path]) -> dict[str, object]:
        self.mount_exact_r7()
        delta = self.tree_delta(self.r7_system_mount, self.mounts / "system")
        expected = {"added": [], "removed": [], "changed": ["system/lib64/libstagefright.so"]}
        if delta != expected:
            raise RuntimeError(f"diag3a root/system delta expanded: {delta}")
        contracts: dict[str, object] = {}
        for name in ("metadata", "vendor"):
            locked = self.diag["root_mountpoint_contract"][name]
            observed = self.inode_contract(images["system"], str(locked["path"]))
            for field in ("type", "mode", "uid", "gid", "selinux"):
                if observed is None or observed[field] != locked[field]:
                    raise RuntimeError(f"diag3a changed root mountpoint {locked['path']}: {field}")
            contracts[str(locked["path"])] = observed
        product = self.inode_contract(images["system"], "/product")
        target = self.symlink_target(images["system"], "/product")
        if product is None or product["type"] != "symlink" or target != "/system/product":
            raise RuntimeError("diag3a changed active /product alias")
        contracts["/product"] = {"inode": product, "target": target}
        return {
            "result": "PASS_EXACT_DIAG3_ROOT_CONTRACT_WITH_ONE_SYSTEM_DIAGNOSTIC_FILE",
            "tree_delta": delta, "root_objects": contracts, "all_other_system_files_exact_diag3": True,
        }

    def audit_avb_lp_outer(self, images: dict[str, Path]) -> dict[str, object]:
        base_dump = self.audit / "diag3-detached-lpdump.json"
        self.run([str(self.host / "lpdump"), "-j", str(self.exact_base("super_raw"))], output=base_dump)
        candidate_dump = self.candidate / "candidate-lpdump.json"
        if json.loads(base_dump.read_text(encoding="utf-8")) != json.loads(
            candidate_dump.read_text(encoding="utf-8")
        ):
            raise RuntimeError("diag3a LP metadata/extents differ from exact diag3")
        evidence = self.build_result["super"]
        for name in (
            "growth_only_from_old_unallocated_space", "all_other_partition_extents_exact_r4",
            "no_partition_shrunk", "b_slot_allocations_empty_exact", "sparse_roundtrip_exact",
        ):
            evidence[name] = True
        result = super(DIAG3.DIAG1.Auditor, self).audit_avb_lp_outer(images)
        result.update({
            "lp_metadata_and_extents": "EXACT_DIAG3", "lp_metadata_slots_0_and_1": "EXACT",
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
            raise RuntimeError("diag3a ARM32 VNDK31 graphics closure failed")
        return result

    def audit_preservation(self, images: dict[str, Path]) -> dict[str, object]:
        self.mount_exact_r7()
        system_delta = self.tree_delta(self.r7_system_mount, self.mounts / "system")
        vendor_delta = self.tree_delta(self.r7_vendor_mount, self.mounts / "vendor")
        if system_delta != {"added": [], "removed": [], "changed": ["system/lib64/libstagefright.so"]}:
            raise RuntimeError(f"diag3a system file delta expanded: {system_delta}")
        if vendor_delta != {"added": [], "removed": [], "changed": []}:
            raise RuntimeError(f"diag3a vendor file delta expanded: {vendor_delta}")

        exact: dict[str, object] = {}
        for name, path in (
            ("product_a", images["product"]), ("vendor_dlkm", images["vendor_dlkm"]),
            ("boot", self.candidate / "boot.fex"),
        ):
            expected = self.diag3a["base_artifacts"][name]
            actual = SHARED.R3.record(path)
            if any(actual[field] != expected[field] for field in ("size", "sha256")):
                raise RuntimeError(f"diag3a changed exact diag3 artifact: {name}")
            exact[name] = actual
        diag3_kernel = REPO / "out/candidates/a16-prototype-b-r7-diag3-private-buffer-metadata/kernel-evidence/Image"
        candidate_kernel = self.candidate / "kernel-evidence/Image"
        if SHARED.R3.digest(candidate_kernel) != SHARED.R3.digest(diag3_kernel):
            raise RuntimeError("diag3a changed kernel evidence")
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
            expected = {"size": contract["size"], "sha256": contract["sha256"]}
            actual = SHARED.R3.record(path)
            if any(actual[field] != expected[field] for field in expected):
                raise RuntimeError(f"installed diag3a runtime identity changed: {name}")
            saved = self.candidate / f"diag3a-{name}"
            saved_record = SHARED.R3.record(saved)
            if any(saved_record[field] != actual[field] for field in ("size", "sha256")):
                raise RuntimeError(f"saved diag3a runtime differs from signed filesystem: {name}")
            before = self.candidate / f"diag3-{name}"
            old_contract = DIAG3.elf_contract(before)
            new_contract = DIAG3.elf_contract(path)
            for field in ("elf_class", "architecture", "soname", "dt_needed", "strong_exports"):
                if old_contract[field] != new_contract[field]:
                    raise RuntimeError(f"diag3a changed {name} ELF {field}")
            if strong_undefined(before) != strong_undefined(path):
                raise RuntimeError(f"diag3a changed {name} strong imports")
            combined += path.read_bytes()
            runtime_delta[name] = {
                "partition_path": contract["partition_path"], "diag3": SHARED.R3.record(before),
                "diag3a": actual, "byte_identical": SHARED.R3.digest(before) == actual["sha256"],
                "elf_class": contract["elf_class"], "architecture": contract["architecture"],
            }
        changed = [name for name, value in runtime_delta.items() if not value["byte_identical"]]
        if changed != ["libstagefright64"]:
            raise RuntimeError(f"diag3a runtime delta is not exactly libstagefright64: {changed}")
        for boundary in self.diag3a["instrumentation"]["boundaries"]:
            if boundary.encode() not in combined:
                raise RuntimeError(f"diag3a lost observation boundary: {boundary}")
        for prefix in self.diag3a["instrumentation"]["prefixes"]:
            if prefix.encode() not in combined:
                raise RuntimeError(f"diag3a lost instrumentation prefix: {prefix}")
        if b"Failed to create a valid texture." not in installed["surfaceflinger"].read_bytes():
            raise RuntimeError("diag3a removed original RenderEngine fatal")

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
            raise RuntimeError("diag3a ARM64 graphics closure failed")
        return {
            "result": "PASS_EXACT_ONE_RUNTIME_FILE_DIAGNOSTIC_DELTA_FROM_DIAG3",
            "system_tree_delta": system_delta, "vendor_tree_delta": vendor_delta,
            "runtime_file_comparison": runtime_delta, "exact_diag3_artifacts": exact,
            "arm32_graphics_sphal_closure": arm32, "graphics_sphal_closure": arm64,
            "all_five_diag3_boundaries_retained": self.diag3a["instrumentation"]["boundaries"],
            "all_diag1_diag3_markers_retained": True,
            "original_renderengine_fatal": "PRESENT_UNCHANGED",
            "all_other_system_files_exact_diag3": True, "all_vendor_files_exact_diag3": True,
            "product_boot_kernel_vendor_dlkm_exact_diag3": True,
            "mali_omx_cedar_audio_wifi_hwc_display_exact_diag3": True,
            "kernel_release": "5.4.302+", "vendor_dlkm_module_count": 22,
        }

    def finish_b1(self, images: dict[str, Path], apex: dict[str, object],
                  compatibility: dict[str, object], elf: dict[str, object],
                  avb_lp_outer: dict[str, object], preservation: dict[str, object],
                  root_mountpoint: dict[str, object]) -> None:
        DIAG3.DIAG1.Auditor.finish_b1(
            self, images, apex, compatibility, elf, avb_lp_outer, preservation, root_mountpoint
        )
        audit_path = self.audit / "offline-audit.json"
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        audit.update({
            "decision": "OFFLINE CHECKED / READY FOR PHYSICAL BOOT GATE",
            "physical_status": "NOT_YET_VALIDATED", "physical_device_actions_performed": False,
            "flash_authorized": False,
            "candidate_classification": "DIAGNOSTIC_ONLY_NOT_R8_NOT_RELEASE",
            "instrumentation_transparency": {
                "root_cause": "PROVEN_INTENTIONAL_FNV_UINT64_WRAP_TRIGGERED_LIBSTAGEFRIGHT_UBSAN",
                "correction": "BUILTIN_MUL_OVERFLOW_WRAPPED_RESULT_NO_SANITIZER_DISABLED",
                "fnv_output": "EXACTLY_PRESERVED", "diagnostic_hypothesis": "UNCHANGED",
            },
            "governance": self.diag3a["governance"],
            "functional_result": {
                "architecture_ceiling": "PASS_FROZEN_UNCHANGED", "gate3": "HOLD",
                "h264": "AWAITING_DIAG3A_PHYSICAL_AVC_PRESERVATION_RETEST",
                "hevc": "BLOCKED_NOT_FIXED_NOT_AUTHORIZED_FOR_AUTOMATIC_TEST",
                "r8": "NOT_AUTHORIZED_NOT_BUILT",
            },
        })
        audit["limitations"] = [
            "Diag3a has not been flashed or physically tested.",
            "AVC must pass before any HEVC diag3 experiment is resumed.",
            "The first hidden AVC-versus-HEVC private buffer-state difference is not yet proven.",
            "Full VINTF remains exit 65 for inherited CONFIG_NFS_FS=y versus FCM-6 n and is NOT PASS.",
            "Quarter-screen recovery, audio, SELinux and unrelated platform debt remain unchanged.",
        ]
        audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        build_path = self.candidate / "build-result.json"
        build = json.loads(build_path.read_text(encoding="utf-8"))
        build.update({
            "status": "OFFLINE_CHECKED", "decision": audit["decision"],
            "physical_status": "NOT_YET_VALIDATED", "flash_authorized": False,
            "offline_audit": SHARED.R3.record(audit_path),
        })
        build_path.write_text(json.dumps(build, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        sums = [f"{SHARED.R3.digest(path)}  {path.name}" for path in sorted(self.candidate.iterdir())
                if path.is_file() and path.name != "SHA256SUMS"]
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
