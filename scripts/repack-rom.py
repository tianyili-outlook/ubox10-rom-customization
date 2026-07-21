#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UBOX10 ROM Repackaging & AVB Signing Automation Pipeline (Milestone M4)
"""

import os
import sys
import shutil
import subprocess

# Paths
TOOLS_DIR = "tools"
WORK_DIR = "work"
FIRMWARE_DIR = "firmware"
EXTRACTED_DIR = os.path.join(FIRMWARE_DIR, "extracted")

MAKE_EXT4FS = os.path.join(TOOLS_DIR, "make_ext4fs.exe")
LPMAKE = os.path.join(TOOLS_DIR, "lpmake.exe")
AVBTOOL = os.path.join(TOOLS_DIR, "avbtool.py")
TESTKEY = os.path.join(TOOLS_DIR, "testkey_rsa2048.pem")
FILE_CONTEXTS = os.path.join(WORK_DIR, "system_extracted/system/etc/selinux/plat_file_contexts")

# Partition Configurations
PARTITIONS = {
    "system": {
        "src_dir": os.path.join(WORK_DIR, "system_extracted/system"),
        "raw_img": os.path.join(WORK_DIR, "system_a_raw.img"),
        "mount_point": "/system",
        # Original raw filesystem size (excluding AVB/FEC metadata)
        "fs_size": 1625026560,
        # Total partition size signed by AVB
        "partition_size": 1651167232,
        "salt": "849ad1a7d5dd18e1e29fdf0526f0b834d754bbe9286407ddcbaf3a18a32d9a26",
    },
    "product": {
        "src_dir": os.path.join(WORK_DIR, "product_extracted"),
        "raw_img": os.path.join(WORK_DIR, "product_a_raw.img"),
        "mount_point": "/product",
        # Enlarged filesystem size to fit preinstalls (300 MB)
        "fs_size": 314572800,
        # Enlarged total partition size (320 MB)
        "partition_size": 335544320,
        "salt": "77968b3ec4c881f36788e05b78b6400e08114a1c4e959c3c73131de6cf9bd8e7",
    },
    "vendor": {
        "orig_img": os.path.join(WORK_DIR, "super_extracted/vendor_a.img"),
        "raw_img": os.path.join(WORK_DIR, "vendor_a_raw.img"),
        "partition_size": 119066624,
        "salt": "fd5d38e3dcce6009a051990978c7efd76c1d67e381f05da77c1cb230d85911c9",
    },
    "vendor_dlkm": {
        "orig_img": os.path.join(WORK_DIR, "super_extracted/vendor_dlkm_a.img"),
        "raw_img": os.path.join(WORK_DIR, "vendor_dlkm_a_raw.img"),
        "partition_size": 6680576,
        "salt": "523caf2a432189513d46cde728abaf1825f66e083ba17a9d812baa50d017820b",
    }
}

def run_cmd(args):
    print("Executing: " + " ".join(args))
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore")
    out, err = p.communicate()
    if p.returncode != 0:
        print("ERROR:")
        print(err)
        sys.exit(p.returncode)
    if out.strip():
        print(out.strip())

def main():
    print("==============================================================")
    print("Starting ROM Repackaging & AVB Signing Pipeline")
    print("==============================================================")

    # 1. Compile modified system and product partitions
    for part_name in ["system", "product"]:
        cfg = PARTITIONS[part_name]
        print(f"\n--- Compiling {part_name} partition to ext4 raw image ---")
        if not os.path.isdir(cfg["src_dir"]):
            print(f"ERROR: Source directory {cfg['src_dir']} not found!")
            sys.exit(1)
        
        args = [
            MAKE_EXT4FS,
            "-l", str(cfg["fs_size"]),
            "-a", cfg["mount_point"],
            "-S", FILE_CONTEXTS,
            cfg["raw_img"],
            cfg["src_dir"]
        ]
        run_cmd(args)

    # 2. Copy unmodified vendor and vendor_dlkm partitions
    for part_name in ["vendor", "vendor_dlkm"]:
        cfg = PARTITIONS[part_name]
        print(f"\n--- Copying unmodified {part_name} partition ---")
        if not os.path.isfile(cfg["orig_img"]):
            print(f"ERROR: Original image {cfg['orig_img']} not found!")
            sys.exit(1)
        shutil.copy2(cfg["orig_img"], cfg["raw_img"])
        print(f"Copied to {cfg['raw_img']}")

    # 3. Add AVB hashtree footer & signature to all partitions
    for part_name, cfg in PARTITIONS.items():
        print(f"\n--- AVB Signing {part_name} partition ---")
        args = [
            sys.executable, AVBTOOL, "add_hashtree_footer",
            "--image", cfg["raw_img"],
            "--partition_name", part_name,
            "--partition_size", str(cfg["partition_size"]),
            "--key", TESTKEY,
            "--algorithm", "SHA256_RSA2048",
            "--salt", cfg["salt"],
            "--do_not_generate_fec"
        ]
        run_cmd(args)

    # 4. Generate chained vbmeta_system.img
    print("\n--- Generating vbmeta_system.img ---")
    run_cmd([
        sys.executable, AVBTOOL, "make_vbmeta_image",
        "--output", os.path.join(WORK_DIR, "vbmeta_system.img"),
        "--key", TESTKEY,
        "--algorithm", "SHA256_RSA2048",
        "--rollback_index", "1644019200",
        "--include_descriptors_from_image", PARTITIONS["system"]["raw_img"],
        "--prop", "com.android.build.system.fingerprint:Unblocktech/apollo_p1/apollo-p1:12/SP1A.211105.004/hush10241757:userdebug/test-keys",
        "--prop", "com.android.build.system.os_version:12",
        "--prop", "com.android.build.system.security_patch:2022-02-05"
    ])

    # 5. Generate chained vbmeta_vendor.img
    print("\n--- Generating vbmeta_vendor.img ---")
    run_cmd([
        sys.executable, AVBTOOL, "make_vbmeta_image",
        "--output", os.path.join(WORK_DIR, "vbmeta_vendor.img"),
        "--key", TESTKEY,
        "--algorithm", "SHA256_RSA2048",
        "--rollback_index", "1644019200",
        "--include_descriptors_from_image", PARTITIONS["vendor"]["raw_img"],
        "--prop", "com.android.build.vendor.fingerprint:Unblocktech/apollo_p1/apollo-p1:12/SP1A.211105.004/hush10241757:userdebug/test-keys",
        "--prop", "com.android.build.vendor.os_version:12"
    ])

    # 6. Generate main vbmeta.img
    print("\n--- Generating main vbmeta.img ---")
    vendor_boot_path = os.path.join(WORK_DIR, "vendor_boot.img")
    if not os.path.exists(vendor_boot_path):
        vendor_boot_path = os.path.join(EXTRACTED_DIR, "vendor_boot.fex")
        
    run_cmd([
        sys.executable, AVBTOOL, "make_vbmeta_image",
        "--output", os.path.join(WORK_DIR, "vbmeta.img"),
        "--key", TESTKEY,
        "--algorithm", "SHA256_RSA2048",
        "--rollback_index", "0",
        "--chain_partition", f"vbmeta_system:1:{TESTKEY}",
        "--chain_partition", f"vbmeta_vendor:2:{TESTKEY}",
        "--include_descriptors_from_image", os.path.join(WORK_DIR, "boot.img"),
        "--include_descriptors_from_image", os.path.join(EXTRACTED_DIR, "dtbo.fex"),
        "--include_descriptors_from_image", vendor_boot_path,
        "--include_descriptors_from_image", PARTITIONS["product"]["raw_img"],
        "--include_descriptors_from_image", PARTITIONS["vendor_dlkm"]["raw_img"],
        "--prop", "com.android.build.boot.fingerprint:Unblocktech/apollo_p1/apollo-p1:12/SP1A.211105.004/hush10241757:userdebug/test-keys",
        "--prop", "com.android.build.boot.os_version:12",
        "--prop", "com.android.build.vendor_boot.fingerprint:Unblocktech/apollo_p1/apollo-p1:12/SP1A.211105.004/hush10241757:userdebug/test-keys",
        "--prop", "com.android.build.product.fingerprint:Unblocktech/apollo_p1/apollo-p1:12/SP1A.211105.004/hush10241757:userdebug/test-keys",
        "--prop", "com.android.build.product.os_version:12",
        "--prop", "com.android.build.product.security_patch:2022-02-05",
        "--prop", "com.android.build.vendor_dlkm.fingerprint:Unblocktech/apollo_p1/apollo-p1:12/SP1A.211105.004/hush10241757:userdebug/test-keys",
        "--prop", "com.android.build.vendor_dlkm.os_version:12",
        "--prop", "com.android.build.dtbo.fingerprint:Unblocktech/apollo_p1/apollo-p1:12/SP1A.211105.004/hush10241757:userdebug/test-keys"
    ])

    # 7. Assemble dynamic logical partitions into super.img (RAW format first)
    print("\n--- Assembling logical partitions into super_raw.img (lpmake) ---")
    super_raw_path = os.path.join(WORK_DIR, "super_raw.img")
    super_sparse_path = os.path.join(WORK_DIR, "super.img")
    
    run_cmd([
        LPMAKE,
        "--device-size", "3221225472",
        "--metadata-size", "65536",
        "--metadata-slots", "3",
        "--super-name", "super",
        "--virtual-ab",
        "--alignment", "1048576",
        "--group", "sb_a:3212836864",
        "--group", "sb_b:3212836864",
        "--partition", "system_a:readonly:1651167232:sb_a",
        "--image", f"system_a={PARTITIONS['system']['raw_img']}",
        "--partition", "system_b:readonly:0:sb_b",
        "--partition", "vendor_a:readonly:119066624:sb_a",
        "--image", f"vendor_a={PARTITIONS['vendor']['raw_img']}",
        "--partition", "vendor_b:readonly:0:sb_b",
        "--partition", "product_a:readonly:335544320:sb_a",
        "--image", f"product_a={PARTITIONS['product']['raw_img']}",
        "--partition", "product_b:readonly:0:sb_b",
        "--partition", "vendor_dlkm_a:readonly:6680576:sb_a",
        "--image", f"vendor_dlkm_a={PARTITIONS['vendor_dlkm']['raw_img']}",
        "--partition", "vendor_dlkm_b:readonly:0:sb_b",
        "--output", super_raw_path
    ])

    # Convert raw super.img to standard sparse format
    print("\n--- Converting raw super image to standard sparse format (img2simg) ---")
    run_cmd([
        os.path.join(TOOLS_DIR, "img2simg.exe"),
        super_raw_path,
        super_sparse_path
    ])

    # Clean up the large raw file
    print(f"Cleaning up temporary raw file: {super_raw_path}")
    if os.path.exists(super_raw_path):
        os.remove(super_raw_path)

    print("\n==============================================================")
    print("ROM Repackaging & AVB Signing Pipeline Complete!")
    print("Output files generated in work/:")
    print("  - system_a_raw.img")
    print("  - product_a_raw.img")
    print("  - vendor_a_raw.img")
    print("  - vendor_dlkm_a_raw.img")
    print("  - vbmeta_system.img")
    print("  - vbmeta_vendor.img")
    print("  - vbmeta.img")
    print("  - super.img")
    print("==============================================================")

if __name__ == "__main__":
    main()
