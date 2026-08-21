#!/usr/bin/env python3
"""Build and offline-audit one Android 16 ARM32 exact-board candidate."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET


REPO = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO / "configs/candidates/a16-prototype-a-r1.json"
DEFAULT_SOURCE = Path("/work/ubox10-a16-prototype-a-inputs/incoming/x12-m8b-remote-r1.img")
DEFAULT_VERIFIED = Path("/work/ubox10-a16-prototype-a-inputs/verified/m8b-remote-r1")
DEFAULT_AOSP = Path("/work/src/ubox10-a16-ceiling")
DEFAULT_GATE1 = Path("/work/build-logs/ubox10-a16-gate1/20260821T035000Z")
DEFAULT_KERNEL_CONFIG = Path(
    "/work/build-logs/ubox10-a16-prototype-a/20260821T150330Z/inventory/kernel.config"
)
CHUNK = 8 * 1024 * 1024
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")
VINTF_ERROR_MARKER = "ERROR: files are incompatible:"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(CHUNK), b""):
            value.update(block)
    return value.hexdigest().upper()


def record(path: Path) -> dict[str, object]:
    return {"path": str(path), "size": path.stat().st_size, "sha256": digest(path)}


def rewrite_paths(value: object, stage: Path, final: Path) -> object:
    if isinstance(value, dict):
        return {key: rewrite_paths(item, stage, final) for key, item in value.items()}
    if isinstance(value, list):
        return [rewrite_paths(item, stage, final) for item in value]
    if isinstance(value, str):
        return value.replace(str(stage), str(final))
    return value


def is_expected_inherited_nfs_exception(output: str) -> bool:
    """Accept only the terminal VINTF incompatibility already inherited from Android 12."""
    clean = ANSI_ESCAPE.sub("", output)
    if VINTF_ERROR_MARKER not in clean:
        return False
    error = clean.rsplit(VINTF_ERROR_MARKER, 1)[1]
    expected = "For config CONFIG_NFS_FS, value = y but required n"
    config_errors = re.findall(r"For config (CONFIG_[A-Z0-9_]+)", error)
    return (
        expected in error
        and config_errors == ["CONFIG_NFS_FS"]
        and "vendor.display." not in error
        and error.rstrip().endswith("INCOMPATIBLE")
    )


class CandidateBuilder:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.config = json.loads(args.config.read_text(encoding="utf-8"))
        self.candidate_id = str(self.config["id"])
        self.final = REPO / "out/candidates" / self.candidate_id
        self.stage = self.final.parent / ("." + self.candidate_id + ".staging-" + uuid.uuid4().hex)
        self.log_file = self.stage / "logs/01-commands.log"
        self.aosp_bin = args.aosp / "out-ceiling/host/linux-x86/bin"
        self.gate1_system = args.aosp / str(self.config["gate1_system"]["relative_to_aosp"])
        self.before_source: dict[str, object] | None = None
        self.logical_before: dict[str, dict[str, object]] = {}
        self.logical_after: dict[str, dict[str, object]] = {}

    def log(self, message: str) -> None:
        print(message, flush=True)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with self.log_file.open("a", encoding="utf-8") as stream:
            stream.write(message + "\n")

    def run(
        self,
        command: list[str],
        *,
        output: Path | None = None,
        allowed: set[int] | None = None,
    ) -> int:
        self.log("$ " + subprocess.list2cmdline(command))
        destination = output if output is not None else self.log_file
        mode = "w" if output is not None else "a"
        with destination.open(mode, encoding="utf-8", newline="\n") as stream:
            done = subprocess.run(
                command,
                cwd=REPO,
                stdout=stream,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
        permitted = {0} if allowed is None else allowed
        if done.returncode not in permitted:
            raise RuntimeError(f"failed command ({done.returncode}): {command[0]}")
        return done.returncode

    @staticmethod
    def require_record(path: Path, expected: dict[str, object], label: str) -> dict[str, object]:
        if not path.is_file():
            raise RuntimeError(f"missing {label}: {path}")
        actual = record(path)
        if actual["size"] != expected["size"] or actual["sha256"] != expected["sha256"]:
            raise RuntimeError(f"{label} identity mismatch: {actual}")
        return actual

    def setup(self) -> None:
        if self.final.exists():
            raise RuntimeError(f"refusing to overwrite existing candidate: {self.final}")
        self.stage.mkdir(parents=True)
        source_spec = self.config["accepted_outer"]
        self.before_source = self.require_record(self.args.source, source_spec, "accepted outer image")
        self.require_record(self.gate1_system, self.config["gate1_system"], "Gate 1 system image")

        integration = self.config["integration"]
        for key, hash_key in (
            ("device_matrix_relative", "device_matrix_sha256"),
            ("sepolicy_patch_relative", "sepolicy_patch_sha256"),
        ):
            path = REPO / str(integration[key])
            if digest(path) != integration[hash_key]:
                raise RuntimeError(f"tracked integration input mismatch: {path}")
        key = REPO / str(self.config["avb"]["key_relative"])
        if digest(key) != self.config["avb"]["key_sha256"]:
            raise RuntimeError("AVB key identity mismatch")

        super_spec = self.config["accepted_super"]
        self.require_record(
            self.args.verified / str(super_spec["sparse_relative"]),
            {"size": super_spec["sparse_size"], "sha256": super_spec["sparse_sha256"]},
            "accepted sparse super",
        )
        self.require_record(
            self.args.verified / str(super_spec["raw_relative"]),
            {"size": super_spec["raw_size"], "sha256": super_spec["raw_sha256"]},
            "accepted raw super",
        )
        for name, expected in self.config["logical_partitions"].items():
            value = self.require_record(
                self.args.verified / "logical" / f"{name}.img", expected, f"accepted {name}"
            )
            self.logical_before[name] = value
        for name, expected in self.config["preserved_outer_payloads"].items():
            self.require_record(self.args.verified / "outer" / name, expected, f"accepted {name}")

        self.run(
            [sys.executable, str(REPO / "tools/sunxi_image_tool.py"), "verify", str(self.args.source)],
            output=self.stage / "accepted-outer-verify.log",
        )
        (self.stage / "input-provenance-before.json").write_text(
            json.dumps({"accepted_outer": self.before_source}, indent=2) + "\n", encoding="utf-8"
        )

    def extract_file(self, image: Path, image_path: str, output: Path) -> None:
        self.run(["debugfs", "-R", f"dump -p {image_path} {output}", str(image)])
        if not output.is_file():
            raise RuntimeError(f"debugfs did not extract {image_path}")

    def make_patched_policy(self, source: Path) -> Path:
        destination = self.stage / "plat_sepolicy.prototype-a.cil"
        text = source.read_text(encoding="utf-8")
        rule = str(self.config["integration"]["removed_generated_cil_rule"])
        if text.count(rule) != 1:
            raise RuntimeError("expected exactly one conflicting platform fuseblk rule")
        destination.write_text(text.replace(rule + "\n", ""), encoding="utf-8", newline="\n")
        if rule in destination.read_text(encoding="utf-8"):
            raise RuntimeError("conflicting platform fuseblk rule remains")
        return destination

    def make_merged_matrix(self, source: Path) -> Path:
        destination = self.stage / "compatibility_matrix.device.xml"
        root = ET.parse(source).getroot()
        fragment_path = REPO / str(self.config["integration"]["device_matrix_relative"])
        fragment = ET.parse(fragment_path).getroot()
        additions = list(fragment.findall("hal"))
        if len(additions) != 2:
            raise RuntimeError("expected exactly two device-specific HAL matrix entries")
        for item in additions:
            root.insert(0, item)
        ET.indent(root, space="    ")
        ET.ElementTree(root).write(destination, encoding="unicode", xml_declaration=False)
        with destination.open("a", encoding="utf-8") as stream:
            stream.write("\n")
        return destination

    def replace_mounted_file(self, source: Path, target: Path) -> None:
        stat_before = target.stat()
        before = (stat_before.st_uid, stat_before.st_gid, stat_before.st_mode & 0o7777)
        before_label = os.getxattr(target, "security.selinux")
        self.run(["sudo", "dd", f"if={source}", f"of={target}", "conv=notrunc", "status=none"])
        self.run(["sudo", "truncate", "-s", str(source.stat().st_size), str(target)])
        stat_after = target.stat()
        after = (stat_after.st_uid, stat_after.st_gid, stat_after.st_mode & 0o7777)
        after_label = os.getxattr(target, "security.selinux")
        if before != after or before_label != after_label:
            raise RuntimeError(f"metadata changed while replacing {target}")

    def prepare_system(self) -> Path:
        system = self.stage / "system_a.img"
        shutil.copyfile(self.gate1_system, system)
        avbtool = self.aosp_bin / "avbtool"
        self.run([str(avbtool), "erase_footer", "--image", str(system)])
        self.run(["e2fsck", "-fy", str(system)], allowed={0, 1})

        work_blocks = 375000
        with system.open("r+b") as stream:
            stream.truncate(work_blocks * 4096)
        self.run(["resize2fs", str(system), str(work_blocks)])
        self.run(["e2fsck", "-fy", "-E", "unshare_blocks", str(system)], allowed={0, 1})

        original_policy = self.stage / "plat_sepolicy.original.cil"
        original_matrix = self.stage / "compatibility_matrix.device.original.xml"
        self.extract_file(system, "/system/etc/selinux/plat_sepolicy.cil", original_policy)
        self.extract_file(system, "/system/etc/vintf/compatibility_matrix.device.xml", original_matrix)
        patched_policy = self.make_patched_policy(original_policy)
        merged_matrix = self.make_merged_matrix(original_matrix)

        mount_dir = self.stage / "system-rw-mount"
        mount_dir.mkdir()
        mounted = False
        try:
            self.run(["sudo", "mount", "-o", "loop,rw,noload", str(system), str(mount_dir)])
            mounted = True
            self.replace_mounted_file(
                patched_policy, mount_dir / "system/etc/selinux/plat_sepolicy.cil"
            )
            self.replace_mounted_file(
                merged_matrix, mount_dir / "system/etc/vintf/compatibility_matrix.device.xml"
            )
            self.run(["sync"])
        finally:
            if mounted:
                self.run(["sudo", "umount", str(mount_dir)])
        mount_dir.rmdir()

        self.run(["e2fsck", "-fy", str(system)], allowed={0, 1})
        self.run(["resize2fs", "-M", str(system)])
        fields = subprocess.check_output(["tune2fs", "-l", str(system)], text=True)
        values: dict[str, int] = {}
        for line in fields.splitlines():
            if line.startswith("Block count:"):
                values["blocks"] = int(line.split(":", 1)[1])
            elif line.startswith("Block size:"):
                values["block_size"] = int(line.split(":", 1)[1])
        filesystem_size = values["blocks"] * values["block_size"]
        with system.open("r+b") as stream:
            stream.truncate(filesystem_size)
        self.run(["e2fsck", "-fy", str(system)], allowed={0, 1})

        avb = self.config["avb"]
        self.run(
            [
                str(avbtool),
                "add_hashtree_footer",
                "--image",
                str(system),
                "--partition_name",
                "system",
                "--partition_size",
                str(avb["partition_size"]),
                "--hash_algorithm",
                "sha256",
                "--salt",
                str(avb["salt"]),
                "--do_not_generate_fec",
                "--prop",
                "com.ubox10.candidate.id:" + self.candidate_id,
                "--prop",
                "com.ubox10.avb.fec:none",
                "--key",
                str(REPO / str(avb["key_relative"])),
                "--algorithm",
                str(avb["algorithm"]),
            ]
        )
        if system.stat().st_size != avb["partition_size"]:
            raise RuntimeError("signed candidate system partition size mismatch")
        return system

    def make_vbmeta_system(self, system: Path) -> Path:
        avb = self.config["avb"]
        output = self.stage / "vbmeta_system.fex"
        self.run(
            [
                str(self.aosp_bin / "avbtool"),
                "make_vbmeta_image",
                "--output",
                str(output),
                "--key",
                str(REPO / str(avb["key_relative"])),
                "--algorithm",
                str(avb["algorithm"]),
                "--rollback_index",
                str(avb["rollback_index"]),
                "--rollback_index_location",
                str(avb["rollback_index_location"]),
                "--include_descriptors_from_image",
                str(system),
            ]
        )
        return output

    def make_super(self, system: Path) -> tuple[Path, Path]:
        source_raw = self.args.verified / str(self.config["accepted_super"]["raw_relative"])
        raw = self.stage / "super.raw.img"
        shutil.copyfile(source_raw, raw)
        offset = int(self.config["accepted_super"]["system_a_physical_offset"])
        with raw.open("r+b") as destination, system.open("rb") as source:
            destination.seek(offset)
            shutil.copyfileobj(source, destination, CHUNK)
        sparse = self.stage / "super.fex"
        self.run([str(self.aosp_bin / "img2simg"), str(raw), str(sparse)])
        self.run(
            [str(self.aosp_bin / "lpdump"), "-a", str(raw)],
            output=self.stage / "super-lpdump.txt",
        )
        self.run(
            [str(self.aosp_bin / "lpdump"), "-j", "-s", "0", str(raw)],
            output=self.stage / "super-lpdump.json",
        )
        metadata = json.loads((self.stage / "super-lpdump.json").read_text(encoding="utf-8"))
        system_meta = next(item for item in metadata["partitions"] if item["name"] == "system_a")
        if int(system_meta["size"]) != system.stat().st_size:
            raise RuntimeError("candidate system no longer matches preserved LP allocation")
        return raw, sparse

    def validate_super(self, raw: Path) -> Path:
        logical = self.stage / "validation-logical"
        logical.mkdir()
        self.run([str(self.aosp_bin / "lpunpack"), str(raw), str(logical)])
        for name, expected in self.config["logical_partitions"].items():
            path = logical / f"{name}.img"
            actual = record(path)
            self.logical_after[name] = actual
            if actual["size"] != expected["size"]:
                raise RuntimeError(f"logical size changed: {name}")
            if name != "system_a" and actual["sha256"] != expected["sha256"]:
                raise RuntimeError(f"protected logical partition changed: {name}")
        if self.logical_after["system_a"]["sha256"] != digest(self.stage / "system_a.img"):
            raise RuntimeError("system bytes changed during super integration")
        return logical / "system_a.img"

    def inventory_image(self, image: Path, label: str) -> Path:
        mount_dir = self.stage / f"{label}-inventory-mount"
        output = self.stage / f"{label}-filesystem-manifest.json"
        mount_dir.mkdir()
        mounted = False
        try:
            self.run(["sudo", "mount", "-o", "loop,ro,noload", str(image), str(mount_dir)])
            mounted = True
            self.run(
                ["sudo", sys.executable, str(REPO / "scripts/inventory-ext4-tree.py"), str(mount_dir), "--output", str(output)]
            )
        finally:
            if mounted:
                rc = self.run(["sudo", "umount", str(mount_dir)], allowed={0, 32})
                if rc:
                    time.sleep(0.5)
                    self.run(["sudo", "umount", str(mount_dir)])
        mount_dir.rmdir()
        return output

    @staticmethod
    def manifest_map(path: Path) -> dict[str, dict[str, object]]:
        return {
            item["path"]: item
            for item in json.loads(path.read_text(encoding="utf-8"))["entries"]
        }

    def validate_system_diff(self, candidate: Path) -> None:
        before = self.manifest_map(self.inventory_image(self.gate1_system, "gate1-system"))
        after = self.manifest_map(self.inventory_image(candidate, "candidate-system"))
        changed = [path for path in sorted(set(before) | set(after)) if before.get(path) != after.get(path)]
        expected = [
            "/system/etc/selinux/plat_sepolicy.cil",
            "/system/etc/vintf/compatibility_matrix.device.xml",
        ]
        if changed != expected:
            raise RuntimeError("unexpected candidate filesystem differences: " + ", ".join(changed[:32]))
        details = {path: {"before": before[path], "after": after[path]} for path in changed}
        (self.stage / "system-filesystem-diff.json").write_text(
            json.dumps({"changed_paths": changed, "details": details}, indent=2) + "\n",
            encoding="utf-8",
        )

    def verify_avb(self, system: Path, vbmeta_system: Path) -> None:
        view = self.stage / "avb-view"
        view.mkdir()
        os.link(system, view / "system.img")
        shutil.copyfile(vbmeta_system, view / "vbmeta_system.img")
        key = REPO / str(self.config["avb"]["key_relative"])
        self.run(
            [str(self.aosp_bin / "avbtool"), "verify_image", "--image", str(view / "vbmeta_system.img"), "--key", str(key)],
            output=self.stage / "avb-chain-verify.log",
        )
        self.run(
            [str(self.aosp_bin / "avbtool"), "verify_image", "--image", str(view / "system.img")],
            output=self.stage / "avb-system-verify.log",
        )
        self.run(
            [str(self.aosp_bin / "avbtool"), "info_image", "--image", str(system)],
            output=self.stage / "system-avb-info.txt",
        )
        self.run(
            [str(self.aosp_bin / "avbtool"), "info_image", "--image", str(vbmeta_system)],
            output=self.stage / "vbmeta-system-avb-info.txt",
        )

    def exact_compatibility_audit(self, system: Path) -> dict[str, object]:
        audit = self.stage / "exact-audit"
        mounts = audit / "mounts"
        root = audit / "root"
        for path in (mounts / "system", mounts / "vendor", mounts / "product", mounts / "vendor_dlkm", root / "odm", root / "apex"):
            path.mkdir(parents=True, exist_ok=True)
        images = {
            "system": system,
            "vendor": self.args.verified / "logical/vendor_a.img",
            "product": self.args.verified / "logical/product_a.img",
            "vendor_dlkm": self.args.verified / "logical/vendor_dlkm_a.img",
        }
        mounted: list[Path] = []
        try:
            for name, image in images.items():
                self.run(["e2fsck", "-fn", str(image)], output=audit / f"e2fsck-{name}.log")
                point = mounts / name
                self.run(["sudo", "mount", "-o", "loop,ro,noload", str(image), str(point)])
                mounted.append(point)
            os.symlink(mounts / "system/system", root / "system")
            os.symlink(mounts / "system/system/system_ext", root / "system_ext")
            os.symlink(mounts / "vendor", root / "vendor")
            os.symlink(mounts / "product", root / "product")
            os.symlink(mounts / "vendor_dlkm", root / "vendor_dlkm")
            shutil.copyfile(
                self.args.gate1 / "offline-closure/linker-root/apex/apex-info-list.xml",
                root / "apex/apex-info-list.xml",
            )
            os.symlink(
                self.args.gate1 / "offline-closure/linker-root/apex/com.android.vndk.v31",
                root / "apex/com.android.vndk.v31",
            )

            checkvintf = self.aosp_bin / "checkvintf"
            system_rc = self.run(
                [str(checkvintf), "--check-one", "--dirmap", f"/system:{root / 'system'}"],
                output=audit / "vintf-system.log",
            )
            full_command = [
                str(checkvintf),
                "--check-compat",
                "--dirmap", f"/system:{root / 'system'}",
                "--dirmap", f"/system_ext:{root / 'system_ext'}",
                "--dirmap", f"/vendor:{root / 'vendor'}",
                "--dirmap", f"/product:{root / 'product'}",
                "--dirmap", f"/odm:{root / 'odm'}",
                "--dirmap", f"/apex:{root / 'apex'}",
                "--property", "ro.product.first_api_level=31",
                "--kernel", f"5.4.125:{self.args.kernel_config}",
            ]
            full_rc = self.run(full_command, output=audit / "vintf-full.log", allowed={65})
            full_text = (audit / "vintf-full.log").read_text(encoding="utf-8", errors="replace")
            if not is_expected_inherited_nfs_exception(full_text):
                raise RuntimeError("candidate VINTF result is not the single expected inherited NFS exception")

            linker_target = audit / "linker-generated"
            linker_target.mkdir()
            self.run(
                [str(self.aosp_bin / "linkerconfig"), "--target", str(linker_target), "--root", str(root), "--vndk", "31", "--product_vndk", ""],
                output=audit / "linkerconfig.log",
            )
            linker_text = (linker_target / "ld.config.txt").read_text(encoding="utf-8")
            if "libaudioroute.so" not in linker_text or "[vendor]" not in linker_text:
                raise RuntimeError("exact candidate linker namespace closure is incomplete")

            system_root = mounts / "system/system"
            system_ext = mounts / "system/system/system_ext"
            self.run(
                [
                    str(self.aosp_bin / "secilc"),
                    str(system_root / "etc/selinux/plat_sepolicy.cil"),
                    str(system_root / "etc/selinux/mapping/31.0.cil"),
                    str(system_root / "etc/selinux/mapping/31.0.compat.cil"),
                    str(system_ext / "etc/selinux/system_ext_sepolicy.cil"),
                    str(system_ext / "etc/selinux/mapping/31.0.cil"),
                    str(system_ext / "etc/selinux/mapping/31.0.compat.cil"),
                    str(mounts / "vendor/etc/selinux/plat_pub_versioned.cil"),
                    str(mounts / "vendor/etc/selinux/vendor_sepolicy.cil"),
                    "-m", "-M", "true", "-G", "-N", "-c", "30",
                    "-o", str(audit / "combined-sepolicy.bin"), "-f", "/dev/null",
                ],
                output=audit / "selinux-compile.log",
            )
        finally:
            for point in reversed(mounted):
                self.run(["sudo", "umount", str(point)])

        elf_csv = self.stage / "elf-inventory.csv"
        elf_summary = self.stage / "elf-summary.md"
        self.run(
            [
                sys.executable,
                str(REPO / "scripts/inventory-elf.py"),
                "--partition", f"system={system}",
                "--partition", f"vendor={images['vendor']}",
                "--partition", f"product={images['product']}",
                "--partition", f"vendor_dlkm={images['vendor_dlkm']}",
                "--csv", str(elf_csv),
                "--summary", str(elf_summary),
                "--label", "a16-prototype-a-r1 exact-board candidate",
            ],
            output=audit / "elf-inventory.log",
        )
        elf_text = elf_summary.read_text(encoding="utf-8")
        if "ELF32 未解析名称：0" not in elf_text or "ELF64 未解析名称：0" not in elf_text:
            raise RuntimeError("candidate ELF name-level dependency audit failed")
        shutil.rmtree(mounts)
        shutil.rmtree(root)
        return {
            "system_vintf": "PASS",
            "full_vintf": "EXPECTED_INHERITED_EXCEPTION",
            "full_vintf_exit": full_rc,
            "full_vintf_exception": self.config["known_vintf_exception"],
            "linkerconfig": "PASS",
            "selinux_split_compile": "PASS",
            "e2fsck": "PASS",
            "elf_name_level": "PASS",
            "system_vintf_exit": system_rc,
        }

    def pack_outer(self, super_image: Path, vbmeta_system: Path) -> tuple[Path, dict[str, object]]:
        firmware = self.stage / f"x12-{self.candidate_id}.img"
        audit_path = self.stage / "outer-payload-audit.json"
        self.run(
            [
                sys.executable,
                str(REPO / "tools/pack_image_preserving.py"),
                "--source", str(self.args.source),
                "--output", str(firmware),
                "--replace", f"super.fex={super_image}",
                "--replace", f"vbmeta_system.fex={vbmeta_system}",
                "--audit", str(audit_path),
            ]
        )
        self.run(
            [sys.executable, str(REPO / "tools/sunxi_image_tool.py"), "verify", str(firmware)],
            output=self.stage / "candidate-outer-verify.log",
        )
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        actions = {item["filename"]: item["action"] for item in audit["payloads"]}
        container = self.config["container"]
        if len(actions) != container["total_entries"]:
            raise RuntimeError("outer entry count changed")
        if sum(value == "preserved" for value in actions.values()) != container["preserved_entries"]:
            raise RuntimeError("outer preservation count changed")
        for name in container["replacements"]:
            if actions.get(name) != "replacement":
                raise RuntimeError(f"missing outer replacement: {name}")
        for name in container["companions"]:
            if actions.get(name) != "companion":
                raise RuntimeError(f"missing regenerated companion: {name}")
        return firmware, audit

    def finish(
        self,
        firmware: Path,
        super_image: Path,
        vbmeta_system: Path,
        compatibility: dict[str, object],
    ) -> None:
        after_source = record(self.args.source)
        if after_source != self.before_source:
            raise RuntimeError("accepted source image changed during candidate build")
        (self.stage / "input-provenance-after.json").write_text(
            json.dumps({"accepted_outer": after_source}, indent=2) + "\n", encoding="utf-8"
        )
        published_logical_after: dict[str, dict[str, object]] = {}
        for name, item in self.logical_after.items():
            published = dict(item)
            published["path"] = str(
                self.stage / "system_a.img"
                if name == "system_a"
                else self.args.verified / "logical" / f"{name}.img"
            )
            published_logical_after[name] = published
        result = {
            "id": self.candidate_id,
            "status": "OFFLINE_CHECKED_CANDIDATE",
            "gate2": "CLOSED",
            "eligible_for_one_uart_first_authorization": True,
            "firmware": record(firmware),
            "system_a": record(self.stage / "system_a.img"),
            "super": record(super_image),
            "vbmeta_system": record(vbmeta_system),
            "logical_before": self.logical_before,
            "logical_after": published_logical_after,
            "payload_delta": ["system_a", "super.fex", "Vsuper.fex", "vbmeta_system.fex", "Vvbmeta_system.fex"],
            "preserved": ["boot/kernel", "boot.fex", "vendor_boot.fex", "vendor_a", "product_a", "vendor_dlkm_a", "vbmeta.fex", "all other outer payloads"],
            "integration_changes": [
                "/system/etc/selinux/plat_sepolicy.cil: remove one conflicting platform fuseblk genfscon",
                "/system/etc/vintf/compatibility_matrix.device.xml: declare two accepted device-specific display HALs",
            ],
            "compatibility": compatibility,
            "avb": "PASS: project test key, system hashtree, vbmeta_system rollback index/location preserved",
            "lp": "PASS: exact 3-slot metadata and all non-system logical bytes preserved",
            "outer": "PASS: 46/50 payloads preserved; two replacements and two regenerated companions",
            "physical_device_actions_performed": False,
            "flash_authorized": False,
            "remaining_limit": "Offline evidence cannot prove boot, runtime HAL behavior, graphics, media, audio, wireless, DRM, or enforced SELinux.",
        }
        result_path = self.stage / "build-result.json"
        result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

        shutil.rmtree(self.stage / "validation-logical")
        shutil.rmtree(self.stage / "avb-view")
        (self.stage / "super.raw.img").unlink()
        for name in ("build-result.json", "outer-payload-audit.json", "input-provenance-before.json", "input-provenance-after.json"):
            path = self.stage / name
            document = rewrite_paths(json.loads(path.read_text(encoding="utf-8")), self.stage, self.final)
            path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        sums = []
        for path in sorted(self.stage.iterdir()):
            if path.is_file() and path.name != "SHA256SUMS":
                sums.append(f"{digest(path)}  {path.name}")
        (self.stage / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
        os.replace(self.stage, self.final)

    def build(self) -> None:
        started = time.time()
        try:
            self.setup()
            system = self.prepare_system()
            vbmeta_system = self.make_vbmeta_system(system)
            raw_super, super_image = self.make_super(system)
            validated_system = self.validate_super(raw_super)
            self.validate_system_diff(validated_system)
            self.verify_avb(validated_system, vbmeta_system)
            compatibility = self.exact_compatibility_audit(validated_system)
            firmware, _outer_audit = self.pack_outer(super_image, vbmeta_system)
            self.finish(firmware, super_image, vbmeta_system, compatibility)
            print(f"SUCCESS: {self.final} in {time.time() - started:.1f}s", flush=True)
        except Exception:
            if self.stage.exists() and not self.args.keep_failed:
                shutil.rmtree(self.stage)
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--verified", type=Path, default=DEFAULT_VERIFIED)
    parser.add_argument("--aosp", type=Path, default=DEFAULT_AOSP)
    parser.add_argument("--gate1", type=Path, default=DEFAULT_GATE1)
    parser.add_argument("--kernel-config", type=Path, default=DEFAULT_KERNEL_CONFIG)
    parser.add_argument("--keep-failed", action="store_true")
    args = parser.parse_args()
    CandidateBuilder(args).build()


if __name__ == "__main__":
    main()
