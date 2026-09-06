#!/usr/bin/env python3
"""Fail-closed offline audit for the bounded a16-dev-p3a-thumbnail-r1 candidate."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


REPO = Path(__file__).resolve().parents[1]
AOSP = Path("/work/src/ubox10-a16-ceiling")
CANDIDATE = REPO / "out/candidates/a16-dev-p3a-thumbnail-r1"
BASE = REPO / "out/candidates/a16-dev-p3a-compat1b-r1"
CONFIG = REPO / "configs/candidates/a16-dev-p3a-thumbnail-r1.json"
AUDIO_AUDIT_PATH = REPO / "scripts/audit-a16-dev-audio-r1.py"
SPEC = importlib.util.spec_from_file_location("audio_r1_audit_for_thumbnail_r1", AUDIO_AUDIT_PATH)
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


def exact_command_output(command: list[str]) -> str:
    return subprocess.check_output(command, text=True, errors="replace")


def stable_elf_surfaces(path: Path) -> dict[str, str]:
    # Header/section/file offsets intentionally change for a new RX segment;
    # runtime VAs, relocations, dynamic ABI and ARM attributes must not.
    commands = {"dynamic": ["-d"], "relocations": ["-r"], "notes": ["-n"],
                "arm_attributes": ["-A"], "dynamic_symbols": ["--dyn-syms"]}
    return {name: re.sub(r'Dynamic section at offset 0x[0-9a-f]+', 'Dynamic section at relocated file offset', exact_command_output(["readelf", "-W", *args, str(path)]))
            for name, args in commands.items()}


class Auditor(AUDIO_AUDIT.Auditor):
    def full_vendor_tree(self, root: Path, label: str) -> dict:
        # Reuse the fail-closed privileged HOST reader, never the old walk that
        # silently skipped directories. These mounts are loop,ro,noload.
        output = self.audit / f"{label}-tree.json"
        self.run(["sudo", sys.executable,
                  str(REPO / "scripts/audit-a16-dev-p3a-compat1b-r1.py"),
                  "--tree-manifest", str(root)], output=output)
        manifest = json.loads(output.read_text())
        if "lib/libOmxVdec.so" not in manifest:
            raise RuntimeError("incomplete vendor tree: libOmxVdec missing")
        return manifest

    def execute(self) -> None:
        if self.audit.exists():
            raise RuntimeError(f"refusing to overwrite audit: {self.audit}")
        self.audit.mkdir(parents=True)
        build_path = self.candidate / "build-result.json"
        build = json.loads(build_path.read_text(encoding="utf-8"))
        if build["status"] != "PACKAGED_AWAITING_FULL_OFFLINE_AUDIT":
            raise RuntimeError("candidate is not in packaged pre-audit state")
        if record(self.base / "x12-a16-dev-p3a-compat1b-r1.img") != {
            "path": str(self.base / "x12-a16-dev-p3a-compat1b-r1.img"),
            "size": self.cfg["base_candidate"]["size"],
            "sha256": self.cfg["base_candidate"]["sha256"],
        }:
            raise RuntimeError("exact tested compat1b base identity changed")

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
                 str(self.candidate / "x12-a16-dev-p3a-thumbnail-r1.img")],
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
                raise RuntimeError("LP metadata/extents differ from exact compat1b")
            with tempfile.TemporaryDirectory(prefix="ubox-p3a-omx-sparse-", dir="/work") as directory:
                raw = Path(directory) / "super.raw.img"
                self.run(
                    [str(self.host / "simg2img"), str(self.candidate / "super.fex"), str(raw)],
                    output=self.audit / "sparse-roundtrip.log",
                )
                if digest(raw) != digest(self.candidate / "super.raw.img"):
                    raise RuntimeError("sparse-to-raw round trip differs")

            points = {name: self.mount(name, path) for name, path in images.items()}
            base_vendor = self.mount("audio-r1-vendor", self.base / "vendor_a.img")
            self.setup_root(points)
            vendor_delta = delta(self.full_vendor_tree(base_vendor, "base-vendor"),
                                 self.full_vendor_tree(points["vendor"], "candidate-vendor"))
            expected_delta = {"added": [], "removed": [], "changed": ["lib/libOmxVdec.so"]}
            if vendor_delta != expected_delta:
                raise RuntimeError(f"semantic vendor delta expanded: {vendor_delta}")
            if record(self.base / "system_a.img")["sha256"] != record(images["system"])["sha256"]:
                raise RuntimeError("compat1b system image changed")

            change = self.cfg["runtime_change"]
            old = self.candidate / "libOmxVdec.compat1b.so"
            new = points["vendor"] / "lib/libOmxVdec.so"
            old_record, new_record = record(old), record(new)
            for item, expected, label in (
                (old_record, change["baseline"], "original"),
                (new_record, change["candidate"], "patched"),
            ):
                if item["size"] != expected["size"] or item["sha256"] != expected["sha256"]:
                    raise RuntimeError(f"{label} libOmxVdec identity changed")
            # Reproduce the complete deterministic patch rather than incorrectly
            # comparing zipped file offsets after segment insertion.
            patcher = REPO / self.cfg["patcher"]["path"]
            if digest(patcher) != self.cfg["patcher"]["sha256"]:
                raise RuntimeError("guarded patcher identity changed")
            reproduced = self.audit / "reproduced-libOmxVdec.so"
            self.run([sys.executable, str(patcher), "--input", str(old),
                      "--output", str(reproduced)], output=self.audit / "patch-proof.json")
            if reproduced.read_bytes() != new.read_bytes():
                raise RuntimeError("packaged OMX does not equal exact guarded patch")
            patch_proof = json.loads((self.audit / "patch-proof.json").read_text())
            old_contract, new_contract = elf_contract(old), elf_contract(new)
            for field in ("elf_class", "machine", "build_id", "soname", "dt_needed",
                          "strong_import_count", "strong_export_count"):
                if old_contract[field] != new_contract[field]:
                    raise RuntimeError(f"patched ELF changed dynamic contract: {field}")
            if stable_elf_surfaces(old) != stable_elf_surfaces(new):
                raise RuntimeError("patched ELF changed dynamic/relocation/attribute ABI")
            closure = self.namespace_closure(new)
            disassembly_records = {}
            for revision in ("clang-r547379", "clang-r530567"):
                tool = self.aosp / f"prebuilts/clang/host/linux-x86/{revision}/bin/llvm-objdump"
                text = exact_command_output([str(tool), "-d", "--triple=thumbv7-linux-gnueabi", str(new)])
                (self.audit / f"omx-patched-{revision}.txt").write_text(text)
                if not re.search(r"e130:\s+ea4f 000c\s+mov\.w\s+r0, r12", text):
                    raise RuntimeError(f"{revision}: prior RC-A operand correction absent")
                for marker in self.cfg["runtime_change"].get("disassembly_markers", []):
                    if marker not in text:
                        raise RuntimeError(f"{revision}: guard instruction missing: {marker}")
                disassembly_records[revision] = "PASS_RETAINED_RCA_AND_APPROVED_GUARD"

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
                "candidate": record(self.candidate / "x12-a16-dev-p3a-thumbnail-r1.img"),
                "decision": "OFFLINE_CHECKED_READY_FOR_BOUNDED_PHYSICAL_VALIDATION",
                "physical_status": "NOT_YET_VALIDATED",
                "physical_device_actions_performed": False,
                "flash_performed": False,
                "classification": "NON_SURFACE_CPU_THUMBNAIL_REPAIR_CANDIDATE_DEVELOPMENT_ONLY_NOT_R8_NOT_RELEASE",
                "filesystem": {
                    "e2fsck": "PASS_SYSTEM_VENDOR_PRODUCT_VENDOR_DLKM",
                    "system_byte_identical_to_compat1b": True,
                    "system_tree_delta": {"added": [], "removed": [], "changed": []},
                    "vendor_tree_delta": vendor_delta,
                    "semantic_runtime_delta_count": 1,
                },
                "elf": {
                    "compat1b": old_record, "thumbnail_r1": new_record,
                    "guarded_patch_proof": patch_proof,
                    "reproduced_exactly": True,
                    "dynamic_symbols_relocations_attributes": "IDENTICAL",
                    "build_id": old_contract["build_id"],
                    "build_id_note": "RETAINED_ORIGINAL_NOT_CANONICAL_PATCH_IDENTITY",
                    "canonical_patched_identity": new_record["sha256"],
                    "namespace_closure": closure,
                },
                "disassembly": "PASS_APPROVED_GUARD_AND_RETAINED_RCA",
                "disassemblers": disassembly_records,
                "preserved_runtime": preserved,
                "avb_lp_outer": {
                    "system_vendor_vbmeta_system_vbmeta_vendor": "PASS",
                    "lp_metadata_and_extents": "EXACT_COMPAT1B",
                    "sparse_raw_roundtrip": "PASS_BYTE_EXACT",
                    "imagewty_outer": "PASS",
                    "boot_kernel_vendor_dlkm_product": "BYTE_IDENTICAL_COMPAT1B",
                },
                "vintf": {
                    "system": "PASS", "system_exit": system_vintf,
                    "full": "NOT_PASS_INHERITED_CONFIG_NFS_FS_MISMATCH_ONLY",
                    "full_exit": full_vintf,
                    "actual": "CONFIG_NFS_FS=y", "required": "CONFIG_NFS_FS=n",
                },
                "governance": self.cfg["governance"],
                "limitations": [
                    "No physical device action, ADB, flash or playback occurred.",
                    "Thumbnail repair is offline only until a bounded physical retest.",
                    "Passing RC-A/RC-A2/audio and compat1b Surface path are retained.",
                    "Main10, HDR, AFBC and protected playback remain unauthorized.",
                    "The proprietary original Build ID note is retained; patched SHA256 is canonical.",
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
    Auditor(parser.parse_args()).execute()


if __name__ == "__main__":
    main()
