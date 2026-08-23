#!/usr/bin/env python3
"""Build and audit the r2 AIC8800D 50 MHz diagnostic candidate."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import time


REPO = Path(__file__).resolve().parents[1]
BASE_BUILDER_PATH = REPO / "scripts/build-m8-kernel-54302-candidate.py"
SPEC = importlib.util.spec_from_file_location("m8_kernel_54302_candidate", BASE_BUILDER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import candidate builder: {BASE_BUILDER_PATH}")
BASE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = BASE
SPEC.loader.exec_module(BASE)


class R2Builder(BASE.Builder):
    """Reuse the r1 filesystem/LP checks while preserving its boot bytes."""

    def pack_outer(self, boot: Path, super_sparse: Path):
        expected_boot = self.cfg["r1_preserved"]["boot"]
        if BASE.record(boot)["size"] != expected_boot["size"] or BASE.digest(boot) != expected_boot["sha256"]:
            raise RuntimeError("reproduced boot is not byte-identical to accepted r1")

        before_payloads = BASE.outer_payloads(self.base)
        firmware = self.stage / f"x12-{self.candidate_id}.img"
        pack_audit_path = self.stage / "outer-payload-audit.json"
        self.run(
            [
                sys.executable, str(REPO / "tools/pack_image_preserving.py"),
                "--source", str(self.base),
                "--output", str(firmware),
                "--replace", f"super.fex={super_sparse}",
                "--audit", str(pack_audit_path),
            ]
        )
        self.run(
            [sys.executable, str(REPO / "tools/sunxi_image_tool.py"), "verify", str(firmware)],
            output=self.stage / "candidate-outer-verify.log",
        )
        after_payloads = BASE.outer_payloads(firmware)
        if set(before_payloads) != set(after_payloads):
            raise RuntimeError("outer payload inventory changed")
        changed = sorted(
            name for name in before_payloads
            if before_payloads[name]["sha256_stored"] != after_payloads[name]["sha256_stored"]
        )
        expected_changed = sorted(
            [*self.cfg["container"]["replacements"], *self.cfg["container"]["companions"]]
        )
        if changed != expected_changed:
            raise RuntimeError(f"unexpected outer payload delta: {changed}")

        pack_audit = json.loads(pack_audit_path.read_text(encoding="utf-8"))
        actions = {item["filename"]: item["action"] for item in pack_audit["payloads"]}
        if len(actions) != self.cfg["container"]["total_entries"]:
            raise RuntimeError("outer entry count changed")
        if sum(action == "preserved" for action in actions.values()) != self.cfg["container"]["preserved_entries"]:
            raise RuntimeError("outer preservation count changed")
        if actions.get("super.fex") != "replacement" or actions.get("Vsuper.fex") != "companion":
            raise RuntimeError("super replacement/companion actions missing")

        extracted = self.stage / "candidate-outer"
        extracted.mkdir()
        self.run(
            [
                sys.executable, str(REPO / "tools/sunxi_image_tool.py"), "extract",
                "-o", str(extracted), "-f", "super.fex", str(firmware),
            ]
        )
        if BASE.digest(extracted / "super.fex") != BASE.digest(super_sparse):
            raise RuntimeError("packed outer super replacement changed")
        return firmware, {
            "candidate": BASE.record(firmware),
            "entry_count": len(actions),
            "changed_payloads": changed,
            "preserved_payload_count": self.cfg["container"]["preserved_entries"],
            "all_preserved_payload_bytes_exact": True,
            "r1_boot_payload_exact": True,
            "imagewty_verify": "PASS",
        }

    def finish(
        self, firmware, image, boot_audit, vendor_dlkm_audit,
        super_audit, outer_audit, started,
    ) -> None:
        if BASE.record(self.base) != self.base_before:
            raise RuntimeError("r1 base changed during construction")
        if BASE.record(self.rollback) != self.rollback_before:
            raise RuntimeError("rollback image changed during construction")
        expected = self.cfg["expected_result"]
        for label, path in (
            ("firmware", firmware),
            ("boot", Path(str(boot_audit["candidate"]["path"]))),
            ("super", Path(str(super_audit["candidate_sparse"]["path"]))),
            ("vendor_dlkm", Path(str(vendor_dlkm_audit["candidate"]["path"]))),
        ):
            actual = BASE.record(path)
            if actual["size"] != expected[label]["size"] or actual["sha256"] != expected[label]["sha256"]:
                raise RuntimeError(f"non-reproducible candidate {label}: {actual}")

        result = {
            "schema": 1,
            "id": self.candidate_id,
            "status": "OFFLINE_CHECKED_DIAGNOSTIC",
            "decision": "AWAIT_SEPARATELY_AUTHORIZED_PHYSICAL_WIFI_VALIDATION",
            "gate2": "CLOSED",
            "physical_device_actions_performed": False,
            "flash_authorized": False,
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
                "r1 boot.fex and Linux 5.4.302 Image bytes",
                "r1 boot header, cmdline, ramdisk and AVB footer",
                "r1 Android 12 system_a, vendor_a and product_a bytes",
                "r1 DT/DTBO, vendor_boot, bootloader, TEE and vbmeta payloads",
                "LP metadata, extents, group limits and three metadata slots",
                "21 non-AIC-BSP module bytes and all module metadata files",
                "m8b-remote-r1 input, r1 candidate and Test8r2 rollback image",
            ],
            "changed": [
                "FEATURE_SDIO_CLOCK constant: 70000000 to 50000000",
                "aic8800_bsp.ko only within vendor_dlkm",
                "vendor_dlkm AVB hashtree/FEC and containing super.fex extent",
                "IMAGEWTY Vsuper checksum companion",
            ],
            "offline_limitations": [
                "Offline checks cannot prove the host realizes exactly 50 MHz on hardware.",
                "Offline checks cannot prove DBG_START_APP_CFM, persistent aic8800_fdrv, wlan0 or Android Wi-Fi usability.",
                "A separately authorized UART-first physical test is required; this result does not authorize flashing.",
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
    parser = BASE.argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path,
        default=REPO / "configs/candidates/m8-kernel-5.4.302-r2.json",
    )
    parser.add_argument("--aosp", type=Path, default=BASE.DEFAULT_AOSP)
    parser.add_argument("--integration-repo", type=Path, default=BASE.DEFAULT_INTEGRATION)
    parser.add_argument("--keep-failed", action="store_true")
    R2Builder(parser.parse_args()).build()


if __name__ == "__main__":
    main()
