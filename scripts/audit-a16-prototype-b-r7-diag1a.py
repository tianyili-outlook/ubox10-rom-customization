#!/usr/bin/env python3
"""Audit diag1a with exact diag1 delta and dual-architecture graphics closure."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys


REPO = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE = REPO / "out/candidates/a16-prototype-b-r7-diag1a"
DEFAULT_CONFIG = REPO / "configs/candidates/a16-prototype-b-r7-diag1a.json"
DEFAULT_AOSP = Path("/work/src/ubox10-a16-ceiling")
DIAG1_PATH = REPO / "scripts/audit-a16-prototype-b-r7-diag1.py"
DIAG1_SPEC = importlib.util.spec_from_file_location("a16_b_r7_diag1_auditor_for_diag1a", DIAG1_PATH)
if DIAG1_SPEC is None or DIAG1_SPEC.loader is None:
    raise RuntimeError(f"cannot import diag1 auditor: {DIAG1_PATH}")
DIAG1 = importlib.util.module_from_spec(DIAG1_SPEC)
sys.modules[DIAG1_SPEC.name] = DIAG1
DIAG1_SPEC.loader.exec_module(DIAG1)

SHARED = DIAG1.SHARED


class Auditor(DIAG1.Auditor):
    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__(args)
        self.diag1_system_mount = self.mounts / "diag1-system"
        self.diag1_vendor_mount = self.mounts / "diag1-vendor"
        self.diag1_mounted = False

    def mount_exact_r7(self) -> None:
        if self.base_mounted:
            return
        exact = REPO / "out/candidates/a16-prototype-b-r7"
        for path, point in (
            (exact / "system_a.img", self.r7_system_mount),
            (exact / "vendor_a.img", self.r7_vendor_mount),
        ):
            point.mkdir(parents=True, exist_ok=True)
            self.run(["sudo", "mount", "-o", "loop,ro,noload", str(path), str(point)])
            self.mounted.append(point)
        self.base_mounted = True

    def mount_exact_diag1(self) -> None:
        if self.diag1_mounted:
            return
        exact = REPO / "out/candidates/a16-prototype-b-r7-diag1"
        for path, point in (
            (exact / "system_a.img", self.diag1_system_mount),
            (exact / "vendor_a.img", self.diag1_vendor_mount),
        ):
            point.mkdir(parents=True, exist_ok=True)
            self.run(["sudo", "mount", "-o", "loop,ro,noload", str(path), str(point)])
            self.mounted.append(point)
        self.diag1_mounted = True

    def run_arm32_closure(self) -> dict[str, object]:
        checker = REPO / "scripts/check-a16-prototype-b-r7-graphics.py"
        common = [
            sys.executable,
            str(checker),
            "--architecture", "arm32",
            "--system-lib", str(self.root / "system/lib"),
            "--runtime-lib", str(self.root / "apex/com.android.runtime/lib/bionic"),
            "--vndk-lib", str(self.root / "apex/com.android.vndk.v31/lib"),
            "--linker-config", str(self.audit / "linker-generated/ld.config.txt"),
        ]
        corrected_json = self.audit / "graphics-sphal-closure-arm32.json"
        self.run(
            common + [
                "--mapper", str(self.mounts / "vendor/lib/hw/android.hardware.graphics.mapper@2.0-impl-2.1.so"),
                "--gralloc", str(self.mounts / "vendor/lib/hw/gralloc.apollo.so"),
                "--output", str(corrected_json),
            ],
            output=self.audit / "graphics-sphal-closure-arm32.log",
        )
        failed_json = self.audit / "diag1-graphics-sphal-closure-arm32-failure.json"
        self.run(
            common + [
                "--mapper", str(self.diag1_vendor_mount / "lib/hw/android.hardware.graphics.mapper@2.0-impl-2.1.so"),
                "--gralloc", str(self.diag1_vendor_mount / "lib/hw/gralloc.apollo.so"),
                "--output", str(failed_json),
            ],
            output=self.audit / "diag1-graphics-sphal-closure-arm32-failure.log",
            allowed={1},
        )
        corrected = json.loads(corrected_json.read_text(encoding="utf-8"))
        failed = json.loads(failed_json.read_text(encoding="utf-8"))
        missing = "_ZNSt3__122__libcpp_verbose_abortEPKcz"
        if (
            corrected["decision"] != "PASS_EXACT_ARM32_MAPPER_GRALLOC_SPHAL_CLOSURE"
            or corrected["gralloc"]["unmatched_count"] != 0
            or corrected["gralloc"]["libcpp_verbose_abort_import"]
        ):
            raise RuntimeError("installed diag1a ARM32 graphics closure failed")
        if failed["gralloc"]["unmatched_strong_imports"] != [missing]:
            raise RuntimeError("installed failed diag1 no longer isolates verbose-abort")
        return {"failed_diag1": failed, "corrected_diag1a": corrected}

    def audit_preservation(self, images: dict[str, Path]) -> dict[str, object]:
        result = super().audit_preservation(images)
        self.mount_exact_diag1()
        system_delta = self.tree_delta(self.diag1_system_mount, self.mounts / "system")
        vendor_delta = self.tree_delta(self.diag1_vendor_mount, self.mounts / "vendor")
        if system_delta != {"added": [], "removed": [], "changed": []}:
            raise RuntimeError(f"diag1a changed diag1 system: {system_delta}")
        expected_vendor = {
            "added": [],
            "removed": [],
            "changed": ["lib/hw/gralloc.apollo.so"],
        }
        if vendor_delta != expected_vendor:
            raise RuntimeError(f"diag1a semantic delta expanded: {vendor_delta}")

        preserved = {
            "/system/bin/surfaceflinger": (
                self.diag1_system_mount / "system/bin/surfaceflinger",
                self.mounts / "system/system/bin/surfaceflinger",
            ),
            "/system/lib64/libstagefright.so": (
                self.diag1_system_mount / "system/lib64/libstagefright.so",
                self.mounts / "system/system/lib64/libstagefright.so",
            ),
            "/vendor/lib64/hw/gralloc.apollo.so": (
                self.diag1_vendor_mount / "lib64/hw/gralloc.apollo.so",
                self.mounts / "vendor/lib64/hw/gralloc.apollo.so",
            ),
        }
        preserved_records: dict[str, object] = {}
        for name, (before, after) in preserved.items():
            before_record = SHARED.R3.record(before)
            after_record = SHARED.R3.record(after)
            if any(before_record[field] != after_record[field] for field in ("size", "sha256")):
                raise RuntimeError(f"diag1a changed preserved diagnostic runtime: {name}")
            preserved_records[name] = after_record

        gralloc_before = self.diag1_vendor_mount / "lib/hw/gralloc.apollo.so"
        gralloc_after = self.mounts / "vendor/lib/hw/gralloc.apollo.so"
        expected_before = self.diag["diag1_delta"]["failed_gralloc32"]
        expected_after = self.diag["diag1_delta"]["corrected_gralloc32"]
        for label, path, expected in (
            ("diag1", gralloc_before, expected_before),
            ("diag1a", gralloc_after, expected_after),
        ):
            actual = SHARED.R3.record(path)
            if actual["size"] != expected["size"] or actual["sha256"] != expected["sha256"]:
                raise RuntimeError(f"installed {label} ARM32 gralloc identity changed")
        if b"UBOX_R7_DIAG1" not in gralloc_after.read_bytes():
            raise RuntimeError("installed corrected ARM32 gralloc lost diagnostic marker")
        imports = subprocess.check_output(
            ["nm", "-D", "--undefined-only", "--format=posix", str(gralloc_after)], text=True
        )
        if "_ZNSt3__122__libcpp_verbose_abortEPKcz" in imports:
            raise RuntimeError("installed corrected ARM32 gralloc retains verbose-abort import")

        arm32_closure = self.run_arm32_closure()
        result.update({
            "result": "PASS_EXACT_ONE_RUNTIME_FILE_BOOT_COMPATIBILITY_DELTA_FROM_DIAG1",
            "diag1_system_tree_delta": system_delta,
            "diag1_vendor_tree_delta": vendor_delta,
            "diag1a_preserved_runtime_files": preserved_records,
            "diag1_gralloc32": SHARED.R3.record(gralloc_before),
            "diag1a_gralloc32": SHARED.R3.record(gralloc_after),
            "arm32_graphics_sphal_closure": arm32_closure,
            "verbose_abort_unmatched_after": False,
            "diagnostic_instrumentation_retained": True,
            "hevc_semantics_changed": False,
        })
        return result

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
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        audit.update({
            "decision": "OFFLINE CHECKED / READY FOR PHYSICAL BOOT GATE",
            "physical_status": "NOT_YET_VALIDATED",
            "physical_device_actions_performed": False,
            "flash_authorized": False,
            "diag1_physical_result": {
                "status": "PHYSICAL_BOOT_FAIL_CLOSED_DIAGNOSTIC_CANDIDATE",
                "root_cause": "ARM32 gralloc unresolved __libcpp_verbose_abort import",
                "surfaceflinger_failed_to_create_composer_client": "DOWNSTREAM",
            },
            "diag1a": {
                "status": "OFFLINE_CHECKED_PENDING_PHYSICAL_BOOT",
                "runtime_delta_from_diag1": ["/vendor/lib/hw/gralloc.apollo.so"],
                "hevc_repair": False,
            },
            "governance": self.diag["governance"],
            "functional_result": {
                "architecture_ceiling": "PASS_FROZEN_UNCHANGED",
                "gate3": "HOLD",
                "h264": "PHYSICAL_PASS_FROM_EXACT_R7",
                "hevc": "FAIL_BLOCKER_NOT_FIXED",
                "r8": "NOT_AUTHORIZED_NOT_BUILT",
            },
        })
        audit["limitations"] = [
            "No physical UBOX action occurred in this correction task.",
            "Diag1a must pass a normal physical boot gate before paired AVC/HEVC capture resumes.",
            "The HEVC first-fatal boundary remains proven, but the first discriminating AVC-versus-HEVC contract field remains unproven.",
            "Full VINTF remains exit 65 only for inherited CONFIG_NFS_FS=y versus FCM-6 n and is NOT PASS.",
            "Quarter-screen recovery and the known post-restart audio crash remain unchanged and unfixed.",
        ]
        audit_path.write_text(
            json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

        build_path = self.candidate / "build-result.json"
        build = json.loads(build_path.read_text(encoding="utf-8"))
        build["status"] = "OFFLINE_CHECKED"
        build["decision"] = audit["decision"]
        build["physical_status"] = audit["physical_status"]
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
