#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
    echo "usage: $0 <system-image> <mount-dir>" >&2
    exit 2
fi

image=$1
root=$2
mounted=0

check_ext4() {
    set +e
    e2fsck -fy "$image"
    status=$?
    set -e
    [[ $status -le 1 ]]
}

cleanup() {
    if [[ $mounted -eq 1 ]]; then
        sync
        umount "$root"
    fi
}
trap cleanup EXIT INT TERM

check_ext4
mount -o loop,rw "$image" "$root"
mounted=1
build_prop="$root/system/build.prop"

[[ -f "$build_prop" ]]
[[ $(grep -c '^ro\.treble\.enabled=false$' "$build_prop") -eq 1 ]]
[[ $(grep -c '^ro\.treble\.enabled=true$' "$build_prop" || true) -eq 0 ]]

before_stat=$(stat -c '%i:%u:%g:%a' "$build_prop")
before_label=$({ getfattr --absolute-names --only-values -n security.selinux "$build_prop" 2>/dev/null || true; } | tr -d '\000')

python3 - "$build_prop" <<'PY'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
old = b"ro.treble.enabled=false"
new = b"ro.treble.enabled=true"
with path.open("r+b") as stream:
    data = stream.read()
    if data.count(old) != 1 or new in data:
        raise SystemExit("unexpected ro.treble.enabled source state")
    data = data.replace(old, new)
    stream.seek(0)
    stream.write(data)
    stream.truncate()
PY

sync
[[ $(grep -c '^ro\.treble\.enabled=true$' "$build_prop") -eq 1 ]]
[[ $(grep -c '^ro\.treble\.enabled=false$' "$build_prop" || true) -eq 0 ]]
[[ $(stat -c '%i:%u:%g:%a' "$build_prop") == "$before_stat" ]]
after_label=$({ getfattr --absolute-names --only-values -n security.selinux "$build_prop" 2>/dev/null || true; } | tr -d '\000')
[[ $after_label == "$before_label" ]]

sync
umount "$root"
mounted=0
check_ext4
