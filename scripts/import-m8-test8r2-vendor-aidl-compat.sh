#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "usage: $0 SYSTEM_EXT4_IMAGE MOUNT_DIRECTORY SOURCE_DIRECTORY" >&2
  exit 2
fi

image=$1
mount_dir=$2
source_dir=$3

[[ $(id -u) -eq 0 ]] || { echo "must run as root" >&2; exit 2; }
[[ -f $image ]] || { echo "system image not found: $image" >&2; exit 2; }
[[ -d $mount_dir ]] || { echo "mount directory not found: $mount_dir" >&2; exit 2; }
[[ -d $source_dir ]] || { echo "source directory not found: $source_dir" >&2; exit 2; }
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
target_dir=$mount_dir/system/lib
[[ -d $target_dir && ! -L $target_dir ]] || { echo "missing canonical /system/lib" >&2; exit 1; }

names=(
  android.hardware.light-V1-ndk_platform.so
  android.hardware.rebootescrow-V1-ndk_platform.so
)
hashes=(
  57ed3a999d158ee449d6621897275610b0479b0f06b7efb1005af397099bf663
  f26aa210060d449aa2d0ed8b7341db28ba072a6f1dd4af31bb2005e427636ab0
)

for index in "${!names[@]}"; do
  name=${names[$index]}
  source=$source_dir/$name
  target=$target_dir/$name
  [[ -f $source && ! -L $source ]] || { echo "missing regular source: $source" >&2; exit 1; }
  [[ ! -e $target && ! -L $target ]] || { echo "refusing to replace existing target: $target" >&2; exit 1; }
  [[ $(sha256sum "$source" | cut -d' ' -f1) == "${hashes[$index]}" ]] || {
    echo "source SHA-256 mismatch: $name" >&2
    exit 1
  }
  install -o 0 -g 0 -m 0644 "$source" "$target"
done

python3 - "$target_dir" "${names[@]}" <<'PY'
import os
import stat
import sys

root = sys.argv[1]
label = b"u:object_r:system_lib_file:s0\0"
for name in sys.argv[2:]:
    path = os.path.join(root, name)
    os.setxattr(path, b"security.selinux", label, follow_symlinks=False)
    value = os.lstat(path)
    if not stat.S_ISREG(value.st_mode) or stat.S_IMODE(value.st_mode) != 0o644:
        raise SystemExit(f"invalid target type or mode: {path}")
    if value.st_uid != 0 or value.st_gid != 0:
        raise SystemExit(f"invalid target owner: {path}")
PY

sync
umount "$mount_dir"
check_ext4
