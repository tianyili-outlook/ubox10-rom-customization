"""Focused binary-patch and governance tests for a16-dev-p3a-omx-r1."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
PATCHER = ROOT / "scripts/patch-a16-p3a-omx-r1.py"
CONFIG = ROOT / "configs/candidates/a16-dev-p3a-omx-r1.json"
REPORT = ROOT / "docs/m8/device-tests/20260904-a16-p3a-omx-r1-build/README.md"
BASE_VENDOR = ROOT / "out/candidates/a16-dev-audio-r1/vendor_a.img"
CANDIDATE = ROOT / "out/candidates/a16-dev-p3a-omx-r1"

SPEC = importlib.util.spec_from_file_location("p3a_omx_r1_patcher", PATCHER)
assert SPEC is not None and SPEC.loader is not None
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)


def _dump_original(destination: Path) -> Path:
    if not BASE_VENDOR.is_file():
        pytest.skip("exact ignored audio-r1 vendor image is unavailable")
    subprocess.run(
        ["debugfs", "-R", f"dump -p /lib/libOmxVdec.so {destination}", str(BASE_VENDOR)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return destination


def test_exact_source_produces_deterministic_three_byte_patch(tmp_path: Path) -> None:
    original_path = _dump_original(tmp_path / "original.so")
    original = original_path.read_bytes()
    patched, changed = PATCH.patch_bytes(original)
    assert len(patched) == len(original) == PATCH.INPUT_SIZE == 83_780
    assert hashlib.sha256(original).hexdigest().upper() == PATCH.INPUT_SHA256
    assert hashlib.sha256(patched).hexdigest().upper() == PATCH.OUTPUT_SHA256
    assert changed == [0xD130, 0xD131, 0xD132]
    assert patched[0xD130:0xD134] == bytes.fromhex("4f ea 0c 00")
    assert original[:0xD130] == patched[:0xD130]
    assert original[0xD134:] == patched[0xD134:]


def test_wrong_source_sha_and_unrelated_binary_refuse_patch(tmp_path: Path) -> None:
    original = bytearray(_dump_original(tmp_path / "original.so").read_bytes())
    original[0x100] ^= 1
    with pytest.raises(ValueError, match="input SHA256 mismatch"):
        PATCH.patch_bytes(bytes(original))
    with pytest.raises(ValueError, match="input size mismatch"):
        PATCH.patch_bytes(Path(sys.executable).read_bytes())


def test_expected_sha_but_wrong_source_bytes_still_refuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = bytearray(_dump_original(tmp_path / "original.so").read_bytes())
    original[PATCH.PATCH_FILE_OFFSET] ^= 1
    monkeypatch.setattr(PATCH, "INPUT_SHA256", hashlib.sha256(original).hexdigest().upper())
    with pytest.raises(ValueError, match="original bytes mismatch"):
        PATCH.patch_bytes(bytes(original))


def test_repeated_patch_attempt_refuses(tmp_path: Path) -> None:
    original = _dump_original(tmp_path / "original.so").read_bytes()
    patched, _ = PATCH.patch_bytes(original)
    with pytest.raises(ValueError, match="input SHA256 mismatch"):
        PATCH.patch_bytes(patched)


def test_patched_disassembly_selects_live_peek_register(tmp_path: Path) -> None:
    original = _dump_original(tmp_path / "original.so").read_bytes()
    patched, _ = PATCH.patch_bytes(original)
    target = tmp_path / "patched.so"
    target.write_bytes(patched)
    tools = [
        ROOT.parent.parent / "src/ubox10-a16-ceiling/prebuilts/clang/host/linux-x86"
        / revision / "bin/llvm-objdump"
        for revision in ("clang-r547379", "clang-r530567")
    ]
    for tool in tools:
        if not tool.is_file():
            pytest.skip(f"AOSP disassembler unavailable: {tool}")
        output = subprocess.check_output([
            str(tool), "-d", "--triple=thumbv7-linux-gnueabi",
            "--start-address=0xde58", "--stop-address=0xe470", str(target),
        ], text=True)
        assert "e130: ea4f 000c" in output
        assert "mov.w\tr0, r12" in output
        assert "e138: e9d0 3127" in output
        assert "e426:" in output and "e42c:" in output and "e460:" in output


def test_patcher_and_builder_scope_are_narrow() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    patcher = PATCHER.read_text(encoding="utf-8")
    builder = (ROOT / "scripts/build-a16-dev-p3a-omx-r1-candidate.py").read_text(
        encoding="utf-8"
    )
    assert config["runtime_change"]["partition_path"] == "/vendor/lib/libOmxVdec.so"
    assert config["runtime_change"]["changed_byte_count"] == 3
    assert config["runtime_change"]["patched_instruction"] == "mov.w r0, r12"
    assert config["status"] == "OFFLINE_CHECKED_READY_FOR_BOUNDED_PHYSICAL_VALIDATION"
    assert config["governance"]["rc_a"] == (
        "PATCH_IMPLEMENTED_OFFLINE_CANDIDATE_BUILT_PHYSICAL_VALIDATION_PENDING"
    )
    assert config["governance"]["rc_b"] == "DEFERRED_EXPECTED_NEXT_BOUNDARY"
    assert config["governance"]["p3b_main10"] == "NOT_AUTHORIZED"
    assert config["governance"]["r8_authorized"] is False
    for forbidden in ("RequestPicture(decoder", "ReturnPicture(decoder", "compat1b"):
        assert forbidden not in patcher
    assert '"changed": ["lib/libOmxVdec.so"]' in builder
    assert '"rc_b_modified": False' in builder


def test_candidate_checker_when_artifact_is_available() -> None:
    if not CANDIDATE.is_dir():
        pytest.skip("ignored P3-A OMX candidate has not been built yet")
    done = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check-a16-dev-p3a-omx-r1.py")],
        cwd=ROOT, text=True, capture_output=True, check=True,
    )
    assert "PASS_A16_DEV_P3A_OMX_R1_EXACT_ONE_RUNTIME_FILE" in done.stdout


def test_no_formal_candidate_or_r8_names_are_created() -> None:
    assert not (ROOT / "out/candidates/a16-prototype-b-r8").exists()
    assert not (ROOT / "out/candidates/r8").exists()


def test_candidate_report_preserves_physical_and_scope_gates() -> None:
    report = REPORT.read_text(encoding="utf-8")
    assert "B970A69C7670C4AE6DFFA3E06EA2317FAA7585B29EE5FA9F7D4740377A17C4A6" in report
    assert "PHYSICAL VALIDATION PENDING" in report
    assert "RC-B/compat1b: DEFERRED" in report
    assert "P3-B Main10: NOT AUTHORIZED" in report
    assert "NOT r8 / NOT RELEASE" in report
