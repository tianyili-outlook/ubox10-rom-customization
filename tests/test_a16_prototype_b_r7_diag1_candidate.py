"""Fail-closed metadata, isolation, marker, and capture-helper locks for r7-diag1."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/candidates/a16-prototype-b-r7-diag1.json"
R7_CONFIG = ROOT / "configs/candidates/a16-prototype-b-r7.json"
OVERLAY = ROOT / "configs/aosp/architecture-ceiling-a16/diagnostics/r7-hevc-diag1"
CANDIDATE = ROOT / "out/candidates/a16-prototype-b-r7-diag1"
HELPER = ROOT / "scripts/capture-a16-prototype-b-r7-diag1-media-paired.ps1"
DOC = ROOT / "docs/m8/candidates/a16-prototype-b-r7-diag1.md"
RECORD = ROOT / "docs/m8/candidates/a16-prototype-b-r7-diag1.json"
PREFIX = "UBOX_R7_DIAG1"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest().upper()


def test_identity_and_governance_are_not_r8() -> None:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert cfg["id"] == "a16-prototype-b-r7-diag1"
    assert cfg["base_candidate"] == {
        "id": "a16-prototype-b-r7",
        "path": "out/candidates/a16-prototype-b-r7/x12-a16-prototype-b-r7.img",
        "size": 1_641_773_056,
        "sha256": "A1F58668AEFFC9DC83CFFD8A49A309839332B6616C02153DCC00A71136A7AA27",
    }
    assert cfg["label"] == "INSTRUMENTATION ONLY / NOT A REPAIR / NOT r8 / NOT A RELEASE"
    assert cfg["governance"]["architecture_ceiling"] == "PASS_FROZEN"
    assert cfg["governance"]["gate3"] == "HOLD"
    assert cfg["governance"]["hevc"] == "FAIL_BLOCKER"
    assert cfg["governance"]["r8_authorized"] is False
    assert cfg["governance"]["development_branch_authorized"] is False


def test_canonical_r7_patch_path_is_isolated() -> None:
    canonical = ROOT / "configs/aosp/architecture-ceiling-a16/patches"
    for path in canonical.rglob("*"):
        if path.is_file():
            assert PREFIX not in path.read_text(encoding="utf-8", errors="replace")
    r7_builder = (ROOT / "scripts/build-a16-prototype-b-r7-candidate.py").read_text()
    r7_config = R7_CONFIG.read_text(encoding="utf-8")
    assert PREFIX not in r7_builder
    assert PREFIX not in r7_config
    assert "diagnostics/r7-hevc-diag1" not in r7_builder


def test_overlay_is_exact_four_patch_diagnostic_series() -> None:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    patches = sorted((OVERLAY / "patches").glob("*.patch"))
    assert len(patches) == 4
    text = "\n".join(path.read_text(encoding="utf-8") for path in patches)
    assert text.count("DIAGNOSTIC ONLY") >= 4
    assert text.count("NO FUNCTIONAL REPAIR") >= 4
    for stage in cfg["diagnostic"]["stages"]:
        assert f"stage={stage}" in text
    assert 'LOG_ALWAYS_FATAL("Failed to create a valid texture.' in text
    assert "not_queried_preserve_state" in text


def test_static_checker_proves_no_repair_and_markers() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check-a16-prototype-b-r7-diag1.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS_DIAGNOSTIC_ONLY_STATIC_ISOLATION" in completed.stdout


def test_source_contract_and_mechanical_overlay() -> None:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert cfg["source_contract"]["tag"] == "android-security-16.0.0_r7"
    assert cfg["source_contract"]["build_id"] == "BP2A.250805.034"
    assert cfg["source_contract"]["api"] == 36
    prepare = (OVERLAY / "prepare.sh").read_text(encoding="utf-8")
    for action in ("apply)", "revert)", "check)"):
        assert action in prepare
    assert "source state: PATCHED" in prepare
    assert "configs/aosp/architecture-ceiling-a16/patches" not in prepare


def test_exact_runtime_delta_contract() -> None:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert set(cfg["runtime_files"]) == {
        "surfaceflinger", "libstagefright64", "gralloc32", "gralloc64"
    }
    assert {
        item["partition_path"] for item in cfg["runtime_files"].values()
    } == {
        "/system/bin/surfaceflinger",
        "/system/lib64/libstagefright.so",
        "/vendor/lib/hw/gralloc.apollo.so",
        "/vendor/lib64/hw/gralloc.apollo.so",
    }
    assert cfg["runtime_files"]["gralloc32"]["elf_class"] == "ELF32"
    assert cfg["runtime_files"]["gralloc64"]["elf_class"] == "ELF64"
    assert cfg["outer_delta"]["changed_payloads_from_base"] == [
        "super.fex", "Vsuper.fex", "vbmeta_system.fex", "Vvbmeta_system.fex",
        "vbmeta_vendor.fex", "Vvbmeta_vendor.fex",
    ]


def test_builder_writes_frozen_extents_and_never_lpadd_replaces() -> None:
    builder = (ROOT / "scripts/build-a16-prototype-b-r7-diag1-candidate.py").read_text()
    assert "lpdump_linear_extents" in builder
    assert "bytes_outside_system_and_vendor_extents_inherited_exact_r7" in builder
    assert '"lpadd"' not in builder
    assert "diag1 changed exact r7 LP metadata or extents" in builder
    assert "refusing to overwrite existing candidate" in builder


def test_candidate_artifact_and_offline_result_if_present() -> None:
    image = CANDIDATE / "x12-a16-prototype-b-r7-diag1.img"
    if not image.is_file():
        import pytest
        pytest.skip("ignored local candidate artifact unavailable")
    assert image.stat().st_size == 1_641_781_248
    assert digest(image) == "A68E7BD75D9819794BE22E9E05BE76969B2883DF8965DC277482E8C99231C6A4"
    result = json.loads((CANDIDATE / "build-result.json").read_text(encoding="utf-8"))
    assert result["outer"]["changed_payloads"] == sorted(
        json.loads(CONFIG.read_text())["outer_delta"]["changed_payloads_from_base"]
    )
    if result["status"] == "OFFLINE_CHECKED":
        audit = json.loads((CANDIDATE / "offline-audit/offline-audit.json").read_text())
        assert audit["decision"] == (
            "OFFLINE CHECKED / READY FOR PAIRED PHYSICAL DIAGNOSTIC VALIDATION"
        )
        assert audit["compatibility"]["system_vintf_exit"] == 0
        assert audit["compatibility"]["full_vintf_exit"] == 65
        assert "NOT PASS" in " ".join(audit["limitations"])


def test_powershell_helper_has_manual_safe_phase_contract() -> None:
    script = HELPER.read_text(encoding="utf-8")
    for phase in ("Baseline", "AVCPre", "AVCPost", "HEVCPre", "HEVCPostRestart", "Final"):
        assert f"'{phase}'" in script
    assert "[int]$Port = 7896" in script
    assert "GetFolderPath('UserProfile')" in script
    assert "Downloads" in script
    assert "Wait-ForAdbReturn" in script
    assert "Start-Sleep -Seconds 2" in script
    assert "Do not reboot" in script
    assert "exactly once" in script
    assert "-ClearLogcat is permitted only in AVCPre or HEVCPre" in script
    assert "pstore_cleared=false" in script
    assert "tombstones_cleared=false" in script
    assert "wm size" not in "\n".join(
        match.group(1)
        for match in re.finditer(r"=\s*'([^']*)'\s*$", script, re.MULTILINE)
    )
    assert "192.168." not in script
    assert script.count("{") == script.count("}")
    assert script.count('@"') == script.count('"@')


def test_candidate_docs_when_present_keep_gate3_hold() -> None:
    if not DOC.is_file() or not RECORD.is_file():
        import pytest
        pytest.skip("candidate documentation not generated yet")
    doc = DOC.read_text(encoding="utf-8")
    record = json.loads(RECORD.read_text(encoding="utf-8"))
    assert "OFFLINE PASS / PHYSICAL BOOT FAIL / CLOSED DIAGNOSTIC CANDIDATE" in doc
    assert "__libcpp_verbose_abort" in doc
    assert "failed to create composer client" in doc
    assert "HEVC is not fixed" in doc
    assert record["physical_status"] == "PHYSICAL_BOOT_FAIL_CLOSED_DIAGNOSTIC_CANDIDATE"
    assert record["physical_result"]["root_cause"] == (
        "PROVEN_ARM32_GRALLOC_UNMATCHED_VNDK31_LIBCPP_STRONG_IMPORT"
    )
    assert record["governance"]["gate3"] == "HOLD"
    assert record["governance"]["r8_authorized"] is False


def test_status_and_todo_keep_architecture_pass_and_gate3_hold() -> None:
    status = (ROOT / "docs/m8/STATUS.md").read_text(encoding="utf-8")
    todo = (ROOT / "docs/m8/TODO.md").read_text(encoding="utf-8")
    assert "PHYSICAL ARCHITECTURE PASS / FROZEN / GATE 3 HOLD" in status
    assert "PHYSICAL BOOT FAIL / ROOT CAUSE PROVEN / CLOSED" in status
    assert "OFFLINE CHECKED / READY FOR PHYSICAL BOOT GATE" in status
    assert "[ ] **33 — Gate 3" in todo
    assert "READY FOR PHYSICAL BOOT GATE" in todo
    assert "R8_AUDIT_DECISION = HOLD_FOR_MORE_EVIDENCE" in todo
    assert "Gate 3 PASS 前不创建" in todo
