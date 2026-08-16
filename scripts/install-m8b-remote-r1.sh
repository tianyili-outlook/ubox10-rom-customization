#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 6 ]]; then
  echo "usage: $0 SYSTEM_EXT4_IMAGE MOUNT_DIRECTORY REMOTE_APK PRIVAPP_XML DEFAULT_PERMISSIONS_XML REMOTE_RRO_APK" >&2
  exit 2
fi

image=$1
mount_dir=$2
remote_apk=$3
privapp_xml=$4
default_permissions_xml=$5
remote_rro=$6

[[ $(id -u) -eq 0 ]] || { echo "must run as root" >&2; exit 2; }
[[ -f $image && -d $mount_dir ]] || { echo "missing image or mount directory" >&2; exit 2; }
mountpoint -q "$mount_dir" && { echo "mount directory is already in use" >&2; exit 2; }

declare -A expected=(
  ["$remote_apk"]="9d1b5c5ef0e293f8ed17c26e8f62de661acc7f2ddc2aaa8ef23e4cabe430b973"
  ["$privapp_xml"]="e46ca371727df823e07495be5451ef2e2a1874a7c4e7fe82a41448f966fa23f2"
  ["$default_permissions_xml"]="b28dcd3e92fd04e77ade71f548a949828cbe5c731d608d5ced9f8bbe0955e563"
  ["$remote_rro"]="71d60aa7a38b86269e16d42df61dbf8fb661d42ace14929db7cf0571ddc314a8"
)
for source in "$remote_apk" "$privapp_xml" "$default_permissions_xml" "$remote_rro"; do
  [[ -f $source && ! -L $source ]] || { echo "missing regular source: $source" >&2; exit 1; }
  [[ $(sha256sum "$source" | cut -d' ' -f1) == "${expected[$source]}" ]] || {
    echo "source SHA-256 mismatch: $source" >&2
    exit 1
  }
done

cleanup() {
  mountpoint -q "$mount_dir" && umount "$mount_dir" || true
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

# These Android 12 ATV components already exist in the accepted m8b-ime-r1
# system and are deliberately reused rather than replaced.
declare -A baseline=(
  ["system/framework/com.android.media.tv.remoteprovider.jar"]="cf2fc4a6878a1cc7576f6af84d430c98d4485ffda992d43a8aa03d9c696c2ebe"
  ["system/etc/permissions/com.android.media.tv.remoteprovider.xml"]="b3c1d21187054fb7049bff10b9da1d38d8685e0c2583ab000129340e74885994"
  ["system/etc/permissions/tv_core_hardware.xml"]="f013dc28dc32bac5afd32c3bdbe05defed1fc6d9cbb48cd1ede21e4a138d1b02"
)
for relative in "${!baseline[@]}"; do
  target="$mount_dir/$relative"
  [[ -f $target && $(sha256sum "$target" | cut -d' ' -f1) == "${baseline[$relative]}" ]] || {
    echo "accepted ATV framework identity mismatch: /$relative" >&2
    exit 1
  }
done
grep -q 'android.software.leanback' "$mount_dir/system/etc/permissions/tv_core_hardware.xml"
grep -q 'android.software.leanback_only' "$mount_dir/system/etc/permissions/tv_core_hardware.xml"

targets=(
  "$mount_dir/system/priv-app/AndroidTvRemoteService/AndroidTvRemoteService.apk"
  "$mount_dir/system/etc/permissions/privapp-permissions-com.google.android.tv.remote.service.xml"
  "$mount_dir/system/etc/default-permissions/default-permissions-com.google.android.tv.remote.service.xml"
  "$mount_dir/system_ext/overlay/UBOX10TvRemoteConfigOverlay.apk"
)
for target in "${targets[@]}"; do
  [[ ! -e $target && ! -L $target ]] || { echo "refusing to replace existing target: $target" >&2; exit 1; }
done

install -d -o 0 -g 0 -m 0755 "$mount_dir/system/priv-app/AndroidTvRemoteService"
install -d -o 0 -g 0 -m 0755 "$mount_dir/system/etc/default-permissions"
install -o 0 -g 0 -m 0644 "$remote_apk" "${targets[0]}"
install -o 0 -g 0 -m 0644 "$privapp_xml" "${targets[1]}"
install -o 0 -g 0 -m 0644 "$default_permissions_xml" "${targets[2]}"
install -o 0 -g 0 -m 0644 "$remote_rro" "${targets[3]}"

python3 - "$mount_dir" <<'PY'
import os
import stat
import sys

root = sys.argv[1]
contracts = {
    "system/priv-app/AndroidTvRemoteService": (0o755, True),
    "system/priv-app/AndroidTvRemoteService/AndroidTvRemoteService.apk": (0o644, False),
    "system/etc/default-permissions": (0o755, True),
    "system/etc/permissions/privapp-permissions-com.google.android.tv.remote.service.xml": (0o644, False),
    "system/etc/default-permissions/default-permissions-com.google.android.tv.remote.service.xml": (0o644, False),
    "system_ext/overlay/UBOX10TvRemoteConfigOverlay.apk": (0o644, False),
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

sources=("$remote_apk" "$privapp_xml" "$default_permissions_xml" "$remote_rro")
for index in "${!targets[@]}"; do
  [[ $(sha256sum "${targets[$index]}" | cut -d' ' -f1) == "${expected[${sources[$index]}]}" ]] || {
    echo "installed SHA-256 mismatch: ${targets[$index]}" >&2
    exit 1
  }
done

sync
umount "$mount_dir"
check_ext4
