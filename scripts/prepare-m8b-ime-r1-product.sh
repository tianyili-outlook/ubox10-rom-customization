#!/usr/bin/env bash
set -euo pipefail

base_image=$1
candidate_image=$2
base_root=$3
candidate_root=$4

mkdir -p "$base_root" "$candidate_root"
cleanup() {
  mountpoint -q "$candidate_root" && umount "$candidate_root" || true
  mountpoint -q "$base_root" && umount "$base_root" || true
}
trap cleanup EXIT INT TERM

mount -o loop,ro "$base_image" "$base_root"
mount -o loop,rw "$candidate_image" "$candidate_root"

# The accepted product predates the Treble source-contract rebuild. Preserve
# its runtime properties byte-for-byte while retaining the normally generated
# LeanbackIME files and NOTICE update from the new product build.
cp --preserve=mode,ownership,timestamps,xattr "$base_root/etc/build.prop" "$candidate_root/etc/build.prop"
cmp "$base_root/etc/build.prop" "$candidate_root/etc/build.prop"
sync
