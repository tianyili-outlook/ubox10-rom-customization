#!/usr/bin/env python3
"""Build and offline-audit the one cgroup-compatible Prototype A r2 candidate."""
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
DEFAULT_CONFIG = REPO / "configs/candidates/a16-prototype-a-r2.json"
DEFAULT_AOSP = Path("/work/src/ubox10-a16-ceiling")
DEFAULT_VERIFIED = Path("/work/ubox10-a16-prototype-a-inputs/verified/m8b-remote-r1")
DEFAULT_SOURCE_REPO = Path("/work/tmp-orangepi-kernel-exact")
DEFAULT_CLANG = Path("/work/toolchains/aosp-clang-android12/clang-r416183b1/bin")
DEFAULT_BUILD_ROOT = Path("/work/kernel-builds/a16-prototype-a-r2")
DEFAULT_HOST_SSL = Path("/work/toolchains/ubuntu-libssl-dev/root")
DEFAULT_HOST_TOOLS = Path("/work/toolchains/ubuntu-bc/root")
DEFAULT_GATE1 = Path("/work/build-logs/ubox10-a16-gate1/20260821T035000Z")
CHUNK = 8 * 1024 * 1024
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(CHUNK), b""):
            value.update(block)
    return value.hexdigest().upper()


def record(path: Path) -> dict[str, object]:
    return {"path": str(path), "size": path.stat().st_size, "sha256": digest(path)}


def rewrite_path_values(value: object, old: Path, new: Path) -> object:
    """Rewrite staging paths in the published result after the atomic move."""
    if isinstance(value, dict):
        return {key: rewrite_path_values(item, old, new) for key, item in value.items()}
    if isinstance(value, list):
        return [rewrite_path_values(item, old, new) for item in value]
    if isinstance(value, str):
        return value.replace(str(old), str(new))
    return value


def config_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("CONFIG_") and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
        elif line.startswith("# CONFIG_") and line.endswith(" is not set"):
            values[line[2:-11]] = "n"
    return values


def expected_inherited_nfs_exception(output: str) -> bool:
    clean = ANSI_ESCAPE.sub("", output)
    if "ERROR: files are incompatible:" not in clean:
        return False
    error = clean.rsplit("ERROR: files are incompatible:", 1)[1]
    config_errors = re.findall(r"For config (CONFIG_[A-Z0-9_]+)", error)
    return (
        "For config CONFIG_NFS_FS, value = y but required n" in error
        and config_errors == ["CONFIG_NFS_FS"]
        and error.rstrip().endswith("INCOMPATIBLE")
    )


class Builder:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.config = json.loads(args.config.read_text(encoding="utf-8"))
        self.candidate_id = str(self.config["id"])
        self.final = REPO / "out/candidates" / self.candidate_id
        self.stage = args.resume_stage or self.final.parent / f".{self.candidate_id}.staging-{uuid.uuid4().hex}"
        self.log = self.stage / "logs/01-commands.log"
        self.aosp_bin = args.aosp / "out-ceiling/host/linux-x86/bin"
        self.base = REPO / str(self.config["base_candidate"]["relative"])
        self.base_before: dict[str, object] | None = None

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
        destination = output if output is not None else self.log
        mode = "w" if output is not None else "a"
        with destination.open(mode, encoding="utf-8", newline="\n") as stream:
            done = subprocess.run(
                command,
                cwd=cwd,
                stdout=stream,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
        if done.returncode not in ({0} if allowed is None else allowed):
            raise RuntimeError(f"failed command ({done.returncode}): {command[0]}")
        return done.returncode

    @staticmethod
    def require(path: Path, expected: dict[str, object], label: str) -> dict[str, object]:
        if not path.is_file():
            raise RuntimeError(f"missing {label}: {path}")
        actual = record(path)
        if actual["size"] != expected["size"] or actual["sha256"] != expected["sha256"]:
            raise RuntimeError(f"{label} identity mismatch: {actual}")
        return actual

    def setup(self) -> None:
        if self.final.exists():
            raise RuntimeError(f"refusing to overwrite existing candidate: {self.final}")
        if self.args.build_root.exists():
            raise RuntimeError(f"refusing to reuse kernel build root: {self.args.build_root}")
        self.stage.mkdir(parents=True)
        self.base_before = self.require(self.base, self.config["base_candidate"], "r1 base candidate")
        kernel = self.config["kernel"]
        base_config = Path(str(kernel["base_config_path"]))
        if digest(base_config) != kernel["base_config_sha256"]:
            raise RuntimeError("retained kernel config identity mismatch")
        for relative_key, hash_key in (
            ("repeat_patch_relative", "repeat_patch_sha256"),
            ("keymap_relative", "keymap_sha256"),
        ):
            path = REPO / str(kernel[relative_key])
            if digest(path) != kernel[hash_key]:
                raise RuntimeError(f"tracked kernel input mismatch: {path}")
        if subprocess.check_output(["git", "-C", str(self.args.source_repo), "rev-parse", "HEAD"], text=True).strip() != kernel["source_commit"]:
            raise RuntimeError("kernel source commit mismatch")
        if subprocess.check_output(["git", "-C", str(self.args.source_repo), "remote", "get-url", "origin"], text=True).strip() != kernel["source_url"]:
            raise RuntimeError("kernel source remote mismatch")
        if subprocess.check_output(["git", "-C", str(self.args.clang.parent.parent), "rev-parse", "HEAD"], text=True).strip() != kernel["toolchain_commit"]:
            raise RuntimeError("clang repository commit mismatch")
        if subprocess.check_output(["git", "-C", str(self.args.clang.parent.parent), "remote", "get-url", "origin"], text=True).strip() != kernel["toolchain_url"]:
            raise RuntimeError("clang repository remote mismatch")
        if not (self.args.host_ssl / "usr/include/openssl/bio.h").is_file() or not (self.args.host_ssl / "usr/lib/x86_64-linux-gnu/libcrypto.so").exists():
            raise RuntimeError("user-local libssl-dev build dependency is incomplete")
        host_dep = kernel["host_dependency"]
        deb = self.args.host_ssl.parent / "download" / f"libssl-dev_{host_dep['version']}_amd64.deb"
        runtime_crypto = self.args.host_ssl / "usr/lib/x86_64-linux-gnu/libcrypto.so.3"
        if digest(deb) != host_dep["deb_sha256"] or digest(runtime_crypto) != host_dep["libcrypto_so3_sha256"]:
            raise RuntimeError("user-local libssl-dev identity mismatch")
        host_bc = kernel["host_bc"]
        bc_deb = self.args.host_tools.parent / "download" / f"bc_{host_bc['version']}_amd64.deb"
        if not (self.args.host_tools / "usr/bin/bc").is_file() or digest(bc_deb) != host_bc["deb_sha256"]:
            raise RuntimeError("user-local bc identity mismatch")
        self.run(
            [sys.executable, str(REPO / "tools/sunxi_image_tool.py"), "verify", str(self.base)],
            output=self.stage / "base-outer-verify.log",
        )

    def extract_outer(self, source: Path, names: list[str], output: Path) -> None:
        output.mkdir(parents=True, exist_ok=True)
        for name in names:
            self.run(
                [sys.executable, str(REPO / "tools/sunxi_image_tool.py"), "extract", "-o", str(output), "-f", name, str(source)]
            )

    def prepare_boot(self) -> tuple[Path, Path, Path]:
        extracted = self.stage / "base-outer"
        names = ["boot.fex", "vendor_boot.fex", "vbmeta.fex", "vbmeta_system.fex", "super.fex"]
        self.extract_outer(self.base, names, extracted)
        boot_spec = self.config["base_boot"]
        boot = extracted / "boot.fex"
        self.require(boot, {"size": boot_spec["size"], "sha256": boot_spec["sha256"]}, "base boot")
        for name, expected in self.config["preserved_payloads"].items():
            self.require(extracted / name, expected, f"base {name}")
        unpacked = self.stage / "base-boot-unpacked"
        self.run(
            [sys.executable, str(self.args.aosp / "system/tools/mkbootimg/unpack_bootimg.py"), "--boot_img", str(boot), "--out", str(unpacked), "--format=mkbootimg"],
            output=self.stage / "base-boot-mkbootimg-args.txt",
        )
        kernel = unpacked / "kernel"
        ramdisk = unpacked / "ramdisk"
        self.require(kernel, {"size": boot_spec["kernel_size"], "sha256": boot_spec["kernel_sha256"]}, "base kernel")
        self.require(ramdisk, {"size": boot_spec["ramdisk_size"], "sha256": boot_spec["ramdisk_sha256"]}, "base ramdisk")
        return boot, kernel, ramdisk

    def generate_keymap(self) -> Path:
        customer = self.stage / "customer_ir_ff40.kl"
        source_system = self.args.verified / "logical/system_a.img"
        self.run(["debugfs", "-R", f"dump -p /system/usr/keylayout/customer_ir_ff40.kl {customer}", str(source_system)])
        generated = self.stage / "generated-input"
        generated.mkdir()
        c_output = generated / "rc-sunxi-keymaps.c"
        self.run(
            [
                sys.executable,
                str(REPO / "scripts/generate-m8b-rc-core-input.py"),
                "--map", str(REPO / str(self.config["kernel"]["keymap_relative"])),
                "--customer", str(customer),
                "--c-output", str(c_output),
                "--kl-output", str(generated / "sunxi-ir.kl"),
                "--report", str(generated / "ff40-map-report.json"),
            ]
        )
        return c_output

    def build_kernel(self, stock_kernel: Path, generated_keymap: Path) -> tuple[Path, Path]:
        output = self.stage / "kernel-build"
        output.mkdir()
        kernel = self.config["kernel"]
        self.run(
            [
                "bash", str(REPO / "scripts/build-a16-prototype-a-r2-kernel.sh"),
                str(stock_kernel), str(generated_keymap), str(output),
                str(self.args.source_repo), str(self.args.clang), str(kernel["source_commit"]),
                str(REPO / str(kernel["repeat_patch_relative"])), str(self.args.build_root),
                str(self.args.host_ssl),
                str(self.args.host_tools),
            ],
            output=self.stage / "kernel-build.log",
        )
        image = output / "Image"
        candidate_config = output / "candidate.config"
        values = config_values(candidate_config)
        for key, expected in {**kernel["required_delta"], **kernel["required_preserved"]}.items():
            if values.get(key, "n") != expected:
                raise RuntimeError(f"candidate kernel capability mismatch: {key}")
        return image, candidate_config

    def build_boot(self, image: Path, ramdisk: Path) -> Path:
        spec = self.config["base_boot"]
        unsigned = self.stage / "boot-unsigned.img"
        self.run(
            [
                sys.executable, str(self.args.aosp / "system/tools/mkbootimg/mkbootimg.py"),
                "--header_version", str(spec["header_version"]),
                "--os_version", str(spec["os_version"]),
                "--os_patch_level", str(spec["os_patch_level"]),
                "--kernel", str(image), "--ramdisk", str(ramdisk),
                "--cmdline", str(spec["cmdline"]), "--output", str(unsigned),
            ]
        )
        self.run(
            [
                str(self.aosp_bin / "avbtool"), "add_hash_footer", "--image", str(unsigned),
                "--partition_name", str(spec["avb_partition_name"]),
                "--partition_size", str(spec["avb_partition_size"]),
                "--hash_algorithm", "sha256", "--salt", str(spec["avb_salt"]),
                "--prop", "com.android.build.boot.fingerprint:" + str(spec["boot_fingerprint"]),
                "--prop", "com.android.build.boot.os_version:" + str(spec["boot_os_version_prop"]),
            ]
        )
        boot = self.stage / "boot.fex"
        unsigned.replace(boot)
        if boot.stat().st_size != spec["avb_partition_size"]:
            raise RuntimeError("candidate boot partition size mismatch")
        self.run([str(self.aosp_bin / "avbtool"), "verify_image", "--image", str(boot)], output=self.stage / "boot-avb-verify.log")
        self.run([str(self.aosp_bin / "avbtool"), "info_image", "--image", str(boot)], output=self.stage / "boot-avb-info.txt")
        validated = self.stage / "candidate-boot-unpacked"
        self.run(
            [sys.executable, str(self.args.aosp / "system/tools/mkbootimg/unpack_bootimg.py"), "--boot_img", str(boot), "--out", str(validated), "--format=mkbootimg"],
            output=self.stage / "candidate-boot-mkbootimg-args.txt",
        )
        if digest(validated / "ramdisk") != self.config["base_boot"]["ramdisk_sha256"]:
            raise RuntimeError("candidate ramdisk changed")
        if digest(validated / "kernel") != digest(image):
            raise RuntimeError("candidate boot does not contain built kernel")
        return boot

    def pack(self, boot: Path) -> tuple[Path, dict[str, object]]:
        firmware = self.stage / f"x12-{self.candidate_id}.img"
        audit_file = self.stage / "outer-payload-audit.json"
        self.run(
            [
                sys.executable, str(REPO / "tools/pack_image_preserving.py"),
                "--source", str(self.base), "--output", str(firmware),
                "--replace", f"boot.fex={boot}", "--audit", str(audit_file),
            ]
        )
        self.run([sys.executable, str(REPO / "tools/sunxi_image_tool.py"), "verify", str(firmware)], output=self.stage / "candidate-outer-verify.log")
        audit = json.loads(audit_file.read_text(encoding="utf-8"))
        actions = {item["filename"]: item["action"] for item in audit["payloads"]}
        contract = self.config["container"]
        if len(actions) != contract["total_entries"] or sum(value == "preserved" for value in actions.values()) != contract["preserved_entries"]:
            raise RuntimeError("outer preservation count mismatch")
        if actions.get("boot.fex") != "replacement" or actions.get("Vboot.fex") != "companion":
            raise RuntimeError("boot replacement/companion audit mismatch")

        extracted = self.stage / "candidate-outer"
        self.extract_outer(firmware, ["boot.fex", *self.config["preserved_payloads"].keys()], extracted)
        if digest(extracted / "boot.fex") != digest(boot):
            raise RuntimeError("packed boot changed")
        for name, expected in self.config["preserved_payloads"].items():
            self.require(extracted / name, expected, f"candidate preserved {name}")
        return firmware, audit

    def cgroup_audit(self, candidate_config: Path) -> dict[str, object]:
        output = self.stage / "cgroup-audit"
        report_path = output / "report.json"
        if report_path.is_file():
            return json.loads(report_path.read_text(encoding="utf-8"))
        output.mkdir(exist_ok=True)
        system = REPO / "out/candidates/a16-prototype-a-r1/system_a.img"
        vendor = self.args.verified / "logical/vendor_a.img"
        extracted: dict[str, Path] = {}
        for name in ("cgroups.json", "task_profiles.json"):
            path = output / name
            self.run(["debugfs", "-R", f"dump -p /system/etc/{name} {path}", str(system)])
            extracted[name] = path
        expected = self.config["system_cgroups"]
        if digest(extracted["cgroups.json"]) != expected["cgroups_sha256"] or digest(extracted["task_profiles.json"]) != expected["task_profiles_sha256"]:
            raise RuntimeError("A16 cgroup/task-profile identity mismatch")
        document = json.loads(extracted["cgroups.json"].read_text(encoding="utf-8"))
        v1 = {item["Controller"]: item for item in document["Cgroups"]}
        if set(v1) != {"blkio", "cpu", "cpuset"} or any(item.get("Optional", False) for item in v1.values()):
            raise RuntimeError("A16 required v1 controller contract changed")
        v2 = {item["Controller"]: item for item in document["Cgroups2"]["Controllers"]}
        if document["Cgroups2"]["Path"] != "/sys/fs/cgroup" or not v2["memory"].get("Optional") or "freezer" not in v2:
            raise RuntimeError("A16 cgroup v2 contract changed")

        absence: dict[str, bool] = {}
        probes = {
            "system_cgroups_31": (system, "/system/etc/task_profiles/cgroups_31.json"),
            "system_task_profiles_31": (system, "/system/etc/task_profiles/task_profiles_31.json"),
            "vendor_cgroups": (vendor, "/etc/cgroups.json"),
            "vendor_task_profiles": (vendor, "/etc/task_profiles.json"),
        }
        for label, (image, path) in probes.items():
            text = subprocess.run(["debugfs", "-R", f"stat {path}", str(image)], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False).stdout
            absence[label] = "File not found" in text
        if not all(absence.values()):
            raise RuntimeError(f"unexpected cgroup override present: {absence}")

        soong = json.loads((self.args.aosp / "out-ceiling/soong/soong.ubox10_ceiling_arm.variables").read_text(encoding="utf-8"))

        def nested_values(value: object, key: str) -> list[object]:
            found: list[object] = []
            if isinstance(value, dict):
                for name, item in value.items():
                    if name == key:
                        found.append(item)
                    found.extend(nested_values(item, key))
            elif isinstance(value, list):
                for item in value:
                    found.extend(nested_values(item, key))
            return found

        isolation_values = nested_values(soong, "cgroup_v2_sys_app_isolation")
        if isolation_values != ["true"]:
            raise RuntimeError("cgroup_v2_sys_app_isolation is not enabled")
        main_bp = (self.args.aosp / "system/core/libprocessgroup/Android.bp").read_text(encoding="utf-8")
        setup_bp = (self.args.aosp / "system/core/libprocessgroup/setup/Android.bp").read_text(encoding="utf-8")
        if main_bp.count('defaults: ["libprocessgroup_build_flags_cc"]') < 1 or 'defaults: ["libprocessgroup_build_flags_cc"]' not in setup_bp:
            raise RuntimeError("libprocessgroup/setup build-flag defaults are inconsistent")
        report = {
            "system_cgroups": record(extracted["cgroups.json"]),
            "system_task_profiles": record(extracted["task_profiles.json"]),
            "required_v1": sorted(v1),
            "cgroup2_root": document["Cgroups2"]["Path"],
            "v2_controllers": v2,
            "overrides_absent": absence,
            "first_api_level": expected["first_api_level"],
            "cgroup_v2_sys_app_isolation": True,
            "build_flag_consumers": ["libprocessgroup", "libprocessgroup_setup"],
            "kernel": {key: value for key, value in config_values(candidate_config).items() if key in {**self.config["kernel"]["required_delta"], **self.config["kernel"]["required_preserved"]}},
            "conclusion": "Required blkio/cpu/cpuset mounts can complete; CgroupSetup can then create /sys/fs/cgroup/apps and /sys/fs/cgroup/system. Optional v2 memory remains a warning-only limitation.",
        }
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return report

    def compatibility_audit(self, candidate_config: Path) -> dict[str, object]:
        audit = self.stage / "exact-audit"
        root = audit / "root"
        for path in (
            root / "system/etc",
            root / "system_ext/etc",
            root / "vendor/etc",
            root / "product/etc",
            root / "odm",
            root / "apex",
        ):
            path.mkdir(parents=True, exist_ok=True)
        images = {
            "system": REPO / "out/candidates/a16-prototype-a-r1/system_a.img",
            "vendor": self.args.verified / "logical/vendor_a.img",
            "product": self.args.verified / "logical/product_a.img",
            "vendor_dlkm": self.args.verified / "logical/vendor_dlkm_a.img",
        }
        for name, image in images.items():
            self.run(["e2fsck", "-fn", str(image)], output=audit / f"e2fsck-{name}.log")

        # The VM deliberately grants no passwordless mount capability. VINTF
        # needs only regular XML files, so extract those read-only with
        # debugfs. Ownership-restoration warnings are expected and irrelevant
        # to checkvintf; file contents remain exact.
        extracts = (
            (images["system"], "/system/etc/vintf", root / "system/etc", "system"),
            (images["system"], "/system/system_ext/etc/vintf", root / "system_ext/etc", "system-ext"),
            (images["vendor"], "/etc/vintf", root / "vendor/etc", "vendor"),
            (images["product"], "/etc/vintf", root / "product/etc", "product"),
        )
        for image, image_path, destination, label in extracts:
            self.run(
                ["debugfs", "-R", f"rdump {image_path} {destination}", str(image)],
                output=audit / f"debugfs-vintf-{label}.log",
            )
        shutil.copyfile(
            self.args.gate1 / "offline-closure/linker-root/apex/apex-info-list.xml",
            root / "apex/apex-info-list.xml",
        )
        os.symlink(
            self.args.gate1 / "offline-closure/linker-root/apex/com.android.vndk.v31",
            root / "apex/com.android.vndk.v31",
        )

        full_command = [
            str(self.aosp_bin / "checkvintf"), "--check-compat",
            "--dirmap", f"/system:{root / 'system'}",
            "--dirmap", f"/system_ext:{root / 'system_ext'}",
            "--dirmap", f"/vendor:{root / 'vendor'}",
            "--dirmap", f"/product:{root / 'product'}",
            "--dirmap", f"/odm:{root / 'odm'}",
            "--dirmap", f"/apex:{root / 'apex'}",
            "--property", "ro.product.first_api_level=31",
            "--kernel", f"5.4.125:{candidate_config}",
        ]
        rc = self.run(full_command, output=audit / "vintf-full.log", allowed={65})
        text = (audit / "vintf-full.log").read_text(encoding="utf-8", errors="replace")
        if not expected_inherited_nfs_exception(text):
            raise RuntimeError("r2 VINTF result is not the single inherited NFS exception")

        r1_audit = REPO / "out/candidates/a16-prototype-a-r1/exact-audit"
        for path in (
            r1_audit / "linker-generated/ld.config.txt",
            r1_audit / "combined-sepolicy.bin",
            r1_audit / "selinux-compile.log",
            REPO / "out/candidates/a16-prototype-a-r1/elf-summary.md",
        ):
            if not path.is_file():
                raise RuntimeError(f"missing accepted r1 compatibility evidence: {path}")
        linker = (r1_audit / "linker-generated/ld.config.txt").read_text(encoding="utf-8")
        elf = (REPO / "out/candidates/a16-prototype-a-r1/elf-summary.md").read_text(encoding="utf-8")
        if "libaudioroute.so" not in linker or "[vendor]" not in linker or "ELF32 未解析名称：0" not in elf or "ELF64 未解析名称：0" not in elf:
            raise RuntimeError("accepted byte-identical r1 compatibility evidence is incomplete")
        return {
            "full_vintf": "EXPECTED_INHERITED_EXCEPTION",
            "full_vintf_exit": rc,
            "only_exception": self.config["known_vintf_exception"],
            "vintf_extraction": "PASS_UNPRIVILEGED_DEBUGFS_RDUMP",
            "linkerconfig": "INHERITED_PASS_FROM_BYTE_IDENTICAL_R1_SYSTEM_SUPER_VENDOR_PRODUCT",
            "selinux_split_compile": "INHERITED_PASS_FROM_BYTE_IDENTICAL_R1_POLICY_INPUTS",
            "elf_name_level": "INHERITED_PASS_FROM_BYTE_IDENTICAL_R1_PARTITIONS",
            "e2fsck": "PASS",
            "apex_and_lp": "INHERITED_PASS_FROM_BYTE_IDENTICAL_R1_SUPER",
        }

    def finish(self, firmware: Path, boot: Path, image: Path, candidate_config: Path, cgroups: dict[str, object], compatibility: dict[str, object]) -> None:
        if record(self.base) != self.base_before:
            raise RuntimeError("r1 base candidate changed during build")
        result = {
            "id": self.candidate_id,
            "status": "OFFLINE_CHECKED_CANDIDATE",
            "gate2": "CLOSED",
            "physical_device_actions_performed": False,
            "flash_authorized": False,
            "firmware": record(firmware),
            "boot": record(boot),
            "kernel": record(image),
            "kernel_config": record(candidate_config),
            "root_cause": "A16 CgroupSetup aborts on required blkio because CONFIG_BLK_CGROUP=n; required cpuset would fail next because CONFIG_CPUSETS=n. The early return prevents creation of /sys/fs/cgroup/system, so init child setup fails before exec for ueventd and apexd-bootstrap.",
            "kernel_delta": self.config["kernel"]["required_delta"],
            "payload_delta": ["kernel", "boot.fex", "Vboot.fex"],
            "preserved": ["r1 system/APEX", "super/LP", "vendor_boot/ramdisk", "vendor/product/vendor_dlkm", "vbmeta/vbmeta_system", "all other outer payloads"],
            "cgroup_audit": cgroups,
            "compatibility": compatibility,
            "avb": "PASS: accepted boot hash-footer structure/properties/salt retained and candidate boot verifies; vbmeta and vbmeta_system preserved byte-for-byte",
            "rollback": "PASS: m8b-remote-r1, Test8r2 and stock rollback assets untouched",
            "decision": "Technically coherent for a separately authorized single UART-first ARM32 exact-board boot; no physical boot is authorized by this result.",
            "remaining_limit": "Offline checks cannot prove cgroup mount success on device, bootstrap APEX activation, servicemanager, zygote32, system_server, graphics, media, audio, wireless, DRM, or enforcing SELinux.",
        }
        result = rewrite_path_values(result, self.stage, self.final)
        (self.stage / "build-result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
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
            _base_boot, stock_kernel, ramdisk = self.prepare_boot()
            generated_keymap = self.generate_keymap()
            image, candidate_config = self.build_kernel(stock_kernel, generated_keymap)
            boot = self.build_boot(image, ramdisk)
            firmware, _audit = self.pack(boot)
            cgroups = self.cgroup_audit(candidate_config)
            compatibility = self.compatibility_audit(candidate_config)
            self.finish(firmware, boot, image, candidate_config, cgroups, compatibility)
            print(f"SUCCESS: {self.final} in {time.time() - started:.1f}s", flush=True)
        except Exception:
            if self.stage.exists() and not self.args.keep_failed:
                shutil.rmtree(self.stage)
            raise

    def resume_after_pack(self) -> None:
        if self.final.exists():
            raise RuntimeError(f"refusing to overwrite existing candidate: {self.final}")
        if not self.stage.is_dir() or self.stage.parent != self.final.parent:
            raise RuntimeError("resume stage must be the exact candidate staging directory")
        firmware = self.stage / f"x12-{self.candidate_id}.img"
        boot = self.stage / "boot.fex"
        image = self.stage / "kernel-build/Image"
        candidate_config = self.stage / "kernel-build/candidate.config"
        for path in (image, candidate_config):
            if not path.is_file():
                raise RuntimeError(f"resume artifact is incomplete: {path}")
        if not firmware.is_file():
            ramdisk = self.stage / "base-boot-unpacked/ramdisk"
            if not ramdisk.is_file():
                raise RuntimeError(f"resume artifact is incomplete: {ramdisk}")
            boot = self.build_boot(image, ramdisk)
            firmware, _audit = self.pack(boot)
        for path in (firmware, boot, self.stage / "outer-payload-audit.json"):
            if not path.is_file():
                raise RuntimeError(f"resume artifact is incomplete: {path}")
        self.base_before = record(self.base)
        cgroups = self.cgroup_audit(candidate_config)
        compatibility = self.compatibility_audit(candidate_config)
        self.finish(firmware, boot, image, candidate_config, cgroups, compatibility)
        print(f"SUCCESS: resumed offline audit and published {self.final}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--aosp", type=Path, default=DEFAULT_AOSP)
    parser.add_argument("--verified", type=Path, default=DEFAULT_VERIFIED)
    parser.add_argument("--source-repo", type=Path, default=DEFAULT_SOURCE_REPO)
    parser.add_argument("--clang", type=Path, default=DEFAULT_CLANG)
    parser.add_argument("--build-root", type=Path, default=DEFAULT_BUILD_ROOT)
    parser.add_argument("--host-ssl", type=Path, default=DEFAULT_HOST_SSL)
    parser.add_argument("--host-tools", type=Path, default=DEFAULT_HOST_TOOLS)
    parser.add_argument("--gate1", type=Path, default=DEFAULT_GATE1)
    parser.add_argument("--keep-failed", action="store_true")
    parser.add_argument("--resume-stage", type=Path)
    args = parser.parse_args()
    builder = Builder(args)
    if args.resume_stage:
        builder.resume_after_pack()
    else:
        builder.build()


if __name__ == "__main__":
    main()
