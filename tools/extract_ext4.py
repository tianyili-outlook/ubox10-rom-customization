import os
import sys

# Ensure user site-packages is in path
sys.path.insert(0, r'C:\Users\tiany\AppData\Roaming\Python\Python313\site-packages')
from ext4 import Volume

def extract_inode(vol, inode, dest_path, stats):
    mode = inode.i_mode
    file_type = mode & 0xF000
    
    if file_type == 0x4000: # Directory
        os.makedirs(dest_path, exist_ok=True)
        stats['dirs'] += 1
        try:
            for entry, ft in inode.opendir():
                name = entry.name_bytes
                if name in (b'.', b'..'):
                    continue
                name_str = name.decode('utf-8', errors='ignore')
                child_dest = os.path.join(dest_path, name_str)
                child_inode = vol.inodes[entry.inode]
                extract_inode(vol, child_inode, child_dest, stats)
        except Exception as e:
            print(f"Error reading directory {dest_path}: {e}")
            
    elif file_type == 0x8000: # Regular file
        parent_dir = os.path.dirname(dest_path)
        os.makedirs(parent_dir, exist_ok=True)
        stats['files'] += 1
        try:
            # Check if file has inline data or standard blocks
            stream = inode.open()
            with open(dest_path, 'wb') as out_f:
                while True:
                    chunk = stream.read(4 * 1024 * 1024)  # 4MB chunks
                    if not chunk:
                        break
                    out_f.write(chunk)
            # Print periodic progress
            if stats['files'] % 1000 == 0:
                print(f"Extracted {stats['files']} files...")
        except Exception as e:
            print(f"Error writing file {dest_path}: {e}")
            
    elif file_type == 0xA000: # Symlink
        parent_dir = os.path.dirname(dest_path)
        os.makedirs(parent_dir, exist_ok=True)
        stats['symlinks'] += 1
        try:
            target = inode.readlink()
            target_str = target.decode('utf-8', errors='ignore')
            with open(dest_path + '.symlink', 'w', encoding='utf-8') as out_f:
                out_f.write(target_str)
        except Exception as e:
            print(f"Error writing symlink {dest_path}: {e}")

def main():
    if len(sys.argv) < 3:
        print("Usage: python extract_ext4.py <ext4_image_path> <dest_dir>")
        sys.exit(1)
        
    img_path = sys.argv[1]
    dest_dir = sys.argv[2]
    
    print(f"Opening {img_path}...")
    stats = {'dirs': 0, 'files': 0, 'symlinks': 0}
    with open(img_path, 'rb') as f:
        vol = Volume(f)
        print("Extracting files...")
        extract_inode(vol, vol.root, dest_dir, stats)
        
    print(f"\nSUCCESS: Extracted {img_path} to {dest_dir}")
    print(f"Statistics: Directories={stats['dirs']}, Files={stats['files']}, Symlinks={stats['symlinks']}")

if __name__ == '__main__':
    main()
