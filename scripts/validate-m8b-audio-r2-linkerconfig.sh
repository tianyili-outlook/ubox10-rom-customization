#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 6 ]]; then
    echo "usage: $0 <system.img> <vendor.img> <product.img> <linkerconfig> <output-dir> <expected-tool-sha256>" >&2
    exit 2
fi

system_image=$1
vendor_image=$2
product_image=$3
linkerconfig=$4
output_dir=$5
expected_tool_sha=$6
work=$(mktemp -d)
system_mount="$work/system-image"
vendor_mount="$work/vendor-image"
product_mount="$work/product-image"
root="$work/root"
target="$work/generated"
mounts=()

cleanup() {
    for ((index=${#mounts[@]}-1; index>=0; index--)); do
        mountpoint -q "${mounts[$index]}" && umount "${mounts[$index]}" || true
    done
    rm -rf "$work"
}
trap cleanup EXIT INT TERM

mkdir -p "$system_mount" "$vendor_mount" "$product_mount" "$root/system" "$root/system_ext" "$root/vendor" \
    "$root/product" "$root/apex/com.android.vndk.v31" "$target" "$output_dir"
mount -o loop,ro "$system_image" "$system_mount"; mounts+=("$system_mount")
mount -o loop,ro "$vendor_image" "$vendor_mount"; mounts+=("$vendor_mount")
mount -o loop,ro "$product_image" "$product_mount"; mounts+=("$product_mount")
mount --bind "$system_mount/system" "$root/system"; mounts+=("$root/system")
mount --bind "$vendor_mount" "$root/vendor"; mounts+=("$root/vendor")
mount --bind "$product_mount" "$root/product"; mounts+=("$root/product")
mount --bind "$system_mount/system/apex/com.android.vndk.current" "$root/apex/com.android.vndk.v31"; mounts+=("$root/apex/com.android.vndk.v31")

[[ $(sha256sum "$linkerconfig" | cut -d' ' -f1) == "${expected_tool_sha,,}" ]]
grep -qx 'ro.treble.enabled=true' "$root/system/build.prop"
grep -qx 'ro.vndk.version=31' "$root/vendor/build.prop"
grep -qx 'libaudioroute.so' "$root/apex/com.android.vndk.v31/etc/vndkcore.libraries.31.txt"

cat > "$root/apex/apex-info-list.xml" <<'XML'
<?xml version="1.0" encoding="utf-8"?>
<apex-info-list>
  <apex-info moduleName="com.android.vndk.v31" modulePath="/apex/com.android.vndk.v31" preinstalledModulePath="/system/apex/com.android.vndk.current" isFactory="true" isActive="true" />
</apex-info-list>
XML

"$linkerconfig" --root "$root" --vndk 31 --product_vndk '' --target "$target"
config="$target/ld.config.txt"
[[ -f "$config" ]]
cp "$config" "$output_dir/ld.config.txt"
grep -Fq '[vendor]' "$config"
grep -Fq 'namespace.vndk.search.paths += /apex/com.android.vndk.v31/${LIB}' "$config"
grep -Fq 'namespace.default.link.vndk.shared_libs' "$config"
grep -F 'namespace.default.link.vndk.shared_libs' "$config" | grep -Fq 'libaudioroute.so'

printf '%s\n' \
    'ro.treble.enabled=true' \
    'ro.vndk.version=31' \
    'vendor section=present' \
    'vndk namespace=present' \
    'vndk search path=/apex/com.android.vndk.v31/${LIB}' \
    'default->vndk libaudioroute.so=present' \
    > "$output_dir/summary.txt"
