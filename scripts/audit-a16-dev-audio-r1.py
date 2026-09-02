#!/usr/bin/env python3
"""Fail-closed offline audit for the bounded a16-dev-audio-r1 candidate."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile


REPO = Path(__file__).resolve().parents[1]
AOSP = Path("/work/src/ubox10-a16-ceiling")
CANDIDATE = REPO / "out/candidates/a16-dev-audio-r1"
BASE = REPO / "out/candidates/a16-prototype-b-r7-hevc-abi-compat1a-sdr-shadow-fd"
CONFIG = REPO / "configs/candidates/a16-dev-audio-r1.json"
HOST = AOSP / "out-ceiling-b1/host/linux-x86/bin"
AVBTOOL = AOSP / "external/avb/avbtool.py"
KEY = REPO / "tools/testkey_rsa2048.pem"
CHUNK = 8 * 1024 * 1024
VERBOSE_ABORT = "_ZNSt3__122__libcpp_verbose_abortEPKcz"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(CHUNK), b""):
                value.update(block)
        return value.hexdigest().upper()
    except PermissionError:
        # Read-only ext4 audit mounts retain Android ownership/modes.  Use the
        # same privileged read boundary as mount/umount without changing data.
        output = subprocess.check_output(["sudo", "sha256sum", str(path)], text=True)
        return output.split()[0].upper()


def record(path: Path) -> dict[str, object]:
    return {"path": str(path), "size": path.stat().st_size, "sha256": digest(path)}


def symbols(path: Path, undefined: bool) -> set[str]:
    command = ["nm", "-D", "--format=posix"]
    command.append("--undefined-only" if undefined else "--defined-only")
    output = subprocess.check_output([*command, str(path)], text=True)
    result: set[str] = set()
    for line in output.splitlines():
        fields = line.split()
        if len(fields) < 2:
            continue
        if undefined and fields[1] != "U":
            continue
        result.add(fields[0].split("@", 1)[0])
    return result


def elf_contract(path: Path) -> dict[str, object]:
    header = subprocess.check_output(["readelf", "-h", str(path)], text=True)
    notes = subprocess.check_output(["readelf", "-W", "-n", str(path)], text=True)
    dynamic = subprocess.check_output(["readelf", "-W", "-d", str(path)], text=True)
    match = lambda pattern, text: re.search(pattern, text, re.MULTILINE)  # noqa: E731
    build_id = match(r"\bBuild ID:\s*([0-9a-fA-F]+)", notes)
    soname = match(r"\(SONAME\).*\[([^]]+)\]", dynamic)
    elf_class = match(r"^\s*Class:\s*(\S+)", header)
    machine = match(r"^\s*Machine:\s*(.+)$", header)
    return {
        **record(path),
        "elf_class": elf_class.group(1) if elf_class else "UNKNOWN",
        "machine": machine.group(1).strip() if machine else "UNKNOWN",
        "build_id": build_id.group(1).lower() if build_id else None,
        "soname": soname.group(1) if soname else None,
        "dt_needed": re.findall(r"\(NEEDED\).*\[([^]]+)\]", dynamic),
        "strong_import_count": len(symbols(path, True)),
        "strong_export_count": len(symbols(path, False)),
    }


def tree_manifest(root: Path) -> dict[str, tuple[object, ...]]:
    result: dict[str, tuple[object, ...]] = {}
    for current, directories, files in os.walk(root, topdown=True, followlinks=False):
        entries = sorted(directories + files)
        for name in entries:
            path = Path(current) / name
            relative = str(path.relative_to(root))
            info = path.lstat()
            attrs: list[tuple[str, str]] = []
            try:
                for attr in sorted(os.listxattr(path, follow_symlinks=False)):
                    attrs.append((attr, os.getxattr(path, attr, follow_symlinks=False).hex()))
            except OSError:
                pass
            if stat.S_ISREG(info.st_mode):
                payload: object = digest(path)
            elif stat.S_ISLNK(info.st_mode):
                payload = os.readlink(path)
                if name in directories:
                    directories.remove(name)
            else:
                payload = None
            result[relative] = (
                stat.S_IFMT(info.st_mode), stat.S_IMODE(info.st_mode), info.st_uid,
                info.st_gid, info.st_size, payload, tuple(attrs),
            )
    return result


def delta(before: dict[str, tuple[object, ...]], after: dict[str, tuple[object, ...]]) -> dict[str, list[str]]:
    return {
        "added": sorted(set(after) - set(before)),
        "removed": sorted(set(before) - set(after)),
        "changed": sorted(name for name in set(before) & set(after) if before[name] != after[name]),
    }


class Auditor:
    def __init__(self, args: argparse.Namespace) -> None:
        self.candidate = args.candidate.resolve()
        self.base = args.base.resolve()
        self.aosp = args.aosp.resolve()
        self.host = self.aosp / "out-ceiling-b1/host/linux-x86/bin"
        self.cfg = json.loads(args.config.read_text(encoding="utf-8"))
        self.audit = self.candidate / "offline-audit"
        self.mounts = self.audit / "mounts"
        self.root = self.audit / "root"
        self.log = self.audit / "commands.log"
        self.mounted: list[Path] = []

    def run(self, command: list[str], *, output: Path, allowed: set[int] = {0}) -> int:
        line = "$ " + subprocess.list2cmdline(command)
        print(line, flush=True)
        self.log.parent.mkdir(parents=True, exist_ok=True)
        with self.log.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")
        output.parent.mkdir(parents=True, exist_ok=True)
        environment = os.environ.copy()
        environment["PATH"] = f"{self.host}:{environment['PATH']}"
        with output.open("w", encoding="utf-8", newline="\n") as stream:
            done = subprocess.run(
                command, cwd=REPO, env=environment, stdout=stream,
                stderr=subprocess.STDOUT, text=True, check=False,
            )
        if done.returncode not in allowed:
            raise RuntimeError(f"command failed ({done.returncode}): {command}")
        return done.returncode

    def mount(self, name: str, image: Path) -> Path:
        point = self.mounts / name
        point.mkdir(parents=True, exist_ok=True)
        self.run(
            ["sudo", "mount", "-o", "loop,ro,noload", str(image), str(point)],
            output=self.audit / f"mount-{name}.log",
        )
        self.mounted.append(point)
        return point

    def setup_root(self, points: dict[str, Path]) -> None:
        self.root.mkdir(parents=True)
        (self.root / "odm").mkdir()
        links = {
            "system": points["system"] / "system",
            "system_ext": points["system"] / "system/system_ext",
            "vendor": points["vendor"],
            "product": points["product"],
            "vendor_dlkm": points["vendor_dlkm"],
            "apex": self.base / "offline-audit/root/apex",
        }
        for name, target in links.items():
            if not target.exists():
                raise RuntimeError(f"offline root input is absent: {target}")
            os.symlink(target, self.root / name)

    def namespace_closure(self, target: Path) -> dict[str, object]:
        contract = elf_contract(target)
        search = [
            self.root / "apex/com.android.runtime/lib/bionic",
            self.root / "apex/com.android.vndk.v31/lib",
            self.root / "vendor/lib", self.root / "system/lib",
        ]
        providers: dict[str, Path] = {}
        for directory in search:
            if not directory.is_dir():
                continue
            for path in directory.rglob("*.so"):
                if not path.is_file():
                    continue
                providers.setdefault(path.name, path)
        missing_needed: list[str] = []
        exports: set[str] = set()
        resolved: list[dict[str, object]] = []
        for needed in contract["dt_needed"]:
            provider = providers.get(str(needed))
            if provider is None:
                missing_needed.append(str(needed))
                continue
            exports.update(symbols(provider, False))
            resolved.append(record(provider) | {"soname": needed})
        imports = symbols(target, True)
        unmatched = sorted(imports - exports)
        if missing_needed or unmatched:
            raise RuntimeError(
                f"audio ARM32 runtime closure failed: needed={missing_needed}, symbols={unmatched}"
            )
        if VERBOSE_ABORT in imports:
            raise RuntimeError("audio wrapper imports unavailable __libcpp_verbose_abort")
        return {
            "result": "PASS_EXACT_ARM32_VENDOR_VNDK31_NAMESPACE_ZERO_UNMATCHED",
            "strong_import_count": len(imports),
            "unmatched_strong_imports": unmatched,
            "unmatched_count": 0,
            "libcpp_verbose_abort_import": False,
            "missing_dt_needed": missing_needed,
            "providers": resolved,
        }

    def execute(self) -> None:
        if self.audit.exists():
            raise RuntimeError(f"refusing to overwrite audit: {self.audit}")
        self.audit.mkdir(parents=True)
        build_path = self.candidate / "build-result.json"
        build = json.loads(build_path.read_text(encoding="utf-8"))
        if build["status"] != "PACKAGED_AWAITING_FULL_OFFLINE_AUDIT":
            raise RuntimeError("candidate is not in packaged pre-audit state")
        expected_base = self.cfg["base_candidate"]
        base_image = self.base / "x12-a16-prototype-b-r7-hevc-abi-compat1a-sdr-shadow-fd.img"
        base_record = record(base_image)
        if base_record["size"] != expected_base["size"] or base_record["sha256"] != expected_base["sha256"]:
            raise RuntimeError("exact physical compat1a base identity changed")

        images = {
            "system": self.candidate / "system_a.img",
            "vendor": self.candidate / "candidate-logical/vendor_a.img",
            "product": self.candidate / "candidate-logical/product_a.img",
            "vendor_dlkm": self.candidate / "vendor_dlkm_a.img",
        }
        try:
            for name, path in images.items():
                self.run(["e2fsck", "-fn", str(path)], output=self.audit / f"e2fsck-{name}.log")
            self.run(
                [sys.executable, str(REPO / "tools/sunxi_image_tool.py"), "verify",
                 str(self.candidate / "x12-a16-dev-audio-r1.img")],
                output=self.audit / "outer-verify.log",
            )
            avb_view = self.audit / "avb-view"
            avb_view.mkdir()
            for name, path, key in (
                ("system", images["system"], KEY), ("vendor", images["vendor"], None),
                ("vbmeta_system", self.candidate / "vbmeta_system.fex", KEY),
                ("vbmeta_vendor", self.candidate / "vbmeta_vendor.fex", KEY),
            ):
                view = avb_view / f"{name}.img"
                os.link(path, view)
                command = [sys.executable, str(AVBTOOL), "verify_image", "--image", str(view)]
                if key is not None:
                    command += ["--key", str(key)]
                self.run(command, output=self.audit / f"verify-{name}.log")
                self.run(
                    [sys.executable, str(AVBTOOL), "info_image", "--image", str(view)],
                    output=self.audit / f"info-{name}.txt",
                )

            base_lp = self.audit / "compat1a-lpdump.json"
            candidate_lp = self.audit / "candidate-lpdump.json"
            self.run([str(self.host / "lpdump"), "-j", str(self.base / "super.raw.img")], output=base_lp)
            self.run([str(self.host / "lpdump"), "-j", str(self.candidate / "super.raw.img")], output=candidate_lp)
            if json.loads(base_lp.read_text()) != json.loads(candidate_lp.read_text()):
                raise RuntimeError("LP metadata/extents differ from exact compat1a")
            with tempfile.TemporaryDirectory(prefix="ubox-audio-r1-sparse-", dir="/work") as raw_dir:
                raw = Path(raw_dir) / "super.raw.img"
                self.run(
                    [str(self.host / "simg2img"), str(self.candidate / "super.fex"), str(raw)],
                    output=self.audit / "sparse-roundtrip.log",
                )
                if digest(raw) != digest(self.candidate / "super.raw.img"):
                    raise RuntimeError("sparse-to-raw round trip differs")

            points = {name: self.mount(name, path) for name, path in images.items()}
            base_vendor = self.mount("compat1a-vendor", self.base / "vendor_a.img")
            self.setup_root(points)
            vendor_delta = delta(tree_manifest(base_vendor), tree_manifest(points["vendor"]))
            expected_delta = {
                "added": [], "removed": [],
                "changed": ["lib/hw/android.hardware.audio@7.0-impl.so"],
            }
            if vendor_delta != expected_delta:
                raise RuntimeError(f"semantic vendor delta expanded: {vendor_delta}")
            base_system = record(self.base / "system_a.img")
            candidate_system = record(images["system"])
            if base_system["size"] != candidate_system["size"] or base_system["sha256"] != candidate_system["sha256"]:
                raise RuntimeError("compat1a system image changed")

            old = self.candidate / "compat1a-audio-impl.so"
            new = points["vendor"] / "lib/hw/android.hardware.audio@7.0-impl.so"
            old_elf, new_elf = elf_contract(old), elf_contract(new)
            if new_elf["elf_class"] != "ELF32" or new_elf["machine"] != "ARM":
                raise RuntimeError("replacement audio wrapper is not ELF32 ARM")
            for field in ("soname", "dt_needed"):
                if old_elf[field] != new_elf[field]:
                    raise RuntimeError(f"audio wrapper changed {field}")
            old_exports, new_exports = symbols(old, False), symbols(new, False)
            required_exports = {
                "HIDL_FETCH_IDevicesFactory",
                "_ZN7android8hardware5audio4V7_014implementation6Device12getAudioPortERKNS1_6common4V7_09AudioPortENSt3__18functionIFvNS2_6ResultES9_EEE",
                "_ZN7android8hardware5audio4V7_014implementation13PrimaryDevice12getAudioPortERKNS1_6common4V7_09AudioPortENSt3__18functionIFvNS2_6ResultES9_EEE",
            }
            if not required_exports <= old_exports or not required_exports <= new_exports:
                raise RuntimeError("required HIDL audio entry point changed")
            closure = self.namespace_closure(new)

            system_vintf = self.run(
                [str(self.host / "checkvintf"), "--check-one", "--dirmap",
                 f"/system:{self.root / 'system'}"],
                output=self.audit / "vintf-system.log",
            )
            full_command = [
                str(self.host / "checkvintf"), "--check-compat",
                "--dirmap", f"/system:{self.root / 'system'}",
                "--dirmap", f"/system_ext:{self.root / 'system_ext'}",
                "--dirmap", f"/vendor:{self.root / 'vendor'}",
                "--dirmap", f"/product:{self.root / 'product'}",
                "--dirmap", f"/odm:{self.root / 'odm'}",
                "--dirmap", f"/apex:{self.root / 'apex'}",
                "--property", "ro.product.first_api_level=31",
                "--kernel", f"5.4.302:{self.candidate / 'kernel-evidence/build-result/built.config'}",
            ]
            full_vintf = self.run(full_command, output=self.audit / "vintf-full.log", allowed={65})
            full_text = (self.audit / "vintf-full.log").read_text(errors="replace")
            config_errors = re.findall(r"For config (CONFIG_[A-Z0-9_]+)", full_text)
            if (
                "For config CONFIG_NFS_FS, value = y but required n" not in full_text
                or config_errors != ["CONFIG_NFS_FS"]
                or not full_text.rstrip().endswith("INCOMPATIBLE")
            ):
                raise RuntimeError("full VINTF is not the inherited NFS-only exit-65 result")

            disassembly = subprocess.check_output(
                [str(self.aosp / "prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump"),
                 "--triple=thumbv7a-linux-android", "-d", "--demangle", str(new)],
                text=True, errors="replace"
            )
            definition = next(
                (line for line in disassembly.splitlines()
                 if line.startswith("000") and
                 "implementation::Device::getAudioPort(" in line),
                "",
            )
            start = disassembly.find(definition) if definition else -1
            excerpt = disassembly[start:start + 6500] if start >= 0 else ""
            if (
                "cbz" not in excerpt or "#0xa4" not in excerpt
                or not re.search(r"\bmovs\s+r1, #0x4\b", excerpt)
            ):
                raise RuntimeError("null guard is not visible in getAudioPort disassembly")
            (self.audit / "audio-getAudioPort-disassembly.txt").write_text(excerpt)

            preserved: dict[str, object] = {}
            for name, spec in self.cfg["preserved_runtime"].items():
                partition_path = str(spec["path"]).lstrip("/")
                if spec["path"].startswith("/system/"):
                    actual = points["system"] / partition_path
                else:
                    actual = points["vendor"] / partition_path.removeprefix("vendor/")
                item = record(actual)
                if item["size"] != spec["size"] or item["sha256"] != spec["sha256"]:
                    raise RuntimeError(f"preserved compat1a runtime changed: {name}")
                preserved[name] = item | {"partition_path": spec["path"]}

            old_imports, new_imports = symbols(old, True), symbols(new, True)
            result = {
                "schema": 1,
                "candidate": record(self.candidate / "x12-a16-dev-audio-r1.img"),
                "decision": "OFFLINE_CHECKED_READY_FOR_BOUNDED_PHYSICAL_VALIDATION",
                "physical_status": "NOT_YET_VALIDATED",
                "physical_device_actions_performed": False,
                "flash_performed": False,
                "classification": "DEVELOPMENT_AUDIO_COMPATIBILITY_CANDIDATE_NOT_R8_NOT_RELEASE",
                "source_exactness": self.cfg["source_contract"] | {"overlay_state": "PATCHED"},
                "filesystem": {
                    "e2fsck": "PASS_SYSTEM_VENDOR_PRODUCT_VENDOR_DLKM",
                    "system_byte_identical_to_compat1a": True,
                    "system_tree_delta": {"added": [], "removed": [], "changed": []},
                    "vendor_tree_delta": vendor_delta,
                    "semantic_runtime_delta_count": 1,
                },
                "runtime_delta": {
                    "path": "/vendor/lib/hw/android.hardware.audio@7.0-impl.so",
                    "compat1a": old_elf,
                    "audio_r1": new_elf,
                    "dt_needed_preserved": True,
                    "required_hidl_exports_preserved": True,
                    "strong_exports": {
                        "baseline_count": len(old_exports), "candidate_count": len(new_exports),
                        "added": sorted(new_exports - old_exports),
                        "removed": sorted(old_exports - new_exports),
                        "classification": "compiler/header template surface changed; required HIDL entry points preserved",
                    },
                    "strong_imports": {
                        "baseline_count": len(old_imports), "candidate_count": len(new_imports),
                        "added": sorted(new_imports - old_imports),
                        "removed": sorted(old_imports - new_imports),
                    },
                    "namespace_closure": closure,
                    "null_safe_disassembly": "PASS_CBZ_GET_AUDIO_PORT_V7_OFFSET_0XA4_TO_NOT_SUPPORTED",
                    "legacy_fallback_for_malformed_v7": False,
                },
                "preserved_runtime": preserved,
                "avb_lp_outer": {
                    "system_vendor_vbmeta_system_vbmeta_vendor": "PASS",
                    "lp_metadata_and_extents": "EXACT_COMPAT1A",
                    "sparse_raw_roundtrip": "PASS_BYTE_EXACT",
                    "imagewty_outer": "PASS",
                    "boot_kernel_vendor_dlkm_product": "BYTE_IDENTICAL_COMPAT1A",
                },
                "vintf": {
                    "system": "PASS", "system_exit": system_vintf,
                    "full": "NOT_PASS_INHERITED_CONFIG_NFS_FS_MISMATCH_ONLY",
                    "full_exit": full_vintf,
                    "actual": "CONFIG_NFS_FS=y", "required": "CONFIG_NFS_FS=n",
                },
                "architecture": {
                    "identity": "ANDROID_16_API36_ZYGOTE64_32_MIXED_ABI_INHERITED_EXACT_SYSTEM",
                    "canonical_r7": "PASS_FROZEN_UNCHANGED",
                    "gate3": "PASS_WITH_EXPLICIT_USER_WAIVER_CLOSED",
                    "compat1a": "PHYSICAL_PASS_AUTHORIZED_SDR_1080P_YV12_EXPERIMENTAL_NOT_R8",
                    "main10_hdr_afbc_protected_4k": "NOT_PROVEN",
                    "r8": "NOT_AUTHORIZED_NOT_BUILT",
                },
                "limitations": [
                    "No physical device action or flash occurred.",
                    "Physical validation is required before the startup audio crash is called fixed.",
                    "Full VINTF remains exit 65 for the inherited CONFIG_NFS_FS mismatch and is not PASS.",
                    "The rebuild uses the current toolchain over the retained wrapper source generation; non-HIDL template symbol sets differ, while required HIDL entry points and the full DT_NEEDED set are preserved and all imports resolve.",
                ],
            }
            audit_path = self.audit / "offline-audit.json"
            audit_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
            build.update({
                "status": "OFFLINE_CHECKED",
                "decision": result["decision"],
                "physical_status": "NOT_YET_VALIDATED",
                "offline_audit": record(audit_path),
            })
            export_result = {
                "strong_exports_preserved": False,
                "required_hidl_exports_preserved": True,
                "strong_export_surface_classification": "CURRENT_TOOLCHAIN_TEMPLATE_SURFACE_CHANGED_ZERO_REQUIRED_HIDL_EXPORT_LOSS",
            }
            build["runtime_delta"]["audio_impl32"].update(export_result)
            build["vendor"]["replaced"]["audio_impl32"].update(export_result)
            build_path.write_text(json.dumps(build, indent=2, sort_keys=True) + "\n")
            sums = [
                f"{digest(path)}  {path.name}"
                for path in sorted(self.candidate.iterdir())
                if path.is_file() and path.name != "SHA256SUMS"
            ]
            (self.candidate / "SHA256SUMS").write_text("\n".join(sums) + "\n")
        finally:
            for point in reversed(self.mounted):
                subprocess.run(["sudo", "umount", str(point)], check=False)
        print("OFFLINE_CHECKED_READY_FOR_BOUNDED_PHYSICAL_VALIDATION")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=CANDIDATE)
    parser.add_argument("--base", type=Path, default=BASE)
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--aosp", type=Path, default=AOSP)
    Auditor(parser.parse_args()).execute()


if __name__ == "__main__":
    main()
