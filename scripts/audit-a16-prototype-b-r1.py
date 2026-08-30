#!/usr/bin/env python3
"""Fully offline-audit the bounded Android 16 Prototype B r1 candidate."""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


REPO = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE = REPO / "out/candidates/a16-prototype-b-r1"
DEFAULT_CONFIG = REPO / "configs/candidates/a16-prototype-b-r1.json"
DEFAULT_AOSP = Path("/work/src/ubox10-a16-ceiling")

R3_PATH = REPO / "scripts/audit-a16-prototype-a-r3.py"
R3_SPEC = importlib.util.spec_from_file_location("a16_a_r3_auditor", R3_PATH)
if R3_SPEC is None or R3_SPEC.loader is None:
    raise RuntimeError(f"cannot import r3 auditor: {R3_PATH}")
R3 = importlib.util.module_from_spec(R3_SPEC)
sys.modules[R3_SPEC.name] = R3
R3_SPEC.loader.exec_module(R3)

R4_PATH = REPO / "scripts/audit-a16-prototype-a-r4.py"
R4_SPEC = importlib.util.spec_from_file_location("a16_a_r4_auditor", R4_PATH)
if R4_SPEC is None or R4_SPEC.loader is None:
    raise RuntimeError(f"cannot import r4 auditor: {R4_PATH}")
R4 = importlib.util.module_from_spec(R4_SPEC)
sys.modules[R4_SPEC.name] = R4
R4_SPEC.loader.exec_module(R4)

BUILD_PATH = REPO / "scripts/build-a16-prototype-b-r1-candidate.py"
BUILD_SPEC = importlib.util.spec_from_file_location("a16_b_r1_builder", BUILD_PATH)
if BUILD_SPEC is None or BUILD_SPEC.loader is None:
    raise RuntimeError(f"cannot import B r1 builder helpers: {BUILD_PATH}")
BUILD = importlib.util.module_from_spec(BUILD_SPEC)
sys.modules[BUILD_SPEC.name] = BUILD
BUILD_SPEC.loader.exec_module(BUILD)


def exact_property(text: str, name: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith(name + "=")]


def parse_dynamic_symbols(output: str) -> tuple[set[str], set[str]]:
    undefined: set[str] = set()
    exported: set[str] = set()
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 8 or not parts[0].endswith(":") or not parts[0][:-1].isdigit():
            continue
        if parts[-1].startswith("(") and parts[-1].endswith(")"):
            parts.pop()
        # The ELF type may be rendered as the three-token "<OS specific>: 10"
        # for AArch64 IFUNC exports. Bind, visibility, index and name are the
        # stable four trailing columns for both standard and OS-specific types.
        bind, index, name = parts[-4], parts[-2], parts[-1].split("@", 1)[0]
        if not name:
            continue
        if index == "UND" and bind == "GLOBAL":
            undefined.add(name)
        elif index != "UND" and bind in {"GLOBAL", "WEAK"}:
            exported.add(name)
    return undefined, exported


def dynamic_symbols(path: Path) -> tuple[set[str], set[str]]:
    output = subprocess.check_output(
        ["sudo", "readelf", "-W", "--dyn-syms", str(path)], text=True
    )
    return parse_dynamic_symbols(output)


def load_candidate_contract(path: Path) -> dict[str, object]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    inherited = raw.get("inherits")
    if inherited is None:
        return raw
    inherited_path = Path(str(inherited))
    if not inherited_path.is_absolute():
        inherited_path = REPO / inherited_path
    merged = json.loads(inherited_path.read_text(encoding="utf-8"))
    merged.update({
        "id": raw["id"],
        "milestone": raw["milestone"],
        "status": raw["status"],
        "base_candidate": raw["base_candidate"],
        "outer_delta": raw["outer_delta"],
        "root_cause": raw["root_cause"],
        "root_mountpoint_contract": raw["root_mountpoint_contract"],
        "_continuation": raw,
    })
    merged["avb"] = dict(merged["avb"])
    merged["avb"]["system"] = raw["avb_system"]
    return merged


class Auditor(R3.Auditor):
    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__(args)
        self.cfg = load_candidate_contract(args.config)
        self.r4_config = json.loads(
            (REPO / "configs/candidates/a16-prototype-a-r4.json").read_text(
                encoding="utf-8"
            )
        )
        self.host = args.aosp / "out-ceiling-b1/host/linux-x86/bin"
        self.avbtool = args.aosp / "external/avb/avbtool.py"
        self.r4_vendor_mount = self.mounts / "r4-vendor"
        self.r1_system_mount = self.mounts / "r1-system"
        self.kernel_evidence = self.candidate / "kernel-evidence"
        if self.cfg["id"] not in {
            "a16-prototype-b-r1",
            "a16-prototype-b-r2",
            "a16-prototype-b-r3",
            "a16-prototype-b-r4",
            "a16-prototype-b-r5",
            "a16-prototype-b-r6",
            "a16-prototype-b-r7",
            "a16-prototype-b-r7-diag1",
            "a16-prototype-b-r7-diag1a",
            "a16-prototype-b-r7-diag2-hevc-crop",
            "a16-prototype-b-r7-diag3-private-buffer-metadata",
        }:
            raise RuntimeError("Prototype B auditor received the wrong contract")
        if self.build_result["id"] != self.cfg["id"]:
            raise RuntimeError("candidate/build contract ID mismatch")

    def mount_r4_vendor(self) -> None:
        source = REPO / "out/candidates/a16-prototype-a-r4/candidate-logical/vendor_a.img"
        expected = self.r4_config["accepted"]["logical"]["vendor_a"]
        actual = R3.record(source)
        if actual["size"] != expected["size"] or actual["sha256"] != expected["sha256"]:
            raise RuntimeError("frozen r4 vendor identity changed")
        self.r4_vendor_mount.mkdir(parents=True, exist_ok=True)
        self.run(["sudo", "mount", "-o", "loop,ro,noload", str(source), str(self.r4_vendor_mount)])
        self.mounted.append(self.r4_vendor_mount)

    def audit_apex(self) -> dict[str, object]:
        apex_dirs = {
            "system": self.root / "system/apex",
            "system_ext": self.root / "system_ext/apex",
            "product": self.root / "product/apex",
            "vendor": self.root / "vendor/apex",
            "odm": self.root / "odm/apex",
        }
        apex_files = sorted(
            path for directory in apex_dirs.values()
            for path in (directory.iterdir() if directory.is_dir() else ())
            if path.suffix in {".apex", ".capex"}
        )
        if not apex_files:
            raise RuntimeError("candidate contains no installed APEX files")
        command = [
            str(self.host / "host_apex_verifier"),
            "--deapexer", str(self.host / "deapexer"),
            "--debugfs", str(self.host / "debugfs_static"),
            "--fsckerofs", str(self.host / "fsck.erofs"),
            "--sdk_version", "36",
        ]
        for partition, path in apex_dirs.items():
            if path.is_dir():
                command.extend([f"--out_{partition}", str(path)])
        self.run(command, output=self.audit / "host-apex-verifier.log")
        activation = self.root / "apex"
        shutil.rmtree(activation)
        activation.mkdir()
        info = activation / "apex-info-list.xml"
        self.run([
            str(self.host / "apexd_host"), "--apex_path", str(activation),
            "--system_path", str(self.root / "system"),
            "--system_ext_path", str(self.root / "system_ext"),
            "--product_path", str(self.root / "product"),
            "--vendor_path", str(self.root / "vendor"),
            "--odm_path", str(self.root / "odm"),
        ], output=self.audit / "apexd-host.log")
        import xml.etree.ElementTree as ET
        apex_infos = ET.parse(info).getroot().findall("apex-info")
        if len(apex_infos) != len(apex_files):
            raise RuntimeError("activated APEX count differs from installed APEX count")
        names = sorted(item.attrib["moduleName"] for item in apex_infos)
        for required in ("com.android.runtime", "com.android.vndk.v31"):
            if required not in names or not (self.root / "apex" / required).is_dir():
                raise RuntimeError(f"required bootstrap APEX missing: {required}")
        routes = list((self.root / "apex/com.android.vndk.v31").rglob("libaudioroute.so"))
        architectures: dict[str, str] = {}
        for path in routes:
            header = subprocess.check_output(["readelf", "-h", str(path)], text=True)
            if "Class:                             ELF64" in header and "AArch64" in header:
                architectures["arm64"] = str(path.relative_to(self.root))
            elif "Class:                             ELF32" in header and "ARM" in header:
                architectures["arm"] = str(path.relative_to(self.root))
        if set(architectures) != {"arm", "arm64"}:
            raise RuntimeError(f"VNDK31 libaudioroute both-arch closure failed: {architectures}")
        return {
            "installed_count": len(apex_files),
            "activated_count": len(apex_infos),
            "installed_names": names,
            "host_apex_verifier_all": "PASS",
            "payload_filesystems_and_init_rc": "PASS",
            "runtime_apex": "PASS",
            "vndk31_apex": "PASS",
            "vndk31_libaudioroute_both_arch": architectures,
            "apex_info_list": R3.record(info),
        }

    def audit_vintf_linker_selinux(self) -> dict[str, object]:
        result = super().audit_vintf_linker_selinux()
        linker = (self.audit / "linker-generated/ld.config.txt").read_text(encoding="utf-8")
        required = (
            "namespace.sphal.search.paths = /odm/${LIB}",
            "namespace.sphal.search.paths += /vendor/${LIB}",
            "namespace.sphal.search.paths += /vendor/${LIB}/egl",
            "namespace.sphal.search.paths += /vendor/${LIB}/hw",
            "namespace.sphal.links = default,rs,vndk",
            "android.hardware.graphics.common@1.0.so",
            "libnativewindow.so",
            "libcutils.so",
            "libc++.so",
        )
        for fragment in required:
            if fragment not in linker:
                raise RuntimeError(f"mixed linker/SP-HAL contract missing: {fragment}")
        result["linkerconfig_mixed_lib_expansion"] = "PASS_${LIB}_ARM_AND_ARM64"
        result["arm64_sphal_search_and_nine_needed_visibility"] = "PASS"
        return result

    def audit_mali_symbols(self) -> dict[str, object]:
        mali = self.root / "vendor/lib64/egl/libGLES_mali.so"
        dynamic = subprocess.check_output(["sudo", "readelf", "-W", "-d", str(mali)], text=True)
        needed = re.findall(r"\(NEEDED\).*\[([^]]+)\]", dynamic)
        expected = self.cfg["arm64_mali_intake"]["dt_needed"]
        if needed != expected:
            raise RuntimeError(f"final Mali DT_NEEDED changed: {needed}")
        undefined, _ = dynamic_symbols(mali)
        if len(undefined) != self.cfg["arm64_mali_intake"]["b0_unique_strong_imports"]:
            raise RuntimeError(f"final Mali strong import count changed: {len(undefined)}")
        exports: set[str] = set()
        providers: dict[str, list[str]] = {}
        for soname in needed:
            output = subprocess.check_output([
                "sudo", "find", "-L", str(self.root / "system"),
                str(self.root / "system_ext"), str(self.root / "vendor"),
                str(self.root / "product"), str(self.root / "apex"),
                "-type", "f", "-name", soname, "-print",
            ])
            candidates = []
            for raw in output.splitlines():
                path = Path(os.fsdecode(raw))
                header = subprocess.check_output(
                    ["sudo", "readelf", "-h", str(path)], text=True,
                    stderr=subprocess.DEVNULL,
                )
                if "Class:                             ELF64" not in header or "AArch64" not in header:
                    continue
                candidates.append(str(path.relative_to(self.root)))
                _, symbols = dynamic_symbols(path)
                exports.update(symbols)
            if not candidates:
                raise RuntimeError(f"no final AArch64 provider for Mali dependency: {soname}")
            providers[soname] = sorted(candidates)
        unresolved = sorted(undefined - exports)
        if unresolved:
            raise RuntimeError(f"final Mali strong imports unresolved: {unresolved[:20]}")
        return {
            "dt_needed": needed,
            "unique_strong_imports": len(undefined),
            "unmatched_strong_imports": 0,
            "provider_candidates": providers,
            "result": "PASS_FINAL_IMAGE_ARM64_SPHAL_SYMBOL_CLOSURE",
        }

    def audit_elf(self, images: dict[str, Path]) -> dict[str, object]:
        csv_path = self.audit / "elf-inventory.csv"
        summary = self.audit / "elf-summary.md"
        command = [sys.executable, str(REPO / "scripts/inventory-elf.py")]
        for name, path in images.items():
            command.extend(["--partition", f"{name}={path}"])
        command.extend([
            "--csv", str(csv_path), "--summary", str(summary),
            "--label", f"{self.cfg['id']} mixed exact-board candidate",
        ])
        self.run(command, output=self.audit / "elf-inventory.log")
        rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
        system64 = [row for row in rows if row["partition"] == "system" and row["machine"] == "AArch64"]
        system32 = [row for row in rows if row["partition"] == "system" and row["machine"] == "ARM"]
        vendor64 = {
            row["path"] for row in rows
            if row["partition"] == "vendor" and row["machine"] == "AArch64"
        }
        expected_vendor64 = {
            "/vendor/lib64/egl/libGLES_mali.so",
            "/vendor/lib64/hw/android.hardware.graphics.mapper@2.0-impl-2.1.so",
            "/vendor/lib64/hw/gralloc.apollo.so",
        }
        continuation = self.cfg.get("_continuation", {})
        census_contract = continuation.get("elf_census_contract", {})
        approved_additional_vendor64 = set(
            census_contract.get("approved_additional_vendor64", [])
        )
        expected_vendor64.update(approved_additional_vendor64)
        if vendor64 != expected_vendor64:
            raise RuntimeError(f"final vendor AArch64 provider set changed: {sorted(vendor64)}")
        if not system64 or not system32:
            raise RuntimeError("system image does not contain both ARM64 and ARM32 userspace")
        vendor64_services = [
            row for row in rows
            if row["partition"] == "vendor" and row["path"].startswith("/vendor/bin/")
            and row["machine"] == "AArch64"
            and row["path"] not in approved_additional_vendor64
        ]
        if vendor64_services:
            raise RuntimeError(f"accepted vendor services were converted to ARM64: {vendor64_services}")
        system_paths = {row["path"] for row in rows if row["partition"] == "system"}
        for required in ("/system/bin/app_process64", "/system/bin/app_process32"):
            if required not in system_paths:
                raise RuntimeError(f"mixed zygote executable absent from final image: {required}")
        zygote_rc = subprocess.check_output(
            [
                "debugfs", "-R", "cat /system/etc/init/hw/init.zygote64_32.rc",
                str(images["system"]),
            ],
            text=True, stderr=subprocess.DEVNULL,
        )
        if "import /system/etc/init/hw/init.zygote64.rc" not in zygote_rc:
            raise RuntimeError("final zygote64_32 primary import contract is missing")
        if "service zygote_secondary /system/bin/app_process32" not in zygote_rc:
            raise RuntimeError("final zygote64_32 secondary service contract is missing")
        primary_rc = subprocess.check_output(
            [
                "debugfs", "-R", "cat /system/etc/init/hw/init.zygote64.rc",
                str(images["system"]),
            ],
            text=True, stderr=subprocess.DEVNULL,
        )
        if "service zygote /system/bin/app_process64" not in primary_rc:
            raise RuntimeError("final zygote64 primary service contract is missing")
        build_prop = subprocess.check_output(
            ["debugfs", "-R", "cat /system/build.prop", str(images["system"])],
            text=True, stderr=subprocess.DEVNULL,
        )
        vendor_prop = subprocess.check_output(
            ["debugfs", "-R", "cat /build.prop", str(images["vendor"])],
            text=True, stderr=subprocess.DEVNULL,
        )
        for line in (
            "ro.system.product.cpu.abilist=arm64-v8a,armeabi-v7a,armeabi",
            "ro.system.product.cpu.abilist64=arm64-v8a",
            "ro.system.product.cpu.abilist32=armeabi-v7a,armeabi",
        ):
            if line not in build_prop.splitlines():
                raise RuntimeError(f"final mixed system ABI property missing: {line}")
        for line in (
            "ro.zygote=zygote64_32",
            "ro.vendor.product.cpu.abilist=arm64-v8a,armeabi-v7a,armeabi",
            "ro.vendor.product.cpu.abilist64=arm64-v8a",
            "ro.vendor.product.cpu.abilist32=armeabi-v7a,armeabi",
            "ro.bionic.arch=arm64", "ro.bionic.2nd_arch=arm",
        ):
            if line not in vendor_prop.splitlines():
                raise RuntimeError(f"final mixed vendor ABI property missing: {line}")
        report = summary.read_text(encoding="utf-8")
        if "ELF32 未解析名称：0" not in report or "ELF64 未解析名称：0" not in report:
            raise RuntimeError("mixed ELF name-level dependency closure failed")
        bpf = [row for row in rows if row["machine"] == "BPF"]
        modules = [
            row for row in rows
            if row["partition"] == "vendor_dlkm" and row["path"].endswith(".ko")
        ]
        return {
            "total_elf": len(rows),
            "system_aarch64_objects": len(system64),
            "system_arm_objects": len(system32),
            "primary_architecture": "ARM64/AArch64",
            "secondary_architecture": "ARM32/ARM",
            "zygote": "zygote64_32",
            "app_process64": "present",
            "app_process32": "present",
            "vendor_aarch64_provider_set": sorted(vendor64),
            "vendor_aarch64_services": len(approved_additional_vendor64),
            "vendor_dlkm_modules": len(modules),
            "elf64_bpf_objects": len(bpf),
            "elf64_bpf_classification": "BPF bytecode, not AArch64 userspace",
            "unresolved_elf32_names": 0,
            "unresolved_elf64_names": 0,
            "mali": self.audit_mali_symbols(),
            "result": "PASS_MIXED_ARM64_PRIMARY_ARM32_SECONDARY",
        }

    def audit_avb_lp_outer(self, images: dict[str, Path]) -> dict[str, object]:
        key = REPO / "tools/testkey_rsa2048.pem"
        avb_dir = self.audit / "avb-view"
        avb_dir.mkdir()
        links = {
            "system.img": images["system"], "vendor.img": images["vendor"],
            "vbmeta_system.img": self.candidate / "vbmeta_system.fex",
            "vbmeta_vendor.img": self.candidate / "vbmeta_vendor.fex",
        }
        for name, source in links.items():
            os.link(source, avb_dir / name)
        for name in ("system.img", "vendor.img"):
            command = [sys.executable, str(self.avbtool), "verify_image", "--image", str(avb_dir / name)]
            if name == "system.img":
                command.extend(["--key", str(key)])
            self.run(command, output=self.audit / f"verify-{name}.log")
        for name in ("vbmeta_system.img", "vbmeta_vendor.img"):
            self.run([
                sys.executable, str(self.avbtool), "verify_image", "--image", str(avb_dir / name),
                "--key", str(key),
            ], output=self.audit / f"verify-{name}.log")
        for name in links:
            self.run([
                sys.executable, str(self.avbtool), "info_image", "--image", str(avb_dir / name)
            ], output=self.audit / f"info-{name}.txt")
        if images["system"].stat().st_size != 1_651_167_232:
            raise RuntimeError("final system AVB extent size changed")
        if images["vendor"].stat().st_size != 150_994_944:
            raise RuntimeError("final vendor AVB extent is not exact 144 MiB")
        vendor_info = (self.audit / "info-vendor.img.txt").read_text()
        if "FEC num roots:         2" not in vendor_info or "Partition Name:        vendor" not in vendor_info:
            raise RuntimeError("final vendor AVB/FEC descriptor changed")
        system_info = (self.audit / "info-system.img.txt").read_text()
        if (
            "Partition Name:        system" not in system_info
            or f"Salt:                  {self.cfg['avb']['system']['salt']}" not in system_info
            or "FEC num roots:         0" not in system_info
        ):
            raise RuntimeError("final system AVB descriptor changed")
        vbmeta_system_info = (self.audit / "info-vbmeta_system.img.txt").read_text()
        vbmeta_vendor_info = (self.audit / "info-vbmeta_vendor.img.txt").read_text()
        for text, location, label in (
            (vbmeta_system_info, 1, "system"), (vbmeta_vendor_info, 0, "vendor")
        ):
            if (
                "Rollback Index:           1644019200" not in text
                or f"Rollback Index Location:  {location}" not in text
                or "Algorithm:                SHA256_RSA2048" not in text
            ):
                raise RuntimeError(f"final vbmeta_{label} rollback/signature contract changed")
        for name in links:
            (avb_dir / name).unlink()
        avb_dir.rmdir()

        lpdump = self.candidate / "candidate-lpdump.json"
        metadata = json.loads(lpdump.read_text(encoding="utf-8"))
        detached_lpdump = self.audit / "detached-lpdump.json"
        self.run([
            str(self.host / "lpdump"), "-j", str(self.candidate / "super.raw.img")
        ], output=detached_lpdump)
        if json.loads(detached_lpdump.read_text(encoding="utf-8")) != metadata:
            raise RuntimeError("detached LP metadata differs from build evidence")
        slot1_lpdump = self.audit / "detached-lpdump-slot1.json"
        self.run([
            str(self.host / "lpdump"), "-s", "1", "-j",
            str(self.candidate / "super.raw.img"),
        ], output=slot1_lpdump)
        if json.loads(slot1_lpdump.read_text(encoding="utf-8")) != metadata:
            raise RuntimeError("detached LP metadata slots 0 and 1 differ")
        group = next(item for item in metadata["groups"] if item["name"] == "sb_a")
        partitions = {
            item["name"]: int(item.get("size", 0)) for item in metadata["partitions"]
        }
        if int(group["maximum_size"]) != 3_212_836_864:
            raise RuntimeError("final sb_a maximum changed")
        if partitions["vendor_a"] != 150_994_944:
            raise RuntimeError("final LP vendor size changed")
        for name in ("system_b", "vendor_b", "product_b", "vendor_dlkm_b"):
            if partitions[name] != 0:
                raise RuntimeError(f"final B-slot allocation changed: {name}")
        super_evidence = self.build_result["super"]
        required_flags = (
            "growth_only_from_old_unallocated_space", "all_other_partition_extents_exact_r4",
            "no_partition_shrunk", "b_slot_allocations_empty_exact", "sparse_roundtrip_exact",
        )
        if any(super_evidence.get(name) is not True for name in required_flags):
            raise RuntimeError("builder LP preservation evidence is incomplete")
        outer = self.build_result["outer"]
        default_changed = [
            "super.fex", "Vsuper.fex", "vbmeta_system.fex", "Vvbmeta_system.fex",
            "vbmeta_vendor.fex", "Vvbmeta_vendor.fex",
        ]
        continuation = self.cfg.get("_continuation", {})
        outer_contract = continuation.get("outer_delta", {})
        expected_changed = sorted(outer_contract.get(
            "changed_payloads_from_base",
            outer_contract.get("changed_payloads_from_r1", default_changed),
        ))
        expected_preserved = int(
            outer_contract.get(
                "preserved_payload_count_from_base",
                outer_contract.get("preserved_payload_count_from_r1", 44),
            )
        )
        if (
            outer["changed_payloads"] != expected_changed
            or outer["preserved_payload_count"] != expected_preserved
        ):
            raise RuntimeError("outer changed/preserved inventory changed")
        base_path = Path(str(self.cfg["base_candidate"]["path"]))
        if not base_path.is_absolute():
            base_path = REPO / base_path
        base_outer = BUILD.PACK.outer_payloads(base_path)
        final_outer = BUILD.PACK.outer_payloads(Path(str(self.build_result["firmware"]["path"])))
        detached_changed = sorted(
            name for name in base_outer
            if base_outer[name]["sha256_stored"] != final_outer[name]["sha256_stored"]
        )
        if detached_changed != expected_changed or set(base_outer) != set(final_outer):
            raise RuntimeError(f"detached outer preservation delta changed: {detached_changed}")
        return {
            "system_avb_hashtree": "PASS",
            "vendor_avb_hashtree_fec": "PASS",
            "vbmeta_system_signature_rollback_location_1": "PASS",
            "vbmeta_vendor_signature_rollback_location_0": "PASS",
            "lp_vendor_a_bytes": partitions["vendor_a"],
            "lp_sb_a_maximum_bytes": int(group["maximum_size"]),
            "lp_other_partition_extents": "EXACT_R4",
            "lp_b_slot_allocations": "EMPTY_EXACT_R4",
            "super_sparse_raw_roundtrip": "PASS",
            "outer_changed_payloads": outer["changed_payloads"],
            "outer_preserved_payload_count": outer["preserved_payload_count"],
            "detached_outer_changed_payloads": detached_changed,
            "imagewty": "PASS",
            "result": "PASS",
        }

    @staticmethod
    def inode_contract(image: Path, path: str) -> dict[str, object] | None:
        output = subprocess.check_output(
            ["debugfs", "-R", f"stat {path}", str(image)],
            text=True, stderr=subprocess.STDOUT,
        )
        if "File not found" in output:
            return None
        header = re.search(r"Type:\s+(\w+)\s+Mode:\s+(\d+)", output)
        owner = re.search(r"User:\s+(\d+)\s+Group:\s+(\d+)", output)
        if header is None or owner is None:
            raise RuntimeError(f"cannot parse inode contract for {path}")
        label_match = re.search(r'security\.selinux \(\d+\) = "([^"\\]+)', output)
        if label_match is None:
            attrs = subprocess.check_output(
                ["debugfs", "-R", f"ea_get {path} security.selinux", str(image)],
                text=True, stderr=subprocess.STDOUT,
            )
            label_match = re.search(r'security\.selinux \(\d+\) = "([^"\\]+)', attrs)
        return {
            "type": header.group(1),
            "mode": header.group(2),
            "uid": int(owner.group(1)),
            "gid": int(owner.group(2)),
            "selinux": label_match.group(1) if label_match else None,
        }

    def audit_root_mountpoint_delta(self, images: dict[str, Path]) -> dict[str, object]:
        if self.cfg["id"] == "a16-prototype-b-r1":
            return {"result": "NOT_APPLICABLE_TO_HISTORICAL_R1_OFFLINE_AUDIT"}

        continuation = self.cfg["_continuation"]
        base_spec = continuation["base_artifacts"]["system_a"]
        base_path = Path(str(base_spec["path"]))
        if not base_path.is_absolute():
            base_path = REPO / base_path
        base_record = R3.record(base_path)
        if (
            base_record["size"] != base_spec["size"]
            or base_record["sha256"] != base_spec["sha256"]
        ):
            raise RuntimeError("frozen r1 system identity changed")
        self.r1_system_mount.mkdir(parents=True)
        self.run([
            "sudo", "mount", "-o", "loop,ro,noload", str(base_path),
            str(self.r1_system_mount),
        ])
        self.mounted.append(self.r1_system_mount)

        before = R4.tree_manifest(self.r1_system_mount)
        after = R4.tree_manifest(self.mounts / "system")
        added = sorted(set(after) - set(before))
        removed = sorted(set(before) - set(after))
        changed = sorted(
            name for name in set(before) & set(after) if before[name] != after[name]
        )
        if added != ["metadata"] or removed or changed:
            raise RuntimeError(
                f"r2 system semantic delta expanded: added={added} "
                f"removed={removed} changed={changed}"
            )

        r4_system = REPO / "out/candidates/a16-prototype-a-r4/system_a.img"
        contract = continuation["root_mountpoint_contract"]
        accepted = self.inode_contract(r4_system, "/metadata")
        base_metadata = self.inode_contract(base_path, "/metadata")
        candidate_metadata = self.inode_contract(images["system"], "/metadata")
        expected = {
            "type": contract["type"], "mode": contract["mode"],
            "uid": contract["uid"], "gid": contract["gid"],
            "selinux": contract["selinux"],
        }
        if accepted != expected or base_metadata is not None or candidate_metadata != expected:
            raise RuntimeError(
                "r4/r1/r2 /metadata contract does not prove the single-cause restoration"
            )

        move_mountpoints = {}
        for path in contract["required_move_mountpoints"]:
            r4_value = self.inode_contract(r4_system, path)
            r1_value = self.inode_contract(base_path, path)
            r2_value = self.inode_contract(images["system"], path)
            if path == "/metadata":
                if r4_value != r2_value or r1_value is not None:
                    raise RuntimeError("/metadata is not the sole restored move destination")
            elif r1_value != r4_value or r2_value != r4_value:
                raise RuntimeError(f"switch-root destination contract changed: {path}")
            move_mountpoints[path] = {"r4": r4_value, "r1": r1_value, "r2": r2_value}

        return {
            "result": "PASS_SINGLE_CAUSE_METADATA_ROOT_MOUNTPOINT_RESTORED",
            "r1_system": R3.record(base_path),
            "r2_system": R3.record(images["system"]),
            "tree_delta_from_r1": {"added": added, "removed": removed, "changed": changed},
            "metadata_contract": {"r4": accepted, "r1": base_metadata, "r2": candidate_metadata},
            "move_mountpoints": move_mountpoints,
            "switch_root_new_root": "/system",
            "failing_source_mount": "/metadata",
            "proven_missing_r1_destination": "/system/metadata",
            "first_stage_init_sha256": continuation["root_cause"]["first_stage_init"]["r1_sha256"],
            "result_scope": "OFFLINE ROOT-CAUSE CORRECTION; PHYSICAL BOOT NOT YET VALIDATED",
        }

    def audit_preservation(self, images: dict[str, Path]) -> dict[str, object]:
        preserved = {}
        for name in ("product_a", "vendor_dlkm_a"):
            image = images["product" if name == "product_a" else "vendor_dlkm"]
            expected = self.r4_config["accepted"]["logical"][name]
            actual = R3.record(image)
            if actual["size"] != expected["size"] or actual["sha256"] != expected["sha256"]:
                raise RuntimeError(f"candidate changed frozen {name}")
            preserved[name] = actual
        for name in ("boot", "vendor_dlkm"):
            candidate = self.candidate / ("boot.fex" if name == "boot" else "vendor_dlkm_a.img")
            baseline = REPO / "out/candidates/a16-prototype-a-r4" / candidate.name
            if R3.record(candidate)["sha256"] != R3.record(baseline)["sha256"]:
                raise RuntimeError(f"candidate changed frozen {name}")
            preserved[name] = R3.record(candidate)
        kernel = Path(str(self.build_result["kernel"]["path"]))
        expected_kernel = self.r4_config["kernel_build"]["image"]
        actual_kernel = R3.record(kernel)
        if (
            actual_kernel["size"] != expected_kernel["size"]
            or actual_kernel["sha256"] != expected_kernel["sha256"]
            or self.build_result.get("kernel_rebuilt") is not False
        ):
            raise RuntimeError("candidate changed frozen Path-A kernel")

        before = R4.tree_manifest(self.r4_vendor_mount)
        after = R4.tree_manifest(self.mounts / "vendor")
        added = sorted(set(after) - set(before))
        removed = sorted(set(before) - set(after))
        changed = sorted(name for name in set(before) & set(after) if before[name] != after[name])
        expected_added = sorted([
            "lib64", "lib64/egl", "lib64/egl/libGLES_mali.so", "lib64/hw",
            "lib64/hw/android.hardware.graphics.mapper@2.0-impl-2.1.so",
            "lib64/hw/gralloc.apollo.so",
        ])
        if added != expected_added or removed or changed != ["build.prop"]:
            raise RuntimeError(
                f"vendor semantic tree delta expanded: added={added} removed={removed} changed={changed}"
            )
        rollback = Path(str(self.r4_config["rollback"]["path"]))
        if R3.record(rollback) != self.r4_config["rollback"]:
            raise RuntimeError("rollback image identity changed")
        return {
            "byte_preserved_images": preserved,
            "kernel": actual_kernel,
            "kernel_rebuilt": False,
            "kernel_release": "5.4.302+",
            "path_a_six_configs": "PRESERVED",
            "vendor_dlkm_module_count": 22,
            "aic_fmac_contract": "PRESERVED",
            "vendor_tree_added": added,
            "vendor_tree_changed": changed,
            "vendor_tree_removed": removed,
            "hardware_authority": {
                "Wi-Fi": "UNCHANGED",
                "Ethernet": "UNCHANGED",
                "audio": "UNCHANGED_KNOWN_R4_BOOT_TIME_DEBT",
                "remote": "UNCHANGED",
                "HDMI_display": "UNCHANGED",
                "DT_DTBO_TEE_DRM_vendor_boot": "UNCHANGED",
            },
            "rollback": R3.record(rollback),
            "result": "PASS",
        }

    def finish_b1(
        self,
        images: dict[str, Path],
        apex: dict[str, object],
        compatibility: dict[str, object],
        elf: dict[str, object],
        avb_lp_outer: dict[str, object],
        preservation: dict[str, object],
        root_mountpoint: dict[str, object],
    ) -> None:
        kernel_audit = json.loads(
            (self.kernel_evidence / "offline-audit.json").read_text(encoding="utf-8")
        )
        hardware = json.loads(
            (self.kernel_evidence / "path-a-hardware-audit.json").read_text(encoding="utf-8")
        )
        if hardware.get("result") != "PASS_PATH_A_R5_HARDWARE_AND_FMAC_CONTRACT":
            raise RuntimeError("Path-A hardware/FMAC evidence changed")
        result = {
            "schema": 1,
            "candidate": self.build_result["firmware"],
            "decision": "OFFLINE CHECKED / READY FOR PHYSICAL VALIDATION",
            "physical_status": "NOT_YET_VALIDATED",
            "physical_device_actions_performed": False,
            "flash_authorized": False,
            "filesystem_image_integrity": "PASS",
            "avb_lp_outer": avb_lp_outer,
            "apex": apex,
            "compatibility": compatibility,
            "elf_abi_linker": elf,
            "preservation": preservation,
            "root_mountpoint": root_mountpoint,
            "kernel": {
                "result": kernel_audit["result"],
                "release": kernel_audit["source"]["kernel_release"],
                "config_contract": kernel_audit["build"]["config_contract"],
                "config_sha256": kernel_audit["build"]["config_sha256"],
                "module_count": kernel_audit["modules"]["count"],
                "hardware_and_fmac_addendum": hardware,
            },
            "limitations": [
                "No physical UBOX action occurred or is authorized by this audit.",
                "Mixed zygote, SurfaceFlinger, system_server and graphics runtime behavior is not a physical PASS.",
                "Offline SELinux compilation does not prove enforcing runtime compatibility.",
                "Full VINTF remains incompatible only for inherited CONFIG_NFS_FS=y versus FCM-6 n.",
                "Known r4 boot-time auto-recovered audio failure remains unchanged and unfixed.",
            ],
        }
        audit_path = self.audit / "offline-audit.json"
        audit_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.build_result["status"] = "OFFLINE_CHECKED"
        self.build_result["decision"] = result["decision"]
        self.build_result["physical_status"] = result["physical_status"]
        self.build_result["offline_audit"] = R3.record(audit_path)
        (self.candidate / "build-result.json").write_text(
            json.dumps(self.build_result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        sums = []
        for path in sorted(self.candidate.iterdir()):
            if path.is_file() and path.name != "SHA256SUMS":
                sums.append(f"{R3.digest(path)}  {path.name}")
        (self.candidate / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")

    def execute(self) -> None:
        images = self.setup()
        try:
            self.mount_images(images)
            self.mount_r4_vendor()
            apex = self.audit_apex()
            compatibility = self.audit_vintf_linker_selinux()
            elf = self.audit_elf(images)
            avb_lp_outer = self.audit_avb_lp_outer(images)
            preservation = self.audit_preservation(images)
            root_mountpoint = self.audit_root_mountpoint_delta(images)
        finally:
            for point in reversed(self.mounted):
                self.run(["sudo", "umount", str(point)], allowed={0, 32})
        self.finish_b1(
            images, apex, compatibility, elf, avb_lp_outer, preservation,
            root_mountpoint,
        )
        print("OFFLINE CHECKED / READY FOR PHYSICAL VALIDATION", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--aosp", type=Path, default=DEFAULT_AOSP)
    parser.add_argument("--kernel-evidence", type=Path)
    parser.add_argument("--resume", action="store_true")
    Auditor(parser.parse_args()).execute()


if __name__ == "__main__":
    main()
