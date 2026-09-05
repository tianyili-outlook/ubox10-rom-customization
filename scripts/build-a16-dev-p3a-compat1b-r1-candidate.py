#!/usr/bin/env python3
"""Build a16-dev-p3a-compat1b-r1 from exact FBM-r1 with only the Mali consumer predicate extension."""
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
CONFIG = REPO / "configs/candidates/a16-dev-p3a-compat1b-r1.json"
AOSP = Path("/work/src/ubox10-a16-ceiling")
AUDIO_BUILDER_PATH = REPO / "scripts/build-a16-dev-audio-r1-candidate.py"
SPEC = importlib.util.spec_from_file_location("audio_r1_builder_for_compat1b", AUDIO_BUILDER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import candidate builder: {AUDIO_BUILDER_PATH}")
AUDIO = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = AUDIO
SPEC.loader.exec_module(AUDIO)
SHARED = AUDIO.SHARED
DIAG1 = AUDIO.DIAG1


def source(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO / path


def command_output(command: list[str]) -> str:
    return subprocess.check_output(command, text=True, errors="replace")


class Builder(AUDIO.Builder):
    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__(args)
        self.fbm_r1 = REPO / "out/candidates/a16-dev-p3a-fbm-r1"

    def setup(self) -> None:
        if self.final.exists():
            raise RuntimeError(f"refusing to overwrite existing candidate: {self.final}")
        gov = self.raw_cfg["governance"]
        if (gov["rc_a2"] != "PHYSICAL_PASS_CLOSED" or gov["p3b_main10"] != "NOT_AUTHORIZED"
                or gov["r8_authorized"] or gov["r8_built"] or gov["release"]):
            raise RuntimeError("compat1b governance changed")
        self.stage.mkdir(parents=True)
        self.require(self.base, self.raw_cfg["base_candidate"], "exact physically tested FBM-r1")
        self.require(self.rollback, self.r4["rollback"], "retained Test8r2 rollback")
        for name, spec in self.raw_cfg["base_artifacts"].items():
            self.require(source(spec["path"]), spec, f"exact FBM-r1 {name}")
        contract = self.raw_cfg["source_contract"]
        self.run([sys.executable, str(source(contract["overlay"]) / "prepare.py"), "check", str(self.args.aosp)])
        for relative, spec in contract["files"].items():
            self.require(self.args.aosp / relative, spec, "exact source")
        for relative, revision in contract["repositories"].items():
            if command_output(["git", "-C", str(self.args.aosp / relative), "rev-parse", "HEAD"]).strip() != revision:
                raise RuntimeError(f"pinned source revision changed: {relative}")
        change = self.raw_cfg["runtime_change"]
        new = Path(change["source_path"])
        old = self.fbm_r1 / "preserved-surfaceflinger"
        self.require(new, change, "targeted SurfaceFlinger output")
        proof_dir = source(contract["build_proof_directory"])
        proof = json.loads((proof_dir / "build-proof.json").read_text())
        if (proof["control"]["sha256"].upper() != change["base_sha256"] or
                proof["compat1b"]["sha256"].upper() != change["sha256"] or
                proof["control_exact_physical_compat1a"] is not True):
            raise RuntimeError("SurfaceFlinger reconstruction-control proof changed")
        for label in ("control", "compat1b"):
            self.require(proof_dir / f"{label}-surfaceflinger",
                         {"size": proof[label]["size"], "sha256": proof[label]["sha256"].upper()},
                         f"exact {label} build proof")
        shutil.copyfile(proof_dir / "build-proof.json", self.stage / "surfaceflinger-build-proof.json")
        self.require(old, {"size": change["base_size"], "sha256": change["base_sha256"]}, "base SurfaceFlinger")
        before, after = DIAG1.elf_contract(old), DIAG1.elf_contract(new)
        for field in ("elf_class", "architecture", "soname", "dt_needed", "exports"):
            if before[field] != after[field]:
                raise RuntimeError(f"SurfaceFlinger ABI drift: {field}")
        if AUDIO.BASE.strong_undefined(old) != AUDIO.BASE.strong_undefined(new):
            raise RuntimeError("SurfaceFlinger strong-import drift")
        for marker in (b"UBOX_R7_DIAG1", b"UBOX_R7_DIAG3", b"UBOX_R7_COMPAT1",
                       b"UBOX_P3_COMPAT1B", b"Failed to create a valid texture."):
            if marker not in new.read_bytes(): raise RuntimeError(f"missing marker/fatal: {marker}")
        shutil.copyfile(old, self.stage / "base-surfaceflinger")
        shutil.copyfile(new, self.stage / "compat1b-surfaceflinger")
        shutil.copytree(self.fbm_r1 / "kernel-evidence", self.stage / "kernel-evidence")
        for name in ("final-build-variables.txt", "mali-intake.json", "active-product-build.prop.r5",
                     "runtime-product-source-audit.json", "boringssl_self_test64"):
            shutil.copyfile(self.fbm_r1 / name, self.stage / name)
        for name, spec in self.raw_cfg["preserved_runtime"].items():
            item = self.fbm_r1 / spec["candidate_file"]
            self.require(item, spec, f"preserved {name}")
            shutil.copyfile(item, self.stage / f"preserved-{name}")

    def prepare_system(self) -> tuple[Path, dict[str, object]]:
        system, audit = AUDIO.BASE.Builder.prepare_system(self)
        audit["base_fbm_r1"] = audit.pop("base_diag3a")
        return system, audit

    def prepare_vendor(self) -> tuple[Path, dict[str, object]]:
        spec = self.raw_cfg["base_artifacts"]["vendor_a"]
        original = source(spec["path"])
        vendor = self.stage / "vendor_a.img"
        shutil.copyfile(original, vendor)
        self.require(vendor, spec, "byte-identical FBM-r1 vendor")
        self.run(["e2fsck", "-fn", str(vendor)])
        self.verify_avb_partition(vendor, "vendor", None)
        return vendor, {"base_fbm_r1": SHARED.record(original), "candidate": SHARED.record(vendor),
                        "tree_delta": {"added": [], "removed": [], "changed": []},
                        "byte_preserved_from_fbm_r1": True, "ext4": "PASS", "avb": "PASS"}

    def build_super(self, system: Path, vendor: Path) -> tuple[Path, dict[str, object]]:
        sparse, audit = super().build_super(system, vendor)
        audit["base_fbm_r1_raw"] = audit.pop("base_compat1a_raw")
        audit["lp_metadata_and_extents_exact_fbm_r1"] = audit.pop(
            "lp_metadata_and_extents_exact_compat1a"
        )
        audit["bytes_outside_changed_extents_exact_fbm_r1"] = audit.pop(
            "bytes_outside_changed_extents_exact_compat1a"
        )
        return sparse, audit

    def finish(self, firmware: Path, system_audit: dict[str, object],
               vendor_audit: dict[str, object], super_audit: dict[str, object],
               outer_audit: dict[str, object], vbmeta_system: Path,
               vbmeta_vendor: Path) -> None:
        for name, key in (("boot.fex", "boot"), ("vendor_dlkm_a.img", "vendor_dlkm")):
            shutil.copyfile(source(self.raw_cfg["base_artifacts"][key]["path"]), self.stage / name)
        outer_audit["all_other_payload_bytes_exact_fbm_r1"] = outer_audit.pop(
            "all_other_payload_bytes_exact_r7"
        )
        result = {
            "schema": 1, "id": self.candidate_id, "label": self.raw_cfg["label"],
            "status": "PACKAGED_AWAITING_FULL_OFFLINE_AUDIT",
            "decision": "PENDING_FULL_OFFLINE_AUDIT", "physical_status": "NOT_YET_VALIDATED",
            "physical_device_actions_performed": False, "flash_performed": False,
            "elapsed_seconds": round(time.time() - self.started, 1),
            "source": {
                "base_repository_commit": "5b11e8aefb1bdd0190f40411fdbde2e6347ebd46",
                "repair_readiness": self.raw_cfg["repair_readiness"],
                "contract": self.raw_cfg["source_contract"], "targeted_modules_built": ["surfaceflinger"],
                "kernel_rebuilt": False, "rc_b_modified": True,
            },
            "base_fbm_r1": SHARED.record(self.base), "firmware": SHARED.record(firmware),
            "system": system_audit, "vendor": vendor_audit, "super": super_audit,
            "outer": outer_audit, "vbmeta_system": SHARED.record(vbmeta_system),
            "vbmeta_vendor": SHARED.record(vbmeta_vendor),
            "boot": {"candidate": SHARED.record(self.stage / "boot.fex"),
                     "byte_preserved_from_fbm_r1": True},
            "vendor_dlkm": {"candidate": SHARED.record(self.stage / "vendor_dlkm_a.img"),
                            "byte_preserved_from_fbm_r1": True, "module_count": 22},
            "kernel": SHARED.record(self.stage / "kernel-evidence/Image"),
            "runtime_delta": system_audit["replaced"],
            "runtime_preserved": self.raw_cfg["preserved_runtime"],
            "governance": self.raw_cfg["governance"],
        }
        result = SHARED.rewrite_paths(result, self.stage, self.final)
        (self.stage / "build-result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        sums = [
            f"{SHARED.digest(path)}  {path.name}" for path in sorted(self.stage.iterdir())
            if path.is_file() and path.name != "SHA256SUMS"
        ]
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
