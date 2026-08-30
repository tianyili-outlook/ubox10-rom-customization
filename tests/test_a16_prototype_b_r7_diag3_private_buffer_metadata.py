"""Static and built locks for the r7-diag3 metadata diagnostic."""
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_diag3_fail_closed_checker() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check-a16-prototype-b-r7-diag3-private-buffer-metadata.py")],
        cwd=ROOT, text=True, capture_output=True, check=True,
    )
    assert "PASS_DIAG3_PRIVATE_BUFFER_METADATA_EXACT_FOUR_RUNTIME_FILE_DELTA" in completed.stdout


def test_diag3_evidence_is_external_and_read_only_input() -> None:
    evidence = Path("/work/evidence/ubox10/r7-diag3-private-buffer-metadata/input/unpacked")
    assert evidence.is_dir()
    assert not evidence.resolve().is_relative_to(ROOT.resolve())


def test_diag3_powershell_capture_safety_when_available() -> None:
    pwsh = shutil.which("pwsh")
    if pwsh is None:
        pytest.skip("PowerShell 7 unavailable on this Linux build host")
    helper = ROOT / "scripts/capture-a16-prototype-b-r7-diag3-private-buffer-metadata.ps1"
    completed = subprocess.run(
        [pwsh, "-NoProfile", "-File", str(helper), "-SelfTest"],
        cwd=ROOT, text=True, capture_output=True, check=True,
    )
    assert "safety self-test: PASS" in completed.stdout
