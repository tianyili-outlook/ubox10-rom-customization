#!/usr/bin/env python3
"""Package the exact SDR YV12 Mali metadata ABI shadow repair candidate."""
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
DEFAULT_CONFIG = REPO / "configs/candidates/a16-prototype-b-r7-hevc-abi-compat1-sdr-shadow.json"
DEFAULT_AOSP = Path("/work/src/ubox10-a16-ceiling")
DIAG3A_CONFIG = REPO / "configs/candidates/a16-prototype-b-r7-diag3a-private-buffer-metadata.json"
DIAG3A_BUILDER = REPO / "scripts/build-a16-prototype-b-r7-diag3a-private-buffer-metadata-candidate.py"
SPEC = importlib.util.spec_from_file_location("r7_diag3a_builder_for_compat1", DIAG3A_BUILDER)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import diag3a builder: {DIAG3A_BUILDER}")
DIAG3A = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = DIAG3A
SPEC.loader.exec_module(DIAG3A)
SHARED = DIAG3A.SHARED
DIAG1 = DIAG3A.DIAG3.DIAG1


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


class Builder(DIAG3A.DIAG3.Builder):
    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__(args)
        self.diag3a_cfg = json.loads(DIAG3A_CONFIG.read_text(encoding="utf-8"))
        self.diag3a = REPO / "out/candidates/a16-prototype-b-r7-diag3a-private-buffer-metadata"

    def setup(self) -> None:
        if self.final.exists():
            raise RuntimeError(f"refusing to overwrite existing candidate: {self.final}")
        governance = self.raw_cfg["governance"]
        if (
            self.raw_cfg["status"] != "EXPERIMENTAL_REPAIR_AUTHORIZED"
            or governance["gate3"] != "HOLD"
            or governance["r8_authorized"] is not False
            or governance["development_branch_created"] is not False
        ):
            raise RuntimeError("compat1 governance is not exact experimental non-r8 Gate-3 HOLD")
        self.stage.mkdir(parents=True)
        self.require(self.base, self.raw_cfg["base_candidate"], "exact diag3a outer")
        self.require(self.rollback, self.r4["rollback"], "Android 12 rollback")
        for name, record in self.raw_cfg["base_artifacts"].items():
            self.require(source(record["path"]), record, f"exact diag3a artifact {name}")

        contract = self.raw_cfg["source_contract"]
        actual = subprocess.check_output(
            ["git", "-C", str(self.args.aosp / "external/skia"), "rev-parse", "HEAD"], text=True
        ).strip()
        if actual != contract["external_skia_commit"]:
            raise RuntimeError(f"external/skia revision changed: {actual}")
        manifest = subprocess.check_output(
            ["git", "-C", str(self.args.aosp / ".repo/manifests"), "rev-parse", "HEAD"], text=True
        ).strip()
        if manifest != contract["manifest_commit"]:
            raise RuntimeError(f"manifest revision changed: {manifest}")
        if SHARED.digest(DIAG3A_CONFIG) != contract["diag3a_config_sha256"]:
            raise RuntimeError("inherited diag3a config identity changed")
        overlay = REPO / contract["overlay"]
        state = subprocess.check_output(
            [str(overlay / "prepare.sh"), "check", str(self.args.aosp)], text=True
        )
        if "source state: PATCHED" not in state:
            raise RuntimeError("compat1 source overlay is not exactly applied")
        for relative, record in contract["files"].items():
            self.require(
                self.args.aosp / relative,
                {"size": record["size"], "sha256": record["sha256"]},
                f"compat1 exact source {relative}",
            )

        change = self.raw_cfg["runtime_change"]
        new = Path(change["source_path"])
        old = self.diag3a / "diag3a-surfaceflinger"
        self.require(new, change, "compat1 surfaceflinger build output")
        self.require(
            old,
            {"size": change["diag3a_size"], "sha256": change["diag3a_sha256"]},
            "exact diag3a surfaceflinger",
        )
        before, after = DIAG1.elf_contract(old), DIAG1.elf_contract(new)
        for field in ("elf_class", "architecture", "soname", "dt_needed", "strong_exports"):
            if before[field] != after[field]:
                raise RuntimeError(f"compat1 changed SurfaceFlinger ELF contract: {field}")
        added = strong_undefined(new) - strong_undefined(old)
        removed = strong_undefined(old) - strong_undefined(new)
        if removed or added != set(change["added_strong_imports"]):
            raise RuntimeError(f"compat1 unexpected strong-import delta: added={added} removed={removed}")
        data = new.read_bytes()
        for marker in (b"UBOX_R7_DIAG1", b"UBOX_R7_DIAG3", b"UBOX_R7_COMPAT1",
                       b"Failed to create a valid texture."):
            if marker not in data:
                raise RuntimeError(f"compat1 SurfaceFlinger lost required marker/fatal: {marker!r}")

        shutil.copyfile(old, self.stage / "diag3a-surfaceflinger")
        shutil.copyfile(new, self.stage / "compat1-surfaceflinger")
        for name, record in self.raw_cfg["preserved_runtime_files"].items():
            base = self.diag3a / record["candidate_file"]
            self.require(base, record, f"exact preserved diag3a runtime {name}")
            output = Path(
                "/work/src/ubox10-a16-ceiling/out-ceiling-b1/target/product/ubox10_ceiling_arm64"
            ) / record["path"].lstrip("/")
            if record["path"].startswith("/vendor/"):
                output = Path(
                    "/work/src/ubox10-a16-ceiling/out-ceiling-b1/target/product/"
                    "ubox10_ceiling_arm64/system"
                ) / record["path"].lstrip("/")
            self.require(output, record, f"byte-preserved build output {name}")
            shutil.copyfile(base, self.stage / f"diag3a-{name}")
            shutil.copyfile(output, self.stage / f"compat1-{name}")

        evidence = Path(self.raw_cfg["physical_evidence"]["path"])
        sums = evidence / "SHA256SUMS"
        if not sums.is_file():
            raise RuntimeError("diag3a AVC/HEVC physical evidence is unavailable")
        for line in sums.read_text(encoding="utf-8").splitlines():
            if line.strip():
                expected, relative = line.split(maxsplit=1)
                item = evidence / relative.lstrip("* ")
                if not item.is_file() or SHARED.digest(item) != expected.upper():
                    raise RuntimeError(f"physical evidence changed: {relative}")

        shutil.copytree(self.diag3a / "kernel-evidence", self.stage / "kernel-evidence")
        for item in (
            "final-build-variables.txt", "mali-intake.json", "active-product-build.prop.r5",
            "runtime-product-source-audit.json", "boringssl_self_test64",
        ):
            shutil.copyfile(self.diag3a / item, self.stage / item)

    def replace_surfaceflinger(self, image: Path) -> dict[str, object]:
        change = self.raw_cfg["runtime_change"]
        internal = "/system/bin/surfaceflinger"
        parent_times = self.inode_times(self.debugfs(image, "stat /system/bin", capture=True))
        installed_old = self.stage / "installed-diag3a-surfaceflinger"
        self.debugfs(image, f"dump -p {internal} {installed_old}")
        self.require(
            installed_old,
            {"size": change["diag3a_size"], "sha256": change["diag3a_sha256"]},
            "installed exact diag3a surfaceflinger",
        )
        self.debugfs(image, f"rm {internal}")
        self.debugfs(image, f"write {change['source_path']} {internal}")
        self.debugfs(image, f"set_inode_field {internal} mode 010{change['mode']}")
        self.debugfs(image, f"set_inode_field {internal} uid {change['uid']}")
        self.debugfs(image, f"set_inode_field {internal} gid {change['gid']}")
        for field in ("ctime", "atime", "mtime", "crtime"):
            self.debugfs(image, f"set_inode_field {internal} {field} {change[field]}")
        self.debugfs(image, f'ea_set {internal} security.selinux "{change["selinux"]}\\000"')
        self.restore_times(image, "/system/bin", parent_times)
        installed_new = self.stage / "installed-compat1-surfaceflinger"
        self.debugfs(image, f"dump -p {internal} {installed_new}")
        self.require(installed_new, change, "installed compat1 surfaceflinger")
        return {
            "partition_path": change["partition_path"], "reason": change["reason"],
            "diag3a": SHARED.record(installed_old), "compat1": SHARED.record(installed_new),
            "elf_class": change["elf_class"], "architecture": change["architecture"],
            "build_id": change["build_id"], "soname_preserved": True,
            "dt_needed_preserved": True, "strong_exports_preserved": True,
            "added_strong_imports": change["added_strong_imports"],
            "diag1_diag3_fatal_preserved": True,
        }

    def prepare_system(self) -> tuple[Path, dict[str, object]]:
        spec = self.raw_cfg["base_artifacts"]["system_a"]
        original = source(spec["path"])
        system = self.stage / "system_a.img"
        shutil.copyfile(original, system)
        self.require(system, spec, "exact diag3a system_a")
        with self.deterministic_ext4_time():
            self.run([sys.executable, str(self.avbtool), "erase_footer", "--image", str(system)])
            self.run(["e2fsck", "-fn", str(system)])
            replaced = {"surfaceflinger": self.replace_surfaceflinger(system)}
            self.run(["e2fsck", "-fy", str(system)], allowed={0, 1})
            self.run(["e2fsck", "-fn", str(system)])
        avb = self.cfg["avb"]["system"]
        self.run([
            sys.executable, str(self.avbtool), "add_hashtree_footer", "--image", str(system),
            "--partition_name", "system", "--partition_size", str(avb["partition_size"]),
            "--hash_algorithm", "sha256", "--salt", str(avb["salt"]), "--do_not_generate_fec",
            "--prop", f"com.ubox10.candidate.id:{self.candidate_id}",
            "--prop", "com.ubox10.avb.fec:none", "--key", str(REPO / avb["key_relative"]),
            "--algorithm", avb["algorithm"],
        ])
        self.verify_avb_partition(system, "system", avb["key_relative"])
        return system, {
            "base_diag3a": SHARED.record(original), "candidate": SHARED.record(system),
            "tree_delta": {"added": [], "removed": [], "changed": ["system/bin/surfaceflinger"]},
            "replaced": replaced, "ext4": "PASS", "avb_hashtree_no_fec": "PASS",
        }

    def prepare_vendor(self) -> tuple[Path, dict[str, object]]:
        spec = self.raw_cfg["base_artifacts"]["vendor_a"]
        original = source(spec["path"])
        vendor = self.stage / "vendor_a.img"
        shutil.copyfile(original, vendor)
        self.require(vendor, spec, "byte-preserved exact diag3a vendor_a")
        self.run(["e2fsck", "-fn", str(vendor)])
        self.verify_avb_partition(vendor, "vendor", None)
        return vendor, {
            "base_diag3a": SHARED.record(original), "candidate": SHARED.record(vendor),
            "tree_delta": {"added": [], "removed": [], "changed": []}, "replaced": {},
            "byte_preserved_from_diag3a": True, "ext4": "PASS", "avb_hashtree_fec": "PASS",
        }

    def build_super(self, system: Path, vendor: Path) -> tuple[Path, dict[str, object]]:
        sparse, audit = DIAG1.Builder.build_super(self, system, vendor)
        (self.stage / "super-sparse-roundtrip.raw.img").unlink()
        (self.stage / "candidate-logical/system_a.img").unlink()
        audit["base_diag3a_raw"] = audit.pop("frozen_r7_raw")
        audit["lp_metadata_and_extents_exact_diag3a"] = audit.pop("lp_metadata_and_extents_exact_r7")
        audit["bytes_outside_changed_extents_exact_diag3a"] = audit.pop(
            "bytes_outside_system_and_vendor_extents_inherited_exact_r7"
        )
        return sparse, audit

    def finish(self, firmware: Path, system_audit: dict[str, object],
               vendor_audit: dict[str, object], super_audit: dict[str, object],
               outer_audit: dict[str, object], vbmeta_system: Path, vbmeta_vendor: Path) -> None:
        for name, key in (("boot.fex", "boot"), ("vendor_dlkm_a.img", "vendor_dlkm")):
            shutil.copyfile(source(self.raw_cfg["base_artifacts"][key]["path"]), self.stage / name)
        outer_audit["all_other_payload_bytes_exact_diag3a"] = outer_audit.pop(
            "all_other_payload_bytes_exact_r7"
        )
        result = {
            "schema": 1, "id": self.candidate_id, "label": self.raw_cfg["label"],
            "status": "PACKAGED_AWAITING_FULL_OFFLINE_AUDIT",
            "decision": "PENDING_FULL_OFFLINE_AUDIT", "physical_status": "NOT_YET_VALIDATED",
            "physical_device_actions_performed": False, "flash_authorized": False,
            "elapsed_seconds": round(time.time() - self.started, 1),
            "source": {**self.raw_cfg["source_contract"], "targeted_modules_built": ["surfaceflinger"],
                       "kernel_rebuilt": False},
            "base_diag3a": SHARED.record(self.base), "firmware": SHARED.record(firmware),
            "system": system_audit, "vendor": vendor_audit, "super": super_audit,
            "outer": outer_audit, "vbmeta_system": SHARED.record(vbmeta_system),
            "vbmeta_vendor": SHARED.record(vbmeta_vendor),
            "boot": {"candidate": SHARED.record(self.stage / "boot.fex"),
                     "byte_preserved_from_diag3a": True},
            "vendor_dlkm": {"candidate": SHARED.record(self.stage / "vendor_dlkm_a.img"),
                            "byte_preserved_from_diag3a": True, "module_count": 22},
            "kernel": SHARED.record(self.stage / "kernel-evidence/Image"),
            "runtime_delta": system_audit["replaced"],
            "runtime_preserved": self.raw_cfg["preserved_runtime_files"],
            "compatibility": self.raw_cfg["compatibility"],
            "instrumentation": self.raw_cfg["instrumentation"],
            "physical_evidence": self.raw_cfg["physical_evidence"],
            "governance": self.raw_cfg["governance"],
        }
        result = SHARED.rewrite_paths(result, self.stage, self.final)
        (self.stage / "build-result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        sums = [f"{SHARED.digest(path)}  {path.name}" for path in sorted(self.stage.iterdir())
                if path.is_file() and path.name != "SHA256SUMS"]
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
