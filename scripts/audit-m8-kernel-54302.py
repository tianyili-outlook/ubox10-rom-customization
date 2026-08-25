#!/usr/bin/env python3
"""Audit the UBOX10 H616 Linux 5.4.302 preservation build."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


CRITICAL_SUBTREES = (
    "arch/arm64/boot/dts/sunxi",
    "drivers/char/sunxi-di",
    "drivers/char/sunxi-gralloc",
    "drivers/char/sunxi_g2d",
    "drivers/media/cedar-ve",
    "drivers/media/platform/sunxi-vin",
    "drivers/net/wireless/aic8800",
    "drivers/sunxi_drm_heap",
    "drivers/usb/sunxi_usb",
    "drivers/video/fbdev/sunxi",
    "modules/gpu/mali-bifrost",
)

REQUIRED_CONFIG = {
    "CONFIG_64BIT": "y",
    "CONFIG_AIC8800_BTLPM_SUPPORT": "m",
    "CONFIG_AIC8800_WLAN_SUPPORT": "m",
    "CONFIG_AIC_WLAN_SUPPORT": "y",
    "CONFIG_ARCH_SUN50IW9": "y",
    "CONFIG_ARCH_SUNXI": "y",
    "CONFIG_ARM64": "y",
    "CONFIG_ARM64_CRC32": "n",
    "CONFIG_BLK_DEV_DM": "y",
    "CONFIG_BPF": "y",
    "CONFIG_BPF_SYSCALL": "y",
    "CONFIG_CGROUPS": "y",
    "CONFIG_CGROUP_BPF": "y",
    "CONFIG_CGROUP_CPUACCT": "y",
    "CONFIG_CGROUP_FREEZER": "y",
    "CONFIG_CGROUP_SCHED": "y",
    "CONFIG_CPU_FREQ": "y",
    "CONFIG_DISP2_SUNXI": "y",
    "CONFIG_DM_CRYPT": "y",
    "CONFIG_DM_VERITY": "y",
    "CONFIG_DRM": "y",
    "CONFIG_HDMI2_DISP2_SUNXI": "y",
    "CONFIG_ION": "y",
    "CONFIG_MODULES": "y",
    "CONFIG_MODVERSIONS": "y",
    "CONFIG_OPTEE": "y",
    "CONFIG_PM_WAKELOCKS": "y",
    "CONFIG_RC_CORE": "y",
    "CONFIG_SND_SOC_SUNXI_AAUDIO": "y",
    "CONFIG_SND_SOC_SUNXI_HDMIAUDIO": "y",
    "CONFIG_SND_SOC_SUNXI_INTERNALCODEC": "y",
    "CONFIG_SND_SOC_SUNXI_SUN50IW9_CODEC": "y",
    "CONFIG_SUNXI_DRM_HEAP": "y",
    "CONFIG_SUNXI_EPHY": "y",
    "CONFIG_SUNXI_G2D": "y",
    "CONFIG_SUNXI_GMAC": "y",
    "CONFIG_SUNXI_GPU_TYPE": '"mali-g31"',
    "CONFIG_SUNXI_MULTI_IR_SUPPORT": "n",
    "CONFIG_SUNXI_SOC_NAME": '"sun50iw9"',
    "CONFIG_SUNXI_THERMAL": "y",
    "CONFIG_SUSPEND": "y",
    "CONFIG_TEE": "y",
    "CONFIG_THERMAL": "y",
    "CONFIG_USB_SUNXI_HCI": "m",
    "CONFIG_VIDEO_ENCODER_DECODER_SUNXI": "y",
}

PATH_A_CONFIG = {
    "CONFIG_BLK_CGROUP": "y",
    "CONFIG_CPUSETS": "y",
    "CONFIG_PROC_PID_CPUSET": "y",
    "CONFIG_NET_CLS_MATCHALL": "y",
    "CONFIG_NET_ACT_POLICE": "y",
    "CONFIG_NET_ACT_BPF": "y",
}

XR819_DONOR_SUBTREE = "e5d1a2df874a1f81f810b443f73709c9559ec07c"
AIC8800_DONOR_SUBTREE = "70c98140316f7ed23af879bb0e3d881883f5e978"
ACCEPTED_RTLWIFI_SUBTREE = "8d1d70eaacbb82e599e3db228045f86a1c4d05a8"

MODULE_METADATA_FIELDS = ("name", "depends", "alias", "firmware", "version", "license")


def run(*command: str) -> str:
    return subprocess.check_output(command, text=True, stderr=subprocess.STDOUT)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def config_values(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if line.startswith("CONFIG_") and "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
        elif line.startswith("# CONFIG_") and line.endswith(" is not set"):
            result[line[2:-11]] = "n"
    return result


def module_field(path: Path, field: str) -> list[str]:
    return run("modinfo", "-F", field, str(path)).splitlines()


def module_symbols(path: Path, flag: str) -> dict[str, str]:
    result: dict[str, str] = {}
    completed = subprocess.run(
        ("modprobe", flag, str(path)),
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if completed.returncode:
        if "No data available" in completed.stdout:
            return result
        raise subprocess.CalledProcessError(
            completed.returncode, completed.args, output=completed.stdout
        )
    for line in completed.stdout.splitlines():
        crc, symbol = line.split(None, 1)
        result[symbol] = crc.lower()
    return result


def clean_git(repo: Path) -> bool:
    return not run("git", "-C", str(repo), "status", "--porcelain").strip()


def ext4_geometry(path: Path) -> dict[str, int]:
    output = run("dumpe2fs", "-h", str(path))
    fields = {}
    wanted = {
        "Block count": "block_count",
        "Free blocks": "free_blocks",
        "Block size": "block_size",
    }
    for line in output.splitlines():
        if ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        if key in wanted:
            fields[wanted[key]] = int(value)
    if set(fields) != set(wanted.values()):
        raise SystemExit(f"could not parse ext4 geometry for {path}: {fields}")
    return fields


def git_object(repo: Path, commit: str, path: str) -> str:
    return run("git", "-C", str(repo), "rev-parse", f"{commit}:{path}").strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--integration-repo", type=Path, required=True)
    parser.add_argument("--integration-commit", required=True)
    parser.add_argument("--vendor-repo", type=Path, required=True)
    parser.add_argument("--vendor-commit", required=True)
    parser.add_argument("--xr819-donor-repo", type=Path, required=True)
    parser.add_argument("--xr819-donor-commit", required=True)
    parser.add_argument("--aic8800-donor-repo", type=Path, required=True)
    parser.add_argument("--aic8800-donor-commit", required=True)
    parser.add_argument("--build-root", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--accepted-modules", type=Path, required=True)
    parser.add_argument("--accepted-vendor-dlkm", type=Path, required=True)
    parser.add_argument(
        "--built-config", choices=("preservation", "path-a"), default="preservation"
    )
    parser.add_argument("--build-log", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result_dir = args.evidence_dir / "build-result"
    build_status = dict(
        line.split("=", 1)
        for line in (args.evidence_dir / "build.status").read_text().splitlines()
        if "=" in line
    )
    if build_status.get("result") != "SUCCESS":
        raise SystemExit(f"build is not successful: {build_status}")

    integration_head = run(
        "git", "-C", str(args.integration_repo), "rev-parse", args.integration_commit
    ).strip()
    integration_tree = run(
        "git", "-C", str(args.integration_repo), "rev-parse", f"{args.integration_commit}^{{tree}}"
    ).strip()
    vendor_tree = run(
        "git", "-C", str(args.vendor_repo), "rev-parse", f"{args.vendor_commit}^{{tree}}"
    ).strip()
    if integration_head != args.integration_commit:
        raise SystemExit("integration commit identity mismatch")
    if not clean_git(args.integration_repo):
        raise SystemExit("integration source repository is not clean")
    if not clean_git(args.vendor_repo):
        raise SystemExit("vendor source repository is not clean")

    donor_report = {}
    for label, repo, commit, source_path, expected_subtree in (
        (
            "xr819",
            args.xr819_donor_repo,
            args.xr819_donor_commit,
            "kernel/linux-5.4/drivers/net/wireless/xr819",
            XR819_DONOR_SUBTREE,
        ),
        (
            "aic8800",
            args.aic8800_donor_repo,
            args.aic8800_donor_commit,
            "drivers/net/wireless/aic8800",
            AIC8800_DONOR_SUBTREE,
        ),
    ):
        head = run("git", "-C", str(repo), "rev-parse", "HEAD").strip()
        subtree = git_object(repo, commit, source_path)
        donor_report[label] = {
            "repository": str(repo),
            "commit": head,
            "source_path": source_path,
            "subtree": subtree,
        }
        if head != commit or subtree != expected_subtree or not clean_git(repo):
            raise SystemExit(f"{label} donor identity/cleanliness mismatch: {donor_report[label]}")

    rtlwifi_subtree = git_object(
        args.vendor_repo, args.vendor_commit, "drivers/net/wireless/realtek/rtlwifi"
    )
    if rtlwifi_subtree != ACCEPTED_RTLWIFI_SUBTREE:
        raise SystemExit(f"accepted rtlwifi subtree mismatch: {rtlwifi_subtree}")

    subtree_report = {}
    for path in CRITICAL_SUBTREES:
        before = git_object(args.vendor_repo, args.vendor_commit, path)
        after = git_object(args.integration_repo, args.integration_commit, path)
        subtree_report[path] = {
            "vendor_object": before,
            "integration_object": after,
            "byte_preserved": before == after,
        }
        if before != after:
            raise SystemExit(f"critical BSP subtree changed: {path}")

    image = result_dir / "Image"
    built_config = result_dir / "built.config"
    image_config = result_dir / "image-extracted.config"
    if built_config.read_bytes() != image_config.read_bytes():
        raise SystemExit("embedded Image configuration differs from build configuration")
    selected_config = result_dir / (
        "path-a.config" if args.built_config == "path-a" else "preservation.config"
    )
    if built_config.read_bytes() != selected_config.read_bytes():
        raise SystemExit(
            f"built Image configuration is not the selected {args.built_config} contract"
        )
    with image.open("rb") as stream:
        stream.seek(56)
        image_magic = stream.read(4)
    if image_magic != b"ARMd":
        raise SystemExit("built Image lacks ARM64 Image magic")

    values = config_values(built_config)
    config_mismatches = {
        key: {"expected": expected, "actual": values.get(key, "n")}
        for key, expected in REQUIRED_CONFIG.items()
        if values.get(key, "n") != expected
    }
    if config_mismatches:
        raise SystemExit(f"hardware config contract mismatch: {config_mismatches}")
    path_a_values = config_values(result_dir / "path-a.config")
    path_a_mismatches = {
        key: {"expected": expected, "actual": path_a_values.get(key, "n")}
        for key, expected in PATH_A_CONFIG.items()
        if path_a_values.get(key, "n") != expected
    }
    if path_a_mismatches:
        raise SystemExit(f"Path-A config contract mismatch: {path_a_mismatches}")

    old_modules = {path.name: path for path in args.accepted_modules.glob("*.ko")}
    release_dirs = sorted((args.build_root / "modules-install/lib/modules").glob("*"))
    if len(release_dirs) != 1:
        raise SystemExit(f"expected one installed kernel release, got {release_dirs}")
    new_modules = {path.name: path for path in release_dirs[0].rglob("*.ko")}
    if set(old_modules) != set(new_modules):
        raise SystemExit(
            "module inventory changed: "
            f"missing={sorted(set(old_modules) - set(new_modules))}, "
            f"added={sorted(set(new_modules) - set(old_modules))}"
        )

    symvers: dict[str, str] = {}
    symvers_sources = [result_dir / "Module.symvers", *sorted(result_dir.glob("*.Module.symvers"))]
    duplicate_crc_conflicts = {}
    superseded_main_symvers = []
    for path in symvers_sources:
        if not path.is_file():
            raise SystemExit(f"missing symbol-version evidence: {path}")
        for line in path.read_text(errors="replace").splitlines():
            fields = line.split()
            if len(fields) < 2:
                continue
            if (
                path.name == "Module.symvers"
                and len(fields) >= 3
                and fields[2].startswith("drivers/net/wireless/aic8800/")
            ):
                superseded_main_symvers.append(fields[1])
                continue
            crc, symbol = fields[0].lower(), fields[1]
            if symbol in symvers and symvers[symbol] != crc:
                duplicate_crc_conflicts[symbol] = [symvers[symbol], crc]
            symvers[symbol] = crc
    if duplicate_crc_conflicts:
        raise SystemExit(f"conflicting provider CRCs: {duplicate_crc_conflicts}")

    module_report = {}
    all_import_mismatches = []
    dependency_changes = []
    alias_changes = []
    export_changes = []
    name_changes = []
    firmware_changes = []
    version_changes = []
    old_allocated_blocks = 0
    new_allocated_blocks = 0
    for name in sorted(old_modules):
        old = old_modules[name]
        new = new_modules[name]
        old_metadata = {field: sorted(module_field(old, field)) for field in MODULE_METADATA_FIELDS}
        new_metadata = {field: sorted(module_field(new, field)) for field in MODULE_METADATA_FIELDS}
        old_depends = sorted(
            filter(None, (old_metadata["depends"][:1] or [""])[0].split(","))
        )
        new_depends = sorted(
            filter(None, (new_metadata["depends"][:1] or [""])[0].split(","))
        )
        old_alias = old_metadata["alias"]
        new_alias = new_metadata["alias"]
        if old_depends != new_depends:
            dependency_changes.append(name)
        if old_alias != new_alias:
            alias_changes.append(name)
        if old_metadata["name"] != new_metadata["name"]:
            name_changes.append(name)
        if old_metadata["firmware"] != new_metadata["firmware"]:
            firmware_changes.append(name)
        if old_metadata["version"] != new_metadata["version"]:
            version_changes.append(name)
        old_exports = module_symbols(old, "--show-exports")
        new_exports = module_symbols(new, "--show-exports")
        if set(old_exports) != set(new_exports):
            export_changes.append(name)
        new_imports = module_symbols(new, "--show-modversions")
        import_mismatches = {
            symbol: {"module_crc": crc, "provider_crc": symvers.get(symbol)}
            for symbol, crc in new_imports.items()
            if symvers.get(symbol) != crc
        }
        all_import_mismatches.extend(f"{name}:{symbol}" for symbol in import_mismatches)
        old_imports = set(module_symbols(old, "--show-modversions"))
        old_blocks = old.stat().st_blocks // 8
        new_blocks = new.stat().st_blocks // 8
        old_allocated_blocks += old_blocks
        new_allocated_blocks += new_blocks
        module_report[name] = {
            "old": {
                "size": old.stat().st_size,
                "allocated_4k_blocks": old_blocks,
                "sha256": digest(old),
                "vermagic": module_field(old, "vermagic")[0],
            },
            "new": {
                "path": str(new),
                "size": new.stat().st_size,
                "allocated_4k_blocks": new_blocks,
                "sha256": digest(new),
                "vermagic": module_field(new, "vermagic")[0],
            },
            "dependencies_preserved": old_depends == new_depends,
            "aliases_preserved": old_alias == new_alias,
            "firmware_metadata_preserved": old_metadata["firmware"] == new_metadata["firmware"],
            "version_metadata_preserved": old_metadata["version"] == new_metadata["version"],
            "export_symbol_names_preserved": set(old_exports) == set(new_exports),
            "export_symbol_count": len(new_exports),
            "export_crc_changes": sorted(
                symbol
                for symbol in set(old_exports) & set(new_exports)
                if old_exports[symbol] != new_exports[symbol]
            ),
            "import_symbol_names_added": sorted(set(new_imports) - old_imports),
            "import_symbol_names_removed": sorted(old_imports - set(new_imports)),
            "new_modversion_mismatches": import_mismatches,
        }
        if not module_report[name]["new"]["vermagic"].startswith("5.4.302+"):
            raise SystemExit(f"unexpected module vermagic: {name}")

    if all_import_mismatches:
        raise SystemExit(f"new module modversion mismatches: {all_import_mismatches}")
    if dependency_changes or alias_changes or export_changes or name_changes:
        raise SystemExit(
            "module interface contract changed: "
            f"names={name_changes}, dependencies={dependency_changes}, "
            f"aliases={alias_changes}, exports={export_changes}"
        )
    if firmware_changes or version_changes:
        raise SystemExit(
            "module source/version contract changed: "
            f"firmware={firmware_changes}, versions={version_changes}"
        )
    accepted_vermagics = sorted(
        set(item["old"]["vermagic"] for item in module_report.values())
    )
    new_vermagics = sorted(
        set(item["new"]["vermagic"] for item in module_report.values())
    )
    if accepted_vermagics != [
        "5.4.125 SMP preempt mod_unload modversions aarch64"
    ]:
        raise SystemExit(f"unexpected accepted module release contract: {accepted_vermagics}")
    if new_vermagics != [
        "5.4.302+ SMP preempt mod_unload modversions aarch64"
    ]:
        raise SystemExit(f"rebuilt module releases are inconsistent: {new_vermagics}")

    filesystem = ext4_geometry(args.accepted_vendor_dlkm)
    module_storage = {
        "accepted_allocated_4k_blocks": old_allocated_blocks,
        "new_allocated_4k_blocks": new_allocated_blocks,
        "accepted_filesystem_free_4k_blocks": filesystem["free_blocks"],
        "maximum_available_4k_blocks": old_allocated_blocks + filesystem["free_blocks"],
        "remaining_4k_blocks_after_replacement": (
            old_allocated_blocks + filesystem["free_blocks"] - new_allocated_blocks
        ),
    }
    if new_allocated_blocks > old_allocated_blocks + filesystem["free_blocks"]:
        raise SystemExit(f"rebuilt modules do not fit fixed vendor_dlkm filesystem: {module_storage}")

    aic_fdrv = new_modules["aic8800_fdrv.ko"]
    aic_bsp = new_modules["aic8800_bsp.ko"]
    if module_field(aic_fdrv, "version") != ["20221108-004-6.4.3.0"]:
        raise SystemExit("AIC8800 fdrv release does not match accepted 20221108-004")
    if sorted(module_field(aic_fdrv, "alias")) != [
        "sdio:c*v5449d0145*",
        "sdio:c*vC8A1dC08D*",
    ]:
        raise SystemExit("AIC8800 fdrv SDIO aliases changed")
    if sorted(module_field(aic_bsp, "alias")) != [
        "sdio:c*v544Ad0146*",
        "sdio:c*vC8A1dC18D*",
    ]:
        raise SystemExit("AIC8800 BSP SDIO aliases changed")
    if len(module_symbols(new_modules["rtlwifi.ko"], "--show-exports")) != 72:
        raise SystemExit("accepted vendor RTLWIFI export surface is incomplete")

    dtb_lines = (result_dir / "dtb-sha256.txt").read_text().splitlines()
    if not dtb_lines:
        raise SystemExit("no DTB was produced")

    if args.build_log:
        log_paths = {"selected_build": args.build_log}
    else:
        log_paths = {
            "main_compile": args.evidence_dir / "attempt2/build.log",
            "successful_finalization": args.evidence_dir / "build.log",
            "aic8800_exact_donor": args.evidence_dir / "aic8800-donor-rebuild/build.log",
            "rtlwifi_vendor_debug": args.evidence_dir / "rtlwifi-debug-rebuild/build.log",
        }
    warning_lines = []
    unresolved_error_lines = []
    log_report = {}
    for label, path in log_paths.items():
        if not path.is_file():
            raise SystemExit(f"missing build log: {path}")
        text = path.read_text(errors="replace")
        warnings = sorted(
            set(line.strip() for line in text.splitlines() if re.search(r"\bwarning:", line, re.I))
        )
        errors = [
            line.strip()
            for line in text.splitlines()
            if re.search(r"(^|\s)(fatal error:|error:)", line, re.I)
        ]
        if label in {"main_compile", "selected_build"}:
            unclassified = [line for line in errors if not line.startswith("llvm-nm: error:")]
        else:
            unclassified = errors
        warning_lines.extend(f"{label}: {line}" for line in warnings)
        unresolved_error_lines.extend(f"{label}: {line}" for line in unclassified)
        log_report[label] = {
            "path": str(path),
            "warning_count": len(warnings),
            "error_count": len(errors),
            "errors": errors,
        }
    if not args.build_log and log_report["main_compile"]["error_count"] != 5:
        raise SystemExit(
            "expected the five classified parallel Mali llvm-nm race lines in the retained "
            f"main log, got {log_report['main_compile']['error_count']}"
        )
    if unresolved_error_lines:
        raise SystemExit(f"build logs contain unresolved errors: {unresolved_error_lines[:10]}")
    warning_lines = sorted(set(warning_lines))
    classified_recovered_failures = []
    if args.build_log:
        llvm_nm_errors = [
            line for line in log_report["selected_build"]["errors"]
            if line.startswith("llvm-nm: error:")
        ]
        if llvm_nm_errors:
            classified_recovered_failures.append({
                "cause": "Vendor Mali parallel clean/build race; final build completed successfully.",
                "source_or_abi_failure": False,
                "retained_error_lines": llvm_nm_errors,
            })
    else:
        classified_recovered_failures = [
            {
                "attempt": "attempt1",
                "cause": "Invocation omitted the vendor NAND KERNEL_SRC export; script fixed before compilation.",
                "source_or_abi_failure": False,
            },
            {
                "attempt": "attempt2 final external GPU step",
                "cause": "Vendor Mali top-level make launched clean/build submakes concurrently; the same source rebuilt sequentially.",
                "source_or_abi_failure": False,
                "retained_error_lines": log_report["main_compile"]["errors"],
            },
        ]

    report = {
        "schema": 1,
        "result": "PASS_WITH_PHYSICAL_VALIDATION_REQUIRED",
        "source": {
            "vendor_commit": args.vendor_commit,
            "vendor_tree": vendor_tree,
            "integration_commit": integration_head,
            "integration_tree": integration_tree,
            "kernel_release": release_dirs[0].name,
            "external_module_sources": {
                **donor_report,
                "rtlwifi": {
                    "repository": str(args.vendor_repo),
                    "commit": args.vendor_commit,
                    "source_path": "drivers/net/wireless/realtek/rtlwifi",
                    "subtree": rtlwifi_subtree,
                },
            },
        },
        "build": {
            "status": build_status,
            "image": {"path": str(image), "size": image.stat().st_size, "sha256": digest(image)},
            "config_contract": args.built_config,
            "config_sha256": digest(built_config),
            "module_symvers_sha256": digest(result_dir / "Module.symvers"),
            "symbol_version_sources": {
                path.name: digest(path) for path in symvers_sources
            },
            "superseded_main_aic8800_symbols": sorted(superseded_main_symvers),
            "dtb_count": len(dtb_lines),
            "unique_warning_count": len(warning_lines),
            "warnings": warning_lines,
            "logs": log_report,
            "classified_recovered_failures": classified_recovered_failures,
        },
        "critical_subtrees": subtree_report,
        "hardware_config": {"required": REQUIRED_CONFIG, "mismatches": config_mismatches},
        "path_a_config": {"required": PATH_A_CONFIG, "mismatches": path_a_mismatches},
        "modules": {
            "count": len(module_report),
            "inventory_exact": True,
            "dependency_metadata_exact": True,
            "alias_metadata_exact": True,
            "firmware_metadata_exact": True,
            "version_metadata_exact": True,
            "export_symbol_names_exact": True,
            "all_new_import_crcs_satisfied": True,
            "accepted_vermagics": accepted_vermagics,
            "new_vermagics": new_vermagics,
            "storage": module_storage,
            "accepted_kernel_module_release_note": (
                "The accepted Image identifies as 5.4.125+ while all accepted vendor_dlkm "
                "modules encode 5.4.125; the rebuilt Image/modules consistently encode 5.4.302+."
            ),
            "packaging_normalization": {
                "module": "rtlwifi.ko",
                "operation": "llvm-strip --strip-unneeded",
                "reason": "Fit the unchanged 1,585-block vendor_dlkm filesystem.",
                "interface_checks_after_strip": [
                    "module name/dependencies/aliases/firmware/version preserved",
                    "72 exported symbol names preserved",
                    "all imported symbols and CRCs satisfied",
                ],
            },
            "items": module_report,
        },
        "offline_limitations": [
            "Compilation and symbol/config preservation cannot exercise clocks, regulators, DVFS or thermal trips.",
            "Compilation and symbol/config preservation cannot exercise HDMI/display, Mali, Cedar/media or audio runtime paths.",
            "Compilation and symbol/config preservation cannot exercise AIC8800/other wireless firmware loading, USB, Ethernet or IR.",
            "Compilation cannot prove OP-TEE secure-world interoperability, suspend/resume or wake sources.",
            "A separately authorized Android 12 kernel-only physical test is required before using this kernel for Path A.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "result": report["result"],
        "image": report["build"]["image"],
        "modules": report["modules"]["count"],
        "dtbs": report["build"]["dtb_count"],
        "warnings": report["build"]["unique_warning_count"],
    }, indent=2))


if __name__ == "__main__":
    main()
