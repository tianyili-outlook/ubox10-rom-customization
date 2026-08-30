#!/usr/bin/env bash
# DIAGNOSTIC ONLY / READ-ONLY PRIVATE BUFFER METADATA / NOT r8.
set -euo pipefail

diag3_action=${1:-check}
diag3_aosp_root=${2:-/work/src/ubox10-a16-ceiling}
diag3_here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
diag3_patches=${diag3_here}/patches

case ${diag3_action} in
    check|apply|revert) ;;
    *) echo "usage: $0 {check|apply|revert} [aosp-root]" >&2; exit 2 ;;
esac

diag3_require_revision() {
    local repository=$1 expected=$2 actual
    actual=$(git -C "${diag3_aosp_root}/${repository}" rev-parse HEAD)
    test "${actual}" = "${expected}" || {
        echo "revision mismatch: ${repository}: ${actual}" >&2
        exit 3
    }
}

diag3_require_hash() {
    local expected=$1 relative=$2 actual
    actual=$(sha256sum "${diag3_aosp_root}/${relative}" | awk '{print $1}')
    test "${actual}" = "${expected}" || return 1
}

diag3_require_absent() {
    test ! -e "${diag3_aosp_root}/$1"
}

diag3_require_revision frameworks/av d1137ad4b24b686d9b00fd1b7be1b520f7b6ee2b
diag3_require_revision external/skia 4c18a9680d52c2cd5e35cfef2f548635a445fafe

diag3_base_hashes() {
    diag3_require_hash dd4a45da3dc29bcb12ed0a9decc8b9ad3261fddf30af0b231906b3557909566d \
        hardware/aw/gpu/mali-bifrost/gralloc/src/mali_gralloc_bufferallocation.cpp
    diag3_require_hash 1c1481d2f3a9a2b5b76e54482dcc1667fc3abf89b58cbed492d7826c1c15e12f \
        hardware/aw/gpu/mali-bifrost/gralloc/src/mali_gralloc_reference.cpp
    diag3_require_hash bf1600cf28cf3180cc77f869b74350716d98c7cd3760c8336751af000c4e945c \
        frameworks/av/media/libstagefright/ACodec.cpp
    diag3_require_hash a30bb5e481f88abf42356eaa48ba3b358368c5fe8f324ea21149b90a9d0ff75e \
        frameworks/av/media/libstagefright/include/media/stagefright/ACodec.h
    diag3_require_hash eef014953484f637e9b22f689e56d126e7a8ee8aabe8831cda91bc532ecf9c30 \
        external/skia/src/gpu/ganesh/gl/AHardwareBufferGL.cpp
    diag3_require_absent hardware/aw/gpu/mali-bifrost/gralloc/src/ubox_r7_diag3_private_handle.h
    diag3_require_absent frameworks/av/media/libstagefright/UBOXR7Diag3PrivateHandle.h
    diag3_require_absent external/skia/src/gpu/ganesh/gl/UBOXR7Diag3PrivateHandle.h
}

diag3_patched_hashes() {
    diag3_require_hash d63b8596dcb0bcb109643f72a068bf23451dd8359ff2769a95b3bbaa6e40bb50 \
        hardware/aw/gpu/mali-bifrost/gralloc/src/mali_gralloc_bufferallocation.cpp
    diag3_require_hash 8e12f67b00c275e3d2b386d247ddd08701f319f3b95f711807504531512a2712 \
        hardware/aw/gpu/mali-bifrost/gralloc/src/mali_gralloc_reference.cpp
    diag3_require_hash fb661be5229c5846eacf0bb7a1a226708e7f57a9a367dab02e9a18860d41d80c \
        frameworks/av/media/libstagefright/ACodec.cpp
    diag3_require_hash a7348cf143e70ddb8c5e92e52e970c93c12d2f7a39b091f6bfa11b3c1d09b153 \
        frameworks/av/media/libstagefright/include/media/stagefright/ACodec.h
    diag3_require_hash 8bee83b3c6b97a4a86a75dce5cddfb1cb9e0f6a08f97579bd0c5dd32a8395192 \
        external/skia/src/gpu/ganesh/gl/AHardwareBufferGL.cpp
    diag3_require_hash def12b9173aabffedb5efe8b18e30ea0cb63d0c036942cdd537d58f21be10563 \
        hardware/aw/gpu/mali-bifrost/gralloc/src/ubox_r7_diag3_private_handle.h
    diag3_require_hash def12b9173aabffedb5efe8b18e30ea0cb63d0c036942cdd537d58f21be10563 \
        frameworks/av/media/libstagefright/UBOXR7Diag3PrivateHandle.h
    diag3_require_hash def12b9173aabffedb5efe8b18e30ea0cb63d0c036942cdd537d58f21be10563 \
        external/skia/src/gpu/ganesh/gl/UBOXR7Diag3PrivateHandle.h
}

diag3_apply() {
    patch --batch --strip=1 --directory="${diag3_aosp_root}" < \
        "${diag3_patches}/0001-gralloc-private-handle-sidecar-trace.patch"
    git -C "${diag3_aosp_root}/frameworks/av" apply \
        "${diag3_patches}/0002-frameworks-av-private-handle-boundaries.patch"
    git -C "${diag3_aosp_root}/external/skia" apply \
        "${diag3_patches}/0003-external-skia-private-handle-pre-egl.patch"
}

diag3_revert() {
    git -C "${diag3_aosp_root}/external/skia" apply --reverse \
        "${diag3_patches}/0003-external-skia-private-handle-pre-egl.patch"
    git -C "${diag3_aosp_root}/frameworks/av" apply --reverse \
        "${diag3_patches}/0002-frameworks-av-private-handle-boundaries.patch"
    patch --batch --reverse --strip=1 --directory="${diag3_aosp_root}" < \
        "${diag3_patches}/0001-gralloc-private-handle-sidecar-trace.patch"
}

case ${diag3_action} in
    apply)
        diag3_base_hashes
        diag3_apply
        diag3_patched_hashes
        ;;
    revert)
        diag3_patched_hashes
        diag3_revert
        diag3_base_hashes
        ;;
    check)
        if diag3_patched_hashes 2>/dev/null; then
            echo "UBOX_R7_DIAG3 source state: PATCHED"
        elif diag3_base_hashes 2>/dev/null; then
            echo "UBOX_R7_DIAG3 source state: DIAG2_WITHOUT_METADATA_TRACE"
        else
            echo "UBOX_R7_DIAG3 source state: UNEXPECTED" >&2
            exit 4
        fi
        ;;
esac
