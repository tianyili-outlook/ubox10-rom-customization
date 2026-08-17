#!/usr/bin/env bash

set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
    echo "error: run through 'wsl.exe ... -u root -- bash run-disposable-build.sh'" >&2
    exit 2
fi

ceiling_variant=${1:-}
ceiling_jobs=${2:-1}
ceiling_aosp_root=${CEILING_AOSP_ROOT:-/home/tianyi/ubox10-a16-ceiling}
ceiling_out_image=${CEILING_OUT_IMAGE:-/mnt/d/ubox10-ceiling-study-storage/a16-out.ext4}
ceiling_mount_dir=${CEILING_MOUNT_DIR:-/mnt/wsl/ubox10-a16-out-volume}
ceiling_out_relative=out-ceiling
ceiling_out_dir=${ceiling_aosp_root}/${ceiling_out_relative}
ceiling_swap_size=${CEILING_SWAP_SIZE:-7G}
ceiling_swap_file=${ceiling_mount_dir}/.ceiling-build.swap
ceiling_legacy_overflow_swap=${ceiling_mount_dir}/.ceiling-graph-overflow.swap
ceiling_soong_gomemlimit=${CEILING_SOONG_GOMEMLIMIT:-6GiB}
ceiling_cpuset=${CEILING_CPUSET:-0-7}
ceiling_cgroup=${CEILING_CGROUP:-/sys/fs/cgroup/ubox10-a16-build}
ceiling_memory_high=${CEILING_MEMORY_HIGH:-9728M}
ceiling_memory_max=${CEILING_MEMORY_MAX:-10G}
ceiling_memory_swap_max=${CEILING_MEMORY_SWAP_MAX:-7G}

case ${ceiling_variant} in
    arm32)
        ceiling_product=ubox10_ceiling_arm
        ceiling_log=${ceiling_aosp_root}/out-study/logs/prototype-a-arm32-systemimage.log
        ;;
    mixed)
        ceiling_product=ubox10_ceiling_arm64
        ceiling_log=${ceiling_aosp_root}/out-study/logs/prototype-b-mixed-systemimage.log
        ;;
    *)
        echo "usage: $0 {arm32|mixed} [jobs]" >&2
        exit 2
        ;;
esac

if ! [[ ${ceiling_jobs} =~ ^[1-9][0-9]*$ ]]; then
    echo "error: jobs must be a positive integer" >&2
    exit 2
fi

if [[ ! -d ${ceiling_aosp_root} || ! -f ${ceiling_aosp_root}/build/envsetup.sh ]]; then
    echo "error: Android source tree not found at ${ceiling_aosp_root}" >&2
    exit 3
fi

if [[ ! -f ${ceiling_out_image} ]]; then
    echo "error: disposable output image not found at ${ceiling_out_image}" >&2
    exit 3
fi

if [[ ! -d ${ceiling_out_dir} ]]; then
    echo "error: bootstrap output directory not found at ${ceiling_out_dir}" >&2
    exit 3
fi

if mountpoint -q "${ceiling_mount_dir}" || mountpoint -q "${ceiling_out_dir}"; then
    echo "error: an output mount is already active" >&2
    exit 4
fi

ceiling_owner=$(stat -c '%U' "${ceiling_aosp_root}")
ceiling_group=$(stat -c '%G' "${ceiling_aosp_root}")
if [[ ${ceiling_owner} == UNKNOWN || ${ceiling_group} == UNKNOWN ]]; then
    echo "error: cannot resolve Android tree owner" >&2
    exit 4
fi

mkdir -p "${ceiling_mount_dir}" "$(dirname "${ceiling_log}")"

ceiling_cleanup() {
    set +e
    if swapon --show=NAME --noheadings | grep -Fxq "${ceiling_swap_file}"; then
        swapoff "${ceiling_swap_file}"
    fi
    sync
    if mountpoint -q "${ceiling_out_dir}"; then
        umount "${ceiling_out_dir}"
    fi
    if mountpoint -q "${ceiling_mount_dir}"; then
        umount "${ceiling_mount_dir}"
    fi
    if [[ -d ${ceiling_cgroup} ]]; then
        rmdir "${ceiling_cgroup}"
    fi
}
trap ceiling_cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

mount -o loop,noatime "${ceiling_out_image}" "${ceiling_mount_dir}"
ceiling_mounted_source=$(findmnt -n -o SOURCE --target "${ceiling_mount_dir}")
ceiling_mounted_type=$(findmnt -n -o FSTYPE --target "${ceiling_mount_dir}")
ceiling_mounted_label=$(blkid -s LABEL -o value "${ceiling_mounted_source}")
if [[ ${ceiling_mounted_source} != /dev/loop* || ${ceiling_mounted_type} != ext4 ||
      ${ceiling_mounted_label} != UBOX10_A16_OUT ]]; then
    echo "error: mounted output is not the labeled disposable ext4 loop image" >&2
    exit 5
fi
chown "${ceiling_owner}:${ceiling_group}" "${ceiling_mount_dir}"

if [[ ! -e ${ceiling_mount_dir}/.ceiling-bootstrap-complete ]]; then
    find "${ceiling_mount_dir}" -mindepth 1 -maxdepth 1 \
        ! -name lost+found -exec rm -rf -- {} +
    runuser -u "${ceiling_owner}" -- cp -a "${ceiling_out_dir}/." "${ceiling_mount_dir}/"
    runuser -u "${ceiling_owner}" -- touch "${ceiling_mount_dir}/.ceiling-bootstrap-complete"
fi

ceiling_swap_bytes=$(numfmt --from=iec "${ceiling_swap_size}")
if [[ -e ${ceiling_swap_file} ]] &&
   (( $(stat -c '%s' "${ceiling_swap_file}") < ceiling_swap_bytes )); then
    if swapon --show=NAME --noheadings | grep -Fxq "${ceiling_swap_file}"; then
        echo "error: undersized disposable swapfile is active" >&2
        exit 5
    fi
    rm -- "${ceiling_swap_file}"
fi
if [[ -e ${ceiling_legacy_overflow_swap} ]]; then
    if swapon --show=NAME --noheadings | grep -Fxq "${ceiling_legacy_overflow_swap}"; then
        echo "error: legacy overflow swapfile is active" >&2
        exit 5
    fi
    rm -- "${ceiling_legacy_overflow_swap}"
fi
if [[ ! -e ${ceiling_swap_file} ]]; then
    fallocate -l "${ceiling_swap_size}" "${ceiling_swap_file}"
    chmod 0600 "${ceiling_swap_file}"
    mkswap -L UBOX10_A16_BUILD_SWAP "${ceiling_swap_file}" >/dev/null
fi
swapon -p 100 "${ceiling_swap_file}"

mount --bind "${ceiling_mount_dir}" "${ceiling_out_dir}"

if [[ -e ${ceiling_cgroup} ]]; then
    echo "error: build cgroup already exists at ${ceiling_cgroup}" >&2
    exit 6
fi
mkdir "${ceiling_cgroup}"
echo "${ceiling_memory_high}" > "${ceiling_cgroup}/memory.high"
echo "${ceiling_memory_max}" > "${ceiling_cgroup}/memory.max"
echo "${ceiling_memory_swap_max}" > "${ceiling_cgroup}/memory.swap.max"
echo 1 > "${ceiling_cgroup}/memory.oom.group"

ceiling_build_status=0
(
    echo "${BASHPID}" > "${ceiling_cgroup}/cgroup.procs"
    if ! taskset -c "${ceiling_cpuset}" true; then
        echo "error: invalid or unavailable CPU set: ${ceiling_cpuset}" >&2
        exit 6
    fi
    exec taskset -c "${ceiling_cpuset}" runuser -u "${ceiling_owner}" -- env \
        CEILING_AOSP_ROOT="${ceiling_aosp_root}" \
        CEILING_OUT_DIR="${ceiling_out_relative}" \
        CEILING_PRODUCT="${ceiling_product}" \
        CEILING_LOG="${ceiling_log}" \
        CEILING_JOBS="${ceiling_jobs}" \
        SOONG_GOMEMLIMIT="${ceiling_soong_gomemlimit}" \
        bash -c '
            set -o pipefail
            cd "${CEILING_AOSP_ROOT}"
            export OUT_DIR=${CEILING_OUT_DIR}
            export BUILD_NUMBER=DISPOSABLE_CEILING_R4
            source build/envsetup.sh >/dev/null
            lunch "${CEILING_PRODUCT}-bp4a-userdebug" >/dev/null
            m -j"${CEILING_JOBS}" systemimage 2>&1 | tee "${CEILING_LOG}"
        '
) || ceiling_build_status=$?

exit ${ceiling_build_status}
