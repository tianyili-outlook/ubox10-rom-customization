#!/usr/bin/env python3
"""Audit the r2 AIC8800D 50 MHz module build against accepted r1."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess


CHUNK = 8 * 1024 * 1024
EXPECTED_PATCH_SHA256 = "ED64ADF7943592281359667FA3CB8E27446FCE6F15AB4711CEC6A30847CC06A5"
EXPECTED_RELEASE = "5.4.302+ SMP preempt mod_unload modversions aarch64"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(CHUNK), b""):
            value.update(block)
    return value.hexdigest().upper()


def record(path: Path) -> dict[str, object]:
    return {"path": str(path), "size": path.stat().st_size, "sha256": digest(path)}


def modules(root: Path) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for path in root.rglob("*.ko"):
        if path.name in paths:
            raise RuntimeError(f"duplicate module basename: {path.name}")
        paths[path.name] = path
    return paths


def command(*args: str) -> list[str]:
    return subprocess.check_output(args, text=True).splitlines()


def symbols(path: Path, mode: str) -> list[str]:
    args = ["nm"]
    if mode == "defined":
        args.extend(["-g", "--defined-only"])
    else:
        args.append("-u")
    args.append(str(path))
    values = []
    for line in command(*args):
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


def donor_delta(donor: Path, built: Path) -> list[dict[str, str | None]]:
    left = {path.relative_to(donor): path for path in donor.rglob("*") if path.is_file()}
    right = {path.relative_to(built): path for path in built.rglob("*") if path.is_file()}
    changes = []
    for relative in sorted(set(left) | set(right)):
        before = digest(left[relative]) if relative in left else None
        after = digest(right[relative]) if relative in right else None
        if before != after:
            changes.append({"path": str(relative), "before": before, "after": after})
    return changes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--r1-evidence", type=Path, required=True)
    parser.add_argument("--r2-evidence", type=Path, required=True)
    parser.add_argument("--r1-build", type=Path, required=True)
    parser.add_argument("--r2-build", type=Path, required=True)
    parser.add_argument("--donor", type=Path, required=True)
    parser.add_argument("--patch", type=Path, required=True)
    parser.add_argument("--candidate-build", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    r1_result = args.r1_evidence / "build-result"
    r2_result = args.r2_evidence / "build-result"
    if "result=SUCCESS" not in (args.r2_evidence / "build.status").read_text():
        raise RuntimeError("r2 build status is not SUCCESS")
    if digest(args.patch) != EXPECTED_PATCH_SHA256:
        raise RuntimeError("r2 compatibility patch identity changed")

    identical_build_files = [
        "built.config", "preservation.config", "path-a.config",
        "Module.symvers", "aic8800.Module.symvers",
    ]
    build_identity = {}
    for name in identical_build_files:
        before = record(r1_result / name)
        after = record(r2_result / name)
        if before["sha256"] != after["sha256"] or before["size"] != after["size"]:
            raise RuntimeError(f"unexpected build drift: {name}")
        build_identity[name] = {"r1": before, "r2": after, "byte_identical": True}
    if normalized_dtb_hashes(r1_result / "dtb-sha256.txt") != normalized_dtb_hashes(r2_result / "dtb-sha256.txt"):
        raise RuntimeError("DTB output hashes changed")

    r1_modules = modules(args.r1_build / "modules-install")
    r2_modules = modules(args.r2_build / "modules-install")
    if set(r1_modules) != set(r2_modules) or len(r1_modules) != 22:
        raise RuntimeError("module inventory changed")
    clean_rebuild_changed_modules = []
    module_audit = {}
    for name in sorted(r1_modules):
        before = record(r1_modules[name])
        after = record(r2_modules[name])
        changed = before["sha256"] != after["sha256"]
        if changed:
            clean_rebuild_changed_modules.append(name)
        metadata = {}
        for field in ("name", "depends", "vermagic"):
            r1_value = subprocess.check_output(["modinfo", "-F", field, str(r1_modules[name])], text=True).strip()
            r2_value = subprocess.check_output(["modinfo", "-F", field, str(r2_modules[name])], text=True).strip()
            if r1_value != r2_value:
                raise RuntimeError(f"module metadata changed: {name}/{field}")
            metadata[field] = r2_value
        if metadata["vermagic"] != EXPECTED_RELEASE:
            raise RuntimeError(f"unexpected vermagic: {name}")
        module_audit[name] = {"r1": before, "r2": after, "changed": changed, "metadata": metadata}
    if "aic8800_bsp.ko" not in clean_rebuild_changed_modules:
        raise RuntimeError("rebuilt AIC BSP did not change")

    bsp_before = r1_modules["aic8800_bsp.ko"]
    bsp_after = r2_modules["aic8800_bsp.ko"]
    exported_before = symbols(bsp_before, "defined")
    exported_after = symbols(bsp_after, "defined")
    undefined_before = symbols(bsp_before, "undefined")
    undefined_after = symbols(bsp_after, "undefined")
    if exported_before != exported_after or undefined_before != undefined_after:
        raise RuntimeError("AIC BSP ELF symbol contract changed")

    donor_root = args.donor / "drivers/net/wireless/aic8800"
    built_root = args.r2_build / "src/drivers/net/wireless/aic8800-accepted"
    source_delta = donor_delta(donor_root, built_root)
    expected_path = "aic8800_bsp/aic_bsp_driver.h"
    if [item["path"] for item in source_delta] != [expected_path]:
        raise RuntimeError(f"AIC donor source delta is not one file: {source_delta}")
    before_text = (donor_root / expected_path).read_text(encoding="utf-8")
    after_text = (built_root / expected_path).read_text(encoding="utf-8")
    if before_text.count("FEATURE_SDIO_CLOCK          70000000") != 1:
        raise RuntimeError("donor 70 MHz source point not unique")
    if after_text.count("FEATURE_SDIO_CLOCK          50000000") != 1:
        raise RuntimeError("r2 50 MHz source point not unique")
    if after_text != before_text.replace(
        "FEATURE_SDIO_CLOCK          70000000",
        "FEATURE_SDIO_CLOCK          50000000",
        1,
    ):
        raise RuntimeError("AIC source has changes beyond the clock constant")

    aicsdio = (built_root / "aic8800_bsp/aicsdio.c").read_text(encoding="utf-8")
    if aicsdio.count("host->ios.clock = feature.sdio_clock;") != 1:
        raise RuntimeError("unexpected BSP SDIO clock assignment count")
    if aicsdio.count("host->ops->set_ios(host, &host->ios);") != 1:
        raise RuntimeError("unexpected BSP set_ios call count")

    if args.candidate_build.exists():
        raise RuntimeError(f"refusing to overwrite candidate module root: {args.candidate_build}")
    candidate_modules_root = args.candidate_build / "modules-install"
    shutil.copytree(args.r1_build / "modules-install", candidate_modules_root, symlinks=True)
    candidate_modules = modules(candidate_modules_root)
    shutil.copyfile(bsp_after, candidate_modules["aic8800_bsp.ko"])
    candidate_modules = modules(candidate_modules_root)
    candidate_changed_modules = sorted(
        name for name in r1_modules
        if digest(r1_modules[name]) != digest(candidate_modules[name])
    )
    if candidate_changed_modules != ["aic8800_bsp.ko"]:
        raise RuntimeError(f"candidate single-module invariant failed: {candidate_changed_modules}")

    image_before = record(r1_result / "Image")
    image_rebuild = record(r2_result / "Image")
    if image_before["size"] != image_rebuild["size"]:
        raise RuntimeError("clean rebuild Image size changed")

    report = {
        "schema": 1,
        "result": "PASS_SINGLE_VARIABLE_OFFLINE",
        "experiment": "AIC8800D runtime SDIO clock request 70 MHz to 50 MHz",
        "patch": record(args.patch),
        "build_identity": build_identity,
        "clean_rebuild_image": {
            "r1": image_before,
            "r2": image_rebuild,
            "byte_identical": image_before["sha256"] == image_rebuild["sha256"],
            "candidate_reuses_r1_image": True,
            "difference_classification": "absolute source path and ThinLTO private-symbol identity; config and Module.symvers are byte-identical",
        },
        "dtbs_byte_identical": True,
        "module_count": len(r2_modules),
        "clean_rebuild_changed_modules": clean_rebuild_changed_modules,
        "candidate_module_root": str(candidate_modules_root),
        "candidate_changed_modules": candidate_changed_modules,
        "modules": module_audit,
        "aic_bsp_symbol_contract": {
            "exported_symbols_identical": True,
            "undefined_symbols_identical": True,
            "exported_count": len(exported_after),
            "undefined_count": len(undefined_after),
        },
        "aic_donor_source_delta": source_delta,
        "source_assertions": {
            "donor_feature_sdio_clock_hz": 70000000,
            "r2_feature_sdio_clock_hz": 50000000,
            "bsp_direct_ios_assignment_count": 1,
            "bsp_direct_host_set_ios_count": 1,
        },
        "physical_validation_required": True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"result": report["result"], "candidate_changed_modules": candidate_changed_modules}, sort_keys=True))


if __name__ == "__main__":
    main()
