"""Exact FBM capacity patch, ownership, packaging and scope regressions."""
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
PATCHER = ROOT / "scripts/patch-a16-p3a-fbm-r1.py"
BASE = ROOT / "out/candidates/a16-dev-p3a-omx-r1/vendor_a.img"
CANDIDATE = ROOT / "out/candidates/a16-dev-p3a-fbm-r1"
SPEC = importlib.util.spec_from_file_location("fbm_patch", PATCHER)
assert SPEC and SPEC.loader
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)


@pytest.fixture
def original(tmp_path):
    if not BASE.is_file():
        pytest.skip("exact external OMX-r1 image absent")
    target = tmp_path / "original.so"
    subprocess.run(["debugfs", "-R", f"dump /lib/libfbm.so {target}", str(BASE)],
                   check=True, capture_output=True)
    return target.read_bytes()


def test_exact_two_byte_patch_and_free_unchanged(original):
    patched, changed = PATCH.patch_bytes(original)
    assert len(patched) == 20980
    assert changed == [0x2936, 0x2937]
    assert PATCH.digest(patched) == PATCH.OUTPUT_SHA256
    assert patched[:0x2934] == original[:0x2934]
    assert patched[0x2938:] == original[0x2938:]
    # Allocation failure branch, metadata store and the entire free/destroy
    # functions all lie outside the only modified immediate instruction.
    assert patched[0x2942:0x294c] == original[0x2942:0x294c]
    assert patched[0x2a70:0x2ccc] == original[0x2a70:0x2ccc]


def test_sha_size_bytes_and_repeat_fail_closed(original, monkeypatch):
    with pytest.raises(ValueError, match="size mismatch"):
        PATCH.patch_bytes(b"unrelated ELF")
    damaged = bytearray(original)
    damaged[0x100] ^= 1
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        PATCH.patch_bytes(bytes(damaged))
    patched, _ = PATCH.patch_bytes(original)
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        PATCH.patch_bytes(patched)
    damaged = bytearray(original)
    damaged[0x2934] ^= 1
    monkeypatch.setattr(PATCH, "INPUT_SHA256", PATCH.digest(bytes(damaged)))
    with pytest.raises(ValueError, match="original bytes mismatch"):
        PATCH.patch_bytes(bytes(damaged))


def test_assembler_and_two_disassemblers_prove_malloc_argument(original, tmp_path):
    clang_root = Path("/work/src/ubox10-a16-ceiling/prebuilts/clang/host/linux-x86")
    if not (clang_root / "clang-r547379/bin/clang").exists():
        pytest.skip("AOSP assembler/disassemblers absent")
    asm = tmp_path / "size.s"
    asm.write_text(".syntax unified\n.thumb\n.text\n.global sizes\n.thumb_func\nsizes:\n"
                   "mov.w r0, #0x1000\nmov.w r0, #0x6000\n")
    obj = tmp_path / "size.o"
    subprocess.run([str(clang_root / "clang-r547379/bin/clang"),
                    "-target", "armv7a-linux-androideabi31", "-c", str(asm), "-o", str(obj)], check=True)
    encoded = tmp_path / "size.bin"
    subprocess.run([str(clang_root / "clang-r547379/bin/llvm-objcopy"),
                    "-O", "binary", "--only-section=.text", str(obj), str(encoded)], check=True)
    assert encoded.read_bytes() == PATCH.ORIGINAL_BYTES + PATCH.PATCHED_BYTES
    target = tmp_path / "patched.so"
    target.write_bytes(PATCH.patch_bytes(original)[0])
    for revision in ("clang-r547379", "clang-r530567"):
        tool = clang_root / revision / "bin/llvm-objdump"
        if not tool.is_file():
            pytest.skip(f"second disassembler absent: {tool}")
        text = subprocess.check_output([str(tool), "-d", "--triple=thumbv7-linux-gnueabi",
                                        "--start-address=0x391c", "--stop-address=0x3ccc", str(target)], text=True)
        for marker in ("3934: f44f 40c0", "mov.w\tr0, #0x6000", "3942: f001 eef6",
                       "3946: b1b8", "3948: f8c8 0098", "3a92: f001 ee7e", "3a98: f8c4 0098"):
            assert marker in text


def test_cli_refuses_existing_output(original, tmp_path):
    source = tmp_path / "source.so"
    target = tmp_path / "target.so"
    source.write_bytes(original)
    target.write_bytes(b"preserve")
    done = subprocess.run([sys.executable, str(PATCHER), "--input", str(source), "--output", str(target)],
                          capture_output=True, text=True)
    assert done.returncode != 0 and "refusing to overwrite" in done.stderr
    assert target.read_bytes() == b"preserve"


def test_governance_and_prior_identities():
    cfg = json.loads((ROOT / "configs/candidates/a16-dev-p3a-fbm-r1.json").read_text())
    assert cfg["runtime_change"]["partition_path"] == "/vendor/lib/libfbm.so"
    assert cfg["runtime_change"]["changed_byte_offsets"] == [0x2936, 0x2937]
    assert cfg["patcher"]["sha256"] == hashlib.sha256(PATCHER.read_bytes()).hexdigest().upper()
    assert cfg["governance"]["rc_a"] == "ORIGINAL_DRAIN_NULL_PHYSICAL_REPAIR_EFFECTIVE"
    assert cfg["governance"]["rc_a2"] == "PATCH_IMPLEMENTED_OFFLINE_CANDIDATE_BUILT_PHYSICAL_VALIDATION_PENDING"
    assert cfg["governance"]["p3b_main10"] == "NOT_AUTHORIZED"
    assert cfg["governance"]["audio_p1"] == "CLOSED"
    assert cfg["governance"]["p2"] == "COMPLETE"
    assert not cfg["governance"]["r8_authorized"] and not cfg["governance"]["r8_built"]
    assert cfg["preserved_runtime"]["omx_r1"]["sha256"] == "5FE74A28EB9E083959FDAC9CFDE870FAA2AF4447DADB7776C1E7F4CFC6D1EE8B"
    assert cfg["preserved_runtime"]["surfaceflinger"]["sha256"] == "06C960E672863AD557AF921565621997CB9B113BA2290049AF91028A405CD0A5"
    assert cfg["preserved_runtime"]["audio_impl32"]["sha256"] == "E2F3D49D757AA4132180C3D247857FC9725D7113E92A079E10181AADBCC062ED"


def test_candidate_checker_if_built():
    if not (CANDIDATE / "offline-audit/offline-audit.json").is_file():
        pytest.skip("new candidate offline audit not yet available")
    done = subprocess.run([sys.executable, str(ROOT / "scripts/check-a16-dev-p3a-fbm-r1.py")],
                          capture_output=True, text=True, check=True)
    assert "PASS_A16_DEV_P3A_FBM_R1_EXACT_ONE_RUNTIME_FILE" in done.stdout
