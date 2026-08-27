#!/usr/bin/env python3
"""Assemble the same bounded Android 16 Prototype B r1 candidate."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid


REPO = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO / "configs/candidates/a16-prototype-b-r1.json"
R4_CONFIG = REPO / "configs/candidates/a16-prototype-a-r4.json"
DEFAULT_AOSP = Path("/work/src/ubox10-a16-ceiling")
CHUNK = 8 * 1024 * 1024
VENDOR_FS_BYTES = 140 * 1024 * 1024

FIT_PATH = REPO / "scripts/audit-a16-prototype-b-r1-vendor-fit.py"
FIT_SPEC = importlib.util.spec_from_file_location("a16_b1_vendor_fit", FIT_PATH)
if FIT_SPEC is None or FIT_SPEC.loader is None:
    raise RuntimeError(f"cannot import vendor staging contract: {FIT_PATH}")
FIT = importlib.util.module_from_spec(FIT_SPEC)
sys.modules[FIT_SPEC.name] = FIT
FIT_SPEC.loader.exec_module(FIT)

PACK_PATH = REPO / "scripts/build-m8-kernel-54302-candidate.py"
PACK_SPEC = importlib.util.spec_from_file_location("m8_pack_helpers", PACK_PATH)
if PACK_SPEC is None or PACK_SPEC.loader is None:
    raise RuntimeError(f"cannot import packaging helpers: {PACK_PATH}")
PACK = importlib.util.module_from_spec(PACK_SPEC)
sys.modules[PACK_SPEC.name] = PACK
PACK_SPEC.loader.exec_module(PACK)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(CHUNK), b""):
            value.update(block)
    return value.hexdigest().upper()


def record(path: Path) -> dict[str, object]:
    return {"path": str(path), "size": path.stat().st_size, "sha256": digest(path)}


def has_avb_footer(path: Path) -> bool:
    if path.stat().st_size < 64:
        return False
    with path.open("rb") as stream:
        stream.seek(-64, os.SEEK_END)
        return stream.read(4) == b"AVBf"


def rewrite_paths(value: object, old: Path, new: Path) -> object:
    if isinstance(value, dict):
        return {key: rewrite_paths(item, old, new) for key, item in value.items()}
    if isinstance(value, list):
        return [rewrite_paths(item, old, new) for item in value]
    if isinstance(value, str):
        return value.replace(str(old), str(new))
    return value


def lpdump_extents(text: str) -> dict[str, list[tuple[int, int]]]:
    result: dict[str, list[tuple[int, int]]] = {}
    name: str | None = None
    in_extents = False
    for line in text.splitlines():
        if line.startswith("  Name: "):
            name = line.split(":", 1)[1].strip()
            result[name] = []
            in_extents = False
        elif name is not None and line == "  Extents:":
            in_extents = True
        elif in_extents:
            match = re.fullmatch(
                r"    (\d+) \.\. (\d+) linear \S+ (\d+)", line
            )
            if match:
                logical_first = int(match.group(1))
                logical_last = int(match.group(2))
                physical_start = int(match.group(3))
                length = logical_last - logical_first + 1
                result[name].append((physical_start, physical_start + length))
            elif line.startswith("------------------------"):
                in_extents = False
    return result


def intervals_size(intervals: list[tuple[int, int]]) -> int:
    return sum(end - start for start, end in intervals)


def interval_contains(intervals: list[tuple[int, int]], target: tuple[int, int]) -> bool:
    return any(start <= target[0] and end >= target[1] for start, end in intervals)


def intervals_overlap(
    left: list[tuple[int, int]], right: list[tuple[int, int]]
) -> bool:
    return any(max(a, c) < min(b, d) for a, b in left for c, d in right)


class Builder:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.cfg = json.loads(args.config.read_text(encoding="utf-8"))
        self.r4 = json.loads(R4_CONFIG.read_text(encoding="utf-8"))
        self.candidate_id = str(self.cfg["id"])
        self.final = REPO / "out/candidates" / self.candidate_id
        self.stage = self.final.parent / f".{self.candidate_id}.staging-{uuid.uuid4().hex}"
        self.log = self.stage / "logs/01-commands.log"
        self.host = args.aosp / "out-ceiling-b1/host/linux-x86/bin"
        self.product = args.aosp / "out-ceiling-b1/target/product/ubox10_ceiling_arm64"
        self.source_system = self.product / "system.img"
        self.avbtool = args.aosp / "external/avb/avbtool.py"
        self.unpack_bootimg = args.aosp / "system/tools/mkbootimg/unpack_bootimg.py"
        self.r4_dir = REPO / "out/candidates/a16-prototype-a-r4"
        self.r4_offline_audit = REPO / str(self.cfg["frozen_r4_offline_audit"]["path"])
        base = Path(str(self.cfg["base_candidate"]["path"]))
        self.base = base if base.is_absolute() else REPO / base
        self.rollback = Path(str(self.r4["rollback"]["path"]))
        self.started = time.time()

    def run(
        self,
        command: list[str],
        *,
        output: Path | None = None,
        allowed: set[int] | None = None,
    ) -> int:
        line = "$ " + subprocess.list2cmdline(command)
        print(line, flush=True)
        self.log.parent.mkdir(parents=True, exist_ok=True)
        with self.log.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")
        destination = output or self.log
        destination.parent.mkdir(parents=True, exist_ok=True)
        mode = "w" if output else "a"
        environment = os.environ.copy()
        environment["PATH"] = f"{self.host}:{environment['PATH']}"
        with destination.open(mode, encoding="utf-8", newline="\n") as stream:
            done = subprocess.run(
                command,
                cwd=REPO,
                env=environment,
                stdout=stream,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
        expected = {0} if allowed is None else allowed
        if done.returncode not in expected:
            raise RuntimeError(f"command failed ({done.returncode}): {command}")
        return done.returncode

    @staticmethod
    def require(path: Path, expected: dict[str, object], label: str) -> dict[str, object]:
        if not path.is_file():
            raise RuntimeError(f"missing {label}: {path}")
        actual = record(path)
        if actual["size"] != expected["size"] or actual["sha256"] != expected["sha256"]:
            raise RuntimeError(f"{label} identity mismatch: {actual}")
        return actual

    def setup(self) -> None:
        if self.final.exists():
            raise RuntimeError(f"refusing to overwrite existing candidate: {self.final}")
        if self.cfg["status"] not in {
            "BUILD_CONTINUATION_AUTHORIZED_144_MIB_VENDOR",
            "OFFLINE_CHECKED_READY_FOR_PHYSICAL_VALIDATION",
            "ROOT_CAUSE_PROVEN_SINGLE_CAUSE_R2_AUTHORIZED",
            "ROOT_CAUSE_PROVEN_SINGLE_CAUSE_R3_AUTHORIZED",
        }:
            raise RuntimeError("B1 storage continuation is not in the authorized pre-pack state")
        fit = self.cfg["partition_fit"]
        if (
            fit["target_partition_bytes"] != 150_994_944
            or fit["frozen_sb_a_maximum_bytes"] != 3_212_836_864
            or fit["sb_a_maximum_size_changed"] is not False
            or fit["other_partition_sizes_or_allocations_changed"] is not False
            or fit["partition_shrink_allowed"] is not False
        ):
            raise RuntimeError("authorized 144 MiB storage geometry contract changed")
        self.stage.mkdir(parents=True)
        self.require(self.base, self.cfg["base_candidate"], "frozen r4 outer image")
        self.require(self.rollback, self.r4["rollback"], "rollback image")
        for name in ("super.raw.img", "boot.fex", "vendor_dlkm_a.img"):
            if not (self.r4_dir / name).is_file():
                raise RuntimeError(f"missing frozen r4 packaging input: {name}")
        self.require(
            self.r4_dir / "boot.fex", self.r4["r3_baseline"]["boot"],
            "frozen r4 boot",
        )
        self.require(
            self.r4_dir / "vendor_dlkm_a.img", self.r4["r3_baseline"]["vendor_dlkm"],
            "frozen r4 vendor_dlkm",
        )
        self.require(
            self.r4_dir / "super.raw.img", self.cfg["frozen_r4_lp"]["super_raw"],
            "frozen r4 raw super",
        )
        for name, spec in self.cfg["frozen_r4_lp"]["logical"].items():
            self.require(self.r4_dir / "candidate-logical" / f"{name}.img", spec, name)
        self.require(
            self.r4_offline_audit, self.cfg["frozen_r4_offline_audit"],
            "frozen r4 offline audit",
        )
        if not self.unpack_bootimg.is_file():
            raise RuntimeError("exact-r7 unpack_bootimg.py is absent")
        evidence = self.stage / "kernel-evidence"
        unpacked = self.stage / "boot-unpacked"
        self.run([
            sys.executable, str(self.unpack_bootimg), "--boot_img",
            str(self.r4_dir / "boot.fex"), "--out", str(unpacked),
            "--format=mkbootimg",
        ], output=self.stage / "unpack-frozen-boot.log")
        evidence.mkdir()
        kernel = evidence / "Image"
        shutil.copyfile(unpacked / "kernel", kernel)
        self.require(
            kernel, self.r4["kernel_build"]["image"],
            "kernel extracted from frozen r4 boot",
        )
        shutil.rmtree(unpacked)
        r4_audit = json.loads(self.r4_offline_audit.read_text(encoding="utf-8"))
        inherited = r4_audit["kernel"]
        hardware = inherited["hardware_and_fmac_addendum"]
        if (
            inherited["result"] != "PASS_WITH_PHYSICAL_VALIDATION_REQUIRED"
            or inherited["release"] != "5.4.302+"
            or inherited["config_contract"] != "path-a"
            or inherited["module_count"] != 22
            or hardware["result"] != "PASS_PATH_A_R5_HARDWARE_AND_FMAC_CONTRACT"
        ):
            raise RuntimeError("frozen r4 kernel/FMAC audit contract changed")
        built = evidence / "build-result"
        built.mkdir()
        tracked_config = REPO / "configs/kernel/m8-kernel-5.4.302/path-a-5.4.302.config"
        shutil.copyfile(tracked_config, built / "built.config")
        if digest(built / "built.config") != inherited["config_sha256"].upper():
            raise RuntimeError("tracked Path-A config differs from frozen r4 audit")
        kernel_audit = {
            "result": inherited["result"],
            "source": {"kernel_release": inherited["release"]},
            "build": {
                "config_contract": inherited["config_contract"],
                "config_sha256": inherited["config_sha256"].upper(),
            },
            "modules": {"count": inherited["module_count"]},
            "provenance": {
                "source": "frozen a16-prototype-a-r4 offline audit",
                "source_sha256": digest(self.r4_offline_audit),
                "kernel_extracted_from_byte_preserved_boot": True,
            },
        }
        (evidence / "offline-audit.json").write_text(
            json.dumps(kernel_audit, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (evidence / "path-a-hardware-audit.json").write_text(
            json.dumps(hardware, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self.require(self.source_system, self.cfg["system_build_output"], "mixed system build")
        manifest = subprocess.check_output(
            ["git", "-C", str(self.args.aosp / ".repo/manifests"), "rev-parse", "HEAD"],
            text=True,
        ).strip()
        if manifest != self.cfg["android16"]["manifest_commit"]:
            raise RuntimeError(f"r7 manifest identity changed: {manifest}")
        for relative, item in self.cfg["tracked_source_inputs"].items():
            tracked = REPO / relative
            installed = self.args.aosp / item["aosp_relative"]
            if digest(tracked) != item["sha256"] or digest(installed) != item["sha256"]:
                raise RuntimeError(f"tracked/AOSP product input mismatch: {relative}")
        gpu = self.cfg["tracked_gpu_source"]
        tree = subprocess.check_output(
            ["git", "-C", str(REPO), "rev-parse", f"HEAD:{gpu['relative']}"], text=True
        ).strip()
        if tree != gpu["git_tree"]:
            raise RuntimeError(f"tracked GPU source tree changed: {tree}")
        if subprocess.run(
            ["diff", "-qr", str(REPO / gpu["relative"]),
             str(self.args.aosp / gpu["aosp_relative"])],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        ).returncode:
            raise RuntimeError("tracked/AOSP GPU source trees differ")
        sepolicy = self.cfg["sepolicy_source"]
        sepolicy_path = self.args.aosp / sepolicy["aosp_relative"]
        if digest(sepolicy_path) != sepolicy["one_line_deferral_sha256"]:
            raise RuntimeError("exact one-line r7 fuseblk deferral changed")
        sepolicy_diff = subprocess.check_output(
            ["git", "-C", str(self.args.aosp / "system/sepolicy"), "diff", "--",
             "private/genfs_contexts"], text=True
        )
        removed = [
            line[1:] for line in sepolicy_diff.splitlines()
            if line.startswith("-") and not line.startswith("---")
        ]
        added = [
            line[1:] for line in sepolicy_diff.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        ]
        if removed != [sepolicy["only_removed_line"]] or added:
            raise RuntimeError("r7 platform sepolicy diff is not the exact one-line deferral")
        for tool in ("lpdump", "lpadd", "lpunpack", "img2simg", "simg2img", "fec"):
            if not (self.host / tool).is_file():
                raise RuntimeError(f"required exact-r7 host tool is absent: {tool}")
        if not self.avbtool.is_file():
            raise RuntimeError("exact-r7 avbtool source is absent")
        self.run(
            [sys.executable, str(REPO / "scripts/check-a16-prototype-b-r1-mali.py")],
            output=self.stage / "mali-intake.json",
        )
        providers = self.provider_sources()
        expected = self.cfg["generated_arm64_providers"]
        self.require(providers["mapper"], expected["mapper"], "ARM64 mapper")
        self.require(providers["gralloc"], expected["gralloc"], "ARM64 gralloc")

    def provider_sources(self) -> dict[str, Path]:
        return {
            "mali": Path(str(self.cfg["arm64_mali_intake"]["path"])),
            "mapper": self.product / (
                "system/vendor/lib64/hw/"
                "android.hardware.graphics.mapper@2.0-impl-2.1.so"
            ),
            "gralloc": self.product / "system/vendor/lib64/hw/gralloc.apollo.so",
        }

    def debugfs(self, image: Path, command: str, *, capture: bool = False) -> str:
        argv = ["debugfs", "-w", "-R", command, str(image)]
        if capture:
            return subprocess.check_output(argv, text=True, stderr=subprocess.STDOUT)
        self.run(argv)
        return ""

    def prepare_system(self) -> tuple[Path, dict[str, object]]:
        system = self.stage / "system_a.img"
        shutil.copyfile(self.source_system, system)
        if has_avb_footer(system):
            self.run([sys.executable, str(self.avbtool), "erase_footer", "--image", str(system)])
        self.run(["e2fsck", "-fy", str(system)], allowed={0, 1})
        self.run(["resize2fs", "-M", str(system)])
        fields = subprocess.check_output(["tune2fs", "-l", str(system)], text=True)
        blocks = int(re.search(r"^Block count:\s+(\d+)$", fields, re.MULTILINE).group(1))
        block_size = int(re.search(r"^Block size:\s+(\d+)$", fields, re.MULTILINE).group(1))
        filesystem_bytes = blocks * block_size
        with system.open("r+b") as stream:
            stream.truncate(filesystem_bytes)
        self.run(["e2fsck", "-fn", str(system)])

        build_prop = self.debugfs(system, "cat /system/build.prop", capture=True)
        required = (
            "ro.build.id=BP2A.250805.034",
            "ro.build.version.sdk=36",
            "ro.build.version.security_patch=2025-08-05",
            "ro.build.version.incremental=UBOX10_A16_QPR0_B1",
            "ro.system.product.cpu.abilist=arm64-v8a,armeabi-v7a,armeabi",
            "ro.system.product.cpu.abilist64=arm64-v8a",
            "ro.system.product.cpu.abilist32=armeabi-v7a,armeabi",
        )
        for line in required:
            if line not in build_prop.splitlines():
                raise RuntimeError(f"mixed system product property missing: {line}")
        for path in (
            "/system/bin/app_process64", "/system/bin/app_process32",
            "/system/bin/linker64", "/system/bin/linker",
            "/system/etc/init/hw/init.zygote64_32.rc",
        ):
            if "Inode:" not in self.debugfs(system, f"stat {path}", capture=True):
                raise RuntimeError(f"mixed system executable missing: {path}")

        soong = json.loads(
            (self.args.aosp / "out-ceiling-b1/soong/soong.ubox10_ceiling_arm64.variables")
            .read_text(encoding="utf-8")
        )
        contract = {
            "DeviceArch": "arm64",
            "DeviceArchVariant": "armv8-a",
            "DeviceCpuVariant": "generic",
            "DeviceAbi": ["arm64-v8a"],
            "DeviceSecondaryArch": "arm",
            "DeviceSecondaryArchVariant": "armv7-a-neon",
            "DeviceSecondaryCpuVariant": "cortex-a15",
            "DeviceSecondaryAbi": ["armeabi-v7a", "armeabi"],
            "Platform_sdk_version": 36,
            "Shipping_api_level": "31",
            "ExtraVndkVersions": ["31"],
            "BuildId": "BP2A.250805.034",
        }
        for key, expected in contract.items():
            if soong.get(key) != expected:
                raise RuntimeError(
                    f"mixed Soong contract mismatch: {key}={soong.get(key)!r}, "
                    f"expected {expected!r}"
                )

        avb = self.cfg["avb"]["system"]
        self.run([
            sys.executable, str(self.avbtool), "add_hashtree_footer",
            "--image", str(system), "--partition_name", "system",
            "--partition_size", str(avb["partition_size"]),
            "--hash_algorithm", "sha256", "--salt", str(avb["salt"]),
            "--do_not_generate_fec",
            "--prop", f"com.ubox10.candidate.id:{self.candidate_id}",
            "--prop", "com.ubox10.avb.fec:none",
            "--key", str(REPO / avb["key_relative"]),
            "--algorithm", avb["algorithm"],
        ])
        if system.stat().st_size != avb["partition_size"]:
            raise RuntimeError("signed system partition size mismatch")
        self.verify_avb_partition(system, "system", avb["key_relative"])
        return system, {
            "source_build": record(self.source_system),
            "candidate": record(system),
            "filesystem_bytes_before_avb": filesystem_bytes,
            "partition_headroom_before_hashtree": avb["partition_size"] - filesystem_bytes,
            "mixed_arm64_arm32_zygote64_32_contract": "PASS",
            "ext4": "PASS",
            "avb_hashtree_no_fec": "PASS",
        }

    def verify_avb_partition(self, image: Path, name: str, key_relative: str | None) -> None:
        view = self.stage / f"{name}-avb-view"
        view.mkdir()
        linked = view / f"{name}.img"
        os.link(image, linked)
        command = [sys.executable, str(self.avbtool), "verify_image", "--image", str(linked)]
        if key_relative:
            command.extend(["--key", str(REPO / key_relative)])
        self.run(command, output=self.stage / f"{name}-avb-verify.log")
        self.run(
            [sys.executable, str(self.avbtool), "info_image", "--image", str(linked)],
            output=self.stage / f"{name}-avb-info.txt",
        )
        linked.unlink()
        view.rmdir()

    def prepare_vendor(self) -> tuple[Path, dict[str, object]]:
        source = self.r4_dir / "candidate-logical/vendor_a.img"
        vendor = self.stage / "vendor_a.img"
        shutil.copyfile(source, vendor)
        if not has_avb_footer(vendor):
            raise RuntimeError("frozen r4 vendor AVB footer is absent")
        self.run([sys.executable, str(self.avbtool), "erase_footer", "--image", str(vendor)])
        if vendor.stat().st_size != 117_104_640:
            raise RuntimeError("frozen vendor original filesystem size changed")
        self.run(["e2fsck", "-fy", str(vendor)], allowed={0, 1})
        self.run(["resize2fs", str(vendor), str(VENDOR_FS_BYTES // 4096)])

        temporary = self.stage / "vendor-build.prop"
        staged = self.stage / "vendor-build.prop.b1"
        self.debugfs(vendor, f"dump -p /build.prop {temporary}")
        property_delta = FIT.replace_properties(temporary, staged)
        if {key: value["before"] for key, value in property_delta.items()} != FIT.PROPERTY_BEFORE:
            raise RuntimeError("frozen vendor property source changed")
        self.debugfs(vendor, "rm /build.prop")
        self.debugfs(vendor, f"write {staged} /build.prop")
        self.debugfs(vendor, "set_inode_field /build.prop mode 0100600")
        self.debugfs(
            vendor, 'ea_set /build.prop security.selinux "u:object_r:vendor_file:s0\\000"'
        )

        for directory, label in (
            ("/lib64", "u:object_r:vendor_file:s0\\000"),
            ("/lib64/egl", "u:object_r:same_process_hal_file:s0\\000"),
            ("/lib64/hw", "u:object_r:vendor_hal_file:s0\\000"),
        ):
            self.debugfs(vendor, f"mkdir {directory}")
            self.debugfs(vendor, f'ea_set {directory} security.selinux "{label}"')
        sources = self.provider_sources()
        destinations = {
            "/lib64/egl/libGLES_mali.so": sources["mali"],
            "/lib64/hw/android.hardware.graphics.mapper@2.0-impl-2.1.so": sources["mapper"],
            "/lib64/hw/gralloc.apollo.so": sources["gralloc"],
        }
        for internal, source_path in destinations.items():
            self.debugfs(vendor, f"write {source_path} {internal}")
            self.debugfs(vendor, f"set_inode_field {internal} mode 0100644")
            self.debugfs(
                vendor,
                f'ea_set {internal} security.selinux '
                '"u:object_r:same_process_hal_file:s0\\000"',
            )
        properties = self.debugfs(vendor, "cat /build.prop", capture=True).splitlines()
        for key, value in FIT.PROPERTY_DELTA.items():
            if f"{key}={value}" not in properties:
                raise RuntimeError(f"staged mixed vendor property missing: {key}")
        for line in ("ro.board.platform=apollo", "ro.vndk.version=31"):
            if line not in properties:
                raise RuntimeError(f"preserved vendor property missing: {line}")
        for index, (internal, source_path) in enumerate(destinations.items()):
            extracted = self.stage / f"vendor-provider-{index}.so"
            self.debugfs(vendor, f"dump {internal} {extracted}")
            if record(extracted)["sha256"] != digest(source_path):
                raise RuntimeError(f"staged provider bytes changed: {internal}")
            label = self.debugfs(vendor, f"ea_list {internal}", capture=True)
            if "u:object_r:same_process_hal_file:s0" not in label:
                raise RuntimeError(f"staged provider label changed: {internal}")

        self.run(["e2fsck", "-fy", str(vendor)], allowed={0, 1})
        self.run(["e2fsck", "-fn", str(vendor)])
        if vendor.stat().st_size != VENDOR_FS_BYTES:
            raise RuntimeError("bounded vendor ext4 size changed")
        avb = self.cfg["avb"]["vendor"]
        self.run([
            sys.executable, str(self.avbtool), "add_hashtree_footer",
            "--image", str(vendor), "--partition_name", "vendor",
            "--partition_size", str(avb["partition_size"]),
            "--hash_algorithm", "sha256", "--salt", avb["salt"],
            "--prop", f"com.android.build.vendor.fingerprint:{avb['fingerprint']}",
            "--prop", f"com.android.build.vendor.os_version:{avb['os_version']}",
        ])
        if vendor.stat().st_size != avb["partition_size"]:
            raise RuntimeError("signed vendor partition size mismatch")
        self.verify_avb_partition(vendor, "vendor", None)
        return vendor, {
            "frozen_r4": record(source),
            "candidate": record(vendor),
            "filesystem_bytes_before_avb": VENDOR_FS_BYTES,
            "partition_headroom_before_hashtree_fec": avb["partition_size"] - VENDOR_FS_BYTES,
            "property_delta": property_delta,
            "providers": {path: record(source_path) for path, source_path in destinations.items()},
            "ext4": "PASS",
            "avb_hashtree_fec": "PASS",
        }

    def make_vbmeta(self, image: Path, partition: str) -> Path:
        avb = self.cfg["avb"][partition]
        output = self.stage / f"vbmeta_{partition}.fex"
        self.run([
            sys.executable, str(self.avbtool), "make_vbmeta_image",
            "--output", str(output), "--key", str(REPO / avb["key_relative"]),
            "--algorithm", avb["algorithm"],
            "--rollback_index", str(avb["rollback_index"]),
            "--rollback_index_location", str(avb["rollback_index_location"]),
            "--include_descriptors_from_image", str(image),
        ])
        view = self.stage / f"vbmeta-{partition}-view"
        view.mkdir()
        os.link(image, view / f"{partition}.img")
        os.link(output, view / f"vbmeta_{partition}.img")
        self.run([
            sys.executable, str(self.avbtool), "verify_image",
            "--image", str(view / f"vbmeta_{partition}.img"),
            "--key", str(REPO / avb["key_relative"]),
        ], output=self.stage / f"vbmeta-{partition}-verify.log")
        self.run([
            sys.executable, str(self.avbtool), "info_image", "--image", str(output)
        ], output=self.stage / f"vbmeta-{partition}-info.txt")
        (view / f"vbmeta_{partition}.img").unlink()
        (view / f"{partition}.img").unlink()
        view.rmdir()
        return output

    def build_super(self, system: Path, vendor: Path) -> tuple[Path, dict[str, object]]:
        source = self.r4_dir / "super.raw.img"
        candidate = self.stage / "super.raw.img"
        self.run(["cp", "--reflink=auto", str(source), str(candidate)])
        geometry = self.r4["super"]
        offset = geometry["system_first_sector"] * geometry["sector_size"]
        expected_size = geometry["system_sector_count"] * geometry["sector_size"]
        if system.stat().st_size != expected_size:
            raise RuntimeError("system image no longer fits exact frozen system_a extent")
        with candidate.open("r+b") as destination, system.open("rb") as payload:
            destination.seek(offset)
            shutil.copyfileobj(payload, destination, CHUNK)
        self.run([
            str(self.host / "lpadd"), "--replace", "--readonly", str(candidate),
            "vendor_a", "sb_a", str(vendor),
        ], output=self.stage / "lpadd-vendor.log")

        old_json = self.stage / "r4-lpdump.json"
        new_json = self.stage / "candidate-lpdump.json"
        old_text = self.stage / "r4-lpdump.txt"
        new_text = self.stage / "candidate-lpdump.txt"
        self.run([str(self.host / "lpdump"), "-j", str(source)], output=old_json)
        self.run([str(self.host / "lpdump"), "-j", str(candidate)], output=new_json)
        self.run([str(self.host / "lpdump"), str(source)], output=old_text)
        self.run([str(self.host / "lpdump"), str(candidate)], output=new_text)
        if digest(old_json) != self.cfg["partition_fit"]["frozen_lpdump_json_sha256"]:
            raise RuntimeError("fresh lpdump of frozen r4 metadata changed")
        metadata = json.loads(new_json.read_text(encoding="utf-8"))
        partitions = {
            item["name"]: int(item.get("size", 0)) for item in metadata["partitions"]
        }
        expected_sizes = {
            "system_a": 1_651_167_232, "vendor_a": 150_994_944,
            "product_a": 272_629_760, "vendor_dlkm_a": 6_680_576,
            "system_b": 0, "vendor_b": 0, "product_b": 0, "vendor_dlkm_b": 0,
        }
        if partitions != expected_sizes:
            raise RuntimeError(f"candidate LP partition sizes changed: {partitions}")
        groups = {item["name"]: int(item.get("maximum_size", 0)) for item in metadata["groups"]}
        if groups != {"default": 0, "sb_a": 3_212_836_864, "sb_b": 3_212_836_864}:
            raise RuntimeError(f"candidate LP group sizes changed: {groups}")
        old_extents = lpdump_extents(old_text.read_text(encoding="utf-8"))
        new_extents = lpdump_extents(new_text.read_text(encoding="utf-8"))
        frozen_contract = {
            name: [tuple(extent) for extent in extents]
            for name, extents in self.cfg["partition_fit"]["frozen_extents_sectors"].items()
        }
        for name, expected in frozen_contract.items():
            if old_extents[name] != expected:
                raise RuntimeError(f"fresh frozen-r4 LP extent differs from contract: {name}")
        candidate_contract = {
            name: [tuple(extent) for extent in extents]
            for name, extents in self.cfg["partition_fit"]["candidate_extents_sectors"].items()
        }
        if new_extents != candidate_contract:
            raise RuntimeError(f"candidate LP extents differ from exact contract: {new_extents}")
        for name in (
            "system_a", "product_a", "vendor_dlkm_a", "system_b", "vendor_b",
            "product_b", "vendor_dlkm_b",
        ):
            if new_extents[name] != old_extents[name]:
                raise RuntimeError(f"forbidden LP extent movement: {name}")
        if intervals_size(new_extents["vendor_a"]) != 150_994_944 // 512:
            raise RuntimeError("candidate vendor extent sector count changed")
        for extent in old_extents["vendor_a"]:
            if not interval_contains(new_extents["vendor_a"], extent):
                raise RuntimeError("candidate vendor growth did not preserve its old allocation")
        other = [
            extent for name in ("system_a", "product_a", "vendor_dlkm_a")
            for extent in old_extents[name]
        ]
        if intervals_overlap(new_extents["vendor_a"], other):
            raise RuntimeError("candidate vendor extent overlaps a preserved partition")
        allocated = sum(partitions.values())
        if allocated != 2_081_472_512:
            raise RuntimeError("candidate sb_a allocation total changed")

        slot1 = self.stage / "candidate-lpdump-slot1.json"
        self.run([str(self.host / "lpdump"), "-s", "1", "-j", str(candidate)], output=slot1)
        if json.loads(slot1.read_text()) != metadata:
            raise RuntimeError("LP metadata slot 0/1 geometry differs")

        sparse = self.stage / "super.fex"
        roundtrip = self.stage / "super-sparse-roundtrip.raw.img"
        self.run([str(self.host / "img2simg"), str(candidate), str(sparse), "4096"])
        self.run([str(self.host / "simg2img"), str(sparse), str(roundtrip)])
        if digest(roundtrip) != digest(candidate):
            raise RuntimeError("super sparse/raw round trip changed bytes")
        extracted = self.stage / "candidate-logical"
        extracted.mkdir()
        self.run([str(self.host / "lpunpack"), str(roundtrip), str(extracted)])
        expected_changed = {"system_a": system, "vendor_a": vendor}
        logical: dict[str, dict[str, object]] = {}
        for name, expected in expected_changed.items():
            path = extracted / f"{name}.img"
            if digest(path) != digest(expected):
                raise RuntimeError(f"candidate super changed {name} bytes")
            logical[name] = record(path)
        for name in ("product_a", "vendor_dlkm_a"):
            path = extracted / f"{name}.img"
            self.require(path, self.r4["accepted"]["logical"][name], f"preserved {name}")
            logical[name] = record(path)
        for name in ("system_b", "vendor_b", "product_b", "vendor_dlkm_b"):
            path = extracted / f"{name}.img"
            if path.stat().st_size != 0:
                raise RuntimeError(f"B-slot logical allocation is no longer empty: {name}")
            logical[name] = record(path)
        return sparse, {
            "frozen_raw": record(source),
            "candidate_raw": record(candidate),
            "candidate_sparse": record(sparse),
            "metadata_version": "10.2",
            "metadata_slots": 3,
            "metadata_slots_0_and_1_exact": True,
            "sb_a_maximum_bytes": 3_212_836_864,
            "sb_a_allocated_bytes": allocated,
            "sb_a_unallocated_bytes": 1_131_364_352,
            "vendor_a_bytes": 150_994_944,
            "vendor_growth_bytes": 31_928_320,
            "growth_only_from_old_unallocated_space": True,
            "all_other_partition_extents_exact_r4": True,
            "no_partition_shrunk": True,
            "b_slot_allocations_empty_exact": True,
            "sparse_roundtrip_exact": True,
            "logical": logical,
        }

    def pack_outer(
        self, super_sparse: Path, vbmeta_system: Path, vbmeta_vendor: Path
    ) -> tuple[Path, dict[str, object]]:
        before = PACK.outer_payloads(self.base)
        firmware = self.stage / f"x12-{self.candidate_id}.img"
        payload_audit = self.stage / "outer-payload-audit.json"
        self.run([
            sys.executable, str(REPO / "tools/pack_image_preserving.py"),
            "--source", str(self.base), "--output", str(firmware),
            "--replace", f"super.fex={super_sparse}",
            "--replace", f"vbmeta_system.fex={vbmeta_system}",
            "--replace", f"vbmeta_vendor.fex={vbmeta_vendor}",
            "--audit", str(payload_audit),
        ])
        self.run([
            sys.executable, str(REPO / "tools/sunxi_image_tool.py"), "verify", str(firmware)
        ], output=self.stage / "candidate-outer-verify.log")
        after = PACK.outer_payloads(firmware)
        if set(before) != set(after) or len(after) != 50:
            raise RuntimeError("outer payload inventory changed")
        changed = sorted(
            name for name in before
            if before[name]["sha256_stored"] != after[name]["sha256_stored"]
        )
        expected = sorted([
            "super.fex", "Vsuper.fex", "vbmeta_system.fex", "Vvbmeta_system.fex",
            "vbmeta_vendor.fex", "Vvbmeta_vendor.fex",
        ])
        if changed != expected:
            raise RuntimeError(f"unexpected outer payload delta: {changed}")
        return firmware, {
            "candidate": record(firmware),
            "entry_count": 50,
            "changed_payloads": changed,
            "preserved_payload_count": 44,
            "all_other_payload_bytes_exact_r4": True,
            "imagewty_verify": "PASS",
            "top_level_vbmeta_byte_preserved": before["vbmeta.fex"] == after["vbmeta.fex"],
            "boot_payload_byte_preserved": before["boot.fex"] == after["boot.fex"],
        }

    def finish(
        self,
        firmware: Path,
        system_audit: dict[str, object],
        vendor_audit: dict[str, object],
        super_audit: dict[str, object],
        outer_audit: dict[str, object],
        vbmeta_system: Path,
        vbmeta_vendor: Path,
    ) -> None:
        self.require(self.base, self.cfg["base_candidate"], "unchanged frozen r4 outer image")
        self.require(self.rollback, self.r4["rollback"], "unchanged rollback image")
        boot = self.stage / "boot.fex"
        vendor_dlkm = self.stage / "vendor_dlkm_a.img"
        shutil.copyfile(self.r4_dir / "boot.fex", boot)
        shutil.copyfile(self.r4_dir / "vendor_dlkm_a.img", vendor_dlkm)
        kernel = self.stage / "kernel-evidence/Image"
        result = {
            "schema": 1,
            "id": self.candidate_id,
            "status": "PACKAGED_AWAITING_FULL_OFFLINE_AUDIT",
            "decision": "PENDING_FULL_OFFLINE_AUDIT",
            "physical_device_actions_performed": False,
            "flash_authorized": False,
            "elapsed_seconds": round(time.time() - self.started, 1),
            "source": {
                "tag": self.cfg["android16"]["tag"],
                "manifest_commit": self.cfg["android16"]["manifest_commit"],
                "build_id": self.cfg["android16"]["build_id"],
                "build_number": self.cfg["android16"]["build_number"],
                "lunch": self.cfg["android16"]["lunch"],
            },
            "firmware": record(firmware),
            "system": system_audit,
            "vendor": vendor_audit,
            "super": super_audit,
            "outer": outer_audit,
            "vbmeta_system": record(vbmeta_system),
            "vbmeta_vendor": record(vbmeta_vendor),
            "boot": {"candidate": record(boot), "byte_preserved_from_r4": True},
            "vendor_dlkm": {
                "candidate": record(vendor_dlkm), "byte_preserved_from_r4": True,
                "module_count": 22,
            },
            "kernel": record(kernel),
            "kernel_rebuilt": False,
            "functional_delta": [
                "ARM64 primary plus ARM32 secondary userspace with zygote64_32",
                "ARM64 Mali, r7 mapper and gralloc.apollo providers",
            ],
            "bounded_storage_consequence": (
                "vendor_a 119066624 -> 150994944 bytes using only frozen sb_a "
                "unallocated space; sb_a maximum and every other partition allocation unchanged"
            ),
            "preserved": [
                "Linux 5.4.302+ Path-A kernel and exact six config additions",
                "all 22 vendor_dlkm modules and AIC FMAC/firmware contract",
                "product_a, all B-slot allocations and every unrelated logical partition",
                "boot, vendor_boot, DT/DTBO, TEE/DRM, factory/security and bootloader",
                "top-level vbmeta, rollback/recovery and 44 unrelated outer payloads",
                "Wi-Fi, Ethernet, audio, remote and HDMI hardware authority",
            ],
        }
        result = rewrite_paths(result, self.stage, self.final)
        (self.stage / "build-result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        sums = []
        for path in sorted(self.stage.iterdir()):
            if path.is_file() and path.name != "SHA256SUMS":
                sums.append(f"{digest(path)}  {path.name}")
        (self.stage / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
        os.replace(self.stage, self.final)

    def execute(self) -> None:
        try:
            self.setup()
            system, system_audit = self.prepare_system()
            vendor, vendor_audit = self.prepare_vendor()
            vbmeta_system = self.make_vbmeta(system, "system")
            vbmeta_vendor = self.make_vbmeta(vendor, "vendor")
            super_sparse, super_audit = self.build_super(system, vendor)
            firmware, outer_audit = self.pack_outer(
                super_sparse, vbmeta_system, vbmeta_vendor
            )
            self.finish(
                firmware, system_audit, vendor_audit, super_audit, outer_audit,
                vbmeta_system, vbmeta_vendor,
            )
        except Exception:
            if self.stage.exists() and not self.args.keep_failed:
                shutil.rmtree(self.stage)
            raise
        print(f"PACKAGED: {self.final}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--aosp", type=Path, default=DEFAULT_AOSP)
    parser.add_argument("--keep-failed", action="store_true")
    Builder(parser.parse_args()).execute()


if __name__ == "__main__":
    main()
