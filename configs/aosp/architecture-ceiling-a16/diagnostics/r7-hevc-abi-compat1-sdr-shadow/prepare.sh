#!/usr/bin/env bash
# EXPERIMENTAL SDR YV12 MALI METADATA ABI COMPATIBILITY / NOT r8.
set -euo pipefail

compat1_action=${1:-check}
compat1_aosp_root=${2:-/work/src/ubox10-a16-ceiling}
compat1_here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
compat1_patch=${compat1_here}/patches/0001-skia-mali-sdr-metadata-shadow.patch

case ${compat1_action} in
    check|apply|revert) ;;
    *) echo "usage: $0 {check|apply|revert} [aosp-root]" >&2; exit 2 ;;
esac

compat1_require_revision() {
    local actual
    actual=$(git -C "${compat1_aosp_root}/external/skia" rev-parse HEAD)
    test "${actual}" = 4c18a9680d52c2cd5e35cfef2f548635a445fafe || {
        echo "external/skia revision mismatch: ${actual}" >&2
        exit 3
    }
}

compat1_require_hash() {
    local expected=$1 relative=$2 actual
    actual=$(sha256sum "${compat1_aosp_root}/${relative}" | awk '{print $1}')
    test "${actual}" = "${expected}"
}

compat1_diag3a_hashes() {
    compat1_require_hash 8bee83b3c6b97a4a86a75dce5cddfb1cb9e0f6a08f97579bd0c5dd32a8395192 \
        external/skia/src/gpu/ganesh/gl/AHardwareBufferGL.cpp
    test ! -e "${compat1_aosp_root}/external/skia/src/gpu/ganesh/gl/UBOXR7Compat1Metadata.h"
}

compat1_patched_hashes() {
    compat1_require_hash 6d44e630c8553eb08f0566bcfd1404232641fdba9049af93c38c29eef4a55c3f \
        external/skia/src/gpu/ganesh/gl/AHardwareBufferGL.cpp
    compat1_require_hash dc745282d45871a0f05473c7c684bae4fcfa707c11ed66a97d3e764a1401f61f \
        external/skia/src/gpu/ganesh/gl/UBOXR7Compat1Metadata.h
}

compat1_require_revision
case ${compat1_action} in
    apply)
        compat1_diag3a_hashes
        git -C "${compat1_aosp_root}/external/skia" apply --unidiff-zero "${compat1_patch}"
        compat1_patched_hashes
        ;;
    revert)
        compat1_patched_hashes
        git -C "${compat1_aosp_root}/external/skia" apply --unidiff-zero --reverse "${compat1_patch}"
        compat1_diag3a_hashes
        ;;
    check)
        if compat1_patched_hashes 2>/dev/null; then
            echo "UBOX_R7_COMPAT1 source state: PATCHED"
        elif compat1_diag3a_hashes 2>/dev/null; then
            echo "UBOX_R7_COMPAT1 source state: DIAG3A_WITHOUT_COMPATIBILITY_VIEW"
        else
            echo "UBOX_R7_COMPAT1 source state: UNEXPECTED" >&2
            exit 4
        fi
        ;;
esac
