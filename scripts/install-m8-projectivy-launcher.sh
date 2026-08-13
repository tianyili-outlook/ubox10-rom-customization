#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "usage: $0 SYSTEM_EXT4_IMAGE MOUNT_DIRECTORY PROJECTIVY_APK" >&2
  exit 2
fi

image=$1
mount_dir=$2
source_apk=$3

[[ $(id -u) -eq 0 ]] || { echo "must run as root" >&2; exit 2; }
[[ -f $image ]] || { echo "system image not found: $image" >&2; exit 2; }
[[ -d $mount_dir ]] || { echo "mount directory not found: $mount_dir" >&2; exit 2; }
[[ -f $source_apk && ! -L $source_apk ]] || { echo "launcher APK not found: $source_apk" >&2; exit 2; }
mountpoint -q "$mount_dir" && { echo "mount directory is already in use: $mount_dir" >&2; exit 2; }

expected_sha256=6818fc2db44411a605ca4d7067fb9d7227aaef2414cff42de58fe13e9321b47a
[[ $(sha256sum "$source_apk" | cut -d' ' -f1) == "$expected_sha256" ]] || {
  echo "Projectivy source SHA-256 mismatch" >&2
  exit 1
}

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
app_root=$mount_dir/system/app
target_dir=$app_root/ProjectivyLauncher
target_apk=$target_dir/ProjectivyLauncher.apk

[[ -d $app_root && ! -L $app_root ]] || { echo "missing canonical /system/app" >&2; exit 1; }
[[ ! -e $target_dir && ! -L $target_dir ]] || { echo "refusing to replace existing Launcher" >&2; exit 1; }

install -d -o 0 -g 0 -m 0755 "$target_dir"
install -o 0 -g 0 -m 0644 "$source_apk" "$target_apk"

python3 - "$target_dir" "$target_apk" <<'PY'
import os
import stat
import sys

label = b"u:object_r:system_file:s0\0"
directory, apk = sys.argv[1:]
for path in (directory, apk):
    os.setxattr(path, b"security.selinux", label, follow_symlinks=False)

directory_stat = os.lstat(directory)
apk_stat = os.lstat(apk)
if not stat.S_ISDIR(directory_stat.st_mode) or stat.S_IMODE(directory_stat.st_mode) != 0o755:
    raise SystemExit("invalid Launcher directory type or mode")
if not stat.S_ISREG(apk_stat.st_mode) or stat.S_IMODE(apk_stat.st_mode) != 0o644:
    raise SystemExit("invalid Launcher APK type or mode")
if (directory_stat.st_uid, directory_stat.st_gid, apk_stat.st_uid, apk_stat.st_gid) != (0, 0, 0, 0):
    raise SystemExit("invalid Launcher owner")
PY

sync
umount "$mount_dir"
check_ext4
