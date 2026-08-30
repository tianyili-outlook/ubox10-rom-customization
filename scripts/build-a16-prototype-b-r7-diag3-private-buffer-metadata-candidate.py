#!/usr/bin/env python3
"""Package the read-only r7-diag3 private-buffer metadata diagnostic."""
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
DEFAULT_CONFIG = REPO / "configs/candidates/a16-prototype-b-r7-diag3-private-buffer-metadata.json"
DEFAULT_AOSP = Path("/work/src/ubox10-a16-ceiling")
DIAG1_CONFIG = REPO / "configs/candidates/a16-prototype-b-r7-diag1.json"
DIAG1_PATH = REPO / "scripts/build-a16-prototype-b-r7-diag1-candidate.py"
SPEC = importlib.util.spec_from_file_location("r7_diag1_builder_for_diag3", DIAG1_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import diag1 builder: {DIAG1_PATH}")
DIAG1 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = DIAG1
SPEC.loader.exec_module(DIAG1)

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
        self.raw_cfg = json.loads(args.config.read_text(encoding="utf-8"))
        self.candidate_id = self.raw_cfg["id"]
        self.cfg["id"] = self.candidate_id
        self.cfg["status"] = self.raw_cfg["status"]
        self.cfg["base_candidate"] = self.raw_cfg["base_candidate"]
        self.cfg["_continuation"] = self.raw_cfg
        self.final = REPO / "out/candidates" / self.candidate_id
        self.stage = self.final.parent / f".{self.candidate_id}.staging-{uuid.uuid4().hex}"
        self.log = self.stage / "logs/01-commands.log"
        self.base = source(self.raw_cfg["base_candidate"]["path"])
        self.started = time.time()
        self.graphics_closure: dict[str, object] = {}

    def setup(self) -> None:
        if self.final.exists():
            raise RuntimeError(f"refusing to overwrite existing candidate: {self.final}")
        if self.raw_cfg["status"] != "INSTRUMENTATION_ONLY_DIAGNOSTIC_AUTHORIZED":
            raise RuntimeError("diag3 is not authorized as diagnostic-only")
        governance = self.raw_cfg["governance"]
        if governance["gate3"] != "HOLD" or governance["r8_authorized"] is not False:
            raise RuntimeError("diag3 must retain Gate 3 HOLD and must not authorize r8")
        self.stage.mkdir(parents=True)
        self.require(self.base, self.raw_cfg["base_candidate"], "exact diag2 outer")
        self.require(self.rollback, self.r4["rollback"], "Android 12 rollback")
        for name, record in self.raw_cfg["base_artifacts"].items():
            self.require(source(record["path"]), record, f"exact diag2 artifact {name}")

        for repository, expected in self.raw_cfg["source_contract"]["repositories"].items():
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
        # The diag3 post-image hashes necessarily supersede the lower overlay
        # post-image hashes. Its reversible base guards prove that the input was
        # exact diag2, so only the top overlay can be PATCHED simultaneously.
        overlay = REPO / self.raw_cfg["source_contract"]["overlay"]
        checked = subprocess.check_output(
            [str(overlay / "prepare.sh"), "check", str(self.args.aosp)], text=True
        )
        if "source state: PATCHED" not in checked:
            raise RuntimeError("diag3 source overlay is not exactly applied")
        for relative, contract in self.raw_cfg["source_contract"]["files"].items():
            path = self.args.aosp / relative
            self.require(path, {"size": contract["size"], "sha256": contract["patched_sha256"]},
                         f"diag3 source {relative}")

        permitted_imports = {
            "surfaceflinger": {"AHardwareBuffer_getNativeHandle"},
            "libstagefright64": {"mmap"},
            "gralloc32": {"__vsnprintf_chk", "fstat"},
            "gralloc64": {"__vsnprintf_chk", "fstat"},
        }
        base = REPO / "out/candidates/a16-prototype-b-r7-diag2-hevc-crop"
        for name, contract in self.raw_cfg["runtime_files"].items():
            new = Path(contract["source_path"])
            old = base / f"diag2-{name}"
            self.require(new, contract, f"diag3 build output {name}")
            self.require(old, {"size": contract["old_size"], "sha256": contract["old_sha256"]},
                         f"diag2 runtime {name}")
            before = DIAG1.elf_contract(old)
            after = DIAG1.elf_contract(new)
            for field in ("elf_class", "architecture", "soname", "dt_needed", "strong_exports"):
                if before[field] != after[field]:
                    raise RuntimeError(f"{name} non-diagnostic ELF contract changed: {field}")
            old_imports, new_imports = strong_undefined(old), strong_undefined(new)
            if old_imports - new_imports or new_imports - old_imports != permitted_imports[name]:
                raise RuntimeError(f"{name} unexpected strong-import delta")
            data = new.read_bytes()
            if b"UBOX_R7_DIAG1" not in data or b"UBOX_R7_DIAG3" not in data:
                raise RuntimeError(f"{name} lost inherited or diag3 marker")
        surfaceflinger = Path(self.raw_cfg["runtime_files"]["surfaceflinger"]["source_path"])
        if b"Failed to create a valid texture." not in surfaceflinger.read_bytes():
            raise RuntimeError("original RenderEngine fatal is absent")

        self.run_graphics_closure()
        diag2 = REPO / "out/candidates/a16-prototype-b-r7-diag2-hevc-crop"
        shutil.copytree(diag2 / "kernel-evidence", self.stage / "kernel-evidence")
        for name in (
            "final-build-variables.txt", "mali-intake.json", "active-product-build.prop.r5",
            "runtime-product-source-audit.json", "boringssl_self_test64",
        ):
            shutil.copyfile(diag2 / name, self.stage / name)

    def run_graphics_closure(self) -> None:
        checker = REPO / "scripts/check-a16-prototype-b-r7-graphics.py"
        diag2 = REPO / "out/candidates/a16-prototype-b-r7-diag2-hevc-crop"
        root = diag2 / "offline-audit/root"
        common = ["--linker-config", str(diag2 / "offline-audit/linker-generated/ld.config.txt")]
        outputs: dict[str, object] = {}
        for arch, mapper, libdir, gralloc in (
            ("arm32", REPO / "out/candidates/a16-prototype-b-r7/retained-mapper32", "lib", "gralloc32"),
            ("arm64", REPO / "out/candidates/a16-prototype-b-r7/r7-mapper.so", "lib64", "gralloc64"),
        ):
            output = self.stage / f"graphics-sphal-closure-{arch}.json"
            command = [
                sys.executable, str(checker), "--architecture", arch, "--mapper", str(mapper),
                "--gralloc", self.raw_cfg["runtime_files"][gralloc]["source_path"],
                "--system-lib", str(self.args.aosp / f"out-ceiling-b1/target/product/ubox10_ceiling_arm64/system/{libdir}"),
                "--runtime-lib", str(root / f"apex/com.android.runtime/{libdir}/bionic"),
                "--vndk-lib", str(root / f"apex/com.android.vndk.v31/{libdir}"),
                *common, "--output", str(output),
            ]
            self.run(command, output=self.stage / f"graphics-sphal-closure-{arch}.log")
            result = json.loads(output.read_text(encoding="utf-8"))
            if result["gralloc"]["unmatched_count"] != 0:
                raise RuntimeError(f"diag3 {arch} gralloc has unmatched strong imports")
            if result["gralloc"]["libcpp_verbose_abort_import"]:
                raise RuntimeError(f"diag3 {arch} gralloc regressed libc++ back-deploy")
            outputs[arch] = result
        self.graphics_closure = outputs

    def replace_runtime_file(self, image: Path, name: str, internal_path: str) -> dict[str, object]:
        contract = self.raw_cfg["runtime_files"][name]
        parent = str(Path(internal_path).parent)
        parent_times = self.inode_times(self.debugfs(image, f"stat {parent}", capture=True))
        old = self.stage / f"diag2-{name}"
        new = self.stage / f"diag3-{name}"
        self.debugfs(image, f"dump -p {internal_path} {old}")
        self.require(old, {"size": contract["old_size"], "sha256": contract["old_sha256"]},
                     f"installed diag2 {name}")
        if b"UBOX_R7_DIAG1" not in old.read_bytes() or b"UBOX_R7_DIAG3" in old.read_bytes():
            raise RuntimeError(f"diag2 marker isolation failed: {name}")
        before, after = DIAG1.elf_contract(old), DIAG1.elf_contract(Path(contract["source_path"]))
        for field in ("elf_class", "architecture", "soname", "dt_needed", "strong_exports"):
            if before[field] != after[field]:
                raise RuntimeError(f"{name} ELF contract changed: {field}")

        self.debugfs(image, f"rm {internal_path}")
        self.debugfs(image, f"write {contract['source_path']} {internal_path}")
        self.debugfs(image, f"set_inode_field {internal_path} mode 010{contract['mode']}")
        self.debugfs(image, f"set_inode_field {internal_path} uid {contract['uid']}")
        self.debugfs(image, f"set_inode_field {internal_path} gid {contract['gid']}")
        for field in ("ctime", "atime", "mtime", "crtime"):
            self.debugfs(image, f"set_inode_field {internal_path} {field} {contract[field]}")
        self.debugfs(image, f'ea_set {internal_path} security.selinux "{contract["selinux"]}\\000"')
        self.restore_times(image, parent, parent_times)
        self.debugfs(image, f"dump -p {internal_path} {new}")
        self.require(new, contract, f"installed diag3 {name}")
        return {
            "partition_path": contract["partition_path"], "reason": contract["reason"],
            "diag2": SHARED.record(old), "diag3": SHARED.record(new),
            "elf_class": contract["elf_class"], "architecture": contract["architecture"],
            "build_id": contract["build_id"], "soname_preserved": True,
            "dt_needed_preserved": True, "strong_exports_preserved": True,
            "diagnostic_marker_present": True,
        }

    def build_super(self, system: Path, vendor: Path) -> tuple[Path, dict[str, object]]:
        sparse, audit = super().build_super(system, vendor)
        (self.stage / "super-sparse-roundtrip.raw.img").unlink()
        (self.stage / "candidate-logical/system_a.img").unlink()
        audit["base_diag2_raw"] = audit.pop("frozen_r7_raw")
        audit["lp_metadata_and_extents_exact_diag2"] = audit.pop("lp_metadata_and_extents_exact_r7")
        audit["bytes_outside_changed_extents_exact_diag2"] = audit.pop(
            "bytes_outside_system_and_vendor_extents_inherited_exact_r7"
        )
        return sparse, audit

    def finish(self, firmware: Path, system_audit: dict[str, object],
               vendor_audit: dict[str, object], super_audit: dict[str, object],
               outer_audit: dict[str, object], vbmeta_system: Path,
               vbmeta_vendor: Path) -> None:
        for name, key in (("boot.fex", "boot"), ("vendor_dlkm_a.img", "vendor_dlkm")):
            shutil.copyfile(source(self.raw_cfg["base_artifacts"][key]["path"]), self.stage / name)
        result = {
            "schema": 1, "id": self.candidate_id, "label": self.raw_cfg["label"],
            "status": "PACKAGED_AWAITING_FULL_OFFLINE_AUDIT",
            "decision": "PENDING_FULL_OFFLINE_AUDIT", "physical_status": "NOT_YET_VALIDATED",
            "physical_device_actions_performed": False, "flash_authorized": False,
            "elapsed_seconds": round(time.time() - self.started, 1),
            "source": {**self.raw_cfg["source_contract"],
                       "targeted_modules_built": ["surfaceflinger", "libstagefright", "gralloc.apollo"],
                       "kernel_rebuilt": False},
            "base_diag2": SHARED.record(self.base), "firmware": SHARED.record(firmware),
            "system": system_audit, "vendor": vendor_audit, "super": super_audit,
            "outer": outer_audit, "vbmeta_system": SHARED.record(vbmeta_system),
            "vbmeta_vendor": SHARED.record(vbmeta_vendor),
            "boot": {"candidate": SHARED.record(self.stage / "boot.fex"),
                     "byte_preserved_from_diag2": True},
            "vendor_dlkm": {"candidate": SHARED.record(self.stage / "vendor_dlkm_a.img"),
                            "byte_preserved_from_diag2": True, "module_count": 22},
            "kernel": SHARED.record(self.stage / "kernel-evidence/Image"),
            "runtime_delta": {name: value for section in (system_audit, vendor_audit)
                              for name, value in section["replaced"].items()},
            "graphics_closure": self.graphics_closure,
            "instrumentation": self.raw_cfg["instrumentation"],
            "governance": self.raw_cfg["governance"],
        }
        outer_audit["all_other_payload_bytes_exact_diag2"] = outer_audit.pop(
            "all_other_payload_bytes_exact_r7"
        )
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
