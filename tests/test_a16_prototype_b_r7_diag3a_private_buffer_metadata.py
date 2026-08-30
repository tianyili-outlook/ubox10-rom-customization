"""Locks for the r7-diag3a instrumentation transparency candidate."""
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_diag3a_fail_closed_checker() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check-a16-prototype-b-r7-diag3a-private-buffer-metadata.py")],
        cwd=ROOT, text=True, capture_output=True, check=True,
    )
    assert "PASS_DIAG3A_EXACT_ONE_RUNTIME_FILE_TRANSPARENCY_DELTA" in completed.stdout


def test_diag3a_fnv_equivalence_and_equivalent_ubsan_build() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check-a16-prototype-b-r7-diag3a-fnv.py")],
        cwd=ROOT, text=True, capture_output=True, check=True,
    )
    assert "PASS_DIAG3A_FNV64_EQUIVALENCE_AND_UBSAN_TRANSPARENCY" in completed.stdout
    assert "ff_24576 size=24576 fnv=0x720923c139c50325" in completed.stdout


def test_diag3a_evidence_is_external() -> None:
    evidence = Path("/work/evidence/ubox10/r7-diag3a-instrumentation-regression/input/unpacked")
    assert evidence.is_dir()
    assert not evidence.resolve().is_relative_to(ROOT.resolve())


def test_diag3a_powershell_capture_safety_when_available() -> None:
    pwsh = shutil.which("pwsh")
    if pwsh is None:
        pytest.skip("PowerShell 7 unavailable on this Linux build host")
    helper = ROOT / "scripts/capture-a16-prototype-b-r7-diag3a-private-buffer-metadata.ps1"
    completed = subprocess.run(
        [pwsh, "-NoProfile", "-File", str(helper), "-SelfTest"],
        cwd=ROOT, text=True, capture_output=True, check=True,
    )
    assert "safety self-test: PASS" in completed.stdout
