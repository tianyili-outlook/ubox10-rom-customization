#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Allwinner IMAGEWTY v3 Firmware Re-packager (Milestone M5)
"""

import struct
import os
import json
import binascii

# Structural constants
HEADER_MAGIC = b'IMAGEWTY'
MAIN_HEADER_SIZE = 96
FILE_HEADER_OFFSET = 1024

MANIFEST_PATH = "work/manifest.json"
EXTRACTED_DIR = "firmware/extracted"
OUTPUT_IMAGE = "x12-purified.img"

# Modified files mapping
MODIFIED_FILES = {
    "super.fex": "work/super.img",
    "vbmeta.fex": "work/vbmeta.img",
    "vbmeta_system.fex": "work/vbmeta_system.img",
    "vbmeta_vendor.fex": "work/vbmeta_vendor.img",
    "boot.fex": "work/boot.img"
}
if os.path.exists("work/vendor_boot.img"):
    MODIFIED_FILES["vendor_boot.fex"] = "work/vendor_boot.img"

CHECKSUM_CHUNK_BYTES = 16 * 1024 * 1024


def calculate_checksum(data):
    """Calculate the Allwinner word checksum without unpacking the whole image at once."""
    view = memoryview(data)
    full_length = len(view) - (len(view) % 4)
    checksum = 0
    for offset in range(0, full_length, CHECKSUM_CHUNK_BYTES):
        chunk_length = min(CHECKSUM_CHUNK_BYTES, full_length - offset)
        words_count = chunk_length // 4
        checksum = (
            checksum
            + sum(struct.unpack_from(f"<{words_count}I", view, offset))
        ) & 0xffffffff
    if full_length != len(view):
        checksum = (
            checksum
            + int.from_bytes(view[full_length:].tobytes(), "little")
        ) & 0xffffffff
    return checksum

def main():
    print("==============================================================")
    print("Starting Allwinner Firmware Container Repackaging")
    print("==============================================================")

    if not os.path.isfile(MANIFEST_PATH):
        print(f"ERROR: manifest.json not found at {MANIFEST_PATH}")
        return

    with open(MANIFEST_PATH, 'r') as f:
        manifest = json.load(f)

    original_files = manifest["files"]
    num_files = manifest["main_header"]["num_files"]
    
    # We will compute the new layout dynamically
    # Start offset for files: directly after the last file header
    # 1024 + 1024 * num_files
    start_offset = FILE_HEADER_OFFSET + 1024 * num_files
    print(f"First file offset: {start_offset}")

    # Prepare to compile the files data and update headers in memory
    compiled_files_data = {}
    
    # First pass: load and process all files, calculate checksums dynamically
    print("\n--- Processing and recalculating partition checksums ---")
    
    # We need to map filenames to their calculated checksums to update companion V-files
    calculated_checksums = {}

    # Standard sorting by index
    sorted_files = sorted(original_files, key=lambda x: x["index"])

    # Load/compile actual file content first for main files
    for entry in sorted_files:
        filename = entry["filename"]
        # Skip V-files for now, they depend on main files
        if filename.startswith('V') and len(filename) > 5 and filename[1:] in [f["filename"] for f in sorted_files]:
            continue

        # Load file data
        if filename in MODIFIED_FILES:
            fpath = MODIFIED_FILES[filename]
            print(f"[*] Loading MODIFIED file: {filename} from {fpath}")
        else:
            fpath = os.path.join(EXTRACTED_DIR, filename)
            # print(f"[*] Loading original file: {filename} from {fpath}")
            
        with open(fpath, 'rb') as f:
            data = f.read()

        compiled_files_data[filename] = data
        calculated_checksums[filename] = calculate_checksum(data)

    # Second pass: generate/process companion V-files
    for entry in sorted_files:
        filename = entry["filename"]
        if filename.startswith('V') and len(filename) > 5:
            main_filename = filename[1:]
            # Check if this V-file corresponds to a main partition we processed
            if main_filename in calculated_checksums:
                chksum = calculated_checksums[main_filename]
                print(f"[+] Generating companion {filename} -> Checksum: {hex(chksum)}")
                # V-file format: 4-byte checksum, padded to 16 bytes
                v_data = struct.pack('<I', chksum) + b'\x00' * 12
                compiled_files_data[filename] = v_data
            else:
                # Load original V-file
                fpath = os.path.join(EXTRACTED_DIR, filename)
                with open(fpath, 'rb') as f:
                    compiled_files_data[filename] = f.read()

    # Third pass: lay out the files, calculate offsets, and format file headers
    print("\n--- Constructing file headers and calculating offsets ---")
    current_offset = start_offset
    new_file_headers = []

    for entry in sorted_files:
        filename = entry["filename"]
        data = compiled_files_data[filename]
        
        orig_len = len(data)
        # Pad to multiple of 1024 bytes for Allwinner alignment
        remainder = orig_len % 1024
        if remainder != 0:
            padded_data = data + b'\x00' * (1024 - remainder)
        else:
            padded_data = data
            
        stored_len = len(padded_data)
        
        # Load the original file header to preserve all metadata fields
        # Original offset in firmware container file was header_offset
        orig_header_offset = entry["header_offset"]
        
        # Read the raw original file header from original image if possible,
        # otherwise we construct it from original manifest values.
        # Since we have the original firmware image 'x12-1024.img', we can read the raw header directly
        # to preserve all original unknown fields (e.g. unknown_0, filename_len, etc.)!
        # Let's open original firmware image to read raw header:
        raw_header = bytearray(1024)
        with open("x12-1024.img", "rb") as f_orig:
            f_orig.seek(orig_header_offset)
            raw_header[:1024] = f_orig.read(1024)
            
        # Overwrite the updated fields: stored_len (uint64), orig_len (uint64), offset (uint64)
        # In IMAGEWTY v3, these fields are at offset 292 (24 bytes total)
        struct.pack_into('<QQQ', raw_header, 292, stored_len, orig_len, current_offset)
        
        new_file_headers.append((current_offset, padded_data, raw_header))
        print(f"  File {entry['index']:<2}: {filename:<25} | Offset: {hex(current_offset):<10} | Length: {orig_len:<10} (Stored: {stored_len})")
        
        current_offset += stored_len

    final_image_size = current_offset
    print(f"\nFinal compiled firmware image size: {final_image_size} bytes ({final_image_size / (1024*1024):.2f} MB)")

    # 4. Read and construct main header
    # Let's read the original main header from x12-1024.img
    with open("x12-1024.img", "rb") as f_orig:
        raw_main_header = bytearray(f_orig.read(MAIN_HEADER_SIZE))
        
    # Update image size field at fields[5] -> byte offset 24 (uint32)
    struct.pack_into('<I', raw_main_header, 24, final_image_size)

    # 5. Write everything to output image
    print(f"\nWriting to {OUTPUT_IMAGE}...")
    with open(OUTPUT_IMAGE, 'wb') as out_f:
        # Write main header
        out_f.write(raw_main_header)
        # Pad to 1024 bytes (start of file headers)
        out_f.write(b'\x00' * (FILE_HEADER_OFFSET - len(raw_main_header)))
        
        # Write all 46 file headers
        for _, _, raw_hdr in new_file_headers:
            out_f.write(raw_hdr)
            
        # Write file data blocks
        for offset, padded_data, _ in new_file_headers:
            # Verify we are writing at the expected offset
            curr_pos = out_f.tell()
            if curr_pos != offset:
                # Pad if there's any gap (should not happen)
                out_f.write(b'\x00' * (offset - curr_pos))
            out_f.write(padded_data)

    print("\n==============================================================")
    print(f"SUCCESS: Rebuilt Allwinner firmware saved to '{OUTPUT_IMAGE}'")
    print("==============================================================")

if __name__ == '__main__':
    main()
