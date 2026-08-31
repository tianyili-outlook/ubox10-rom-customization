#!/usr/bin/env bash
# COMPAT1A SHADOW-FD SIZE CORRECTION / EXPERIMENTAL SDR YV12 / NOT r8.
set -euo pipefail

compat1a_action=${1:-check}
compat1a_aosp_root=${2:-/work/src/ubox10-a16-ceiling}
compat1a_here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
compat1a_patch=${compat1a_here}/patches/0001-skia-compat1a-sized-shadow-memfd.patch

case ${compat1a_action} in
    check|apply|revert) ;;
    *) echo "usage: $0 {check|apply|revert} [aosp-root]" >&2; exit 2 ;;
esac

compat1a_require_revision() {
    local actual
    actual=$(git -C "${compat1a_aosp_root}/external/skia" rev-parse HEAD)
    test "${actual}" = 4c18a9680d52c2cd5e35cfef2f548635a445fafe || {
        echo "external/skia revision mismatch: ${actual}" >&2
        exit 3
    }
}

compat1a_require_hash() {
    local expected=$1 relative=$2 actual
    actual=$(sha256sum "${compat1a_aosp_root}/${relative}" | awk '{print $1}')
    test "${actual}" = "${expected}"
}

compat1a_compat1_hashes() {
    compat1a_require_hash 6d44e630c8553eb08f0566bcfd1404232641fdba9049af93c38c29eef4a55c3f \
        external/skia/src/gpu/ganesh/gl/AHardwareBufferGL.cpp
    compat1a_require_hash dc745282d45871a0f05473c7c684bae4fcfa707c11ed66a97d3e764a1401f61f \
        external/skia/src/gpu/ganesh/gl/UBOXR7Compat1Metadata.h
}

compat1a_patched_hashes() {
    compat1a_require_hash 328cc3f7e68616e1b19522d5b9047fb2fa6cabc71c1dc28dcf33c02a7691c1d3 \
        external/skia/src/gpu/ganesh/gl/AHardwareBufferGL.cpp
    compat1a_require_hash 98228a9599eedfcd6c073124c31a48e105e3360e7c62ed05c4c77d2300951294 \
        external/skia/src/gpu/ganesh/gl/UBOXR7Compat1Metadata.h
}

compat1a_require_revision
case ${compat1a_action} in
    apply)
        compat1a_compat1_hashes
        git -C "${compat1a_aosp_root}/external/skia" apply --unidiff-zero "${compat1a_patch}"
        compat1a_patched_hashes
        ;;
    revert)
        compat1a_patched_hashes
        git -C "${compat1a_aosp_root}/external/skia" apply --unidiff-zero --reverse "${compat1a_patch}"
        compat1a_compat1_hashes
        ;;
    check)
        if compat1a_patched_hashes 2>/dev/null; then
            echo "UBOX_R7_COMPAT1A source state: PATCHED"
        elif compat1a_compat1_hashes 2>/dev/null; then
            echo "UBOX_R7_COMPAT1A source state: COMPAT1_WITHOUT_FD_CORRECTION"
        else
            echo "UBOX_R7_COMPAT1A source state: UNEXPECTED" >&2
            exit 4
        fi
        ;;
esac
