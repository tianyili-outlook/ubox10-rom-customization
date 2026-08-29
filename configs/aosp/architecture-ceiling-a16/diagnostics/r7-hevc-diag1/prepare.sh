#!/usr/bin/env bash
# DIAGNOSTIC ONLY / NO FUNCTIONAL REPAIR / NOT r8.
set -euo pipefail

diag_action=${1:-check}
diag_aosp_root=${2:-/work/src/ubox10-a16-ceiling}
diag_here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
diag_patches=${diag_here}/patches

case ${diag_action} in
    check|apply|revert) ;;
    *) echo "usage: $0 {check|apply|revert} [aosp-root]" >&2; exit 2 ;;
esac

diag_require_revision() {
    local diag_repository=$1
    local diag_expected=$2
    local diag_actual
    diag_actual=$(git -C "${diag_aosp_root}/${diag_repository}" rev-parse HEAD)
    test "${diag_actual}" = "${diag_expected}" || {
        echo "revision mismatch: ${diag_repository}: ${diag_actual}" >&2
        exit 3
    }
}

diag_require_hash() {
    local diag_expected=$1
    local diag_path=$2
    local diag_actual
    diag_actual=$(sha256sum "${diag_aosp_root}/${diag_path}" | awk '{print $1}')
    test "${diag_actual}" = "${diag_expected}" || {
        echo "source hash mismatch: ${diag_path}: ${diag_actual}" >&2
        exit 4
    }
}

diag_require_revision frameworks/native d862b53356dc26794fb5451782806979c46e6769
diag_require_revision external/skia 4c18a9680d52c2cd5e35cfef2f548635a445fafe
diag_require_revision frameworks/av d1137ad4b24b686d9b00fd1b7be1b520f7b6ee2b

diag_base_hashes() {
    diag_require_hash 026aae9505baead76e4031abe46cfdb9410cd03e2172a718f0e73f40bbf204c8 frameworks/native/libs/renderengine/skia/SkiaRenderEngine.cpp
    diag_require_hash b6fc78ac41b519753666c222594f954fe014efc3dd856e001cdaf8e0f3342e94 frameworks/native/libs/renderengine/skia/compat/GaneshBackendTexture.cpp
    diag_require_hash e236b1b942f349fb23fd5507347937c245a500299ddf1cc53e23526358552633 external/skia/src/gpu/ganesh/gl/AHardwareBufferGL.cpp
    diag_require_hash 06a686e91e5d56140b23e13a452c5ab4ec7775fb683664aec6fc2517110e69ee frameworks/av/media/libstagefright/MediaCodec.cpp
    diag_require_hash 1e3c7a3453db970412ea67c580f242d50056e7e17ffa34ec4987939c4e6443a2 frameworks/av/media/libstagefright/ACodec.cpp
    diag_require_hash 9db9dd8ba83f22c2fd09804d95d27c406490c502f265f23a3adc8b3323f4f71f frameworks/av/media/libstagefright/SurfaceUtils.cpp
    diag_require_hash 1108e1512c5062ee44fcd22a5c8c75a414e1f7abd7ad2bb7eb608c289dfc593c hardware/aw/gpu/mali-bifrost/gralloc/src/mali_gralloc_bufferallocation.cpp
    diag_require_hash 7cee72eb2603059dc28adad1705e978846800ca05790aae45c8afcaebb4b04a3 hardware/aw/gpu/mali-bifrost/gralloc/src/mali_gralloc_reference.cpp
}

diag_patched_hashes() {
    diag_require_hash 055c8f0516f16c948ea2d95c1fcae7306e7092e50adb4b686335ac2bc0942920 frameworks/native/libs/renderengine/skia/SkiaRenderEngine.cpp
    diag_require_hash f5ddd5cf31927671fb39f72741b5c5780eea2d9ec6cd7e410fc58e0140df4a68 frameworks/native/libs/renderengine/skia/compat/GaneshBackendTexture.cpp
    diag_require_hash eef014953484f637e9b22f689e56d126e7a8ee8aabe8831cda91bc532ecf9c30 external/skia/src/gpu/ganesh/gl/AHardwareBufferGL.cpp
    diag_require_hash 9808e8a87ae9a595311318c9c95bf8577eb4a6ad0d4e1d4b48afe4db9e5ef71b frameworks/av/media/libstagefright/MediaCodec.cpp
    diag_require_hash 88d26648f93a043951844e4ad90c6d748931f76d1ec20cff74d0a3b479687fe6 frameworks/av/media/libstagefright/ACodec.cpp
    diag_require_hash d130d9240adf7a62511ff53d86b9462bae585f83863a98f01fec1a2c26afdf74 frameworks/av/media/libstagefright/SurfaceUtils.cpp
    diag_require_hash dd4a45da3dc29bcb12ed0a9decc8b9ad3261fddf30af0b231906b3557909566d hardware/aw/gpu/mali-bifrost/gralloc/src/mali_gralloc_bufferallocation.cpp
    diag_require_hash 1c1481d2f3a9a2b5b76e54482dcc1667fc3abf89b58cbed492d7826c1c15e12f hardware/aw/gpu/mali-bifrost/gralloc/src/mali_gralloc_reference.cpp
}

diag_apply() {
    git -C "${diag_aosp_root}/frameworks/native" apply "${diag_patches}/0001-frameworks-native-renderengine-trace.patch"
    git -C "${diag_aosp_root}/external/skia" apply "${diag_patches}/0002-external-skia-egl-gl-trace.patch"
    git -C "${diag_aosp_root}/frameworks/av" apply "${diag_patches}/0003-frameworks-av-media-native-window-trace.patch"
    patch --batch --strip=1 --directory="${diag_aosp_root}" < "${diag_patches}/0004-gralloc-private-contract-trace.patch"
}

diag_revert() {
    patch --batch --reverse --strip=1 --directory="${diag_aosp_root}" < "${diag_patches}/0004-gralloc-private-contract-trace.patch"
    git -C "${diag_aosp_root}/frameworks/av" apply --reverse "${diag_patches}/0003-frameworks-av-media-native-window-trace.patch"
    git -C "${diag_aosp_root}/external/skia" apply --reverse "${diag_patches}/0002-external-skia-egl-gl-trace.patch"
    git -C "${diag_aosp_root}/frameworks/native" apply --reverse "${diag_patches}/0001-frameworks-native-renderengine-trace.patch"
}

case ${diag_action} in
    apply)
        diag_base_hashes
        diag_apply
        diag_patched_hashes
        ;;
    revert)
        diag_patched_hashes
        diag_revert
        diag_base_hashes
        ;;
    check)
        if diag_patched_hashes 2>/dev/null; then
            echo "UBOX_R7_DIAG1 source state: PATCHED"
        elif diag_base_hashes 2>/dev/null; then
            echo "UBOX_R7_DIAG1 source state: CANONICAL_R7_UNPATCHED"
        else
            echo "UBOX_R7_DIAG1 source state: UNEXPECTED" >&2
            exit 5
        fi
        ;;
esac
