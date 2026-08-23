#!/usr/bin/env python3
"""Audit the post-START_APP-timeout CCCR snapshot build against r1/r3."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys


REPO = Path(__file__).resolve().parents[1]
R3_AUDIT = REPO / "scripts/audit-m8-kernel-54302-r3.py"
SPEC = importlib.util.spec_from_file_location("m8_kernel_54302_r3_audit", R3_AUDIT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import audit helpers: {R3_AUDIT}")
R3 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = R3
SPEC.loader.exec_module(R3)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--r1-evidence", type=Path, required=True)
    parser.add_argument("--r3-evidence", type=Path, required=True)
    parser.add_argument("--r4-evidence", type=Path, required=True)
    parser.add_argument("--r1-build", type=Path, required=True)
    parser.add_argument("--r3-build", type=Path, required=True)
    parser.add_argument("--r4-build", type=Path, required=True)
    parser.add_argument("--donor", type=Path, required=True)
    parser.add_argument("--trace-patch", type=Path, required=True)
    parser.add_argument("--cccr-patch", type=Path, required=True)
    parser.add_argument("--candidate-build", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    for label, evidence in (("r3", args.r3_evidence), ("r4", args.r4_evidence)):
        if "result=SUCCESS" not in (evidence / "build.status").read_text():
            raise RuntimeError(f"{label} build status is not SUCCESS")

    cccr_text = args.cccr_patch.read_text(encoding="utf-8")
    added = "\n".join(
        line[1:] for line in cccr_text.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    )
    for forbidden in (
        "FEATURE_SDIO_CLOCK", "msleep(", "udelay(", "mdelay(",
        "schedule_timeout(", "wait_for_completion_timeout(",
        "RWNX_CMD_TIMEOUT_MS", "sdio_writesb(", "sdio_readsb(",
        "sdio_writeb(", "sdio_f0_writeb(", "retry", "retries",
    ):
        if forbidden in added:
            raise RuntimeError(f"CCCR patch contains forbidden functional delta: {forbidden}")
    for required, count in (
        ("#ifndef __GENKSYMS__", 1),
        ("sdio_claim_host(func)", 1),
        ("sdio_release_host(func)", 1),
        ("sdio_f0_readb(func, SDIO_CCCR_INTx", 1),
        ("sdio_f0_readb(func, SDIO_CCCR_IENx", 1),
        ("atomic_xchg(&trace->active, 0)", 1),
    ):
        if added.count(required) != count:
            raise RuntimeError(f"unexpected diagnostic source count for {required!r}")

    r1_result = args.r1_evidence / "build-result"
    r4_result = args.r4_evidence / "build-result"
    identical_build_files = [
        "built.config", "preservation.config", "path-a.config",
        "Module.symvers", "aic8800.Module.symvers",
    ]
    build_identity = {}
    for name in identical_build_files:
        before = R3.record(r1_result / name)
        after = R3.record(r4_result / name)
        if (before["size"], before["sha256"]) != (after["size"], after["sha256"]):
            raise RuntimeError(f"unexpected build contract drift: {name}")
        build_identity[name] = {"r1": before, "r4": after, "byte_identical": True}
    if R3.normalized_dtb_hashes(r1_result / "dtb-sha256.txt") != R3.normalized_dtb_hashes(
        r4_result / "dtb-sha256.txt"
    ):
        raise RuntimeError("DTB output hashes changed")

    r1_modules = R3.modules(args.r1_build / "modules-install")
    r3_modules = R3.modules(args.r3_build / "modules-install")
    r4_modules = R3.modules(args.r4_build / "modules-install")
    if set(r1_modules) != set(r3_modules) or set(r1_modules) != set(r4_modules) or len(r4_modules) != 22:
        raise RuntimeError("module inventory changed")
    module_audit = {}
    for name in sorted(r1_modules):
        metadata = {}
        for field in ("name", "depends", "vermagic"):
            values = [
                subprocess.check_output(["modinfo", "-F", field, str(modules[name])], text=True).strip()
                for modules in (r1_modules, r3_modules, r4_modules)
            ]
            if len(set(values)) != 1:
                raise RuntimeError(f"module metadata changed: {name}/{field}")
            metadata[field] = values[0]
        if metadata["vermagic"] != R3.EXPECTED_RELEASE:
            raise RuntimeError(f"unexpected vermagic: {name}")
        module_audit[name] = {
            "r1": R3.record(r1_modules[name]),
            "r3": R3.record(r3_modules[name]),
            "r4": R3.record(r4_modules[name]),
            "metadata": metadata,
        }

    bsp_r1 = r1_modules["aic8800_bsp.ko"]
    bsp_r3 = r3_modules["aic8800_bsp.ko"]
    bsp_r4 = r4_modules["aic8800_bsp.ko"]
    if R3.digest(bsp_r4) in (R3.digest(bsp_r1), R3.digest(bsp_r3)):
        raise RuntimeError("r4 AIC BSP does not contain a distinct snapshot build")
    if R3.symbols(bsp_r1, "defined") != R3.symbols(bsp_r4, "defined"):
        raise RuntimeError("AIC BSP exported symbol contract changed")
    r3_undefined = set(R3.symbols(bsp_r3, "undefined"))
    r4_undefined = set(R3.symbols(bsp_r4, "undefined"))
    if r4_undefined - r3_undefined != {"sdio_f0_readb"} or r3_undefined - r4_undefined:
        raise RuntimeError("unexpected r3-to-r4 unresolved-symbol delta")

    donor_root = args.donor / "drivers/net/wireless/aic8800"
    r3_root = args.r3_build / "src/drivers/net/wireless/aic8800-accepted"
    r4_root = args.r4_build / "src/drivers/net/wireless/aic8800-accepted"
    donor_changes = R3.source_delta(donor_root, r4_root)
    if [item["path"] for item in donor_changes] != R3.EXPECTED_SOURCE_PATHS:
        raise RuntimeError(f"unexpected donor-to-r4 source delta: {donor_changes}")
    r3_changes = R3.source_delta(r3_root, r4_root)
    expected_r3_delta = ["aic8800_bsp/aic_bsp_driver.c", "aic8800_bsp/aicsdio.h"]
    if [item["path"] for item in r3_changes] != expected_r3_delta:
        raise RuntimeError(f"unexpected r3-to-r4 source delta: {r3_changes}")

    header = (r4_root / "aic8800_bsp/aic_bsp_driver.h").read_text(encoding="utf-8")
    if header.count("#define FEATURE_SDIO_CLOCK          70000000") != 1:
        raise RuntimeError("r4 does not preserve the r1/r3 70 MHz behavior")
    driver = (r4_root / "aic8800_bsp/aic_bsp_driver.c").read_text(encoding="utf-8")
    snapshot_pos = driver.index("aic_startapp_trace_timeout_snapshot(aicdev)")
    close_pos = driver.index("!atomic_xchg(&trace->active, 0)", snapshot_pos)
    intx_pos = driver.index("sdio_f0_readb(func, SDIO_CCCR_INTx")
    ienx_pos = driver.index("sdio_f0_readb(func, SDIO_CCCR_IENx")
    if not (snapshot_pos < close_pos and intx_pos < ienx_pos):
        raise RuntimeError("timeout snapshot / trace close / CCCR read order changed")

    if args.candidate_build.exists():
        raise RuntimeError(f"refusing to overwrite candidate module root: {args.candidate_build}")
    candidate_modules_root = args.candidate_build / "modules-install"
    shutil.copytree(args.r1_build / "modules-install", candidate_modules_root, symlinks=True)
    candidate_modules = R3.modules(candidate_modules_root)
    shutil.copyfile(bsp_r4, candidate_modules["aic8800_bsp.ko"])
    changed_modules = sorted(
        name for name in r1_modules
        if R3.digest(r1_modules[name]) != R3.digest(candidate_modules[name])
    )
    if changed_modules != ["aic8800_bsp.ko"]:
        raise RuntimeError(f"candidate single-module invariant failed: {changed_modules}")

    report = {
        "schema": 1,
        "result": "PASS_POST_TIMEOUT_CCCR_INSTRUMENTATION_ONLY",
        "trace_patch": R3.record(args.trace_patch),
        "cccr_patch": R3.record(args.cccr_patch),
        "donor_source_delta": donor_changes,
        "r3_to_r4_source_delta": r3_changes,
        "r1_sdio_clock_hz_preserved": 70_000_000,
        "timeout_snapshot": {
            "trace_window_closed_after_snapshot": True,
            "read_order": ["SDIO_CCCR_INTx", "SDIO_CCCR_IENx"],
            "writes": 0,
            "timeout_or_retry_changes": 0,
            "pre_timeout_control_flow_changes": 0,
        },
        "dtbs_byte_identical": True,
        "build_identity": build_identity,
        "module_count": len(r4_modules),
        "candidate_changed_modules": changed_modules,
        "candidate_module_root": str(candidate_modules_root),
        "modules": module_audit,
        "aic_bsp_symbol_contract": {
            "exported_symbols_identical_to_r1": True,
            "module_export_crcs_byte_identical_to_r1": True,
            "r3_to_r4_added_imports": ["sdio_f0_readb"],
        },
        "behavioral_changes_before_startapp_timeout": [],
        "physical_validation_required": True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"result": report["result"], "candidate_changed_modules": changed_modules}, sort_keys=True))


if __name__ == "__main__":
    main()
