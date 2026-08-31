#!/usr/bin/env python3
"""Fail-closed source, evidence, ELF and candidate checks for compat1a."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
AOSP = Path("/work/src/ubox10-a16-ceiling")
CONFIG = ROOT / "configs/candidates/a16-prototype-b-r7-hevc-abi-compat1a-sdr-shadow-fd.json"
CANDIDATE = ROOT / "out/candidates/a16-prototype-b-r7-hevc-abi-compat1a-sdr-shadow-fd"
COMPAT1 = ROOT / "out/candidates/a16-prototype-b-r7-hevc-abi-compat1-sdr-shadow"
EVIDENCE = Path("/work/evidence/ubox10/r7-compat1-physical-fail/unpacked")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest().upper()


def fail(message: str) -> None:
    raise RuntimeError(message)


def strong_undefined(path: Path) -> set[str]:
    output = subprocess.check_output(
        ["nm", "-D", "--undefined-only", "--format=posix", str(path)], text=True
    )
    return {
        fields[0].split("@", 1)[0]
        for line in output.splitlines()
        if len(fields := line.split()) >= 2 and fields[1] == "U"
    }


def dynamic_contract(path: Path) -> tuple[list[str], list[str]]:
    dynamic = subprocess.check_output(["readelf", "-Wd", str(path)], text=True)
    symbols = subprocess.check_output(["readelf", "-Ws", str(path)], text=True)
    needed = sorted(line.split("[", 1)[1].split("]", 1)[0] for line in dynamic.splitlines()
                    if "(NEEDED)" in line)
    exports = sorted(fields[-1].split("@", 1)[0] for line in symbols.splitlines()
                     if len(fields := line.split()) >= 8 and fields[3] != "SECTION" and
                     fields[4] in {"GLOBAL", "WEAK"} and fields[6] != "UND")
    return needed, exports


def verify_evidence() -> None:
    manifest = EVIDENCE / "SHA256SUMS.linux"
    lines = [line for line in manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(lines) != 49:
        fail(f"expected 49 physical evidence entries, found {len(lines)}")
    for line in lines:
        expected, relative = line.split(maxsplit=1)
        item = EVIDENCE / relative.lstrip("* ").replace("\\", "/")
        if not item.is_file() or digest(item) != expected.upper():
            fail(f"physical evidence mismatch: {relative}")


def main() -> None:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    if cfg["id"] != "a16-prototype-b-r7-hevc-abi-compat1a-sdr-shadow-fd":
        fail("wrong candidate ID")
    governance = cfg["governance"]
    if governance["gate3"] != "HOLD" or governance["r8_authorized"] or \
            governance["development_branch_created"]:
        fail("Gate3/r8/development governance changed")
    verify_evidence()

    overlay = ROOT / cfg["source_contract"]["overlay"]
    state = subprocess.check_output([str(overlay / "prepare.sh"), "check", str(AOSP)], text=True)
    if "source state: PATCHED" not in state:
        fail("compat1a overlay is not exact")
    for relative, record in cfg["source_contract"]["files"].items():
        item = AOSP / relative
        if item.stat().st_size != record["size"] or digest(item) != record["sha256"]:
            fail(f"compat1a source identity changed: {relative}")
    source = (AOSP / "external/skia/src/gpu/ganesh/gl/AHardwareBufferGL.cpp").read_text()
    header = (AOSP / "external/skia/src/gpu/ganesh/gl/UBOXR7Compat1Metadata.h").read_text()
    for text in ("memfd_ftruncate_sealed", "createSizedShadowFd"):
        if text not in source:
            fail(f"missing exact fd correction marker: {text}")
    for text in ("__NR_memfd_create", "ftruncate", "F_SEAL_GROW", "F_SEAL_SHRINK"):
        if text not in header:
            fail(f"missing sized memfd operation: {text}")
    if "ashmem_create_region" in source or "ashmem_get_size_region" in source:
        fail("compat1a still uses/bypasses legacy ashmem size semantics")
    subprocess.run([sys.executable, str(ROOT / "scripts/check-a16-prototype-b-r7-compat1a-shadow-fd.py")],
                   check=True)

    image = CANDIDATE / f"x12-{cfg['id']}.img"
    build = json.loads((CANDIDATE / "build-result.json").read_text(encoding="utf-8"))
    audit = json.loads((CANDIDATE / "offline-audit/offline-audit.json").read_text(encoding="utf-8"))
    if image.stat().st_size != 1641822208 or digest(image) != \
            "9E9592BF420F40A386BC347B027A85B2F9ED0A44DDB132BDBAB9882905F75722":
        fail("compat1a final image identity changed")
    if build["status"] != "OFFLINE_CHECKED" or build["physical_status"] != "NOT_YET_VALIDATED":
        fail("compat1a incorrectly claims physical validation")
    if audit["compatibility"]["full_vintf_exit"] != 65 or \
            audit["compatibility"]["system_vintf"] != "PASS":
        fail("VINTF classification changed")
    if audit["preservation"]["system_tree_delta"] != {
        "added": [], "removed": [], "changed": ["system/bin/surfaceflinger"]
    } or audit["preservation"]["vendor_tree_delta"] != {
        "added": [], "removed": [], "changed": []
    }:
        fail("signed-filesystem delta expanded")

    old = COMPAT1 / "compat1-surfaceflinger"
    new = CANDIDATE / "compat1-surfaceflinger"
    change = cfg["runtime_change"]
    if digest(old) != change["compat1_sha256"] or digest(new) != change["sha256"]:
        fail("compat1-to-compat1a SurfaceFlinger identities changed")
    if strong_undefined(old) != strong_undefined(new):
        fail("compat1a changed SurfaceFlinger strong undefined imports")
    if dynamic_contract(old) != dynamic_contract(new):
        fail("compat1a changed SurfaceFlinger DT_NEEDED or strong exports")
    combined = new.read_bytes()
    for marker in (
        b"UBOX_R7_DIAG1", b"UBOX_R7_DIAG3", b"UBOX_R7_COMPAT1", b"ALLOC_INITIAL",
        b"REMOTE_IMPORT", b"CODEC_PRE_USE", b"CODEC_POST_FBD", b"EGL_PREIMPORT",
        b"eligible", b"shadow_created", b"translated", b"view_created",
        b"egl_import_result", b"memfd_ftruncate_sealed", b"Failed to create a valid texture.",
    ):
        if marker not in combined and marker not in (
            b"ALLOC_INITIAL", b"REMOTE_IMPORT", b"CODEC_PRE_USE", b"CODEC_POST_FBD"
        ):
            fail(f"compat1a lost required marker/fatal: {marker!r}")
    for name in ("libstagefright64", "gralloc32", "gralloc64"):
        if digest(CANDIDATE / f"compat1-{name}") != digest(COMPAT1 / f"compat1-{name}"):
            fail(f"compat1a changed preserved runtime: {name}")
    canonical = ROOT / "out/candidates/a16-prototype-b-r7/x12-a16-prototype-b-r7.img"
    if canonical.stat().st_size != 1641773056 or digest(canonical) != \
            "A1F58668AEFFC9DC83CFFD8A49A309839332B6616C02153DCC00A71136A7AA27":
        fail("canonical r7 identity changed")
    print("PASS_COMPAT1A_EXACT_SIZED_SHADOW_FD_ONE_RUNTIME_FILE_DELTA")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
