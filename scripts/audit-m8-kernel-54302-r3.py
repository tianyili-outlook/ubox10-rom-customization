#!/usr/bin/env python3
"""Audit the START_APP-only AIC8800 BSP trace build against physical r1."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess


CHUNK = 8 * 1024 * 1024
EXPECTED_RELEASE = "5.4.302+ SMP preempt mod_unload modversions aarch64"
EXPECTED_SOURCE_PATHS = [
    "aic8800_bsp/aic_bsp_driver.c",
    "aic8800_bsp/aic_bsp_txrxif.c",
    "aic8800_bsp/aicsdio.c",
    "aic8800_bsp/aicsdio.h",
]


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(CHUNK), b""):
            value.update(block)
    return value.hexdigest().upper()


def record(path: Path) -> dict[str, object]:
    return {"path": str(path), "size": path.stat().st_size, "sha256": digest(path)}


def modules(root: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for path in root.rglob("*.ko"):
        if path.name in result:
            raise RuntimeError(f"duplicate module basename: {path.name}")
        result[path.name] = path
    return result


def command(*args: str) -> list[str]:
    return subprocess.check_output(args, text=True).splitlines()


def symbols(path: Path, mode: str) -> list[str]:
    args = ["nm", "-g", "--defined-only"] if mode == "defined" else ["nm", "-u"]
    values = []
    for line in command(*args, str(path)):
        fields = line.split()
        if fields:
            values.append(re.sub(r"\.llvm\.\d+$", ".llvm.<build-id>", fields[-1]))
    return sorted(values)


def normalized_dtb_hashes(path: Path) -> dict[str, str]:
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        sha256, filename = line.split(maxsplit=1)
        marker = "/arch/arm64/boot/dts/"
        if marker not in filename:
            raise RuntimeError(f"unexpected DTB path: {filename}")
        result[filename.split(marker, 1)[1]] = sha256.upper()
    return result


def source_delta(donor: Path, built: Path) -> list[dict[str, str | None]]:
    before = {path.relative_to(donor): path for path in donor.rglob("*") if path.is_file()}
    after = {path.relative_to(built): path for path in built.rglob("*") if path.is_file()}
    changes = []
    for relative in sorted(set(before) | set(after)):
        old = digest(before[relative]) if relative in before else None
        new = digest(after[relative]) if relative in after else None
        if old != new:
            changes.append({"path": str(relative), "before": old, "after": new})
    return changes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--r1-evidence", type=Path, required=True)
    parser.add_argument("--r3-evidence", type=Path, required=True)
    parser.add_argument("--r1-build", type=Path, required=True)
    parser.add_argument("--r3-build", type=Path, required=True)
    parser.add_argument("--donor", type=Path, required=True)
    parser.add_argument("--patch", type=Path, required=True)
    parser.add_argument("--candidate-build", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    r1_result = args.r1_evidence / "build-result"
    r3_result = args.r3_evidence / "build-result"
    if "result=SUCCESS" not in (args.r3_evidence / "build.status").read_text():
        raise RuntimeError("r3 build status is not SUCCESS")

    patch_text = args.patch.read_text(encoding="utf-8")
    added_text = "\n".join(
        line[1:] for line in patch_text.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    )
    forbidden = (
        "FEATURE_SDIO_CLOCK          50000000",
        "msleep(", "udelay(", "mdelay(", "schedule_timeout(",
        "wait_for_completion_timeout", "CMD_TX_TIMEOUT", "RWNX_CMD_TIMEOUT_MS",
        "sdio_claim_host", "sdio_release_host", "sdio_writesb", "sdio_readsb",
    )
    for value in forbidden:
        if value in added_text:
            raise RuntimeError(f"trace patch contains forbidden functional/timing delta: {value}")
    if patch_text.count("AIC_STARTAPP_TRACE:") != 1:
        raise RuntimeError("trace patch must contain exactly one compact summary site")

    identical_build_files = [
        "built.config", "preservation.config", "path-a.config",
        "Module.symvers", "aic8800.Module.symvers",
    ]
    build_identity = {}
    for name in identical_build_files:
        before = record(r1_result / name)
        after = record(r3_result / name)
        if before["size"] != after["size"] or before["sha256"] != after["sha256"]:
            raise RuntimeError(f"unexpected build contract drift: {name}")
        build_identity[name] = {"r1": before, "r3": after, "byte_identical": True}
    if normalized_dtb_hashes(r1_result / "dtb-sha256.txt") != normalized_dtb_hashes(
        r3_result / "dtb-sha256.txt"
    ):
        raise RuntimeError("DTB output hashes changed")

    r1_modules = modules(args.r1_build / "modules-install")
    r3_modules = modules(args.r3_build / "modules-install")
    if set(r1_modules) != set(r3_modules) or len(r1_modules) != 22:
        raise RuntimeError("module inventory changed")
    module_audit = {}
    for name in sorted(r1_modules):
        before = record(r1_modules[name])
        after = record(r3_modules[name])
        metadata = {}
        for field in ("name", "depends", "vermagic"):
            old = subprocess.check_output(["modinfo", "-F", field, str(r1_modules[name])], text=True).strip()
            new = subprocess.check_output(["modinfo", "-F", field, str(r3_modules[name])], text=True).strip()
            if old != new:
                raise RuntimeError(f"module metadata changed: {name}/{field}")
            metadata[field] = new
        if metadata["vermagic"] != EXPECTED_RELEASE:
            raise RuntimeError(f"unexpected vermagic: {name}")
        module_audit[name] = {"r1": before, "r3": after, "metadata": metadata}

    bsp_before = r1_modules["aic8800_bsp.ko"]
    bsp_after = r3_modules["aic8800_bsp.ko"]
    if digest(bsp_before) == digest(bsp_after):
        raise RuntimeError("instrumented AIC BSP did not change")
    if symbols(bsp_before, "defined") != symbols(bsp_after, "defined"):
        raise RuntimeError("AIC BSP exported symbol contract changed")
    if symbols(bsp_before, "undefined") != symbols(bsp_after, "undefined"):
        raise RuntimeError("AIC BSP unresolved symbol contract changed")

    donor_root = args.donor / "drivers/net/wireless/aic8800"
    built_root = args.r3_build / "src/drivers/net/wireless/aic8800-accepted"
    changes = source_delta(donor_root, built_root)
    if [item["path"] for item in changes] != EXPECTED_SOURCE_PATHS:
        raise RuntimeError(f"unexpected AIC source delta: {changes}")
    donor_header = (donor_root / "aic8800_bsp/aic_bsp_driver.h").read_text(encoding="utf-8")
    built_header = (built_root / "aic8800_bsp/aic_bsp_driver.h").read_text(encoding="utf-8")
    clock_line = "#define FEATURE_SDIO_CLOCK          70000000"
    if donor_header.count(clock_line) != 1 or built_header.count(clock_line) != 1:
        raise RuntimeError("r3 does not preserve the r1 70 MHz functional source baseline")

    driver = (built_root / "aic8800_bsp/aic_bsp_driver.c").read_text(encoding="utf-8")
    sdio = (built_root / "aic8800_bsp/aicsdio.c").read_text(encoding="utf-8")
    txrx = (built_root / "aic8800_bsp/aic_bsp_txrxif.c").read_text(encoding="utf-8")
    assertions = {
        "single_summary_site": driver.count("AIC_STARTAPP_TRACE:") == 1,
        "runtime_token_capture": driver.count("WRITE_ONCE(trace->token, cmd->tkn)") == 1,
        "startapp_id_gate": driver.count("cmd->id == DBG_START_APP_REQ") >= 1,
        "expected_cfm_gate": driver.count("cmd->reqid == DBG_START_APP_CFM") >= 1,
        "tx_cmd53_return_capture": sdio.count("startapp_trace.tx_cmd53_ret, err") == 1,
        "tx_cmd53_state_gate": sdio.count("startapp_trace.tx_cmd53_state") >= 6,
        "irq_window_counter": sdio.count("startapp_trace.irq_count") == 1,
        "irq_post_return_counter": sdio.count("startapp_trace.irq_after_tx_return_count") == 1,
        "rx_cmd53_return_capture": sdio.count("startapp_trace.rx_cmd53_ret, ret") == 1,
        "rx_post_return_counter": sdio.count("startapp_trace.rx_after_tx_return_count") == 1,
        "rx_header_capture": txrx.count("startapp_trace.rx_msg_id") == 1,
        "cfm_dispatch_capture": driver.count("startapp_trace.cfm_seen") == 1,
        "token_match_capture": driver.count("trace->token_match, 1") == 1,
        "completion_capture": driver.count("trace->completion, 1") == 1,
    }
    if not all(assertions.values()):
        raise RuntimeError(f"trace source assertions failed: {assertions}")

    if args.candidate_build.exists():
        raise RuntimeError(f"refusing to overwrite candidate module root: {args.candidate_build}")
    candidate_modules_root = args.candidate_build / "modules-install"
    shutil.copytree(args.r1_build / "modules-install", candidate_modules_root, symlinks=True)
    candidate_modules = modules(candidate_modules_root)
    shutil.copyfile(bsp_after, candidate_modules["aic8800_bsp.ko"])
    changed_modules = sorted(
        name for name in r1_modules
        if digest(r1_modules[name]) != digest(modules(candidate_modules_root)[name])
    )
    if changed_modules != ["aic8800_bsp.ko"]:
        raise RuntimeError(f"candidate single-module invariant failed: {changed_modules}")

    report = {
        "schema": 1,
        "result": "PASS_STARTAPP_INSTRUMENTATION_ONLY",
        "patch": record(args.patch),
        "source_delta": changes,
        "source_assertions": assertions,
        "r1_sdio_clock_hz_preserved": 70_000_000,
        "dtbs_byte_identical": True,
        "build_identity": build_identity,
        "module_count": len(r3_modules),
        "candidate_changed_modules": changed_modules,
        "candidate_module_root": str(candidate_modules_root),
        "modules": module_audit,
        "aic_bsp_symbol_contract": {
            "exported_symbols_identical": True,
            "undefined_symbols_identical": True,
        },
        "behavioral_changes": [],
        "physical_validation_required": True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"result": report["result"], "candidate_changed_modules": changed_modules}, sort_keys=True))


if __name__ == "__main__":
    main()
