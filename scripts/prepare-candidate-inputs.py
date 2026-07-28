#!/usr/bin/env python3
"""Restore reproducible candidate-build inputs from the official IMAGEWTY image."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from ubox10_rom.ext4_image import read_manifest  # noqa: E402
from ubox10_rom.ext4_manifest import assess_root_hierarchy  # noqa: E402


OFFICIAL_IMAGE = REPO / "x12-1024.img"
OFFICIAL_IMAGE_SHA256 = (
    "371A653604618E8B78786F279EA6F64E5D1028B430C9B41F330B08456A264065"
)
EXTRACTED_DIR = REPO / "firmware" / "extracted"
IMAGEWTY_MANIFEST = REPO / "work" / "manifest.json"
SUNXI_TOOL = REPO / "tools" / "sunxi_image_tool.py"
LOGICAL_EXTRACTOR = REPO / "scripts" / "extract-logical-partition.py"
OFFICIAL_SUPER_SHA256 = (
    "BE6FAAA476D5DD17F9E6578ED8A48DA351C9D7C7EFD2C9AEBD65788F42A7F479"
)

PARTITIONS = {
    "system_a": {
        "output": REPO / "out/official-system-a/20260726-r1/system_a.img",
        "sha256": "B154BFE5DF8AED02C0765E5774B74EACD00F94D102305BEEE3CA2BD0C122BDAF",
        "manifest": "official-system-a-manifest.json",
    },
    "product_a": {
        "output": REPO / "out/official-product-a/20260726-r1/product_a.img",
        "sha256": "361E798D5744665345C29EF9712D2EA41E0BB461AE906BD8CBE6DA9D99C1068E",
        "manifest": "manifest.json",
    },
    "vendor_a": {
        "output": REPO / "out/official-vendor-a/20260726-r1/vendor_a.img",
        "sha256": "BB91A8B7ED4AC0145F434F89FD76865EB4311F234AA46D67C8373A7CD5B4929A",
        "manifest": "manifest.json",
    },
    "vendor_dlkm_a": {
        "output": REPO
        / "out/official-vendor-dlkm-a/20260726-r1/vendor_dlkm_a.img",
        "sha256": "C589DC0B12E150469F179738F127F36F6321943577453A7DB335AB9E647B8FE5",
        "manifest": "manifest.json",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def matches_container_payload(
    container: Path,
    extracted: Path,
    offset: int,
    length: int,
) -> bool:
    if not extracted.is_file() or extracted.stat().st_size != length:
        return False
    remaining = length
    with container.open("rb") as source, extracted.open("rb") as candidate:
        source.seek(offset)
        while remaining:
            chunk_size = min(4 * 1024 * 1024, remaining)
            source_chunk = source.read(chunk_size)
            candidate_chunk = candidate.read(chunk_size)
            if (
                len(source_chunk) != chunk_size
                or candidate_chunk != source_chunk
            ):
                return False
            remaining -= chunk_size
        return candidate.read(1) == b""


def console_safe(value: str) -> str:
    encoding = sys.stdout.encoding or "utf-8"
    return value.encode(encoding, errors="replace").decode(encoding, errors="replace")


def run(args: list[str]) -> None:
    result = subprocess.run(
        args,
        cwd=REPO,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if result.returncode:
        raise RuntimeError(
            f"command failed ({result.returncode}): "
            f"{subprocess.list2cmdline(args)}\n"
            f"{console_safe(result.stdout)}\n{console_safe(result.stderr)}"
        )
    if result.stdout.strip():
        print(console_safe(result.stdout.rstrip()))


def safe_staging_directory() -> Path:
    parent = REPO / "out"
    parent.mkdir(parents=True, exist_ok=True)
    for _ in range(100):
        candidate = parent / f".prepare-candidate-inputs-{uuid.uuid4().hex[:8]}"
        try:
            candidate.mkdir()
        except FileExistsError:
            continue
        return candidate
    raise RuntimeError("unable to allocate candidate-input staging directory")


def verify_official_container() -> None:
    if not OFFICIAL_IMAGE.is_file():
        raise RuntimeError(f"official recovery/source image is missing: {OFFICIAL_IMAGE}")
    observed = sha256(OFFICIAL_IMAGE)
    if observed != OFFICIAL_IMAGE_SHA256:
        raise RuntimeError(
            f"official image SHA-256 mismatch: {observed} != {OFFICIAL_IMAGE_SHA256}"
        )
    if not SUNXI_TOOL.is_file() or not LOGICAL_EXTRACTOR.is_file():
        raise RuntimeError("required extraction scripts are missing")
    run([sys.executable, str(SUNXI_TOOL), "verify", str(OFFICIAL_IMAGE)])


def ensure_imagewty_inputs(staging: Path) -> Path:
    manifest_staging = staging / "manifest.json"
    run(
        [
            sys.executable,
            str(SUNXI_TOOL),
            "list",
            str(OFFICIAL_IMAGE),
            "--json",
            str(manifest_staging),
        ]
    )
    manifest = json.loads(manifest_staging.read_text(encoding="utf-8"))
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise RuntimeError("IMAGEWTY manifest contains no files")

    expected_entries: dict[str, tuple[int, int]] = {}
    for entry in entries:
        name = entry.get("filename")
        length = entry.get("orig_len")
        offset = entry.get("offset")
        if (
            not isinstance(name, str)
            or Path(name).name != name
            or not isinstance(length, int)
            or length < 0
            or not isinstance(offset, int)
            or offset < 0
            or name in expected_entries
        ):
            raise RuntimeError(f"unsafe IMAGEWTY manifest entry: {entry!r}")
        expected_entries[name] = (offset, length)

    extracted_valid = all(
        matches_container_payload(
            OFFICIAL_IMAGE,
            EXTRACTED_DIR / name,
            offset,
            length,
        )
        for name, (offset, length) in expected_entries.items()
    )
    if not extracted_valid:
        extracted_staging = staging / "extracted"
        run(
            [
                sys.executable,
                str(SUNXI_TOOL),
                "extract",
                str(OFFICIAL_IMAGE),
                "--out",
                str(extracted_staging),
            ]
        )
        for name, (offset, length) in expected_entries.items():
            source = extracted_staging / name
            if not matches_container_payload(
                OFFICIAL_IMAGE,
                source,
                offset,
                length,
            ):
                raise RuntimeError(
                    f"extracted IMAGEWTY entry mismatch: {name}"
                )
        EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
        for name in expected_entries:
            source = extracted_staging / name
            target = EXTRACTED_DIR / name
            source.replace(target)

    IMAGEWTY_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    manifest_staging.replace(IMAGEWTY_MANIFEST)
    super_image = EXTRACTED_DIR / "super.fex"
    observed_super = sha256(super_image)
    if observed_super != OFFICIAL_SUPER_SHA256:
        raise RuntimeError(
            f"official super SHA-256 mismatch: {observed_super} != "
            f"{OFFICIAL_SUPER_SHA256}"
        )
    return super_image


def publish_partition_metadata(partition: str, image: Path, spec: dict) -> None:
    manifest = read_manifest(image)
    manifest["source"]["path"] = str(spec["output"].resolve())
    if partition == "system_a":
        root = assess_root_hierarchy(manifest)
        if root.status != "PASS":
            raise RuntimeError(
                f"official system root hierarchy failed: {root.reason_codes}"
            )
    manifest_path = spec["output"].parent / spec["manifest"]
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    extraction = {
        "source": str((EXTRACTED_DIR / "super.fex").resolve()),
        "source_sha256": OFFICIAL_SUPER_SHA256,
        "partition": partition,
        "bytes": image.stat().st_size,
        "output": str(spec["output"].resolve()),
        "output_sha256": spec["sha256"],
    }
    (spec["output"].parent / "extraction.json").write_text(
        json.dumps(extraction, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def ensure_logical_partitions(staging: Path, super_image: Path) -> None:
    for partition, spec in PARTITIONS.items():
        output = spec["output"]
        if output.exists():
            observed = sha256(output)
            if observed != spec["sha256"]:
                raise RuntimeError(
                    f"refusing mismatched existing input: {output} ({observed})"
                )
        else:
            extraction_dir = staging / partition
            run(
                [
                    sys.executable,
                    str(LOGICAL_EXTRACTOR),
                    "--super",
                    str(super_image),
                    "--partition",
                    partition,
                    "--output-dir",
                    str(extraction_dir),
                ]
            )
            extracted = extraction_dir / f"{partition}.img"
            observed = sha256(extracted)
            if observed != spec["sha256"]:
                raise RuntimeError(
                    f"{partition} SHA-256 mismatch: {observed} != {spec['sha256']}"
                )
            output.parent.mkdir(parents=True, exist_ok=True)
            extracted.replace(output)
        publish_partition_metadata(partition, output, spec)
        print(f"PASS {partition}: {spec['sha256']}")


def main() -> int:
    verify_official_container()
    staging = safe_staging_directory()
    try:
        super_image = ensure_imagewty_inputs(staging)
        ensure_logical_partitions(staging, super_image)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    print("Candidate build inputs are ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
