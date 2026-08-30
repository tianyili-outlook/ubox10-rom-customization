#!/usr/bin/env bash
# DIAGNOSTIC ONLY / SINGLE-VARIABLE HEVC VISIBLE-CROP TEST / NOT r8.
set -euo pipefail

diag2_action=${1:-check}
diag2_aosp_root=${2:-/work/src/ubox10-a16-ceiling}
diag2_here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
diag2_patch=${diag2_here}/patches/0001-frameworks-av-hevc-visible-crop.patch

case ${diag2_action} in
    check|apply|revert) ;;
    *) echo "usage: $0 {check|apply|revert} [aosp-root]" >&2; exit 2 ;;
esac

diag2_require_revision() {
    local repository=$1 expected=$2 actual
    actual=$(git -C "${diag2_aosp_root}/${repository}" rev-parse HEAD)
    test "${actual}" = "${expected}" || {
        echo "revision mismatch: ${repository}: ${actual}" >&2
        exit 3
    }
}

diag2_require_hash() {
    local expected=$1 relative=$2 actual
    actual=$(sha256sum "${diag2_aosp_root}/${relative}" | awk '{print $1}')
    test "${actual}" = "${expected}" || return 1
}

diag2_require_revision frameworks/av d1137ad4b24b686d9b00fd1b7be1b520f7b6ee2b

diag2_base_hashes() {
    diag2_require_hash 88d26648f93a043951844e4ad90c6d748931f76d1ec20cff74d0a3b479687fe6 \
        frameworks/av/media/libstagefright/ACodec.cpp
}

diag2_patched_hashes() {
    diag2_require_hash bf1600cf28cf3180cc77f869b74350716d98c7cd3760c8336751af000c4e945c \
        frameworks/av/media/libstagefright/ACodec.cpp
}

case ${diag2_action} in
    apply)
        diag2_base_hashes
        git -C "${diag2_aosp_root}/frameworks/av" apply "${diag2_patch}"
        diag2_patched_hashes
        ;;
    revert)
        diag2_patched_hashes
        git -C "${diag2_aosp_root}/frameworks/av" apply --reverse "${diag2_patch}"
        diag2_base_hashes
        ;;
    check)
        if diag2_patched_hashes 2>/dev/null; then
            echo "UBOX_R7_DIAG2_HEVC_CROP source state: PATCHED"
        elif diag2_base_hashes 2>/dev/null; then
            echo "UBOX_R7_DIAG2_HEVC_CROP source state: DIAG1A_WITHOUT_CROP_DELTA"
        else
            echo "UBOX_R7_DIAG2_HEVC_CROP source state: UNEXPECTED" >&2
            exit 4
        fi
        ;;
esac
