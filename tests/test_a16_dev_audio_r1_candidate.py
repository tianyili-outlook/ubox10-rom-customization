"""Governance and focused behavior locks for a16-dev-audio-r1."""
from pathlib import Path
import json
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "out/candidates/a16-dev-audio-r1"


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
    assert record["physical_status"] == "NOT_YET_VALIDATED"
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
        "OFFLINE_RECONSTRUCTION_ABI_PASS_READY_FOR_PHYSICAL_VALIDATION"
    assert config["reconstruction_abi_review"]["control_to_guarded"] == {
        "strong_import_sets_identical": True,
        "dynamic_export_sets_identical": True,
        "only_material_executable_function_delta": "Device::getAudioPort",
    }
    assert "OFFLINE_RECONSTRUCTION_ABI_PASS / READY_FOR_PHYSICAL_VALIDATION / " \
        "DEVELOPMENT AUDIO COMPATIBILITY CANDIDATE / NOT r8 / NOT RELEASE" in status
