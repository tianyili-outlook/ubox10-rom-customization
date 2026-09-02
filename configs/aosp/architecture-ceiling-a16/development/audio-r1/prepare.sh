#!/usr/bin/env bash
# A16 DEV AUDIO R1 / RETAINED WRAPPER NULL-CALLBACK COMPATIBILITY / NOT r8 / NOT RELEASE.
set -euo pipefail

audio_r1_action=${1:-check}
audio_r1_aosp=${2:-/work/src/ubox10-a16-ceiling}
audio_r1_here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
audio_r1_contract=${audio_r1_here}/source-contract.json
audio_r1_patch=${audio_r1_here}/patches/0001-audio-hidl-guard-null-get-audio-port-v7.patch

case ${audio_r1_action} in check|apply|revert) ;; *)
    echo "usage: $0 {check|apply|revert} [aosp-root]" >&2; exit 2;; esac

audio_r1_state() {
    python3 - "${audio_r1_aosp}" "${audio_r1_contract}" "$1" <<'PY'
import hashlib, json, pathlib, sys
root, contract, key = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), sys.argv[3]
records = json.loads(contract.read_text())[key]
for relative, expected in records.items():
    path = root / relative
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise SystemExit(1)
PY
}

audio_r1_require_revisions() {
    local hi fmq
    hi=$(git -C "${audio_r1_aosp}/hardware/interfaces" rev-parse HEAD)
    fmq=$(git -C "${audio_r1_aosp}/system/libfmq" rev-parse HEAD)
    test "${hi}" = b553275c84253b074a8532a6ff0f4406c43e606e
    test "${fmq}" = 674a2103f2bd9bd5505c58e83af3042be2a24adf
}

audio_r1_project_retained() {
    git -C "${audio_r1_aosp}/hardware/interfaces" restore \
        --source=4a8246e3757732cb787327c3f8ad5cbacf910d1e -- \
        audio/core/all-versions/default/Device.cpp \
        audio/core/all-versions/default/DevicesFactory.cpp \
        audio/core/all-versions/default/ParametersUtil.cpp \
        audio/core/all-versions/default/PrimaryDevice.cpp \
        audio/core/all-versions/default/Stream.cpp \
        audio/core/all-versions/default/StreamIn.cpp \
        audio/core/all-versions/default/StreamOut.cpp \
        audio/core/all-versions/default/include/core/default/Device.h \
        audio/core/all-versions/default/include/core/default/DevicesFactory.h \
        audio/core/all-versions/default/include/core/default/ParametersUtil.h \
        audio/core/all-versions/default/include/core/default/PrimaryDevice.h \
        audio/core/all-versions/default/include/core/default/Stream.h \
        audio/core/all-versions/default/include/core/default/StreamIn.h \
        audio/core/all-versions/default/include/core/default/StreamOut.h \
        audio/core/all-versions/default/include/core/default/Util.h
    git -C "${audio_r1_aosp}/system/libfmq" restore \
        --source=8dd3bc99a159970f44298bb8e3d83366aac63273 -- base/fmq/MQDescriptorBase.h
    git -C "${audio_r1_aosp}/hardware/interfaces" apply --check "${audio_r1_patch}"
    git -C "${audio_r1_aosp}/hardware/interfaces" apply "${audio_r1_patch}"
}

audio_r1_restore_current() {
    git -C "${audio_r1_aosp}/hardware/interfaces" apply --check --reverse "${audio_r1_patch}"
    git -C "${audio_r1_aosp}/hardware/interfaces" apply --reverse "${audio_r1_patch}"
    git -C "${audio_r1_aosp}/hardware/interfaces" restore --source=b553275c84253b074a8532a6ff0f4406c43e606e -- \
        audio/core/all-versions/default/Device.cpp \
        audio/core/all-versions/default/DevicesFactory.cpp \
        audio/core/all-versions/default/ParametersUtil.cpp \
        audio/core/all-versions/default/PrimaryDevice.cpp \
        audio/core/all-versions/default/Stream.cpp \
        audio/core/all-versions/default/StreamIn.cpp \
        audio/core/all-versions/default/StreamOut.cpp \
        audio/core/all-versions/default/include/core/default/Device.h \
        audio/core/all-versions/default/include/core/default/DevicesFactory.h \
        audio/core/all-versions/default/include/core/default/ParametersUtil.h \
        audio/core/all-versions/default/include/core/default/PrimaryDevice.h \
        audio/core/all-versions/default/include/core/default/Stream.h \
        audio/core/all-versions/default/include/core/default/StreamIn.h \
        audio/core/all-versions/default/include/core/default/StreamOut.h \
        audio/core/all-versions/default/include/core/default/Util.h
    git -C "${audio_r1_aosp}/system/libfmq" restore \
        --source=674a2103f2bd9bd5505c58e83af3042be2a24adf -- base/fmq/MQDescriptorBase.h
}

audio_r1_require_revisions
case ${audio_r1_action} in
    check)
        if audio_r1_state patched_sha256; then
            echo "UBOX_A16_DEV_AUDIO_R1 source state: PATCHED"
        elif audio_r1_state clean_sha256; then
            echo "UBOX_A16_DEV_AUDIO_R1 source state: CLEAN_BASE"
        else
            echo "UBOX_A16_DEV_AUDIO_R1 source state: UNEXPECTED" >&2; exit 4
        fi ;;
    apply)
        audio_r1_state clean_sha256
        audio_r1_project_retained
        audio_r1_state patched_sha256 ;;
    revert)
        audio_r1_state patched_sha256
        audio_r1_restore_current
        audio_r1_state clean_sha256 ;;
esac
