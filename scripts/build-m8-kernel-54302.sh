#!/bin/bash
set -euo pipefail

if [ "$#" -lt 14 ] || [ "$#" -gt 17 ]; then
    echo "usage: $0 SOURCE_REPO SOURCE_COMMIT ACCEPTED_IMAGE KEYMAP_JSON RC_PATCH CLANG_BIN HOST_SSL_ROOT HOST_TOOLS_ROOT BUILD_ROOT EVIDENCE_DIR XR819_DONOR_REPO XR819_DONOR_COMMIT AIC8800_DONOR_REPO AIC8800_DONOR_COMMIT [AIC8800_COMPAT_PATCH] [EXPECTED_AIC8800_SDIO_CLOCK_HZ] [AIC8800_DIAGNOSTIC_PATCH]" >&2
    exit 2
fi

source_repo=$(realpath -e "$1")
source_commit=$2
accepted_image=$(realpath -e "$3")
keymap_json=$(realpath -e "$4")
rc_patch=$(realpath -e "$5")
clang_bin=$(realpath -e "$6")
host_ssl_root=$(realpath -e "$7")
host_tools_root=$(realpath -e "$8")
build_root=$9
evidence_dir=${10}
xr819_donor_repo=$(realpath -e "${11}")
xr819_donor_commit=${12}
aic8800_donor_repo=$(realpath -e "${13}")
aic8800_donor_commit=${14}
aic8800_compat_patch=${15:-}
aic8800_expected_sdio_clock=${16:-50000000}
aic8800_diagnostic_patch=${17:-}
if [ -n "${aic8800_compat_patch}" ]; then
    aic8800_compat_patch=$(realpath -e "${aic8800_compat_patch}")
fi
if [ -n "${aic8800_diagnostic_patch}" ]; then
    aic8800_diagnostic_patch=$(realpath -e "${aic8800_diagnostic_patch}")
fi
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/.." && pwd)
contract_dir="${repo_root}/configs/kernel/m8-kernel-5.4.302"
kernel_src="${build_root}/src"
kernel_out="${build_root}/out"
modules_root="${build_root}/modules-install"
result_dir="${evidence_dir}/build-result"
status_file="${evidence_dir}/build.status"
start_epoch=$(date +%s)
monitor_pid=
vmstat_pid=

write_status() {
    local result=$1
    local code=$2
    local end_epoch
    end_epoch=$(date +%s)
    {
        printf 'result=%s\n' "${result}"
        printf 'exit_code=%s\n' "${code}"
        printf 'source_commit=%s\n' "${source_commit}"
        printf 'build_root=%s\n' "${build_root}"
        printf 'start_epoch=%s\n' "${start_epoch}"
        printf 'end_epoch=%s\n' "${end_epoch}"
        printf 'elapsed_seconds=%s\n' "$((end_epoch - start_epoch))"
    } > "${status_file}"
}

on_exit() {
    local code=$?
    trap - EXIT
    if [ -n "${monitor_pid}" ]; then
        kill "${monitor_pid}" 2>/dev/null || true
        wait "${monitor_pid}" 2>/dev/null || true
    fi
    if [ -n "${vmstat_pid}" ]; then
        kill "${vmstat_pid}" 2>/dev/null || true
        wait "${vmstat_pid}" 2>/dev/null || true
    fi
    if [ "${code}" -eq 0 ]; then
        write_status SUCCESS 0
    else
        write_status FAILED "${code}"
    fi
    exit "${code}"
}
trap on_exit EXIT

test -x "${source_repo}/scripts/extract-ikconfig"
test -f "${accepted_image}"
test -f "${keymap_json}"
test -f "${rc_patch}"
test -x "${clang_bin}/clang"
test -f "${host_ssl_root}/usr/include/openssl/bio.h"
test -e "${host_ssl_root}/usr/lib/x86_64-linux-gnu/libcrypto.so"
test -x "${host_tools_root}/usr/bin/bc"
if [ -n "${aic8800_compat_patch}" ]; then
    test -f "${aic8800_compat_patch}"
fi
if [ -n "${aic8800_diagnostic_patch}" ]; then
    test -f "${aic8800_diagnostic_patch}"
fi
test "$(git -C "${xr819_donor_repo}" rev-parse HEAD)" = "${xr819_donor_commit}"
test "$(git -C "${xr819_donor_repo}" rev-parse 'HEAD:kernel/linux-5.4/drivers/net/wireless/xr819')" = e5d1a2df874a1f81f810b443f73709c9559ec07c
git -C "${xr819_donor_repo}" diff --quiet
git -C "${xr819_donor_repo}" diff --cached --quiet
test "$(git -C "${aic8800_donor_repo}" rev-parse HEAD)" = "${aic8800_donor_commit}"
test "$(git -C "${aic8800_donor_repo}" rev-parse 'HEAD:drivers/net/wireless/aic8800')" = 70c98140316f7ed23af879bb0e3d881883f5e978
git -C "${aic8800_donor_repo}" diff --quiet
git -C "${aic8800_donor_repo}" diff --cached --quiet
test "$(git -C "${source_repo}" rev-parse HEAD)" = "${source_commit}"
git -C "${source_repo}" diff --quiet
git -C "${source_repo}" diff --cached --quiet
test ! -e "${build_root}"
test ! -e "${status_file}"

mkdir -p "${evidence_dir}" "${result_dir}" "${build_root}" "${kernel_out}"
write_status RUNNING 0

(
    printf 'utc\tmem_available_kib\twork_available_kib\tload1\trunnable\tblocked\n'
    while true; do
        now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
        mem=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
        disk=$(df --output=avail -k /work | tail -1 | tr -d ' ')
        load=$(cut -d' ' -f1 /proc/loadavg)
        run=$(awk '$1 == "procs_running" {print $2}' /proc/stat)
        blocked=$(awk '$1 == "procs_blocked" {print $2}' /proc/stat)
        printf '%s\t%s\t%s\t%s\t%s\t%s\n' "${now}" "${mem}" "${disk}" "${load}" "${run}" "${blocked}"
        sleep 60
    done
) > "${evidence_dir}/resources.tsv" &
monitor_pid=$!
vmstat -t 60 > "${evidence_dir}/vmstat.log" &
vmstat_pid=$!

{
    date -u +%Y-%m-%dT%H:%M:%SZ
    uname -a
    nproc
    free -h
    df -h /work
    git -C "${source_repo}" remote -v
    git -C "${source_repo}" show -s --format=fuller "${source_commit}"
    git -C "${source_repo}" rev-parse "${source_commit}^{tree}"
    "${clang_bin}/clang" --version
    sha256sum "${accepted_image}" "${keymap_json}" "${rc_patch}"
    if [ -n "${aic8800_compat_patch}" ]; then
        sha256sum "${aic8800_compat_patch}"
    fi
    if [ -n "${aic8800_diagnostic_patch}" ]; then
        sha256sum "${aic8800_diagnostic_patch}"
    fi
    git -C "${xr819_donor_repo}" remote -v
    git -C "${xr819_donor_repo}" show -s --format=fuller "${xr819_donor_commit}"
    git -C "${xr819_donor_repo}" rev-parse \
        'HEAD:kernel/linux-5.4/drivers/net/wireless/xr819'
    git -C "${aic8800_donor_repo}" remote -v
    git -C "${aic8800_donor_repo}" show -s --format=fuller "${aic8800_donor_commit}"
    git -C "${aic8800_donor_repo}" rev-parse \
        'HEAD:drivers/net/wireless/aic8800'
} > "${evidence_dir}/build-provenance.txt"

git -C "${source_repo}" worktree add --detach "${kernel_src}" "${source_commit}"
git -C "${kernel_src}" apply --unidiff-zero --check "${rc_patch}"
git -C "${kernel_src}" apply --unidiff-zero "${rc_patch}"
test ! -e "${kernel_src}/drivers/net/wireless/xr819"
mkdir -p "${kernel_src}/drivers/net/wireless/xr819"
cp -a "${xr819_donor_repo}/kernel/linux-5.4/drivers/net/wireless/xr819/." \
    "${kernel_src}/drivers/net/wireless/xr819/"
test ! -e "${kernel_src}/drivers/net/wireless/aic8800-accepted"
mkdir -p "${kernel_src}/drivers/net/wireless/aic8800-accepted"
cp -a "${aic8800_donor_repo}/drivers/net/wireless/aic8800/." \
    "${kernel_src}/drivers/net/wireless/aic8800-accepted/"
if [ -n "${aic8800_compat_patch}" ]; then
    git -C "${kernel_src}" apply --check "${aic8800_compat_patch}"
    git -C "${kernel_src}" apply "${aic8800_compat_patch}"
    cp "${aic8800_compat_patch}" "${result_dir}/aic8800-compatibility-source.patch"
    grep -q "^#define FEATURE_SDIO_CLOCK          ${aic8800_expected_sdio_clock} " \
        "${kernel_src}/drivers/net/wireless/aic8800-accepted/aic8800_bsp/aic_bsp_driver.h"
fi
if [ -n "${aic8800_diagnostic_patch}" ]; then
    git -C "${kernel_src}" apply --check "${aic8800_diagnostic_patch}"
    git -C "${kernel_src}" apply "${aic8800_diagnostic_patch}"
    cp "${aic8800_diagnostic_patch}" "${result_dir}/aic8800-diagnostic-source.patch"
fi
test "$(git -C "${source_repo}" rev-parse '9ab7a758149d3c9b721878a0c18b3f9c5d6c93e6:drivers/net/wireless/realtek/rtlwifi')" = 8d1d70eaacbb82e599e3db228045f86a1c4d05a8
test ! -e "${kernel_src}/drivers/net/wireless/rtlwifi-accepted"
mkdir -p "${kernel_src}/drivers/net/wireless/rtlwifi-accepted"
git -C "${source_repo}" archive 9ab7a758149d3c9b721878a0c18b3f9c5d6c93e6 \
    drivers/net/wireless/realtek/rtlwifi \
    | tar -x --strip-components=5 \
        -C "${kernel_src}/drivers/net/wireless/rtlwifi-accepted"
python3 "${script_dir}/generate-m8b-rc-core-input.py" \
    --map "${keymap_json}" \
    --c-output "${result_dir}/rc-sunxi-keymaps.c" \
    --kl-output "${result_dir}/sunxi-ir.kl" \
    --report "${result_dir}/ff40-generation.json"
cp "${result_dir}/rc-sunxi-keymaps.c" "${kernel_src}/drivers/media/rc/rc-sunxi-keymaps.c"

"${kernel_src}/scripts/extract-ikconfig" "${accepted_image}" > "${result_dir}/accepted-extracted.config"
cmp "${contract_dir}/accepted-5.4.125.config" "${result_dir}/accepted-extracted.config"
cp "${result_dir}/accepted-extracted.config" "${kernel_out}/.config"
"${kernel_src}/scripts/config" --file "${kernel_out}/.config" --disable SUNXI_MULTI_IR_SUPPORT

export PATH="${host_tools_root}/usr/bin:${clang_bin}:${PATH}"
export ARCH=arm64
export CROSS_COMPILE=aarch64-linux-gnu-
export LLVM=1
export LLVM_IAS=1
export KBUILD_BUILD_USER=codex
export KBUILD_BUILD_HOST=ubox10-gcp
export KBUILD_BUILD_VERSION=1
export KBUILD_BUILD_TIMESTAMP='Thu Aug 13 22:30:00 +08 2026'
export KERNEL_SRC="${kernel_src}"
export HOSTCFLAGS="-I${host_ssl_root}/usr/include -I${host_ssl_root}/usr/include/x86_64-linux-gnu"
export HOSTLDFLAGS="-L${host_ssl_root}/usr/lib/x86_64-linux-gnu"

make -C "${kernel_src}" O="${kernel_out}" olddefconfig
cp "${kernel_out}/.config" "${result_dir}/preservation.config"
diff -u \
    --label accepted-5.4.125.config \
    --label preservation-5.4.302.config \
    "${result_dir}/accepted-extracted.config" \
    "${result_dir}/preservation.config" \
    > "${result_dir}/preservation-effective.diff" || true

python3 - "${result_dir}/accepted-extracted.config" "${result_dir}/preservation.config" "${result_dir}/preservation-delta.json" <<'PY'
import json
import sys
from pathlib import Path

def values(path):
    result = {}
    for line in Path(path).read_text().splitlines():
        if line.startswith("CONFIG_") and "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
        elif line.startswith("# CONFIG_") and line.endswith(" is not set"):
            result[line[2:-11]] = "n"
    return result

before, after = map(values, sys.argv[1:3])
changed = {
    key: [before.get(key), after.get(key)]
    for key in sorted(set(before) | set(after))
    if before.get(key) != after.get(key)
}
expected = {
    "CONFIG_ANDROID_KABI_RESERVE": [None, "y"],
    "CONFIG_ANDROID_VENDOR_OEM_DATA": [None, "y"],
    "CONFIG_ARM64_ERRATUM_1742098": [None, "y"],
    "CONFIG_ARM64_ERRATUM_3194386": [None, "y"],
    "CONFIG_BATTERY_RT5033": [None, "n"],
    "CONFIG_BPF_UNPRIV_DEFAULT_OFF": [None, "n"],
    "CONFIG_CC_HAS_ASM_GOTO_OUTPUT": [None, "y"],
    "CONFIG_CC_HAS_AUTO_VAR_INIT_ZERO_ENABLER": [None, "y"],
    "CONFIG_CRYPTO_LIB_BLAKE2S": ["n", None],
    "CONFIG_CRYPTO_LIB_BLAKE2S_GENERIC": [None, "y"],
    "CONFIG_DECNET": ["n", None],
    "CONFIG_DRM_MXSFB": ["n", None],
    "CONFIG_FORTIFY_SOURCE": ["n", None],
    "CONFIG_INET_TABLE_PERTURB_ORDER": [None, "16"],
    "CONFIG_LEDS_CLASS_MULTICOLOR": [None, "n"],
    "CONFIG_LIB_MEMNEQ": [None, "y"],
    "CONFIG_MFD_TI_AM335X_TSCADC": ["n", None],
    "CONFIG_MITIGATE_SPECTRE_BRANCH_HISTORY": [None, "y"],
    "CONFIG_NET_CLS_RSVP": ["n", None],
    "CONFIG_NET_CLS_RSVP6": ["n", None],
    "CONFIG_NET_CLS_TCINDEX": ["n", None],
    "CONFIG_NET_SCH_CBQ": ["n", None],
    "CONFIG_NET_SCH_DSMARK": ["n", None],
    "CONFIG_NVM": ["n", None],
    "CONFIG_NVME_TCP": [None, "n"],
    "CONFIG_PROC_MEM_ALWAYS_FORCE": [None, "y"],
    "CONFIG_PROC_MEM_FORCE_PTRACE": [None, "n"],
    "CONFIG_PROC_MEM_NO_FORCE": [None, "n"],
    "CONFIG_PSTORE_BLK": ["n", None],
    "CONFIG_REFCOUNT_FULL": ["y", None],
    "CONFIG_SURFACE_PLATFORMS": [None, "y"],
    "CONFIG_XOR_BLOCKS": [None, "y"],
}
Path(sys.argv[3]).write_text(json.dumps(changed, indent=2, sort_keys=True) + "\n")
if changed != expected:
    raise SystemExit(f"unexpected effective config delta: {changed}")
PY

cmp "${contract_dir}/preservation-5.4.302.config" "${result_dir}/preservation.config"
cmp "${contract_dir}/preservation-effective.diff" "${result_dir}/preservation-effective.diff"
cmp "${contract_dir}/preservation-delta.json" "${result_dir}/preservation-delta.json"

cp "${result_dir}/preservation.config" "${kernel_out}/.config.path-a-input"
for option in BLK_CGROUP CPUSETS NET_CLS_MATCHALL NET_ACT_POLICE NET_ACT_BPF; do
    "${kernel_src}/scripts/config" --file "${kernel_out}/.config.path-a-input" --enable "${option}"
done
cp "${kernel_out}/.config" "${kernel_out}/.config.preservation"
cp "${kernel_out}/.config.path-a-input" "${kernel_out}/.config"
make -C "${kernel_src}" O="${kernel_out}" olddefconfig
cp "${kernel_out}/.config" "${result_dir}/path-a.config"
diff -u \
    --label preservation-5.4.302.config \
    --label path-a-5.4.302.config \
    "${result_dir}/preservation.config" \
    "${result_dir}/path-a.config" \
    > "${result_dir}/path-a-effective.diff" || true
python3 - "${result_dir}/preservation.config" "${result_dir}/path-a.config" "${result_dir}/path-a-delta.json" <<'PY'
import json
import sys
from pathlib import Path

def values(path):
    result = {}
    for line in Path(path).read_text().splitlines():
        if line.startswith("CONFIG_") and "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
        elif line.startswith("# CONFIG_") and line.endswith(" is not set"):
            result[line[2:-11]] = "n"
    return result

before, after = map(values, sys.argv[1:3])
changed = {
    key: [before.get(key), after.get(key)]
    for key in sorted(set(before) | set(after))
    if before.get(key) != after.get(key)
}
expected = {
    "CONFIG_BLK_CGROUP": ["n", "y"],
    "CONFIG_BLK_CGROUP_IOCOST": [None, "n"],
    "CONFIG_BLK_CGROUP_IOLATENCY": [None, "n"],
    "CONFIG_BLK_DEV_THROTTLING": [None, "n"],
    "CONFIG_CPUSETS": ["n", "y"],
    "CONFIG_NET_ACT_BPF": ["n", "y"],
    "CONFIG_NET_ACT_POLICE": ["n", "y"],
    "CONFIG_NET_CLS_MATCHALL": ["n", "y"],
    "CONFIG_PROC_PID_CPUSET": [None, "y"],
}
Path(sys.argv[3]).write_text(json.dumps(changed, indent=2, sort_keys=True) + "\n")
if changed != expected:
    raise SystemExit(f"unexpected Path-A config delta: {changed}")
PY

cmp "${contract_dir}/path-a-5.4.302.config" "${result_dir}/path-a.config"
cmp "${contract_dir}/path-a-effective.diff" "${result_dir}/path-a-effective.diff"
cmp "${contract_dir}/path-a-delta.json" "${result_dir}/path-a-delta.json"

cp "${kernel_out}/.config.preservation" "${kernel_out}/.config"
make -C "${kernel_src}" O="${kernel_out}" olddefconfig
cmp "${result_dir}/preservation.config" "${kernel_out}/.config"

make -C "${kernel_src}" O="${kernel_out}" -j8 Image modules dtbs
make -C "${kernel_src}" O="${kernel_out}" modules_install INSTALL_MOD_PATH="${modules_root}"
make -C "${kernel_src}/modules/gpu/mali-bifrost/driver" \
    KDIR="${kernel_out}" O="${kernel_out}" all
make -C "${kernel_src}/modules/gpu" \
    KERNEL_SRC="${kernel_out}" O="${kernel_out}" GPU_TYPE=mali-g31 \
    INSTALL_MOD_PATH="${modules_root}" modules_install
make -C "${kernel_src}" O="${kernel_out}" \
    M=drivers/net/wireless/rtlwifi-accepted \
    CONFIG_RTLWIFI=m CONFIG_RTLWIFI_USB=m CONFIG_RTLWIFI_DEBUG=y \
    KCFLAGS=-DCONFIG_RTLWIFI_DEBUG \
    -j8 modules
"${clang_bin}/llvm-strip" --strip-unneeded \
    "${kernel_out}/drivers/net/wireless/rtlwifi-accepted/rtlwifi.ko"
make -C "${kernel_src}" O="${kernel_out}" \
    M=drivers/net/wireless/rtlwifi-accepted \
    CONFIG_RTLWIFI=m CONFIG_RTLWIFI_USB=m CONFIG_RTLWIFI_DEBUG=y \
    INSTALL_MOD_PATH="${modules_root}" modules_install
make -C "${kernel_src}" O="${kernel_out}" \
    M=drivers/net/wireless/xr819 CONFIG_XR819_WLAN=m -j8 modules
make -C "${kernel_src}" O="${kernel_out}" \
    M=drivers/net/wireless/xr819 CONFIG_XR819_WLAN=m \
    INSTALL_MOD_PATH="${modules_root}" modules_install

# The accepted AIC8800 modules are 20221108-004, newer than the 20211129
# sources in the pinned Orange Pi commit. Rebuild the exact hash-pinned
# Allwinner source as a bounded external module set, then replace only those
# three installed module files. The donor BSP's generated verifier carries
# DWARF that the accepted module does not, so remove debug-only sections.
make -C "${kernel_src}" O="${kernel_out}" \
    M=drivers/net/wireless/aic8800-accepted \
    CONFIG_AIC_WLAN_SUPPORT=y CONFIG_AIC_INTF_SDIO=y \
    CONFIG_AIC8800_WLAN_SUPPORT=m CONFIG_AIC8800_BTLPM_SUPPORT=m \
    -j8 modules
aic_bsp="${kernel_out}/drivers/net/wireless/aic8800-accepted/aic8800_bsp/aic8800_bsp.ko"
aic_fdrv="${kernel_out}/drivers/net/wireless/aic8800-accepted/aic8800_fdrv/aic8800_fdrv.ko"
aic_btlpm="${kernel_out}/drivers/net/wireless/aic8800-accepted/aic8800_btlpm/aic8800_btlpm.ko"
"${clang_bin}/llvm-strip" --strip-debug "${aic_bsp}"
module_release=$(make -s -C "${kernel_src}" O="${kernel_out}" kernelrelease)
release_dir="${modules_root}/lib/modules/${module_release}"
cp "${aic_bsp}" \
    "${release_dir}/kernel/drivers/net/wireless/aic8800/aic8800_bsp/aic8800_bsp.ko"
cp "${aic_fdrv}" \
    "${release_dir}/kernel/drivers/net/wireless/aic8800/aic8800_fdrv/aic8800_fdrv.ko"
cp "${aic_btlpm}" \
    "${release_dir}/kernel/drivers/net/wireless/aic8800/aic8800_btlpm/aic8800_btlpm.ko"
depmod -b "${modules_root}" "${module_release}"

cp "${kernel_out}/arch/arm64/boot/Image" "${result_dir}/Image"
cp "${kernel_out}/.config" "${result_dir}/built.config"
cp "${kernel_out}/Module.symvers" "${result_dir}/Module.symvers"
cp "${kernel_out}/System.map" "${result_dir}/System.map"
cp "${kernel_out}/drivers/net/wireless/rtlwifi-accepted/Module.symvers" \
    "${result_dir}/rtlwifi.Module.symvers"
cp "${kernel_out}/drivers/net/wireless/xr819/Module.symvers" \
    "${result_dir}/xr819.Module.symvers"
cp "${kernel_src}/modules/gpu/mali-bifrost/driver/drivers/gpu/arm/midgard/Module.symvers" \
    "${result_dir}/mali.Module.symvers"
cp "${kernel_out}/drivers/net/wireless/aic8800-accepted/Module.symvers" \
    "${result_dir}/aic8800.Module.symvers"
"${kernel_src}/scripts/extract-ikconfig" "${result_dir}/Image" > "${result_dir}/image-extracted.config"
cmp "${result_dir}/built.config" "${result_dir}/image-extracted.config"

find "${kernel_out}/arch/arm64/boot/dts" -type f -name '*.dtb' -print0 \
    | sort -z | xargs -0 -r sha256sum > "${result_dir}/dtb-sha256.txt"
find "${modules_root}/lib/modules" -type f -name '*.ko' -print0 \
    | sort -z | xargs -0 -r sha256sum > "${result_dir}/module-sha256.txt"
find "${modules_root}/lib/modules" -type f -name '*.ko' -print0 \
    | sort -z | while IFS= read -r -d '' module; do
        printf '%s\t%s\t%s\t%s\n' \
            "$(basename "${module}")" \
            "$(modinfo -F name "${module}")" \
            "$(modinfo -F vermagic "${module}")" \
            "$(modinfo -F depends "${module}")"
    done > "${result_dir}/modules.tsv"

git -C "${kernel_src}" diff --check
git -C "${kernel_src}" diff -- \
    drivers/media/rc/rc-main.c drivers/media/rc/rc-sunxi-keymaps.c \
    > "${result_dir}/accepted-external-source.diff"
git -C "${kernel_src}" status --short > "${result_dir}/build-worktree-status.txt"
image_magic=$(od -An -tx1 -j56 -N4 "${result_dir}/Image" | tr -d ' \n')
test "${image_magic}" = 41524d64
{
    git -C "${kernel_src}" rev-parse HEAD
    git -C "${kernel_src}" rev-parse 'HEAD^{tree}'
    git -C "${xr819_donor_repo}" rev-parse HEAD
    git -C "${xr819_donor_repo}" rev-parse \
        'HEAD:kernel/linux-5.4/drivers/net/wireless/xr819'
    git -C "${aic8800_donor_repo}" rev-parse HEAD
    git -C "${aic8800_donor_repo}" rev-parse \
        'HEAD:drivers/net/wireless/aic8800'
    git -C "${source_repo}" rev-parse \
        '9ab7a758149d3c9b721878a0c18b3f9c5d6c93e6:drivers/net/wireless/realtek/rtlwifi'
    "${clang_bin}/clang" --version | head -2
    make -s -C "${kernel_src}" O="${kernel_out}" kernelrelease
    printf 'ARM64 Image magic at byte 56: %s\n' "${image_magic}"
    stat -c '%s  %n' "${result_dir}/Image"
    sha256sum \
        "${result_dir}/Image" \
        "${result_dir}/built.config" \
        "${result_dir}/Module.symvers" \
        "${result_dir}/System.map" \
        "${result_dir}/accepted-external-source.diff"
} > "${result_dir}/build-identity.txt"

grep -q '0x00ff404d, KEY_POWER' "${kernel_src}/drivers/media/rc/rc-sunxi-keymaps.c"
grep -q '0x00ff400b, KEY_UP' "${kernel_src}/drivers/media/rc/rc-sunxi-keymaps.c"
! grep -q '0x00ff4054' "${kernel_src}/drivers/media/rc/rc-sunxi-keymaps.c"
grep -q '^#ifdef CONFIG_SUNXI_MULTI_IR_SUPPORT$' "${kernel_src}/drivers/media/rc/rc-main.c"
grep -q '^# CONFIG_SUNXI_MULTI_IR_SUPPORT is not set$' "${result_dir}/built.config"
grep -q '^CONFIG_ARCH_SUN50IW9=y$' "${result_dir}/built.config"
grep -q '^CONFIG_SUNXI_SOC_NAME="sun50iw9"$' "${result_dir}/built.config"
grep -q '^CONFIG_SUNXI_GPU_TYPE="mali-g31"$' "${result_dir}/built.config"
test "$(find "${modules_root}/lib/modules" -type f -name '*.ko' | wc -l)" -eq 22

sha256sum "${result_dir}/"* > "${result_dir}/SHA256SUMS"
