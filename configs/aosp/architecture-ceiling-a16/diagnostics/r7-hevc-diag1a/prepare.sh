#!/usr/bin/env bash
# DIAGNOSTIC ONLY / BOOT-COMPATIBILITY CORRECTION / NOT AN HEVC REPAIR / NOT r8.
set -euo pipefail

diag1a_action=${1:-check}
diag1a_aosp_root=${2:-/work/src/ubox10-a16-ceiling}
diag1a_here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
diag1a_patch=${diag1a_here}/patches/0001-gralloc-arm32-vndk31-libcpp-backdeploy.patch
diag1_prepare=${diag1a_here}/../r7-hevc-diag1/prepare.sh

case ${diag1a_action} in
    check|apply|revert) ;;
    *) echo "usage: $0 {check|apply|revert} [aosp-root]" >&2; exit 2 ;;
esac

diag1a_require_hash() {
    local diag1a_expected=$1
    local diag1a_path=$2
    local diag1a_actual
    diag1a_actual=$(sha256sum "${diag1a_aosp_root}/${diag1a_path}" | awk '{print $1}')
    test "${diag1a_actual}" = "${diag1a_expected}" || {
        echo "source hash mismatch: ${diag1a_path}: ${diag1a_actual}" >&2
        return 1
    }
}

diag1a_require_diag1() {
    local diag1a_state
    diag1a_state=$("${diag1_prepare}" check "${diag1a_aosp_root}")
    [[ ${diag1a_state} == *"source state: PATCHED"* ]] || {
        echo "diag1 instrumentation overlay is not exactly applied" >&2
        exit 3
    }
}

diag1a_base_hashes() {
    diag1a_require_hash 378ae5af1897f86f7c5341a0f2b935bfb37722a1ec7b7d8557f3960cb1bb09b4 hardware/aw/gpu/mali-bifrost/gralloc/src/Android.mk
    diag1a_require_hash 4f3bb9bd1715b45ac1f59391b9738144a97855d046357503f646d7802431d689 hardware/aw/gpu/mali-bifrost/gralloc/src/vndk31_libcpp_backdeploy.h
}

diag1a_patched_hashes() {
    diag1a_require_hash fe3db3087ebe24b0399ab736a10144808a09b6cb954727caebe62ca35d5610bf hardware/aw/gpu/mali-bifrost/gralloc/src/Android.mk
    diag1a_require_hash 528bc00d55b88763d0b7ab9498796d7e7db56c954a821d441629a13721101439 hardware/aw/gpu/mali-bifrost/gralloc/src/vndk31_libcpp_backdeploy.h
}

diag1a_require_diag1
case ${diag1a_action} in
    apply)
        diag1a_base_hashes
        patch --batch --strip=1 --directory="${diag1a_aosp_root}" < "${diag1a_patch}"
        diag1a_patched_hashes
        ;;
    revert)
        diag1a_patched_hashes
        patch --batch --reverse --strip=1 --directory="${diag1a_aosp_root}" < "${diag1a_patch}"
        diag1a_base_hashes
        ;;
    check)
        if diag1a_patched_hashes 2>/dev/null; then
            echo "UBOX_R7_DIAG1A source state: PATCHED"
        elif diag1a_base_hashes 2>/dev/null; then
            echo "UBOX_R7_DIAG1A source state: DIAG1_WITHOUT_BOOT_CORRECTION"
        else
            echo "UBOX_R7_DIAG1A source state: UNEXPECTED" >&2
            exit 4
        fi
        ;;
esac
