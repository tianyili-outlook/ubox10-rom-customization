#!/usr/bin/env python3
"""Build and offline-audit one Android 12 H616 Linux 5.4.302 candidate."""
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


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from tools.pack_image_preserving import parse_image  # noqa: E402


DEFAULT_CONFIG = REPO / "configs/candidates/m8-kernel-5.4.302-r1.json"
DEFAULT_AOSP = Path("/work/src/ubox10-a16-ceiling")
DEFAULT_INTEGRATION = Path("/work/src/ubox10-kernel-5.4.302-common")
CHUNK = 8 * 1024 * 1024


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(CHUNK), b""):
            value.update(block)
    return value.hexdigest().upper()


def digest_range(path: Path, offset: int, length: int) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        stream.seek(offset)
        remaining = length
        while remaining:
            block = stream.read(min(CHUNK, remaining))
            if not block:
                raise RuntimeError(f"short range read: {path} at {offset}+{length}")
            value.update(block)
            remaining -= len(block)
    return value.hexdigest().upper()


def record(path: Path) -> dict[str, object]:
    return {"path": str(path), "size": path.stat().st_size, "sha256": digest(path)}


def rewrite_paths(value: object, old: Path, new: Path) -> object:
    if isinstance(value, dict):
        return {key: rewrite_paths(item, old, new) for key, item in value.items()}
    if isinstance(value, list):
        return [rewrite_paths(item, old, new) for item in value]
    if isinstance(value, str):
        return value.replace(str(old), str(new))
    return value


def outer_payloads(path: Path) -> dict[str, dict[str, object]]:
    _prefix, entries = parse_image(path)
    result = {}
    with path.open("rb") as stream:
        for entry in entries:
            length = int(entry["stored_len"])
            stream.seek(int(entry["offset"]))
            value = hashlib.sha256()
            remaining = length
            while remaining:
                block = stream.read(min(CHUNK, remaining))
                if not block:
                    raise RuntimeError(f"truncated outer payload: {entry['filename']}")
                value.update(block)
                remaining -= len(block)
            result[str(entry["filename"])] = {
                "orig_len": int(entry["orig_len"]),
                "stored_len": length,
                "sha256_stored": value.hexdigest().upper(),
            }
    return result


class Builder:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.cfg = json.loads(args.config.read_text(encoding="utf-8"))
        self.candidate_id = str(self.cfg["id"])
        self.final = REPO / "out/candidates" / self.candidate_id
        self.stage = self.final.parent / f".{self.candidate_id}.staging-{uuid.uuid4().hex}"
        self.log = self.stage / "logs/01-commands.log"
        self.verified = Path(str(self.cfg["verified_root"]))
        self.evidence = Path(str(self.cfg["kernel_build"]["evidence_dir"]))
        self.build_root = Path(str(self.cfg["kernel_build"]["build_root"]))
        self.aosp_bin = args.aosp / "out-ceiling/host/linux-x86/bin"
        self.base = Path(str(self.cfg["base_candidate"]["path"]))
        self.rollback = Path(str(self.cfg["rollback"]["path"]))
        self.base_before: dict[str, object] | None = None
        self.rollback_before: dict[str, object] | None = None
        self.module_paths: dict[str, Path] = {}

    def run(
        self,
        command: list[str],
        *,
        output: Path | None = None,
        allowed: set[int] | None = None,
        cwd: Path = REPO,
    ) -> int:
        line = "$ " + subprocess.list2cmdline(command)
        print(line, flush=True)
        self.log.parent.mkdir(parents=True, exist_ok=True)
        with self.log.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")
        destination = output or self.log
        mode = "w" if output else "a"
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open(mode, encoding="utf-8", newline="\n") as stream:
            environment = os.environ.copy()
            environment["PATH"] = f"{self.aosp_bin}:{environment['PATH']}"
            done = subprocess.run(
                command,
                cwd=cwd,
                env=environment,
                stdout=stream,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
        expected = {0} if allowed is None else allowed
        if done.returncode not in expected:
            raise RuntimeError(f"failed command ({done.returncode}): {command}")
        return done.returncode

    @staticmethod
    def require(path: Path, expected: dict[str, object], label: str) -> dict[str, object]:
        if not path.is_file():
            raise RuntimeError(f"missing {label}: {path}")
        actual = record(path)
        if actual["size"] != expected["size"] or actual["sha256"] != expected["sha256"]:
            raise RuntimeError(f"{label} identity mismatch: {actual}")
        return actual

    def verified_path(self, spec: dict[str, object]) -> Path:
        return self.verified / str(spec["relative"])

    def evidence_path(self, spec: dict[str, object]) -> Path:
        return self.evidence / str(spec["relative"])

    def setup(self) -> None:
        if self.final.exists():
            raise RuntimeError(f"refusing to overwrite candidate: {self.final}")
        self.stage.mkdir(parents=True)
        self.base_before = self.require(self.base, self.cfg["base_candidate"], "accepted outer")
        self.rollback_before = self.require(self.rollback, self.cfg["rollback"], "rollback image")

        accepted = self.cfg["accepted"]
        for label in ("boot", "super_sparse", "super_raw"):
            self.require(self.verified_path(accepted[label]), accepted[label], f"accepted {label}")
        for label, spec in accepted["logical"].items():
            self.require(self.verified_path(spec), spec, f"accepted logical {label}")
        for label, spec in accepted["protected_outer"].items():
            self.require(self.verified_path(spec), spec, f"accepted outer {label}")

        build = self.cfg["kernel_build"]
        for label in ("image", "preservation_config", "path_a_config", "offline_audit"):
            self.require(self.evidence_path(build[label]), build[label], f"kernel {label}")
        audit = json.loads(self.evidence_path(build["offline_audit"]).read_text(encoding="utf-8"))
        if audit.get("result") != "PASS_WITH_PHYSICAL_VALIDATION_REQUIRED":
            raise RuntimeError("kernel offline audit is not accepted")
        if audit["source"]["integration_commit"].upper() != self.cfg["integration"]["commit"]:
            raise RuntimeError("kernel audit/integration identity mismatch")
        if audit["modules"]["storage"]["remaining_4k_blocks_after_replacement"] != 1:
            raise RuntimeError("kernel audit no longer proves fixed vendor_dlkm fit")

        head = subprocess.check_output(
            ["git", "-C", str(self.args.integration_repo), "rev-parse", "HEAD"], text=True
        ).strip().upper()
        tree = subprocess.check_output(
            ["git", "-C", str(self.args.integration_repo), "rev-parse", "HEAD^{tree}"], text=True
        ).strip().upper()
        dirty = subprocess.check_output(
            ["git", "-C", str(self.args.integration_repo), "status", "--porcelain"], text=True
        ).strip()
        if head != self.cfg["integration"]["commit"] or tree != self.cfg["integration"]["tree"] or dirty:
            raise RuntimeError("integration source identity/cleanliness mismatch")

        release_root = self.build_root / "modules-install/lib/modules" / build["module_release"]
        candidates: dict[str, list[Path]] = {}
        for path in release_root.rglob("*.ko"):
            candidates.setdefault(path.name, []).append(path)
        if set(candidates) != {item["file"] for item in build["modules"]}:
            raise RuntimeError("installed module inventory changed")
        for item in build["modules"]:
            paths = candidates[item["file"]]
            if len(paths) != 1:
                raise RuntimeError(f"ambiguous module path: {item['file']} -> {paths}")
            path = paths[0]
            self.require(path, item, f"rebuilt module {item['file']}")
            name = subprocess.check_output(["modinfo", "-F", "name", str(path)], text=True).strip()
            depends = subprocess.check_output(["modinfo", "-F", "depends", str(path)], text=True).strip()
            vermagic = subprocess.check_output(["modinfo", "-F", "vermagic", str(path)], text=True).strip()
            if name != item["name"] or [value for value in depends.split(",") if value] != item["depends"]:
                raise RuntimeError(f"module metadata mismatch: {item['file']}")
            if vermagic != "5.4.302+ SMP preempt mod_unload modversions aarch64":
                raise RuntimeError(f"module vermagic mismatch: {item['file']}: {vermagic}")
            self.module_paths[item["file"]] = path

        required_tools = (
            "avbtool", "fec", "img2simg", "lpdump", "lpunpack", "simg2img",
        )
        for tool in required_tools:
            if not (self.aosp_bin / tool).is_file():
                raise RuntimeError(f"missing AOSP host tool: {tool}")
        self.run(
            [sys.executable, str(REPO / "tools/sunxi_image_tool.py"), "verify", str(self.base)],
            output=self.stage / "base-outer-verify.log",
        )

    def build_boot(self) -> tuple[Path, Path, dict[str, object]]:
        spec = self.cfg["accepted"]["boot"]
        accepted_boot = self.verified_path(spec)
        unpacked = self.stage / "accepted-boot-unpacked"
        self.run(
            [
                sys.executable,
                str(self.args.aosp / "system/tools/mkbootimg/unpack_bootimg.py"),
                "--boot_img", str(accepted_boot),
                "--out", str(unpacked),
                "--format=mkbootimg",
            ],
            output=self.stage / "accepted-boot-mkbootimg-args.txt",
        )
        self.require(
            unpacked / "kernel",
            {"size": spec["kernel_size"], "sha256": spec["kernel_sha256"]},
            "accepted boot kernel",
        )
        self.require(
            unpacked / "ramdisk",
            {"size": spec["ramdisk_size"], "sha256": spec["ramdisk_sha256"]},
            "accepted boot ramdisk",
        )
        accepted_args = (self.stage / "accepted-boot-mkbootimg-args.txt").read_text().strip()
        for fragment in (
            "--header_version 3", "--os_version 12.0.0", "--os_patch_level 2022-02",
            "--cmdline 'console=ttyS0,115200n8 ignore_loglevel'",
        ):
            if fragment not in accepted_args:
                raise RuntimeError(f"accepted boot header contract changed: {fragment}")

        image = self.evidence_path(self.cfg["kernel_build"]["image"])
        unsigned = self.stage / "boot-unsigned.img"
        self.run(
            [
                sys.executable, str(self.args.aosp / "system/tools/mkbootimg/mkbootimg.py"),
                "--header_version", str(spec["header_version"]),
                "--os_version", str(spec["os_version"]),
                "--os_patch_level", str(spec["os_patch_level"]),
                "--kernel", str(image),
                "--ramdisk", str(unpacked / "ramdisk"),
                "--cmdline", str(spec["cmdline"]),
                "--output", str(unsigned),
            ]
        )
        self.run(
            [
                str(self.aosp_bin / "avbtool"), "add_hash_footer",
                "--image", str(unsigned),
                "--partition_name", str(spec["avb_partition_name"]),
                "--partition_size", str(spec["avb_partition_size"]),
                "--hash_algorithm", "sha256",
                "--salt", str(spec["avb_salt"]),
                "--prop", "com.android.build.boot.fingerprint:" + str(spec["fingerprint"]),
                "--prop", "com.android.build.boot.os_version:" + str(spec["os_version_prop"]),
            ]
        )
        boot = self.stage / "boot.fex"
        unsigned.replace(boot)
        if boot.stat().st_size != spec["avb_partition_size"]:
            raise RuntimeError("candidate boot partition size changed")
        self.run(
            [str(self.aosp_bin / "avbtool"), "verify_image", "--image", str(boot)],
            output=self.stage / "boot-avb-verify.log",
        )
        self.run(
            [str(self.aosp_bin / "avbtool"), "info_image", "--image", str(boot)],
            output=self.stage / "boot-avb-info.txt",
        )
        avb_info = (self.stage / "boot-avb-info.txt").read_text()
        for fragment in (
            "Algorithm:                NONE",
            "Partition Name:        boot",
            f"Salt:                  {spec['avb_salt']}",
            str(spec["fingerprint"]),
        ):
            if fragment not in avb_info:
                raise RuntimeError(f"candidate boot AVB contract changed: {fragment}")

        candidate_unpacked = self.stage / "candidate-boot-unpacked"
        self.run(
            [
                sys.executable,
                str(self.args.aosp / "system/tools/mkbootimg/unpack_bootimg.py"),
                "--boot_img", str(boot),
                "--out", str(candidate_unpacked),
                "--format=mkbootimg",
            ],
            output=self.stage / "candidate-boot-mkbootimg-args.txt",
        )
        if digest(candidate_unpacked / "kernel") != digest(image):
            raise RuntimeError("candidate boot kernel replacement mismatch")
        if digest(candidate_unpacked / "ramdisk") != spec["ramdisk_sha256"]:
            raise RuntimeError("candidate boot ramdisk changed")
        candidate_args = (self.stage / "candidate-boot-mkbootimg-args.txt").read_text().strip()
        for fragment in (
            "--header_version 3", "--os_version 12.0.0", "--os_patch_level 2022-02",
            "--cmdline 'console=ttyS0,115200n8 ignore_loglevel'",
        ):
            if fragment not in candidate_args:
                raise RuntimeError(f"candidate boot header contract changed: {fragment}")
        audit = {
            "accepted": record(accepted_boot),
            "candidate": record(boot),
            "kernel_before": record(unpacked / "kernel"),
            "kernel_after": record(candidate_unpacked / "kernel"),
            "ramdisk_before": record(unpacked / "ramdisk"),
            "ramdisk_after": record(candidate_unpacked / "ramdisk"),
            "header_cmdline_preserved": True,
            "avb_hash_footer_verified": True,
        }
        return boot, image, audit

    def build_vendor_dlkm(self) -> tuple[Path, dict[str, object]]:
        spec = self.cfg["vendor_dlkm"]
        accepted_spec = self.cfg["accepted"]["logical"]["vendor_dlkm_a"]
        accepted = self.verified_path(accepted_spec)
        filesystem = self.stage / "vendor_dlkm-filesystem.img"
        shutil.copyfile(accepted, filesystem)
        with filesystem.open("r+b") as stream:
            stream.truncate(int(spec["filesystem_size"]))

        label_file = self.stage / "vendor-file.selinux"
        self.run(
            [
                "debugfs", "-R",
                f"ea_get -f {label_file} /lib/modules/rtlwifi.ko security.selinux",
                str(accepted),
            ],
            output=self.stage / "accepted-module-label.log",
        )
        expected_label = str(spec["selinux_label"]).replace("\\0", "\0").encode()
        if label_file.read_bytes() != expected_label:
            raise RuntimeError(f"accepted module SELinux label changed: {label_file.read_bytes()!r}")

        batch = self.stage / "vendor-dlkm-debugfs.commands"
        commands = []
        for name in sorted(self.module_paths):
            commands.append(f"rm /lib/modules/{name}")
        for name in sorted(self.module_paths):
            source = self.module_paths[name]
            target = f"/lib/modules/{name}"
            commands.extend(
                [
                    f"write {source} {target}",
                    f"set_inode_field {target} mode {spec['module_mode']}",
                    f"set_inode_field {target} uid {spec['module_uid']}",
                    f"set_inode_field {target} gid {spec['module_gid']}",
                    f"ea_set -f {label_file} {target} security.selinux",
                    f"set_inode_field {target} atime {spec['module_timestamp']}",
                    f"set_inode_field {target} ctime {spec['module_timestamp']}",
                    f"set_inode_field {target} mtime {spec['module_timestamp']}",
                    f"set_inode_field {target} crtime {spec['module_crtime']}",
                ]
            )
        commands.extend(
            [
                f"set_inode_field /lib/modules atime {spec['module_timestamp']}",
                f"set_inode_field /lib/modules ctime {spec['module_timestamp']}",
                f"set_inode_field /lib/modules mtime {spec['module_timestamp']}",
                f"set_inode_field /lib/modules crtime {spec['module_crtime']}",
                f"set_super_value wtime {spec['module_crtime']}",
                f"set_super_value lastcheck {spec['module_crtime']}",
                f"set_super_value mkfs_time {spec['module_crtime']}",
            ]
        )
        batch.write_text("\n".join(commands) + "\n", encoding="utf-8")
        self.run(
            ["debugfs", "-w", "-f", str(batch), str(filesystem)],
            output=self.stage / "vendor-dlkm-debugfs.log",
        )
        if "Command not found" in (self.stage / "vendor-dlkm-debugfs.log").read_text(errors="replace"):
            raise RuntimeError("debugfs module replacement command failed")

        self.run(
            ["e2fsck", "-fn", str(filesystem)],
            output=self.stage / "vendor-dlkm-e2fsck-before-avb.log",
        )
        self.run(
            ["dumpe2fs", "-h", str(filesystem)],
            output=self.stage / "vendor-dlkm-dumpe2fs.txt",
        )
        geometry = (self.stage / "vendor-dlkm-dumpe2fs.txt").read_text(errors="replace")
        for fragment in (
            f"Block count:              {spec['filesystem_blocks']}",
            f"Block size:               {spec['filesystem_block_size']}",
            f"Free blocks:              {spec['candidate_free_blocks']}",
        ):
            if fragment not in geometry:
                raise RuntimeError(f"candidate vendor_dlkm geometry mismatch: {fragment}")

        candidate_root = self.stage / "candidate-vendor-dlkm-root"
        candidate_root.mkdir()
        self.run(
            ["debugfs", "-R", f"rdump / {candidate_root}", str(filesystem)],
            output=self.stage / "vendor-dlkm-rdump.log",
        )
        extracted_modules = candidate_root / "lib/modules"
        if {path.name for path in extracted_modules.glob("*.ko")} != set(self.module_paths):
            raise RuntimeError("candidate vendor_dlkm module file set changed")
        for name, source in self.module_paths.items():
            if digest(extracted_modules / name) != digest(source):
                raise RuntimeError(f"candidate vendor_dlkm module bytes changed: {name}")

        accepted_static = self.stage / "accepted-vendor-dlkm-static"
        candidate_static = self.stage / "candidate-vendor-dlkm-static"
        accepted_static.mkdir()
        candidate_static.mkdir()
        static_paths = (
            "/lib/modules/modules.alias", "/lib/modules/modules.dep",
            "/lib/modules/modules.load", "/lib/modules/modules.softdep",
            "/etc/build.prop", "/etc/fs_config_dirs", "/etc/fs_config_files", "/etc/NOTICE.xml.gz",
        )
        for image, root in ((accepted, accepted_static), (filesystem, candidate_static)):
            for internal in static_paths:
                target = root / internal.lstrip("/").replace("/", "__")
                self.run(
                    ["debugfs", "-R", f"dump -p {internal} {target}", str(image)],
                    output=self.stage / f"debugfs-static-{root.name}-{target.name}.log",
                )
        static_audit = {}
        for internal in static_paths:
            name = internal.lstrip("/").replace("/", "__")
            before = accepted_static / name
            after = candidate_static / name
            if before.read_bytes() != after.read_bytes():
                raise RuntimeError(f"non-module vendor_dlkm file changed: {internal}")
            static_audit[internal] = record(after)

        stat_log = self.stage / "candidate-module-metadata.txt"
        allocated_blocks = 0
        for name in sorted(self.module_paths):
            stat_output = subprocess.check_output(
                ["debugfs", "-R", f"stat /lib/modules/{name}", str(filesystem)],
                text=True, stderr=subprocess.STDOUT,
            )
            with stat_log.open("a", encoding="utf-8") as stream:
                stream.write(f"== {name} ==\n{stat_output}")
            if "Mode:  0644" not in stat_output or not re.search(r"User:\s+0\s+Group:\s+0", stat_output):
                raise RuntimeError(f"candidate module inode metadata changed: {name}")
            match = re.search(r"Blockcount:\s+(\d+)", stat_output)
            if not match:
                raise RuntimeError(f"missing candidate module block count: {name}")
            allocated_blocks += int(match.group(1)) // 8
            value_file = self.stage / "module-labels" / name
            value_file.parent.mkdir(exist_ok=True)
            self.run(
                [
                    "debugfs", "-R",
                    f"ea_get -f {value_file} /lib/modules/{name} security.selinux",
                    str(filesystem),
                ],
                output=self.stage / "logs" / f"ea-{name}.log",
            )
            if value_file.read_bytes() != expected_label:
                raise RuntimeError(f"candidate module SELinux label changed: {name}")
        if allocated_blocks != spec["candidate_module_inode_blocks"]:
            raise RuntimeError(f"candidate module allocation changed: {allocated_blocks}")

        # avbtool resolves hashtree payloads from the descriptor partition
        # name, so verification must see the image as vendor_dlkm.img. Rename
        # it back to the slot-qualified logical-partition name afterwards.
        avb_image = self.stage / "vendor_dlkm.img"
        filesystem.replace(avb_image)
        self.run(
            [
                str(self.aosp_bin / "avbtool"), "add_hashtree_footer",
                "--image", str(avb_image),
                "--partition_size", str(spec["partition_size"]),
                "--partition_name", str(spec["avb_partition_name"]),
                "--hash_algorithm", "sha256",
                "--salt", str(spec["avb_salt"]),
                "--fec_num_roots", str(spec["fec_num_roots"]),
                "--prop", "com.android.build.vendor_dlkm.fingerprint:" + str(spec["fingerprint"]),
                "--prop", "com.android.build.vendor_dlkm.os_version:" + str(spec["os_version_prop"]),
            ]
        )
        if avb_image.stat().st_size != spec["partition_size"]:
            raise RuntimeError("candidate vendor_dlkm partition size changed")
        self.run(
            [str(self.aosp_bin / "avbtool"), "verify_image", "--image", str(avb_image)],
            output=self.stage / "vendor-dlkm-avb-verify.log",
        )
        self.run(
            [str(self.aosp_bin / "avbtool"), "info_image", "--image", str(avb_image)],
            output=self.stage / "vendor-dlkm-avb-info.txt",
        )
        avb_info = (self.stage / "vendor-dlkm-avb-info.txt").read_text()
        for fragment in (
            "Original image size:      6492160 bytes",
            "Algorithm:                NONE",
            "Partition Name:        vendor_dlkm",
            f"Salt:                  {spec['avb_salt']}",
            "FEC num roots:         2",
            str(spec["fingerprint"]),
        ):
            if fragment not in avb_info:
                raise RuntimeError(f"candidate vendor_dlkm AVB contract changed: {fragment}")
        self.run(
            ["e2fsck", "-fn", str(avb_image)],
            output=self.stage / "vendor-dlkm-e2fsck-final.log",
        )
        vendor_dlkm = self.stage / "vendor_dlkm_a.img"
        avb_image.replace(vendor_dlkm)
        audit = {
            "accepted": record(accepted),
            "candidate": record(vendor_dlkm),
            "filesystem_size_preserved": True,
            "filesystem_blocks": spec["filesystem_blocks"],
            "free_blocks_after_replacement": spec["candidate_free_blocks"],
            "modules": [record(extracted_modules / name) for name in sorted(self.module_paths)],
            "module_inventory_exact": True,
            "module_allocated_4k_blocks": allocated_blocks,
            "host_staging_allocated_4k_blocks": spec["host_module_allocated_blocks"],
            "sparse_module_note": "debugfs stores one all-zero gspca_main block as a hole; one filesystem block remains free.",
            "module_inode_mode_uid_gid_exact": True,
            "module_selinux_label_exact": True,
            "module_metadata_files_exact": True,
            "static_files": static_audit,
            "e2fsck": "PASS",
            "avb_hashtree_fec": "PASS",
        }
        return vendor_dlkm, audit

    def build_super(self, vendor_dlkm: Path) -> tuple[Path, dict[str, object]]:
        raw_spec = self.cfg["accepted"]["super_raw"]
        source = self.verified_path(raw_spec)
        candidate_raw = self.stage / "super.raw.img"
        self.run(["cp", "--reflink=auto", str(source), str(candidate_raw)])
        if record(candidate_raw) != {"path": str(candidate_raw), "size": raw_spec["size"], "sha256": raw_spec["sha256"]}:
            raise RuntimeError("copied accepted raw super changed")

        geometry = self.cfg["super"]
        offset = int(geometry["vendor_dlkm_first_sector"]) * int(geometry["sector_size"])
        length = int(geometry["vendor_dlkm_sector_count"]) * int(geometry["sector_size"])
        if length != vendor_dlkm.stat().st_size:
            raise RuntimeError("vendor_dlkm extent length mismatch")
        prefix_before = digest_range(source, 0, offset)
        suffix_offset = offset + length
        suffix_length = source.stat().st_size - suffix_offset
        suffix_before = digest_range(source, suffix_offset, suffix_length)
        with candidate_raw.open("r+b") as destination, vendor_dlkm.open("rb") as payload:
            destination.seek(offset)
            shutil.copyfileobj(payload, destination, CHUNK)
        if digest_range(candidate_raw, offset, length) != digest(vendor_dlkm):
            raise RuntimeError("candidate raw super vendor_dlkm replacement mismatch")
        if digest_range(candidate_raw, 0, offset) != prefix_before:
            raise RuntimeError("candidate raw super prefix changed")
        if digest_range(candidate_raw, suffix_offset, suffix_length) != suffix_before:
            raise RuntimeError("candidate raw super suffix changed")

        accepted_lpdump = self.stage / "accepted-lpdump.json"
        candidate_lpdump = self.stage / "candidate-lpdump.json"
        self.run([str(self.aosp_bin / "lpdump"), "-j", str(source)], output=accepted_lpdump)
        self.run([str(self.aosp_bin / "lpdump"), "-j", str(candidate_raw)], output=candidate_lpdump)
        if json.loads(accepted_lpdump.read_text()) != json.loads(candidate_lpdump.read_text()):
            raise RuntimeError("LP metadata/geometry changed")

        super_sparse = self.stage / "super.fex"
        self.run([str(self.aosp_bin / "img2simg"), str(candidate_raw), str(super_sparse), "4096"])
        roundtrip_raw = self.stage / "super-sparse-roundtrip.raw.img"
        self.run([str(self.aosp_bin / "simg2img"), str(super_sparse), str(roundtrip_raw)])
        if record(roundtrip_raw)["size"] != candidate_raw.stat().st_size or digest(roundtrip_raw) != digest(candidate_raw):
            raise RuntimeError("sparse super does not round-trip to the exact candidate raw image")
        sparse_lpdump = self.stage / "candidate-sparse-lpdump.json"
        self.run([str(self.aosp_bin / "lpdump"), "-j", str(roundtrip_raw)], output=sparse_lpdump)
        if json.loads(accepted_lpdump.read_text()) != json.loads(sparse_lpdump.read_text()):
            raise RuntimeError("sparse LP metadata/geometry changed")

        extracted = self.stage / "candidate-logical"
        extracted.mkdir()
        command = [str(self.aosp_bin / "lpunpack")]
        for name in self.cfg["accepted"]["logical"]:
            command.extend(["-p", name])
        command.extend([str(roundtrip_raw), str(extracted)])
        self.run(command, output=self.stage / "candidate-lpunpack.log")
        logical_audit = {}
        for name, spec in self.cfg["accepted"]["logical"].items():
            path = extracted / f"{name}.img"
            if name == "vendor_dlkm_a":
                expected = record(vendor_dlkm)
                if path.stat().st_size != expected["size"] or digest(path) != expected["sha256"]:
                    raise RuntimeError("candidate super vendor_dlkm logical bytes changed")
            else:
                self.require(path, spec, f"candidate logical {name}")
            logical_audit[name] = record(path)
        audit = {
            "accepted_raw": record(source),
            "candidate_raw": record(candidate_raw),
            "candidate_sparse": record(super_sparse),
            "metadata_geometry_exact": True,
            "sparse_roundtrip_raw_exact": True,
            "extent": {"offset": offset, "length": length},
            "bytes_outside_vendor_dlkm_extent_exact": True,
            "logical": logical_audit,
            "system_vendor_product_byte_preserved": True,
        }
        return super_sparse, audit

    def pack_outer(self, boot: Path, super_sparse: Path) -> tuple[Path, dict[str, object]]:
        before_payloads = outer_payloads(self.base)
        firmware = self.stage / f"x12-{self.candidate_id}.img"
        pack_audit_path = self.stage / "outer-payload-audit.json"
        self.run(
            [
                sys.executable, str(REPO / "tools/pack_image_preserving.py"),
                "--source", str(self.base),
                "--output", str(firmware),
                "--replace", f"boot.fex={boot}",
                "--replace", f"super.fex={super_sparse}",
                "--audit", str(pack_audit_path),
            ]
        )
        self.run(
            [sys.executable, str(REPO / "tools/sunxi_image_tool.py"), "verify", str(firmware)],
            output=self.stage / "candidate-outer-verify.log",
        )
        after_payloads = outer_payloads(firmware)
        if set(before_payloads) != set(after_payloads):
            raise RuntimeError("outer payload inventory changed")
        changed = sorted(
            name for name in before_payloads
            if before_payloads[name]["sha256_stored"] != after_payloads[name]["sha256_stored"]
        )
        expected_changed = sorted([*self.cfg["container"]["replacements"], *self.cfg["container"]["companions"]])
        if changed != expected_changed:
            raise RuntimeError(f"unexpected outer payload delta: {changed}")
        pack_audit = json.loads(pack_audit_path.read_text(encoding="utf-8"))
        actions = {item["filename"]: item["action"] for item in pack_audit["payloads"]}
        if len(actions) != self.cfg["container"]["total_entries"]:
            raise RuntimeError("outer entry count changed")
        if sum(action == "preserved" for action in actions.values()) != self.cfg["container"]["preserved_entries"]:
            raise RuntimeError("outer preservation count changed")
        for name in self.cfg["container"]["replacements"]:
            if actions.get(name) != "replacement":
                raise RuntimeError(f"missing outer replacement: {name}")
        for name in self.cfg["container"]["companions"]:
            if actions.get(name) != "companion":
                raise RuntimeError(f"missing outer companion: {name}")

        extracted = self.stage / "candidate-outer"
        extracted.mkdir()
        for name, source in (("boot.fex", boot), ("super.fex", super_sparse)):
            self.run(
                [
                    sys.executable, str(REPO / "tools/sunxi_image_tool.py"), "extract",
                    "-o", str(extracted), "-f", name, str(firmware),
                ]
            )
            if digest(extracted / name) != digest(source):
                raise RuntimeError(f"packed outer replacement changed: {name}")
        return firmware, {
            "candidate": record(firmware),
            "entry_count": len(actions),
            "changed_payloads": changed,
            "preserved_payload_count": self.cfg["container"]["preserved_entries"],
            "all_preserved_payload_bytes_exact": True,
            "imagewty_verify": "PASS",
        }

    def finish(
        self,
        firmware: Path,
        image: Path,
        boot_audit: dict[str, object],
        vendor_dlkm_audit: dict[str, object],
        super_audit: dict[str, object],
        outer_audit: dict[str, object],
        started: float,
    ) -> None:
        if record(self.base) != self.base_before:
            raise RuntimeError("accepted m8b-remote-r1 input changed during construction")
        if record(self.rollback) != self.rollback_before:
            raise RuntimeError("rollback image changed during construction")
        expected = self.cfg["expected_result"]
        for label, path in (
            ("firmware", firmware),
            ("boot", Path(str(boot_audit["candidate"]["path"]))),
            ("super", Path(str(super_audit["candidate_sparse"]["path"]))),
            ("vendor_dlkm", Path(str(vendor_dlkm_audit["candidate"]["path"]))),
        ):
            actual = record(path)
            if actual["size"] != expected[label]["size"] or actual["sha256"] != expected[label]["sha256"]:
                raise RuntimeError(f"non-reproducible candidate {label}: {actual}")
        result = {
            "schema": 1,
            "id": self.candidate_id,
            "status": "OFFLINE_CHECKED",
            "decision": "GO_FOR_SEPARATELY_AUTHORIZED_ANDROID12_KERNEL_ONLY_PHYSICAL_VALIDATION",
            "gate2": "CLOSED",
            "physical_device_actions_performed": False,
            "flash_authorized": False,
            "firmware": record(firmware),
            "kernel": record(image),
            "kernel_release": "5.4.302+",
            "source_commit": self.cfg["integration"]["commit"],
            "source_tree": self.cfg["integration"]["tree"],
            "elapsed_seconds": round(time.time() - started, 1),
            "boot": boot_audit,
            "vendor_dlkm": vendor_dlkm_audit,
            "super": super_audit,
            "outer": outer_audit,
            "preserved": [
                "accepted Android 12 system_a, vendor_a and product_a bytes",
                "accepted boot header/cmdline/ramdisk and partition size",
                "LP metadata, extents, group limits and three metadata slots",
                "46/50 outer payload bytes including bootloader, TEE, DTBO, vendor_boot and vbmeta",
                "all non-module vendor_dlkm file content and module loading metadata",
                "m8b-remote-r1 input and Test8r2 rollback image",
            ],
            "changed": [
                "boot kernel and boot AVB digest",
                "22 matching vendor_dlkm modules and vendor_dlkm AVB hashtree/FEC",
                "super.fex representation containing the changed vendor_dlkm extent",
                "IMAGEWTY Vboot/Vsuper checksum companions",
            ],
            "offline_limitations": [
                "Compilation/config/symbol checks do not exercise H616 display, Mali, Cedar/media, audio, wireless, Ethernet, USB or IR hardware.",
                "Offline checks do not exercise clocks, regulators, thermal/DVFS, OP-TEE, suspend/resume or wake sources.",
                "A separately authorized UART-first Android 12 kernel-only physical test is required; this result does not authorize flashing.",
            ],
        }
        result = rewrite_paths(result, self.stage, self.final)
        (self.stage / "build-result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
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
            boot, image, boot_audit = self.build_boot()
            vendor_dlkm, vendor_dlkm_audit = self.build_vendor_dlkm()
            super_sparse, super_audit = self.build_super(vendor_dlkm)
            firmware, outer_audit = self.pack_outer(boot, super_sparse)
            self.finish(
                firmware, image, boot_audit, vendor_dlkm_audit,
                super_audit, outer_audit, started,
            )
            print(f"SUCCESS: {self.final} ({time.time() - started:.1f}s)", flush=True)
        except Exception:
            if self.stage.exists() and not self.args.keep_failed:
                shutil.rmtree(self.stage)
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--aosp", type=Path, default=DEFAULT_AOSP)
    parser.add_argument("--integration-repo", type=Path, default=DEFAULT_INTEGRATION)
    parser.add_argument("--keep-failed", action="store_true")
    args = parser.parse_args()
    Builder(args).build()


if __name__ == "__main__":
    main()
