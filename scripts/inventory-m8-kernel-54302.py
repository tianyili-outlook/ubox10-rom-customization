#!/usr/bin/env python3
"""Inventory the retained M8 H616 BSP delta before a 5.4 LTS update."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import subprocess
from pathlib import Path


CATEGORIES: dict[str, tuple[str, ...]] = {
    "h616_sun50iw9_dts_bindings": (
        r"^arch/arm64/boot/dts/sunxi/",
        r"^include/dt-bindings/.+(sun50iw9|sunxi|allwinner)",
        r"^Documentation/devicetree/bindings/.+(sunxi|allwinner)",
    ),
    "display_hdmi_framebuffer_drm": (
        r"^drivers/video/fbdev/sunxi/",
        r"^drivers/gpu/drm/.+(sunxi|allwinner)",
        r"^drivers/char/sunxi-(di|gralloc)/",
        r"^drivers/video/sunxi/",
        r"^include/.+(disp|hdmi|sunxi_fb)",
    ),
    "mali_g31_kbase": (
        r"^modules/gpu/mali-bifrost/",
        r"^drivers/gpu/arm/",
        r"^include/.+mali",
    ),
    "cedar_vpu_media_vin": (
        r"^drivers/media/cedar-ve/",
        r"^drivers/media/platform/sunxi/",
        r"^drivers/media/platform/sunxi-vin/",
        r"^drivers/staging/media/sunxi/",
        r"^include/.+(cedar|ve_|sunxi.*vin)",
    ),
    "g2d_dma_heaps_ion": (
        r"^drivers/char/sunxi_g2d/",
        r"^drivers/sunxi_drm_heap/",
        r"^drivers/staging/android/ion/",
        r"^drivers/dma-buf/",
        r"^include/.+(dma-heap|ion|sunxi.*heap)",
    ),
    "apollo_audio": (
        r"^sound/soc/sunxi/",
        r"^sound/soc/sunxi_v2/",
        r"^include/.+sunxi.*(audio|snd|codec)",
    ),
    "aic8800_wifi_bluetooth": (
        r"^drivers/net/wireless/aic8800/",
        r"^drivers/bluetooth/.+aic",
    ),
    "ethernet": (
        r"^drivers/net/ethernet/(allwinner|sunxi)/",
        r"^drivers/net/ethernet/stmicro/stmmac/",
        r"^drivers/net/phy/.+(sunxi|ephy)",
    ),
    "usb_host_device": (
        r"^drivers/usb/sunxi_usb/",
        r"^drivers/usb/(host|gadget|musb|dwc3)/",
        r"^include/.+sunxi.*usb",
    ),
    "ir_rc_core": (
        r"^drivers/media/rc/",
        r"^drivers/input/.+sunxi.*ir",
    ),
    "thermal_dvfs_clocks_regulators": (
        r"^drivers/(thermal|cpufreq|devfreq|opp)/",
        r"^drivers/clk/(sunxi|sunxi-ng)/",
        r"^drivers/regulator/.+(sunxi|axp)",
        r"^include/.+(sunxi.*(clk|thermal)|axp)",
    ),
    "suspend_wake": (
        r"^drivers/char/sunxi_standby/",
        r"^drivers/soc/sunxi/.+(suspend|standby|pm)",
        r"^kernel/power/",
    ),
    "tee_optee": (
        r"^drivers/tee/",
        r"^include/(linux|uapi/linux)/tee",
    ),
    "block_dm_avb_filesystems": (
        r"^drivers/block/loop\.c$",
        r"^drivers/md/dm(-|\.c|/)",
        r"^fs/(verity|crypto)/",
        r"^include/linux/(device-mapper|dm-|fsverity)",
    ),
}

CRITICAL_SUBTREES = (
    "arch/arm64/boot/dts/sunxi",
    "modules/gpu/mali-bifrost",
    "drivers/video/fbdev/sunxi",
    "drivers/media/cedar-ve",
    "drivers/media/platform/sunxi-vin",
    "drivers/char/sunxi_g2d",
    "drivers/char/sunxi-di",
    "drivers/char/sunxi-gralloc",
    "drivers/sunxi_drm_heap",
    "drivers/net/wireless/aic8800",
    "drivers/usb/sunxi_usb",
)

CONFIG_KEYS = (
    "CONFIG_ARM64", "CONFIG_COMPAT", "CONFIG_ARCH_SUNXI", "CONFIG_ARCH_SUN50IW9",
    "CONFIG_SUNXI_SOC_NAME", "CONFIG_SUNXI_GPU_TYPE", "CONFIG_DRM",
    "CONFIG_DISP2_SUNXI", "CONFIG_HDMI2_DISP2_SUNXI",
    "CONFIG_VIDEO_ENCODER_DECODER_SUNXI", "CONFIG_SUNXI_G2D",
    "CONFIG_ION", "CONFIG_DMABUF_HEAPS", "CONFIG_SUNXI_DRM_HEAP",
    "CONFIG_SND_SOC_SUNXI_INTERNALCODEC", "CONFIG_SND_SOC_SUNXI_SUN50IW9_CODEC",
    "CONFIG_SND_SOC_SUNXI_AAUDIO", "CONFIG_SND_SOC_SUNXI_HDMIAUDIO",
    "CONFIG_AIC_WLAN_SUPPORT", "CONFIG_AIC8800_WLAN_SUPPORT",
    "CONFIG_AIC8800_BTLPM_SUPPORT", "CONFIG_SUNXI_GMAC", "CONFIG_SUNXI_EPHY",
    "CONFIG_USB_SUNXI_HCI", "CONFIG_RC_CORE", "CONFIG_RC_MAP_SUNXI",
    "CONFIG_SUNXI_MULTI_IR_SUPPORT", "CONFIG_THERMAL", "CONFIG_SUNXI_THERMAL",
    "CONFIG_CPU_FREQ",
    "CONFIG_SUSPEND", "CONFIG_PM_WAKELOCKS", "CONFIG_TEE", "CONFIG_OPTEE",
    "CONFIG_MODULES", "CONFIG_MODVERSIONS", "CONFIG_DM_VERITY", "CONFIG_DM_CRYPT",
    "CONFIG_BLK_DEV_DM", "CONFIG_BLK_CGROUP", "CONFIG_CPUSETS",
    "CONFIG_PROC_PID_CPUSET", "CONFIG_NET_CLS_MATCHALL", "CONFIG_NET_ACT_POLICE",
    "CONFIG_NET_ACT_BPF", "CONFIG_BPF", "CONFIG_BPF_SYSCALL", "CONFIG_CGROUP_BPF",
)


def run(repo: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout


def git_object(repo: Path, ref: str, path: str | None = None) -> str | None:
    spec = f"{ref}:{path}" if path else ref
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", spec], text=True,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def config_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if line.startswith("CONFIG_") and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
        elif line.startswith("# CONFIG_") and line.endswith(" is not set"):
            values[line[2:-11]] = "n"
    return values


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def categories_for(path: str) -> list[str]:
    return [
        category for category, patterns in CATEGORIES.items()
        if any(re.search(pattern, path) for pattern in patterns)
    ]


def parse_delta(repo: Path, base: str, vendor: str) -> list[dict[str, object]]:
    records = []
    output = run(repo, "diff", "--no-renames", "--name-status", base, vendor)
    for line in output.splitlines():
        status, path = line.split("\t", 1)
        records.append({"status": status, "path": path, "categories": categories_for(path)})
    return records


def module_record(module: Path) -> dict[str, object]:
    def field(name: str) -> str:
        result = subprocess.run(
            ["modinfo", "-F", name, str(module)], text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
        )
        return result.stdout.strip()

    return {
        "file": module.name,
        "size": module.stat().st_size,
        "sha256": digest(module),
        "name": field("name"),
        "vermagic": field("vermagic"),
        "depends": [item for item in field("depends").split(",") if item],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--vendor", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--integration", required=True)
    parser.add_argument("--accepted-config", type=Path, required=True)
    parser.add_argument("--accepted-modules", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    delta = parse_delta(args.repo, args.base, args.vendor)
    update_paths = set(run(
        args.repo, "diff", "--no-renames", "--name-only", args.base, args.target,
    ).splitlines())
    integration_paths = set(run(
        args.repo, "diff", "--no-renames", "--name-only", args.vendor, args.integration,
    ).splitlines())

    statuses = collections.Counter(str(item["status"]) for item in delta)
    top_levels = collections.Counter(str(item["path"]).split("/", 1)[0] for item in delta)
    critical: dict[str, dict[str, object]] = {}
    for category in CATEGORIES:
        entries = [item for item in delta if category in item["categories"]]
        critical[category] = {
            "count": len(entries),
            "status_counts": dict(sorted(collections.Counter(
                str(item["status"]) for item in entries
            ).items())),
            "update_overlap_count": sum(str(item["path"]) in update_paths for item in entries),
            "integration_changed_count": sum(
                str(item["path"]) in integration_paths for item in entries
            ),
            "files": entries,
        }

    grep = run(
        args.repo, "grep", "-n", "-E",
        r"EXPORT_SYMBOL(_GPL|_NS|_NS_GPL)?[[:space:]]*\(", args.vendor,
        "--", "*.c", "*.h", check=False,
    )
    delta_by_path = {str(item["path"]): item for item in delta}
    exports = []
    export_re = re.compile(r"EXPORT_SYMBOL(?:_GPL|_NS|_NS_GPL)?\s*\(\s*([A-Za-z0-9_]+)")
    for line in grep.splitlines():
        match = re.match(r"^[^:]+:(.+?):([0-9]+):(.*)$", line)
        if not match:
            continue
        path, line_number, text = match.groups()
        entry = delta_by_path.get(path)
        symbol = export_re.search(text)
        if entry and entry["categories"] and symbol:
            exports.append({
                "symbol": symbol.group(1), "path": path,
                "line": int(line_number), "categories": entry["categories"],
            })

    accepted_config = config_values(args.accepted_config)
    modules = sorted(args.accepted_modules.glob("*.ko"))
    result = {
        "schema": 1,
        "lineage": {
            "base_commit": git_object(args.repo, args.base),
            "base_tree": git_object(args.repo, f"{args.base}^{{tree}}"),
            "vendor_commit": git_object(args.repo, args.vendor),
            "vendor_tree": git_object(args.repo, f"{args.vendor}^{{tree}}"),
            "target_commit": git_object(args.repo, args.target),
            "target_tree": git_object(args.repo, f"{args.target}^{{tree}}"),
            "integration_commit": git_object(args.repo, args.integration),
            "integration_tree": git_object(args.repo, f"{args.integration}^{{tree}}"),
        },
        "vendor_delta": {
            "file_count": len(delta),
            "status_counts": dict(sorted(statuses.items())),
            "top_level_counts": dict(sorted(top_levels.items())),
            "update_overlap_count": sum(str(item["path"]) in update_paths for item in delta),
            "vendor_added_changed_by_integration": sorted(
                str(item["path"]) for item in delta
                if item["status"] == "A" and str(item["path"]) in integration_paths
            ),
        },
        "critical_categories": critical,
        "critical_subtrees": {
            path: {
                "vendor_object": git_object(args.repo, args.vendor, path),
                "integration_object": git_object(args.repo, args.integration, path),
                "preserved": git_object(args.repo, args.vendor, path)
                == git_object(args.repo, args.integration, path),
            }
            for path in CRITICAL_SUBTREES
        },
        "source_level_exports_in_critical_vendor_delta": sorted(
            exports, key=lambda item: (str(item["symbol"]), str(item["path"])),
        ),
        "accepted_android12_config": {
            "path": str(args.accepted_config),
            "size": args.accepted_config.stat().st_size,
            "sha256": digest(args.accepted_config),
            "selected_values": {key: accepted_config.get(key) for key in CONFIG_KEYS},
        },
        "accepted_vendor_dlkm_modules": [module_record(path) for path in modules],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
