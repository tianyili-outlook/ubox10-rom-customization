"""Governance locks for the P3-A RC-A OMX drain repair-readiness study."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = (
    ROOT
    / "docs/m8/device-tests/20260904-a16-p3a-omx-drain-repair-readiness/README.md"
)


def _report() -> str:
    return REPORT.read_text(encoding="utf-8")


def test_exact_binary_and_fault_mapping_remain_locked() -> None:
    text = _report()
    assert "29f500e3089651c41a4c2a88c1f82b99ee389af7a83101ce929516018d5cea87" in text
    assert "2042d7e0112320dc855cccee324af569" in text
    assert "83,780 bytes" in text
    assert "`0xe138`, `__anDrain(OmxDecoder*)+1212`" in text
    assert "`OmxDecoder+0x58e0`" in text
    assert "`+0x9c/+0xa0/+0xa4/+0xa8`" in text


def test_source_archaeology_is_versioned_and_not_overclaimed() -> None:
    text = _report()
    assert "e68d4a727085d02d4622d85b5234304349d4e448" in text
    assert "63344eadfbab18195046678079d2f3d32d0c61cc" in text
    assert "e4246be521203adb2d93d52482239044a7f9b6fe" in text
    assert "a912bbe300d522e199001bd903bab22e54eff37b" in text
    assert "NEAR-EXACT SAME STATE MACHINE" in text
    assert "No candidate is labelled exact" in text


def test_two_picture_ownership_and_repair_semantics_are_locked() -> None:
    text = _report()
    assert "`NextPictureInfo`" in text and "non-owning peek" in text
    assert "`RequestPicture`" in text and "dequeues" in text
    assert "`ReturnPicture`" in text and "releases/recycles" in text
    assert "A — read color aspects from the peeked `picture`" in text
    assert "Do not add" in text and "NULL-only early return" in text
    assert "No dequeue, count change, FBD, leak or extra return" in text


def test_reachability_and_generality_are_not_misstated_as_4k_only() -> None:
    text = _report()
    assert "`ValidPictureNum(decoder, 0) > 0`" in text
    assert "`OmxDecoder+0x58bc == 0`" in text
    assert "geometry comparison is equal or alignment-equivalent" in text
    assert "not classified as a 4K-only defect" in text
    assert "generic copy-path lifecycle" in text
    assert "invocation selected copy mode" in text
    assert "remain unknown" in text


def test_readiness_and_deferred_scope_are_locked() -> None:
    text = _report()
    assert "RC-A = READY_FOR_NARROW_BINARY_PATCH" in text
    assert "NO OMX FIX IS APPLIED" in text
    assert "RC-B/compat1b is deferred and unchanged" in text
    assert "P3-B Main10 remains **NOT AUTHORIZED**" in text
    assert "Audio startup P1 remains **CLOSED**" in text
    assert "P2 remains **COMPLETE**" in text
    assert "`r8` remains **NOT AUTHORIZED / NOT BUILT**" in text
    assert "No physical retest occurred" in text
    assert "no Android image or candidate was built" in text


def test_readiness_history_and_current_candidate_transition_are_both_locked() -> None:
    readiness = _report()
    assert "READY_FOR_NARROW_BINARY_PATCH" in readiness
    assert "NO FIX APPLIED" in readiness
    status = (ROOT / "docs/m8/STATUS.md").read_text(encoding="utf-8")
    todo = (ROOT / "docs/m8/TODO.md").read_text(encoding="utf-8")
    for text in (status, todo):
        normalized = " ".join(text.split())
        assert "READY_FOR_NARROW_BINARY_PATCH" in normalized
        assert "PATCH IMPLEMENTED OFFLINE" in normalized
        assert "PHYSICAL VALIDATION PENDING" in normalized
        assert "compat1b" in normalized
