#!/usr/bin/env python3
"""Measure the frozen r4 vendor extent against the exact B1 provider delta."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile


REPO = Path(__file__).resolve().parents[1]
DEFAULT_VENDOR = (
    REPO
    / "out/candidates/a16-prototype-a-r4/candidate-logical/vendor_a.img"
)
DEFAULT_MALI = Path(
    "/work/local-proprietary/ubox10/prototype-b-b1/libGLES_mali.so"
)
DEFAULT_PRODUCT = Path(
    "/work/src/ubox10-a16-ceiling/out-ceiling-b1/target/product/"
    "ubox10_ceiling_arm64"
)
DEFAULT_AVBTOOL = Path(
    "/work/src/ubox10-a16-ceiling/external/avb/avbtool.py"
)
PARTITION_BYTES = 119_066_624
ORIGINAL_FS_BYTES = 117_104_640
VENDOR_SHA256 = "BB91A8B7ED4AC0145F434F89FD76865EB4311F234AA46D67C8373A7CD5B4929A"

PROPERTY_DELTA = {
    "ro.zygote": "zygote64_32",
    "ro.vendor.product.cpu.abilist": "arm64-v8a,armeabi-v7a,armeabi",
    "ro.vendor.product.cpu.abilist64": "arm64-v8a",
    "ro.vendor.product.cpu.abilist32": "armeabi-v7a,armeabi",
    "ro.bionic.arch": "arm64",
    "ro.bionic.cpu_variant": "generic",
    "ro.bionic.2nd_arch": "arm",
    "ro.bionic.2nd_cpu_variant": "cortex-a15",
    "dalvik.vm.isa.arm.variant": "cortex-a15",
    "dalvik.vm.isa.arm64.variant": "generic",
}
PROPERTY_BEFORE = {
    "ro.zygote": "zygote32",
    "ro.vendor.product.cpu.abilist": "armeabi-v7a,armeabi",
    "ro.vendor.product.cpu.abilist64": "",
    "ro.vendor.product.cpu.abilist32": "armeabi-v7a,armeabi",
    "ro.bionic.arch": "arm",
    "ro.bionic.cpu_variant": "cortex-a7",
    "ro.bionic.2nd_arch": "",
    "ro.bionic.2nd_cpu_variant": "",
    "dalvik.vm.isa.arm.variant": "cortex-a7",
    "dalvik.vm.isa.arm64.variant": "<absent>",
}


def run(argv: list[str], *, capture: bool = False) -> str:
    result = subprocess.run(
        argv,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )
    return result.stdout if capture else ""


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest().upper()


def ext4_fields(image: Path) -> dict[str, int]:
    output = run(["tune2fs", "-l", str(image)], capture=True)
    labels = {
        "Block count": "block_count",
        "Free blocks": "free_blocks",
        "Block size": "block_size",
        "Inode count": "inode_count",
        "Free inodes": "free_inodes",
    }
    values: dict[str, int] = {}
    for line in output.splitlines():
        if ":" not in line:
            continue
        label, raw = line.split(":", 1)
        if label in labels:
            values[labels[label]] = int(raw.strip())
    if set(values) != set(labels.values()):
        raise RuntimeError(f"incomplete tune2fs fields: {values}")
    return values


def replace_properties(source: Path, output: Path) -> dict[str, dict[str, str]]:
    lines = source.read_text(encoding="utf-8").splitlines()
    seen: set[str] = set()
    before: dict[str, str] = {}
    result: list[str] = []
    for line in lines:
        if "=" not in line or line.lstrip().startswith("#"):
            result.append(line)
            continue
        key, value = line.split("=", 1)
        if key in PROPERTY_DELTA:
            before[key] = value
            result.append(f"{key}={PROPERTY_DELTA[key]}")
            seen.add(key)
        else:
            result.append(line)
    for key, value in PROPERTY_DELTA.items():
        if key not in seen:
            before[key] = "<absent>"
            result.append(f"{key}={value}")
    output.write_text("\n".join(result) + "\n", encoding="utf-8")
    return {
        key: {"before": before[key], "after": value}
        for key, value in PROPERTY_DELTA.items()
    }


def debugfs(image: Path, command: str, *, capture: bool = False) -> str:
    return run(
        ["debugfs", "-w", "-R", command, str(image)],
        capture=capture,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vendor", type=Path, default=DEFAULT_VENDOR)
    parser.add_argument("--mali", type=Path, default=DEFAULT_MALI)
    parser.add_argument("--product", type=Path, default=DEFAULT_PRODUCT)
    parser.add_argument("--avbtool", type=Path, default=DEFAULT_AVBTOOL)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    providers = {
        "/lib64/egl/libGLES_mali.so": args.mali,
        "/lib64/hw/android.hardware.graphics.mapper@2.0-impl-2.1.so": (
            args.product
            / "system/vendor/lib64/hw/"
            "android.hardware.graphics.mapper@2.0-impl-2.1.so"
        ),
        "/lib64/hw/gralloc.apollo.so": (
            args.product / "system/vendor/lib64/hw/gralloc.apollo.so"
        ),
    }
    for path in [args.vendor, args.avbtool, *providers.values()]:
        if not path.is_file():
            raise RuntimeError(f"required input is absent: {path}")
    if args.vendor.stat().st_size != PARTITION_BYTES:
        raise RuntimeError("frozen r4 vendor extent size changed")
    if digest(args.vendor) != VENDOR_SHA256:
        raise RuntimeError("frozen r4 vendor bytes changed")
    config = json.loads(
        (REPO / "configs/candidates/a16-prototype-b-r1.json").read_text(
            encoding="utf-8"
        )
    )
    expected_provider_hashes = {
        "/lib64/egl/libGLES_mali.so": config["arm64_mali_intake"]["sha256"],
        "/lib64/hw/android.hardware.graphics.mapper@2.0-impl-2.1.so": (
            config["generated_arm64_providers"]["mapper"]["sha256"]
        ),
        "/lib64/hw/gralloc.apollo.so": (
            config["generated_arm64_providers"]["gralloc"]["sha256"]
        ),
    }
    for internal, source in providers.items():
        if digest(source) != expected_provider_hashes[internal]:
            raise RuntimeError(f"provider identity mismatch: {internal}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="a16-b1-vendor-fit-", dir=args.output.parent
    ) as raw_tmp:
        tmp = Path(raw_tmp)
        image = tmp / "vendor-staged.img"
        shutil.copyfile(args.vendor, image)
        before = ext4_fields(image)
        run(["python3", str(args.avbtool), "erase_footer", "--image", str(image)])
        if image.stat().st_size != ORIGINAL_FS_BYTES:
            raise RuntimeError("r4 vendor AVB original-image size changed")
        run(["e2fsck", "-fy", str(image)])
        # Create bounded temporary headroom solely to measure the minimum ext4
        # representation. The accepted LP geometry is never modified.
        run(["resize2fs", str(image), "40000"])

        build_prop = tmp / "build.prop"
        debugfs(image, f"dump -p /build.prop {build_prop}")
        staged_prop = tmp / "build.prop.b1"
        property_delta = replace_properties(build_prop, staged_prop)
        actual_before = {
            key: values["before"] for key, values in property_delta.items()
        }
        if actual_before != PROPERTY_BEFORE:
            raise RuntimeError(
                f"frozen vendor property contract changed: {actual_before}"
            )
        debugfs(image, "rm /build.prop")
        debugfs(image, f"write {staged_prop} /build.prop")
        debugfs(image, "set_inode_field /build.prop mode 0100600")
        debugfs(image, 'ea_set /build.prop security.selinux "u:object_r:vendor_file:s0\\000"')

        for directory, label in (
            ("/lib64", "u:object_r:vendor_file:s0\\000"),
            ("/lib64/egl", "u:object_r:same_process_hal_file:s0\\000"),
            ("/lib64/hw", "u:object_r:vendor_hal_file:s0\\000"),
        ):
            debugfs(image, f"mkdir {directory}")
            debugfs(image, f'ea_set {directory} security.selinux "{label}"')
        for internal, source in providers.items():
            debugfs(image, f"write {source} {internal}")
            debugfs(image, f"set_inode_field {internal} mode 0100644")
            debugfs(
                image,
                f'ea_set {internal} security.selinux '
                '"u:object_r:same_process_hal_file:s0\\000"',
            )

        staged_properties = debugfs(image, "cat /build.prop", capture=True)
        for key, value in PROPERTY_DELTA.items():
            if f"{key}={value}" not in staged_properties.splitlines():
                raise RuntimeError(f"staged vendor property is absent: {key}={value}")
        for preserved in ("ro.board.platform=apollo", "ro.vndk.version=31"):
            if preserved not in staged_properties.splitlines():
                raise RuntimeError(f"preserved vendor property is absent: {preserved}")
        for index, (internal, source) in enumerate(providers.items()):
            verified = tmp / f"provider-{index}.so"
            debugfs(image, f"dump {internal} {verified}")
            if verified.stat().st_size != source.stat().st_size:
                raise RuntimeError(f"staged provider size changed: {internal}")
            if digest(verified) != digest(source):
                raise RuntimeError(f"staged provider bytes changed: {internal}")
            label = debugfs(image, f"ea_list {internal}", capture=True)
            if "u:object_r:same_process_hal_file:s0" not in label:
                raise RuntimeError(f"staged provider label is wrong: {internal}")

        run(["e2fsck", "-fy", str(image)])
        run(["resize2fs", "-M", str(image)])
        run(["e2fsck", "-fn", str(image)])
        staged = ext4_fields(image)
        staged_fs_bytes = staged["block_count"] * staged["block_size"]
        available_fs_bytes = ORIGINAL_FS_BYTES
        overflow = max(0, staged_fs_bytes - available_fs_bytes)
        result = {
            "schema": 1,
            "candidate": "a16-prototype-b-r1",
            "result": "PARTITION_FIT_BLOCKER" if overflow else "PASS",
            "frozen_vendor": {
                "path": str(args.vendor),
                "partition_bytes": PARTITION_BYTES,
                "filesystem_bytes": ORIGINAL_FS_BYTES,
                "sha256": digest(args.vendor),
                "ext4": before,
            },
            "staged_delta": {
                "properties": property_delta,
                "providers": {
                    internal: {
                        "source": str(source),
                        "size": source.stat().st_size,
                        "sha256": digest(source),
                    }
                    for internal, source in providers.items()
                },
                "provider_bytes": sum(path.stat().st_size for path in providers.values()),
            },
            "minimum_ext4": {
                **staged,
                "bytes": staged_fs_bytes,
            },
            "fixed_extent": {
                "available_filesystem_bytes": available_fs_bytes,
                "minimum_filesystem_overflow_bytes": overflow,
                "avb_fec_footer_bytes_reserved": PARTITION_BYTES - ORIGINAL_FS_BYTES,
                "note": (
                    "Overflow is established before AVB regeneration; the fixed extent "
                    "therefore cannot contain this staged filesystem plus its required "
                    "vendor hashtree/FEC/footer."
                ),
            },
        }
        args.output.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
