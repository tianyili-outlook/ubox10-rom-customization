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

paths=(
  system/bin/multi_ir
  system/etc/init/multi_ir.rc
  system/usr/keylayout/customer_ir_ff40.kl
  system/usr/keylayout/sunxi-ir.kl
  system/usr/keylayout/sunxi-ir-uinput.kl
  system/lib/libmultiirservice.so
  system/lib/libinput.so
)
hashes=(
  2a72f8fbcf29db3da9aa29ee61a95380b44b44dafdf8cadaadb41097262fc687
  7016a9c2648c4ecd4ae3977e1169c4cfa394ff6e721664e0a5a1fd128bbb1bbd
  db54f9843081ddc492f9bdd35e7ee341ebcb4562991513cb5b7a26bbbc74de39
  89f237061963cc333e55a3e3451e175be6144794493fe0315122a7986f77ddda
  1b54a9c2b39c8922407f4a806825496ae6e4f0e1c16b394d7c09465afb58b391
  02bbb53f33cd0aac2186a940b6e1b5d92539fada2a7a07e894dc65e138183a38
  764069a044e639a5567803fe530602a525fc66857413c6bc0e4c515040b1f557
)

check_ext4
mount -o loop,rw "$image" "$mount_dir"

for index in "${!paths[@]}"; do
  relative=${paths[$index]}
  source=$source_dir/$relative
  target=$mount_dir/$relative
  [[ -f $source && ! -L $source ]] || { echo "missing regular source: $source" >&2; exit 1; }
  [[ $(sha256sum "$source" | cut -d' ' -f1) == "${hashes[$index]}" ]] || {
    echo "source SHA-256 mismatch: $relative" >&2
    exit 1
  }
  if [[ $relative == system/lib/libinput.so ]]; then
    [[ -f $target && ! -L $target ]] || { echo "missing r11 libinput target" >&2; exit 1; }
    [[ $(sha256sum "$target" | cut -d' ' -f1) == d82dba765cab4ca6be42dbe8b6673ff34d97b80cd56d461a89468156caf9ffc2 ]] || {
      echo "r11 libinput identity mismatch" >&2
      exit 1
    }
  else
    [[ ! -e $target && ! -L $target ]] || { echo "refusing to replace existing target: $target" >&2; exit 1; }
  fi
done

install -o 0 -g 2000 -m 0755 "$source_dir/system/bin/multi_ir" "$mount_dir/system/bin/multi_ir"
install -o 0 -g 0 -m 0644 "$source_dir/system/etc/init/multi_ir.rc" "$mount_dir/system/etc/init/multi_ir.rc"
for name in customer_ir_ff40.kl sunxi-ir.kl sunxi-ir-uinput.kl; do
  install -o 0 -g 0 -m 0644 "$source_dir/system/usr/keylayout/$name" "$mount_dir/system/usr/keylayout/$name"
done
for name in libmultiirservice.so libinput.so; do
  install -o 0 -g 0 -m 0644 "$source_dir/system/lib/$name" "$mount_dir/system/lib/$name"
done

python3 - "$mount_dir" <<'PY'
import os
import stat
import sys

root = sys.argv[1]
contracts = {
    "system/bin/multi_ir": (0o755, 0, 2000, b"u:object_r:multi_ir_exec:s0\0"),
    "system/etc/init/multi_ir.rc": (0o644, 0, 0, b"u:object_r:system_file:s0\0"),
    "system/usr/keylayout/customer_ir_ff40.kl": (0o644, 0, 0, b"u:object_r:system_file:s0\0"),
    "system/usr/keylayout/sunxi-ir.kl": (0o644, 0, 0, b"u:object_r:system_file:s0\0"),
    "system/usr/keylayout/sunxi-ir-uinput.kl": (0o644, 0, 0, b"u:object_r:system_file:s0\0"),
    "system/lib/libmultiirservice.so": (0o644, 0, 0, b"u:object_r:system_lib_file:s0\0"),
    "system/lib/libinput.so": (0o644, 0, 0, b"u:object_r:system_lib_file:s0\0"),
}
for relative, (mode, uid, gid, label) in contracts.items():
    path = os.path.join(root, relative)
    os.setxattr(path, b"security.selinux", label, follow_symlinks=False)
    value = os.lstat(path)
    if not stat.S_ISREG(value.st_mode) or stat.S_IMODE(value.st_mode) != mode:
        raise SystemExit(f"invalid target type or mode: {path}")
    if value.st_uid != uid or value.st_gid != gid:
        raise SystemExit(f"invalid target owner: {path}")
PY

for index in "${!paths[@]}"; do
  relative=${paths[$index]}
  [[ $(sha256sum "$mount_dir/$relative" | cut -d' ' -f1) == "${hashes[$index]}" ]] || {
    echo "installed SHA-256 mismatch: $relative" >&2
    exit 1
  }
done

sync
umount "$mount_dir"
check_ext4
