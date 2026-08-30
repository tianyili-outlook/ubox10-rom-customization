#!/usr/bin/env python3
"""Package diag3a as one diagnostic-only libstagefright delta from exact diag3."""
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
DEFAULT_CONFIG = REPO / "configs/candidates/a16-prototype-b-r7-diag3a-private-buffer-metadata.json"
DEFAULT_AOSP = Path("/work/src/ubox10-a16-ceiling")
DIAG3_CONFIG = REPO / "configs/candidates/a16-prototype-b-r7-diag3-private-buffer-metadata.json"
DIAG3_BUILDER = REPO / "scripts/build-a16-prototype-b-r7-diag3-private-buffer-metadata-candidate.py"
SPEC = importlib.util.spec_from_file_location("r7_diag3_builder_for_diag3a", DIAG3_BUILDER)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import diag3 builder: {DIAG3_BUILDER}")
DIAG3 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = DIAG3
SPEC.loader.exec_module(DIAG3)
SHARED = DIAG3.SHARED


def source(path: str) -> Path:
    value = Path(path)
    return value if value.is_absolute() else REPO / value


class Builder(DIAG3.Builder):
    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__(args)
        self.diag3_cfg = json.loads(DIAG3_CONFIG.read_text(encoding="utf-8"))
        self.runtime = {key: dict(value) for key, value in self.diag3_cfg["runtime_files"].items()}
        change = self.raw_cfg["runtime_change"]
        current = self.runtime[change["name"]]
        current.update({
            "old_size": change["diag3_size"], "old_sha256": change["diag3_sha256"],
            "size": change["size"], "sha256": change["sha256"],
            "build_id": change["build_id"], "reason": change["reason"],
        })

    def setup(self) -> None:
        if self.final.exists():
            raise RuntimeError(f"refusing to overwrite existing candidate: {self.final}")
        governance = self.raw_cfg["governance"]
        if (
            self.raw_cfg["status"] != "INSTRUMENTATION_ONLY_DIAGNOSTIC_AUTHORIZED"
            or governance["gate3"] != "HOLD"
            or governance["r8_authorized"] is not False
        ):
            raise RuntimeError("diag3a governance is not diagnostic-only / Gate 3 HOLD")
        self.stage.mkdir(parents=True)
        self.require(self.base, self.raw_cfg["base_candidate"], "exact diag3 outer")
        self.require(self.rollback, self.r4["rollback"], "Android 12 rollback")
        for name, record in self.raw_cfg["base_artifacts"].items():
            self.require(source(record["path"]), record, f"exact diag3 artifact {name}")

        contract = self.raw_cfg["source_contract"]
        actual = subprocess.check_output(
            ["git", "-C", str(self.args.aosp / "frameworks/av"), "rev-parse", "HEAD"], text=True
        ).strip()
        if actual != contract["frameworks_av_commit"]:
            raise RuntimeError(f"frameworks/av revision changed: {actual}")
        manifest = subprocess.check_output(
            ["git", "-C", str(self.args.aosp / ".repo/manifests"), "rev-parse", "HEAD"], text=True
        ).strip()
        if manifest != contract["manifest_commit"]:
            raise RuntimeError(f"manifest revision changed: {manifest}")
        if SHARED.digest(DIAG3_CONFIG) != contract["diag3_config_sha256"]:
            raise RuntimeError("inherited diag3 config identity changed")
        overlay = REPO / contract["overlay"]
        state = subprocess.check_output(
            [str(overlay / "prepare.sh"), "check", str(self.args.aosp)], text=True
        )
        if "source state: PATCHED" not in state:
            raise RuntimeError("diag3a source overlay is not exactly applied")

        changed = contract["changed_file"]
        self.require(
            self.args.aosp / changed["path"],
            {"size": changed["size"], "sha256": changed["sha256"]},
            "diag3a corrected FNV helper",
        )
        for relative, inherited in self.diag3_cfg["source_contract"]["files"].items():
            if relative == changed["path"]:
                continue
            self.require(
                self.args.aosp / relative,
                {"size": inherited["size"], "sha256": inherited["patched_sha256"]},
                f"inherited exact diag3 source {relative}",
            )

        diag3 = REPO / "out/candidates/a16-prototype-b-r7-diag3-private-buffer-metadata"
        for name, runtime in self.runtime.items():
            old = diag3 / f"diag3-{name}"
            self.require(
                old,
                {"size": runtime["old_size"] if name == "libstagefright64" else runtime["size"],
                 "sha256": runtime["old_sha256"] if name == "libstagefright64" else runtime["sha256"]},
                f"exact diag3 runtime {name}",
            )
            shutil.copyfile(old, self.stage / f"diag3-{name}")
            if name in self.raw_cfg["preserved_runtime_files"]:
                new = Path(runtime["source_path"])
                self.require(new, runtime, f"byte-preserved build output {name}")
                shutil.copyfile(new, self.stage / f"diag3a-{name}")

        name = self.raw_cfg["runtime_change"]["name"]
        runtime = self.runtime[name]
        binary = Path(runtime["source_path"])
        self.require(binary, runtime, "corrected diag3a libstagefright")
        before = DIAG3.DIAG1.elf_contract(diag3 / f"diag3-{name}")
        after = DIAG3.DIAG1.elf_contract(binary)
        for field in ("elf_class", "architecture", "soname", "dt_needed", "strong_exports"):
            if before[field] != after[field]:
                raise RuntimeError(f"diag3a changed libstagefright ELF contract: {field}")
        if DIAG3.strong_undefined(diag3 / f"diag3-{name}") != DIAG3.strong_undefined(binary):
            raise RuntimeError("diag3a changed libstagefright strong imports")
        data = binary.read_bytes()
        for marker in (b"UBOX_R7_DIAG1", b"UBOX_R7_DIAG3", b"CODEC_PRE_USE", b"CODEC_POST_FBD"):
            if marker not in data:
                raise RuntimeError(f"corrected libstagefright lost marker: {marker!r}")

        evidence = Path(self.raw_cfg["physical_evidence"]["path"])
        sums = evidence / "SHA256SUMS"
        if not sums.is_file():
            raise RuntimeError("diag3 physical regression evidence is unavailable")
        for line in sums.read_text(encoding="utf-8").splitlines():
            if line.strip():
                expected, relative = line.split(maxsplit=1)
                path = evidence / relative.lstrip("* ")
                if not path.is_file() or SHARED.digest(path) != expected.upper():
                    raise RuntimeError(f"diag3 physical evidence changed: {relative}")

        shutil.copytree(diag3 / "kernel-evidence", self.stage / "kernel-evidence")
        for item in (
            "final-build-variables.txt", "mali-intake.json", "active-product-build.prop.r5",
            "runtime-product-source-audit.json", "boringssl_self_test64",
        ):
            shutil.copyfile(diag3 / item, self.stage / item)

    def replace_runtime_file(self, image: Path, name: str, internal_path: str) -> dict[str, object]:
        if name != "libstagefright64":
            raise RuntimeError(f"diag3a refuses unexpected runtime replacement: {name}")
        runtime = self.runtime[name]
        parent = str(Path(internal_path).parent)
        parent_times = self.inode_times(self.debugfs(image, f"stat {parent}", capture=True))
        old = self.stage / f"diag3-{name}"
        installed_old = self.stage / f"installed-diag3-{name}"
        new = self.stage / f"diag3a-{name}"
        self.debugfs(image, f"dump -p {internal_path} {installed_old}")
        self.require(installed_old, {"size": runtime["old_size"], "sha256": runtime["old_sha256"]},
                     "installed exact diag3 libstagefright")
        self.require(old, {"size": runtime["old_size"], "sha256": runtime["old_sha256"]},
                     "saved exact diag3 libstagefright")
        self.debugfs(image, f"rm {internal_path}")
        self.debugfs(image, f"write {runtime['source_path']} {internal_path}")
        self.debugfs(image, f"set_inode_field {internal_path} mode 010{runtime['mode']}")
        self.debugfs(image, f"set_inode_field {internal_path} uid {runtime['uid']}")
        self.debugfs(image, f"set_inode_field {internal_path} gid {runtime['gid']}")
        for field in ("ctime", "atime", "mtime", "crtime"):
            self.debugfs(image, f"set_inode_field {internal_path} {field} {runtime[field]}")
        self.debugfs(image, f'ea_set {internal_path} security.selinux "{runtime["selinux"]}\\000"')
        self.restore_times(image, parent, parent_times)
        self.debugfs(image, f"dump -p {internal_path} {new}")
        self.require(new, runtime, "installed corrected diag3a libstagefright")
        return {
            "partition_path": runtime["partition_path"], "reason": runtime["reason"],
            "diag3": SHARED.record(old), "diag3a": SHARED.record(new),
            "elf_class": runtime["elf_class"], "architecture": runtime["architecture"],
            "build_id": runtime["build_id"], "soname_preserved": True,
            "dt_needed_preserved": True, "strong_exports_preserved": True,
            "strong_imports_preserved": True, "diag1_diag3_markers_preserved": True,
        }

    def prepare_system(self) -> tuple[Path, dict[str, object]]:
        spec = self.raw_cfg["base_artifacts"]["system_a"]
        original = source(spec["path"])
        system = self.stage / "system_a.img"
        shutil.copyfile(original, system)
        self.require(system, spec, "exact diag3 system_a")
        with self.deterministic_ext4_time():
            self.run([sys.executable, str(self.avbtool), "erase_footer", "--image", str(system)])
            self.run(["e2fsck", "-fn", str(system)])
            replaced = {"libstagefright64": self.replace_runtime_file(
                system, "libstagefright64", "/system/lib64/libstagefright.so"
            )}
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
            "base_diag3": SHARED.record(original), "candidate": SHARED.record(system),
            "tree_delta": {"added": [], "removed": [], "changed": ["system/lib64/libstagefright.so"]},
            "replaced": replaced, "ext4": "PASS", "avb_hashtree_no_fec": "PASS",
        }

    def prepare_vendor(self) -> tuple[Path, dict[str, object]]:
        spec = self.raw_cfg["base_artifacts"]["vendor_a"]
        original = source(spec["path"])
        vendor = self.stage / "vendor_a.img"
        shutil.copyfile(original, vendor)
        self.require(vendor, spec, "byte-preserved exact diag3 vendor_a")
        self.run(["e2fsck", "-fn", str(vendor)])
        self.verify_avb_partition(vendor, "vendor", None)
        return vendor, {
            "base_diag3": SHARED.record(original), "candidate": SHARED.record(vendor),
            "tree_delta": {"added": [], "removed": [], "changed": []}, "replaced": {},
            "byte_preserved_from_diag3": True, "ext4": "PASS", "avb_hashtree_fec": "PASS",
        }

    def build_super(self, system: Path, vendor: Path) -> tuple[Path, dict[str, object]]:
        sparse, audit = DIAG3.DIAG1.Builder.build_super(self, system, vendor)
        (self.stage / "super-sparse-roundtrip.raw.img").unlink()
        (self.stage / "candidate-logical/system_a.img").unlink()
        audit["base_diag3_raw"] = audit.pop("frozen_r7_raw")
        audit["lp_metadata_and_extents_exact_diag3"] = audit.pop("lp_metadata_and_extents_exact_r7")
        audit["bytes_outside_changed_extents_exact_diag3"] = audit.pop(
            "bytes_outside_system_and_vendor_extents_inherited_exact_r7"
        )
        return sparse, audit

    def finish(self, firmware: Path, system_audit: dict[str, object],
               vendor_audit: dict[str, object], super_audit: dict[str, object],
               outer_audit: dict[str, object], vbmeta_system: Path, vbmeta_vendor: Path) -> None:
        for name, key in (("boot.fex", "boot"), ("vendor_dlkm_a.img", "vendor_dlkm")):
            shutil.copyfile(source(self.raw_cfg["base_artifacts"][key]["path"]), self.stage / name)
        outer_audit["all_other_payload_bytes_exact_diag3"] = outer_audit.pop(
            "all_other_payload_bytes_exact_r7"
        )
        result = {
            "schema": 1, "id": self.candidate_id, "label": self.raw_cfg["label"],
            "status": "PACKAGED_AWAITING_FULL_OFFLINE_AUDIT",
            "decision": "PENDING_FULL_OFFLINE_AUDIT", "physical_status": "NOT_YET_VALIDATED",
            "physical_device_actions_performed": False, "flash_authorized": False,
            "elapsed_seconds": round(time.time() - self.started, 1),
            "source": {**self.raw_cfg["source_contract"], "targeted_modules_built": ["libstagefright"],
                       "kernel_rebuilt": False},
            "base_diag3": SHARED.record(self.base), "firmware": SHARED.record(firmware),
            "system": system_audit, "vendor": vendor_audit, "super": super_audit,
            "outer": outer_audit, "vbmeta_system": SHARED.record(vbmeta_system),
            "vbmeta_vendor": SHARED.record(vbmeta_vendor),
            "boot": {"candidate": SHARED.record(self.stage / "boot.fex"),
                     "byte_preserved_from_diag3": True},
            "vendor_dlkm": {"candidate": SHARED.record(self.stage / "vendor_dlkm_a.img"),
                            "byte_preserved_from_diag3": True, "module_count": 22},
            "kernel": SHARED.record(self.stage / "kernel-evidence/Image"),
            "runtime_delta": system_audit["replaced"],
            "runtime_preserved": self.raw_cfg["preserved_runtime_files"],
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
