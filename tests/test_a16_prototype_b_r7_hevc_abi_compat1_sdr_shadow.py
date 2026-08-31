"""Locks for the first SDR YV12 Mali metadata ABI repair experiment."""
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_compat1_fail_closed_checker() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check-a16-prototype-b-r7-hevc-abi-compat1-sdr-shadow.py")],
        cwd=ROOT, text=True, capture_output=True, check=True,
    )
    assert "PASS_COMPAT1_EXACT_ONE_RUNTIME_FILE_SDR_SHADOW_DELTA" in completed.stdout


def test_compat1_exact_attr_translation_under_sanitizers() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check-a16-prototype-b-r7-compat1-metadata.py")],
        cwd=ROOT, text=True, capture_output=True, check=True,
    )
    assert "active_attr=23544 legacy_attr=128 bytes=56 original_unchanged=PASS" in completed.stdout


def test_compat1_evidence_is_external() -> None:
    evidence = Path("/work/evidence/ubox10/r7-diag3a-avc-hevc/unpacked")
    assert evidence.is_dir()
    assert not evidence.resolve().is_relative_to(ROOT.resolve())


def test_compat1_capture_contract_is_manual_and_bounded() -> None:
    helper = ROOT / "scripts/capture-a16-prototype-b-r7-hevc-abi-compat1-sdr-shadow.ps1"
    text = helper.read_text(encoding="utf-8")
    for phase in (
        "BootGate", "AVCPre", "AVCLive", "AVCPost", "HEVCPre", "HEVCLive", "HEVCPost",
        "InteractionPost", "AVCRegressionPre", "AVCRegressionLive", "AVCRegressionPost", "Final",
    ):
        assert phase in text
    assert "C:\\platform-tools\\adb.exe" in text
    assert "192.168.1.9:7896" in text
    assert "automatic_reboot=false" in text
    assert "automatic_player_control=false" in text
    assert "unsupported_tests=Main10,HDR,AFBC,protected,4K" in text
    assert " shell reboot" not in text.lower()


def test_compat1_powershell_capture_safety_when_available() -> None:
    pwsh = shutil.which("pwsh")
    if pwsh is None:
        pytest.skip("PowerShell 7 unavailable on this Linux build host")
    helper = ROOT / "scripts/capture-a16-prototype-b-r7-hevc-abi-compat1-sdr-shadow.ps1"
    completed = subprocess.run(
        [pwsh, "-NoProfile", "-File", str(helper), "-SelfTest"],
        cwd=ROOT, text=True, capture_output=True, check=True,
    )
    assert "safety self-test: PASS" in completed.stdout
