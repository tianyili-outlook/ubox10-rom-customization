"""Governance locks for P3-A RC-A2 and exact 4K compat1b forensics."""
from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[1]
REPORT = (
    ROOT
    / "docs/m8/device-tests/20260905-a16-p3a-rca2-compat1b-forensics/README.md"
)
CONFIG = ROOT / "configs/candidates/a16-dev-p3a-omx-r1.json"


def _report() -> str:
    return REPORT.read_text(encoding="utf-8")


def _normalized_report() -> str:
    return " ".join(_report().split())


def test_evidence_and_incidents_are_separated() -> None:
    text = _normalized_report()
    assert "62ce8f1623bbc4569a14f2c90bb5e9011657ee6765781e93e30b317d4e6f7921" in text
    assert "7/7 PASS, 0 FAIL" in text
    assert "A — medialibrary preparse" in text
    assert "B — formal manual playback" in text
    assert "PID 596" in text and "PID 2503 survives" in text


def test_rca2_capacity_root_cause_and_readiness_are_locked() -> None:
    text = _normalized_report()
    assert "VideoPicture+0x98" in text
    assert "cdc_malloc(0x1000)" in text
    assert "0x5bb8" in text and "23,480" in text
    assert "19,384 bytes" in text
    assert "C — HEAP HEADER OVERWRITTEN BEFORE FIRST FREE" in text
    assert "READY_FOR_NARROW_BINARY_PATCH" in text
    assert "after: pPicture->pMetaData = cdc_malloc(0x6000)" in text
    assert "does not leak" in text


def test_exact_4k_buffer_and_two_populations_are_locked() -> None:
    text = _normalized_report()
    assert "9891309682700..2707" in text and "12,441,664" in text
    assert "9891309682708..2721" in text and "19,489,120" in text
    assert "buffer_id = 9891309682708" in text
    assert "backing_store_id= 2229088026704" in text
    for value in (
        "0x40402d00", "0x40400900", "0x40000000", "0x80000010",
        "19,492,864", "24,576", "0x00000010",
    ):
        assert value in text


def test_metadata_conclusion_is_strong_but_does_not_invent_raw_words() -> None:
    text = _normalized_report()
    assert "B — SAME METADATA ABI COLLISION, VERY HIGH CONFIDENCE" in text
    assert "0x80..0xb7" in text
    assert "cannot be recovered from this archive" in text
    assert "A separate 4K/auto-AFBC import limitation can exist" in text


def test_compat1b_scope_and_translation_are_exact() -> None:
    text = _normalized_report()
    assert "READY_FOR_EXACT_COMPAT1B_IMPLEMENTATION" in text
    assert "original[23544..23599] -> shadow[0x80..0xb7]" in text
    assert "copy exactly 56 bytes" in text
    for excluded in ("Main10", "P010", "HDR10", "HLG", "protected/DRM"):
        assert excluded in text
    assert "Image fd, all planes, total size, usage" in text


def test_candidate_and_project_governance_are_consistent() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert config["status"] == "PHYSICAL_TESTED_P3A_FAIL_RCA_EFFECTIVE_RCA2_AND_RCB_IDENTIFIED"
    assert config["physical_evidence"]["candidate_test_completed"] is True
    assert config["physical_evidence"]["p3a_pass"] is False
    assert config["physical_evidence"]["original_rc_a_repair_effective"] is True
    assert config["governance"]["rc_a"] == "ORIGINAL_DRAIN_NULL_PHYSICAL_REPAIR_EFFECTIVE"
    assert config["governance"]["rc_a2"] == (
        "PHYSICAL_FAIL_FORENSICS_COMPLETE_READY_FOR_NARROW_BINARY_PATCH"
    )
    assert config["governance"]["rc_b"] == (
        "PHYSICAL_FAIL_EXACT_4K_CONTRACT_CAPTURED_COMPAT1B_IMPLEMENTATION_READY"
    )
    assert config["governance"]["p3b_main10"] == "NOT_AUTHORIZED"
    assert config["governance"]["r8_authorized"] is False
    assert config["governance"]["r8_built"] is False
    assert config["governance"]["physical_validation_required"] is False


def test_canonical_summaries_point_to_parallel_forensics() -> None:
    path = "20260905-a16-p3a-rca2-compat1b-forensics/README.md"
    for rel in ("docs/m8/STATUS.md", "docs/m8/TODO.md", "docs/DEVICE_TEST.md"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert path in text
        assert "RC-A2" in text and "compat1b" in text
        assert "P3-B" in text and "NOT AUTHORIZED" in text


def test_no_runtime_fix_or_new_candidate_is_tracked() -> None:
    # The forensic snapshot did not implement a fix. The subsequent explicitly
    # authorized compat1b-r1 build must not rewrite that historical conclusion.
    assert "READY_FOR_EXACT_COMPAT1B_IMPLEMENTATION" in _report()
    assert "No Android image was built" in _report()
    assert not (ROOT / "out/candidates/a16-dev-p3a-rca2-r1").exists()
    assert not (ROOT / "out/candidates/a16-dev-p3a-compat1b").exists()
