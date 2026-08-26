#!/usr/bin/env python3
"""Build the strict two-delta Android 16 Prototype A r4 successor."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import time


REPO = Path(__file__).resolve().parents[1]
R3_PATH = REPO / "scripts/build-a16-prototype-a-r3-candidate.py"
SPEC = importlib.util.spec_from_file_location("a16_prototype_a_r3_builder", R3_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import r3 candidate builder: {R3_PATH}")
R3 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = R3
SPEC.loader.exec_module(R3)

DEFAULT_CONFIG = REPO / "configs/candidates/a16-prototype-a-r4.json"
DEFAULT_AOSP = Path("/work/src/ubox10-a16-ceiling")
DEFAULT_INTEGRATION = Path("/work/src/ubox10-kernel-5.4.302-common")


class R4Builder(R3.R3Builder):
    """Reuse r3 system/AVB logic while byte-preserving its hardware payloads."""

    def preserve_boot_and_vendor_dlkm(
        self,
    ) -> tuple[Path, Path, dict[str, object], dict[str, object]]:
        boot_source = self.verified_path(self.cfg["accepted"]["boot"])
        vendor_dlkm_source = self.verified_path(
            self.cfg["accepted"]["logical"]["vendor_dlkm_a"]
        )
        boot = self.stage / "boot.fex"
        vendor_dlkm = self.stage / "vendor_dlkm_a.img"
        shutil.copyfile(boot_source, boot)
        shutil.copyfile(vendor_dlkm_source, vendor_dlkm)
        self.require(boot, self.cfg["r3_baseline"]["boot"], "preserved r3 boot")
        self.require(
            vendor_dlkm,
            self.cfg["r3_baseline"]["vendor_dlkm"],
            "preserved r3 vendor_dlkm",
        )
        boot_audit = {
            "accepted": R3.BASE.record(boot_source),
            "candidate": R3.BASE.record(boot),
            "byte_preserved_from_r3": True,
            "kernel_rebuilt": False,
            "ramdisk_rebuilt": False,
            "avb_footer_preserved": True,
        }
        vendor_dlkm_audit = {
            "accepted": R3.BASE.record(vendor_dlkm_source),
            "candidate": R3.BASE.record(vendor_dlkm),
            "byte_preserved_from_r3": True,
            "module_set_rebuilt": False,
            "module_count": 22,
            "avb_hashtree_fec_preserved": True,
        }
        return boot, vendor_dlkm, boot_audit, vendor_dlkm_audit

    def build_super(
        self, system: Path, vendor_dlkm: Path
    ) -> tuple[Path, dict[str, object]]:
        sparse, audit = super().build_super(system, vendor_dlkm)
        source = self.verified_path(self.cfg["accepted"]["super_raw"])
        candidate = Path(str(audit["candidate_raw"]["path"]))
        sector_size = int(self.cfg["super"]["sector_size"])
        offset = int(self.cfg["super"]["system_first_sector"]) * sector_size
        length = int(self.cfg["super"]["system_sector_count"]) * sector_size
        spans = ((0, offset), (offset + length, source.stat().st_size - offset - length))
        for span_offset, span_length in spans:
            before = R3.digest_range(source, span_offset, span_length)
            after = R3.digest_range(candidate, span_offset, span_length)
            if before != after:
                raise RuntimeError("r4 raw super changed bytes outside system_a")
        audit["bytes_outside_system_a_extent_exact"] = True
        audit["vendor_dlkm_extent_byte_preserved_from_r3"] = True
        audit["only_logical_partition_changed"] = "system_a"
        return sparse, audit

    def pack_outer(
        self, boot: Path, super_sparse: Path, vbmeta_system: Path
    ) -> tuple[Path, dict[str, object]]:
        # boot is intentionally validated and copied into the candidate directory,
        # but the outer packer receives no boot replacement: the r3 bytes remain.
        self.require(boot, self.cfg["r3_baseline"]["boot"], "r4 preserved boot")
        before = R3.BASE.outer_payloads(self.base)
        firmware = self.stage / f"x12-{self.candidate_id}.img"
        audit_path = self.stage / "outer-payload-audit.json"
        self.run(
            [
                sys.executable,
                str(REPO / "tools/pack_image_preserving.py"),
                "--source",
                str(self.base),
                "--output",
                str(firmware),
                "--replace",
                f"super.fex={super_sparse}",
                "--replace",
                f"vbmeta_system.fex={vbmeta_system}",
                "--audit",
                str(audit_path),
            ]
        )
        self.run(
            [
                sys.executable,
                str(REPO / "tools/sunxi_image_tool.py"),
                "verify",
                str(firmware),
            ],
            output=self.stage / "candidate-outer-verify.log",
        )
        after = R3.BASE.outer_payloads(firmware)
        if set(before) != set(after):
            raise RuntimeError("r4 outer payload inventory changed")
        changed = sorted(
            name
            for name in before
            if before[name]["sha256_stored"] != after[name]["sha256_stored"]
        )
        expected = sorted(
            [*self.cfg["container"]["replacements"], *self.cfg["container"]["companions"]]
        )
        if changed != expected:
            raise RuntimeError(f"unexpected r4 outer payload delta: {changed}")
        actions = {
            item["filename"]: item["action"]
            for item in json.loads(audit_path.read_text())["payloads"]
        }
        if len(actions) != self.cfg["container"]["total_entries"]:
            raise RuntimeError("r4 outer payload count changed")
        preserved = sum(value == "preserved" for value in actions.values())
        if preserved != self.cfg["container"]["preserved_entries"]:
            raise RuntimeError(f"r4 outer preserved count changed: {preserved}")
        return firmware, {
            "candidate": R3.BASE.record(firmware),
            "entry_count": len(actions),
            "changed_payloads": changed,
            "preserved_payload_count": preserved,
            "all_other_payload_bytes_exact": True,
            "imagewty_verify": "PASS",
            "boot_payload_byte_preserved_from_r3": True,
        }

    def finish_r4(
        self,
        firmware: Path,
        system_audit: dict[str, object],
        boot_audit: dict[str, object],
        vendor_dlkm_audit: dict[str, object],
        super_audit: dict[str, object],
        outer_audit: dict[str, object],
        started: float,
    ) -> None:
        if (
            R3.BASE.record(self.base) != self.base_before
            or R3.BASE.record(self.rollback) != self.rollback_before
        ):
            raise RuntimeError("r3 baseline or rollback changed during r4 construction")
        kernel = self.evidence_path(self.cfg["kernel_build"]["image"])
        result = {
            "schema": 1,
            "id": self.candidate_id,
            "status": "PACKAGED_AWAITING_FULL_OFFLINE_AUDIT",
            "physical_device_actions_performed": False,
            "flash_authorized": False,
            "elapsed_seconds": round(time.time() - started, 1),
            "firmware": R3.BASE.record(firmware),
            "kernel": R3.BASE.record(kernel),
            "kernel_release": "5.4.302+",
            "kernel_rebuilt": False,
            "functional_delta": self.cfg["functional_delta"],
            "system": system_audit,
            "boot": boot_audit,
            "vendor_dlkm": vendor_dlkm_audit,
            "super": super_audit,
            "outer": outer_audit,
            "vbmeta_system": R3.BASE.record(self.vbmeta_system),
            "preserved_from_r3": [
                "boot, kernel, ramdisk and boot AVB footer",
                "all 22 vendor_dlkm modules and vendor_dlkm AVB/FEC",
                "accepted vendor_a and product_a",
                "vendor_boot, DT/DTBO, TEE, DRM, factory/security and bootloader",
                "top-level vbmeta, rollback/recovery and every unrelated IMAGEWTY payload",
                "HDMI, audio, Wi-Fi and Ethernet hardware authority",
            ],
        }
        result = R3.BASE.rewrite_paths(result, self.stage, self.final)
        (self.stage / "build-result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        expected = self.cfg.get("expected_result")
        if expected:
            checks = {
                "firmware": firmware,
                "system": self.system,
                "boot": Path(str(boot_audit["candidate"]["path"])),
                "vendor_dlkm": Path(str(vendor_dlkm_audit["candidate"]["path"])),
                "super": Path(str(super_audit["candidate_sparse"]["path"])),
                "vbmeta_system": self.vbmeta_system,
            }
            for label, path in checks.items():
                actual = R3.BASE.record(path)
                if (
                    actual["size"] != expected[label]["size"]
                    or actual["sha256"] != expected[label]["sha256"]
                ):
                    raise RuntimeError(f"non-reproducible r4 {label}: {actual}")
        sums = []
        for path in sorted(self.stage.iterdir()):
            if path.is_file() and path.name != "SHA256SUMS":
                sums.append(f"{R3.BASE.digest(path)}  {path.name}")
        (self.stage / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
        os.replace(self.stage, self.final)

    def build(self) -> None:
        started = time.time()
        try:
            self.setup()
            system, system_audit = self.prepare_system()
            vbmeta_system = self.make_vbmeta_system(system)
            boot, vendor_dlkm, boot_audit, vendor_dlkm_audit = (
                self.preserve_boot_and_vendor_dlkm()
            )
            super_sparse, super_audit = self.build_super(system, vendor_dlkm)
            firmware, outer_audit = self.pack_outer(boot, super_sparse, vbmeta_system)
            self.finish_r4(
                firmware,
                system_audit,
                boot_audit,
                vendor_dlkm_audit,
                super_audit,
                outer_audit,
                started,
            )
            print(f"SUCCESS: {self.final} ({time.time() - started:.1f}s)", flush=True)
        except Exception:
            if self.stage.exists() and not self.args.keep_failed:
                shutil.rmtree(self.stage)
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--aosp", type=Path, default=DEFAULT_AOSP)
    parser.add_argument("--integration-repo", type=Path, default=DEFAULT_INTEGRATION)
    parser.add_argument("--keep-failed", action="store_true")
    R4Builder(parser.parse_args()).build()


if __name__ == "__main__":
    main()
