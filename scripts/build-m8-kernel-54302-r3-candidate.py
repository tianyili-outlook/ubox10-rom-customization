#!/usr/bin/env python3
"""Build the r3 START_APP instrumentation-only Android 12 candidate."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import time


REPO = Path(__file__).resolve().parents[1]
R1_CONFIG = REPO / "configs/candidates/m8-kernel-5.4.302-r1.json"
R2_BUILDER_PATH = REPO / "scripts/build-m8-kernel-54302-r2-candidate.py"
SPEC = importlib.util.spec_from_file_location("m8_kernel_54302_r2_candidate", R2_BUILDER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import candidate builder: {R2_BUILDER_PATH}")
R2 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = R2
SPEC.loader.exec_module(R2)
BASE = R2.BASE


class R3Builder(R2.R2Builder):
    """Reuse r1 bytes and replace only its AIC BSP with the traced module."""

    def __init__(self, args: argparse.Namespace) -> None:
        r3 = json.loads(args.config.read_text(encoding="utf-8"))
        selected = args.config
        args.config = R1_CONFIG
        super().__init__(args)
        args.config = selected

        self.cfg["id"] = r3["id"]
        self.cfg["purpose"] = r3["purpose"]
        self.cfg["decision_scope"] = r3["decision_scope"]
        self.cfg["base_candidate"] = r3["base_candidate"]
        self.cfg["rollback"] = r3["rollback"]
        self.cfg["container"] = r3["container"]
        self.cfg["r1_preserved"] = r3["r1_preserved"]
        self.cfg["experiment"] = r3["experiment"]
        self.cfg["expected_result"] = r3.get("expected_result", {})
        self.cfg["kernel_build"]["build_root"] = r3["candidate_module_build"]
        self.cfg["vendor_dlkm"].update(r3["vendor_dlkm_delta"])
        for module in self.cfg["kernel_build"]["modules"]:
            if module["file"] == "aic8800_bsp.ko":
                module.update(r3["instrumented_module"])
                break
        else:
            raise RuntimeError("r1 module contract lacks aic8800_bsp.ko")

        self.candidate_id = r3["id"]
        self.final = REPO / "out/candidates" / self.candidate_id
        self.stage = self.final.parent / f".{self.candidate_id}.staging-{BASE.uuid.uuid4().hex}"
        self.log = self.stage / "logs/01-commands.log"
        self.base = Path(str(self.cfg["base_candidate"]["path"]))
        self.rollback = Path(str(self.cfg["rollback"]["path"]))
        self.build_root = Path(str(self.cfg["kernel_build"]["build_root"]))

    def finish(
        self, firmware, image, boot_audit, vendor_dlkm_audit,
        super_audit, outer_audit, started,
    ) -> None:
        if BASE.record(self.base) != self.base_before:
            raise RuntimeError("physical r1 base changed during construction")
        if BASE.record(self.rollback) != self.rollback_before:
            raise RuntimeError("rollback image changed during construction")

        artifacts = {
            "firmware": BASE.record(firmware),
            "boot": BASE.record(Path(str(boot_audit["candidate"]["path"]))),
            "super": BASE.record(Path(str(super_audit["candidate_sparse"]["path"]))),
            "vendor_dlkm": BASE.record(Path(str(vendor_dlkm_audit["candidate"]["path"]))),
        }
        expected = self.cfg.get("expected_result", {})
        if expected:
            for label, actual in artifacts.items():
                if actual["size"] != expected[label]["size"] or actual["sha256"] != expected[label]["sha256"]:
                    raise RuntimeError(f"non-reproducible candidate {label}: {actual}")

        result = {
            "schema": 1,
            "id": self.candidate_id,
            "status": "OFFLINE_CHECKED_INSTRUMENTATION_ONLY",
            "decision": "AWAIT_SEPARATE_EXPLICIT_PHYSICAL_AUTHORIZATION",
            "gate2": "CLOSED",
            "physical_device_actions_performed": False,
            "flash_authorized": False,
            "not_a_fix": True,
            "firmware": BASE.record(firmware),
            "kernel": BASE.record(image),
            "kernel_release": "5.4.302+",
            "source_commit": self.cfg["integration"]["commit"],
            "source_tree": self.cfg["integration"]["tree"],
            "elapsed_seconds": round(time.time() - started, 1),
            "experiment": self.cfg["experiment"],
            "boot": boot_audit,
            "vendor_dlkm": vendor_dlkm_audit,
            "super": super_audit,
            "outer": outer_audit,
            "preserved": [
                "physical r1 boot.fex, Linux 5.4.302 Image, ramdisk, DT and boot AVB bytes",
                "r1 Android 12 system_a, vendor_a, product_a and userspace bytes",
                "r1 DTBO, vendor_boot, bootloader, TEE and vbmeta payloads",
                "LP metadata, extents, group limits and three metadata slots",
                "21 unrelated module bytes and all module metadata/static vendor_dlkm files",
                "r1 70 MHz AIC runtime clock behavior and original timeouts/control flow",
                "m8b-remote-r1 input, physical r1 candidate and Test8r2 rollback image",
            ],
            "changed": [
                "START_APP-gated observability source in the pinned AIC8800 BSP",
                "aic8800_bsp.ko only within vendor_dlkm",
                "vendor_dlkm AVB hashtree/FEC and containing super.fex extent",
                "IMAGEWTY Vsuper checksum companion",
            ],
            "offline_limitations": [
                "Instrumentation does not change or prove Wi-Fi behavior.",
                "Only a separately authorized UART run can locate the 1037/1038 runtime boundary.",
                "This candidate does not authorize flashing and does not open Gate 2.",
            ],
        }
        result = BASE.rewrite_paths(result, self.stage, self.final)
        (self.stage / "build-result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        sums = []
        for path in sorted(self.stage.iterdir()):
            if path.is_file() and path.name != "SHA256SUMS":
                sums.append(f"{BASE.digest(path)}  {path.name}")
        (self.stage / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
        os.replace(self.stage, self.final)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path,
        default=REPO / "configs/candidates/m8-kernel-5.4.302-r3.json",
    )
    parser.add_argument("--aosp", type=Path, default=BASE.DEFAULT_AOSP)
    parser.add_argument("--integration-repo", type=Path, default=BASE.DEFAULT_INTEGRATION)
    parser.add_argument("--keep-failed", action="store_true")
    R3Builder(parser.parse_args()).build()


if __name__ == "__main__":
    main()
