#!/bin/bash
set -euo pipefail

if [ "$#" -ne 10 ]; then
    echo "usage: $0 STOCK_KERNEL GENERATED_KEYMAP_C OUTPUT_DIR SOURCE_REPO CLANG_BIN EXPECTED_COMMIT KERNEL_PATCH BUILD_ROOT HOST_SSL_ROOT HOST_TOOLS_ROOT" >&2
    exit 2
fi

stock_kernel=$1
generated_keymap=$2
output_dir=$3
source_repo=$4
clang_bin=$5
expected_commit=$6
kernel_patch=$7
build_root=$8
host_ssl_root=$9
host_tools_root=${10}
kernel_src="${build_root}/src"
kernel_out="${build_root}/out"

test -f "${stock_kernel}"
test -f "${generated_keymap}"
test -f "${kernel_patch}"
test -x "${source_repo}/scripts/extract-ikconfig"
test -x "${clang_bin}/clang"
test -f "${host_ssl_root}/usr/include/openssl/bio.h"
test -e "${host_ssl_root}/usr/lib/x86_64-linux-gnu/libcrypto.so"
test -x "${host_tools_root}/usr/bin/bc"
test "$(git -C "${source_repo}" rev-parse HEAD)" = "${expected_commit}"
git -C "${source_repo}" diff --quiet
git -C "${source_repo}" diff --cached --quiet
if [ -e "${build_root}" ]; then
    echo "refusing to reuse kernel build root: ${build_root}" >&2
    exit 1
fi

mkdir -p "${build_root}" "${kernel_out}" "${output_dir}"
git -C "${source_repo}" worktree add --detach "${kernel_src}" "${expected_commit}"
git -C "${kernel_src}" apply --unidiff-zero --check "${kernel_patch}"
git -C "${kernel_src}" apply --unidiff-zero "${kernel_patch}"
cp "${generated_keymap}" "${kernel_src}/drivers/media/rc/rc-sunxi-keymaps.c"
"${kernel_src}/scripts/extract-ikconfig" "${stock_kernel}" > "${output_dir}/base-extracted.config"
cp "${output_dir}/base-extracted.config" "${kernel_out}/.config"
"${kernel_src}/scripts/config" --file "${kernel_out}/.config" --disable SUNXI_MULTI_IR_SUPPORT
"${kernel_src}/scripts/config" --file "${kernel_out}/.config" --enable BLK_CGROUP
"${kernel_src}/scripts/config" --file "${kernel_out}/.config" --enable CPUSETS

export PATH="${host_tools_root}/usr/bin:${clang_bin}:${PATH}"
export KBUILD_BUILD_USER=codex
export KBUILD_BUILD_HOST=m8b-rc-core
export KBUILD_BUILD_VERSION=1
export KBUILD_BUILD_TIMESTAMP='Thu Aug 13 22:30:00 +08 2026'
export KERNEL_SRC="${kernel_src}"
export HOSTCFLAGS="-I${host_ssl_root}/usr/include -I${host_ssl_root}/usr/include/x86_64-linux-gnu"
export HOSTLDFLAGS="-L${host_ssl_root}/usr/lib/x86_64-linux-gnu"

make -C "${kernel_src}" O="${kernel_out}" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- LLVM=1 LLVM_IAS=1 olddefconfig
diff -u "${output_dir}/base-extracted.config" "${kernel_out}/.config" > "${output_dir}/kernel-config.diff" || true

grep -q '^CONFIG_BLK_CGROUP=y$' "${kernel_out}/.config"
grep -q '^CONFIG_CPUSETS=y$' "${kernel_out}/.config"
grep -q '^CONFIG_PROC_PID_CPUSET=y$' "${kernel_out}/.config"
grep -q '^# CONFIG_MEMCG is not set$' "${kernel_out}/.config"
grep -q '^CONFIG_CGROUPS=y$' "${kernel_out}/.config"
grep -q '^CONFIG_CGROUP_SCHED=y$' "${kernel_out}/.config"
grep -q '^CONFIG_CGROUP_CPUACCT=y$' "${kernel_out}/.config"
grep -q '^CONFIG_CGROUP_FREEZER=y$' "${kernel_out}/.config"

python3 - "${output_dir}/base-extracted.config" "${kernel_out}/.config" <<'PY'
from pathlib import Path
import sys

def values(path):
    result = {}
    for line in Path(path).read_text().splitlines():
        if line.startswith("CONFIG_") and "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
        elif line.startswith("# CONFIG_") and line.endswith(" is not set"):
            result[line[2:-11]] = "n"
    return result

before, after = map(values, sys.argv[1:])
changed = {key: [before.get(key), after.get(key)] for key in sorted(set(before) | set(after)) if before.get(key) != after.get(key)}
expected = {
    "CONFIG_BLK_CGROUP": ["n", "y"],
    # These policy symbols become visible when BLK_CGROUP is enabled. Keep
    # them disabled: Android only needs the generic controller for the
    # required v1 blkio hierarchy and NormalIoPriority membership here.
    "CONFIG_BLK_DEV_THROTTLING": [None, "n"],
    "CONFIG_BLK_CGROUP_IOLATENCY": [None, "n"],
    "CONFIG_BLK_CGROUP_IOCOST": [None, "n"],
    "CONFIG_CPUSETS": ["n", "y"],
    "CONFIG_PROC_PID_CPUSET": [None, "y"],
}
if changed != expected:
    raise SystemExit(f"unexpected olddefconfig delta: {changed}")
PY

make -C "${kernel_src}" O="${kernel_out}" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- LLVM=1 LLVM_IAS=1 -j8 Image

cp "${kernel_out}/arch/arm64/boot/Image" "${output_dir}/Image"
cp "${kernel_out}/.config" "${output_dir}/candidate.config"
"${kernel_src}/scripts/extract-ikconfig" "${output_dir}/Image" > "${output_dir}/image-extracted.config"
cmp "${output_dir}/candidate.config" "${output_dir}/image-extracted.config"
git -C "${kernel_src}" diff --check
git -C "${kernel_src}" diff -- drivers/media/rc/rc-main.c drivers/media/rc/rc-sunxi-keymaps.c > "${output_dir}/kernel-source.diff"
git -C "${kernel_src}" status --short > "${output_dir}/kernel-source-status.txt"
{
    git -C "${kernel_src}" rev-parse HEAD
    git -C "${source_repo}" rev-parse HEAD
    "${clang_bin}/clang" --version | head -2
    stat -c '%s  %n' "${output_dir}/Image"
    sha256sum "${output_dir}/Image" "${output_dir}/candidate.config" "${output_dir}/kernel-config.diff" "${output_dir}/kernel-source.diff"
} > "${output_dir}/kernel-build-identity.txt"

grep -q '0x00ff404d, KEY_POWER' "${kernel_src}/drivers/media/rc/rc-sunxi-keymaps.c"
grep -q '0x00ff400b, KEY_UP' "${kernel_src}/drivers/media/rc/rc-sunxi-keymaps.c"
! grep -q '0x00ff4054' "${kernel_src}/drivers/media/rc/rc-sunxi-keymaps.c"
grep -q '^#ifdef CONFIG_SUNXI_MULTI_IR_SUPPORT$' "${kernel_src}/drivers/media/rc/rc-main.c"

git -C "${source_repo}" worktree remove --force "${kernel_src}"
