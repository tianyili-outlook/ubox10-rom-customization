"""Governance locks for the evidence-backed Android 16 P2 audit result."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "docs/m8/device-tests/20260903-a16-p2-boot-runtime-audit/README.md"


def _result() -> str:
    return RESULT.read_text(encoding="utf-8")


def test_result_identity_integrity_and_continuity_are_locked() -> None:
    text = _result()
    assert "c3aca6ace9e84477d2fa2c47a419bc19b6887a2b2dd9616e54ce2446e6389428" in text
    assert "105/105 OK, 0 failures" in text
    assert "09a7494f9f4f084e7e3121db847af3d1aed7e2e7815a1c3bc5accb06b9e49928" in text
    assert "commands_entered=false" in text
    assert "1f47a2b3-2618-44ec-866a-566c14ded851" in text
    for identity in (
        "`zygote64` 489/1", "`zygote` 490/1", "audio HIDL 501/1",
        "`audioserver` 527/1", "`surfaceflinger` 535/1", "`system_server` 778/489",
    ):
        assert identity in text


def test_issue_matrix_has_exact_schema_and_taxonomy() -> None:
    text = _result()
    expected_header = (
        "| ID | Subsystem | Classification | Signature / finding | Evidence file(s) | "
        "First timestamp | Last timestamp | Count/frequency | Boot-only vs persistent | "
        "PID/service | Known vs new | User-visible/functional impact | Likely layer/root cause | "
        "Confidence | Recommended priority | Recommended next action |"
    )
    assert expected_header in text
    allowed = (
        "P1 / BLOCKER", "P2 / ACTIVE DEBT", "P3 / NON-BLOCKING NOISE",
        "KNOWN INHERITED DEBT", "EXPECTED / BY DESIGN", "NEEDS MORE EVIDENCE",
    )
    rows = [line for line in text.splitlines() if line.startswith("| P2-")]
    assert len(rows) == 24
    for row in rows:
        assert sum(token in row for token in allowed) == 1, row
    assert "P1 / BLOCKER |" not in "\n".join(rows)


def test_verdict_preserves_audio_architecture_and_scope() -> None:
    text = _result()
    normalized = " ".join(text.split())
    assert "NO NEW P1 BLOCKER" in text
    assert "NO CRITICAL RESTART" in text
    assert "NO PERSISTENT FATAL LOOP" in normalized
    assert "audio startup P1 remains **CLOSED**" in text
    assert "Canonical r7 remains **PASS / FROZEN / UNCHANGED**" in text
    assert "`PASS_WITH_EXPLICIT_USER_WAIVER` / CLOSED" in text
    assert "does not itself start or pass P3" in text
    assert "Main10" in text and "does not" in text
    assert "r8 remains **NOT AUTHORIZED / NOT BUILT**" in text


def test_known_debt_and_collector_limits_are_not_promoted() -> None:
    text = _result()
    assert "CONFIG_NFS_FS=y` versus FCM-6 `n`" in text
    assert "Preserve NOT PASS" in text
    assert "Device is permissive" in text
    assert "collector-created shell denials" in text
    assert "Four non-success specs are access/empty/multi-path semantics, not device defects" in text
    assert "No media playback" in text
