#!/usr/bin/env python3
"""Fail-closed offline audit for the bounded a16-dev-p3a-compat1b-r1 candidate."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile


REPO = Path(__file__).resolve().parents[1]
AOSP = Path("/work/src/ubox10-a16-ceiling")
CANDIDATE = REPO / "out/candidates/a16-dev-p3a-compat1b-r1"
BASE = REPO / "out/candidates/a16-dev-p3a-fbm-r1"
CONFIG = REPO / "configs/candidates/a16-dev-p3a-compat1b-r1.json"
AUDIO_AUDIT_PATH = REPO / "scripts/audit-a16-dev-audio-r1.py"
SPEC = importlib.util.spec_from_file_location("audio_r1_audit_for_compat1b", AUDIO_AUDIT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import audit: {AUDIO_AUDIT_PATH}")
AUDIO_AUDIT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = AUDIO_AUDIT
SPEC.loader.exec_module(AUDIO_AUDIT)

digest = AUDIO_AUDIT.digest
record = AUDIO_AUDIT.record
elf_contract = AUDIO_AUDIT.elf_contract
delta = AUDIO_AUDIT.delta
KEY = AUDIO_AUDIT.KEY
AVBTOOL = AUDIO_AUDIT.AVBTOOL


def strict_tree_manifest(root: Path) -> dict:
    """Read every directory or fail; Android /system/bin is root:shell 0751."""
    result = {}
    def unreadable(error):
        raise error
    for current, directories, files in os.walk(root, topdown=True, followlinks=False,
                                                onerror=unreadable):
        for name in sorted(directories + files):
            path = Path(current) / name
            info = path.lstat()
            attrs = [(a, os.getxattr(path, a, follow_symlinks=False).hex())
                     for a in sorted(os.listxattr(path, follow_symlinks=False))]
            if stat.S_ISREG(info.st_mode):
                payload = digest(path)
            elif stat.S_ISLNK(info.st_mode):
                payload = os.readlink(path)
                if name in directories: directories.remove(name)
            else:
                payload = None
            result[str(path.relative_to(root))] = (
                stat.S_IFMT(info.st_mode), stat.S_IMODE(info.st_mode), info.st_uid,
                info.st_gid, info.st_size, payload, attrs)
    return result


class Auditor(AUDIO_AUDIT.Auditor):
    def full_tree(self, root: Path, label: str) -> dict:
        # Privileged HOST read of a loop,ro,noload image. No device or filesystem mutation.
        output = self.audit / f"{label}-tree.json"
        self.run(["sudo", sys.executable, str(Path(__file__).resolve()),
                  "--tree-manifest", str(root)], output=output)
        manifest = json.loads(output.read_text())
        if "system/bin/surfaceflinger" not in manifest:
            raise RuntimeError("incomplete system tree: SurfaceFlinger missing")
        return manifest

    def surfaceflinger_closure(self, target: Path) -> dict[str, object]:
        search = [self.root / "system/lib64", self.root / "system/system_ext/lib64",
                  self.root / "apex/com.android.runtime/lib64/bionic"]
        search += sorted((self.root / "apex").glob("*/lib64"))
        providers = {}
        for directory in search:
            if directory.is_dir():
                for path in directory.glob("*.so"):
                    if path.is_file(): providers.setdefault(path.name, path)
        exports = set()
        resolved = []
        for needed in elf_contract(target)["dt_needed"]:
            if needed not in providers: raise RuntimeError(f"missing SF provider: {needed}")
            provider = providers[needed]
            exports.update(AUDIO_AUDIT.symbols(provider, False))
            resolved.append(record(provider))
        unmatched = sorted(AUDIO_AUDIT.symbols(target, True) - exports)
        if unmatched: raise RuntimeError(f"unmatched SF strong imports: {unmatched}")
        return {"result": "PASS_EXACT_ARM64_DIRECT_NEEDED_CLOSURE", "unmatched_count": 0,
                "providers": resolved}

    def execute(self) -> None:
        if self.audit.exists():
            raise RuntimeError(f"refusing to overwrite audit: {self.audit}")
        self.audit.mkdir(parents=True)
        frozen = {}
        for name, spec in self.cfg["frozen_artifacts"].items():
            item = record(REPO / spec["path"])
            if item["size"] != spec["size"] or item["sha256"] != spec["sha256"]:
                raise RuntimeError(f"frozen/rollback identity changed: {name}")
            frozen[name] = item
        build_path = self.candidate / "build-result.json"
        build = json.loads(build_path.read_text(encoding="utf-8"))
        if build["status"] != "PACKAGED_AWAITING_FULL_OFFLINE_AUDIT":
            raise RuntimeError("candidate is not in packaged pre-audit state")
        if record(self.base / "x12-a16-dev-p3a-fbm-r1.img") != {
            "path": str(self.base / "x12-a16-dev-p3a-fbm-r1.img"),
            "size": self.cfg["base_candidate"]["size"],
            "sha256": self.cfg["base_candidate"]["sha256"],
        }:
            raise RuntimeError("exact tested FBM-r1 base identity changed")

        images = {
            "system": self.candidate / "system_a.img",
            "vendor": self.candidate / "candidate-logical/vendor_a.img",
            "product": self.candidate / "candidate-logical/product_a.img",
            "vendor_dlkm": self.candidate / "vendor_dlkm_a.img",
        }
        try:
            for name, path in images.items():
                self.run(["e2fsck", "-fn", str(path)], output=self.audit / f"e2fsck-{name}.log")
            self.run(
                [sys.executable, str(REPO / "tools/sunxi_image_tool.py"), "verify",
                 str(self.candidate / "x12-a16-dev-p3a-compat1b-r1.img")],
                output=self.audit / "outer-verify.log",
            )

            avb_view = self.audit / "avb-view"
            avb_view.mkdir()
            for name, path, key in (
                ("system", images["system"], KEY), ("vendor", images["vendor"], None),
                ("vbmeta_system", self.candidate / "vbmeta_system.fex", KEY),
                ("vbmeta_vendor", self.candidate / "vbmeta_vendor.fex", KEY),
            ):
                view = avb_view / f"{name}.img"
                os.link(path, view)
                command = [sys.executable, str(AVBTOOL), "verify_image", "--image", str(view)]
                if key is not None:
                    command += ["--key", str(key)]
                self.run(command, output=self.audit / f"verify-{name}.log")
                self.run(
                    [sys.executable, str(AVBTOOL), "info_image", "--image", str(view)],
                    output=self.audit / f"info-{name}.txt",
                )

            base_lp = self.audit / "audio-r1-lpdump.json"
            candidate_lp = self.audit / "candidate-lpdump.json"
            self.run([str(self.host / "lpdump"), "-j", str(self.base / "super.raw.img")], output=base_lp)
            self.run([str(self.host / "lpdump"), "-j", str(self.candidate / "super.raw.img")], output=candidate_lp)
            if json.loads(base_lp.read_text()) != json.loads(candidate_lp.read_text()):
                raise RuntimeError("LP metadata/extents differ from exact FBM-r1")
            with tempfile.TemporaryDirectory(prefix="ubox-p3a-omx-sparse-", dir="/work") as directory:
                raw = Path(directory) / "super.raw.img"
                self.run(
                    [str(self.host / "simg2img"), str(self.candidate / "super.fex"), str(raw)],
                    output=self.audit / "sparse-roundtrip.log",
                )
                if digest(raw) != digest(self.candidate / "super.raw.img"):
                    raise RuntimeError("sparse-to-raw round trip differs")

            points = {name: self.mount(name, path) for name, path in images.items()}
            base_system = self.mount("fbm-r1-system", self.base / "system_a.img")
            self.setup_root(points)
            system_delta = delta(self.full_tree(base_system, "base-system"),
                                 self.full_tree(points["system"], "candidate-system"))
            if system_delta != {"added": [], "removed": [], "changed": ["system/bin/surfaceflinger"]}:
                raise RuntimeError(f"semantic system delta expanded: {system_delta}")
            if digest(self.base / "vendor_a.img") != digest(images["vendor"]):
                raise RuntimeError("FBM-r1 vendor image changed")
            vendor_delta = {"added": [], "removed": [], "changed": []}
            change = self.cfg["runtime_change"]
            old = base_system / "system/bin/surfaceflinger"
            new = points["system"] / "system/bin/surfaceflinger"
            old_record, new_record = record(old), record(new)
            for item, expected, label in (
                (old_record, {"size": change["base_size"], "sha256": change["base_sha256"]}, "base"),
                (new_record, change, "compat1b"),
            ):
                if item["size"] != expected["size"] or item["sha256"] != expected["sha256"]:
                    raise RuntimeError(f"{label} SurfaceFlinger identity changed")
            old_contract, new_contract = elf_contract(old), elf_contract(new)
            for field in ("elf_class", "machine", "soname", "dt_needed"):
                if old_contract[field] != new_contract[field]:
                    raise RuntimeError(f"SurfaceFlinger dynamic contract changed: {field}")
            for undefined in (True, False):
                if AUDIO_AUDIT.symbols(old, undefined) != AUDIO_AUDIT.symbols(new, undefined):
                    raise RuntimeError("SurfaceFlinger dynamic symbol sets changed")
            closure = self.surfaceflinger_closure(new)
            if digest(Path(change["source_path"])) != new_record["sha256"]:
                raise RuntimeError("packaged SurfaceFlinger differs from guarded build output")
            self.run([sys.executable, str(REPO / self.cfg["source_contract"]["overlay"] / "prepare.py"),
                      "check", str(self.aosp)], output=self.audit / "source-check.log")

            preserved: dict[str, object] = {}
            for name, spec in self.cfg["preserved_runtime"].items():
                relative = str(spec["path"]).lstrip("/")
                actual = (
                    points["system"] / relative
                    if spec["path"].startswith("/system/")
                    else points["vendor"] / relative.removeprefix("vendor/")
                )
                item = record(actual)
                if item["size"] != spec["size"] or item["sha256"] != spec["sha256"]:
                    raise RuntimeError(f"preserved runtime changed: {name}")
                preserved[name] = item | {"partition_path": spec["path"]}

            system_vintf = self.run(
                [str(self.host / "checkvintf"), "--check-one", "--dirmap",
                 f"/system:{self.root / 'system'}"],
                output=self.audit / "vintf-system.log",
            )
            full_vintf = self.run([
                str(self.host / "checkvintf"), "--check-compat",
                "--dirmap", f"/system:{self.root / 'system'}",
                "--dirmap", f"/system_ext:{self.root / 'system_ext'}",
                "--dirmap", f"/vendor:{self.root / 'vendor'}",
                "--dirmap", f"/product:{self.root / 'product'}",
                "--dirmap", f"/odm:{self.root / 'odm'}",
                "--dirmap", f"/apex:{self.root / 'apex'}",
                "--property", "ro.product.first_api_level=31",
                "--kernel", f"5.4.302:{self.candidate / 'kernel-evidence/build-result/built.config'}",
            ], output=self.audit / "vintf-full.log", allowed={65})
            full_text = (self.audit / "vintf-full.log").read_text(errors="replace")
            if (
                full_vintf != 65
                or "For config CONFIG_NFS_FS, value = y but required n" not in full_text
                or re.findall(r"For config (CONFIG_[A-Z0-9_]+)", full_text) != ["CONFIG_NFS_FS"]
                or not full_text.rstrip().endswith("INCOMPATIBLE")
            ):
                raise RuntimeError("full VINTF is not the inherited NFS-only exit-65 result")

            result = {
                "schema": 1,
                "candidate": record(self.candidate / "x12-a16-dev-p3a-compat1b-r1.img"),
                "decision": "OFFLINE_CHECKED_READY_FOR_BOUNDED_PHYSICAL_VALIDATION",
                "physical_status": "NOT_YET_VALIDATED",
                "physical_device_actions_performed": False,
                "flash_performed": False,
                "classification": "P3A_RC_B_COMPAT1B_CANDIDATE_DEVELOPMENT_ONLY_NOT_R8_NOT_RELEASE",
                "filesystem": {
                    "e2fsck": "PASS_SYSTEM_VENDOR_PRODUCT_VENDOR_DLKM",
                    "vendor_byte_identical_to_fbm_r1": True,
                    "system_tree_delta": system_delta,
                    "vendor_tree_delta": vendor_delta,
                    "semantic_runtime_delta_count": 1,
                },
                "elf": {"base": old_contract, "compat1b": new_contract,
                        "imports_exports_dt_needed_soname": "IDENTICAL",
                        "namespace_closure": closure},
                "preserved_runtime": preserved,
                "frozen_artifacts": frozen,
                "avb_lp_outer": {
                    "system_vendor_vbmeta_system_vbmeta_vendor": "PASS",
                    "lp_metadata_and_extents": "EXACT_FBM_R1",
                    "sparse_raw_roundtrip": "PASS_BYTE_EXACT",
                    "imagewty_outer": "PASS",
                    "boot_kernel_vendor_dlkm_product": "BYTE_IDENTICAL_FBM_R1",
                },
                "vintf": {
                    "system": "PASS", "system_exit": system_vintf,
                    "full": "NOT_PASS_INHERITED_CONFIG_NFS_FS_MISMATCH_ONLY",
                    "full_exit": full_vintf,
                    "actual": "CONFIG_NFS_FS=y", "required": "CONFIG_NFS_FS=n",
                },
                "governance": {
                    "canonical_r7": "PASS_FROZEN_UNCHANGED",
                    "gate3": "PASS_WITH_EXPLICIT_USER_WAIVER_CLOSED",
                    "compat1a": "PHYSICAL_PASS_AUTHORIZED_SDR_1080P_YV12_BEHAVIOR_PRESERVED",
                    "audio_p1": "CLOSED", "p2": "COMPLETE",
                    "p3a": "PHYSICAL_FAIL_FORENSICS_COMPLETE",
                    "rc_a": "ORIGINAL_DRAIN_NULL_PHYSICAL_REPAIR_EFFECTIVE",
                    "rc_a2": "PHYSICAL_PASS_CLOSED",
                    "rc_b": "COMPAT1B_IMPLEMENTED_OFFLINE_CANDIDATE_BUILT_PHYSICAL_VALIDATION_PENDING",
                    "p3b_main10": "NOT_AUTHORIZED",
                    "r8": "NOT_AUTHORIZED_NOT_BUILT",
                },
                "limitations": [
                    "No physical device action, ADB, flash or playback occurred.",
                    "RC-A2 physical PASS is retained from the verified FBM-r1 evidence.",
                    "RC-B compatibility translation is offline only; downstream 4K import/render remains unproven.",
                    "Main10, HDR, AFBC and protected playback remain unauthorized.",
                    "Only the exact captured SDR replacement-buffer class is eligible, not general AFBC.",
                    "Full VINTF remains exit 65 for inherited CONFIG_NFS_FS and is not PASS.",
                ],
            }
            audit_path = self.audit / "offline-audit.json"
            audit_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
            build.update({
                "status": "OFFLINE_CHECKED", "decision": result["decision"],
                "physical_status": "NOT_YET_VALIDATED", "offline_audit": record(audit_path),
            })
            build_path.write_text(json.dumps(build, indent=2, sort_keys=True) + "\n")
            sums = [
                f"{digest(path)}  {path.name}" for path in sorted(self.candidate.iterdir())
                if path.is_file() and path.name != "SHA256SUMS"
            ]
            (self.candidate / "SHA256SUMS").write_text("\n".join(sums) + "\n")
        finally:
            for point in reversed(self.mounted):
                subprocess.run(["sudo", "umount", str(point)], check=False)
        print("OFFLINE_CHECKED_READY_FOR_BOUNDED_PHYSICAL_VALIDATION")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=CANDIDATE)
    parser.add_argument("--base", type=Path, default=BASE)
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--aosp", type=Path, default=AOSP)
    parser.add_argument("--tree-manifest", type=Path)
    args = parser.parse_args()
    if args.tree_manifest:
        print(json.dumps(strict_tree_manifest(args.tree_manifest), sort_keys=True))
        return
    Auditor(args).execute()


if __name__ == "__main__":
    main()
