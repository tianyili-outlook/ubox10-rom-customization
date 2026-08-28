#!/usr/bin/env python3
"""Fail closed on the Prototype B normal-boot product property source."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess


REPO = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO / "configs/candidates/a16-prototype-b-r5.json"
DEFAULT_AOSP = Path("/work/src/ubox10-a16-ceiling")
ABI_KEYS = (
    "ro.product.product.cpu.abilist",
    "ro.product.product.cpu.abilist32",
    "ro.product.product.cpu.abilist64",
)
DUMPVARS = (
    "TARGET_ARCH", "TARGET_2ND_ARCH", "TARGET_CPU_ABI_LIST",
    "TARGET_CPU_ABI_LIST_32_BIT", "TARGET_CPU_ABI_LIST_64_BIT",
    "TARGET_COPY_OUT_PRODUCT", "PRODUCT_OUT",
)


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


def debugfs(image: Path, command: str) -> str:
    return subprocess.check_output(
        ["debugfs", "-R", command, str(image)],
        text=True, stderr=subprocess.DEVNULL,
    )


def parse_properties(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key] = value
    return result


def parse_dumpvars(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    pattern = re.compile(r"^([A-Z0-9_]+)=(.*)$")
    for line in text.splitlines():
        match = pattern.match(line)
        if not match:
            continue
        parsed = shlex.split(match.group(2), posix=True)
        if len(parsed) != 1:
            raise RuntimeError(f"malformed dumpvars assignment: {line}")
        values[match.group(1)] = parsed[0]
    missing = sorted(set(DUMPVARS) - set(values))
    if missing:
        raise RuntimeError(f"dumpvars output is incomplete: {missing}")
    return values


def run_dumpvars(aosp: Path) -> tuple[dict[str, str], str]:
    env = os.environ.copy()
    env.update({
        "TARGET_PRODUCT": "ubox10_ceiling_arm64",
        "TARGET_BUILD_VARIANT": "userdebug",
        "TARGET_RELEASE": "bp2a",
        "OUT_DIR": "out-ceiling-b1",
        "BUILD_NUMBER": "UBOX10_A16_QPR0_B5",
    })
    command = [
        str(aosp / "build/soong/soong_ui.bash"), "--dumpvars-mode",
        "--vars=" + " ".join(DUMPVARS), "--var-prefix=",
    ]
    output = subprocess.check_output(command, cwd=aosp, env=env, text=True)
    return parse_dumpvars(output), output


def expected_from_build_variables(
    contract: dict[str, object], variables: dict[str, str]
) -> dict[str, str]:
    mapping = contract["must_equal_build_variables"]
    assert isinstance(mapping, dict)
    expected = {name: variables[str(variable)] for name, variable in mapping.items()}
    configured = contract["properties"]
    if expected != configured:
        raise RuntimeError(
            f"configured ABI triplet diverges from final build variables: "
            f"configured={configured}, final={expected}"
        )
    merged = expected[ABI_KEYS[2]]
    if expected[ABI_KEYS[1]]:
        merged += ("," if merged else "") + expected[ABI_KEYS[1]]
    if merged != expected[ABI_KEYS[0]]:
        raise RuntimeError("final build-variable ABI lists are not canonical 64-then-32")
    return expected


def audit(
    config_path: Path, aosp: Path, system: Path, inactive_product: Path,
    dumpvars_text: str | None = None,
) -> dict[str, object]:
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    contract = cfg["active_product_property_contract"]
    root = debugfs(system, "stat /product")
    expected_root = contract["root_object"]
    if (
        "Type: symlink" not in root
        or f'Fast link dest: "{expected_root["target"]}"' not in root
        or "Mode:  0644" not in root
        or "User:     0   Group:     0" not in root
    ):
        raise RuntimeError("signed system root /product is not the locked runtime alias")
    root_xattr = debugfs(system, "ea_list /product")
    if expected_root["selinux"] not in root_xattr:
        raise RuntimeError("signed root /product SELinux contract changed")

    skip_text = debugfs(system, f'cat {cfg["skip_mount_contract"]["path"]}')
    if (
        len(skip_text.encode()) != cfg["skip_mount_contract"]["size"]
        or digest_bytes(skip_text.encode()) != cfg["skip_mount_contract"]["sha256"]
        or cfg["skip_mount_contract"]["required_pattern"] not in skip_text.splitlines()
    ):
        raise RuntimeError("signed skip_mount.cfg no longer removes standalone /product")

    active_path = str(contract["active_path"])
    active_text = debugfs(system, f"cat {active_path}")
    active = parse_properties(active_text)
    inactive_text = debugfs(inactive_product, "cat /etc/build.prop")
    inactive = parse_properties(inactive_text)
    if any(key in inactive for key in ABI_KEYS):
        raise RuntimeError("inactive logical product_a still carries the ABI triplet")

    if dumpvars_text is None:
        variables, dumpvars_text = run_dumpvars(aosp)
    else:
        variables = parse_dumpvars(dumpvars_text)
    expected = expected_from_build_variables(contract, variables)
    if variables["TARGET_COPY_OUT_PRODUCT"] != "system/product":
        raise RuntimeError("final product no longer installs product content in system/product")
    if {key: active.get(key) for key in ABI_KEYS} != expected:
        raise RuntimeError("runtime-active embedded product property source is not canonical")

    generated = Path(str(contract["generated_path"]))
    generated_props = parse_properties(generated.read_text(encoding="utf-8"))
    if {key: generated_props.get(key) for key in ABI_KEYS} != expected:
        raise RuntimeError("source-generated product build.prop diverges from final build variables")
    expected_generated = (
        aosp / variables["PRODUCT_OUT"] / variables["TARGET_COPY_OUT_PRODUCT"]
        / "etc/build.prop"
    ).resolve()
    if generated.resolve() != expected_generated:
        raise RuntimeError(
            f"generated product path is not TARGET_OUT_PRODUCT: "
            f"{generated.resolve()} != {expected_generated}"
        )

    derived = {
        "source": "product",
        "ro.product.cpu.abilist": expected[ABI_KEYS[0]],
        "ro.product.cpu.abilist32": expected[ABI_KEYS[1]],
        "ro.product.cpu.abilist64": expected[ABI_KEYS[2]],
    }
    if derived != contract["expected_global_derivation"]:
        raise RuntimeError("exact-r7 offline global ABI derivation changed")
    return {
        "schema": 1,
        "result": "PASS_ACTIVE_RUNTIME_PRODUCT_SOURCE_AND_EXACT_R7_ABI_DERIVATION",
        "system_image": str(system),
        "inactive_product_image": str(inactive_product),
        "root_product": {"type": "symlink", "target": "/system/product"},
        "skip_mount_product": "PRESENT",
        "active_path": active_path,
        "active_properties": expected,
        "inactive_product_triplet": "ABSENT",
        "final_build_variables": variables,
        "generated_path": str(generated),
        "generated_sha256": digest_bytes(generated.read_bytes()),
        "expected_runtime_global_derivation": derived,
        "guard": "PATCH_LOCATION_EQUALS_RUNTIME_RESOLVED_PROPERTY_SOURCE",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--aosp", type=Path, default=DEFAULT_AOSP)
    parser.add_argument("--system-image", type=Path, required=True)
    parser.add_argument("--inactive-product-image", type=Path, required=True)
    parser.add_argument("--dumpvars-file", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    dumpvars_text = (
        args.dumpvars_file.read_text(encoding="utf-8") if args.dumpvars_file else None
    )
    result = audit(
        args.config, args.aosp, args.system_image, args.inactive_product_image,
        dumpvars_text,
    )
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    print("PASS_ACTIVE_RUNTIME_PRODUCT_SOURCE")
    print(encoded, end="")


if __name__ == "__main__":
    main()
