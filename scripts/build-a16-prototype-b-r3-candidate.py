#!/usr/bin/env python3
"""Build B r3 by restoring only the accepted root /vendor mountpoint."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import time


REPO = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO / "configs/candidates/a16-prototype-b-r3.json"
DEFAULT_AOSP = Path("/work/src/ubox10-a16-ceiling")
CHUNK = 8 * 1024 * 1024

R2_PATH = REPO / "scripts/build-a16-prototype-b-r2-candidate.py"
R2_SPEC = importlib.util.spec_from_file_location("a16_b_r2_builder_for_r3", R2_PATH)
if R2_SPEC is None or R2_SPEC.loader is None:
    raise RuntimeError(f"cannot import r2 builder helpers: {R2_PATH}")
R2 = importlib.util.module_from_spec(R2_SPEC)
sys.modules[R2_SPEC.name] = R2
R2_SPEC.loader.exec_module(R2)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(CHUNK), b""):
            value.update(block)
    return value.hexdigest().upper()


def record(path: Path) -> dict[str, object]:
    return {"path": str(path), "size": path.stat().st_size, "sha256": digest(path)}


def source(path: str) -> Path:
    value = Path(path)
    return value if value.is_absolute() else REPO / value


class Builder(R2.Builder):
    def setup(self) -> None:
        if self.final.exists():
            raise RuntimeError(f"refusing to overwrite existing candidate: {self.final}")
        if self.raw_cfg["status"] != "ROOT_CAUSE_PROVEN_SINGLE_CAUSE_R3_AUTHORIZED":
            raise RuntimeError("r3 single-cause build is not authorized")
        # Call the shared B1 setup directly; r2's wrapper accepts only the r2
        # authorization string. All B1 source/provider/kernel gates still run.
        R2.R1.Builder.setup(self)
        for name, spec in self.raw_cfg["base_artifacts"].items():
            self.require(source(str(spec["path"])), spec, f"frozen r2 {name}")

    def prepare_system(self) -> tuple[Path, dict[str, object]]:
        spec = self.raw_cfg["base_artifacts"]["system_a"]
        original = source(str(spec["path"]))
        system = self.stage / "system_a.img"
        shutil.copyfile(original, system)

        before = self.debugfs(system, "stat /vendor", capture=True)
        if "Type: symlink" not in before or 'Fast link dest: "/system/vendor"' not in before:
            raise RuntimeError("r2 system does not contain the proven /vendor symlink")
        self.run([sys.executable, str(self.avbtool), "erase_footer", "--image", str(system)])
        avb = self.cfg["avb"]["system"]
        if system.stat().st_size != avb["original_filesystem_size"]:
            raise RuntimeError("r2 system AVB original image size changed")
        self.run(["e2fsck", "-fn", str(system)])

        contract = self.raw_cfg["root_mountpoint_contract"]["r4"]
        previous_fake_time = os.environ.get("E2FSPROGS_FAKE_TIME")
        os.environ["E2FSPROGS_FAKE_TIME"] = str(int(str(contract["crtime"]), 16))
        try:
            self.debugfs(system, "rm /vendor")
            self.debugfs(system, "mkdir /vendor")
            for field, value in (
                ("mode", "040755"), ("uid", "0"), ("gid", "2000"),
                ("ctime", str(contract["ctime"])), ("atime", str(contract["atime"])),
                ("mtime", str(contract["mtime"])), ("crtime", str(contract["crtime"])),
            ):
                self.debugfs(system, f"set_inode_field /vendor {field} {value}")
            self.debugfs(
                system,
                'ea_set /vendor security.selinux "u:object_r:vendor_file:s0\\000"',
            )
            # Replacing a symlink with a directory intentionally increments the
            # root link count. Restore every other root inode timestamp to r2.
            for field, value in (
                ("ctime", "0x6a8ffae2"), ("atime", "0x6a8ffae2"),
                ("mtime", "0x6a8ffae2"), ("crtime", "0x6a8ffae4"),
            ):
                self.debugfs(system, f"set_inode_field / {field} {value}")
            self.run(["e2fsck", "-fy", str(system)], allowed={0, 1})
        finally:
            if previous_fake_time is None:
                os.environ.pop("E2FSPROGS_FAKE_TIME", None)
            else:
                os.environ["E2FSPROGS_FAKE_TIME"] = previous_fake_time

        vendor = self.debugfs(system, "stat /vendor", capture=True)
        xattrs = self.debugfs(system, "ea_list /vendor", capture=True)
        for fragment in ("Type: directory", "Mode:  0755", "User:     0", "Group:  2000"):
            if fragment not in vendor:
                raise RuntimeError(f"r3 /vendor inode contract mismatch: {fragment}")
        if contract["selinux"] not in xattrs:
            raise RuntimeError("r3 /vendor SELinux label mismatch")
        for path in ("/odm", "/metadata", "/vendor_dlkm", "/oem"):
            output = self.debugfs(system, f"stat {path}", capture=True)
            if "Type: directory" not in output:
                raise RuntimeError(f"r3 canonical root directory missing: {path}")
        for path, target in (
            ("/product", "/system/product"),
            ("/system_ext", "/system/system_ext"),
        ):
            output = self.debugfs(system, f"stat {path}", capture=True)
            if "Type: symlink" not in output or f'Fast link dest: "{target}"' not in output:
                raise RuntimeError(f"r3 GSI root symlink contract changed: {path}")
        skip_mount = self.debugfs(
            system, "cat /system/system_ext/etc/init/config/skip_mount.cfg", capture=True
        )
        for mountpoint in ("/oem", "/product", "/system_ext"):
            if mountpoint not in skip_mount.splitlines():
                raise RuntimeError(f"r3 GSI skip-mount contract missing: {mountpoint}")
        self.run(["e2fsck", "-fn", str(system)])

        self.run([
            sys.executable, str(self.avbtool), "add_hashtree_footer",
            "--image", str(system), "--partition_name", "system",
            "--partition_size", str(avb["partition_size"]),
            "--hash_algorithm", "sha256", "--salt", str(avb["salt"]),
            "--do_not_generate_fec",
            "--prop", f"com.ubox10.candidate.id:{self.candidate_id}",
            "--prop", "com.ubox10.avb.fec:none",
            "--key", str(REPO / avb["key_relative"]),
            "--algorithm", avb["algorithm"],
        ])
        if system.stat().st_size != avb["partition_size"]:
            raise RuntimeError("r3 signed system size mismatch")
        self.verify_avb_partition(system, "system", avb["key_relative"])
        return system, {
            "base_r2": record(original),
            "candidate": record(system),
            "filesystem_bytes_before_avb": avb["original_filesystem_size"],
            "ext4": "PASS",
            "avb_hashtree_no_fec": "PASS",
            "semantic_delta": ["replace root /vendor symlink with accepted empty directory"],
            "root_mountpoint_contract": self.raw_cfg["root_mountpoint_contract"],
            "all_other_b1_system_semantics_expected_preserved": True,
        }

    def pack_outer(
        self, super_sparse: Path, vbmeta_system: Path, vbmeta_vendor: Path
    ) -> tuple[Path, dict[str, object]]:
        self.require(
            vbmeta_vendor, self.raw_cfg["base_artifacts"]["vbmeta_vendor"],
            "byte-preserved r2 vbmeta_vendor",
        )
        before = R2.R1.PACK.outer_payloads(self.base)
        firmware = self.stage / f"x12-{self.candidate_id}.img"
        payload_audit = self.stage / "outer-payload-audit.json"
        self.run([
            sys.executable, str(REPO / "tools/pack_image_preserving.py"),
            "--source", str(self.base), "--output", str(firmware),
            "--replace", f"super.fex={super_sparse}",
            "--replace", f"vbmeta_system.fex={vbmeta_system}",
            "--audit", str(payload_audit),
        ])
        self.run([
            sys.executable, str(REPO / "tools/sunxi_image_tool.py"), "verify", str(firmware)
        ], output=self.stage / "candidate-outer-verify.log")
        after = R2.R1.PACK.outer_payloads(firmware)
        changed = sorted(
            name for name in before
            if before[name]["sha256_stored"] != after[name]["sha256_stored"]
        )
        expected = sorted(self.raw_cfg["outer_delta"]["changed_payloads_from_base"])
        if set(before) != set(after) or len(after) != 50 or changed != expected:
            raise RuntimeError(f"unexpected r3 outer delta: {changed}")
        return firmware, {
            "candidate": record(firmware),
            "entry_count": 50,
            "changed_payloads": changed,
            "preserved_payload_count": 46,
            "all_other_payload_bytes_exact_r2": True,
            "imagewty_verify": "PASS",
            "top_level_vbmeta_byte_preserved": before["vbmeta.fex"] == after["vbmeta.fex"],
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
            "status": "PACKAGED_AWAITING_FULL_OFFLINE_AUDIT",
            "decision": "PENDING_FULL_OFFLINE_AUDIT",
            "physical_device_actions_performed": False,
            "flash_authorized": False,
            "elapsed_seconds": round(time.time() - self.started, 1),
            "source": {
                "tag": self.cfg["android16"]["tag"],
                "manifest_commit": self.cfg["android16"]["manifest_commit"],
                "build_id": self.cfg["android16"]["build_id"],
                "build_number": self.cfg["android16"]["build_number"],
                "lunch": self.cfg["android16"]["lunch"],
                "android_system_rebuilt": False,
            },
            "base_r2": record(self.base),
            "firmware": record(firmware),
            "system": system_audit,
            "vendor": vendor_audit,
            "super": super_audit,
            "outer": outer_audit,
            "vbmeta_system": record(vbmeta_system),
            "vbmeta_vendor": record(vbmeta_vendor),
            "boot": {"candidate": record(self.stage / "boot.fex"), "byte_preserved_from_r2": True},
            "vendor_dlkm": {
                "candidate": record(self.stage / "vendor_dlkm_a.img"),
                "byte_preserved_from_r2": True,
                "module_count": 22,
            },
            "kernel": record(self.stage / "kernel-evidence/Image"),
            "kernel_rebuilt": False,
            "root_cause": self.raw_cfg["root_cause"],
            "functional_delta_from_r2": self.raw_cfg["allowed_semantic_delta"],
            "forbidden_changes": self.raw_cfg["forbidden_changes"],
            "preserved": [
                "all r2 mixed ARM64/ARM32, zygote64_32 and graphics-provider semantics",
                "vendor_a, product_a, vendor_dlkm_a and every B-slot byte",
                "LP geometry, kernel, boot, vendor_boot, fstab, DT/DTBO and top-level vbmeta",
                "Mali, mapper, gralloc and every retained hardware-facing service",
                "46 of 50 r2 outer payloads",
            ],
        }
        result = R2.R1.rewrite_paths(result, self.stage, self.final)
        (self.stage / "build-result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        sums = []
        for path in sorted(self.stage.iterdir()):
            if path.is_file() and path.name != "SHA256SUMS":
                sums.append(f"{digest(path)}  {path.name}")
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
