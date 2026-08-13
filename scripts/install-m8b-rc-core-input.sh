#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 4 ]]; then
  echo "usage: $0 SYSTEM_EXT4_IMAGE MOUNT_DIRECTORY DISABLED_MULTI_IR_RC SUNXI_IR_KL" >&2
  exit 2
fi

image=$1
mount_dir=$2
multi_ir_rc=$3
sunxi_ir_kl=$4

[[ $(id -u) -eq 0 ]] || { echo "must run as root" >&2; exit 2; }
[[ -f $image && -d $mount_dir && -f $multi_ir_rc && -f $sunxi_ir_kl ]] || {
  echo "missing image, mount directory, or generated input source" >&2
  exit 2
}
mountpoint -q "$mount_dir" && { echo "mount directory is already in use" >&2; exit 2; }

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

rc_target="$mount_dir/system/etc/init/multi_ir.rc"
kl_target="$mount_dir/system/usr/keylayout/sunxi-ir.kl"
[[ -f $rc_target && ! -L $rc_target && -f $kl_target && ! -L $kl_target ]] || {
  echo "r13 remote target is missing or not a regular file" >&2
  exit 1
}
[[ $(sha256sum "$rc_target" | cut -d' ' -f1) == 7016a9c2648c4ecd4ae3977e1169c4cfa394ff6e721664e0a5a1fd128bbb1bbd ]] || {
  echo "r13 multi_ir.rc identity mismatch" >&2
  exit 1
}
[[ $(sha256sum "$kl_target" | cut -d' ' -f1) == 89f237061963cc333e55a3e3451e175be6144794493fe0315122a7986f77ddda ]] || {
  echo "r13 sunxi-ir.kl identity mismatch" >&2
  exit 1
}

install -o 0 -g 0 -m 0644 "$multi_ir_rc" "$rc_target"
install -o 0 -g 0 -m 0644 "$sunxi_ir_kl" "$kl_target"

python3 - "$rc_target" "$kl_target" <<'PY'
import os
import stat
import sys

label = b"u:object_r:system_file:s0\0"
for path in sys.argv[1:]:
    os.setxattr(path, b"security.selinux", label, follow_symlinks=False)
    value = os.lstat(path)
    if not stat.S_ISREG(value.st_mode) or stat.S_IMODE(value.st_mode) != 0o644:
        raise SystemExit(f"invalid target type or mode: {path}")
    if value.st_uid != 0 or value.st_gid != 0:
        raise SystemExit(f"invalid target owner: {path}")
PY

grep -qx '        disabled' "$rc_target"
! grep -q 'MOUSE' "$kl_target"
sync
umount "$mount_dir"
check_ext4
