"""Locks for compat1a's single-variable sized-shadow-fd correction."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = Path("/work/evidence/ubox10/r7-compat1a-physical-pass/unpacked")


def _digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest().upper()


def test_compat1a_fail_closed_candidate_checker() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check-a16-prototype-b-r7-hevc-abi-compat1a-sdr-shadow-fd.py")],
        cwd=ROOT, text=True, capture_output=True, check=True,
    )
    assert "PASS_COMPAT1A_EXACT_SIZED_SHADOW_FD_ONE_RUNTIME_FILE_DELTA" in result.stdout


def test_compat1a_json_and_gate_status() -> None:
    record = json.loads((ROOT / "docs/m8/candidates/a16-prototype-b-r7-hevc-abi-compat1a-sdr-shadow-fd.json").read_text())
    config = json.loads((ROOT / "configs/candidates/a16-prototype-b-r7-hevc-abi-compat1a-sdr-shadow-fd.json").read_text())
    assert record["offline"]["status"] == "OFFLINE_CHECKED_READY_FOR_PHYSICAL_BOOT_GATE"
    assert record["offline"]["full_vintf_exit"] == 65
    assert record["physical"]["status"] == "PHYSICAL_PASS_AUTHORIZED_SDR_1080P_YV12_ONLY"
    assert record["physical"]["supplemental_avc"].startswith("SUPPLEMENTAL_UNPLANNED")
    assert record["governance"]["gate3"] == "PASS_WITH_EXPLICIT_USER_WAIVER"
    assert record["governance"]["gate3_result"].endswith("r7-gate3-physical-result.json")
    assert config["governance"]["record_scope"] == "BUILD_INPUT_BEFORE_COMPAT1A_PHYSICAL_VALIDATION"
    assert config["governance"]["physical_status"] == "NOT_YET_VALIDATED_AT_BUILD_TIME"
    assert config["governance"]["current_physical_status"] == \
        "PHYSICAL_PASS_AUTHORIZED_SDR_1080P_YV12_ONLY"
    assert config["subsequent_physical_result"]["runtime_image_rebuilt"] is False
    assert config["governance"]["gate3"] == "HOLD_AT_BUILD_TIME"
    assert config["governance"]["current_gate3_status"] == \
        "PASS_WITH_EXPLICIT_USER_WAIVER"
    assert config["subsequent_gate3_result"]["runtime_image_rebuilt"] is False


def test_compat1a_physical_result_record_and_raw_evidence_when_available() -> None:
    result = json.loads((ROOT / "docs/m8/candidates/a16-prototype-b-r7-hevc-abi-compat1a-sdr-shadow-fd-physical-result.json").read_text())
    assert result["candidate_identity"]["sha256"] == \
        "9E9592BF420F40A386BC347B027A85B2F9ED0A44DDB132BDBAB9882905F75722"
    assert result["physical_status"] == "PHYSICAL_PASS_AUTHORIZED_SDR_1080P_YV12_ONLY"
    assert result["results"]["supplemental_avc_after_hevc"]["formal_avc_regression"] is False
    assert result["gate3"]["authorized_sdr_avc_hevc_media_subgate"] == "PASS"
    assert result["gate3"]["overall"] == "PASS_WITH_EXPLICIT_USER_WAIVER"
    assert result["gate3"]["waiver"] == "REMOTE_POWER_CURRENT_SESSION_REVALIDATION"
    assert result["gate3"]["remaining_blockers"] == []
    assert result["not_validated"] == ["Main10", "HDR", "AFBC", "protected content", "4K"]
    if not EVIDENCE.is_dir():
        pytest.skip("external compat1a physical evidence is unavailable")

    manifest = EVIDENCE / "SHA256SUMS"
    lines = [line for line in manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 107
    assert _digest(manifest) == "709B24563701266EE67B1D4A3AEC6577346BC7C46F48241E483DA425FA65A101"
    for line in lines:
        expected, relative = line.split(maxsplit=1)
        item = EVIDENCE / relative.lstrip("* ")
        assert item.is_file(), relative
        assert _digest(item) == expected.upper(), relative

    primary = (EVIDENCE / "20260831T152227Z-hevclive/hevc-live-logcat-all.txt").read_text(
        encoding="utf-8", errors="replace")
    interaction = (EVIDENCE / "20260831T153139Z-hevclive/hevc-live-logcat-all.txt").read_text(
        encoding="utf-8", errors="replace")
    required_hevc = (
        "eligible=1", "shadow_created=1", "fd_type=memfd_ftruncate_sealed",
        "translated=1", "src_offset=23544", "dst_offset=128", "bytes=56",
        "original_prot=read", "original_unchanged=1", "attr_copy=1",
        "view_created=1", "method=CLONE", "original_fd2_unchanged=1",
        "egl_import_result=1", "view=sdr_shadow", "client_buffer_null=0",
        "stage=EGL_CREATE_IMAGE", "stage=BACKEND_TEXTURE",
    )
    for text in (primary, interaction):
        for marker in required_hevc:
            assert text.count(marker) == 14, marker
        assert text.count("stage=EGL_CREATE_IMAGE") == text.count("result=1 image=")
        assert text.count("stage=BACKEND_TEXTURE") == text.count("valid=1 w=1920 h=1088")
        for forbidden in ("EGL_BAD_ALLOC", "egl_error=0x3003", "Failed to create a valid texture",
                          "Fatal signal 6", "SIGABRT"):
            assert forbidden not in text

    for relative in (
        "20260831T151835Z-avclive/avc-live-logcat-all.txt",
        "20260831T153751Z-avcregressionlive/avc-regression-live-logcat-all.txt",
    ):
        avc = (EVIDENCE / relative).read_text(encoding="utf-8", errors="replace")
        assert avc.count("eligible=0") == 9
        assert avc.count("reason=metadata_gate") == 9
        assert avc.count("view=original client_buffer_null=0") == 9
        assert avc.count("stage=EGL_CREATE_IMAGE") == 9
        assert avc.count("stage=BACKEND_TEXTURE") == 9
        assert "eligible=1" not in avc
        assert "EGL_BAD_ALLOC" not in avc

    identities = list(EVIDENCE.glob("*/identity-uptime-services.txt"))
    assert identities
    assert {item.read_text(encoding="utf-8").splitlines()[2] for item in identities} == {
        "3dd67a8e-fe9f-46f7-b35d-fb34bd264217"
    }
    for relative in (
        "20260831T151910Z-avcpost/crash-buffer.txt",
        "20260831T152310Z-hevcpost/crash-buffer.txt",
        "20260831T153234Z-interactionpost/crash-buffer.txt",
        "20260831T153828Z-avcregressionpost/crash-buffer.txt",
        "20260831T153840Z-final/crash-buffer.txt",
    ):
        assert (EVIDENCE / relative).stat().st_size == 0
    assert (EVIDENCE / "20260831T151359Z-bootgate/tombstones.txt").read_bytes() == \
        (EVIDENCE / "20260831T153840Z-final/tombstones.txt").read_bytes()
    supplemental = (EVIDENCE / "20260831T152957Z-supplemental-avc-after-hevc/README.txt").read_text()
    assert "classification=SUPPLEMENTAL_UNPLANNED_AVC_AFTER_HEVC" in supplemental
    assert "formal_avc_regression=false" in supplemental


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
    assert "Confirm-RemoteFileSize" in text
    assert "Write-Utf8NoBom (Join-Path $CaptureRoot $Name) $Text" in text
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
