"""Locks for compat1a's single-variable sized-shadow-fd correction."""
from pathlib import Path
import json
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_compat1a_fail_closed_candidate_checker() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check-a16-prototype-b-r7-hevc-abi-compat1a-sdr-shadow-fd.py")],
        cwd=ROOT, text=True, capture_output=True, check=True,
    )
    assert "PASS_COMPAT1A_EXACT_SIZED_SHADOW_FD_ONE_RUNTIME_FILE_DELTA" in result.stdout


def test_compat1a_json_and_gate_status() -> None:
    record = json.loads((ROOT / "docs/m8/candidates/a16-prototype-b-r7-hevc-abi-compat1a-sdr-shadow-fd.json").read_text())
    assert record["offline"]["status"] == "OFFLINE_CHECKED_READY_FOR_PHYSICAL_BOOT_GATE"
    assert record["offline"]["full_vintf_exit"] == 65
    assert record["governance"]["gate3"] == "HOLD"


def test_compat1a_helper_enforces_bootgate_media_avc_order() -> None:
    helper = ROOT / "scripts/capture-a16-prototype-b-r7-hevc-abi-compat1a-sdr-shadow-fd.ps1"
    text = helper.read_text(encoding="utf-8")
    assert "C:\\platform-tools\\adb.exe" in text
    assert "${DeviceIp}:7896" in text
    assert "-DeviceIp is required" in text
    assert "STATE-BOOTGATE-REVIEWED-PASS" in text
    assert "STATE-MEDIA-READY" in text
    assert "STATE-AVC-REVIEWED-PASS" in text
    assert "STATE-INTERACTION-POST-CAPTURED" in text
    assert "STATE-AVC-REGRESSION-POST-CAPTURED" in text
    assert text.index("'BootGate' {") < text.index("'PrepareMedia' {") < text.index("'AVCPre' {")
    assert "diag1a-avc-aac-1080p30.mp4" in text
    assert "diag1a-hevc-aac-1080p30.mp4" in text
    assert "org.videolan.vlc/.StartActivity" in text
    assert "transfer size mismatch" in text
    assert "automatic_reboot=false" in text
    assert "automatic_playback=false" in text
    assert " shell reboot" not in text.lower()


def test_compat1a_powershell_safety_when_available() -> None:
    pwsh = shutil.which("pwsh")
    if pwsh is None:
        pytest.skip("PowerShell 7 unavailable on this Linux build host")
    helper = ROOT / "scripts/capture-a16-prototype-b-r7-hevc-abi-compat1a-sdr-shadow-fd.ps1"
    result = subprocess.run([pwsh, "-NoProfile", "-File", str(helper), "-SelfTest"],
                            cwd=ROOT, text=True, capture_output=True, check=True)
    assert "BootGate-first capture safety self-test: PASS" in result.stdout
