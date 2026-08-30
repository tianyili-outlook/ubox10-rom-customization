#!/usr/bin/env python3
"""Package diag1a by correcting only the instrumented ARM32 gralloc closure."""
from __future__ import annotations

import argparse
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
DEFAULT_CONFIG = REPO / "configs/candidates/a16-prototype-b-r7-diag1a.json"
DEFAULT_AOSP = Path("/work/src/ubox10-a16-ceiling")
DIAG1_CONFIG = REPO / "configs/candidates/a16-prototype-b-r7-diag1.json"
DIAG1_PATH = REPO / "scripts/build-a16-prototype-b-r7-diag1-candidate.py"
DIAG1_SPEC = importlib.util.spec_from_file_location("a16_b_r7_diag1_builder_for_diag1a", DIAG1_PATH)
if DIAG1_SPEC is None or DIAG1_SPEC.loader is None:
    raise RuntimeError(f"cannot import diag1 builder: {DIAG1_PATH}")
DIAG1 = importlib.util.module_from_spec(DIAG1_SPEC)
sys.modules[DIAG1_SPEC.name] = DIAG1
DIAG1_SPEC.loader.exec_module(DIAG1)

SHARED = DIAG1.SHARED
PACK = DIAG1.PACK


def source(path: str) -> Path:
    value = Path(path)
    return value if value.is_absolute() else REPO / value


def strong_undefined(path: Path) -> set[str]:
    output = subprocess.check_output(
        ["nm", "-D", "--undefined-only", "--format=posix", str(path)], text=True
    )
    return {
        fields[0].split("@", 1)[0]
        for line in output.splitlines()
        if len(fields := line.split()) >= 2 and fields[1] == "U"
    }


class Builder(DIAG1.Builder):
    def __init__(self, args: argparse.Namespace) -> None:
        base_args = argparse.Namespace(
            config=DIAG1_CONFIG, aosp=args.aosp, keep_failed=args.keep_failed
        )
        super().__init__(base_args)
        self.args = args
        self.diag1_cfg = json.loads(DIAG1_CONFIG.read_text(encoding="utf-8"))
        self.raw_cfg = json.loads(args.config.read_text(encoding="utf-8"))
        self.candidate_id = str(self.raw_cfg["id"])
        self.cfg["id"] = self.candidate_id
        self.cfg["status"] = self.raw_cfg["status"]
        self.cfg["base_candidate"] = self.raw_cfg["base_candidate"]
        self.cfg["_continuation"] = self.raw_cfg
        self.final = REPO / "out/candidates" / self.candidate_id
        self.stage = self.final.parent / f".{self.candidate_id}.staging-{uuid.uuid4().hex}"
        self.log = self.stage / "logs/01-commands.log"
        self.base = source(str(self.raw_cfg["base_candidate"]["path"]))
        self.diag1 = REPO / "out/candidates/a16-prototype-b-r7-diag1"
        self.started = time.time()
        self.arm32_closure: dict[str, object] = {}

    def setup(self) -> None:
        if self.final.exists():
            raise RuntimeError(f"refusing to overwrite existing candidate: {self.final}")
        if self.raw_cfg["status"] != "INSTRUMENTATION_ONLY_BOOT_COMPATIBILITY_CORRECTION_AUTHORIZED":
            raise RuntimeError("diag1a is not authorized as a boot-compatibility correction")
        governance = self.raw_cfg["governance"]
        if governance["r8_authorized"] is not False or governance["gate3"] != "HOLD":
            raise RuntimeError("diag1a must retain Gate 3 HOLD and must not authorize r8")
        self.stage.mkdir(parents=True)
        self.require(self.base, self.raw_cfg["base_candidate"], "immutable failed diag1 outer")
        self.require(self.rollback, self.r4["rollback"], "Android 12 rollback")
        for name, spec in self.raw_cfg["base_artifacts"].items():
            self.require(source(str(spec["path"])), spec, f"exact diag1 artifact {name}")

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

        for key in ("overlay", "boot_compatibility_overlay"):
            overlay = REPO / str(self.raw_cfg["source_contract"][key])
            checked = subprocess.check_output(
                [str(overlay / "prepare.sh"), "check", str(self.args.aosp)], text=True
            )
            if "source state: PATCHED" not in checked:
                raise RuntimeError(f"source overlay is not exactly applied: {key}")

        for relative, contract in self.raw_cfg["source_contract"]["files"].items():
            path = self.args.aosp / relative
            self.require(
                path,
                {"size": path.stat().st_size, "sha256": contract["patched_sha256"]},
                f"diag1 source {relative}",
            )
        for relative, contract in self.raw_cfg["source_contract"]["boot_compatibility_files"].items():
            path = self.args.aosp / relative
            self.require(
                path,
                {"size": path.stat().st_size, "sha256": contract["patched_sha256"]},
                f"diag1a source {relative}",
            )

        delta = self.raw_cfg["diag1_delta"]
        failed = source(str(delta["failed_gralloc32"]["path"]))
        corrected = source(str(delta["corrected_gralloc32"]["path"]))
        self.require(failed, delta["failed_gralloc32"], "failed diag1 ARM32 gralloc")
        self.require(corrected, delta["corrected_gralloc32"], "corrected diag1a ARM32 gralloc")
        symbol = "_ZNSt3__122__libcpp_verbose_abortEPKcz"
        failed_imports = strong_undefined(failed)
        corrected_imports = strong_undefined(corrected)
        if symbol not in failed_imports:
            raise RuntimeError("failed diag1 no longer proves the verbose-abort import")
        if symbol in corrected_imports or "abort" not in corrected_imports:
            raise RuntimeError("corrected ARM32 gralloc does not preserve abort back-deploy semantics")
        before = DIAG1.elf_contract(failed)
        after = DIAG1.elf_contract(corrected)
        for field in ("elf_class", "architecture", "soname", "dt_needed", "strong_exports"):
            if before[field] != after[field]:
                raise RuntimeError(f"ARM32 gralloc compatibility correction changed {field}")
        if b"UBOX_R7_DIAG1" not in corrected.read_bytes():
            raise RuntimeError("corrected ARM32 gralloc lost diagnostic instrumentation")

        for name, expected in delta["preserved_runtime_files"].items():
            if name == "/system/bin/surfaceflinger":
                path = self.diag1 / "diag1-surfaceflinger"
            elif name == "/system/lib64/libstagefright.so":
                path = self.diag1 / "diag1-libstagefright64"
            else:
                path = self.diag1 / "diag1-gralloc64"
            if SHARED.digest(path) != expected:
                raise RuntimeError(f"preserved diag1 runtime identity changed: {name}")

        self.run_arm32_closure(failed, corrected)

        shutil.copytree(self.diag1 / "kernel-evidence", self.stage / "kernel-evidence")
        for name in (
            "final-build-variables.txt",
            "mali-intake.json",
            "active-product-build.prop.r5",
            "runtime-product-source-audit.json",
            "boringssl_self_test64",
        ):
            shutil.copyfile(self.diag1 / name, self.stage / name)
        for name in ("surfaceflinger", "libstagefright64", "gralloc64"):
            shutil.copyfile(self.diag1 / f"diag1-{name}", self.stage / f"diag1a-{name}")
        for name in ("surfaceflinger", "libstagefright64", "gralloc32", "gralloc64"):
            shutil.copyfile(self.diag1 / f"r7-{name}", self.stage / f"r7-{name}")

    def run_arm32_closure(self, failed: Path, corrected: Path) -> None:
        checker = REPO / "scripts/check-a16-prototype-b-r7-graphics.py"
        root = self.diag1 / "offline-audit/root"
        common = [
            sys.executable,
            str(checker),
            "--architecture", "arm32",
            "--mapper", str(REPO / "out/candidates/a16-prototype-b-r7/retained-mapper32"),
            "--system-lib", str(self.args.aosp / "out-ceiling-b1/target/product/ubox10_ceiling_arm64/system/lib"),
            "--runtime-lib", str(root / "apex/com.android.runtime/lib/bionic"),
            "--vndk-lib", str(root / "apex/com.android.vndk.v31/lib"),
            "--linker-config", str(self.diag1 / "offline-audit/linker-generated/ld.config.txt"),
        ]
        corrected_json = self.stage / "arm32-graphics-closure-prepack.json"
        self.run(
            common + ["--gralloc", str(corrected), "--output", str(corrected_json)],
            output=self.stage / "arm32-graphics-closure-prepack.log",
        )
        failed_json = self.stage / "diag1-arm32-graphics-closure-failure.json"
        self.run(
            common + ["--gralloc", str(failed), "--output", str(failed_json)],
            output=self.stage / "diag1-arm32-graphics-closure-failure.log",
            allowed={1},
        )
        passed = json.loads(corrected_json.read_text(encoding="utf-8"))
        rejected = json.loads(failed_json.read_text(encoding="utf-8"))
        missing = "_ZNSt3__122__libcpp_verbose_abortEPKcz"
        if (
            passed["decision"] != "PASS_EXACT_ARM32_MAPPER_GRALLOC_SPHAL_CLOSURE"
            or passed["gralloc"]["unmatched_count"] != 0
            or passed["gralloc"]["libcpp_verbose_abort_import"]
        ):
            raise RuntimeError("corrected ARM32 prepack closure did not pass")
        if rejected["gralloc"]["unmatched_strong_imports"] != [missing]:
            raise RuntimeError("failed diag1 closure no longer isolates verbose-abort")
        self.arm32_closure = {
            "failed_diag1": rejected,
            "corrected_diag1a": passed,
        }

    def prepare_system(self) -> tuple[Path, dict[str, object]]:
        spec = self.raw_cfg["base_artifacts"]["system_a"]
        original = source(str(spec["path"]))
        system = self.stage / "system_a.img"
        shutil.copyfile(original, system)
        self.require(system, spec, "byte-identical diag1 system_a")
        return system, {
            "base_diag1": SHARED.record(original),
            "candidate": SHARED.record(system),
            "byte_preserved_from_diag1": True,
            "tree_delta": {"added": [], "removed": [], "changed": []},
            "avb_byte_preserved": True,
        }

    def replace_arm32_gralloc(self, vendor: Path) -> dict[str, object]:
        contract = self.raw_cfg["runtime_files"]["gralloc32"]
        delta = self.raw_cfg["diag1_delta"]
        internal_path = "/lib/hw/gralloc.apollo.so"
        parent = str(Path(internal_path).parent)
        parent_times = self.inode_times(self.debugfs(vendor, f"stat {parent}", capture=True))
        old = self.stage / "diag1-gralloc32"
        new = self.stage / "diag1a-gralloc32"
        self.debugfs(vendor, f"dump -p {internal_path} {old}")
        self.require(old, delta["failed_gralloc32"], "installed failed diag1 ARM32 gralloc")
        source_binary = source(str(delta["corrected_gralloc32"]["path"]))
        self.debugfs(vendor, f"rm {internal_path}")
        self.debugfs(vendor, f"write {source_binary} {internal_path}")
        self.debugfs(vendor, f"set_inode_field {internal_path} mode 010{contract['mode']}")
        self.debugfs(vendor, f"set_inode_field {internal_path} uid {contract['uid']}")
        self.debugfs(vendor, f"set_inode_field {internal_path} gid {contract['gid']}")
        for field in ("ctime", "atime", "mtime", "crtime"):
            self.debugfs(vendor, f"set_inode_field {internal_path} {field} {contract[field]}")
        self.debugfs(
            vendor,
            f'ea_set {internal_path} security.selinux "{contract["selinux"]}\\000"',
        )
        self.restore_times(vendor, parent, parent_times)
        self.debugfs(vendor, f"dump -p {internal_path} {new}")
        self.require(new, contract, "installed corrected diag1a ARM32 gralloc")
        inode = self.debugfs(vendor, f"stat {internal_path}", capture=True)
        attrs = self.debugfs(vendor, f"ea_list {internal_path}", capture=True)
        if (
            f"Mode:  {contract['mode']}" not in inode
            or f"User:     {contract['uid']}" not in inode
            or f"Group:  {contract['gid']:4d}" not in inode
            or contract["selinux"] not in attrs
        ):
            raise RuntimeError("installed corrected ARM32 gralloc inode contract changed")
        return {
            "partition_path": contract["partition_path"],
            "diag1": SHARED.record(old),
            "diag1a": SHARED.record(new),
            "elf_class": contract["elf_class"],
            "architecture": contract["architecture"],
            "dt_needed_preserved": True,
            "soname_preserved": True,
            "strong_exports_preserved": True,
            "removed_strong_import": "_ZNSt3__122__libcpp_verbose_abortEPKcz",
            "added_strong_import": "abort",
            "unmatched_strong_import_count": 0,
            "diagnostic_marker_present": True,
            "inode": {
                "mode": contract["mode"],
                "uid": contract["uid"],
                "gid": contract["gid"],
                "selinux": contract["selinux"],
            },
        }

    def prepare_vendor(self) -> tuple[Path, dict[str, object]]:
        spec = self.raw_cfg["base_artifacts"]["vendor_a"]
        original = source(str(spec["path"]))
        vendor = self.stage / "vendor_a.img"
        shutil.copyfile(original, vendor)
        self.require(vendor, spec, "exact failed diag1 vendor_a")
        with self.deterministic_ext4_time():
            self.run([sys.executable, str(self.avbtool), "erase_footer", "--image", str(vendor)])
            self.run(["e2fsck", "-fn", str(vendor)])
            replacement = self.replace_arm32_gralloc(vendor)
            self.run(["e2fsck", "-fy", str(vendor)], allowed={0, 1})
            self.run(["e2fsck", "-fn", str(vendor)])
        avb = self.cfg["avb"]["vendor"]
        self.run([
            sys.executable, str(self.avbtool), "add_hashtree_footer",
            "--image", str(vendor),
            "--partition_name", "vendor",
            "--partition_size", str(avb["partition_size"]),
            "--hash_algorithm", "sha256",
            "--salt", avb["salt"],
            "--prop", f"com.android.build.vendor.fingerprint:{avb['fingerprint']}",
            "--prop", f"com.android.build.vendor.os_version:{avb['os_version']}",
        ])
        self.verify_avb_partition(vendor, "vendor", None)
        return vendor, {
            "base_diag1": SHARED.record(original),
            "candidate": SHARED.record(vendor),
            "tree_delta": {
                "added": [],
                "removed": [],
                "changed": ["lib/hw/gralloc.apollo.so"],
            },
            "replaced": {"gralloc32": replacement},
            "ext4": "PASS",
            "avb_hashtree_fec": "PASS",
        }

    def make_vbmeta(self, image: Path, partition: str) -> Path:
        if partition == "system":
            spec = self.raw_cfg["base_artifacts"]["vbmeta_system"]
            output = self.stage / "vbmeta_system.fex"
            shutil.copyfile(source(str(spec["path"])), output)
            self.require(output, spec, "byte-identical diag1 vbmeta_system")
            return output
        return super().make_vbmeta(image, partition)

    def build_super(self, system: Path, vendor: Path) -> tuple[Path, dict[str, object]]:
        spec = self.raw_cfg["base_artifacts"]["super_raw"]
        original = source(str(spec["path"]))
        candidate = self.stage / "super.raw.img"
        self.run(["cp", "--reflink=auto", str(original), str(candidate)])
        old_text = self.stage / "diag1-lpdump.txt"
        self.run([str(self.host / "lpdump"), str(original)], output=old_text)
        extents = DIAG1.lpdump_linear_extents(old_text.read_text(encoding="utf-8"))
        sector_size = 512
        vendor_extents = extents.get("vendor_a", [])
        capacity = sum(end - start for start, end in vendor_extents) * sector_size
        if capacity != vendor.stat().st_size:
            raise RuntimeError("diag1a vendor bytes do not exactly fill frozen diag1 extents")
        with candidate.open("r+b", buffering=0) as output, vendor.open("rb", buffering=0) as input_file:
            for start, end in vendor_extents:
                remaining = (end - start) * sector_size
                output.seek(start * sector_size)
                while remaining:
                    chunk = input_file.read(min(8 * 1024 * 1024, remaining))
                    if not chunk:
                        raise RuntimeError("short read while copying diag1a vendor")
                    output.write(chunk)
                    remaining -= len(chunk)
            if input_file.read(1):
                raise RuntimeError("trailing bytes while copying diag1a vendor")

        old_json = self.stage / "diag1-lpdump.json"
        new_json = self.stage / "candidate-lpdump.json"
        slot1 = self.stage / "candidate-lpdump-slot1.json"
        self.run([str(self.host / "lpdump"), "-j", str(original)], output=old_json)
        self.run([str(self.host / "lpdump"), "-j", str(candidate)], output=new_json)
        self.run([str(self.host / "lpdump"), "-s", "1", "-j", str(candidate)], output=slot1)
        base_metadata = json.loads(old_json.read_text(encoding="utf-8"))
        if base_metadata != json.loads(new_json.read_text(encoding="utf-8")):
            raise RuntimeError("diag1a changed exact diag1 LP metadata or extents")
        if base_metadata != json.loads(slot1.read_text(encoding="utf-8")):
            raise RuntimeError("diag1a LP metadata slots differ")

        sparse = self.stage / "super.fex"
        roundtrip = self.stage / "super-sparse-roundtrip.raw.img"
        self.run([str(self.host / "img2simg"), str(candidate), str(sparse), "4096"])
        self.run([str(self.host / "simg2img"), str(sparse), str(roundtrip)])
        if SHARED.digest(roundtrip) != SHARED.digest(candidate):
            raise RuntimeError("diag1a sparse/raw super roundtrip changed bytes")
        extracted = self.stage / "candidate-logical"
        extracted.mkdir()
        self.run([str(self.host / "lpunpack"), str(roundtrip), str(extracted)])
        expected = {
            "system_a": system,
            "vendor_a": vendor,
            "product_a": source(str(self.raw_cfg["base_artifacts"]["product_a"]["path"])),
            "vendor_dlkm_a": source(str(self.raw_cfg["base_artifacts"]["vendor_dlkm"]["path"])),
        }
        logical: dict[str, dict[str, object]] = {}
        for name, expected_path in expected.items():
            path = extracted / f"{name}.img"
            self.require(path, SHARED.record(expected_path), f"diag1a detached logical {name}")
            logical[name] = SHARED.record(path)
        for name in ("system_b", "vendor_b", "product_b", "vendor_dlkm_b"):
            path = extracted / f"{name}.img"
            if path.stat().st_size != 0:
                raise RuntimeError(f"diag1a changed empty B-slot contract: {name}")
            logical[name] = SHARED.record(path)
        return sparse, {
            "frozen_diag1_raw": SHARED.record(original),
            "candidate_raw": SHARED.record(candidate),
            "candidate_sparse": SHARED.record(sparse),
            "metadata_slots_0_and_1_exact": True,
            "lp_metadata_and_extents_exact_diag1": True,
            "logical_vendor_written_in_place_to_frozen_extents": [list(item) for item in vendor_extents],
            "bytes_outside_vendor_extents_inherited_exact_diag1": True,
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
            "--source", str(self.base),
            "--output", str(firmware),
            "--replace", f"super.fex={super_sparse}",
            "--replace", f"vbmeta_vendor.fex={vbmeta_vendor}",
            "--audit", str(payload_audit),
        ])
        self.run([
            sys.executable, str(REPO / "tools/sunxi_image_tool.py"),
            "verify", str(firmware),
        ], output=self.stage / "candidate-outer-verify.log")
        after = PACK.outer_payloads(firmware)
        changed = sorted(
            name for name in before
            if before[name]["sha256_stored"] != after[name]["sha256_stored"]
        )
        expected = sorted(self.raw_cfg["outer_delta"]["changed_payloads_from_base"])
        if set(before) != set(after) or len(after) != 50 or changed != expected:
            raise RuntimeError(f"unexpected diag1a outer payload delta: {changed}")
        return firmware, {
            "candidate": SHARED.record(firmware),
            "entry_count": 50,
            "changed_payloads": changed,
            "preserved_payload_count": 46,
            "all_other_payload_bytes_exact_diag1": True,
            "imagewty_verify": "PASS",
            "top_level_vbmeta_byte_preserved": before["vbmeta.fex"] == after["vbmeta.fex"],
            "vbmeta_system_byte_preserved": before["vbmeta_system.fex"] == after["vbmeta_system.fex"],
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
                "targeted_modules_built": ["device_gralloc.apollo_32_all_targets"],
                "architecture_scope": "ARM32_GRALLOC_ONLY",
                "android_system_rebuilt": False,
                "kernel_rebuilt": False,
            },
            "base_diag1": SHARED.record(self.base),
            "firmware": SHARED.record(firmware),
            "system": system_audit,
            "vendor": vendor_audit,
            "super": super_audit,
            "outer": outer_audit,
            "vbmeta_system": SHARED.record(vbmeta_system),
            "vbmeta_vendor": SHARED.record(vbmeta_vendor),
            "boot": {"candidate": SHARED.record(self.stage / "boot.fex"), "byte_preserved_from_diag1": True},
            "vendor_dlkm": {"candidate": SHARED.record(self.stage / "vendor_dlkm_a.img"), "byte_preserved_from_diag1": True, "module_count": 22},
            "kernel": SHARED.record(self.stage / "kernel-evidence/Image"),
            "root_cause": self.raw_cfg["root_cause"],
            "compatibility_mechanism": self.raw_cfg["source_contract"]["boot_compatibility_mechanism"],
            "arm32_graphics_closure": self.arm32_closure,
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
