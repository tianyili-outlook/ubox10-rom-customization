#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import shutil
import sys

SYSTEM_DIR = "work/system_extracted"
BUILD_PROP_PATH = os.path.join(SYSTEM_DIR, "system/build.prop")

# 1. Directories to remove (adware and factory diagnostics)
TO_DELETE = [
    "system/app/happycast",
    "system/app/DragonAgingTV",
    "system/app/DragonAtt",
    "system/app/DragonBox",
    "system/app/Factory_detection"
]

# 2. Launcher replacement configuration
NEW_LAUNCHER_SRC = "system/SimpleLauncher.ap"
NEW_LAUNCHER_DST_DIR = "system/app/SimpleLauncher"
NEW_LAUNCHER_DST_FILE = "system/app/SimpleLauncher/SimpleLauncher.apk"

PROP_CHANGES = {
    "ro.sw.defaultlauncher_package": "ch.arnab.simplelauncher",
    "ro.sw.defaultlauncher_class": "ch.arnab.simplelauncher.HomeScreen",
    "persist.debug.logpersistd": "false",
    "persist.debug.logcat.enable": "false",
    "persist.debug.kernel_log.enable": "false",
    "persist.debug.crashdump.enable": "false"
}

def purify_rom():
    print("========================================")
    print("Starting ROM purification (Milestone M3)...")
    print("========================================")
    
    if not os.path.exists(SYSTEM_DIR):
        print(f"ERROR: Extracted system directory {SYSTEM_DIR} not found.")
        sys.exit(1)
        
    # Step 1: Delete unwanted directories
    deleted_count = 0
    for rel_path in TO_DELETE:
        full_path = os.path.join(SYSTEM_DIR, rel_path)
        if os.path.exists(full_path):
            print(f"[-] Deleting adware/diagnostic folder: {rel_path}...")
            try:
                shutil.rmtree(full_path)
                deleted_count += 1
            except Exception as e:
                print(f"    Warning: failed to delete: {e}")
        else:
            print(f"[ ] Path already gone or not present: {rel_path}")
            
    # Step 2: Preload the backup clean TV launcher
    src_ap = os.path.join(SYSTEM_DIR, NEW_LAUNCHER_SRC)
    dst_dir = os.path.join(SYSTEM_DIR, NEW_LAUNCHER_DST_DIR)
    dst_apk = os.path.join(SYSTEM_DIR, NEW_LAUNCHER_DST_FILE)
    
    if os.path.exists(src_ap):
        print(f"[+] Preloading clean backup launcher from {NEW_LAUNCHER_SRC}...")
        os.makedirs(dst_dir, exist_ok=True)
        try:
            shutil.copy2(src_ap, dst_apk)
            print(f"    Copied to {NEW_LAUNCHER_DST_FILE}")
        except Exception as e:
            print(f"    Error preloading launcher: {e}")
            sys.exit(1)
    else:
        # Check if already preloaded
        if os.path.exists(dst_apk):
            print(f"[ ] Backup launcher already preloaded in {NEW_LAUNCHER_DST_FILE}")
        else:
            print(f"ERROR: Preload source launcher {src_ap} not found!")
            sys.exit(1)
            
    # Step 3: Modify build.prop
    if not os.path.exists(BUILD_PROP_PATH):
        print(f"ERROR: build.prop not found at {BUILD_PROP_PATH}!")
        sys.exit(1)
        
    print(f"[+] Modifying {BUILD_PROP_PATH}...")
    try:
        # Read lines
        with open(BUILD_PROP_PATH, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            
        modified_lines = []
        applied_keys = set()
        
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('#') or '=' not in stripped:
                modified_lines.append(line)
                continue
                
            key, val = stripped.split('=', 1)
            key = key.strip()
            
            if key in PROP_CHANGES:
                new_val = PROP_CHANGES[key]
                print(f"    Modifying property: {key} = {new_val} (was {val.strip()})")
                modified_lines.append(f"{key}={new_val}\n")
                applied_keys.add(key)
            else:
                modified_lines.append(line)
                
        # Append keys that were not found in build.prop
        for key, val in PROP_CHANGES.items():
            if key not in applied_keys:
                print(f"    Adding property: {key} = {val}")
                modified_lines.append(f"{key}={val}\n")
                
        # Save back
        with open(BUILD_PROP_PATH, 'w', encoding='utf-8') as f:
            f.writelines(modified_lines)
            
        print("SUCCESS: build.prop updated.")
    except Exception as e:
        print(f"ERROR writing build.prop: {e}")
        sys.exit(1)
        
    print("========================================")
    print(f"ROM purification complete! Cleaned {deleted_count} apps.")
    print("========================================")

if __name__ == '__main__':
    purify_rom()
