#!/usr/bin/env python3
import argparse
import binascii
import json
import os
import struct
import sys

# IMAGEWTY v3 structural constants
HEADER_MAGIC = b'IMAGEWTY'
MAIN_HEADER_SIZE = 96
FILE_HEADER_OFFSET = 1024

def parse_main_header(f):
    f.seek(0)
    data = f.read(MAIN_HEADER_SIZE)
    if len(data) < MAIN_HEADER_SIZE:
        raise ValueError("File is too small to contain the main header.")
        
    magic, header_version, header_size = struct.unpack('<8sII', data[:16])
    if magic != HEADER_MAGIC:
        raise ValueError(f"Invalid magic bytes: {magic}. Expected: {HEADER_MAGIC}")
        
    # Unpack the entire main header
    # format: <8s22I (8 bytes magic, 22 uint32 fields = 96 bytes)
    fields = struct.unpack('<8s22I', data)
    ram_base = fields[3]
    version = fields[4]
    image_size = fields[5]
    num_files = fields[14]
    
    return {
        "magic": magic.decode('ascii', errors='ignore'),
        "header_version": header_version,
        "header_size": header_size,
        "ram_base": ram_base,
        "version": version,
        "image_size": image_size,
        "num_files": num_files
    }

def parse_file_headers(f, num_files):
    files = []
    current_offset = FILE_HEADER_OFFSET
    
    for i in range(num_files):
        f.seek(current_offset)
        hdr_data = f.read(1024)
        if len(hdr_data) < 1024:
            raise ValueError(f"Failed to read 1024 bytes for file header at offset {current_offset}")
            
        filename_len, total_header_size = struct.unpack('<II', hdr_data[:8])
        maintype = hdr_data[8:16].decode('ascii', errors='ignore').strip('\x00').strip()
        subtype = hdr_data[16:32].decode('ascii', errors='ignore').strip('\x00').strip()
        unknown_0 = struct.unpack('<I', hdr_data[32:36])[0]
        
        # Extract filename (256 bytes starting at offset 36)
        filename_raw = hdr_data[36:36+256]
        filename = filename_raw.decode('ascii', errors='ignore').split('\x00')[0]
        
        # In v3, metadata fields (stored_len, orig_len, offset) start at offset 292
        stored_len, orig_len, offset = struct.unpack('<QQQ', hdr_data[292:292+24])
        
        files.append({
            "index": i,
            "header_offset": current_offset,
            "total_header_size": total_header_size,
            "maintype": maintype,
            "subtype": subtype,
            "filename": filename,
            "stored_len": stored_len,
            "orig_len": orig_len,
            "offset": offset
        })
        current_offset += total_header_size
        
    return files

def calculate_checksum(f, offset, length):
    f.seek(offset)
    chksum = 0
    bytes_read = 0
    chunk_size = 4 * 1024 * 1024 # 4MB buffer
    
    while bytes_read < length:
        to_read = min(chunk_size, length - bytes_read)
        chunk = f.read(to_read)
        if not chunk:
            break
            
        # If the read chunk length is not a multiple of 4, pad it with zeros
        remainder = len(chunk) % 4
        if remainder != 0:
            chunk += b'\x00' * (4 - remainder)
            
        words_count = len(chunk) // 4
        words = struct.unpack(f'<{words_count}I', chunk)
        chksum = (chksum + sum(words)) & 0xffffffff
        bytes_read += len(chunk)
        
    return chksum

def cmd_list(args):
    with open(args.image, 'rb') as f:
        main_header = parse_main_header(f)
        files = parse_file_headers(f, main_header["num_files"])
        
    if args.json:
        # Save to JSON file
        with open(args.json, 'w', encoding='utf-8') as out_f:
            json.dump({
                "main_header": main_header,
                "files": files
            }, out_f, indent=2)
        print(f"Manifest written to {args.json}")
    else:
        # Print table
        print(f"Image: {args.image}")
        print(f"Magic: {main_header['magic']}, Version: {hex(main_header['header_version'])}, Files: {main_header['num_files']}")
        print(f"{'Index':<5} | {'Filename':<25} | {'Maintype':<10} | {'Subtype':<18} | {'Offset (Hex)':<12} | {'Stored Len':<12} | {'Original Len':<12}")
        print("-" * 110)
        for file in files:
            print(f"{file['index']:<5} | {file['filename']:<25} | {file['maintype']:<10} | {file['subtype']:<18} | {hex(file['offset']):<12} | {file['stored_len']:<12} | {file['orig_len']:<12}")

def cmd_verify(args):
    with open(args.image, 'rb') as f:
        main_header = parse_main_header(f)
        files = parse_file_headers(f, main_header["num_files"])
        
        # Build filename mapping (lowercase for case-insensitive matching)
        file_map = {file["filename"].lower(): file for file in files}
        
        results = []
        verified_count = 0
        failed_count = 0
        
        print(f"Verifying partition checksums in {args.image}...")
        for file in files:
            name = file["filename"]
            # Look for companion 'V' files
            if name.startswith('V') and name[1:].lower() in file_map:
                main_file = file_map[name[1:].lower()]
                
                # Read expected checksum from V file (first 4 bytes)
                f.seek(file["offset"])
                v_data = f.read(4)
                if len(v_data) < 4:
                    print(f"[-] {name}: Failed to read expected checksum from V-file.")
                    results.append({"companion": name, "main": main_file["filename"], "status": "read_error"})
                    failed_count += 1
                    continue
                expected_sum = struct.unpack('<I', v_data)[0]
                
                # Calculate checksum of the main file
                calculated_sum = calculate_checksum(f, main_file["offset"], main_file["stored_len"])
                
                if expected_sum == calculated_sum:
                    print(f"[+] {main_file['filename']:<20} (verified by {name:<21}) -> Checksum OK (hex={hex(expected_sum)})")
                    results.append({"companion": name, "main": main_file["filename"], "status": "OK", "checksum": hex(expected_sum)})
                    verified_count += 1
                else:
                    print(f"[-] {main_file['filename']:<20} (verified by {name:<21}) -> Checksum MISMATCH! Expected={hex(expected_sum)}, Calculated={hex(calculated_sum)}")
                    results.append({"companion": name, "main": main_file["filename"], "status": "mismatch", "expected": hex(expected_sum), "calculated": hex(calculated_sum)})
                    failed_count += 1
                    
        print("-" * 60)
        print(f"Verification complete: {verified_count} partitions OK, {failed_count} mismatches/errors.")
        if failed_count > 0:
            sys.exit(1)

def cmd_extract(args):
    out_dir = args.out or 'firmware/extracted'
    os.makedirs(out_dir, exist_ok=True)
    
    with open(args.image, 'rb') as f:
        main_header = parse_main_header(f)
        files = parse_file_headers(f, main_header["num_files"])
        
        target_files = files
        if args.file:
            target_files = [file for file in files if file["filename"].lower() == args.file.lower()]
            if not target_files:
                print(f"Error: File '{args.file}' not found in firmware image.")
                sys.exit(1)
                
        print(f"Extracting {len(target_files)} files to '{out_dir}'...")
        for file in target_files:
            filename = file["filename"]
            offset = file["offset"]
            # We extract orig_len bytes to avoid trailing alignment padding
            length = file["orig_len"]
            
            dest_path = os.path.join(out_dir, filename)
            print(f"[*] Extracting {filename} ({length} bytes) at offset {hex(offset)}...")
            
            f.seek(offset)
            with open(dest_path, 'wb') as out_f:
                bytes_written = 0
                chunk_size = 4 * 1024 * 1024 # 4MB
                while bytes_written < length:
                    to_read = min(chunk_size, length - bytes_written)
                    chunk = f.read(to_read)
                    if not chunk:
                        break
                    out_f.write(chunk)
                    bytes_written += len(chunk)
                    
        print("[+] Extraction complete.")

def main():
    parser = argparse.ArgumentParser(description="Allwinner IMAGEWTY (PhoenixCard) firmware customization utility")
    subparsers = parser.add_subparsers(dest="command", required=True, help="Subcommands")
    
    # List command
    parser_list = subparsers.add_parser("list", help="List files in the firmware image")
    parser_list.add_argument("image", help="Path to Allwinner firmware image (.img)")
    parser_list.add_argument("--json", help="Path to write JSON manifest output")
    parser_list.set_defaults(func=cmd_list)
    
    # Verify command
    parser_verify = subparsers.add_parser("verify", help="Verify partition checksums using companion V-files")
    parser_verify.add_argument("image", help="Path to Allwinner firmware image (.img)")
    parser_verify.set_defaults(func=cmd_verify)
    
    # Extract command
    parser_extract = subparsers.add_parser("extract", help="Extract partitions/files from the firmware image")
    parser_extract.add_argument("image", help="Path to Allwinner firmware image (.img)")
    parser_extract.add_argument("-o", "--out", help="Output directory (default: firmware/extracted)")
    parser_extract.add_argument("-f", "--file", help="Specific filename to extract (case-insensitive)")
    parser_extract.set_defaults(func=cmd_extract)
    
    args = parser.parse_args()
    args.func(args)

if __name__ == '__main__':
    main()
