#!/usr/bin/env python3
"""Build a16-dev-p3a-omx-r1 from exact audio-r1 with one guarded ELF patch."""
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


REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "configs/candidates/a16-dev-p3a-omx-r1.json"
AOSP = Path("/work/src/ubox10-a16-ceiling")
AUDIO_BUILDER_PATH = REPO / "scripts/build-a16-dev-audio-r1-candidate.py"
SPEC = importlib.util.spec_from_file_location("audio_r1_builder_for_p3a_omx_r1", AUDIO_BUILDER_PATH)
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
        self.audio_r1 = REPO / "out/candidates/a16-dev-audio-r1"
        self.patched_omx = self.stage / "libOmxVdec.p3a-omx-r1.so"

    def setup(self) -> None:
        if self.final.exists():
            raise RuntimeError(f"refusing to overwrite existing candidate: {self.final}")
        governance = self.raw_cfg["governance"]
        if (
            self.raw_cfg["status"] != "P3A_RC_A_BINARY_PATCH_AUTHORIZED"
            or governance["rc_b"] != "DEFERRED_EXPECTED_NEXT_BOUNDARY"
            or governance["p3b_main10"] != "NOT_AUTHORIZED"
            or governance["r8_authorized"]
            or governance["r8_built"]
            or governance["release"]
        ):
            raise RuntimeError("P3-A RC-A candidate governance changed")

        self.stage.mkdir(parents=True)
        self.require(self.base, self.raw_cfg["base_candidate"], "exact physical audio-r1 outer")
        for name, record in self.raw_cfg["base_artifacts"].items():
            self.require(source(record["path"]), record, f"exact audio-r1 artifact {name}")

        readiness = source(self.raw_cfg["repair_readiness"]["report"])
        report = readiness.read_text(encoding="utf-8")
        for marker in (
            "RC-A = READY_FOR_NARROW_BINARY_PATCH",
            "A — read color aspects from the peeked `picture`",
            "RC-B/compat1b is deferred and unchanged",
        ):
            if marker not in report:
                raise RuntimeError(f"repair-readiness contract missing: {marker}")

        patcher = source(self.raw_cfg["patcher"]["path"])
        self.require(
            patcher,
            {"size": patcher.stat().st_size, "sha256": self.raw_cfg["patcher"]["sha256"]},
            "exact deterministic RC-A patcher",
        )
        change = self.raw_cfg["runtime_change"]
        original = self.stage / "libOmxVdec.audio-r1.so"
        self.debugfs(
            source(self.raw_cfg["base_artifacts"]["vendor_a"]["path"]),
            f"dump -p {change['internal_path']} {original}",
        )
        self.require(original, change["baseline"], "exact audio-r1 libOmxVdec")
        self.run(
            [sys.executable, str(patcher), "--input", str(original),
             "--output", str(self.patched_omx)],
            output=self.stage / "patch-result.json",
        )
        self.require(self.patched_omx, change["candidate"], "patched RC-A libOmxVdec")

        before = original.read_bytes()
        after = self.patched_omx.read_bytes()
        changed = [index for index, pair in enumerate(zip(before, after)) if pair[0] != pair[1]]
        if changed != change["changed_byte_offsets"] or len(before) != len(after):
            raise RuntimeError(f"unexpected RC-A byte delta: {changed}")
        elf_before = DIAG1.elf_contract(original)
        elf_after = DIAG1.elf_contract(self.patched_omx)
        for field in ("elf_class", "architecture", "build_id", "soname", "dt_needed",
                      "exports", "strong_exports", "weak_exports"):
            if elf_before[field] != elf_after[field]:
                raise RuntimeError(f"RC-A patch changed ELF contract field: {field}")

        objdump = self.args.aosp / "prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump"
        windows: dict[str, str] = {}
        for label, target in (("before", original), ("after", self.patched_omx)):
            text = command_output([
                str(objdump), "-d", "--demangle", "--triple=thumbv7-linux-gnueabi",
                "--start-address=0xde58", "--stop-address=0xe470", str(target),
            ])
            windows[label] = text
            (self.stage / f"omx-drain-{label}-disassembly.txt").write_text(
                text, encoding="utf-8"
            )
        if not re.search(r"e130:\s+f8d8 0000\s+ldr\.w\s+r0, \[r8\]", windows["before"]):
            raise RuntimeError("original NULL-prone slot load was not decoded")
        if not re.search(r"e130:\s+ea4f 000c\s+mov\.w\s+r0, r12", windows["after"]):
            raise RuntimeError("patched peek-register selection was not decoded")
        for marker in (
            "de72: 4606",  # save NextPictureInfo result in r6
            "de7a: 2e00",  # NULL check
            "dea0: 46b4",  # retain peek in r12
            "e128: f8cd c04c",  # spill same peek value
            "e426:",  # later RequestPicture call
            "e42c:",  # store acquired picture into +0x58e0
            "e460:",  # later acquisition NULL check
        ):
            if marker not in windows["before"] or marker not in windows["after"]:
                raise RuntimeError(f"drain lifecycle marker changed or missing: {marker}")

        shutil.copytree(self.audio_r1 / "kernel-evidence", self.stage / "kernel-evidence")
        for name in (
            "final-build-variables.txt", "mali-intake.json", "active-product-build.prop.r5",
            "runtime-product-source-audit.json", "boringssl_self_test64",
        ):
            shutil.copyfile(self.audio_r1 / name, self.stage / name)
        for name, record in self.raw_cfg["preserved_runtime"].items():
            item = self.audio_r1 / record["candidate_file"]
            self.require(item, record, f"preserved audio-r1 runtime {name}")
            shutil.copyfile(item, self.stage / f"preserved-{name}")

    def prepare_system(self) -> tuple[Path, dict[str, object]]:
        spec = self.raw_cfg["base_artifacts"]["system_a"]
        original = source(spec["path"])
        system = self.stage / "system_a.img"
        shutil.copyfile(original, system)
        self.require(system, spec, "byte-preserved audio-r1 system")
        self.run(["e2fsck", "-fn", str(system)])
        self.verify_avb_partition(system, "system", self.cfg["avb"]["system"]["key_relative"])
        return system, {
            "base_audio_r1": SHARED.record(original), "candidate": SHARED.record(system),
            "tree_delta": {"added": [], "removed": [], "changed": []},
            "byte_preserved_from_audio_r1": True, "ext4": "PASS", "avb": "PASS",
        }

    def replace_omx(self, image: Path) -> dict[str, object]:
        change = self.raw_cfg["runtime_change"]
        internal = change["internal_path"]
        parent = "/lib"
        parent_times = self.inode_times(self.debugfs(image, f"stat {parent}", capture=True))
        old = self.stage / "installed-audio-r1-libOmxVdec.so"
        self.debugfs(image, f"dump -p {internal} {old}")
        self.require(old, change["baseline"], "installed exact audio-r1 libOmxVdec")
        self.debugfs(image, f"rm {internal}")
        self.debugfs(image, f"write {self.patched_omx} {internal}")
        self.debugfs(image, f"set_inode_field {internal} mode 010{change['mode']}")
        self.debugfs(image, f"set_inode_field {internal} uid {change['uid']}")
        self.debugfs(image, f"set_inode_field {internal} gid {change['gid']}")
        for field in ("ctime", "atime", "mtime", "crtime"):
            self.debugfs(image, f"set_inode_field {internal} {field} {change[field]}")
        self.debugfs(image, f'ea_set {internal} security.selinux "{change["selinux"]}\\000"')
        self.restore_times(image, parent, parent_times)
        new = self.stage / "installed-p3a-omx-r1-libOmxVdec.so"
        self.debugfs(image, f"dump -p {internal} {new}")
        self.require(new, change["candidate"], "installed patched libOmxVdec")
        return {
            "partition_path": change["partition_path"], "reason": change["reason"],
            "audio_r1": SHARED.record(old), "p3a_omx_r1": SHARED.record(new),
            "file_offset": change["file_offset"],
            "virtual_address": change["virtual_address"],
            "original_bytes": change["original_bytes"],
            "patched_bytes": change["patched_bytes"],
            "changed_byte_offsets": change["changed_byte_offsets"],
            "changed_byte_count": change["changed_byte_count"],
            "instruction_width": change["instruction_width"],
            "build_id_note_retained": change["candidate"]["build_id_note_retained"],
            "elf_contract_preserved": True,
        }

    def prepare_vendor(self) -> tuple[Path, dict[str, object]]:
        spec = self.raw_cfg["base_artifacts"]["vendor_a"]
        original = source(spec["path"])
        vendor = self.stage / "vendor_a.img"
        shutil.copyfile(original, vendor)
        self.require(vendor, spec, "exact audio-r1 vendor")
        with self.deterministic_ext4_time():
            self.run([sys.executable, str(self.avbtool), "erase_footer", "--image", str(vendor)])
            self.run(["e2fsck", "-fn", str(vendor)])
            replacement = self.replace_omx(vendor)
            self.run(["e2fsck", "-fy", str(vendor)], allowed={0, 1})
            self.run(["e2fsck", "-fn", str(vendor)])
        avb = self.cfg["avb"]["vendor"]
        self.run([
            sys.executable, str(self.avbtool), "add_hashtree_footer", "--image", str(vendor),
            "--partition_name", "vendor", "--partition_size", str(avb["partition_size"]),
            "--hash_algorithm", "sha256", "--salt", avb["salt"],
            "--prop", f"com.android.build.vendor.fingerprint:{avb['fingerprint']}",
            "--prop", f"com.android.build.vendor.os_version:{avb['os_version']}",
        ])
        self.verify_avb_partition(vendor, "vendor", None)
        return vendor, {
            "base_audio_r1": SHARED.record(original), "candidate": SHARED.record(vendor),
            "tree_delta": {"added": [], "removed": [], "changed": ["lib/libOmxVdec.so"]},
            "replaced": {"libOmxVdec32": replacement}, "ext4": "PASS", "avb": "PASS",
        }

    def build_super(self, system: Path, vendor: Path) -> tuple[Path, dict[str, object]]:
        sparse, audit = super().build_super(system, vendor)
        audit["base_audio_r1_raw"] = audit.pop("base_compat1a_raw")
        audit["lp_metadata_and_extents_exact_audio_r1"] = audit.pop(
            "lp_metadata_and_extents_exact_compat1a"
        )
        audit["bytes_outside_changed_extents_exact_audio_r1"] = audit.pop(
            "bytes_outside_changed_extents_exact_compat1a"
        )
        return sparse, audit

    def finish(self, firmware: Path, system_audit: dict[str, object],
               vendor_audit: dict[str, object], super_audit: dict[str, object],
               outer_audit: dict[str, object], vbmeta_system: Path,
               vbmeta_vendor: Path) -> None:
        for name, key in (("boot.fex", "boot"), ("vendor_dlkm_a.img", "vendor_dlkm")):
            shutil.copyfile(source(self.raw_cfg["base_artifacts"][key]["path"]), self.stage / name)
        outer_audit["all_other_payload_bytes_exact_audio_r1"] = outer_audit.pop(
            "all_other_payload_bytes_exact_r7"
        )
        result = {
            "schema": 1, "id": self.candidate_id, "label": self.raw_cfg["label"],
            "status": "PACKAGED_AWAITING_FULL_OFFLINE_AUDIT",
            "decision": "PENDING_FULL_OFFLINE_AUDIT", "physical_status": "NOT_YET_VALIDATED",
            "physical_device_actions_performed": False, "flash_performed": False,
            "elapsed_seconds": round(time.time() - self.started, 1),
            "source": {
                "base_repository_commit": "4ca27333b3b845864bd19de03f82e0cf51c70b5d",
                "repair_readiness": self.raw_cfg["repair_readiness"],
                "patcher": self.raw_cfg["patcher"], "android_rebuilt": False,
                "kernel_rebuilt": False, "rc_b_modified": False,
            },
            "base_audio_r1": SHARED.record(self.base), "firmware": SHARED.record(firmware),
            "system": system_audit, "vendor": vendor_audit, "super": super_audit,
            "outer": outer_audit, "vbmeta_system": SHARED.record(vbmeta_system),
            "vbmeta_vendor": SHARED.record(vbmeta_vendor),
            "boot": {"candidate": SHARED.record(self.stage / "boot.fex"),
                     "byte_preserved_from_audio_r1": True},
            "vendor_dlkm": {"candidate": SHARED.record(self.stage / "vendor_dlkm_a.img"),
                            "byte_preserved_from_audio_r1": True, "module_count": 22},
            "kernel": SHARED.record(self.stage / "kernel-evidence/Image"),
            "runtime_delta": vendor_audit["replaced"],
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
