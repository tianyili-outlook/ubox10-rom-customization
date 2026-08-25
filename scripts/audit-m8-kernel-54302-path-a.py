#!/usr/bin/env python3
"""Prove the retained r5 hardware/FMAC contract in a Path-A kernel build."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys


REPO = Path(__file__).resolve().parents[1]
R5_PATH = REPO / "scripts/audit-m8-kernel-54302-r5.py"
SPEC = importlib.util.spec_from_file_location("m8_kernel_54302_r5_audit", R5_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import r5 audit helpers: {R5_PATH}")
R5 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = R5
SPEC.loader.exec_module(R5)

EXPECTED_PATCHES = {
    "aic8800d-startapp-trace.patch":
        "B65CC9940302D8F204012B7365EC1437B48A3AA6C7A7E772E4F0A57E266EFFE4",
    "aic8800d-startapp-timeout-cccr.patch":
        "2E338EF6F8003F0CFD5F504039D0350263DB8AD0103758EE01D76400A195F251",
    "aic8800d-fmac-address-contract.patch":
        "10BE1AE58CB900DBD8B5250960B2FBA3846CC29DFFF676DAE5D87D17EBCADBD3",
}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest().upper()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-root", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--objdump", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = args.evidence_dir / "build-result"
    config = result / "built.config"
    source = args.build_root / "src"
    module_paths = list(
        (args.build_root / "modules-install/lib/modules/5.4.302+").rglob("aic8800_bsp.ko")
    )
    if len(module_paths) != 1:
        raise RuntimeError(f"ambiguous Path-A AIC BSP module: {module_paths}")
    module = module_paths[0]

    patches = {}
    for name, expected in EXPECTED_PATCHES.items():
        path = REPO / "configs/kernel/m8-kernel-5.4.302" / name
        actual = digest(path)
        if actual != expected:
            raise RuntimeError(f"retained r5 patch identity changed: {name}: {actual}")
        patches[name] = actual

    values = {}
    for line in config.read_text().splitlines():
        if line.startswith("CONFIG_") and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
        elif line.startswith("# CONFIG_") and line.endswith(" is not set"):
            values[line[2:-11]] = "n"
    required = {
        "CONFIG_BLK_CGROUP": "y", "CONFIG_CPUSETS": "y",
        "CONFIG_PROC_PID_CPUSET": "y", "CONFIG_NET_CLS_MATCHALL": "y",
        "CONFIG_NET_ACT_POLICE": "y", "CONFIG_NET_ACT_BPF": "y",
        "CONFIG_MEMCG": "n", "CONFIG_DEBUG_INFO_BTF": "n",
        "CONFIG_INCFS_FS": "n",
    }
    mismatches = {
        key: {"expected": expected, "actual": values.get(key, "n")}
        for key, expected in required.items() if values.get(key, "n") != expected
    }
    if mismatches:
        raise RuntimeError(f"Path-A bounded config contract changed: {mismatches}")

    driver = (
        source / "drivers/net/wireless/aic8800-accepted/"
        "aic8800_bsp/aic_bsp_8800d.c"
    )
    driver_text = driver.read_text(encoding="utf-8", errors="replace")
    driver_header = driver.with_name("aic_bsp_driver.h").read_text(
        encoding="utf-8", errors="replace"
    )
    if "#define FEATURE_SDIO_CLOCK          70000000" not in driver_header:
        raise RuntimeError("accepted 70 MHz AIC source contract changed")
    if "#ifdef AICWF_SDIO_SUPPORT" not in driver_text:
        raise RuntimeError("r5 FMAC address guard correction is absent")
    strings = subprocess.check_output(["strings", str(module)], text=True)
    for marker in ("AIC_STARTAPP_TRACE:", "cccr_intx=0x%02x"):
        if marker not in strings:
            raise RuntimeError(f"retained r5 diagnostic marker missing: {marker}")

    # The build operates on a private source copy. Prove it did not touch the
    # generic MMC/SDIO implementation or DT/firmware authority while applying
    # the tracked RC/AIC deltas.
    for path in (
        "drivers/mmc", "arch/arm64/boot/dts/sunxi",
        "drivers/net/wireless/aic8800/aic8800_fdrv",
    ):
        changed = subprocess.check_output(
            ["git", "-C", str(source), "diff", "--name-only", "HEAD", "--", path],
            text=True,
        ).splitlines()
        if changed:
            raise RuntimeError(f"protected kernel subtree changed: {path}: {changed}")

    addresses = R5.address_contract(module, args.objdump, R5.FMAC_BASE)
    report = {
        "schema": 1,
        "result": "PASS_PATH_A_R5_HARDWARE_AND_FMAC_CONTRACT",
        "kernel_release": "5.4.302+",
        "config_sha256": digest(config),
        "bounded_path_a_config": required,
        "patches": patches,
        "aic_sdio_clock_hz": 70000000,
        "fmac": addresses,
        "retained_trace_and_cccr_markers": True,
        "generic_mmc_sdio_unchanged": True,
        "dt_authority_unchanged": True,
        "aic_fdrv_firmware_authority_unchanged": True,
        "physical_device_actions_performed": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(report["result"])


if __name__ == "__main__":
    main()
