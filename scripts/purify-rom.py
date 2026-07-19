#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UBOX10 ROM Purification & Preinstall Script (Milestone M3+)

This script performs all confirmed deletions and preinstalls on the extracted
system/product/vendor partitions:

  P0 Deletions (confirmed):
    - X12 (安博定制桌面)
    - UBTunnel.6 (安博 VPN 隧道)
    - settingwizard (安博设置向导)
    - browser-v1.1 (安博定制浏览器)
    - AwlogSettings (全志日志配置)
    - zysrf (Google 注音输入法)

  P1 Deletions (confirmed):
    - H618_UpgradeV3 (厂商 OTA 升级工具)
    - NanoOtaBle (蓝牙遥控器 OTA)
    - Update (系统更新检查器)
    - CZFileManager (超卓文件管理器)
    - TvdFileManager (全志文件管理器)
    - BLEAutoPair (蓝牙自动配对 - 用户确认使用红外遥控器)
    - Chrome (浏览器 - 用户确认删除)

  Vendor Deletions:
    - vendor/111.mp3 (开机音效)

  Preinstalls:
    - FLauncher (默认启动器, 替代 X12)
    - SimpleLauncher (已存在, 保留为 fallback)

  build.prop Modifications:
    - 默认启动器指向 FLauncher
    - 关闭日志持久化
"""

import os
import shutil
import sys
import hashlib

# ===== Configuration =====

SYSTEM_DIR = "work/system_extracted"
PRODUCT_DIR = "work/product_extracted"
VENDOR_DIR = "work/vendor_extracted"
BUILD_PROP_PATH = os.path.join(SYSTEM_DIR, "system/build.prop")
PREINSTALL_APKS_DIR = "work/preinstall_apks"

# P0: Strongly recommended deletions (confirmed by user)
P0_DELETE = [
    ("system/app/X12",                "X12 安博定制桌面启动器"),
    ("system/app/UBTunnel.6",         "UBTunnel 安博 VPN 隧道客户端"),
    ("system/app/settingwizard",      "settingwizard 安博定制设置向导"),
    ("system/app/browser-v1.1",       "browser 安博定制浏览器"),
    ("system/app/AwlogSettings",      "AwlogSettings 全志日志调试配置"),
    ("system/app/zysrf",              "zysrf Google 注音输入法"),
]

# P1: Recommended deletions (confirmed by user)
P1_DELETE = [
    ("system/app/H618_UpgradeV3",     "H618_UpgradeV3 厂商 OTA 升级工具"),
    ("system/app/NanoOtaBle",         "NanoOtaBle 蓝牙遥控器 OTA"),
    ("system/app/Update",             "Update 系统更新检查器"),
    ("system/app/CZFileManager3.1.7_official_site", "CZFileManager 超卓文件管理器"),
    ("system/app/Chrome",             "Chrome 浏览器"),
    ("system/priv-app/TvdFileManager", "TvdFileManager 全志文件管理器"),
    ("system/priv-app/BLEAutoPair",   "BLEAutoPair 蓝牙自动配对服务"),
]

# Vendor file deletions
VENDOR_DELETE = [
    ("111.mp3", "开机音效文件"),
]

# Preinstall: FLauncher as system default launcher
FLAUNCHER_SRC = os.path.join(PREINSTALL_APKS_DIR, "FLauncher.apk")
FLAUNCHER_DST_DIR = os.path.join(SYSTEM_DIR, "system/app/FLauncher")
FLAUNCHER_DST_APK = os.path.join(FLAUNCHER_DST_DIR, "FLauncher.apk")

# Preinstall: SmartTube to product/app (user can uninstall)
SMARTTUBE_SRC = os.path.join(PREINSTALL_APKS_DIR, "SmartTube.apk")
SMARTTUBE_DST_DIR = os.path.join(PRODUCT_DIR, "app/SmartTube")
SMARTTUBE_DST_APK = os.path.join(SMARTTUBE_DST_DIR, "SmartTube.apk")

# Optional preinstalls (user needs to manually download from Play Store/APKMirror)
OPTIONAL_PREINSTALLS = {
    "Gboard.apk": {
        "dst_dir": os.path.join(PRODUCT_DIR, "app/Gboard"),
        "dst_name": "Gboard.apk",
        "description": "Gboard Google 输入法",
    },
    "GoogleFiles.apk": {
        "dst_dir": os.path.join(PRODUCT_DIR, "app/GoogleFiles"),
        "dst_name": "GoogleFiles.apk",
        "description": "Google Files 文件管理器",
    },
    "VLC.apk": {
        "dst_dir": os.path.join(PRODUCT_DIR, "app/VLC"),
        "dst_name": "VLC.apk",
        "description": "VLC 万能视频播放器",
    },
    "SendFilesToTV.apk": {
        "dst_dir": os.path.join(PRODUCT_DIR, "app/SendFilesToTV"),
        "dst_name": "SendFilesToTV.apk",
        "description": "Send Files to TV 局域网传输工具",
    },
}

# build.prop property changes
PROP_CHANGES = {
    # FLauncher as default launcher
    "ro.sw.defaultlauncher_package": "me.efesser.flauncher",
    "ro.sw.defaultlauncher_class": "me.efesser.flauncher.MainActivity",
    # Disable debug logging
    "persist.debug.logpersistd": "false",
    "persist.debug.logcat.enable": "false",
    "persist.debug.kernel_log.enable": "false",
    "persist.debug.crashdump.enable": "false",
}


def sha256_file(filepath):
    """Calculate SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(64 * 1024), b''):
            h.update(chunk)
    return h.hexdigest().upper()


def delete_entries(base_dir, entries, priority_label):
    """Delete a list of directories/files from a base directory."""
    deleted = 0
    freed_bytes = 0
    for rel_path, desc in entries:
        full_path = os.path.join(base_dir, rel_path)
        if os.path.exists(full_path):
            # Calculate size before deletion
            if os.path.isdir(full_path):
                size = sum(
                    os.path.getsize(os.path.join(dp, f))
                    for dp, _, files in os.walk(full_path)
                    for f in files
                )
            else:
                size = os.path.getsize(full_path)

            print(f"  [-] [{priority_label}] Deleting: {desc}")
            print(f"       Path: {rel_path}  ({size / (1024*1024):.1f} MB)")
            try:
                if os.path.isdir(full_path):
                    shutil.rmtree(full_path)
                else:
                    os.remove(full_path)
                deleted += 1
                freed_bytes += size
            except Exception as e:
                print(f"       WARNING: Failed to delete: {e}")
        else:
            print(f"  [ ] Already removed: {rel_path}")
    return deleted, freed_bytes


def preinstall_apk(src, dst_dir, dst_apk, name):
    """Copy an APK to the target partition directory."""
    if not os.path.isfile(src):
        print(f"  [!] SKIP: {name} APK not found at {src}")
        return False

    if os.path.isfile(dst_apk):
        print(f"  [ ] {name} already preinstalled at {dst_apk}")
        return True

    print(f"  [+] Preinstalling {name}...")
    print(f"       Source: {src}")
    print(f"       Target: {dst_apk}")
    print(f"       SHA-256: {sha256_file(src)}")
    os.makedirs(dst_dir, exist_ok=True)
    shutil.copy2(src, dst_apk)
    print(f"       Size: {os.path.getsize(dst_apk) / (1024*1024):.1f} MB")
    return True


def modify_build_prop():
    """Modify build.prop with the configured property changes."""
    if not os.path.isfile(BUILD_PROP_PATH):
        print(f"  ERROR: build.prop not found at {BUILD_PROP_PATH}")
        sys.exit(1)

    print(f"  [+] Modifying {BUILD_PROP_PATH}...")
    with open(BUILD_PROP_PATH, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    modified_lines = []
    applied_keys = set()

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('#') or '=' not in stripped:
            modified_lines.append(line)
            continue

        key = stripped.split('=', 1)[0].strip()
        old_val = stripped.split('=', 1)[1].strip()

        if key in PROP_CHANGES:
            new_val = PROP_CHANGES[key]
            if old_val != new_val:
                print(f"       Modify: {key} = {new_val}  (was: {old_val})")
            else:
                print(f"       Unchanged: {key} = {new_val}")
            modified_lines.append(f"{key}={new_val}\n")
            applied_keys.add(key)
        else:
            modified_lines.append(line)

    # Append keys not found in existing build.prop
    for key, val in PROP_CHANGES.items():
        if key not in applied_keys:
            print(f"       Add: {key} = {val}")
            modified_lines.append(f"{key}={val}\n")

    with open(BUILD_PROP_PATH, 'w', encoding='utf-8') as f:
        f.writelines(modified_lines)
    print("       build.prop updated successfully.")


def purify_rom():
    print("=" * 60)
    print("UBOX10 ROM Purification & Preinstall Script")
    print("=" * 60)

    # Validate directories
    for d, label in [(SYSTEM_DIR, "system"), (PRODUCT_DIR, "product"), (VENDOR_DIR, "vendor")]:
        if not os.path.isdir(d):
            print(f"ERROR: {label} extracted directory not found: {d}")
            sys.exit(1)

    total_deleted = 0
    total_freed = 0

    # ── Step 1: P0 Deletions (system partition) ──
    print("\n── Step 1: P0 强烈推荐删除 (Strong Recommendation) ──")
    d, f = delete_entries(SYSTEM_DIR, P0_DELETE, "P0")
    total_deleted += d
    total_freed += f

    # ── Step 2: P1 Deletions (system partition) ──
    print("\n── Step 2: P1 推荐删除 (Recommended) ──")
    d, f = delete_entries(SYSTEM_DIR, P1_DELETE, "P1")
    total_deleted += d
    total_freed += f

    # ── Step 3: Vendor deletions ──
    print("\n── Step 3: Vendor 分区清理 ──")
    d, f = delete_entries(VENDOR_DIR, VENDOR_DELETE, "VEN")
    total_deleted += d
    total_freed += f

    # ── Step 4: Preinstall FLauncher ──
    print("\n── Step 4: 预装应用 ──")
    preinstall_apk(FLAUNCHER_SRC, FLAUNCHER_DST_DIR, FLAUNCHER_DST_APK, "FLauncher")

    # ── Step 5: Preinstall SmartTube ──
    preinstall_apk(SMARTTUBE_SRC, SMARTTUBE_DST_DIR, SMARTTUBE_DST_APK, "SmartTube")

    # ── Step 6: Optional preinstalls ──
    print("\n── Step 5: 可选预装应用 (需手动下载 APK 至 work/preinstall_apks/) ──")
    for filename, cfg in OPTIONAL_PREINSTALLS.items():
        src = os.path.join(PREINSTALL_APKS_DIR, filename)
        preinstall_apk(src, cfg["dst_dir"], os.path.join(cfg["dst_dir"], cfg["dst_name"]), cfg["description"])

    # ── Step 7: Modify build.prop ──
    print("\n── Step 6: 修改 build.prop ──")
    modify_build_prop()

    # ── Summary ──
    print("\n" + "=" * 60)
    print(f"ROM purification complete!")
    print(f"  Deleted items:     {total_deleted}")
    print(f"  Space freed:       {total_freed / (1024*1024):.1f} MB")
    print(f"  Default launcher:  FLauncher (me.efesser.flauncher)")
    print("=" * 60)

    # Check for missing optional preinstalls
    missing = []
    for filename, cfg in OPTIONAL_PREINSTALLS.items():
        src = os.path.join(PREINSTALL_APKS_DIR, filename)
        if not os.path.isfile(src):
            missing.append((filename, cfg["description"]))
    if missing:
        print("\n[WARNING] 以下可选预装 APK 未找到，请手动下载后重新运行脚本：")
        for fn, desc in missing:
            print(f"    - {PREINSTALL_APKS_DIR}/{fn}  ({desc})")
        print("  下载来源推荐：APKMirror (apkmirror.com) 或 Google Play Store")
        print("  注意选择 arm64-v8a 架构版本")


if __name__ == '__main__':
    purify_rom()
