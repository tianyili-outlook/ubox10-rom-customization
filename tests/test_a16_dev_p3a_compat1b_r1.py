"""Exact consumer-only compat1b eligibility, translation, preservation and governance."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "configs/aosp/architecture-ceiling-a16/development/p3a-compat1b-r1"
AOSP = Path("/work/src/ubox10-a16-ceiling")
CFG = ROOT / "configs/candidates/a16-dev-p3a-compat1b-r1.json"


def test_contract_and_full_translation_under_sanitizers(tmp_path):
    compiler = AOSP / "prebuilts/clang/host/linux-x86/clang-r547379/bin/clang++"
    shared = AOSP / "external/skia/src/gpu/ganesh/gl/UBOXR7Compat1Metadata.h"
    if not compiler.is_file() or not shared.is_file():
        pytest.skip("external AOSP compiler/compat1a header absent")
    assert hashlib.sha256(shared.read_bytes()).hexdigest() == (
        "98228a9599eedfcd6c073124c31a48e105e3360e7c62ed05c4c77d2300951294")
    target = tmp_path / "contract"
    subprocess.run([str(compiler), "-std=c++17", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined,integer", "-fno-sanitize-recover=all",
                    "-I", str(OVERLAY), "-I", str(shared.parent),
                    str(ROOT / "tests/fixtures/a16_p3a_compat1b_contract.cpp"),
                    "-o", str(target)], check=True)
    subprocess.run([str(target)], check=True)


def test_overlay_does_not_change_translation_ownership_or_compat1a_predicate():
    patch = (OVERLAY / "compat1b.patch").read_text()
    changed = "\n".join(line[1:] for line in patch.splitlines()
                        if line.startswith(("+", "-")) and not line.startswith(("+++", "---")))
    for forbidden in ("memcpy(", "translateMetadata(", "native_handle_clone(",
                      "AHardwareBuffer_createFromHandle(", "AHardwareBuffer_release(",
                      "RequestPicture", "ReturnPicture", "eglCreateImageKHR(",
                      "munmap(", "close(", "createSizedShadowFd(",
                      "const bool exactPublicContract", "const bool exactHandleContract",
                      "const bool exactSdrAttr", "const bool legacyCropCollision"):
        assert forbidden not in changed
    assert "handle->version == 12" in changed
    assert "fstat(handle->data[0]" in changed
    assert "compat1bContract ? !compat1bMetadata" in changed
    assert "UBOX_P3_COMPAT1B eligible=1" in changed
    assert patch.count("--- a/") == 1


def test_exact_sdr_attr_matches_physical_hash():
    # Physical logger's full active-attribute hash proves the 28-byte unset HDR sentinel too.
    attr = b"\xff" * 52 + (0x10010000).to_bytes(4, "little")
    value = 14695981039346656037
    for byte in attr:
        value = ((value ^ byte) * 1099511628211) & ((1 << 64) - 1)
    assert value == 0xe7e2d4496502c218


def test_isolated_build_requires_exact_control_and_restores_audio_input():
    text = (ROOT / "scripts/build-a16-p3a-compat1b-surfaceflinger.py").read_text()
    assert 'for label in ("control", "compat1b")' in text
    assert 'digest(data) != CONTROL_SHA or len(data) != 8577592' in text
    assert 'fmq.write_bytes(original)' in text.split('finally:', 1)[1]
    assert 'm -j16 surfaceflinger' in text
    assert '06c960e672863ad557af921565621997cb9b113ba2290049af91028a405cd0a5' in text
    assert '69d61adc1c0123ce90f9abc6956a7305126b3ee7e970c08d8569b718f7ffaa0b' in text


def test_manifest_is_complete_and_permission_errors_fail_closed(tmp_path, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location("compat1b_audit_test", ROOT / "scripts/audit-a16-dev-p3a-compat1b-r1.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    target = tmp_path / "system/bin/surfaceflinger"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"baseline")
    before = module.strict_tree_manifest(tmp_path)
    target.write_bytes(b"new-code")
    after = module.strict_tree_manifest(tmp_path)
    assert module.delta(before, after) == {
        "added": [], "removed": [], "changed": ["system/bin/surfaceflinger"]}
    def denied(*args, **kwargs):
        kwargs["onerror"](PermissionError("directory cannot be enumerated"))
    monkeypatch.setattr(module.os, "walk", denied)
    with pytest.raises(PermissionError):
        module.strict_tree_manifest(tmp_path)


def test_physical_contract_preserves_staging_and_no_scope_expansion():
    report = (ROOT / 'docs/m8/device-tests/20260905-a16-p3a-compat1b-r1-build/README.md').read_text()
    for marker in ('BootGate FIRST', 'REVIEW', 'first-launch VLC', 'formal AVCPre',
                   'one manual Main8 SDR 4K30 attempt', 'No Main10',
                   'metadata collision', 'physical validation'):
        assert marker.lower() in report.lower()
    assert report.index('BootGate FIRST') < report.index('install/verify VLC') < report.index('formal AVCPre')


def test_governance_prior_fixes_and_one_runtime_scope():
    cfg = json.loads(CFG.read_text())
    assert cfg["runtime_change"]["partition_path"] == "/system/bin/surfaceflinger"
    gov = cfg["governance"]
    assert gov["rc_a2"] == "PHYSICAL_PASS_CLOSED"
    assert gov["rc_b"] == "COMPAT1B_IMPLEMENTED_OFFLINE_CANDIDATE_BUILT_PHYSICAL_VALIDATION_PENDING"
    assert gov["audio_p1"] == "CLOSED" and gov["p2"] == "COMPLETE"
    assert gov["p3a"] == "PHYSICAL_FAIL_FORENSICS_COMPLETE"
    assert gov["p3b_main10"] == "NOT_AUTHORIZED"
    assert not gov["r8_authorized"] and not gov["r8_built"] and not gov["release"]
    for name, sha in {
        "fbm_r1": "786264793BB16083CD62BC3BC0B6A2AE4673DBC75504A79EAC189DB943840E9F",
        "omx_r1": "5FE74A28EB9E083959FDAC9CFDE870FAA2AF4447DADB7776C1E7F4CFC6D1EE8B",
        "audio_impl32": "E2F3D49D757AA4132180C3D247857FC9725D7113E92A079E10181AADBCC062ED",
    }.items():
        assert cfg["preserved_runtime"][name]["sha256"] == sha


def test_external_physical_evidence_if_present():
    cfg = json.loads(CFG.read_text())
    evidence = cfg["physical_evidence"]
    archive = Path(evidence["archive"])
    if not archive.is_file():
        pytest.skip("raw evidence deliberately outside Git")
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == evidence["sha256"]
    import zipfile
    with zipfile.ZipFile(archive) as z:
        manifests = [n for n in z.namelist() if n.endswith("/SHA256SUMS.txt") or n == "SHA256SUMS.txt"]
        assert len(manifests) == 1
        manifest = Path(manifests[0])
        members = {str(Path(n)): n for n in z.namelist()}
        entries = z.read(manifests[0]).decode("utf-8-sig").splitlines()
        count = 0
        for line in entries:
            if not line.strip(): continue
            sha, name = line.split(maxsplit=1)
            member = manifest.parent / name.lstrip("* ").replace("\\", "/")
            assert hashlib.sha256(z.read(members[str(member)])).hexdigest() == sha.lower()
            count += 1
        assert count == 12


def test_candidate_if_built():
    candidate = ROOT / "out/candidates/a16-dev-p3a-compat1b-r1"
    if not (candidate / "offline-audit/offline-audit.json").is_file():
        pytest.skip("candidate offline audit absent")
    subprocess.run([sys.executable, str(ROOT / "scripts/check-a16-dev-p3a-compat1b-r1.py")], check=True)
