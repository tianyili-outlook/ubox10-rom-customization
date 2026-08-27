#!/usr/bin/env python3
"""Build B r2 by restoring only the accepted /metadata system-root mountpoint."""
from __future__ import annotations

import argparse
import copy
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
DEFAULT_CONFIG = REPO / "configs/candidates/a16-prototype-b-r2.json"
DEFAULT_AOSP = Path("/work/src/ubox10-a16-ceiling")
CHUNK = 8 * 1024 * 1024

R1_PATH = REPO / "scripts/build-a16-prototype-b-r1-candidate.py"
R1_SPEC = importlib.util.spec_from_file_location("a16_b_r1_builder_for_r2", R1_PATH)
if R1_SPEC is None or R1_SPEC.loader is None:
    raise RuntimeError(f"cannot import r1 builder helpers: {R1_PATH}")
R1 = importlib.util.module_from_spec(R1_SPEC)
sys.modules[R1_SPEC.name] = R1
R1_SPEC.loader.exec_module(R1)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(CHUNK), b""):
            value.update(block)
    return value.hexdigest().upper()


def record(path: Path) -> dict[str, object]:
    return {"path": str(path), "size": path.stat().st_size, "sha256": digest(path)}


def source(path: str) -> Path:
    value = Path(path)
    return value if value.is_absolute() else REPO / value


class Builder(R1.Builder):
    def __init__(self, args: argparse.Namespace) -> None:
        raw = json.loads(args.config.read_text(encoding="utf-8"))
        inherited = source(str(raw["inherits"]))
        merged = json.loads(inherited.read_text(encoding="utf-8"))
        merged.update({
            "id": raw["id"],
            "milestone": raw["milestone"],
            "status": raw["status"],
            "base_candidate": raw["base_candidate"],
            "root_cause": raw["root_cause"],
            "root_mountpoint_contract": raw["root_mountpoint_contract"],
            "outer_delta": raw["outer_delta"],
            "allowed_semantic_delta": raw["allowed_semantic_delta"],
            "forbidden_changes": raw["forbidden_changes"],
        })
        merged["avb"] = copy.deepcopy(merged["avb"])
        merged["avb"]["system"] = raw["avb_system"]

        self.args = args
        self.raw_cfg = raw
        self.cfg = merged
        self.r4 = json.loads(R1.R4_CONFIG.read_text(encoding="utf-8"))
        self.candidate_id = str(raw["id"])
        self.final = REPO / "out/candidates" / self.candidate_id
        self.stage = self.final.parent / f".{self.candidate_id}.staging-{uuid.uuid4().hex}"
        self.log = self.stage / "logs/01-commands.log"
        self.host = args.aosp / "out-ceiling-b1/host/linux-x86/bin"
        self.product = args.aosp / "out-ceiling-b1/target/product/ubox10_ceiling_arm64"
        self.source_system = self.product / "system.img"
        self.avbtool = args.aosp / "external/avb/avbtool.py"
        self.unpack_bootimg = args.aosp / "system/tools/mkbootimg/unpack_bootimg.py"
        self.r4_dir = REPO / "out/candidates/a16-prototype-a-r4"
        self.r1_dir = REPO / "out/candidates/a16-prototype-b-r1"
        self.r4_offline_audit = REPO / str(self.cfg["frozen_r4_offline_audit"]["path"])
        self.base = source(str(raw["base_candidate"]["path"]))
        self.rollback = Path(str(self.r4["rollback"]["path"]))
        self.started = time.time()

    def setup(self) -> None:
        if self.final.exists():
            raise RuntimeError(f"refusing to overwrite existing candidate: {self.final}")
        if self.raw_cfg["status"] != "ROOT_CAUSE_PROVEN_SINGLE_CAUSE_R2_AUTHORIZED":
            raise RuntimeError("r2 single-cause build is not authorized")
        super().setup()
        for name, spec in self.raw_cfg["base_artifacts"].items():
            self.require(source(str(spec["path"])), spec, f"frozen r1 {name}")

    def prepare_system(self) -> tuple[Path, dict[str, object]]:
        spec = self.raw_cfg["base_artifacts"]["system_a"]
        original = source(str(spec["path"]))
        system = self.stage / "system_a.img"
        shutil.copyfile(original, system)

        before = self.debugfs(system, "stat /metadata", capture=True)
        if "File not found" not in before:
            raise RuntimeError("r1 system unexpectedly already contains /metadata")
        self.run([sys.executable, str(self.avbtool), "erase_footer", "--image", str(system)])
        avb = self.cfg["avb"]["system"]
        if system.stat().st_size != avb["original_filesystem_size"]:
            raise RuntimeError("r1 system AVB original image size changed")
        self.run(["e2fsck", "-fn", str(system)])

        # Fix the e2fsprogs clock and restore the accepted inode timestamps so
        # repeated builds do not turn the one-directory delta into time noise.
        previous_fake_time = os.environ.get("E2FSPROGS_FAKE_TIME")
        os.environ["E2FSPROGS_FAKE_TIME"] = str(int("6a8e980e", 16))
        try:
            self.debugfs(system, "mkdir /metadata")
            for field, value in (
                ("mode", "040755"), ("uid", "0"), ("gid", "0"),
                ("ctime", "0x6a8d83ab"), ("atime", "0x6a8d83ab"),
                ("mtime", "0x6a8d83ab"), ("crtime", "0x6a8e980e"),
            ):
                self.debugfs(system, f"set_inode_field /metadata {field} {value}")
            self.debugfs(
                system,
                'ea_set /metadata security.selinux "u:object_r:metadata_file:s0\\000"',
            )
            # mkdir necessarily changes the parent link count; keep all other
            # parent timestamps equal to the frozen r1 root inode.
            for field, value in (
                ("ctime", "0x6a8ffae2"), ("atime", "0x6a8ffae2"),
                ("mtime", "0x6a8ffae2"), ("crtime", "0x6a8ffae4"),
            ):
                self.debugfs(system, f"set_inode_field / {field} {value}")
            self.run(["e2fsck", "-fy", str(system)], allowed={0, 1})
        finally:
            if previous_fake_time is None:
                os.environ.pop("E2FSPROGS_FAKE_TIME", None)
            else:
                os.environ["E2FSPROGS_FAKE_TIME"] = previous_fake_time

        contract = self.raw_cfg["root_mountpoint_contract"]
        metadata = self.debugfs(system, "stat /metadata", capture=True)
        xattrs = self.debugfs(system, "ea_list /metadata", capture=True)
        for fragment in (
            "Type: directory", "Mode:  0755", "User:     0", "Group:     0",
        ):
            if fragment not in metadata:
                raise RuntimeError(f"r2 /metadata inode contract mismatch: {fragment}")
        if contract["selinux"] not in xattrs:
            raise RuntimeError("r2 /metadata SELinux label mismatch")
        for path in contract["required_move_mountpoints"]:
            output = self.debugfs(system, f"stat {path}", capture=True)
            if "Type: directory" not in output:
                raise RuntimeError(f"r2 switch-root destination is absent/not-directory: {path}")
        self.run(["e2fsck", "-fn", str(system)])

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
            raise RuntimeError("r2 signed system size mismatch")
        self.verify_avb_partition(system, "system", avb["key_relative"])
        return system, {
            "base_r1": record(original),
            "candidate": record(system),
            "filesystem_bytes_before_avb": avb["original_filesystem_size"],
            "ext4": "PASS",
            "avb_hashtree_no_fec": "PASS",
            "semantic_delta": ["add root directory /metadata"],
            "root_mountpoint_contract": contract,
            "all_other_b1_system_semantics_expected_preserved": True,
        }

    def prepare_vendor(self) -> tuple[Path, dict[str, object]]:
        spec = self.raw_cfg["base_artifacts"]["vendor_a"]
        original = source(str(spec["path"]))
        vendor = self.stage / "vendor_a.img"
        shutil.copyfile(original, vendor)
        self.require(vendor, spec, "byte-preserved r1 vendor_a")
        self.verify_avb_partition(vendor, "vendor", None)
        return vendor, {
            "base_r1": record(original),
            "candidate": record(vendor),
            "byte_preserved_from_r1": True,
            "ext4": "PASS_INHERITED_AND_REVERIFIED",
            "avb_hashtree_fec": "PASS_INHERITED_AND_REVERIFIED",
        }

    def build_super(self, system: Path, vendor: Path) -> tuple[Path, dict[str, object]]:
        spec = self.raw_cfg["base_artifacts"]["super_raw"]
        original = source(str(spec["path"]))
        candidate = self.stage / "super.raw.img"
        self.run(["cp", "--reflink=auto", str(original), str(candidate)])
        extents = self.cfg["partition_fit"]["candidate_extents_sectors"]
        system_extents = extents["system_a"]
        if system_extents != [[2048, 3226984]]:
            raise RuntimeError("r1 system_a is not the expected single fixed extent")
        offset = system_extents[0][0] * 512
        extent_bytes = (system_extents[0][1] - system_extents[0][0]) * 512
        if system.stat().st_size != extent_bytes:
            raise RuntimeError("r2 system does not fit the exact r1 extent")
        with candidate.open("r+b") as destination, system.open("rb") as payload:
            destination.seek(offset)
            shutil.copyfileobj(payload, destination, CHUNK)

        old_json = self.stage / "r1-lpdump.json"
        new_json = self.stage / "candidate-lpdump.json"
        self.run([str(self.host / "lpdump"), "-j", str(original)], output=old_json)
        self.run([str(self.host / "lpdump"), "-j", str(candidate)], output=new_json)
        if json.loads(old_json.read_text()) != json.loads(new_json.read_text()):
            raise RuntimeError("r2 changed LP metadata/geometry")
        slot1 = self.stage / "candidate-lpdump-slot1.json"
        self.run([str(self.host / "lpdump"), "-s", "1", "-j", str(candidate)], output=slot1)
        if json.loads(slot1.read_text()) != json.loads(new_json.read_text()):
            raise RuntimeError("r2 LP metadata slots 0 and 1 differ")

        sparse = self.stage / "super.fex"
        roundtrip = self.stage / "super-sparse-roundtrip.raw.img"
        self.run([str(self.host / "img2simg"), str(candidate), str(sparse), "4096"])
        self.run([str(self.host / "simg2img"), str(sparse), str(roundtrip)])
        if digest(roundtrip) != digest(candidate):
            raise RuntimeError("r2 sparse/raw super roundtrip changed bytes")

        extracted = self.stage / "candidate-logical"
        extracted.mkdir()
        self.run([str(self.host / "lpunpack"), str(roundtrip), str(extracted)])
        expected = copy.deepcopy(self.cfg["partition_fit"]["candidate_extents_sectors"])
        logical: dict[str, dict[str, object]] = {}
        for name in expected:
            path = extracted / f"{name}.img"
            if name == "system_a":
                if digest(path) != digest(system):
                    raise RuntimeError("r2 super changed system_a bytes")
            else:
                baseline = self.r1_dir / "candidate-logical" / f"{name}.img"
                if digest(path) != digest(baseline) or path.stat().st_size != baseline.stat().st_size:
                    raise RuntimeError(f"r2 changed preserved logical partition: {name}")
            logical[name] = record(path)
        return sparse, {
            "frozen_raw": record(original),
            "candidate_raw": record(candidate),
            "candidate_sparse": record(sparse),
            "metadata_version": "10.2",
            "metadata_slots": 3,
            "metadata_slots_0_and_1_exact": True,
            "sb_a_maximum_bytes": 3_212_836_864,
            "sb_a_allocated_bytes": 2_081_472_512,
            "sb_a_unallocated_bytes": 1_131_364_352,
            "vendor_a_bytes": 150_994_944,
            "vendor_growth_bytes": 31_928_320,
            "growth_only_from_old_unallocated_space": True,
            "all_other_partition_extents_exact_r4": True,
            "no_partition_shrunk": True,
            "b_slot_allocations_empty_exact": True,
            "sparse_roundtrip_exact": True,
            "lp_geometry_byte_preserved_from_r1": True,
            "logical": logical,
        }

    def pack_outer(
        self, super_sparse: Path, vbmeta_system: Path, vbmeta_vendor: Path
    ) -> tuple[Path, dict[str, object]]:
        self.require(
            vbmeta_vendor, self.raw_cfg["base_artifacts"]["vbmeta_vendor"],
            "byte-preserved r1 vbmeta_vendor",
        )
        before = R1.PACK.outer_payloads(self.base)
        firmware = self.stage / f"x12-{self.candidate_id}.img"
        payload_audit = self.stage / "outer-payload-audit.json"
        self.run([
            sys.executable, str(REPO / "tools/pack_image_preserving.py"),
            "--source", str(self.base), "--output", str(firmware),
            "--replace", f"super.fex={super_sparse}",
            "--replace", f"vbmeta_system.fex={vbmeta_system}",
            "--audit", str(payload_audit),
        ])
        self.run([
            sys.executable, str(REPO / "tools/sunxi_image_tool.py"), "verify", str(firmware)
        ], output=self.stage / "candidate-outer-verify.log")
        after = R1.PACK.outer_payloads(firmware)
        changed = sorted(
            name for name in before
            if before[name]["sha256_stored"] != after[name]["sha256_stored"]
        )
        expected = sorted(self.raw_cfg["outer_delta"]["changed_payloads_from_r1"])
        if set(before) != set(after) or len(after) != 50 or changed != expected:
            raise RuntimeError(f"unexpected r2 outer delta: {changed}")
        return firmware, {
            "candidate": record(firmware),
            "entry_count": 50,
            "changed_payloads": changed,
            "preserved_payload_count": 46,
            "all_other_payload_bytes_exact_r1": True,
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
        for name in ("boot.fex", "vendor_dlkm_a.img"):
            shutil.copyfile(self.r1_dir / name, self.stage / name)
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
                "android_system_rebuilt": False,
            },
            "base_r1": record(self.base),
            "firmware": record(firmware),
            "system": system_audit,
            "vendor": vendor_audit,
            "super": super_audit,
            "outer": outer_audit,
            "vbmeta_system": record(vbmeta_system),
            "vbmeta_vendor": record(vbmeta_vendor),
            "boot": {"candidate": record(self.stage / "boot.fex"), "byte_preserved_from_r1": True},
            "vendor_dlkm": {
                "candidate": record(self.stage / "vendor_dlkm_a.img"),
                "byte_preserved_from_r1": True,
                "module_count": 22,
            },
            "kernel": record(self.stage / "kernel-evidence/Image"),
            "kernel_rebuilt": False,
            "root_cause": self.raw_cfg["root_cause"],
            "functional_delta_from_r1": self.raw_cfg["allowed_semantic_delta"],
            "forbidden_changes": self.raw_cfg["forbidden_changes"],
            "preserved": [
                "all r1 mixed ARM64/ARM32, zygote64_32 and graphics-provider semantics",
                "vendor_a, product_a, vendor_dlkm_a and every B-slot byte",
                "LP geometry, kernel, boot, vendor_boot, fstab, DT/DTBO and top-level vbmeta",
                "Mali, mapper, gralloc and every retained hardware-facing service",
                "46 of 50 r1 outer payloads",
            ],
        }
        result = R1.rewrite_paths(result, self.stage, self.final)
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
            vbmeta_vendor = self.stage / "vbmeta_vendor.fex"
            shutil.copyfile(
                source(str(self.raw_cfg["base_artifacts"]["vbmeta_vendor"]["path"])),
                vbmeta_vendor,
            )
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
