"""Governance locks for the failed Android 16 P3-A 4K30 experiment."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = (
    ROOT
    / "docs/m8/device-tests/20260903-a16-p3a-4k30-failure-forensics/README.md"
)


def _report() -> str:
    return REPORT.read_text(encoding="utf-8")


def test_evidence_and_exact_omx_fault_are_locked() -> None:
    text = _report()
    assert "69c9fdfccd2546a96752dda21af9d969e1a1e8641e3bad309073121354676c78" in text
    assert "73/73" in text and "89/89" in text
    assert "29f500e3089651c41a4c2a88c1f82b99ee389af7a83101ce929516018d5cea87" in text
    assert "2042d7e0112320dc855cccee324af569" in text
    assert "__anDrain(OmxDecoder*)+1212" in text
    assert "ldrd  r3, r1, [r0, #0x9c]" in text
    assert "OmxDecoder+0x58e0" in text
    assert "RequestPicture" in text and "0xe42c" in text


def test_graphics_conclusion_does_not_overclaim_missing_4k_contract() -> None:
    text = _report()
    assert "3840x2160" in text
    assert "842094169 == 0x32315659 == YV12" in text
    assert "view=original" in text
    assert "C — BOTH POSSIBLE" in text
    assert "not yet a physical proof of the 4K collision" in text
    for missing in ("Usage", "AFBC", "Sidecar size/state"):
        assert missing in text


def test_repair_order_and_scope_are_locked() -> None:
    text = _report()
    assert "ORDER 1" in text
    assert "OMX drain" in text and "then consider compat1b" in text
    assert "P3-A: **PHYSICAL FAIL / FORENSICS COMPLETE**" in text
    assert "P3-B Main10: **NOT AUTHORIZED**" in text
    assert "Audio startup P1: **CLOSED**" in text
    assert "P2: **COMPLETE**" in text
    assert "`r8`: **NOT AUTHORIZED / NOT BUILT**" in text
    assert "No physical retest" in text
    assert "Android build" in text


def test_canonical_governance_summaries_reference_forensics() -> None:
    expected = "P3-A PHYSICAL FAIL / FORENSICS COMPLETE"
    status = (ROOT / "docs/m8/STATUS.md").read_text(encoding="utf-8")
    todo = (ROOT / "docs/m8/TODO.md").read_text(encoding="utf-8")
    device = (ROOT / "docs/DEVICE_TEST.md").read_text(encoding="utf-8")
    assert expected in status
    assert "P3-A — PHYSICAL FAIL" in todo
    assert "RC-A2/RC-B FORENSICS COMPLETE" in todo
    assert expected in device
    for text in (status, todo, device):
        assert "P3-B" in text and "NOT AUTHORIZED" in text
