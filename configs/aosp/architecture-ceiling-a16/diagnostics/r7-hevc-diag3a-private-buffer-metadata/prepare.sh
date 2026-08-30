#!/usr/bin/env bash
# DIAGNOSTIC ONLY / FNV WRAP TRANSPARENCY CORRECTION / NOT r8.
set -euo pipefail

diag3a_action=${1:-check}
diag3a_aosp_root=${2:-/work/src/ubox10-a16-ceiling}
diag3a_here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
diag3a_patch=${diag3a_here}/patches/0001-libstagefright-fnv-wrap.patch

case ${diag3a_action} in
    check|apply|revert) ;;
    *) echo "usage: $0 {check|apply|revert} [aosp-root]" >&2; exit 2 ;;
esac

diag3a_require_revision() {
    local repository=$1 expected=$2 actual
    actual=$(git -C "${diag3a_aosp_root}/${repository}" rev-parse HEAD)
    test "${actual}" = "${expected}" || {
        echo "revision mismatch: ${repository}: ${actual}" >&2
        exit 3
    }
}

diag3a_require_hash() {
    local expected=$1 relative=$2 actual
    actual=$(sha256sum "${diag3a_aosp_root}/${relative}" | awk '{print $1}')
    test "${actual}" = "${expected}" || return 1
}

diag3a_require_revision frameworks/av d1137ad4b24b686d9b00fd1b7be1b520f7b6ee2b

diag3a_diag3_hashes() {
    diag3a_require_hash def12b9173aabffedb5efe8b18e30ea0cb63d0c036942cdd537d58f21be10563 \
        frameworks/av/media/libstagefright/UBOXR7Diag3PrivateHandle.h || return 1
    diag3a_require_hash fb661be5229c5846eacf0bb7a1a226708e7f57a9a367dab02e9a18860d41d80c \
        frameworks/av/media/libstagefright/ACodec.cpp || return 1
    diag3a_require_hash a7348cf143e70ddb8c5e92e52e970c93c12d2f7a39b091f6bfa11b3c1d09b153 \
        frameworks/av/media/libstagefright/include/media/stagefright/ACodec.h
}

diag3a_patched_hashes() {
    diag3a_require_hash b5fc7a29869836e35a8a4f9b31e0d9386609da013336c04ebb93df01dae5ea47 \
        frameworks/av/media/libstagefright/UBOXR7Diag3PrivateHandle.h || return 1
    diag3a_require_hash fb661be5229c5846eacf0bb7a1a226708e7f57a9a367dab02e9a18860d41d80c \
        frameworks/av/media/libstagefright/ACodec.cpp || return 1
    diag3a_require_hash a7348cf143e70ddb8c5e92e52e970c93c12d2f7a39b091f6bfa11b3c1d09b153 \
        frameworks/av/media/libstagefright/include/media/stagefright/ACodec.h
}

case ${diag3a_action} in
    apply)
        diag3a_diag3_hashes
        patch --batch --strip=1 --directory="${diag3a_aosp_root}/frameworks/av" < "${diag3a_patch}"
        diag3a_patched_hashes
        ;;
    revert)
        diag3a_patched_hashes
        patch --batch --reverse --strip=1 --directory="${diag3a_aosp_root}/frameworks/av" < "${diag3a_patch}"
        diag3a_diag3_hashes
        ;;
    check)
        if diag3a_patched_hashes 2>/dev/null; then
            echo "UBOX_R7_DIAG3A source state: PATCHED"
        elif diag3a_diag3_hashes 2>/dev/null; then
            echo "UBOX_R7_DIAG3A source state: DIAG3_WITHOUT_FNV_WRAP_CORRECTION"
        else
            echo "UBOX_R7_DIAG3A source state: UNEXPECTED" >&2
            exit 4
        fi
        ;;
esac
