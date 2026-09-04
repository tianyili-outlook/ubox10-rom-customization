#!/usr/bin/env python3
"""Fail-closed offline audit for the bounded a16-dev-p3a-omx-r1 candidate."""
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
CANDIDATE = REPO / "out/candidates/a16-dev-p3a-omx-r1"
BASE = REPO / "out/candidates/a16-dev-audio-r1"
CONFIG = REPO / "configs/candidates/a16-dev-p3a-omx-r1.json"
AUDIO_AUDIT_PATH = REPO / "scripts/audit-a16-dev-audio-r1.py"
SPEC = importlib.util.spec_from_file_location("audio_r1_audit_for_p3a_omx_r1", AUDIO_AUDIT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import audit: {AUDIO_AUDIT_PATH}")
AUDIO_AUDIT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = AUDIO_AUDIT
SPEC.loader.exec_module(AUDIO_AUDIT)

digest = AUDIO_AUDIT.digest
record = AUDIO_AUDIT.record
elf_contract = AUDIO_AUDIT.elf_contract
tree_manifest = AUDIO_AUDIT.tree_manifest
delta = AUDIO_AUDIT.delta
KEY = AUDIO_AUDIT.KEY
AVBTOOL = AUDIO_AUDIT.AVBTOOL


def exact_command_output(command: list[str]) -> str:
    return subprocess.check_output(command, text=True, errors="replace")


def static_elf_surfaces(path: Path) -> dict[str, str]:
    commands = {
        "elf_header": ["readelf", "-W", "-h"],
        "program_headers": ["readelf", "-W", "-l"],
        "section_layout": ["readelf", "-W", "-S"],
        "dynamic": ["readelf", "-W", "-d"],
        "relocations": ["readelf", "-W", "-r"],
        "notes": ["readelf", "-W", "-n"],
        "arm_attributes": ["readelf", "-W", "-A"],
        "dynamic_symbols": ["readelf", "-W", "--dyn-syms"],
    }
    return {name: exact_command_output([*command, str(path)]) for name, command in commands.items()}


class Auditor(AUDIO_AUDIT.Auditor):
    def execute(self) -> None:
        if self.audit.exists():
            raise RuntimeError(f"refusing to overwrite audit: {self.audit}")
        self.audit.mkdir(parents=True)
        build_path = self.candidate / "build-result.json"
        build = json.loads(build_path.read_text(encoding="utf-8"))
        if build["status"] != "PACKAGED_AWAITING_FULL_OFFLINE_AUDIT":
            raise RuntimeError("candidate is not in packaged pre-audit state")
        if record(self.base / "x12-a16-dev-audio-r1.img") != {
            "path": str(self.base / "x12-a16-dev-audio-r1.img"),
            "size": self.cfg["base_candidate"]["size"],
            "sha256": self.cfg["base_candidate"]["sha256"],
        }:
            raise RuntimeError("exact physically proven audio-r1 base identity changed")

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
                 str(self.candidate / "x12-a16-dev-p3a-omx-r1.img")],
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
                raise RuntimeError("LP metadata/extents differ from exact audio-r1")
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
            vendor_delta = delta(tree_manifest(base_vendor), tree_manifest(points["vendor"]))
            expected_delta = {"added": [], "removed": [], "changed": ["lib/libOmxVdec.so"]}
            if vendor_delta != expected_delta:
                raise RuntimeError(f"semantic vendor delta expanded: {vendor_delta}")
            if record(self.base / "system_a.img")["sha256"] != record(images["system"])["sha256"]:
                raise RuntimeError("audio-r1 system image changed")

            change = self.cfg["runtime_change"]
            old = self.candidate / "libOmxVdec.audio-r1.so"
            new = points["vendor"] / "lib/libOmxVdec.so"
            old_record, new_record = record(old), record(new)
            for item, expected, label in (
                (old_record, change["baseline"], "original"),
                (new_record, change["candidate"], "patched"),
            ):
                if item["size"] != expected["size"] or item["sha256"] != expected["sha256"]:
                    raise RuntimeError(f"{label} libOmxVdec identity changed")
            original = old.read_bytes()
            patched = new.read_bytes()
            changed = [index for index, pair in enumerate(zip(original, patched)) if pair[0] != pair[1]]
            if changed != change["changed_byte_offsets"] or len(original) != len(patched):
                raise RuntimeError(f"unexpected patched ELF bytes: {changed}")
            offset = change["file_offset"]
            if original[offset:offset + 4].hex(" ") != change["original_bytes"]:
                raise RuntimeError("original instruction bytes changed")
            if patched[offset:offset + 4].hex(" ") != change["patched_bytes"]:
                raise RuntimeError("patched instruction bytes changed")

            old_contract, new_contract = elf_contract(old), elf_contract(new)
            for field in ("elf_class", "machine", "build_id", "soname", "dt_needed",
                          "strong_import_count", "strong_export_count"):
                if old_contract[field] != new_contract[field]:
                    raise RuntimeError(f"patched ELF changed dynamic contract: {field}")
            old_surfaces, new_surfaces = static_elf_surfaces(old), static_elf_surfaces(new)
            changed_surfaces = [name for name in old_surfaces if old_surfaces[name] != new_surfaces[name]]
            if changed_surfaces:
                raise RuntimeError(f"patched ELF changed static contract: {changed_surfaces}")
            closure = self.namespace_closure(new)

            disassembly_records: dict[str, str] = {}
            for revision in ("clang-r547379", "clang-r530567"):
                tool = self.aosp / f"prebuilts/clang/host/linux-x86/{revision}/bin/llvm-objdump"
                text = exact_command_output([
                    str(tool), "-d", "--demangle", "--triple=thumbv7-linux-gnueabi",
                    "--start-address=0xde58", "--stop-address=0xfb00", str(new),
                ])
                (self.audit / f"omx-drain-patched-{revision}.txt").write_text(text)
                for marker in (
                    "de72: 4606", "de7a: 2e00", "dea0: 46b4",
                    "e130: ea4f 000c", "mov.w\tr0, r12", "e138: e9d0 3127",
                    "e426:", "e42c:", "e460:", "fa74:", "faa4:", "faaa:",
                ):
                    if marker not in text:
                        raise RuntimeError(f"{revision} lifecycle disassembly missing: {marker}")
                disassembly_records[revision] = "PASS"

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
                "candidate": record(self.candidate / "x12-a16-dev-p3a-omx-r1.img"),
                "decision": "OFFLINE_CHECKED_READY_FOR_BOUNDED_PHYSICAL_VALIDATION",
                "physical_status": "NOT_YET_VALIDATED",
                "physical_device_actions_performed": False,
                "flash_performed": False,
                "classification": "P3A_RC_A_REPAIR_CANDIDATE_DEVELOPMENT_ONLY_NOT_R8_NOT_RELEASE",
                "filesystem": {
                    "e2fsck": "PASS_SYSTEM_VENDOR_PRODUCT_VENDOR_DLKM",
                    "system_byte_identical_to_audio_r1": True,
                    "system_tree_delta": {"added": [], "removed": [], "changed": []},
                    "vendor_tree_delta": vendor_delta,
                    "semantic_runtime_delta_count": 1,
                },
                "elf": {
                    "audio_r1": old_record, "p3a_omx_r1": new_record,
                    "changed_byte_offsets": changed, "changed_byte_count": len(changed),
                    "patch_range": [offset, offset + 4],
                    "all_bytes_outside_patch_range_identical": True,
                    "elf_header_program_headers_sections_dynamic_symbols_relocations_attributes":
                        "BYTE_OR_TEXT_IDENTICAL",
                    "gnu_debugdata": "BYTE_IDENTICAL_BY_OUTSIDE_PATCH_PROOF",
                    "build_id": old_contract["build_id"],
                    "build_id_note": "RETAINED_ORIGINAL_NOT_CANONICAL_PATCH_IDENTITY",
                    "canonical_patched_identity": new_record["sha256"],
                    "namespace_closure": closure,
                },
                "disassembly": "PASS_PEEK_R12_SELECTED_REQUEST_FBD_RETURN_UNCHANGED",
                "disassemblers": disassembly_records,
                "preserved_runtime": preserved,
                "avb_lp_outer": {
                    "system_vendor_vbmeta_system_vbmeta_vendor": "PASS",
                    "lp_metadata_and_extents": "EXACT_AUDIO_R1",
                    "sparse_raw_roundtrip": "PASS_BYTE_EXACT",
                    "imagewty_outer": "PASS",
                    "boot_kernel_vendor_dlkm_product": "BYTE_IDENTICAL_AUDIO_R1",
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
                    "compat1a": "PHYSICAL_PASS_AUTHORIZED_SDR_1080P_YV12_UNCHANGED",
                    "audio_p1": "CLOSED", "p2": "COMPLETE",
                    "p3a": "PHYSICAL_FAIL_FORENSICS_COMPLETE",
                    "rc_a": "PATCH_IMPLEMENTED_OFFLINE_CANDIDATE_BUILT_PHYSICAL_VALIDATION_PENDING",
                    "rc_b": "DEFERRED_EXPECTED_NEXT_BOUNDARY",
                    "p3b_main10": "NOT_AUTHORIZED",
                    "r8": "NOT_AUTHORIZED_NOT_BUILT",
                },
                "limitations": [
                    "No physical device action, ADB, flash or playback occurred.",
                    "RC-A is not physical PASS until one bounded hardware retest.",
                    "RC-B/compat1b is unchanged and expected to remain the next possible boundary.",
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
