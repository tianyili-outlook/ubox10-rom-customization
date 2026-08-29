#!/usr/bin/env python3
"""Package exact r7 with four instrumentation-only UBOX_R7_DIAG1 ELF files."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
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
DEFAULT_CONFIG = REPO / "configs/candidates/a16-prototype-b-r7-diag1.json"
DEFAULT_AOSP = Path("/work/src/ubox10-a16-ceiling")
R7_PATH = REPO / "scripts/build-a16-prototype-b-r7-candidate.py"
R7_SPEC = importlib.util.spec_from_file_location("a16_b_r7_builder_for_diag1", R7_PATH)
if R7_SPEC is None or R7_SPEC.loader is None:
    raise RuntimeError(f"cannot import r7 builder: {R7_PATH}")
R7 = importlib.util.module_from_spec(R7_SPEC)
sys.modules[R7_SPEC.name] = R7
R7_SPEC.loader.exec_module(R7)

SHARED = R7.SHARED
PACK = SHARED.PACK


def source(path: str) -> Path:
    value = Path(path)
    return value if value.is_absolute() else REPO / value


def lpdump_linear_extents(text: str) -> dict[str, list[tuple[int, int]]]:
    """Return each partition's physical [start, end) sectors in logical order."""
    result: dict[str, list[tuple[int, int]]] = {}
    partition: str | None = None
    in_extents = False
    for line in text.splitlines():
        name = re.match(r"^  Name: (\S+)$", line)
        if name:
            partition = name.group(1)
            result.setdefault(partition, [])
            in_extents = False
            continue
        if partition is not None and line == "  Extents:":
            in_extents = True
            continue
        if in_extents:
            extent = re.match(
                r"^    (\d+) \.\. (\d+) linear \S+ (\d+)$", line
            )
            if extent:
                logical_start, logical_end, physical_start = map(int, extent.groups())
                if logical_end < logical_start:
                    raise RuntimeError(f"invalid LP extent: {line}")
                sectors = logical_end - logical_start + 1
                result[partition].append((physical_start, physical_start + sectors))
                continue
            if line.startswith("------------------------"):
                in_extents = False
    return result


def elf_contract(path: Path) -> dict[str, object]:
    header = subprocess.check_output(["readelf", "-h", str(path)], text=True)
    dynamic = subprocess.check_output(["readelf", "-W", "-d", str(path)], text=True)
    notes = subprocess.check_output(["readelf", "-W", "-n", str(path)], text=True)
    exports = subprocess.check_output(
        ["nm", "-D", "--defined-only", "--format=posix", str(path)], text=True
    )
    parsed_exports = [line.split() for line in exports.splitlines() if line.strip()]
    build_id = re.search(r"\bBuild ID:\s*([0-9a-fA-F]+)", notes)
    soname = re.search(r"\(SONAME\).*\[([^]]+)\]", dynamic)
    return {
        "elf_class": "ELF64" if "Class:                             ELF64" in header else "ELF32",
        "architecture": "AArch64" if "Machine:                           AArch64" in header else "ARM",
        "build_id": build_id.group(1).lower() if build_id else None,
        "soname": soname.group(1) if soname else None,
        "dt_needed": re.findall(r"\(NEEDED\).*\[([^]]+)\]", dynamic),
        "exports": sorted(fields[0] for fields in parsed_exports),
        "strong_exports": sorted(
            fields[0] for fields in parsed_exports
            if len(fields) > 1 and fields[1].upper() not in {"W", "V"}
        ),
        "weak_exports": sorted(
            fields[0] for fields in parsed_exports
            if len(fields) > 1 and fields[1].upper() in {"W", "V"}
        ),
    }


class Builder(R7.Builder):
    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__(args)
        self.raw_cfg = json.loads(args.config.read_text(encoding="utf-8"))
        self.args = args
        self.candidate_id = str(self.raw_cfg["id"])
        self.cfg["id"] = self.candidate_id
        self.cfg["status"] = self.raw_cfg["status"]
        self.cfg["base_candidate"] = self.raw_cfg["base_candidate"]
        self.cfg["_continuation"] = self.raw_cfg
        self.final = REPO / "out/candidates" / self.candidate_id
        self.stage = self.final.parent / f".{self.candidate_id}.staging-{uuid.uuid4().hex}"
        self.log = self.stage / "logs/01-commands.log"
        self.base = source(str(self.raw_cfg["base_candidate"]["path"]))
        self.started = time.time()

    @contextmanager
    def deterministic_ext4_time(self):
        previous = os.environ.get("E2FSPROGS_FAKE_TIME")
        os.environ["E2FSPROGS_FAKE_TIME"] = str(int("6a8fff2d", 16))
        try:
            yield
        finally:
            if previous is None:
                os.environ.pop("E2FSPROGS_FAKE_TIME", None)
            else:
                os.environ["E2FSPROGS_FAKE_TIME"] = previous

    def setup(self) -> None:
        if self.final.exists():
            raise RuntimeError(f"refusing to overwrite existing candidate: {self.final}")
        if self.raw_cfg["status"] != "INSTRUMENTATION_ONLY_DIAGNOSTIC_AUTHORIZED":
            raise RuntimeError("diag1 is not authorized as instrumentation-only")
        if self.raw_cfg["governance"]["r8_authorized"] is not False:
            raise RuntimeError("diag1 must not authorize r8")
        self.stage.mkdir(parents=True)
        self.require(self.base, self.raw_cfg["base_candidate"], "immutable exact r7 outer")
        self.require(self.rollback, self.r4["rollback"], "Android 12 rollback")
        for name, spec in self.raw_cfg["base_artifacts"].items():
            self.require(source(str(spec["path"])), spec, f"exact r7 artifact {name}")

        revisions = self.raw_cfg["source_contract"]["repositories"]
        for repository, expected in revisions.items():
            actual = subprocess.check_output(
                ["git", "-C", str(self.args.aosp / repository), "rev-parse", "HEAD"],
                text=True,
            ).strip()
            if actual != expected:
                raise RuntimeError(f"source revision changed: {repository}: {actual}")
        manifest = subprocess.check_output(
            ["git", "-C", str(self.args.aosp / ".repo/manifests"), "rev-parse", "HEAD"],
            text=True,
        ).strip()
        if manifest != self.raw_cfg["source_contract"]["manifest_commit"]:
            raise RuntimeError(f"manifest revision changed: {manifest}")

        overlay = REPO / self.raw_cfg["source_contract"]["overlay"]
        checked = subprocess.check_output(
            [str(overlay / "prepare.sh"), "check", str(self.args.aosp)], text=True
        )
        if "source state: PATCHED" not in checked:
            raise RuntimeError("the isolated diag1 source overlay is not exactly applied")
        for relative, contract in self.raw_cfg["source_contract"]["files"].items():
            path = self.args.aosp / relative
            self.require(
                path,
                {"size": path.stat().st_size, "sha256": contract["patched_sha256"]},
                f"patched source {relative}",
            )

        for name, contract in self.raw_cfg["runtime_files"].items():
            binary = Path(str(contract["source_path"]))
            self.require(binary, contract, f"diag1 build output {name}")
            dynamic = elf_contract(binary)
            for field in ("elf_class", "architecture", "build_id"):
                if dynamic[field] != contract[field]:
                    raise RuntimeError(f"{name} {field} changed: {dynamic[field]}")
            if contract.get("soname") != dynamic["soname"]:
                raise RuntimeError(f"{name} SONAME changed: {dynamic['soname']}")
            data = binary.read_bytes()
            if b"UBOX_R7_DIAG1" not in data:
                raise RuntimeError(f"{name} lacks the diagnostic marker")
        surfaceflinger = Path(str(self.raw_cfg["runtime_files"]["surfaceflinger"]["source_path"]))
        if b"Failed to create a valid texture." not in surfaceflinger.read_bytes():
            raise RuntimeError("the original RenderEngine fatal text is absent")

        r7 = REPO / "out/candidates/a16-prototype-b-r7"
        shutil.copytree(r7 / "kernel-evidence", self.stage / "kernel-evidence")
        for name in (
            "final-build-variables.txt",
            "mali-intake.json",
            "active-product-build.prop.r5",
            "runtime-product-source-audit.json",
            "boringssl_self_test64",
        ):
            shutil.copyfile(r7 / name, self.stage / name)

    @staticmethod
    def inode_times(stat_text: str) -> dict[str, str]:
        result: dict[str, str] = {}
        for field in ("ctime", "atime", "mtime", "crtime"):
            match = re.search(rf"^\s*{field}:\s*(0x[0-9a-fA-F]+)", stat_text, re.MULTILINE)
            if match is None:
                raise RuntimeError(f"cannot parse ext4 {field}")
            result[field] = match.group(1)
        return result

    def restore_times(self, image: Path, path: str, times: dict[str, str]) -> None:
        for field, value in times.items():
            self.debugfs(image, f"set_inode_field {path} {field} {value}")

    def replace_runtime_file(
        self, image: Path, name: str, internal_path: str
    ) -> dict[str, object]:
        contract = self.raw_cfg["runtime_files"][name]
        parent = str(Path(internal_path).parent)
        parent_times = self.inode_times(self.debugfs(image, f"stat {parent}", capture=True))
        old = self.stage / f"r7-{name}"
        new = self.stage / f"diag1-{name}"
        self.debugfs(image, f"dump -p {internal_path} {old}")
        self.require(
            old,
            {"size": contract["old_size"], "sha256": contract["old_sha256"]},
            f"frozen r7 {name}",
        )
        if b"UBOX_R7_DIAG1" in old.read_bytes():
            raise RuntimeError(f"canonical r7 unexpectedly contains diag1 marker: {name}")
        before_elf = elf_contract(old)
        after_elf = elf_contract(Path(str(contract["source_path"])))
        for field in ("elf_class", "architecture", "soname", "dt_needed", "strong_exports"):
            if before_elf[field] != after_elf[field]:
                raise RuntimeError(f"{name} non-logging ELF contract changed: {field}")

        self.debugfs(image, f"rm {internal_path}")
        self.debugfs(image, f"write {contract['source_path']} {internal_path}")
        self.debugfs(image, f"set_inode_field {internal_path} mode 010{contract['mode']}")
        self.debugfs(image, f"set_inode_field {internal_path} uid {contract['uid']}")
        self.debugfs(image, f"set_inode_field {internal_path} gid {contract['gid']}")
        for field in ("ctime", "atime", "mtime", "crtime"):
            self.debugfs(image, f"set_inode_field {internal_path} {field} {contract[field]}")
        self.debugfs(
            image,
            f'ea_set {internal_path} security.selinux "{contract["selinux"]}\\000"',
        )
        self.restore_times(image, parent, parent_times)
        self.debugfs(image, f"dump -p {internal_path} {new}")
        self.require(new, contract, f"installed diag1 {name}")
        inode = self.debugfs(image, f"stat {internal_path}", capture=True)
        attrs = self.debugfs(image, f"ea_list {internal_path}", capture=True)
        if (
            f"Mode:  {contract['mode']}" not in inode
            or f"User:     {contract['uid']}" not in inode
            or f"Group:  {contract['gid']:4d}" not in inode
            or contract["selinux"] not in attrs
        ):
            raise RuntimeError(f"installed diag1 inode contract changed: {name}")
        return {
            "partition_path": contract["partition_path"],
            "reason": contract["reason"],
            "r7": SHARED.record(old),
            "diag1": SHARED.record(new),
            "elf_class": contract["elf_class"],
            "architecture": contract["architecture"],
            "build_id": contract["build_id"],
            "inode": {
                "mode": contract["mode"],
                "uid": contract["uid"],
                "gid": contract["gid"],
                "selinux": contract["selinux"],
            },
            "dt_needed_preserved": True,
            "dynamic_strong_exports_preserved": True,
            "weak_exports_removed": sorted(
                set(before_elf["weak_exports"]) - set(after_elf["weak_exports"])
            ),
            "weak_exports_added": sorted(
                set(after_elf["weak_exports"]) - set(before_elf["weak_exports"])
            ),
            "diagnostic_marker_present": True,
        }

    def prepare_system(self) -> tuple[Path, dict[str, object]]:
        spec = self.raw_cfg["base_artifacts"]["system_a"]
        original = source(str(spec["path"]))
        system = self.stage / "system_a.img"
        shutil.copyfile(original, system)
        self.require(system, spec, "exact frozen r7 system_a")
        with self.deterministic_ext4_time():
            self.run([sys.executable, str(self.avbtool), "erase_footer", "--image", str(system)])
            self.run(["e2fsck", "-fn", str(system)])
            replacements = {
                "surfaceflinger": self.replace_runtime_file(
                    system, "surfaceflinger", "/system/bin/surfaceflinger"
                ),
                "libstagefright64": self.replace_runtime_file(
                    system, "libstagefright64", "/system/lib64/libstagefright.so"
                ),
            }
            self.run(["e2fsck", "-fy", str(system)], allowed={0, 1})
            self.run(["e2fsck", "-fn", str(system)])

        avb = self.cfg["avb"]["system"]
        self.run([
            sys.executable,
            str(self.avbtool),
            "add_hashtree_footer",
            "--image",
            str(system),
            "--partition_name",
            "system",
            "--partition_size",
            str(avb["partition_size"]),
            "--hash_algorithm",
            "sha256",
            "--salt",
            str(avb["salt"]),
            "--do_not_generate_fec",
            "--prop",
            f"com.ubox10.candidate.id:{self.candidate_id}",
            "--prop",
            "com.ubox10.avb.fec:none",
            "--key",
            str(REPO / avb["key_relative"]),
            "--algorithm",
            avb["algorithm"],
        ])
        self.verify_avb_partition(system, "system", avb["key_relative"])
        return system, {
            "base_r7": SHARED.record(original),
            "candidate": SHARED.record(system),
            "tree_delta": {
                "added": [],
                "removed": [],
                "changed": ["system/bin/surfaceflinger", "system/lib64/libstagefright.so"],
            },
            "replaced": replacements,
            "ext4": "PASS",
            "avb_hashtree_no_fec": "PASS",
        }

    def prepare_vendor(self) -> tuple[Path, dict[str, object]]:
        spec = self.raw_cfg["base_artifacts"]["vendor_a"]
        original = source(str(spec["path"]))
        vendor = self.stage / "vendor_a.img"
        shutil.copyfile(original, vendor)
        self.require(vendor, spec, "exact frozen r7 vendor_a")
        with self.deterministic_ext4_time():
            self.run([sys.executable, str(self.avbtool), "erase_footer", "--image", str(vendor)])
            self.run(["e2fsck", "-fn", str(vendor)])
            replacements = {
                "gralloc32": self.replace_runtime_file(
                    vendor, "gralloc32", "/lib/hw/gralloc.apollo.so"
                ),
                "gralloc64": self.replace_runtime_file(
                    vendor, "gralloc64", "/lib64/hw/gralloc.apollo.so"
                ),
            }
            self.run(["e2fsck", "-fy", str(vendor)], allowed={0, 1})
            self.run(["e2fsck", "-fn", str(vendor)])

        avb = self.cfg["avb"]["vendor"]
        self.run([
            sys.executable,
            str(self.avbtool),
            "add_hashtree_footer",
            "--image",
            str(vendor),
            "--partition_name",
            "vendor",
            "--partition_size",
            str(avb["partition_size"]),
            "--hash_algorithm",
            "sha256",
            "--salt",
            avb["salt"],
            "--prop",
            f"com.android.build.vendor.fingerprint:{avb['fingerprint']}",
            "--prop",
            f"com.android.build.vendor.os_version:{avb['os_version']}",
        ])
        self.verify_avb_partition(vendor, "vendor", None)
        return vendor, {
            "base_r7": SHARED.record(original),
            "candidate": SHARED.record(vendor),
            "tree_delta": {
                "added": [],
                "removed": [],
                "changed": ["lib/hw/gralloc.apollo.so", "lib64/hw/gralloc.apollo.so"],
            },
            "replaced": replacements,
            "ext4": "PASS",
            "avb_hashtree_fec": "PASS",
        }

    def make_vbmeta(self, image: Path, partition: str) -> Path:
        return SHARED.Builder.make_vbmeta(self, image, partition)

    def build_super(self, system: Path, vendor: Path) -> tuple[Path, dict[str, object]]:
        spec = self.raw_cfg["base_artifacts"]["super_raw"]
        original = source(str(spec["path"]))
        candidate = self.stage / "super.raw.img"
        self.run(["cp", "--reflink=auto", str(original), str(candidate)])

        old_text = self.stage / "r7-lpdump.txt"
        self.run([str(self.host / "lpdump"), str(original)], output=old_text)
        extents = lpdump_linear_extents(old_text.read_text(encoding="utf-8"))
        sector_size = 512
        copied_extents: dict[str, list[list[int]]] = {}
        with candidate.open("r+b", buffering=0) as output:
            for partition, image in (("system_a", system), ("vendor_a", vendor)):
                partition_extents = extents.get(partition, [])
                capacity = sum(end - start for start, end in partition_extents) * sector_size
                if capacity != image.stat().st_size:
                    raise RuntimeError(
                        f"{partition} bytes do not exactly fill frozen r7 extents: "
                        f"image={image.stat().st_size} extents={capacity}"
                    )
                copied_extents[partition] = [list(item) for item in partition_extents]
                with image.open("rb", buffering=0) as input_file:
                    for start, end in partition_extents:
                        remaining = (end - start) * sector_size
                        output.seek(start * sector_size)
                        while remaining:
                            chunk = input_file.read(min(8 * 1024 * 1024, remaining))
                            if not chunk:
                                raise RuntimeError(f"short read while copying {partition}")
                            output.write(chunk)
                            remaining -= len(chunk)
                    if input_file.read(1):
                        raise RuntimeError(f"trailing bytes while copying {partition}")

        old_json = self.stage / "r7-lpdump.json"
        new_json = self.stage / "candidate-lpdump.json"
        self.run([str(self.host / "lpdump"), "-j", str(original)], output=old_json)
        self.run([str(self.host / "lpdump"), "-j", str(candidate)], output=new_json)
        if json.loads(old_json.read_text(encoding="utf-8")) != json.loads(
            new_json.read_text(encoding="utf-8")
        ):
            raise RuntimeError("diag1 changed exact r7 LP metadata or extents")
        slot1 = self.stage / "candidate-lpdump-slot1.json"
        self.run([str(self.host / "lpdump"), "-s", "1", "-j", str(candidate)], output=slot1)
        if json.loads(slot1.read_text(encoding="utf-8")) != json.loads(
            new_json.read_text(encoding="utf-8")
        ):
            raise RuntimeError("diag1 LP metadata slots 0 and 1 differ")

        sparse = self.stage / "super.fex"
        roundtrip = self.stage / "super-sparse-roundtrip.raw.img"
        self.run([str(self.host / "img2simg"), str(candidate), str(sparse), "4096"])
        self.run([str(self.host / "simg2img"), str(sparse), str(roundtrip)])
        if SHARED.digest(roundtrip) != SHARED.digest(candidate):
            raise RuntimeError("diag1 sparse/raw super roundtrip changed bytes")
        extracted = self.stage / "candidate-logical"
        extracted.mkdir()
        self.run([str(self.host / "lpunpack"), str(roundtrip), str(extracted)])
        expected = {
            "system_a": system,
            "vendor_a": vendor,
            "product_a": source(str(self.raw_cfg["base_artifacts"]["product_a"]["path"])),
            "vendor_dlkm_a": source(
                str(self.raw_cfg["base_artifacts"]["vendor_dlkm"]["path"])
            ),
        }
        logical: dict[str, dict[str, object]] = {}
        for name, expected_path in expected.items():
            path = extracted / f"{name}.img"
            expected_record = SHARED.record(expected_path)
            self.require(path, expected_record, f"diag1 detached logical {name}")
            logical[name] = SHARED.record(path)
        for name in ("system_b", "vendor_b", "product_b", "vendor_dlkm_b"):
            path = extracted / f"{name}.img"
            if path.stat().st_size != 0:
                raise RuntimeError(f"diag1 changed empty B-slot contract: {name}")
            logical[name] = SHARED.record(path)
        return sparse, {
            "frozen_r7_raw": SHARED.record(original),
            "candidate_raw": SHARED.record(candidate),
            "candidate_sparse": SHARED.record(sparse),
            "metadata_slots_0_and_1_exact": True,
            "lp_metadata_and_extents_exact_r7": True,
            "logical_bytes_written_in_place_to_frozen_extents": copied_extents,
            "bytes_outside_system_and_vendor_extents_inherited_exact_r7": True,
            "growth_only_from_old_unallocated_space": True,
            "all_other_partition_extents_exact_r4": True,
            "sb_a_maximum_bytes": 3212836864,
            "sb_a_allocated_bytes": 2081472512,
            "sb_a_unallocated_bytes": 1131364352,
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
            sys.executable,
            str(REPO / "tools/pack_image_preserving.py"),
            "--source",
            str(self.base),
            "--output",
            str(firmware),
            "--replace",
            f"super.fex={super_sparse}",
            "--replace",
            f"vbmeta_system.fex={vbmeta_system}",
            "--replace",
            f"vbmeta_vendor.fex={vbmeta_vendor}",
            "--audit",
            str(payload_audit),
        ])
        self.run([
            sys.executable,
            str(REPO / "tools/sunxi_image_tool.py"),
            "verify",
            str(firmware),
        ], output=self.stage / "candidate-outer-verify.log")
        after = PACK.outer_payloads(firmware)
        changed = sorted(
            name for name in before
            if before[name]["sha256_stored"] != after[name]["sha256_stored"]
        )
        expected = sorted(self.raw_cfg["outer_delta"]["changed_payloads_from_base"])
        if set(before) != set(after) or len(after) != 50 or changed != expected:
            raise RuntimeError(f"unexpected diag1 outer payload delta: {changed}")
        return firmware, {
            "candidate": SHARED.record(firmware),
            "entry_count": 50,
            "changed_payloads": changed,
            "preserved_payload_count": 44,
            "all_other_payload_bytes_exact_r7": True,
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
        for name, key in (("boot.fex", "boot"), ("vendor_dlkm_a.img", "vendor_dlkm")):
            shutil.copyfile(source(str(self.raw_cfg["base_artifacts"][key]["path"])), self.stage / name)
        result = {
            "schema": 1,
            "id": self.candidate_id,
            "label": self.raw_cfg["label"],
            "status": "PACKAGED_AWAITING_FULL_OFFLINE_AUDIT",
            "decision": "PENDING_FULL_OFFLINE_AUDIT",
            "physical_status": "NOT_YET_VALIDATED",
            "physical_device_actions_performed": False,
            "flash_authorized": False,
            "elapsed_seconds": round(time.time() - self.started, 1),
            "source": {
                "tag": self.raw_cfg["source_contract"]["tag"],
                "build_id": self.raw_cfg["source_contract"]["build_id"],
                "api": self.raw_cfg["source_contract"]["api"],
                "manifest_commit": self.raw_cfg["source_contract"]["manifest_commit"],
                "repositories": self.raw_cfg["source_contract"]["repositories"],
                "targeted_modules_built": ["surfaceflinger", "libstagefright", "gralloc.apollo"],
                "kernel_rebuilt": False,
            },
            "base_r7": SHARED.record(self.base),
            "firmware": SHARED.record(firmware),
            "system": system_audit,
            "vendor": vendor_audit,
            "super": super_audit,
            "outer": outer_audit,
            "vbmeta_system": SHARED.record(vbmeta_system),
            "vbmeta_vendor": SHARED.record(vbmeta_vendor),
            "boot": {
                "candidate": SHARED.record(self.stage / "boot.fex"),
                "byte_preserved_from_r7": True,
            },
            "vendor_dlkm": {
                "candidate": SHARED.record(self.stage / "vendor_dlkm_a.img"),
                "byte_preserved_from_r7": True,
                "module_count": 22,
            },
            "kernel": SHARED.record(self.stage / "kernel-evidence/Image"),
            "diagnostic": self.raw_cfg["diagnostic"],
            "governance": self.raw_cfg["governance"],
            "allowed_semantic_delta": self.raw_cfg["allowed_semantic_delta"],
            "forbidden_changes": self.raw_cfg["forbidden_changes"],
        }
        result = SHARED.rewrite_paths(result, self.stage, self.final)
        (self.stage / "build-result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        sums = []
        for path in sorted(self.stage.iterdir()):
            if path.is_file() and path.name != "SHA256SUMS":
                sums.append(f"{SHARED.digest(path)}  {path.name}")
        (self.stage / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
        os.replace(self.stage, self.final)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--aosp", type=Path, default=DEFAULT_AOSP)
    parser.add_argument("--keep-failed", action="store_true")
    Builder(parser.parse_args()).execute()


if __name__ == "__main__":
    main()
