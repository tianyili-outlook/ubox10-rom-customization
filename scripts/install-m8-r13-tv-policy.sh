#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 5 ]]; then
  echo "usage: $0 SYSTEM_EXT4_IMAGE MOUNT_DIRECTORY AWTVPROVISION_APK PERMISSIONS_XML POWER_OVERLAY_APK" >&2
  exit 2
fi

image=$1
mount_dir=$2
provision_apk=$3
permissions_xml=$4
power_overlay=$5

[[ $(id -u) -eq 0 ]] || { echo "must run as root" >&2; exit 2; }
[[ -f $image && -d $mount_dir ]] || { echo "missing image or mount directory" >&2; exit 2; }
mountpoint -q "$mount_dir" && { echo "mount directory is already in use" >&2; exit 2; }

declare -A expected=(
  ["$provision_apk"]="d74df03c4bbab8adcfc543d9f34d98c87178a63d15f66785b1ee3d286edb68d8"
  ["$permissions_xml"]="98c3c29a10f4956bbab65f74e405e7b3f8df20c262a22ff7fcc755c0f92f7e6a"
  ["$power_overlay"]="b695200e1153f750b3bf1cd92228ee6e360ba7b12608cb56019d316017481c91"
)
for source in "$provision_apk" "$permissions_xml" "$power_overlay"; do
  [[ -f $source && ! -L $source ]] || { echo "missing regular source: $source" >&2; exit 1; }
  [[ $(sha256sum "$source" | cut -d' ' -f1) == "${expected[$source]}" ]] || {
    echo "source SHA-256 mismatch: $source" >&2
    exit 1
  }
done

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

targets=(
  "$mount_dir/system_ext/priv-app/AwTvProvision/AwTvProvision.apk"
  "$mount_dir/system_ext/etc/permissions/provision-permissions.xml"
  "$mount_dir/system_ext/overlay/M8TvPowerPolicyOverlay.apk"
)
for target in "${targets[@]}"; do
  [[ ! -e $target && ! -L $target ]] || { echo "refusing to replace existing target: $target" >&2; exit 1; }
done

install -d -o 0 -g 0 -m 0755 "$mount_dir/system_ext/priv-app/AwTvProvision"
install -d -o 0 -g 0 -m 0755 "$mount_dir/system_ext/overlay"
install -o 0 -g 0 -m 0644 "$provision_apk" "${targets[0]}"
install -o 0 -g 0 -m 0644 "$permissions_xml" "${targets[1]}"
install -o 0 -g 0 -m 0644 "$power_overlay" "${targets[2]}"

python3 - "$mount_dir" <<'PY'
import os
import stat
import sys

root = sys.argv[1]
contracts = {
    "system_ext/priv-app/AwTvProvision": (0o755, True),
    "system_ext/priv-app/AwTvProvision/AwTvProvision.apk": (0o644, False),
    "system_ext/etc/permissions/provision-permissions.xml": (0o644, False),
    "system_ext/overlay": (0o755, True),
    "system_ext/overlay/M8TvPowerPolicyOverlay.apk": (0o644, False),
}
label = b"u:object_r:system_file:s0\0"
for relative, (mode, directory) in contracts.items():
    path = os.path.join(root, relative)
    os.setxattr(path, b"security.selinux", label, follow_symlinks=False)
    value = os.lstat(path)
    valid_type = stat.S_ISDIR(value.st_mode) if directory else stat.S_ISREG(value.st_mode)
    if not valid_type or stat.S_IMODE(value.st_mode) != mode:
        raise SystemExit(f"invalid target type or mode: {path}")
    if value.st_uid != 0 or value.st_gid != 0:
        raise SystemExit(f"invalid target owner: {path}")
PY

for index in "${!targets[@]}"; do
  source=("$provision_apk" "$permissions_xml" "$power_overlay")
  [[ $(sha256sum "${targets[$index]}" | cut -d' ' -f1) == "${expected[${source[$index]}]}" ]] || {
    echo "installed SHA-256 mismatch: ${targets[$index]}" >&2
    exit 1
  }
done

sync
umount "$mount_dir"
check_ext4
