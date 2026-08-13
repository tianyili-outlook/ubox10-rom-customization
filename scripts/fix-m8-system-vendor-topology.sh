#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 SYSTEM_EXT4_IMAGE MOUNT_DIRECTORY" >&2
  exit 2
fi

image=$1
mount_dir=$2

[[ $(id -u) -eq 0 ]] || { echo "must run as root" >&2; exit 2; }
[[ -f $image ]] || { echo "system image not found: $image" >&2; exit 2; }
[[ -d $mount_dir ]] || { echo "mount directory not found: $mount_dir" >&2; exit 2; }
mountpoint -q "$mount_dir" && { echo "mount directory is already in use: $mount_dir" >&2; exit 2; }

cleanup() {
  if mountpoint -q "$mount_dir"; then
    umount "$mount_dir"
  fi
}
trap cleanup EXIT INT TERM

check_ext4() {
  set +e
  e2fsck -fy "$image"
  status=$?
  set -e
  [[ $status -le 1 ]] || return "$status"
}

check_ext4
mount -o loop,rw "$image" "$mount_dir"

vendor=$mount_dir/vendor
system_vendor=$mount_dir/system/vendor

[[ -L $vendor ]] || { echo "expected /vendor source symlink" >&2; exit 1; }
[[ $(readlink "$vendor") == /system/vendor ]] || { echo "unexpected /vendor source target" >&2; exit 1; }
[[ -d $system_vendor && ! -L $system_vendor ]] || { echo "expected /system/vendor source directory" >&2; exit 1; }

for target in product vendor_dlkm oem; do
  [[ -d $mount_dir/$target && ! -L $mount_dir/$target ]] || {
    echo "non-canonical early mount target before repair: /$target" >&2
    exit 1
  }
  [[ $(realpath "$mount_dir/$target") == "$mount_dir/$target" ]] || {
    echo "realpath mismatch before repair: /$target" >&2
    exit 1
  }
done

rm -- "$vendor"
find "$system_vendor" -xdev -depth -delete
mkdir "$vendor"
chown 0:2000 "$vendor"
chmod 0755 "$vendor"
ln -s /vendor "$system_vendor"
chown -h 0:0 "$system_vendor"

python3 - "$vendor" "$system_vendor" <<'PY'
import os
import sys

label = b"u:object_r:vendor_file:s0\0"
for path in sys.argv[1:]:
    os.setxattr(path, b"security.selinux", label, follow_symlinks=False)
PY

sync
umount "$mount_dir"

# Android image assembly records root symlinks as mode 0644; match the
# bootable Test8r2 topology exactly instead of leaving ln(1)'s 0777 mode.
debugfs -w -R 'set_inode_field /system/vendor mode 0120644' "$image"
check_ext4

debugfs -R 'stat /vendor' "$image" 2>&1 | grep -q 'Type: directory.*Mode:  0755'
debugfs -R 'stat /system/vendor' "$image" 2>&1 | grep -q 'Type: symlink.*Mode:  0644'
debugfs -R 'stat /system/vendor' "$image" 2>&1 | grep -q 'Fast link dest: "/vendor"'
