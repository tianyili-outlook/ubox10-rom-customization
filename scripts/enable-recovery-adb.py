#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UBOX10 Recovery ADB Enablement Tool (Milestone M6)
"""

import os
import sys
import struct
import subprocess
import lz4.block

# Paths
TOOLS_DIR = "tools"
WORK_DIR = "work"
BOOT_DIR = os.path.join(WORK_DIR, "boot")
ORIG_BOOT_FEX = "firmware/extracted/boot.fex"
REBUILT_RAMDISK = os.path.join(BOOT_DIR, "ramdisk_rebuilt")
REBUILT_BOOT_IMG = os.path.join(WORK_DIR, "boot.img")

UNPACK_BOOTIMG = os.path.join(TOOLS_DIR, "unpack_bootimg.py")
MKBOOTIMG = os.path.join(TOOLS_DIR, "mkbootimg.py")
AVBTOOL = os.path.join(TOOLS_DIR, "avbtool.py")

def align_to_4(val):
    return (val + 3) & ~3

def decompress_ramdisk(ramdisk_path):
    print(f"Decompressing original ramdisk from {ramdisk_path}...")
    with open(ramdisk_path, 'rb') as f:
        magic = f.read(4)
        if magic != b'\x02\x21\x4c\x18':
            raise ValueError(f"Invalid LZ4 magic: {magic.hex()}")
            
        decompressed_data = bytearray()
        block_idx = 0
        while True:
            size_data = f.read(4)
            if len(size_data) < 4:
                break
            block_size = struct.unpack('<I', size_data)[0]
            if block_size == 0:
                break
            compressed_block = f.read(block_size)
            decomp_block = lz4.block.decompress(compressed_block, uncompressed_size=8388608)
            decompressed_data.extend(decomp_block)
            block_idx += 1
            
    print(f"Decompressed ramdisk size: {len(decompressed_data)} bytes across {block_idx} blocks.")
    return bytes(decompressed_data)

def parse_cpio(data):
    offset = 0
    total_len = len(data)
    entries = []
    
    while offset < total_len:
        if offset + 110 > total_len:
            break
        magic = data[offset:offset+6]
        if magic != b'070701':
            break
            
        fields_raw = data[offset+6:offset+110]
        fields = [int(fields_raw[i:i+8], 16) for i in range(0, 104, 8)]
        
        mode = fields[1]
        filesize = fields[6]
        namesize = fields[11]
        
        name_start = offset + 110
        name_end = name_start + namesize
        filename_bytes = data[name_start:name_end]
        filename = filename_bytes.split(b'\x00')[0].decode('utf-8', errors='ignore')
        
        data_start = align_to_4(name_end)
        data_end = data_start + filesize
        file_data = data[data_start:data_end]
        
        next_offset = align_to_4(data_end)
        
        entries.append({
            'magic': magic,
            'fields': fields,
            'filename_bytes': filename_bytes,
            'filename': filename,
            'file_data': file_data
        })
        
        if filename == "TRAILER!!!":
            trailing_padding = data[next_offset:]
            entries.append({
                'trailing_padding': trailing_padding
            })
            break
            
        offset = next_offset
        
    return entries

def serialize_cpio(entries):
    out = bytearray()
    for entry in entries:
        if 'trailing_padding' in entry:
            out.extend(entry['trailing_padding'])
            break
            
        # Serialize header
        header = entry['magic']
        for val in entry['fields']:
            header += f"{val:08x}".encode()
        out.extend(header)
        out.extend(entry['filename_bytes'])
        
        # Align header + name
        header_len = len(header) + len(entry['filename_bytes'])
        aligned_header_len = align_to_4(header_len)
        out.extend(b'\x00' * (aligned_header_len - header_len))
        
        # Write data
        out.extend(entry['file_data'])
        
        # Align data
        data_len = len(entry['file_data'])
        aligned_data_len = align_to_4(data_len)
        out.extend(b'\x00' * (aligned_data_len - data_len))
        
    return bytes(out)

def compress_ramdisk_legacy_lz4(cpio_data):
    print("Compressing CPIO to legacy LZ4 block format (High Compression)...")
    chunk_size = 8388608  # 8 MB chunks
    compressed_bytes = bytearray(b'\x02\x21\x4c\x18')  # Magic
    
    offset = 0
    total_len = len(cpio_data)
    block_idx = 0
    
    while offset < total_len:
        chunk = cpio_data[offset:offset+chunk_size]
        compressed_block = lz4.block.compress(chunk, mode='high_compression', compression=9, store_size=False)
        
        # Write 4-byte size (little-endian)
        compressed_bytes.extend(struct.pack('<I', len(compressed_block)))
        # Write compressed block
        compressed_bytes.extend(compressed_block)
        
        print(f"Compressed Block {block_idx}: {len(chunk)} -> {len(compressed_block)} bytes.")
        offset += chunk_size
        block_idx += 1
        
    return bytes(compressed_bytes)

def modify_properties(entries):
    print("Modifying prop.default to inject Recovery ADB configurations...")
    prop_entry = None
    for entry in entries:
        if entry.get('filename') == 'prop.default':
            prop_entry = entry
            break
            
    if not prop_entry:
        raise ValueError("Could not find prop.default in cpio archive!")
        
    prop_text = prop_entry['file_data'].decode('utf-8', errors='ignore')
    lines = prop_text.splitlines()
    
    new_props = {
        'ro.debuggable': '1',
        'ro.secure': '0',
        'persist.sys.usb.config': 'adb',
        'sys.usb.config': 'adb',
        'ro.adb.secure': '0',
        'service.adb.root': '1',
        'ro.build.type': 'userdebug'
    }
    
    modified_lines = []
    processed_keys = set()
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            modified_lines.append(line)
            continue
            
        if '=' in line:
            key, val = line.split('=', 1)
            key = key.strip()
            if key in new_props:
                modified_lines.append(f"{key}={new_props[key]}")
                processed_keys.add(key)
                print(f"  [Override] {key}: {val} -> {new_props[key]}")
            else:
                modified_lines.append(line)
        else:
            modified_lines.append(line)
            
    # Append any keys that weren't in the original prop.default
    for key, val in new_props.items():
        if key not in processed_keys:
            modified_lines.append(f"{key}={val}")
            print(f"  [Add] {key}={val}")
            
    new_prop_text = "\n".join(modified_lines) + "\n"
    new_prop_data = new_prop_text.encode('utf-8')
    
    # Update size in cpio metadata fields
    # fields[6] is filesize
    prop_entry['file_data'] = new_prop_data
    prop_entry['fields'][6] = len(new_prop_data)
    print("prop.default successfully updated!")

def modify_init_rc(entries):
    print("Modifying init.recovery.sun50iw9p1.rc to force USB configuration trigger...")
    rc_entry = None
    for entry in entries:
        if entry.get('filename') == 'init.recovery.sun50iw9p1.rc':
            rc_entry = entry
            break
            
    if not rc_entry:
        raise ValueError("Could not find init.recovery.sun50iw9p1.rc in cpio archive!")
        
    rc_text = rc_entry['file_data'].decode('utf-8', errors='ignore')
    
    # Revert any previous custom modifications by truncating to standard end of file
    idx = rc_text.find("setenv HOSTNAME console")
    if idx != -1:
        rc_text = rc_text[:idx + len("setenv HOSTNAME console")] + "\n"
        
    # Append the manual ConfigFS setup and adbd start sequence directly on boot
    custom_trigger = (
        "\n\non boot\n"
        "    mount configfs none /config\n"
        "    mkdir /config/usb_gadget/g1 0770 shell shell\n"
        "    write /config/usb_gadget/g1/idVendor 0x18D1\n"
        "    write /config/usb_gadget/g1/idProduct 0xD001\n"
        "    mkdir /config/usb_gadget/g1/strings/0x409 0770\n"
        "    write /config/usb_gadget/g1/strings/0x409/serialnumber \"ubox10_recovery\"\n"
        "    write /config/usb_gadget/g1/strings/0x409/manufacturer \"Google\"\n"
        "    write /config/usb_gadget/g1/strings/0x409/product \"Recovery ADB\"\n"
        "    mkdir /config/usb_gadget/g1/functions/ffs.adb\n"
        "    mkdir /config/usb_gadget/g1/configs/b.1 0777 shell shell\n"
        "    mkdir /config/usb_gadget/g1/configs/b.1/strings/0x409 0770 shell shell\n"
        "    write /config/usb_gadget/g1/configs/b.1/strings/0x409/configuration \"adb\"\n"
        "    symlink /config/usb_gadget/g1/functions/ffs.adb /config/usb_gadget/g1/configs/b.1/f1\n"
        "    mkdir /dev/usb-ffs 0775 shell shell\n"
        "    mkdir /dev/usb-ffs/adb 0770 shell shell\n"
        "    mount functionfs adb /dev/usb-ffs/adb uid=2000,gid=2000\n"
        "    start adbd\n"
        "    write /config/usb_gadget/g1/UDC \"5100000.udc-controller\"\n"
    )
    
    new_rc_text = rc_text + custom_trigger
    new_rc_data = new_rc_text.encode('utf-8')
    rc_entry['file_data'] = new_rc_data
    rc_entry['fields'][6] = len(new_rc_data)
    print("init.recovery.sun50iw9p1.rc successfully updated with manual ConfigFS sequence!")

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
    print("Starting Recovery ADB Enablement & boot.img Rebuilder")
    print("==============================================================")
    
    # Ensure BOOT_DIR exists
    os.makedirs(BOOT_DIR, exist_ok=True)
    
    # 1. Unpack original boot.fex if kernel/ramdisk do not exist
    orig_ramdisk_path = os.path.join(BOOT_DIR, "ramdisk")
    orig_kernel_path = os.path.join(BOOT_DIR, "kernel")
    
    if not os.path.isfile(orig_ramdisk_path) or not os.path.isfile(orig_kernel_path):
        print(f"Extracting kernel and ramdisk from original boot.fex: {ORIG_BOOT_FEX}")
        if not os.path.isfile(ORIG_BOOT_FEX):
            print(f"ERROR: Original {ORIG_BOOT_FEX} not found!")
            sys.exit(1)
        run_cmd([
            sys.executable, UNPACK_BOOTIMG,
            "--boot_img", ORIG_BOOT_FEX,
            "--out", BOOT_DIR
        ])
        
    # 2. Decompress ramdisk
    cpio_data = decompress_ramdisk(orig_ramdisk_path)
    
    # 3. Parse CPIO archive
    entries = parse_cpio(cpio_data)
    
    # 4. Modify prop.default
    modify_properties(entries)
    
    # 4b. Modify device-specific init.rc
    modify_init_rc(entries)
    
    # 5. Re-serialize CPIO
    new_cpio_data = serialize_cpio(entries)
    
    # 6. Re-compress legacy LZ4 ramdisk
    new_compressed_ramdisk = compress_ramdisk_legacy_lz4(new_cpio_data)
    
    # Save the new compressed ramdisk
    with open(REBUILT_RAMDISK, 'wb') as f:
        f.write(new_compressed_ramdisk)
    print(f"Recompressed ramdisk saved to {REBUILT_RAMDISK} (size: {len(new_compressed_ramdisk)} bytes)")
    
    # 7. Rebuild boot.img (header version 3)
    print("\n--- Packaging boot.img (mkbootimg) ---")
    run_cmd([
        sys.executable, MKBOOTIMG,
        "--header_version", "3",
        "--os_version", "12.0.0",
        "--os_patch_level", "2022-02",
        "--kernel", orig_kernel_path,
        "--ramdisk", REBUILT_RAMDISK,
        "--cmdline", "androidboot.selinux=permissive",
        "--output", REBUILT_BOOT_IMG
    ])
    
    # 8. Sign boot.img with AVB hash footer
    print("\n--- Signing boot.img with AVB hash footer ---")
    # Original salt: c52f504c468b5668e4a5e443f424a3dc26800dc95881d9562cb7cc56594b04f6
    run_cmd([
        sys.executable, AVBTOOL, "add_hash_footer",
        "--image", REBUILT_BOOT_IMG,
        "--partition_name", "boot",
        "--partition_size", "67108864",
        "--salt", "c52f504c468b5668e4a5e443f424a3dc26800dc95881d9562cb7cc56594b04f6"
    ])
    
    print("\n==============================================================")
    print("Recovery ADB boot.img compilation and signing COMPLETE!")
    print(f"Output saved to: {REBUILT_BOOT_IMG}")
    print("==============================================================")

if __name__ == "__main__":
    main()
