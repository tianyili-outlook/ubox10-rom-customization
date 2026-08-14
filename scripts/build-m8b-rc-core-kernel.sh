#!/bin/bash
set -euo pipefail

if [ "$#" -lt 5 ] || [ "$#" -gt 6 ]; then
    echo "usage: $0 STOCK_KERNEL GENERATED_KEYMAP_C OUTPUT_DIR BUILD_ID EXPECTED_COMMIT [KERNEL_PATCH]" >&2
    exit 2
fi

stock_kernel=$1
generated_keymap=$2
output_dir=$3
build_id=$4
expected_commit=$5
kernel_patch=${6:-}
source_repo=/home/tianyi/ubox10-kernel-sun50iw9-m8b
clang_bin=/home/tianyi/ubox10-aosp/prebuilts/clang/host/linux-x86/clang-r416183b1/bin
build_root="/home/tianyi/ubox10-kernel-builds/${build_id}"
kernel_src="${build_root}/src"
kernel_out="${build_root}/out"

test -f "${stock_kernel}"
test -f "${generated_keymap}"
test -x "${source_repo}/scripts/extract-ikconfig"
test "$(git -C "${source_repo}" rev-parse HEAD)" = "${expected_commit}"
git -C "${source_repo}" diff --quiet
git -C "${source_repo}" diff --cached --quiet
if [ -e "${build_root}" ]; then
    echo "refusing to reuse kernel build root: ${build_root}" >&2
    exit 1
fi

mkdir -p "${build_root}" "${output_dir}"
git -C "${source_repo}" worktree add --detach "${kernel_src}" "${expected_commit}"
if [ -n "${kernel_patch}" ]; then
    test -f "${kernel_patch}"
    git -C "${kernel_src}" apply --unidiff-zero --check "${kernel_patch}"
    git -C "${kernel_src}" apply --unidiff-zero "${kernel_patch}"
fi
cp "${generated_keymap}" "${kernel_src}/drivers/media/rc/rc-sunxi-keymaps.c"
"${kernel_src}/scripts/extract-ikconfig" "${stock_kernel}" > "${output_dir}/r13-exact.config"
cp "${output_dir}/r13-exact.config" "${kernel_out}/.config" 2>/dev/null || {
    mkdir -p "${kernel_out}"
    cp "${output_dir}/r13-exact.config" "${kernel_out}/.config"
}
"${kernel_src}/scripts/config" --file "${kernel_out}/.config" --disable SUNXI_MULTI_IR_SUPPORT

export PATH="${clang_bin}:${PATH}"
export KBUILD_BUILD_USER=codex
export KBUILD_BUILD_HOST=m8b-rc-core
export KBUILD_BUILD_VERSION=1
export KBUILD_BUILD_TIMESTAMP='Thu Aug 13 22:30:00 +08 2026'
export KERNEL_SRC="${kernel_src}"

make -C "${kernel_src}" O="${kernel_out}" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- LLVM=1 LLVM_IAS=1 olddefconfig
diff -u "${output_dir}/r13-exact.config" "${kernel_out}/.config" > "${output_dir}/kernel-config.diff" || true
make -C "${kernel_src}" O="${kernel_out}" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- LLVM=1 LLVM_IAS=1 -j12 Image

cp "${kernel_out}/arch/arm64/boot/Image" "${output_dir}/Image"
cp "${kernel_out}/.config" "${output_dir}/candidate.config"
git -C "${kernel_src}" diff --check
git -C "${kernel_src}" diff -- drivers/media/rc/rc-main.c drivers/media/rc/rc-sunxi-keymaps.c > "${output_dir}/kernel-source.diff"
git -C "${kernel_src}" status --short > "${output_dir}/kernel-source-status.txt"
{
    git -C "${kernel_src}" rev-parse HEAD
    "${clang_bin}/clang" --version | head -2
    file "${output_dir}/Image"
    stat -c '%s  %n' "${output_dir}/Image"
    sha256sum "${output_dir}/Image" "${output_dir}/candidate.config" "${output_dir}/kernel-source.diff"
} > "${output_dir}/kernel-build-identity.txt"

grep -q '^# CONFIG_SUNXI_MULTI_IR_SUPPORT is not set$' "${output_dir}/candidate.config"
! grep -q '^CONFIG_SUNXI_MULTI_IR_SUPPORT=y$' "${output_dir}/candidate.config"
grep -q '0x00ff404d, KEY_POWER' "${kernel_src}/drivers/media/rc/rc-sunxi-keymaps.c"
grep -q '0x00ff400b, KEY_UP' "${kernel_src}/drivers/media/rc/rc-sunxi-keymaps.c"
! grep -q '0x00ff4054' "${kernel_src}/drivers/media/rc/rc-sunxi-keymaps.c"
if [ -n "${kernel_patch}" ]; then
    grep -q '^#ifdef CONFIG_SUNXI_MULTI_IR_SUPPORT$' "${kernel_src}/drivers/media/rc/rc-main.c"
    if git -C "${kernel_src}" diff --quiet --exit-code -- drivers/media/rc/rc-main.c; then
        echo "expected kernel patch did not change rc-main.c" >&2
        exit 1
    fi
else
    git -C "${kernel_src}" diff --quiet --exit-code -- drivers/media/rc/rc-main.c
fi
