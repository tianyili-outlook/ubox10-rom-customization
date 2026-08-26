#!/usr/bin/env python3
"""Run the exact-board offline compatibility audit for Prototype A r3."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET


REPO = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE = REPO / "out/candidates/a16-prototype-a-r3"
DEFAULT_AOSP = Path("/work/src/ubox10-a16-ceiling")
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


def expected_nfs_only(output: str) -> bool:
    clean = ANSI_ESCAPE.sub("", output)
    marker = "ERROR: files are incompatible:"
    if marker not in clean:
        return False
    error = clean.rsplit(marker, 1)[1]
    config_errors = re.findall(r"For config (CONFIG_[A-Z0-9_]+)", error)
    return (
        "For config CONFIG_NFS_FS, value = y but required n" in error
        and config_errors == ["CONFIG_NFS_FS"]
        and "vendor.display." not in error
        and error.rstrip().endswith("INCOMPATIBLE")
    )


class Auditor:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.candidate = args.candidate
        self.audit = self.candidate / "offline-audit"
        self.host = args.aosp / "out-ceiling/host/linux-x86/bin"
        self.mounts = self.audit / "mounts"
        self.root = self.audit / "root"
        self.mounted: list[Path] = []
        self.log = self.audit / "commands.log"
        self.build_result = json.loads(
            (self.candidate / "build-result.json").read_text(encoding="utf-8")
        )
        self.kernel_evidence = (
            args.kernel_evidence
            if args.kernel_evidence is not None
            else Path(str(self.build_result["kernel"]["path"])).parent.parent
        )

    def run(
        self, command: list[str], *, output: Path | None = None,
        allowed: set[int] | None = None,
    ) -> int:
        line = "$ " + subprocess.list2cmdline(command)
        print(line, flush=True)
        self.log.parent.mkdir(parents=True, exist_ok=True)
        with self.log.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")
        destination = output or self.log
        destination.parent.mkdir(parents=True, exist_ok=True)
        mode = "w" if output else "a"
        environment = os.environ.copy()
        environment["PATH"] = f"{self.host}:{environment['PATH']}"
        with destination.open(mode, encoding="utf-8", newline="\n") as stream:
            done = subprocess.run(
                command, cwd=REPO, env=environment, stdout=stream,
                stderr=subprocess.STDOUT, text=True, check=False,
            )
        expected = {0} if allowed is None else allowed
        if done.returncode not in expected:
            raise RuntimeError(f"command failed ({done.returncode}): {command}")
        return done.returncode

    def setup(self) -> dict[str, Path]:
        if self.audit.exists() and not self.args.resume:
            raise RuntimeError(f"refusing to overwrite audit: {self.audit}")
        if self.args.resume:
            if not self.audit.is_dir() or (self.audit / "offline-audit.json").exists():
                raise RuntimeError("resume requires an incomplete existing audit directory")
        else:
            self.audit.mkdir(parents=True)
        if self.build_result["status"] != "PACKAGED_AWAITING_FULL_OFFLINE_AUDIT":
            raise RuntimeError("candidate is not in the packaged pre-audit state")
        firmware = Path(str(self.build_result["firmware"]["path"]))
        if record(firmware) != self.build_result["firmware"]:
            raise RuntimeError("candidate firmware identity changed")
        kernel_audit_path = self.kernel_evidence / "offline-audit.json"
        kernel_audit = json.loads(kernel_audit_path.read_text(encoding="utf-8"))
        if kernel_audit.get("result") != "PASS_WITH_PHYSICAL_VALIDATION_REQUIRED":
            raise RuntimeError("Path-A kernel audit is not a pass")
        if kernel_audit["build"].get("config_contract") != "path-a":
            raise RuntimeError("kernel audit did not select the Path-A config")

        images = {
            "system": self.candidate / "system_a.img",
            "vendor": self.candidate / "candidate-logical/vendor_a.img",
            "product": self.candidate / "candidate-logical/product_a.img",
            "vendor_dlkm": self.candidate / "vendor_dlkm_a.img",
        }
        for name, path in images.items():
            self.run(["e2fsck", "-fn", str(path)], output=self.audit / f"e2fsck-{name}.log")
        self.run(
            [sys.executable, str(REPO / "tools/sunxi_image_tool.py"), "verify", str(firmware)],
            output=self.audit / "outer-verify.log",
        )
        return images

    def mount_images(self, images: dict[str, Path]) -> None:
        for name in images:
            (self.mounts / name).mkdir(parents=True, exist_ok=True)
        for name, image in images.items():
            point = self.mounts / name
            self.run(["sudo", "mount", "-o", "loop,ro,noload", str(image), str(point)])
            self.mounted.append(point)
        (self.root / "odm").mkdir(parents=True, exist_ok=True)
        (self.root / "apex").mkdir(parents=True, exist_ok=True)
        links = {
            "system": self.mounts / "system/system",
            "system_ext": self.mounts / "system/system/system_ext",
            "vendor": self.mounts / "vendor",
            "product": self.mounts / "product",
            "vendor_dlkm": self.mounts / "vendor_dlkm",
        }
        for name, target in links.items():
            link = self.root / name
            if link.is_symlink():
                if link.resolve() != target.resolve():
                    raise RuntimeError(f"resume root link changed: {link}")
            elif link.exists():
                raise RuntimeError(f"offline root path is not the expected symlink: {link}")
            else:
                os.symlink(target, link)

    def audit_apex(self) -> dict[str, object]:
        apex_dirs = {
            "system": self.root / "system/apex",
            "system_ext": self.root / "system_ext/apex",
            "product": self.root / "product/apex",
            "vendor": self.root / "vendor/apex",
            "odm": self.root / "odm/apex",
        }
        apex_files = sorted(
            path for directory in apex_dirs.values()
            for path in (directory.iterdir() if directory.is_dir() else ())
            if path.suffix in {".apex", ".capex"}
        )
        if not apex_files:
            raise RuntimeError("candidate contains no installed APEX files")
        verifier = [
            str(self.host / "host_apex_verifier"),
            "--deapexer", str(self.host / "deapexer"),
            "--debugfs", str(self.host / "debugfs_static"),
            "--fsckerofs", str(self.host / "fsck.erofs"),
            "--sdk_version", "36",
        ]
        for partition, path in apex_dirs.items():
            if path.is_dir():
                verifier.extend([f"--out_{partition}", str(path)])
        self.run(verifier, output=self.audit / "host-apex-verifier.log")

        command = [
            str(self.host / "apexd_host"), "--apex_path", str(self.root / "apex"),
            "--system_path", str(self.root / "system"),
            "--system_ext_path", str(self.root / "system_ext"),
            "--product_path", str(self.root / "product"),
            "--vendor_path", str(self.root / "vendor"),
            "--odm_path", str(self.root / "odm"),
        ]
        info = self.root / "apex/apex-info-list.xml"
        if not info.is_file():
            self.run(command, output=self.audit / "apexd-host.log")
        apex_infos = ET.parse(info).getroot().findall("apex-info")
        if len(apex_infos) != len(apex_files):
            raise RuntimeError("activated APEX count differs from installed APEX count")
        names = sorted(item.attrib["moduleName"] for item in apex_infos)
        for required in ("com.android.runtime", "com.android.vndk.v31"):
            if required not in names or not (self.root / "apex" / required).is_dir():
                raise RuntimeError(f"required bootstrap/linker APEX is missing: {required}")
        vndk = self.root / "apex/com.android.vndk.v31"
        libaudioroute = list(vndk.rglob("libaudioroute.so"))
        if len(libaudioroute) != 1:
            raise RuntimeError("VNDK31 ARM32 libaudioroute.so is missing or ambiguous")
        machine = subprocess.check_output(
            ["readelf", "-h", str(libaudioroute[0])], text=True
        )
        if "Class:                             ELF32" not in machine or "Machine:                           ARM" not in machine:
            raise RuntimeError("VNDK31 libaudioroute.so is not ARM32")
        return {
            "installed_count": len(apex_files),
            "installed_names": names,
            "host_apex_verifier_all": "PASS",
            "activated_count": len(apex_infos),
            "payload_filesystems_and_init_rc": "PASS",
            "runtime_apex": "PASS",
            "vndk31_apex": "PASS",
            "vndk31_libaudioroute_arm32": "PASS",
            "apex_info_list": record(info),
        }

    def audit_vintf_linker_selinux(self) -> dict[str, object]:
        system_rc = self.run(
            [str(self.host / "checkvintf"), "--check-one", "--dirmap", f"/system:{self.root / 'system'}"],
            output=self.audit / "vintf-system.log",
        )
        full = [
            str(self.host / "checkvintf"), "--check-compat",
            "--dirmap", f"/system:{self.root / 'system'}",
            "--dirmap", f"/system_ext:{self.root / 'system_ext'}",
            "--dirmap", f"/vendor:{self.root / 'vendor'}",
            "--dirmap", f"/product:{self.root / 'product'}",
            "--dirmap", f"/odm:{self.root / 'odm'}",
            "--dirmap", f"/apex:{self.root / 'apex'}",
            "--property", "ro.product.first_api_level=31",
            "--kernel", f"5.4.302:{self.kernel_evidence / 'build-result/built.config'}",
        ]
        full_rc = self.run(full, output=self.audit / "vintf-full.log", allowed={65})
        full_text = (self.audit / "vintf-full.log").read_text(errors="replace")
        if not expected_nfs_only(full_text):
            raise RuntimeError("full VINTF result is not the sole inherited NFS exception")

        linker_dir = self.audit / "linker-generated"
        linker_dir.mkdir(exist_ok=True)
        self.run(
            [str(self.host / "linkerconfig"), "--target", str(linker_dir),
             "--root", str(self.root), "--vndk", "31", "--product_vndk", "",
             "--treblelize"],
            output=self.audit / "linkerconfig.log",
        )
        linker = (linker_dir / "ld.config.txt").read_text(encoding="utf-8")
        required_linker = (
            "[vendor]", "namespace.default.links = rs,system,vndk",
            "namespace.default.link.vndk.shared_libs =", "libaudioroute.so",
            "/apex/com.android.vndk.v31/${LIB}",
        )
        for fragment in required_linker:
            if fragment not in linker:
                raise RuntimeError(f"generated vendor linker namespace is incomplete: {fragment}")

        system_root = self.root / "system"
        system_ext = self.root / "system_ext"
        vendor = self.root / "vendor"
        self.run(
            [
                str(self.host / "secilc"),
                str(system_root / "etc/selinux/plat_sepolicy.cil"),
                str(system_root / "etc/selinux/mapping/31.0.cil"),
                str(system_root / "etc/selinux/mapping/31.0.compat.cil"),
                str(system_ext / "etc/selinux/system_ext_sepolicy.cil"),
                str(system_ext / "etc/selinux/mapping/31.0.cil"),
                str(system_ext / "etc/selinux/mapping/31.0.compat.cil"),
                str(vendor / "etc/selinux/plat_pub_versioned.cil"),
                str(vendor / "etc/selinux/vendor_sepolicy.cil"),
                "-m", "-M", "true", "-G", "-N", "-c", "30",
                "-o", str(self.audit / "combined-sepolicy.bin"), "-f", "/dev/null",
            ],
            output=self.audit / "selinux-compile.log",
        )
        return {
            "system_vintf": "PASS",
            "system_vintf_exit": system_rc,
            "full_vintf": "INCOMPATIBLE_EXPECTED_INHERITED_NFS_EXCEPTION_ONLY",
            "full_vintf_exit": full_rc,
            "full_vintf_exception": {
                "actual": "CONFIG_NFS_FS=y", "required": "CONFIG_NFS_FS=n",
                "classification": "inherited FCM-6 conformance exception; full VINTF is not a pass",
            },
            "linkerconfig_vendor_vndk31": "PASS",
            "selinux_split_compile": "PASS_OFFLINE_ONLY_NOT_RUNTIME_ENFORCING_CLAIM",
        }

    def audit_elf(self, images: dict[str, Path]) -> dict[str, object]:
        csv_path = self.audit / "elf-inventory.csv"
        summary = self.audit / "elf-summary.md"
        command = [sys.executable, str(REPO / "scripts/inventory-elf.py")]
        for name, path in images.items():
            command.extend(["--partition", f"{name}={path}"])
        command.extend([
            "--csv", str(csv_path), "--summary", str(summary),
            "--label", f"{self.build_result['id']} exact-board candidate",
        ])
        self.run(command, output=self.audit / "elf-inventory.log")
        rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
        aarch64 = [row for row in rows if row["machine"] == "AArch64"]
        kernel_modules = [
            row for row in aarch64
            if row["partition"] == "vendor_dlkm" and row["path"].endswith(".ko")
        ]
        packaged_test_shims = [
            row for row in aarch64
            if row["partition"] == "system"
            and row["path"].endswith(
                "CtsShimPriv.apk!/lib/arm64-v8a/libshim_jni.so"
            )
        ]
        aarch64_consumers = [
            row for row in aarch64
            if row not in kernel_modules and row not in packaged_test_shims
        ]
        if aarch64_consumers or len(packaged_test_shims) != 1:
            raise RuntimeError(
                "unexpected AArch64 userspace inventory: "
                f"consumers={aarch64_consumers[:5]} shims={packaged_test_shims}"
            )
        bpf = [row for row in rows if row["machine"] == "BPF"]
        invalid_elf64 = [
            row for row in rows
            if row["class"] == "ELF64" and row["machine"] != "BPF"
            and row not in kernel_modules and row not in packaged_test_shims
        ]
        if invalid_elf64:
            raise RuntimeError(f"unexpected ELF64 userspace objects: {invalid_elf64[:5]}")
        build_prop = subprocess.check_output(
            ["debugfs", "-R", "cat /system/build.prop", str(images["system"])],
            text=True, stderr=subprocess.DEVNULL,
        )
        vendor_prop = subprocess.check_output(
            ["debugfs", "-R", "cat /build.prop", str(images["vendor"])],
            text=True, stderr=subprocess.DEVNULL,
        )
        architecture_contract = (
            "ro.system.product.cpu.abilist=armeabi-v7a,armeabi",
            "ro.system.product.cpu.abilist32=armeabi-v7a,armeabi",
            "ro.system.product.cpu.abilist64=",
        )
        if any(line not in build_prop for line in architecture_contract):
            raise RuntimeError("system ARM32/no-secondary-ABI properties are incomplete")
        if "ro.zygote=zygote32" not in vendor_prop:
            raise RuntimeError("accepted exact-board zygote selection is not zygote32")
        def image_path_exists(path: str) -> bool:
            output = subprocess.check_output(
                ["debugfs", "-R", f"stat {path}", str(images["system"])],
                text=True, stderr=subprocess.STDOUT,
            )
            return "Inode:" in output

        if image_path_exists("/system/bin/app_process64") or image_path_exists(
            "/system/bin/linker64"
        ):
            raise RuntimeError("ARM64 platform userspace executable is present")
        text = summary.read_text(encoding="utf-8")
        if "ELF32 未解析名称：0" not in text or "ELF64 未解析名称：0" not in text:
            raise RuntimeError("ELF name-level dependency closure failed")
        return {
            "total_elf": len(rows),
            "aarch64_userspace_consumers": 0,
            "inactive_packaged_aarch64_cts_test_shim": len(packaged_test_shims),
            "inactive_packaged_aarch64_classification": (
                "AOSP CTS test-only APK payload selected by the ARM prebuilt; unavailable to "
                "zygote32 because arm64 is absent from the product ABI lists; not a platform "
                "AArch64 consumer or secondary ABI"
            ),
            "aarch64_kernel_modules": len(kernel_modules),
            "primary_abi": "armeabi-v7a",
            "secondary_architecture": "none",
            "zygote": "zygote32",
            "app_process64": "absent",
            "linker64": "absent",
            "elf64_bpf_objects": len(bpf),
            "elf64_bpf_classification": "BPF bytecode, not AArch64 userspace",
            "unresolved_elf32_names": 0,
            "unresolved_elf64_names": 0,
            "accepted_vendor_dependency_name_closure": "PASS",
        }

    def finish(
        self, images: dict[str, Path], apex: dict[str, object],
        compatibility: dict[str, object], elf: dict[str, object],
    ) -> None:
        kernel_audit = json.loads(
            (self.kernel_evidence / "offline-audit.json").read_text(encoding="utf-8")
        )
        kernel_hardware = json.loads(
            (self.kernel_evidence / "path-a-hardware-audit.json").read_text(
                encoding="utf-8"
            )
        )
        if kernel_hardware.get("result") != "PASS_PATH_A_R5_HARDWARE_AND_FMAC_CONTRACT":
            raise RuntimeError("Path-A hardware/FMAC addendum is not a pass")
        result = {
            "schema": 1,
            "candidate": self.build_result["firmware"],
            "decision": "OFFLINE CHECKED / READY TO REQUEST PHYSICAL VALIDATION",
            "gate2": "UNBLOCKED_AWAITING_EXPLICIT_PHYSICAL_VALIDATION_DECISION",
            "physical_device_actions_performed": False,
            "flash_authorized": False,
            "filesystem_image_integrity": "PASS",
            "avb_lp_outer": "PASS_FROM_CANDIDATE_BUILD_EVIDENCE",
            "apex": apex,
            "compatibility": compatibility,
            "elf_abi": elf,
            "kernel": {
                "result": kernel_audit["result"],
                "release": kernel_audit["source"]["kernel_release"],
                "config_contract": kernel_audit["build"]["config_contract"],
                "config_sha256": kernel_audit["build"]["config_sha256"],
                "module_count": kernel_audit["modules"]["count"],
                "hardware_config": "PASS",
                "module_abi_crc_closure": "PASS",
                "hardware_and_fmac_addendum": kernel_hardware,
            },
            "limitations": [
                "No physical UBOX action occurred or is authorized by this audit.",
                "Offline SELinux compilation does not prove enforcing runtime compatibility.",
                "No boot, zygote, system_server, SurfaceFlinger or HWC runtime pass is claimed.",
                "Full VINTF remains incompatible only for the inherited CONFIG_NFS_FS exception.",
            ],
        }
        (self.audit / "offline-audit.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        self.build_result["status"] = "OFFLINE_CHECKED"
        self.build_result["decision"] = result["decision"]
        self.build_result["gate2"] = result["gate2"]
        self.build_result["offline_audit"] = record(self.audit / "offline-audit.json")
        (self.candidate / "build-result.json").write_text(
            json.dumps(self.build_result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        sums = []
        for path in sorted(self.candidate.iterdir()):
            if path.is_file() and path.name != "SHA256SUMS":
                sums.append(f"{digest(path)}  {path.name}")
        (self.candidate / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")

    def execute(self) -> None:
        images = self.setup()
        try:
            self.mount_images(images)
            apex = self.audit_apex()
            compatibility = self.audit_vintf_linker_selinux()
            elf = self.audit_elf(images)
        finally:
            for point in reversed(self.mounted):
                self.run(["sudo", "umount", str(point)], allowed={0, 32})
        self.finish(images, apex, compatibility, elf)
        print("OFFLINE CHECKED / READY TO REQUEST PHYSICAL VALIDATION", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--aosp", type=Path, default=DEFAULT_AOSP)
    parser.add_argument(
        "--kernel-evidence", type=Path,
        help="Path-A evidence directory; default derives from build-result.json",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="resume an incomplete audit after a bounded harness correction",
    )
    Auditor(parser.parse_args()).execute()


if __name__ == "__main__":
    main()
