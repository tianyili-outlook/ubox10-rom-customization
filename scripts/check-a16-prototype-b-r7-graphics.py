#!/usr/bin/env python3
"""Fail-closed mapper/gralloc closure against an exact ARM32/ARM64 SP-HAL namespace."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


CHUNK = 8 * 1024 * 1024
PASS_DECISION = {
    "arm32": "PASS_EXACT_ARM32_MAPPER_GRALLOC_SPHAL_CLOSURE",
    "arm64": "PASS_EXACT_ARM64_MAPPER_GRALLOC_SPHAL_CLOSURE",
}
FAIL_DECISION = {
    "arm32": "FAIL_CLOSED_ARM32_MAPPER_GRALLOC_SPHAL_CLOSURE",
    "arm64": "FAIL_CLOSED_ARM64_MAPPER_GRALLOC_SPHAL_CLOSURE",
}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(CHUNK), b""):
            value.update(block)
    return value.hexdigest().upper()


def elf_metadata(path: Path) -> dict[str, object]:
    header = subprocess.check_output(["readelf", "-h", str(path)], text=True)
    notes = subprocess.check_output(["readelf", "-W", "-n", str(path)], text=True)
    dynamic = subprocess.check_output(["readelf", "-W", "-d", str(path)], text=True)
    build_id = re.search(r"\bBuild ID:\s*([0-9a-fA-F]+)", notes)
    soname = re.search(r"\(SONAME\).*\[([^]]+)\]", dynamic)
    needed = re.findall(r"\(NEEDED\).*\[([^]]+)\]", dynamic)
    elf_class = re.search(r"^\s*Class:\s*(\S+)", header, re.MULTILINE)
    machine = re.search(r"^\s*Machine:\s*(.+)$", header, re.MULTILINE)
    return {
        "path": str(path),
        "size": path.stat().st_size,
        "sha256": digest(path),
        "elf_class": elf_class.group(1) if elf_class else "UNKNOWN",
        "machine": machine.group(1).strip() if machine else "UNKNOWN",
        "build_id": build_id.group(1).lower() if build_id else None,
        "soname": soname.group(1) if soname else None,
        "dt_needed": needed,
    }


def dynamic_symbols(path: Path) -> tuple[set[str], set[str]]:
    undefined: set[str] = set()
    exported: set[str] = set()
    output = subprocess.check_output(
        ["nm", "-D", "--undefined-only", "--format=posix", str(path)], text=True
    )
    for line in output.splitlines():
        fields = line.split()
        if len(fields) >= 2 and fields[1] == "U":
            undefined.add(fields[0].split("@", 1)[0])
    output = subprocess.check_output(
        ["nm", "-D", "--defined-only", "--format=posix", str(path)], text=True
    )
    for line in output.splitlines():
        fields = line.split()
        if len(fields) >= 2:
            exported.add(fields[0].split("@", 1)[0])
    return undefined, exported


def linker_set(text: str, key: str) -> set[str]:
    prefix = key + " = "
    values = [line[len(prefix):] for line in text.splitlines() if line.startswith(prefix)]
    if not values:
        raise RuntimeError(f"linkerconfig key is absent: {key}")
    if len(set(values)) != 1:
        raise RuntimeError(f"linkerconfig key has divergent values: {key}")
    return set(values[0].split(":"))


def inspect(
    path: Path,
    *,
    expected_soname: str,
    expected_export: str,
    default_libs: set[str],
    vndk_libs: set[str],
    system_lib: Path,
    runtime_lib: Path,
    vndk_lib: Path,
    expected_elf_class: str,
    expected_machine: str,
) -> dict[str, object]:
    metadata = elf_metadata(path)
    undefined, own_exports = dynamic_symbols(path)
    providers: list[dict[str, str]] = []
    provider_exports: set[str] = set()
    missing: list[dict[str, str]] = []
    for soname in metadata["dt_needed"]:
        if soname in vndk_libs:
            namespace = "vndk"
            provider = vndk_lib / soname
        elif soname in default_libs:
            namespace = "default"
            runtime = runtime_lib / soname
            provider = runtime if runtime.exists() else system_lib / soname
        else:
            missing.append({"soname": soname, "reason": "NOT_EXPORTED_TO_SPHAL"})
            continue
        if not provider.exists():
            missing.append({"soname": soname, "reason": f"MISSING_IN_{namespace.upper()}"})
            continue
        _, exports = dynamic_symbols(provider)
        provider_exports.update(exports)
        providers.append({
            "soname": soname,
            "namespace": namespace,
            "path": str(provider),
            "size": provider.stat().st_size,
            "sha256": digest(provider),
        })
    unmatched = sorted(undefined - provider_exports)
    failures: list[str] = []
    if (
        metadata["elf_class"] != expected_elf_class
        or metadata["machine"] != expected_machine
    ):
        failures.append("WRONG_ELF_ARCHITECTURE")
    if metadata["soname"] != expected_soname:
        failures.append("WRONG_SONAME")
    if expected_export not in own_exports:
        failures.append("REQUIRED_EXPORT_MISSING")
    if missing:
        failures.append("DT_NEEDED_NAMESPACE_CLOSURE_MISSING")
    if unmatched:
        failures.append("STRONG_SYMBOL_CLOSURE_MISSING")
    return {
        "identity": metadata,
        "required_export": expected_export,
        "required_export_present": expected_export in own_exports,
        "strong_import_count": len(undefined),
        "providers": providers,
        "missing_dependencies": missing,
        "unmatched_strong_imports": unmatched,
        "unmatched_count": len(unmatched),
        "libcpp_verbose_abort_import": "_ZNSt3__122__libcpp_verbose_abortEPKcz" in undefined,
        "result": "PASS" if not failures else "FAIL",
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mapper", type=Path, required=True)
    parser.add_argument("--gralloc", type=Path, required=True)
    parser.add_argument("--architecture", choices=("arm32", "arm64"), default="arm64")
    parser.add_argument("--system-lib", "--system-lib64", dest="system_lib", type=Path, required=True)
    parser.add_argument("--runtime-lib", "--runtime-lib64", dest="runtime_lib", type=Path, required=True)
    parser.add_argument("--vndk-lib", "--vndk-lib64", dest="vndk_lib", type=Path, required=True)
    parser.add_argument("--linker-config", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    linker = args.linker_config.read_text(encoding="utf-8")
    default_libs = linker_set(linker, "namespace.sphal.link.default.shared_libs")
    vndk_libs = linker_set(linker, "namespace.sphal.link.vndk.shared_libs")
    expected = {
        "arm32": {"expected_elf_class": "ELF32", "expected_machine": "ARM"},
        "arm64": {"expected_elf_class": "ELF64", "expected_machine": "AArch64"},
    }[args.architecture]
    shared = {
        "default_libs": default_libs,
        "vndk_libs": vndk_libs,
        "system_lib": args.system_lib,
        "runtime_lib": args.runtime_lib,
        "vndk_lib": args.vndk_lib,
        **expected,
    }
    result = {
        "schema": 1,
        "architecture": args.architecture,
        "mapper": inspect(
            args.mapper,
            expected_soname="android.hardware.graphics.mapper@2.0-impl-2.1.so",
            expected_export="HIDL_FETCH_IMapper",
            **shared,
        ),
        "gralloc": inspect(
            args.gralloc,
            expected_soname="gralloc.apollo.so",
            expected_export="HMI",
            **shared,
        ),
    }
    result["decision"] = (
        PASS_DECISION[args.architecture]
        if result["mapper"]["result"] == result["gralloc"]["result"] == "PASS"
        else FAIL_DECISION[args.architecture]
    )
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    sys.stdout.write(rendered)
    if result["decision"].startswith("FAIL_CLOSED"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
