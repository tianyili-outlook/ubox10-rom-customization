#!/usr/bin/env python3
"""Audit diag3 as an exact four-file observation-only delta from diag2."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile


REPO = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE = REPO / "out/candidates/a16-prototype-b-r7-diag3-private-buffer-metadata"
DEFAULT_CONFIG = REPO / "configs/candidates/a16-prototype-b-r7-diag3-private-buffer-metadata.json"
DEFAULT_AOSP = Path("/work/src/ubox10-a16-ceiling")
DIAG1_PATH = REPO / "scripts/audit-a16-prototype-b-r7-diag1.py"
SPEC = importlib.util.spec_from_file_location("r7_diag1_auditor_for_diag3", DIAG1_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import diag1 auditor: {DIAG1_PATH}")
DIAG1 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = DIAG1
SPEC.loader.exec_module(DIAG1)
SHARED = DIAG1.SHARED


def elf_contract(path: Path) -> dict[str, object]:
    header = subprocess.check_output(["readelf", "-h", str(path)], text=True)
    dynamic = subprocess.check_output(["readelf", "-W", "-d", str(path)], text=True)
    exports = subprocess.check_output(
        ["nm", "-D", "--defined-only", "--format=posix", str(path)], text=True
    )
    parsed = [line.split() for line in exports.splitlines() if line.strip()]
    soname = re.search(r"\(SONAME\).*\[([^]]+)\]", dynamic)
    return {
        "elf_class": "ELF64" if "Class:                             ELF64" in header else "ELF32",
        "architecture": "AArch64" if "Machine:                           AArch64" in header else "ARM",
        "soname": soname.group(1) if soname else None,
        "dt_needed": re.findall(r"\(NEEDED\).*\[([^]]+)\]", dynamic),
        "strong_exports": sorted(
            fields[0] for fields in parsed
            if len(fields) > 1 and fields[1].upper() not in {"W", "V"}
        ),
    }


class Auditor(DIAG1.Auditor):
    def __init__(self, args: argparse.Namespace) -> None:
        self.diag3 = json.loads(args.config.read_text(encoding="utf-8"))
        merged = json.loads(
            (REPO / "configs/candidates/a16-prototype-b-r7-diag1.json").read_text(
                encoding="utf-8"
            )
        )
        for key in ("id", "label", "status", "base_candidate", "base_artifacts",
                    "source_contract", "instrumentation", "outer_delta", "governance"):
            merged[key] = self.diag3[key]
        merged["milestone"] = "Diag3 private buffer metadata observation diagnostic"
        merged["diagnostic"] = {
            "classification": "INSTRUMENTATION_ONLY_NOT_R8_NOT_RELEASE",
            "prefix": "UBOX_R7_DIAG3",
            "semantic_change": "NONE_OBSERVATION_ONLY",
            "base": "EXACT_DIAG2",
        }
        for name, delta in self.diag3["runtime_files"].items():
            runtime = merged["runtime_files"][name]
            runtime.update(delta)

        temporary = tempfile.NamedTemporaryFile(
            mode="w", prefix="ubox-r7-diag3-audit-", suffix=".json", delete=False
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

    def run_arm32_closure(self) -> dict[str, object]:
        output = self.audit / "graphics-sphal-closure-arm32.json"
        self.run([
            sys.executable,
            str(REPO / "scripts/check-a16-prototype-b-r7-graphics.py"),
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
        if (
            result["decision"] != "PASS_EXACT_ARM32_MAPPER_GRALLOC_SPHAL_CLOSURE"
            or result["gralloc"]["unmatched_count"] != 0
            or result["gralloc"]["libcpp_verbose_abort_import"]
        ):
            raise RuntimeError("diag3 ARM32 graphics closure failed")
        return result

    def audit_preservation(self, images: dict[str, Path]) -> dict[str, object]:
        result = super().audit_preservation(images)
        expected_system = {
            "added": [], "removed": [],
            "changed": ["system/bin/surfaceflinger", "system/lib64/libstagefright.so"],
        }
        expected_vendor = {
            "added": [], "removed": [],
            "changed": ["lib/hw/gralloc.apollo.so", "lib64/hw/gralloc.apollo.so"],
        }
        if result["system_tree_delta"] != expected_system:
            raise RuntimeError("diag3 system delta is not exact from diag2")
        if result["vendor_tree_delta"] != expected_vendor:
            raise RuntimeError("diag3 vendor delta is not exact from diag2")

        installed: dict[str, Path] = {
            "surfaceflinger": self.mounts / "system/system/bin/surfaceflinger",
            "libstagefright64": self.mounts / "system/system/lib64/libstagefright.so",
            "gralloc32": self.mounts / "vendor/lib/hw/gralloc.apollo.so",
            "gralloc64": self.mounts / "vendor/lib64/hw/gralloc.apollo.so",
        }
        runtime_delta: dict[str, object] = {}
        combined = b""
        for name, path in installed.items():
            contract = self.diag3["runtime_files"][name]
            old = self.candidate / f"diag2-{name}"
            expected_old = {"size": contract["old_size"], "sha256": contract["old_sha256"]}
            old_record = SHARED.R3.record(old)
            new_record = SHARED.R3.record(path)
            if any(old_record[field] != expected_old[field] for field in ("size", "sha256")):
                raise RuntimeError(f"saved diag2 identity changed: {name}")
            if any(new_record[field] != contract[field] for field in ("size", "sha256")):
                raise RuntimeError(f"installed diag3 identity changed: {name}")
            before = elf_contract(old)
            after = elf_contract(path)
            for field in ("elf_class", "architecture", "soname", "dt_needed", "strong_exports"):
                if before[field] != after[field]:
                    raise RuntimeError(f"diag3 changed {name} ELF {field}")
            if b"UBOX_R7_DIAG1" not in path.read_bytes() or b"UBOX_R7_DIAG3" not in path.read_bytes():
                raise RuntimeError(f"diag3 markers absent: {name}")
            combined += path.read_bytes()
            runtime_delta[name] = {
                "partition_path": contract["partition_path"],
                "diag2": old_record,
                "diag3": new_record,
                "elf_class": contract["elf_class"],
                "architecture": contract["architecture"],
                "reason": contract["reason"],
                "dt_needed_preserved": True,
                "soname_preserved": True,
                "strong_exports_preserved": True,
            }

        old_stages = (
            "CODEC_SELECT", "CODEC_OUTPUT", "NATIVE_WINDOW", "GRALLOC_ALLOC",
            "GRALLOC_HANDLE", "AHB_DESC", "RENDERENGINE_MAP", "NATIVE_CLIENT_BUFFER",
            "EGL_CREATE_IMAGE", "GL_GEN_TEXTURE", "GL_BIND_TEXTURE",
            "GL_EGL_IMAGE_TARGET", "BACKEND_TEXTURE",
        )
        new_stages = tuple(self.diag3["instrumentation"]["stages"])
        for stage in old_stages + new_stages:
            if stage.encode() not in combined:
                raise RuntimeError(f"diag3 runtime marker stage absent: {stage}")
        sf = installed["surfaceflinger"].read_bytes()
        if b"Failed to create a valid texture." not in sf:
            raise RuntimeError("diag3 removed the RenderEngine fatal")

        arm32 = self.run_arm32_closure()
        result.update({
            "result": "PASS_EXACT_FOUR_RUNTIME_FILE_OBSERVATION_ONLY_DELTA_FROM_DIAG2",
            "base_candidate": "a16-prototype-b-r7-diag2-hevc-crop",
            "runtime_file_delta_from_diag2": runtime_delta,
            "arm32_graphics_sphal_closure": arm32,
            "all_diag1_stages_retained": list(old_stages),
            "all_diag3_stages_present": list(new_stages),
            "original_renderengine_fatal": "PRESENT_UNCHANGED",
            "all_other_system_files_exact_diag2": True,
            "all_other_vendor_files_exact_diag2": True,
            "semantic_change": "NONE_OBSERVATION_ONLY",
        })
        return result

    def finish_b1(self, images: dict[str, Path], apex: dict[str, object],
                  compatibility: dict[str, object], elf: dict[str, object],
                  avb_lp_outer: dict[str, object], preservation: dict[str, object],
                  root_mountpoint: dict[str, object]) -> None:
        DIAG1.Auditor.finish_b1(
            self, images, apex, compatibility, elf, avb_lp_outer, preservation,
            root_mountpoint,
        )
        audit_path = self.audit / "offline-audit.json"
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        audit.update({
            "decision": "OFFLINE CHECKED / READY FOR PHYSICAL BOOT GATE",
            "physical_status": "NOT_YET_VALIDATED",
            "physical_device_actions_performed": False,
            "flash_authorized": False,
            "candidate_classification": "DIAGNOSTIC_ONLY_NOT_R8_NOT_RELEASE",
            "evidence_status": "DIAG2_PHYSICAL_INPUT_READ_ONLY_AUDITED_AND_HASH_VERIFIED",
            "governance": self.diag3["governance"],
            "functional_result": {
                "architecture_ceiling": "PASS_FROZEN_UNCHANGED",
                "gate3": "HOLD",
                "h264": "PHYSICAL_PASS_CONTROL",
                "hevc": "BLOCKED_NOT_FIXED",
                "r8": "NOT_AUTHORIZED_NOT_BUILT",
            },
        })
        audit["limitations"] = [
            "Diag3 has not been flashed or physically tested.",
            "The first hidden AVC-versus-HEVC private buffer-state difference is not yet proven.",
            "The closed ARM32 decoder and proprietary Mali importer remain observational boundaries.",
            "Full VINTF remains exit 65 for inherited CONFIG_NFS_FS=y versus FCM-6 n and is NOT PASS.",
            "Quarter-screen recovery, audio, SELinux, and unrelated platform debt remain unchanged.",
        ]
        audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        build_path = self.candidate / "build-result.json"
        build = json.loads(build_path.read_text(encoding="utf-8"))
        build.update({
            "status": "OFFLINE_CHECKED",
            "decision": audit["decision"],
            "physical_status": audit["physical_status"],
            "flash_authorized": False,
            "offline_audit": SHARED.R3.record(audit_path),
        })
        build_path.write_text(json.dumps(build, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        sums = [f"{SHARED.R3.digest(path)}  {path.name}"
                for path in sorted(self.candidate.iterdir())
                if path.is_file() and path.name != "SHA256SUMS"]
        (self.candidate / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")

    def execute(self) -> None:
        try:
            images = self.setup()
            try:
                self.mount_images(images)
                self.mount_r4_vendor()
                apex = self.audit_apex()
                compatibility = self.audit_vintf_linker_selinux()
                elf = self.audit_elf(images)
                avb_lp_outer = self.audit_avb_lp_outer(images)
                preservation = self.audit_preservation(images)
                root_mountpoint = self.audit_root_mountpoint_delta(images)
            finally:
                for point in reversed(self.mounted):
                    self.run(["sudo", "umount", str(point)], allowed={0, 32})
            self.finish_b1(
                images, apex, compatibility, elf, avb_lp_outer, preservation,
                root_mountpoint,
            )
            print("OFFLINE CHECKED / READY FOR PHYSICAL BOOT GATE", flush=True)
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
