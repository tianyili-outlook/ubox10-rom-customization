"""Locks the evidence-backed Gate 3 governance closure and its sole waiver."""
from pathlib import Path
import hashlib
import json

import pytest


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "docs/m8/candidates/a16-prototype-b-r7-gate3-physical-result.json"
EVIDENCE = Path("/work/evidence/ubox10/r7-gate3-20260901/unpacked")
ARCHIVE = Path("/work/evidence/ubox10/r7-gate3-20260901/UBOX10-GATE3-PHYSICAL-20260901.zip")


def _digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest().upper()


def test_gate3_verdict_preserves_contract_and_exact_waiver() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    assert result["verdict"] == "PASS_WITH_EXPLICIT_USER_WAIVER"
    assert result["unqualified_pass"] is False
    assert result["remaining_gate3_blockers"] == []
    assert result["results"]["3A_architecture_regression"]["status"] == "PASS"
    assert result["results"]["3B_media"]["status"] == "PASS"
    assert result["results"]["3C_remote"]["status"] == "PASS_WITH_EXPLICIT_USER_WAIVER"
    assert result["results"]["3D_wifi_lifecycle"]["status"] == "PASS"
    assert result["results"]["3E_platform_sanity"]["status"] == "PASS"
    assert [item["item"] for item in result["waivers"]] == [
        "REMOTE_POWER_CURRENT_SESSION_REVALIDATION"
    ]
    power = result["results"]["3C_remote"]["keys"]["POWER"]
    assert power["scan"] is None
    assert power["current_session"] == "NOT_REVALIDATED"
    assert power["waiver"] == "EXPLICITLY_WAIVED_BY_USER"
    menu = result["results"]["3C_remote"]["keys"]["MENU"]
    assert menu["visible_behavior"] == "NONE"
    assert menu["input_failure"] is False
    assert result["optional_not_tested"] == ["USB_USER_DEFERRED", "ETHERNET_USER_DEFERRED"]


def test_gate3_scope_and_governance_do_not_expand() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    assert result["not_proven_by_gate3"] == [
        "Main10", "HDR", "AFBC", "protected content", "4K"
    ]
    assert result["known_separate_debt"]["audio_startup_crash"] == \
        "KNOWN_UNFIXED_POST_ARCHITECTURE_P1"
    assert result["known_separate_debt"]["full_vintf"] == \
        "EXIT_65_INHERITED_CONFIG_NFS_FS_MISMATCH_NOT_PASS"
    governance = result["governance"]
    assert governance["canonical_r7"] == "PASS_FROZEN_UNCHANGED"
    assert governance["compat1a"] == "EXPERIMENTAL_REPAIR_NOT_R8_NOT_RELEASE"
    assert governance["r8"] == "NOT_AUTHORIZED_NOT_BUILT"
    assert governance["development_branch_created"] is False
    assert governance["runtime_or_image_changed_by_closure"] is False


def test_gate3_authoritative_docs_keep_truthful_verdict_and_original_rule() -> None:
    device = (ROOT / "docs/DEVICE_TEST.md").read_text(encoding="utf-8")
    status = (ROOT / "docs/m8/STATUS.md").read_text(encoding="utf-8")
    todo = (ROOT / "docs/m8/TODO.md").read_text(encoding="utf-8")
    for text in (device, status, todo):
        assert "PASS_WITH_EXPLICIT_USER_WAIVER" in text
        assert "POWER" in text
        assert "NOT AUTHORIZED" in text or "未授权" in text
    assert "Gate 3 只有在 3A 全部保持、三类 required media playback、intended remote matrix" in device
    assert "USB host/storage\n和 Ethernet 仅在 fixture 可用时测试" in device
    assert "[x] **33 — Gate 3" in todo


def test_gate3_external_evidence_integrity_and_decisive_records_when_available() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    if not EVIDENCE.is_dir() or not ARCHIVE.is_file():
        pytest.skip("external Gate 3 physical evidence is unavailable")

    provenance = result["evidence_provenance"]
    assert _digest(ARCHIVE) == provenance["archive_sha256_actual"]
    assert provenance["user_reported_archive_sha256"] is None
    assert provenance["archive_sha256_external_comparison"].startswith("NOT_PERFORMABLE")
    manifest = EVIDENCE / "SHA256SUMS.txt"
    lines = [line for line in manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 37
    assert _digest(manifest) == provenance["manifest_sha256"]
    for line in lines:
        expected, relative = line.split(maxsplit=1)
        item = EVIDENCE / relative.lstrip("* ")
        assert item.is_file(), relative
        assert _digest(item) == expected.upper(), relative

    architecture = (EVIDENCE / "ARCH3A/architecture-final.txt").read_text(errors="replace")
    for token in ("SDK=36", "ANDROID=16", "ZYGOTE_CONFIG=zygote64_32",
                  "ABILIST64=arm64-v8a", "ABILIST32=armeabi-v7a,armeabi",
                  "EGL=mali", "PLATFORM=apollo", "Mali-G31"):
        assert token in architecture

    vp9 = (EVIDENCE / "VP9/VP9Post/vp9-key-lines.txt").read_text(errors="replace")
    for token in ("CodecId=A_VORBIS", "CodecId=V_VP9",
                  "using OMX.allwinner.video.decoder.vp9",
                  "makeComponentInstance(OMX.allwinner.video.decoder.vp9)",
                  "bIsSoftDecoder is:0", "width=640, height=480"):
        assert token in vp9
    assert (EVIDENCE / "VP9/VP9Post/crash-buffer.txt").stat().st_size == 0
    assert (EVIDENCE / "VP9/VP9Pre/tombstones.txt").read_bytes() == \
        (EVIDENCE / "VP9/VP9Post/tombstones.txt").read_bytes()

    remote = (EVIDENCE / "REMOTE/remote-matrix-getevent.txt").read_text(errors="replace")
    for scan, key in (("00ff400b", "KEY_UP"), ("00ff400e", "KEY_DOWN"),
                      ("00ff4010", "KEY_LEFT"), ("00ff4011", "KEY_RIGHT"),
                      ("00ff400d", "KEY_OK"), ("00ff4042", "KEY_BACK"),
                      ("00ff401a", "KEY_HOMEPAGE"), ("00ff4045", "KEY_MENU"),
                      ("00ff4015", "KEY_VOLUMEUP"), ("00ff401c", "KEY_VOLUMEDOWN")):
        assert scan in remote
        assert key in remote
    assert "KEY_POWER" not in remote

    wifi = (EVIDENCE / "WIFI/Post/logcat-all.txt").read_text(errors="replace")
    network = (EVIDENCE / "WIFI/Post/network.txt").read_text(errors="replace")
    for token in ("setWifiEnabled package=com.android.tv.settings uid=1000 enable=false",
                  "setWifiEnabled package=com.android.tv.settings uid=1000 enable=true",
                  "CTRL-EVENT-CONNECTED - Connection to f4:ca:e7:70:66:f0 completed"):
        assert token in wifi
    for token in ('SSID: "SINGTEL-UKC7"', "Supplicant state: COMPLETED", "192.168.1.3"):
        assert token in network
    assert (EVIDENCE / "WIFI/Post/crash-buffer.txt").stat().st_size == 0
    assert (EVIDENCE / "WIFI/Pre/tombstones.txt").read_bytes() == \
        (EVIDENCE / "WIFI/Post/tombstones.txt").read_bytes()

    assert "DATA_WRITE_DELETE_PASS" in \
        (EVIDENCE / "SANITY/data-sanity-retest.txt").read_text(errors="replace")
    assert (EVIDENCE / "SANITY/crash-buffer.txt").stat().st_size == 0
