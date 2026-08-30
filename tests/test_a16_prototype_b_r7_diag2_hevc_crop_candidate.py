"""Static and built locks for the r7-diag2 HEVC crop diagnostic."""
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_diag2_hevc_crop_fail_closed_checker() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check-a16-prototype-b-r7-diag2-hevc-crop.py")],
        cwd=ROOT, text=True, capture_output=True, check=True,
    )
    assert "PASS_DIAG2_HEVC_CROP_SINGLE_RUNTIME_FILE_DELTA" in completed.stdout


def test_diag2_evidence_is_external_and_untracked() -> None:
    evidence = Path("/work/evidence/ubox10/r7-diag2-hevc-crop")
    assert evidence.is_dir()
    assert not evidence.resolve().is_relative_to(ROOT.resolve())
