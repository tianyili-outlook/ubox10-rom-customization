#!/usr/bin/env python3
"""Audit diag2 as an exact one-runtime-file semantic delta from diag1a."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile


REPO = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE = REPO / "out/candidates/a16-prototype-b-r7-diag2-hevc-crop"
DEFAULT_CONFIG = REPO / "configs/candidates/a16-prototype-b-r7-diag2-hevc-crop.json"
DEFAULT_AOSP = Path("/work/src/ubox10-a16-ceiling")
DIAG1A_PATH = REPO / "scripts/audit-a16-prototype-b-r7-diag1a.py"
SPEC = importlib.util.spec_from_file_location("r7_diag1a_auditor_for_diag2_crop", DIAG1A_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import diag1a auditor: {DIAG1A_PATH}")
DIAG1A = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = DIAG1A
SPEC.loader.exec_module(DIAG1A)

DIAG1 = DIAG1A.DIAG1
SHARED = DIAG1A.SHARED


class Auditor(DIAG1A.Auditor):
    def __init__(self, args: argparse.Namespace) -> None:
        self.diag2 = json.loads(args.config.read_text(encoding="utf-8"))
        merged = json.loads(
            (REPO / "configs/candidates/a16-prototype-b-r7-diag1a.json").read_text(
                encoding="utf-8"
            )
        )
        merged["id"] = self.diag2["id"]
        merged["milestone"] = "Diag2 exact HEVC visible-crop single-variable diagnostic"
        merged["status"] = self.diag2["status"]
        merged["label"] = self.diag2["label"]
        merged["base_candidate"] = self.diag2["base_candidate"]
        merged["governance"] = self.diag2["governance"]
        merged["outer_delta"] = self.diag2["outer_delta"]
        runtime = merged["runtime_files"]["libstagefright64"]
        delta = self.diag2["runtime_delta"]
        runtime.update({
            "source_path": delta["source_path"],
            "size": delta["candidate"]["size"],
            "sha256": delta["candidate"]["sha256"],
            "build_id": delta["build_id"],
            "reason": "exact HEVC 1920x1080 visible crop retained across 1920x1088 alignment",
        })
        temporary = tempfile.NamedTemporaryFile(
            mode="w", prefix="ubox-r7-diag2-audit-", suffix=".json", delete=False
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
        self.diag2_system_mount = self.mounts / "diag1a-system"
        self.diag2_vendor_mount = self.mounts / "diag1a-vendor"
        self.diag1a_mounted = False

    def mount_exact_diag1a(self) -> None:
        if self.diag1a_mounted:
            return
        base = REPO / "out/candidates/a16-prototype-b-r7-diag1a"
        for image, point in ((base / "system_a.img", self.diag2_system_mount),
                             (base / "vendor_a.img", self.diag2_vendor_mount)):
            point.mkdir(parents=True, exist_ok=True)
            self.run(["sudo", "mount", "-o", "loop,ro,noload", str(image), str(point)])
            self.mounted.append(point)
        self.diag1a_mounted = True

    def audit_preservation(self, images: dict[str, Path]) -> dict[str, object]:
        result = DIAG1.Auditor.audit_preservation(self, images)
        self.mount_exact_diag1a()
        system_delta = self.tree_delta(self.diag2_system_mount, self.mounts / "system")
        vendor_delta = self.tree_delta(self.diag2_vendor_mount, self.mounts / "vendor")
        expected_system = {"added": [], "removed": [],
                           "changed": ["system/lib64/libstagefright.so"]}
        if system_delta != expected_system:
            raise RuntimeError(f"diag2 semantic delta expanded in system: {system_delta}")
        if vendor_delta != {"added": [], "removed": [], "changed": []}:
            raise RuntimeError(f"diag2 changed diag1a vendor: {vendor_delta}")

        preserved_records: dict[str, object] = {}
        for name, before, after in (
            ("/system/bin/surfaceflinger",
             self.diag2_system_mount / "system/bin/surfaceflinger",
             self.mounts / "system/system/bin/surfaceflinger"),
            ("/vendor/lib/hw/gralloc.apollo.so",
             self.diag2_vendor_mount / "lib/hw/gralloc.apollo.so",
             self.mounts / "vendor/lib/hw/gralloc.apollo.so"),
            ("/vendor/lib64/hw/gralloc.apollo.so",
             self.diag2_vendor_mount / "lib64/hw/gralloc.apollo.so",
             self.mounts / "vendor/lib64/hw/gralloc.apollo.so"),
        ):
            before_record = SHARED.R3.record(before)
            after_record = SHARED.R3.record(after)
            if any(before_record[field] != after_record[field]
                   for field in ("size", "sha256")):
                raise RuntimeError(f"diag2 changed preserved runtime file: {name}")
            preserved_records[name] = after_record

        self.mount_exact_diag1()
        arm32 = self.run_arm32_closure()
        result.update({
            "result": "PASS_EXACT_ONE_RUNTIME_FILE_HEVC_CROP_DELTA_FROM_DIAG1A",
            "diag1a_system_tree_delta": system_delta,
            "diag1a_vendor_tree_delta": vendor_delta,
            "diag1a_preserved_runtime_files": preserved_records,
            "arm32_graphics_sphal_closure": arm32,
            "libstagefright_elf_contract": {
                "class": "ELF64", "architecture": "AArch64",
                "soname_preserved": True, "dt_needed_preserved": True,
                "strong_exports_preserved": True,
                "undefined_strong_imports_preserved": True,
            },
            "visible_crop_only_semantic_delta": self.diag2["semantic_delta"],
            "all_other_diag1a_runtime_files_exact": True,
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
            "decision": "OFFLINE CHECKED / READY FOR PHYSICAL VALIDATION",
            "physical_status": "NOT_YET_VALIDATED",
            "physical_device_actions_performed": False,
            "flash_authorized": False,
            "candidate_classification": "DIAGNOSTIC_ONLY_NOT_R8_NOT_RELEASE",
            "evidence_status": "DIAG1A_PAIRED_PHYSICAL_EVIDENCE_READ_ONLY_AUDITED",
            "semantic_delta": self.diag2["semantic_delta"],
            "governance": self.diag2["governance"],
            "functional_result": {
                "architecture_ceiling": "PASS_FROZEN_UNCHANGED",
                "gate3": "HOLD", "h264": "PHYSICAL_PASS_CONTROL",
                "hevc": "BLOCKED_PENDING_DIAG2_PHYSICAL_VALIDATION",
                "r8": "NOT_AUTHORIZED_NOT_BUILT",
            },
        })
        audit["limitations"] = [
            "Diag2 has not been flashed or physically tested.",
            "The crop-to-EGL_BAD_ALLOC causal hypothesis remains pending physical validation.",
            "No HEVC PASS or repair is claimed.",
            "Full VINTF remains exit 65 for inherited CONFIG_NFS_FS=y versus FCM-6 n and is NOT PASS.",
            "Quarter-screen recovery and the known audio defect remain unchanged.",
        ]
        audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n",
                              encoding="utf-8")
        build_path = self.candidate / "build-result.json"
        build = json.loads(build_path.read_text(encoding="utf-8"))
        build.update({"status": "OFFLINE_CHECKED", "decision": audit["decision"],
                      "physical_status": audit["physical_status"], "flash_authorized": False,
                      "offline_audit": SHARED.R3.record(audit_path)})
        build_path.write_text(json.dumps(build, indent=2, sort_keys=True) + "\n",
                              encoding="utf-8")
        sums = [f"{SHARED.R3.digest(path)}  {path.name}"
                for path in sorted(self.candidate.iterdir())
                if path.is_file() and path.name != "SHA256SUMS"]
        (self.candidate / "SHA256SUMS").write_text("\n".join(sums) + "\n",
                                                   encoding="utf-8")

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
