"""Fail-closed metadata, VNDK closure, and single-runtime-delta locks for r7-diag1a."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/candidates/a16-prototype-b-r7-diag1a.json"
CANDIDATE = ROOT / "out/candidates/a16-prototype-b-r7-diag1a"
OVERLAY = ROOT / "configs/aosp/architecture-ceiling-a16/diagnostics/r7-hevc-diag1a"
VERBOSE_ABORT = "_ZNSt3__122__libcpp_verbose_abortEPKcz"


def test_identity_and_gate_policy() -> None:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert cfg["id"] == "a16-prototype-b-r7-diag1a"
    assert cfg["base_candidate"] == {
        "id": "a16-prototype-b-r7-diag1",
        "path": "out/candidates/a16-prototype-b-r7-diag1/x12-a16-prototype-b-r7-diag1.img",
        "size": 1_641_781_248,
        "sha256": "A68E7BD75D9819794BE22E9E05BE76969B2883DF8965DC277482E8C99231C6A4",
    }
    assert "BOOT-COMPATIBILITY CORRECTION" in cfg["label"]
    assert "NOT AN HEVC REPAIR" in cfg["label"]
    assert cfg["governance"]["architecture_ceiling"] == "PASS_FROZEN"
    assert cfg["governance"]["gate3"] == "HOLD"
    assert cfg["governance"]["hevc"] == "FAIL_BLOCKER"
    assert cfg["governance"]["r8_authorized"] is False
    assert cfg["governance"]["development_branch_authorized"] is False


def test_reuses_exact_r7_fatal_hook_without_touching_instrumentation() -> None:
    patches = sorted((OVERLAY / "patches").glob("*.patch"))
    assert [path.name for path in patches] == [
        "0001-gralloc-arm32-vndk31-libcpp-backdeploy.patch"
    ]
    patch = patches[0].read_text(encoding="utf-8")
    assert "LOCAL_CPPFLAGS_32 += -include $(LOCAL_PATH)/vndk31_libcpp_backdeploy.h" in patch
    assert "#define _LIBCPP_VERBOSE_ABORT(...) __builtin_abort()" in patch
    assert "defined(__arm__)" in patch
    assert "mali_gralloc_bufferallocation.cpp" not in patch
    assert "mali_gralloc_reference.cpp" not in patch
    assert "LOG_ALWAYS_FATAL(" not in patch


def test_generic_strong_import_closure_is_permanent_prepack_guard() -> None:
    checker = (ROOT / "scripts/check-a16-prototype-b-r7-graphics.py").read_text()
    builder = (ROOT / "scripts/build-a16-prototype-b-r7-diag1a-candidate.py").read_text()
    auditor = (ROOT / "scripts/audit-a16-prototype-b-r7-diag1a.py").read_text()
    assert 'choices=("arm32", "arm64")' in checker
    assert "undefined - provider_exports" in checker
    assert '"unmatched_strong_imports": unmatched' in checker
    assert "self.run_arm32_closure(failed, corrected)" in builder
    assert "PASS_EXACT_ARM32_MAPPER_GRALLOC_SPHAL_CLOSURE" in builder
    assert "arm32_graphics_sphal_closure" in auditor
    assert VERBOSE_ABORT in builder
    assert VERBOSE_ABORT in auditor


def test_diag1a_static_and_built_checker() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check-a16-prototype-b-r7-diag1a.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS_DIAG1A_BOOT_COMPATIBILITY_SINGLE_DELTA" in completed.stdout


def test_built_candidate_exact_closure_and_delta_if_present() -> None:
    if not CANDIDATE.is_dir():
        pytest.skip("ignored local diag1a candidate artifact unavailable")
    audit = json.loads(
        (CANDIDATE / "offline-audit/offline-audit.json").read_text(encoding="utf-8")
    )
    assert audit["decision"] == "OFFLINE CHECKED / READY FOR PHYSICAL BOOT GATE"
    assert audit["physical_status"] == "NOT_YET_VALIDATED"
    preservation = audit["preservation"]
    assert preservation["diag1_system_tree_delta"] == {
        "added": [], "removed": [], "changed": []
    }
    assert preservation["diag1_vendor_tree_delta"] == {
        "added": [], "removed": [], "changed": ["lib/hw/gralloc.apollo.so"]
    }
    before = preservation["arm32_graphics_sphal_closure"]["failed_diag1"]["gralloc"]
    after = preservation["arm32_graphics_sphal_closure"]["corrected_diag1a"]["gralloc"]
    assert before["unmatched_strong_imports"] == [VERBOSE_ABORT]
    assert after["unmatched_count"] == 0
    assert after["unmatched_strong_imports"] == []
    assert after["libcpp_verbose_abort_import"] is False
    assert audit["compatibility"]["system_vintf_exit"] == 0
    assert audit["compatibility"]["full_vintf_exit"] == 65
    assert "NOT PASS" in " ".join(audit["limitations"])


def test_diag1a_docs_when_present_keep_pending_physical_boot() -> None:
    doc = ROOT / "docs/m8/candidates/a16-prototype-b-r7-diag1a.md"
    record = ROOT / "docs/m8/candidates/a16-prototype-b-r7-diag1a.json"
    if not doc.is_file() or not record.is_file():
        pytest.skip("diag1a candidate documentation not generated yet")
    text = doc.read_text(encoding="utf-8")
    data = json.loads(record.read_text(encoding="utf-8"))
    assert "OFFLINE CHECKED / READY FOR PHYSICAL BOOT GATE" in text
    assert "HEVC is not fixed" in text
    assert data["physical_status"] == "OFFLINE_CHECKED_READY_FOR_PHYSICAL_BOOT_GATE"
    assert data["governance"]["gate3"] == "HOLD"
    assert data["governance"]["r8_authorized"] is False


def test_status_todo_and_device_test_gate_media_on_normal_boot() -> None:
    status = (ROOT / "docs/m8/STATUS.md").read_text(encoding="utf-8")
    todo = (ROOT / "docs/m8/TODO.md").read_text(encoding="utf-8")
    device = (ROOT / "docs/DEVICE_TEST.md").read_text(encoding="utf-8")
    assert "PHYSICAL BOOT FAIL / ROOT CAUSE PROVEN / CLOSED" in status
    assert "OFFLINE CHECKED / READY FOR PHYSICAL BOOT GATE" in status
    assert "READY FOR PHYSICAL BOOT GATE" in todo
    assert "boot PASS之后" in todo
    assert "PHYSICAL BOOT PASS / PAIRED EVIDENCE CAPTURED" in status
    assert "OFFLINE CHECKED / READY FOR PHYSICAL VALIDATION" in todo
    assert "COMPAT1 SDR YV12 MALI METADATA SHADOW READY FOR PHYSICAL BOOT GATE" in device
    assert "AVC通过后才执行" in device
    for text in (status, todo, device):
        assert "Gate 3" in text
        assert "r8" in text.lower()
