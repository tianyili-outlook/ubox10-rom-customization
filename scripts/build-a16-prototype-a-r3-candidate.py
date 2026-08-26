#!/usr/bin/env python3
"""Build one Android 16 QPR0 ARM32/Path-A exact-board r3 candidate."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


REPO = Path(__file__).resolve().parents[1]
BASE_PATH = REPO / "scripts/build-m8-kernel-54302-candidate.py"
SPEC = importlib.util.spec_from_file_location("m8_kernel_54302_candidate", BASE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import candidate builder: {BASE_PATH}")
BASE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = BASE
SPEC.loader.exec_module(BASE)

DEFAULT_CONFIG = REPO / "configs/candidates/a16-prototype-a-r3.json"
DEFAULT_AOSP = Path("/work/src/ubox10-a16-ceiling")
DEFAULT_INTEGRATION = Path("/work/src/ubox10-kernel-5.4.302-common")
CHUNK = 8 * 1024 * 1024


def digest_range(path: Path, offset: int, length: int) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        stream.seek(offset)
        remaining = length
        while remaining:
            block = stream.read(min(CHUNK, remaining))
            if not block:
                raise RuntimeError(f"short range read from {path}")
            value.update(block)
            remaining -= len(block)
    return value.hexdigest().upper()


class R3Builder(BASE.Builder):
    """Reuse the accepted kernel-component builder and replace both LP extents."""

    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__(args)
        self.android = self.cfg["android16"]
        self.source_system = args.aosp / str(self.android["system_relative"])
        self.system: Path | None = None
        self.vbmeta_system: Path | None = None

    def setup(self) -> None:
        build = self.cfg["kernel_build"]
        audit_path = self.evidence / str(build["offline_audit"]["relative"])
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        if "modules" not in build:
            modules = []
            for filename, item in sorted(audit["modules"]["items"].items()):
                path = Path(item["new"]["path"])
                name = subprocess.check_output(
                    ["modinfo", "-F", "name", str(path)], text=True
                ).strip()
                depends = subprocess.check_output(
                    ["modinfo", "-F", "depends", str(path)], text=True
                ).strip()
                modules.append({
                    "file": filename,
                    "name": name,
                    "size": item["new"]["size"],
                    "sha256": item["new"]["sha256"].upper(),
                    "depends": [value for value in depends.split(",") if value],
                })
            build["modules"] = modules
            build["module_count"] = len(modules)
        super().setup()
        self.require(self.source_system, self.android["system"], "r7 source-built system")
        key = REPO / str(self.android["avb"]["key_relative"])
        if BASE.digest(key) != self.android["avb"]["key_sha256"]:
            raise RuntimeError("system AVB key identity mismatch")
        for relative, expected in self.android["tracked_inputs"].items():
            path = REPO / relative
            if BASE.digest(path) != expected:
                raise RuntimeError(f"tracked Android integration input mismatch: {path}")

    def extract_file(self, image: Path, internal: str, output: Path) -> None:
        self.run(["debugfs", "-R", f"dump -p {internal} {output}", str(image)])
        if not output.is_file():
            raise RuntimeError(f"debugfs did not extract {internal}")

    def prepare_system(self) -> tuple[Path, dict[str, object]]:
        system = self.stage / "system_a.img"
        shutil.copyfile(self.source_system, system)
        avbtool = self.aosp_bin / "avbtool"
        self.run([str(avbtool), "erase_footer", "--image", str(system)])
        self.run(["e2fsck", "-fy", str(system)], allowed={0, 1})
        self.run(["resize2fs", "-M", str(system)])
        fields = subprocess.check_output(["tune2fs", "-l", str(system)], text=True)
        values: dict[str, int] = {}
        for line in fields.splitlines():
            if line.startswith("Block count:"):
                values["blocks"] = int(line.split(":", 1)[1])
            elif line.startswith("Block size:"):
                values["block_size"] = int(line.split(":", 1)[1])
        filesystem_size = values["blocks"] * values["block_size"]
        with system.open("r+b") as stream:
            stream.truncate(filesystem_size)
        self.run(["e2fsck", "-fn", str(system)])

        policy = self.stage / "plat_sepolicy.cil"
        matrix = self.stage / "compatibility_matrix.device.xml"
        build_prop = self.stage / "system-build.prop"
        self.extract_file(system, "/system/etc/selinux/plat_sepolicy.cil", policy)
        self.extract_file(system, "/system/etc/vintf/compatibility_matrix.device.xml", matrix)
        self.extract_file(system, "/system/build.prop", build_prop)
        if '(genfscon fuseblk "/"' in policy.read_text(encoding="utf-8"):
            raise RuntimeError("r7 platform fuseblk rule was not deferred in the source build")
        root = ET.parse(matrix).getroot()
        hals = []
        for hal in root.findall("hal"):
            interface = hal.find("interface")
            hals.append((
                hal.attrib.get("format"), hal.findtext("name"), hal.findtext("version"),
                interface.findtext("name") if interface is not None else None,
                interface.findtext("instance") if interface is not None else None,
            ))
        if hals != [
            ("hidl", "vendor.display.config", "1.0", "IDisplayConfig", "default"),
            ("aidl", "vendor.display.output", "2", "IDisplayOutputManager", "default"),
        ]:
            raise RuntimeError(f"source-built device matrix HAL scope changed: {hals}")
        properties = build_prop.read_text(encoding="utf-8", errors="replace")
        required = (
            "ro.build.id=BP2A.250805.034",
            "ro.build.version.sdk=36",
            "ro.build.version.security_patch=2025-08-05",
            f"ro.build.version.incremental={self.android['build_number']}",
            "ro.product.cpu.abi=armeabi-v7a",
            "ro.product.cpu.abi2=armeabi",
            "ro.system.product.cpu.abilist=armeabi-v7a,armeabi",
            "ro.system.product.cpu.abilist64=",
        )
        for line in required:
            if line not in properties:
                raise RuntimeError(f"source-built ARM32 product property missing: {line}")
        if "arm64-v8a" in properties:
            raise RuntimeError("source-built product unexpectedly declares an ARM64 ABI")
        soong_vars_path = (
            self.args.aosp / "out-ceiling/soong/soong.ubox10_ceiling_arm.variables"
        )
        soong_vars = json.loads(soong_vars_path.read_text(encoding="utf-8"))
        soong_contract = {
            "DeviceArch": "arm",
            "DeviceArchVariant": "armv7-a-neon",
            "DeviceAbi": ["armeabi-v7a", "armeabi"],
            "DeviceSecondaryArch": "",
            "DeviceSecondaryAbi": [],
            "Platform_sdk_version": 36,
            "Shipping_api_level": "31",
            "ExtraVndkVersions": ["31"],
            "BuildId": "BP2A.250805.034",
        }
        for key, expected in soong_contract.items():
            if soong_vars.get(key) != expected:
                raise RuntimeError(
                    f"source-built Soong product contract mismatch: {key}="
                    f"{soong_vars.get(key)!r}, expected {expected!r}"
                )

        avb = self.android["avb"]
        self.run(
            [
                str(avbtool), "add_hashtree_footer",
                "--image", str(system),
                "--partition_name", "system",
                "--partition_size", str(avb["partition_size"]),
                "--hash_algorithm", "sha256",
                "--salt", str(avb["salt"]),
                "--do_not_generate_fec",
                "--prop", "com.ubox10.candidate.id:" + self.candidate_id,
                "--prop", "com.ubox10.avb.fec:none",
                "--key", str(REPO / str(avb["key_relative"])),
                "--algorithm", str(avb["algorithm"]),
            ]
        )
        if system.stat().st_size != avb["partition_size"]:
            raise RuntimeError("signed system partition size mismatch")
        avb_view = self.stage / "system-avb-view"
        avb_view.mkdir()
        os.link(system, avb_view / "system.img")
        self.run(
            [str(avbtool), "verify_image", "--image", str(avb_view / "system.img")],
            output=self.stage / "system-avb-verify.log",
        )
        (avb_view / "system.img").unlink()
        avb_view.rmdir()
        self.run(
            [str(avbtool), "info_image", "--image", str(system)],
            output=self.stage / "system-avb-info.txt",
        )
        self.system = system
        return system, {
            "source_build": BASE.record(self.source_system),
            "candidate": BASE.record(system),
            "filesystem_bytes_before_avb": filesystem_size,
            "headroom_bytes": int(avb["partition_size"]) - filesystem_size,
            "ext4": "PASS",
            "source_integrated_matrix": "PASS",
            "source_integrated_fuseblk_deferral": "PASS",
            "arm32_no_secondary_arch_zygote32_product_contract": "PASS",
            "avb_hashtree_no_fec": "PASS",
        }

    def make_vbmeta_system(self, system: Path) -> Path:
        avb = self.android["avb"]
        output = self.stage / "vbmeta_system.fex"
        self.run(
            [
                str(self.aosp_bin / "avbtool"), "make_vbmeta_image",
                "--output", str(output),
                "--key", str(REPO / str(avb["key_relative"])),
                "--algorithm", str(avb["algorithm"]),
                "--rollback_index", str(avb["rollback_index"]),
                "--rollback_index_location", str(avb["rollback_index_location"]),
                "--include_descriptors_from_image", str(system),
            ]
        )
        avb_view = self.stage / "vbmeta-system-avb-view"
        avb_view.mkdir()
        os.link(system, avb_view / "system.img")
        os.link(output, avb_view / "vbmeta_system.img")
        self.run(
            [str(self.aosp_bin / "avbtool"), "verify_image", "--image",
             str(avb_view / "vbmeta_system.img"), "--key",
             str(REPO / str(avb["key_relative"]))],
            output=self.stage / "vbmeta-system-avb-verify.log",
        )
        (avb_view / "vbmeta_system.img").unlink()
        (avb_view / "system.img").unlink()
        avb_view.rmdir()
        self.run(
            [str(self.aosp_bin / "avbtool"), "info_image", "--image", str(output)],
            output=self.stage / "vbmeta-system-avb-info.txt",
        )
        self.vbmeta_system = output
        return output

    def build_super(
        self, system: Path, vendor_dlkm: Path
    ) -> tuple[Path, dict[str, object]]:
        raw_spec = self.cfg["accepted"]["super_raw"]
        source = self.verified_path(raw_spec)
        candidate = self.stage / "super.raw.img"
        self.run(["cp", "--reflink=auto", str(source), str(candidate)])
        if BASE.digest(candidate) != raw_spec["sha256"]:
            raise RuntimeError("accepted raw super copy changed")

        geometry = self.cfg["super"]
        sector_size = int(geometry["sector_size"])
        replacements = [
            (
                "system_a", int(geometry["system_first_sector"]) * sector_size,
                int(geometry["system_sector_count"]) * sector_size, system,
            ),
            (
                "vendor_dlkm_a", int(geometry["vendor_dlkm_first_sector"]) * sector_size,
                int(geometry["vendor_dlkm_sector_count"]) * sector_size, vendor_dlkm,
            ),
        ]
        for name, _offset, length, payload in replacements:
            if length != payload.stat().st_size:
                raise RuntimeError(f"{name} extent length mismatch")
        spans = []
        cursor = 0
        for _name, offset, length, _payload in sorted(replacements, key=lambda item: item[1]):
            spans.append((cursor, offset - cursor, digest_range(source, cursor, offset - cursor)))
            cursor = offset + length
        spans.append((cursor, source.stat().st_size - cursor,
                      digest_range(source, cursor, source.stat().st_size - cursor)))
        with candidate.open("r+b") as destination:
            for _name, offset, _length, payload in replacements:
                destination.seek(offset)
                with payload.open("rb") as stream:
                    shutil.copyfileobj(stream, destination, CHUNK)
        for offset, length, expected in spans:
            if digest_range(candidate, offset, length) != expected:
                raise RuntimeError("raw super bytes outside intended extents changed")

        accepted_dump = self.stage / "accepted-lpdump.json"
        candidate_dump = self.stage / "candidate-lpdump.json"
        self.run([str(self.aosp_bin / "lpdump"), "-j", str(source)], output=accepted_dump)
        self.run([str(self.aosp_bin / "lpdump"), "-j", str(candidate)], output=candidate_dump)
        if json.loads(accepted_dump.read_text()) != json.loads(candidate_dump.read_text()):
            raise RuntimeError("LP metadata or geometry changed")

        sparse = self.stage / "super.fex"
        roundtrip = self.stage / "super-sparse-roundtrip.raw.img"
        self.run([str(self.aosp_bin / "img2simg"), str(candidate), str(sparse), "4096"])
        self.run([str(self.aosp_bin / "simg2img"), str(sparse), str(roundtrip)])
        if BASE.digest(roundtrip) != BASE.digest(candidate):
            raise RuntimeError("sparse/raw super round trip changed bytes")
        extracted = self.stage / "candidate-logical"
        extracted.mkdir()
        self.run([str(self.aosp_bin / "lpunpack"), str(roundtrip), str(extracted)])
        expected_changed = {"system_a": system, "vendor_dlkm_a": vendor_dlkm}
        logical = {}
        for name, spec in self.cfg["accepted"]["logical"].items():
            path = extracted / f"{name}.img"
            if name in expected_changed:
                if BASE.digest(path) != BASE.digest(expected_changed[name]):
                    raise RuntimeError(f"candidate super changed {name} bytes")
            else:
                self.require(path, spec, f"preserved logical {name}")
            logical[name] = BASE.record(path)
        return sparse, {
            "accepted_raw": BASE.record(source),
            "candidate_raw": BASE.record(candidate),
            "candidate_sparse": BASE.record(sparse),
            "metadata_geometry_exact": True,
            "empty_slot_metadata_preserved": True,
            "sparse_roundtrip_exact": True,
            "bytes_outside_system_and_vendor_dlkm_extents_exact": True,
            "logical": logical,
        }

    def pack_outer(
        self, boot: Path, super_sparse: Path, vbmeta_system: Path
    ) -> tuple[Path, dict[str, object]]:
        before = BASE.outer_payloads(self.base)
        firmware = self.stage / f"x12-{self.candidate_id}.img"
        audit_path = self.stage / "outer-payload-audit.json"
        self.run(
            [
                sys.executable, str(REPO / "tools/pack_image_preserving.py"),
                "--source", str(self.base), "--output", str(firmware),
                "--replace", f"boot.fex={boot}",
                "--replace", f"super.fex={super_sparse}",
                "--replace", f"vbmeta_system.fex={vbmeta_system}",
                "--audit", str(audit_path),
            ]
        )
        self.run(
            [sys.executable, str(REPO / "tools/sunxi_image_tool.py"), "verify", str(firmware)],
            output=self.stage / "candidate-outer-verify.log",
        )
        after = BASE.outer_payloads(firmware)
        if set(before) != set(after):
            raise RuntimeError("outer payload inventory changed")
        changed = sorted(
            name for name in before
            if before[name]["sha256_stored"] != after[name]["sha256_stored"]
        )
        expected = sorted([
            *self.cfg["container"]["replacements"], *self.cfg["container"]["companions"]
        ])
        if changed != expected:
            raise RuntimeError(f"unexpected outer payload delta: {changed}")
        actions = {
            item["filename"]: item["action"]
            for item in json.loads(audit_path.read_text())["payloads"]
        }
        if len(actions) != self.cfg["container"]["total_entries"]:
            raise RuntimeError("outer payload count changed")
        if sum(value == "preserved" for value in actions.values()) != self.cfg["container"]["preserved_entries"]:
            raise RuntimeError("outer preserved-payload count changed")
        return firmware, {
            "candidate": BASE.record(firmware),
            "entry_count": len(actions),
            "changed_payloads": changed,
            "preserved_payload_count": self.cfg["container"]["preserved_entries"],
            "all_other_payload_bytes_exact": True,
            "imagewty_verify": "PASS",
        }

    def finish_r3(
        self, firmware: Path, image: Path, system_audit: dict[str, object],
        boot_audit: dict[str, object], vendor_dlkm_audit: dict[str, object],
        super_audit: dict[str, object], outer_audit: dict[str, object], started: float,
    ) -> None:
        if BASE.record(self.base) != self.base_before or BASE.record(self.rollback) != self.rollback_before:
            raise RuntimeError("accepted base or rollback changed during construction")
        result = {
            "schema": 1,
            "id": self.candidate_id,
            "status": "PACKAGED_AWAITING_FULL_OFFLINE_AUDIT",
            "physical_device_actions_performed": False,
            "flash_authorized": False,
            "elapsed_seconds": round(time.time() - started, 1),
            "firmware": BASE.record(firmware),
            "kernel": BASE.record(image),
            "kernel_release": "5.4.302+",
            "system": system_audit,
            "boot": boot_audit,
            "vendor_dlkm": vendor_dlkm_audit,
            "super": super_audit,
            "outer": outer_audit,
            "vbmeta_system": BASE.record(self.vbmeta_system),
            "changed_classes": [
                "Android 16 r7 system_a and vbmeta_system",
                "Path-A Image/boot and complete matching vendor_dlkm module set",
                "required LP sparse representation, AVB descriptors/trees and outer checksums",
            ],
            "preserved_hardware_authority": [
                "accepted vendor_a and product_a",
                "accepted vendor_boot/ramdisk, DT/DTBO, TEE, bootloader and top-level vbmeta",
                "factory/security/rollback/recovery payloads and all unrelated IMAGEWTY entries",
            ],
        }
        result = BASE.rewrite_paths(result, self.stage, self.final)
        (self.stage / "build-result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        expected = self.cfg.get("expected_result")
        if expected:
            for label, path in (
                ("firmware", firmware), ("boot", Path(str(boot_audit["candidate"]["path"]))),
                ("system", self.system), ("super", Path(str(super_audit["candidate_sparse"]["path"]))),
                ("vendor_dlkm", Path(str(vendor_dlkm_audit["candidate"]["path"]))),
                ("vbmeta_system", self.vbmeta_system),
            ):
                actual = BASE.record(path)
                if actual["size"] != expected[label]["size"] or actual["sha256"] != expected[label]["sha256"]:
                    raise RuntimeError(f"non-reproducible {label}: {actual}")
        sums = []
        for path in sorted(self.stage.iterdir()):
            if path.is_file() and path.name != "SHA256SUMS":
                sums.append(f"{BASE.digest(path)}  {path.name}")
        (self.stage / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
        os.replace(self.stage, self.final)

    def build(self) -> None:
        started = time.time()
        try:
            self.setup()
            system, system_audit = self.prepare_system()
            vbmeta_system = self.make_vbmeta_system(system)
            boot, image, boot_audit = self.build_boot()
            vendor_dlkm, vendor_dlkm_audit = self.build_vendor_dlkm()
            super_sparse, super_audit = self.build_super(system, vendor_dlkm)
            firmware, outer_audit = self.pack_outer(boot, super_sparse, vbmeta_system)
            self.finish_r3(
                firmware, image, system_audit, boot_audit, vendor_dlkm_audit,
                super_audit, outer_audit, started,
            )
            print(f"SUCCESS: {self.final} ({time.time() - started:.1f}s)", flush=True)
        except Exception:
            if self.stage.exists() and not self.args.keep_failed:
                shutil.rmtree(self.stage)
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--aosp", type=Path, default=DEFAULT_AOSP)
    parser.add_argument("--integration-repo", type=Path, default=DEFAULT_INTEGRATION)
    parser.add_argument("--keep-failed", action="store_true")
    R3Builder(parser.parse_args()).build()


if __name__ == "__main__":
    main()
