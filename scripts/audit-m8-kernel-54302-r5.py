#!/usr/bin/env python3
"""Audit the r5 FMAC address contract against r4 and the working 5.4.125 BSP."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


REPO = Path(__file__).resolve().parents[1]
R3_AUDIT = REPO / "scripts/audit-m8-kernel-54302-r3.py"
SPEC = importlib.util.spec_from_file_location("m8_kernel_54302_r3_audit", R3_AUDIT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import audit helpers: {R3_AUDIT}")
R3 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = R3
SPEC.loader.exec_module(R3)


FMAC_BASE = 0x00120000
R4_FMAC_BASE = 0x00110000
PATCH_READ_OFFSET = 0x180
DRIVER_RELATIVE = Path("aic8800_bsp/aic_bsp_8800d.c")
FIRMWARE = {
    "fmacfw.bin": (260984, "FC3BC7865CBB01560E706E87FEA23F07CBF86B0E9F76649381D553FE8E781904"),
    "fw_adid_u03.bin": (1208, "6C7CC9D899D2A4E5B91B0F009AA6679498131ADC27D220B96EC162536370A190"),
    "fw_patch_u03.bin": (64204, "4B97D0F7C41F29EDB4B9082F0FB3B920770A8EF9C3F7E8D93C062AEDD9E778CD"),
    "fw_patch_table_u03.bin": (1336, "9EC1A1CC6A6249E3EE8302DC952D71C9F494FEC2A1A16499FFB72893C0A475ED"),
}


def disassembly(module: Path, objdump: Path) -> str:
    return subprocess.check_output(
        [
            str(objdump), "-dr", "--no-show-raw-insn",
            "--disassemble-symbols=aicbsp_8800d_fw_init", str(module),
        ],
        text=True,
    )


def direct_w1_call_values(text: str, callee: str) -> list[int]:
    """Recover direct w1 constants at AArch64 calls from final linked module code."""
    lines = text.splitlines()
    result: list[int] = []
    for call_index, line in enumerate(lines):
        if f"R_AARCH64_CALL26\t{callee}" not in line:
            continue
        start = max(0, call_index - 24)
        instructions = []
        for candidate in lines[start:call_index]:
            match = re.match(r"\s*[0-9a-f]+:\s+(.+)$", candidate)
            if match:
                instructions.append(match.group(1).strip())
        value: int | None = None
        for instruction in instructions:
            match = re.fullmatch(r"mov\s+w1,\s+#(-?\d+)", instruction)
            if match:
                value = int(match.group(1)) & 0xFFFFFFFF
                continue
            match = re.fullmatch(r"movk\s+w1,\s+#(\d+),\s+lsl\s+#(\d+)", instruction)
            if match and value is not None:
                immediate = int(match.group(1))
                shift = int(match.group(2))
                mask = 0xFFFF << shift
                value = (value & ~mask) | (immediate << shift)
                continue
            if re.match(r"(?:mov|add|sub|orr|and|ldr|ldur|csel)\s+w1,", instruction):
                value = None
        if value is not None:
            result.append(value)
    return result


def address_contract(module: Path, objdump: Path, expected_base: int) -> dict[str, object]:
    text = disassembly(module, objdump)
    upload_values = direct_w1_call_values(text, "rwnx_plat_bin_fw_upload_android")
    read_values = direct_w1_call_values(text, "rwnx_send_dbg_mem_read_req")
    start_values = direct_w1_call_values(text, "rwnx_send_dbg_start_app_req")
    expected_read = expected_base + PATCH_READ_OFFSET
    for label, values, expected in (
        ("FMAC upload", upload_values, expected_base),
        ("FMAC patch read", read_values, expected_read),
        ("START_APP", start_values, expected_base),
    ):
        if values.count(expected) != 1:
            raise RuntimeError(f"{label} final-ELF proof failed: expected {expected:#010x}, saw {values}")
    return {
        "module": R3.record(module),
        "aicbsp_8800d_fw_init": {
            "fmac_upload_direct_w1_values": upload_values,
            "patch_read_direct_w1_values": read_values,
            "start_app_direct_w1_values": start_values,
        },
        "proved": {
            "fmac_upload_destination": f"0x{expected_base:08X}",
            "patch_read_address": f"0x{expected_read:08X}",
            "start_app_bootaddr": f"0x{expected_base:08X}",
        },
    }


def firmware_contract(image: Path) -> dict[str, object]:
    result = {}
    with tempfile.TemporaryDirectory(prefix="m8-r5-firmware-") as directory:
        root = Path(directory)
        for name, (expected_size, expected_sha256) in FIRMWARE.items():
            output = root / name
            subprocess.check_call(
                ["debugfs", "-R", f"dump -p /etc/firmware/{name} {output}", str(image)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            actual = R3.record(output)
            if actual["size"] != expected_size or actual["sha256"] != expected_sha256:
                raise RuntimeError(f"firmware identity changed: {name}: {actual}")
            result[name] = {"size": actual["size"], "sha256": actual["sha256"]}
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--r4-evidence", type=Path, required=True)
    parser.add_argument("--r5-evidence", type=Path, required=True)
    parser.add_argument("--r4-build", type=Path, required=True)
    parser.add_argument("--r4-candidate-build", type=Path, required=True)
    parser.add_argument("--r5-build", type=Path, required=True)
    parser.add_argument("--working-bsp", type=Path, required=True)
    parser.add_argument("--contract-patch", type=Path, required=True)
    parser.add_argument("--candidate-build", type=Path, required=True)
    parser.add_argument("--objdump", type=Path, required=True)
    parser.add_argument("--packaged-bsp", type=Path)
    parser.add_argument("--r4-vendor", type=Path)
    parser.add_argument("--packaged-vendor", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    for label, evidence in (("r4", args.r4_evidence), ("r5", args.r5_evidence)):
        if "result=SUCCESS" not in (evidence / "build.status").read_text():
            raise RuntimeError(f"{label} build status is not SUCCESS")

    patch_text = args.contract_patch.read_text(encoding="utf-8")
    added = [
        line[1:] for line in patch_text.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]
    removed = [
        line[1:] for line in patch_text.splitlines()
        if line.startswith("-") and not line.startswith("---")
    ]
    if added != ["#ifdef AICWF_SDIO_SUPPORT"] or removed != ["#ifdef CONFIG_AIC_INTF_SDIO"]:
        raise RuntimeError("r5 contract patch is not the locked one-line guard correction")

    r4_result = args.r4_evidence / "build-result"
    r5_result = args.r5_evidence / "build-result"
    build_identity = {}
    for name in (
        "built.config", "preservation.config", "path-a.config",
        "Module.symvers", "aic8800.Module.symvers",
    ):
        before = R3.record(r4_result / name)
        after = R3.record(r5_result / name)
        if (before["size"], before["sha256"]) != (after["size"], after["sha256"]):
            raise RuntimeError(f"unexpected r4-to-r5 build drift: {name}")
        build_identity[name] = {"r4": before, "r5": after, "byte_identical": True}
    if R3.normalized_dtb_hashes(r4_result / "dtb-sha256.txt") != R3.normalized_dtb_hashes(
        r5_result / "dtb-sha256.txt"
    ):
        raise RuntimeError("normalized DTB output hashes changed")

    r4_modules = R3.modules(args.r4_candidate_build / "modules-install")
    r5_raw_modules = R3.modules(args.r5_build / "modules-install")
    if set(r4_modules) != set(r5_raw_modules) or len(r5_raw_modules) != 22:
        raise RuntimeError("module inventory changed")
    bsp_r4 = r4_modules["aic8800_bsp.ko"]
    bsp_r5 = r5_raw_modules["aic8800_bsp.ko"]
    for name in sorted(r4_modules):
        for field in ("name", "depends", "vermagic"):
            before = subprocess.check_output(
                ["modinfo", "-F", field, str(r4_modules[name])], text=True
            ).strip()
            after = subprocess.check_output(
                ["modinfo", "-F", field, str(r5_raw_modules[name])], text=True
            ).strip()
            if before != after:
                raise RuntimeError(f"module metadata changed: {name}/{field}")
        vermagic = subprocess.check_output(
            ["modinfo", "-F", "vermagic", str(r5_raw_modules[name])], text=True
        ).strip()
        if vermagic != R3.EXPECTED_RELEASE:
            raise RuntimeError(f"unexpected vermagic: {name}")
    if R3.symbols(bsp_r4, "defined") != R3.symbols(bsp_r5, "defined"):
        raise RuntimeError("AIC BSP exported symbol contract changed")
    if R3.symbols(bsp_r4, "undefined") != R3.symbols(bsp_r5, "undefined"):
        raise RuntimeError("AIC BSP import contract changed")

    r4_root = args.r4_build / "src/drivers/net/wireless/aic8800-accepted"
    r5_root = args.r5_build / "src/drivers/net/wireless/aic8800-accepted"
    source_changes = R3.source_delta(r4_root, r5_root)
    if [item["path"] for item in source_changes] != [str(DRIVER_RELATIVE)]:
        raise RuntimeError(f"unexpected r4-to-r5 source delta: {source_changes}")
    r4_driver = (r4_root / DRIVER_RELATIVE).read_text(encoding="utf-8")
    r5_driver = (r5_root / DRIVER_RELATIVE).read_text(encoding="utf-8")
    if r4_driver.count("#ifdef CONFIG_AIC_INTF_SDIO") != 1:
        raise RuntimeError("r4 source no longer has the expected broken guard")
    expected_r5_driver = r4_driver.replace(
        "#ifdef CONFIG_AIC_INTF_SDIO", "#ifdef AICWF_SDIO_SUPPORT", 1
    )
    if r5_driver != expected_r5_driver:
        raise RuntimeError("r5 source contains more than the locked guard correction")
    if r5_driver.count("RAM_FMAC_FW_ADDR") != 5:
        raise RuntimeError("unexpected RAM_FMAC_FW_ADDR use count")
    header = (r5_root / "aic8800_bsp/aic_bsp_driver.h").read_text(encoding="utf-8")
    if header.count("#define FEATURE_SDIO_CLOCK          70000000") != 1:
        raise RuntimeError("r5 does not preserve the r4 70 MHz request")

    r4_contract = address_contract(bsp_r4, args.objdump, R4_FMAC_BASE)
    r5_contract = address_contract(bsp_r5, args.objdump, FMAC_BASE)
    working_contract = address_contract(args.working_bsp, args.objdump, FMAC_BASE)
    r5_disassembly = disassembly(bsp_r5, args.objdump)
    for forbidden in (R4_FMAC_BASE, R4_FMAC_BASE + PATCH_READ_OFFSET):
        values = []
        for callee in (
            "rwnx_plat_bin_fw_upload_android",
            "rwnx_send_dbg_mem_read_req",
            "rwnx_send_dbg_start_app_req",
        ):
            values.extend(direct_w1_call_values(r5_disassembly, callee))
        if forbidden in values:
            raise RuntimeError(f"r5 final ELF retains forbidden old contract value {forbidden:#x}")
    module_strings = subprocess.check_output(["strings", str(bsp_r5)], text=True)
    for trace_fragment in ("AIC_STARTAPP_TRACE:", "cccr_intx=0x%02x", "cccr_ienx=0x%02x"):
        if trace_fragment not in module_strings:
            raise RuntimeError(f"r4 diagnostic trace missing from r5 module: {trace_fragment}")

    candidate_modules_root = args.candidate_build / "modules-install"
    if not args.candidate_build.exists():
        shutil.copytree(args.r4_candidate_build / "modules-install", candidate_modules_root, symlinks=True)
        candidate_modules = R3.modules(candidate_modules_root)
        shutil.copyfile(bsp_r5, candidate_modules["aic8800_bsp.ko"])
    candidate_modules = R3.modules(candidate_modules_root)
    if R3.digest(candidate_modules["aic8800_bsp.ko"]) != R3.digest(bsp_r5):
        raise RuntimeError("candidate module root does not contain the audited r5 BSP")
    candidate_changes = sorted(
        name for name in r4_modules
        if R3.digest(r4_modules[name]) != R3.digest(candidate_modules[name])
    )
    if candidate_changes != ["aic8800_bsp.ko"]:
        raise RuntimeError(f"candidate single-module invariant failed: {candidate_changes}")
    packaged_contract = None
    if args.packaged_bsp is not None:
        if R3.digest(args.packaged_bsp) != R3.digest(bsp_r5):
            raise RuntimeError("packaged BSP differs from the final audited build module")
        packaged_contract = address_contract(args.packaged_bsp, args.objdump, FMAC_BASE)
    firmware_audit = None
    if (args.r4_vendor is None) != (args.packaged_vendor is None):
        raise RuntimeError("r4 and packaged vendor images must be supplied together")
    if args.r4_vendor is not None and args.packaged_vendor is not None:
        if R3.digest(args.r4_vendor) != R3.digest(args.packaged_vendor):
            raise RuntimeError("packaged vendor image differs from r4")
        r4_firmware = firmware_contract(args.r4_vendor)
        packaged_firmware = firmware_contract(args.packaged_vendor)
        if r4_firmware != packaged_firmware:
            raise RuntimeError("packaged firmware differs from r4")
        firmware_audit = {
            "r4_vendor": R3.record(args.r4_vendor),
            "packaged_vendor": R3.record(args.packaged_vendor),
            "vendor_byte_identical": True,
            "exact_firmware_byte_identical": True,
            "files": packaged_firmware,
        }
    module_audit = {}
    for name in sorted(r4_modules):
        metadata = {
            field: subprocess.check_output(
                ["modinfo", "-F", field, str(candidate_modules[name])], text=True
            ).strip()
            for field in ("name", "depends", "vermagic")
        }
        module_audit[name] = {
            "r4": R3.record(r4_modules[name]),
            "r5_candidate": R3.record(candidate_modules[name]),
            "metadata": metadata,
            "byte_identical": R3.digest(r4_modules[name]) == R3.digest(candidate_modules[name]),
        }

    report = {
        "schema": 1,
        "result": "PASS_R5_FMAC_ADDRESS_CONTRACT_ONLY",
        "contract_patch": R3.record(args.contract_patch),
        "r4_to_r5_source_delta": source_changes,
        "source_change": "RAM_FMAC_FW_ADDR guard: CONFIG_AIC_INTF_SDIO -> AICWF_SDIO_SUPPORT",
        "final_elf_address_contract": {
            "r4": r4_contract,
            "r5": r5_contract,
            "accepted_working_5_4_125": working_contract,
            "r5_matches_working_contract": True,
            "r5_differs_from_r4_only_at_address_contract": True,
            "packaged_r5": packaged_contract,
        },
        "firmware_preservation": firmware_audit,
        "r4_trace_and_timeout_cccr_instrumentation_present": True,
        "r4_sdio_clock_hz_preserved": 70_000_000,
        "dtbs_byte_identical": True,
        "build_identity": build_identity,
        "raw_build_image": {
            "r4": R3.record(r4_result / "Image"),
            "r5": R3.record(r5_result / "Image"),
            "used_in_candidate": False,
            "reason": "clean ThinLTO output is build-path-dependent; candidate reuses the exact r4/r1 Image",
        },
        "module_count": len(candidate_modules),
        "r4_to_r5_changed_modules": candidate_changes,
        "other_21_modules_byte_identical": True,
        "candidate_module_root": str(candidate_modules_root),
        "modules": module_audit,
        "aic_bsp_abi": {
            "exported_symbols_identical_to_r4": True,
            "imports_identical_to_r4": True,
            "module_export_crcs_byte_identical_to_r4": True,
            "vermagic": R3.EXPECTED_RELEASE,
        },
        "physical_validation_required": True,
        "physical_device_actions_performed": False,
        "gate2": "CLOSED",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "result": report["result"],
        "changed_modules": candidate_changes,
        "r5_contract": r5_contract["proved"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
