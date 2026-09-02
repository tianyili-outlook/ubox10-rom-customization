#!/usr/bin/env python3
"""Build a16-dev-audio-r1 from exact compat1a with one ARM32 audio wrapper delta."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "configs/candidates/a16-dev-audio-r1.json"
AOSP = Path("/work/src/ubox10-a16-ceiling")
BASE_PATH = REPO / "scripts/build-a16-prototype-b-r7-hevc-abi-compat1-sdr-shadow-candidate.py"
SPEC = importlib.util.spec_from_file_location("compat1_builder_for_audio_r1", BASE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import builder: {BASE_PATH}")
BASE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = BASE
SPEC.loader.exec_module(BASE)
SHARED = BASE.SHARED
DIAG1 = BASE.DIAG1


def source(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO / path


class Builder(BASE.Builder):
    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__(args)
        self.compat1a = REPO / "out/candidates/a16-prototype-b-r7-hevc-abi-compat1a-sdr-shadow-fd"

    def setup(self) -> None:
        if self.final.exists():
            raise RuntimeError(f"refusing to overwrite existing candidate: {self.final}")
        gov = self.raw_cfg["governance"]
        if (self.raw_cfg["status"] != "DEVELOPMENT_AUDIO_COMPATIBILITY_AUTHORIZED"
                or gov["gate3"] != "PASS_WITH_EXPLICIT_USER_WAIVER_CLOSED"
                or gov["r8_authorized"] or gov["r8_built"]):
            raise RuntimeError("audio-r1 development governance changed")
        self.stage.mkdir(parents=True)
        self.require(self.base, self.raw_cfg["base_candidate"], "exact compat1a outer")
        for name, record in self.raw_cfg["base_artifacts"].items():
            self.require(source(record["path"]), record, f"exact compat1a artifact {name}")

        contract = self.raw_cfg["source_contract"]
        revisions = {
            ".repo/manifests": contract["manifest_commit"],
            "hardware/interfaces": contract["hardware_interfaces_commit"],
            "system/libfmq": contract["system_libfmq_commit"],
        }
        for relative, expected in revisions.items():
            actual = subprocess.check_output(
                ["git", "-C", str(self.args.aosp / relative), "rev-parse", "HEAD"], text=True
            ).strip()
            if actual != expected:
                raise RuntimeError(f"source revision changed: {relative}={actual}")
        state = subprocess.check_output([
            str(REPO / contract["overlay"] / "prepare.sh"), "check", str(self.args.aosp)
        ], text=True)
        if "source state: PATCHED" not in state:
            raise RuntimeError("audio-r1 source overlay is not exact")

        change = self.raw_cfg["runtime_change"]
        new = Path(change["source_path"])
        self.require(new, change["candidate"], "audio-r1 ARM32 build output")
        old = self.stage / "compat1a-audio-impl.so"
        self.debugfs(source(self.raw_cfg["base_artifacts"]["vendor_a"]["path"]),
                     f"dump -p {change['internal_path']} {old}")
        self.require(old, change["baseline"], "compat1a audio implementation")
        before, after = DIAG1.elf_contract(old), DIAG1.elf_contract(new)
        for field in ("elf_class", "architecture", "soname", "dt_needed", "strong_exports"):
            if before[field] != after[field]:
                raise RuntimeError(f"audio-r1 changed ELF contract: {field}")
        symbols = subprocess.check_output(
            ["nm", "-D", "--undefined-only", str(new)], text=True
        )
        if "__libcpp_verbose_abort" in symbols or "details5checkEbPKc" in symbols:
            raise RuntimeError("audio-r1 retains a post-VNDK31 strong import")
        shutil.copyfile(new, self.stage / "audio-r1-audio-impl.so")

        shutil.copytree(self.compat1a / "kernel-evidence", self.stage / "kernel-evidence")
        for name in ("final-build-variables.txt", "mali-intake.json",
                     "active-product-build.prop.r5", "runtime-product-source-audit.json",
                     "boringssl_self_test64"):
            shutil.copyfile(self.compat1a / name, self.stage / name)
        for name, record in self.raw_cfg["preserved_runtime"].items():
            item = self.compat1a / record["candidate_file"]
            self.require(item, record, f"preserved compat1a {name}")
            shutil.copyfile(item, self.stage / f"compat1a-{name}")

    def prepare_system(self) -> tuple[Path, dict[str, object]]:
        spec = self.raw_cfg["base_artifacts"]["system_a"]
        original = source(spec["path"])
        system = self.stage / "system_a.img"
        shutil.copyfile(original, system)
        self.require(system, spec, "byte-preserved compat1a system")
        self.run(["e2fsck", "-fn", str(system)])
        self.verify_avb_partition(system, "system", self.cfg["avb"]["system"]["key_relative"])
        return system, {
            "base_compat1a": SHARED.record(original), "candidate": SHARED.record(system),
            "tree_delta": {"added": [], "removed": [], "changed": []},
            "byte_preserved_from_compat1a": True, "ext4": "PASS", "avb": "PASS",
        }

    def replace_audio(self, image: Path) -> dict[str, object]:
        change = self.raw_cfg["runtime_change"]
        internal = change["internal_path"]
        parent = "/lib/hw"
        parent_times = self.inode_times(self.debugfs(image, f"stat {parent}", capture=True))
        old = self.stage / "installed-compat1a-audio-impl.so"
        self.debugfs(image, f"dump -p {internal} {old}")
        self.require(old, change["baseline"], "installed compat1a audio implementation")
        self.debugfs(image, f"rm {internal}")
        self.debugfs(image, f"write {change['source_path']} {internal}")
        self.debugfs(image, f"set_inode_field {internal} mode 010{change['mode']}")
        self.debugfs(image, f"set_inode_field {internal} uid {change['uid']}")
        self.debugfs(image, f"set_inode_field {internal} gid {change['gid']}")
        for field in ("ctime", "atime", "mtime", "crtime"):
            self.debugfs(image, f"set_inode_field {internal} {field} {change[field]}")
        self.debugfs(image, f'ea_set {internal} security.selinux "{change["selinux"]}\\000"')
        self.restore_times(image, parent, parent_times)
        new = self.stage / "installed-audio-r1-audio-impl.so"
        self.debugfs(image, f"dump -p {internal} {new}")
        self.require(new, change["candidate"], "installed audio-r1 implementation")
        return {
            "partition_path": change["partition_path"], "reason": change["reason"],
            "compat1a": SHARED.record(old), "audio_r1": SHARED.record(new),
            "elf_class": change["elf_class"], "machine": change["machine"],
            "soname_preserved": True, "dt_needed_preserved": True,
            "strong_exports_preserved": False, "required_hidl_exports_preserved": True,
            "strong_export_surface_classification":
                "CURRENT_TOOLCHAIN_TEMPLATE_SURFACE_CHANGED_ZERO_REQUIRED_HIDL_EXPORT_LOSS",
            "exact_namespace_unmatched_imports": 0,
        }

    def prepare_vendor(self) -> tuple[Path, dict[str, object]]:
        spec = self.raw_cfg["base_artifacts"]["vendor_a"]
        original = source(spec["path"])
        vendor = self.stage / "vendor_a.img"
        shutil.copyfile(original, vendor)
        self.require(vendor, spec, "exact compat1a vendor")
        with self.deterministic_ext4_time():
            self.run([sys.executable, str(self.avbtool), "erase_footer", "--image", str(vendor)])
            self.run(["e2fsck", "-fn", str(vendor)])
            replacement = self.replace_audio(vendor)
            self.run(["e2fsck", "-fy", str(vendor)], allowed={0, 1})
            self.run(["e2fsck", "-fn", str(vendor)])
        avb = self.cfg["avb"]["vendor"]
        self.run([sys.executable, str(self.avbtool), "add_hashtree_footer", "--image", str(vendor),
                  "--partition_name", "vendor", "--partition_size", str(avb["partition_size"]),
                  "--hash_algorithm", "sha256", "--salt", avb["salt"],
                  "--prop", f"com.android.build.vendor.fingerprint:{avb['fingerprint']}",
                  "--prop", f"com.android.build.vendor.os_version:{avb['os_version']}"])
        self.verify_avb_partition(vendor, "vendor", None)
        return vendor, {
            "base_compat1a": SHARED.record(original), "candidate": SHARED.record(vendor),
            "tree_delta": {"added": [], "removed": [],
                           "changed": ["lib/hw/android.hardware.audio@7.0-impl.so"]},
            "replaced": {"audio_impl32": replacement}, "ext4": "PASS", "avb": "PASS",
        }

    def build_super(self, system: Path, vendor: Path) -> tuple[Path, dict[str, object]]:
        sparse, audit = DIAG1.Builder.build_super(self, system, vendor)
        for item in (self.stage / "super-sparse-roundtrip.raw.img",
                     self.stage / "candidate-logical/system_a.img"):
            item.unlink()
        audit["base_compat1a_raw"] = audit.pop("frozen_r7_raw")
        audit["lp_metadata_and_extents_exact_compat1a"] = audit.pop(
            "lp_metadata_and_extents_exact_r7")
        audit["bytes_outside_changed_extents_exact_compat1a"] = audit.pop(
            "bytes_outside_system_and_vendor_extents_inherited_exact_r7")
        return sparse, audit

    def finish(self, firmware: Path, system_audit: dict[str, object],
               vendor_audit: dict[str, object], super_audit: dict[str, object],
               outer_audit: dict[str, object], vbmeta_system: Path,
               vbmeta_vendor: Path) -> None:
        for name, key in (("boot.fex", "boot"), ("vendor_dlkm_a.img", "vendor_dlkm")):
            shutil.copyfile(source(self.raw_cfg["base_artifacts"][key]["path"]), self.stage / name)
        outer_audit["all_other_payload_bytes_exact_compat1a"] = outer_audit.pop(
            "all_other_payload_bytes_exact_r7")
        result = {
            "schema": 1, "id": self.candidate_id, "label": self.raw_cfg["label"],
            "status": "PACKAGED_AWAITING_FULL_OFFLINE_AUDIT",
            "decision": "PENDING_FULL_OFFLINE_AUDIT", "physical_status": "NOT_YET_VALIDATED",
            "physical_device_actions_performed": False, "flash_performed": False,
            "elapsed_seconds": round(time.time() - self.started, 1),
            "source": {**self.raw_cfg["source_contract"],
                       "targeted_modules_built": ["android.hardware.audio@7.0-impl_32"],
                       "kernel_rebuilt": False, "surfaceflinger_rebuilt": False},
            "base_compat1a": SHARED.record(self.base), "firmware": SHARED.record(firmware),
            "system": system_audit, "vendor": vendor_audit, "super": super_audit,
            "outer": outer_audit, "vbmeta_system": SHARED.record(vbmeta_system),
            "vbmeta_vendor": SHARED.record(vbmeta_vendor),
            "boot": {"candidate": SHARED.record(self.stage / "boot.fex"),
                     "byte_preserved_from_compat1a": True},
            "vendor_dlkm": {"candidate": SHARED.record(self.stage / "vendor_dlkm_a.img"),
                            "byte_preserved_from_compat1a": True, "module_count": 22},
            "kernel": SHARED.record(self.stage / "kernel-evidence/Image"),
            "runtime_delta": vendor_audit["replaced"],
            "runtime_preserved": self.raw_cfg["preserved_runtime"],
            "governance": self.raw_cfg["governance"],
        }
        result = SHARED.rewrite_paths(result, self.stage, self.final)
        (self.stage / "build-result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        sums = [f"{SHARED.digest(path)}  {path.name}" for path in sorted(self.stage.iterdir())
                if path.is_file() and path.name != "SHA256SUMS"]
        (self.stage / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
        os.replace(self.stage, self.final)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--aosp", type=Path, default=AOSP)
    parser.add_argument("--keep-failed", action="store_true")
    Builder(parser.parse_args()).execute()


if __name__ == "__main__":
    main()
