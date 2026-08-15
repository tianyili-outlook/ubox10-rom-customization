#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 4 ]]; then
  echo "usage: $0 TARGET_SYSTEM_IMAGE TARGET_MOUNT REFERENCE_SYSTEM_IMAGE REFERENCE_MOUNT" >&2
  exit 2
fi

target_image=$1
target_mount=$2
reference_image=$3
reference_mount=$4

[[ $(id -u) -eq 0 ]] || { echo "must run as root" >&2; exit 2; }
[[ -f $target_image ]] || { echo "target system image not found: $target_image" >&2; exit 2; }
[[ -f $reference_image ]] || { echo "reference system image not found: $reference_image" >&2; exit 2; }
[[ -d $target_mount && -d $reference_mount ]] || { echo "mount directory missing" >&2; exit 2; }
mountpoint -q "$target_mount" && { echo "target mount is already in use" >&2; exit 2; }
mountpoint -q "$reference_mount" && { echo "reference mount is already in use" >&2; exit 2; }

cleanup() {
  mountpoint -q "$reference_mount" && umount "$reference_mount" || true
  mountpoint -q "$target_mount" && umount "$target_mount" || true
}
trap cleanup EXIT INT TERM

check_target_ext4() {
  set +e
  e2fsck -fy "$target_image"
  status=$?
  set -e
  [[ $status -le 1 ]] || return "$status"
}

check_target_ext4
mount -o loop,rw "$target_image" "$target_mount"
mount -o loop,ro "$reference_image" "$reference_mount"

source_dir=$reference_mount/system/apex/com.android.vndk.current
target_parent=$target_mount/system/apex
target_dir=$target_parent/com.android.vndk.current

[[ -d $source_dir && ! -L $source_dir ]] || { echo "Test8r2 VNDK APEX source is missing" >&2; exit 1; }
[[ -d $target_parent && ! -L $target_parent ]] || { echo "target /system/apex is not canonical" >&2; exit 1; }
[[ ! -e $target_dir && ! -L $target_dir ]] || { echo "refusing to replace an existing VNDK APEX" >&2; exit 1; }
[[ $(sha256sum "$source_dir/apex_manifest.pb" | cut -d' ' -f1) == 4b4b240c316eba192b815f3480e643945a02b135ce616126533e7cb750809ea3 ]] || {
  echo "Test8r2 VNDK manifest identity mismatch" >&2
  exit 1
}
[[ $(sha256sum "$source_dir/lib/libaudioroute.so" | cut -d' ' -f1) == bb5393ce70cd1a4ad9ed62814339ca3695788532242708b0d46daed87d603623 ]] || {
  echo "Test8r2 libaudioroute identity mismatch" >&2
  exit 1
}

cp -a --preserve=all "$source_dir" "$target_dir"
sync
umount "$reference_mount"
umount "$target_mount"
check_target_ext4
