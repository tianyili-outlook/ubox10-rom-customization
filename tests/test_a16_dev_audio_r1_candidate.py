"""Governance and focused behavior locks for a16-dev-audio-r1."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "out/candidates/a16-dev-audio-r1"
EVIDENCE_ARCHIVE = Path(
    "/work/physical-evidence/ubox10/a16-dev-audio-r1/20260902-214327/"
    "UBOX10-A16-DEV-AUDIO-R1-20260902-214327.zip"
)
EVIDENCE_ROOT = "UBOX10-A16-DEV-AUDIO-R1-20260902-214327/"


def test_audio_r1_checker() -> None:
    done = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check-a16-dev-audio-r1.py")],
        cwd=ROOT, text=True, capture_output=True, check=True,
    )
    assert "PASS_A16_DEV_AUDIO_R1_EXACT_ONE_RUNTIME_FILE_NULL_V7_GUARD" in done.stdout


def test_guard_model_under_host_sanitizers(tmp_path: Path) -> None:
    compiler = shutil.which("clang++") or shutil.which("g++")
    assert compiler is not None
    source = ROOT / "tests/fixtures/a16_dev_audio_r1_guard_model.cpp"
    binary = tmp_path / "guard-model"
    subprocess.run(
        [compiler, "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror",
         "-fsanitize=address,undefined", "-fno-omit-frame-pointer", str(source), "-o", str(binary)],
        check=True,
    )
    subprocess.run([str(binary)], check=True)


def test_source_scope_and_no_malformed_v7_fallback() -> None:
    patch = (ROOT / "configs/aosp/architecture-ceiling-a16/development/audio-r1/patches/0001-audio-hidl-guard-null-get-audio-port-v7.patch").read_text()
    assert "if (mDevice->get_audio_port_v7 == nullptr)" in patch
    assert "_hidl_cb(Result::NOT_SUPPORTED, port);" in patch
    guard = patch[patch.index("if (mDevice->get_audio_port_v7 == nullptr)"):
                  patch.index("return getAudioPortImpl(port, _hidl_cb, mDevice->get_audio_port_v7")]
    assert "get_audio_port," not in guard
    forbidden = ("audio.primary.apollo.so", "AudioPolicyManager", "SurfaceFlinger.cpp",
                 "external/skia", "kernel/", "sleep(", "retry")
    for marker in forbidden:
        assert marker not in patch


def test_candidate_and_governance_contract() -> None:
    record = json.loads((ROOT / "docs/m8/candidates/a16-dev-audio-r1.json").read_text())
    config = json.loads((ROOT / "configs/candidates/a16-dev-audio-r1.json").read_text())
    status = (ROOT / "docs/m8/STATUS.md").read_text()
    audit = json.loads((CANDIDATE / "offline-audit/offline-audit.json").read_text())
    assert record["candidate"]["size"] == 1641830400
    assert record["candidate"]["sha256"] == \
        "270B5D822AB3BB13D8EDCD9BE374DA1D6ED512D6D60063E123046C23B8AF9D62"
    assert audit["filesystem"]["semantic_runtime_delta_count"] == 1
    assert audit["filesystem"]["vendor_tree_delta"]["changed"] == [
        "lib/hw/android.hardware.audio@7.0-impl.so"
    ]
    assert audit["filesystem"]["system_byte_identical_to_compat1a"] is True
    assert audit["preserved_runtime"]["surfaceflinger"]["sha256"] == \
        "06C960E672863AD557AF921565621997CB9B113BA2290049AF91028A405CD0A5"
    assert record["governance"]["canonical_r7"] == "PASS_FROZEN_UNCHANGED"
    assert record["governance"]["gate3"] == "PASS_WITH_EXPLICIT_USER_WAIVER_CLOSED"
    assert record["governance"]["r8"] == "NOT_AUTHORIZED_NOT_BUILT"
    assert record["governance"]["main10_hdr_afbc_protected_4k"] == "NOT_PROVEN"
    assert record["offline"]["full_vintf_exit"] == 65
    assert record["physical_status"] == "PASS"
    physical = record["physical_validation"]
    assert physical["p1_arm32_audio_startup_crash"] == "CLOSED"
    assert physical["evidence_archive_sha256"] == \
        "BDB3D13ECF54DF3CD1C7B3F6DC5D160DDF9D43CD51E6F1D66B8DC28910F09064"
    assert physical["internal_manifest"] == "PASS_48_OF_48"
    assert physical["boot_id"] == "90882ee3-4884-445c-ae9c-cada3a1a6449"
    assert physical["continuous_pids"] == {
        "audioserver": 534, "audio_hidl": 504, "surfaceflinger": 547,
        "system_server": 787, "zygote64": 492, "zygote32": 493,
    }
    assert physical["historical_pc_zero_signature"] == "ABSENT"
    assert physical["new_crash_or_tombstone"] is False
    assert record["offline"]["status"] == \
        "OFFLINE_RECONSTRUCTION_ABI_PASS_READY_FOR_PHYSICAL_VALIDATION"
    review = record["reconstruction_abi_review"]
    assert review["verdict"] == "OFFLINE_RECONSTRUCTION_ABI_PASS"
    assert review["readiness"] == "READY_FOR_PHYSICAL_VALIDATION"
    assert review["control_guard_dynamic_abi_sets_identical"] is True
    assert review["only_material_executable_function_delta"] == "Device::getAudioPort"
    assert review["reverse_consumer_elfs_scanned"] == 2474
    assert review["removed_exports_required_by_vendor_consumers"] == 0
    assert review["temporary_control_committed_or_packaged"] is False
    assert config["status"] == \
        "PHYSICAL_VALIDATION_PASS_P1_ARM32_AUDIO_STARTUP_CRASH_CLOSED"
    assert config["physical_validation"]["gates"] == {
        "boot_gate": "PASS", "hdmi_disconnect_connect": "PASS",
        "avc_aac_hdmi": "PASS", "hevc_aac_hdmi": "PASS",
        "vp9_vorbis_hdmi": "PASS", "final_census": "PASS",
    }
    assert config["governance"]["physical_validation_required"] is False
    assert config["reconstruction_abi_review"]["control_to_guarded"] == {
        "strong_import_sets_identical": True,
        "dynamic_export_sets_identical": True,
        "only_material_executable_function_delta": "Device::getAudioPort",
    }
    assert "PHYSICAL VALIDATION PASS / P1 ARM32 AUDIO STARTUP CRASH CLOSED / " \
        "DEVELOPMENT AUDIO COMPATIBILITY CANDIDATE / NOT r8 / NOT RELEASE" in status


def test_external_physical_evidence_when_available() -> None:
    if not EVIDENCE_ARCHIVE.is_file():
        pytest.skip("external audio-r1 physical evidence is unavailable")

    digest = hashlib.sha256(EVIDENCE_ARCHIVE.read_bytes()).hexdigest().upper()
    assert digest == "BDB3D13ECF54DF3CD1C7B3F6DC5D160DDF9D43CD51E6F1D66B8DC28910F09064"
    with zipfile.ZipFile(EVIDENCE_ARCHIVE) as archive:
        manifest = archive.read(EVIDENCE_ROOT + "SHA256SUMS.txt").decode()
        entries = [line for line in manifest.splitlines() if line.strip()]
        assert len(entries) == 48
        for line in entries:
            expected, relative = line.split(maxsplit=1)
            payload = archive.read(EVIDENCE_ROOT + relative.lstrip("* "))
            assert hashlib.sha256(payload).hexdigest() == expected

        boot = archive.read(EVIDENCE_ROOT + "BootGate/identity.txt").decode()
        final = archive.read(EVIDENCE_ROOT + "Final-Census/identity-pids.txt").decode()
        for marker in ("BOOT_ID=90882ee3-4884-445c-ae9c-cada3a1a6449",
                       "SDK=36", "ANDROID=16", "ZYGOTE=zygote64_32"):
            assert marker in boot
            assert marker in final
        for marker in ("AUDIOSERVER=534", "AUDIO_HIDL=504", "SF=547",
                       "SYSTEM_SERVER=787", "ZYGOTE64=492", "ZYGOTE32=493"):
            assert marker in final

        transition = archive.read(
            EVIDENCE_ROOT + "HDMI-Transition/Post/transition-search.txt").decode()
        for marker in ("disconnect=1024", "connect=1024", "AUDIO_DEVICE_OUT_HDMI"):
            assert marker in transition
        final_audio = archive.read(EVIDENCE_ROOT + "Final-Census/audio-flinger.txt").decode()
        assert "Hardware status: 0" in final_audio
        assert "Output devices: 0x400 (AUDIO_DEVICE_OUT_HDMI)" in final_audio

        for relative in ("BootGate/crash-buffer.txt", "HDMI-Transition/Post/crash.txt",
                         "Media-Smoke/AVC/Post/crash.txt", "Media-Smoke/HEVC/Post/crash.txt",
                         "Media-Smoke/VP9/Post/crash.txt", "Final-Census/crash.txt"):
            assert archive.read(EVIDENCE_ROOT + relative) == b""
        boot_tombstones = archive.read(EVIDENCE_ROOT + "BootGate/tombstones.txt")
        assert archive.read(EVIDENCE_ROOT + "Final-Census/tombstones.txt") == boot_tombstones

        all_logs = b"".join(
            archive.read(name) for name in archive.namelist()
            if name.endswith(".txt") and not name.endswith("PHYSICAL-RESULTS.txt")
        ).decode(errors="replace")
        for forbidden in ("getAudioPortImpl", "Fatal signal", "SEGV_MAPERR", "pc 00000000"):
            assert forbidden not in all_logs
