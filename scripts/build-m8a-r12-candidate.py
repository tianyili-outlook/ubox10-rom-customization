#!/usr/bin/env python3
"""Build r12 by restoring the exact Test8r2 Allwinner multi_ir/uinput remote stack."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import time


REPO = Path(__file__).resolve().parents[1]
BASE_BUILDER = REPO / "scripts" / "build-m8a-r11-candidate.py"
AUDITOR = REPO / "scripts" / "audit-logical-system-init.py"
DEFAULT_CONFIG = REPO / "configs" / "candidates" / "m8a-initial-atv-r12.json"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load module: " + str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


r11 = load_module(BASE_BUILDER, "m8a_r11_builder")


class BuildR12(r11.BuildR11):
    def __init__(self, config: dict[str, object], keep_failed: bool) -> None:
        super().__init__(config, keep_failed)
        self.reference_remote: Path | None = None
        self.reference_remote_before: dict[str, object] | None = None
        self.remote_source_dir: Path | None = None

    def setup(self) -> None:
        super().setup()
        reference = self.config["reference_test8r2"]
        assert isinstance(reference, dict)
        self.reference_remote = self.project_root / str(reference["project_relative"])
        if not self.reference_remote.is_file():
            raise RuntimeError("missing Test8r2 remote reference: " + str(self.reference_remote))
        self.reference_remote_before = r11.r10.base.record(self.reference_remote)
        if (
            self.reference_remote_before["size"] != reference["size"]
            or self.reference_remote_before["sha256"] != reference["sha256"]
        ):
            raise RuntimeError("Test8r2 remote reference identity mismatch")
        self.extract_reference_remote(reference)

    @staticmethod
    def _sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest().upper()

    @staticmethod
    def _customer_map(data: bytes) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        for line in data.decode("utf-8").splitlines():
            fields = line.split()
            if len(fields) >= 4 and fields[0] == "key":
                result.append({"scancode": int(fields[1], 0), "label": fields[2], "flag": fields[3]})
        return result

    @staticmethod
    def _linux_key_map(data: bytes) -> dict[int, str]:
        result: dict[int, str] = {}
        for line in data.decode("utf-8").splitlines():
            fields = line.split()
            if len(fields) >= 3 and fields[0] == "key":
                result[int(fields[1], 0)] = fields[2]
        return result

    def extract_reference_remote(self, reference: dict[str, object]) -> None:
        assert self.reference_remote is not None and self.reference_remote_before is not None
        outer = self.stage / "test8r2-remote-source"
        outer.mkdir()
        self.run([
            sys.executable,
            str(r11.r10.base.TOOLS / "sunxi_image_tool.py"),
            "extract", "-o", str(outer), "-f", "super.fex", str(self.reference_remote),
        ])
        super_image = outer / "super.fex"
        super_record = r11.r10.base.record(super_image)
        if super_record["size"] != reference["super_size"] or super_record["sha256"] != reference["super_sha256"]:
            raise RuntimeError("Test8r2 remote super identity mismatch")

        auditor = load_module(AUDITOR, "m8a_r12_logical_auditor")
        source = auditor.open_super_source(super_image)
        self.remote_source_dir = self.stage / "test8r2-remote-files"
        self.remote_source_dir.mkdir()
        extracted: list[dict[str, object]] = []
        contents: dict[str, bytes] = {}
        try:
            metadata = auditor.parse_lp_metadata(source)
            logical = auditor.LogicalPartitionSource(source, metadata, "system_a")
            ext4 = auditor.Ext4Reader(logical)
            artifacts = self.config["remote_artifacts"]
            assert isinstance(artifacts, list)
            for item in artifacts:
                assert isinstance(item, dict)
                source_path = str(item["source_path"])
                inode = ext4.lookup(source_path.lstrip("/"))
                if inode.mode & 0xF000 != 0x8000 or inode.mode & 0o7777 != int(str(item["mode"]), 8):
                    raise RuntimeError("unexpected Test8r2 remote inode: " + source_path)
                data = ext4.read_inode_data(inode)
                if len(data) != item["size"] or self._sha256(data) != item["sha256"]:
                    raise RuntimeError("Test8r2 remote artifact identity mismatch: " + source_path)
                target = self.remote_source_dir / source_path.lstrip("/")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                contents[source_path] = data
                extracted.append({
                    "partition": "system_a",
                    "source_path": source_path,
                    "destination_path": item["destination_path"],
                    "size": len(data),
                    "sha256": item["sha256"],
                    "mode": item["mode"],
                    "uid": item["uid"],
                    "gid": item["gid"],
                    "selinux": item["selinux"],
                    "build_id": item.get("build_id"),
                })
        finally:
            source.close()

        customer = self._customer_map(contents["/system/usr/keylayout/customer_ir_ff40.kl"])
        customer_by_scan = {int(item["scancode"]): item for item in customer}
        expected = {
            11: "DPAD_UP", 14: "DPAD_DOWN", 16: "DPAD_LEFT", 17: "DPAD_RIGHT",
            13: "DPAD_CENTER", 66: "BACK", 26: "HOME", 21: "VOLUME_UP", 28: "VOLUME_DOWN",
            77: "POWER", 84: "MOUSE",
        }
        if len(customer) != 49 or any(customer_by_scan.get(code, {}).get("label") != label for code, label in expected.items()):
            raise RuntimeError("customer_ir_ff40 mapping contract mismatch")

        physical = self._linux_key_map(contents["/system/usr/keylayout/sunxi-ir.kl"])
        virtual = self._linux_key_map(contents["/system/usr/keylayout/sunxi-ir-uinput.kl"])
        required_linux = {19: "DPAD_UP", 20: "DPAD_DOWN", 21: "DPAD_LEFT", 22: "DPAD_RIGHT", 23: "DPAD_CENTER", 232: "MOUSE"}
        if any(physical.get(code) != label or virtual.get(code) != label for code, label in required_linux.items()):
            raise RuntimeError("sunxi IR keylayout contract mismatch")

        multi = contents["/system/bin/multi_ir"]
        for marker in (
            b"/dev/uinput\0", b"customer_ir_\0", b"sunxi-ir.kl\0", b"sunxi-ir-uinput\0",
            b"VirtualMouse\0", b"MultiirService enterMouseMode\0", b"MultiirService exitMouseMode\0",
        ):
            if marker not in multi:
                raise RuntimeError("multi_ir mouse/runtime marker missing: " + marker.decode("ascii").rstrip("\0"))

        libinput = contents["/system/lib/libinput.so"]
        mouse = self.config["mouse_contract"]
        assert isinstance(mouse, dict)
        for label in mouse["vendor_labels"]:
            if (str(label).encode("ascii") + b"\0") not in libinput:
                raise RuntimeError("Test8r2 libinput vendor label missing: " + str(label))

        report = {
            "reference_candidate": self.reference_remote_before,
            "reference_super": super_record,
            "source_tree_result": "The current AOSP checkout has no vendor/aw tree; exact binary debug strings identify vendor/aw/homlet/hardware/input/multi_ir, so the pinned Test8r2 system is the authoritative build input.",
            "artifacts": extracted,
            "customer_ir_ff40": {
                "path": "/system/usr/keylayout/customer_ir_ff40.kl",
                "sha256": "DB54F9843081DDC492F9BDD35E7EE341EBCB4562991513CB5B7A26BBBC74DE39",
                "file_context": "u:object_r:system_file:s0",
                "active_entries": customer,
                "mouse_toggle": {"scancode": 84, "raw_msc_scan": "ff4054", "label": "MOUSE"},
                "power": {"scancode": 77, "raw_msc_scan": "ff404d", "label": "POWER"},
            },
            "mouse_implementation": {
                "owner": "/system/bin/multi_ir",
                "functions_from_embedded_debug_symbols": [
                    "setMouseMode(int)", "ir_key_repeat(int)", "detect_key_input(key_dev_t*)",
                    "report_mouse_keyevent(int,int)", "create_virtual_mouse_dev(char*)",
                    "setup_virtual_input_dev(char*)",
                ],
                "output": "uinput EV_REL REL_X/REL_Y plus EV_KEY; Test8r2 reports CURSOR/DPAD and 1920x1080 pointer ranges",
                "repeat_and_acceleration": "multi_ir owns repeat timing and pointer movement; setitimer/gettimeofday imports and the repeat/mouse debug symbols keep this behavior inside the exact binary",
                "libinput_compatibility": "Exact Test8r2 libinput is required because r11 libinput lacks the Allwinner labels and KeyLayoutMap rejects an unknown label with BAD_VALUE.",
            },
            "excluded": self.config["excluded_test8r2_artifacts"],
        }
        (self.stage / "remote-source.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    def repair_system(self, source: Path) -> Path:
        if self.remote_source_dir is None:
            raise RuntimeError("remote sources were not prepared")
        system = self.stage / "system_a.img"
        shutil.copyfile(source, system)
        self.run([sys.executable, str(r11.r10.base.TOOLS / "avbtool.py"), "erase_footer", "--image", str(system)])
        work_size = str(self.config["system_work_size"])
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "truncate", "-s", work_size, self.wsl_path(system)])
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "resize2fs", self.wsl_path(system), work_size])
        mount_dir = self.stage / "system-mount"
        mount_dir.mkdir()
        self.run([
            "wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "bash",
            self.wsl_path(REPO / "scripts" / "install-m8-test8r2-remote-stack.sh"),
            self.wsl_path(system), self.wsl_path(mount_dir), self.wsl_path(self.remote_source_dir),
        ])
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "resize2fs", "-M", self.wsl_path(system)])
        mount_dir.rmdir()

        avb = self.config["avb"]
        assert isinstance(avb, dict)
        self.run([
            sys.executable, str(r11.r10.base.TOOLS / "avbtool.py"), "add_hashtree_footer",
            "--image", str(system), "--partition_name", "system",
            "--partition_size", str(avb["partition_size"]), "--hash_algorithm", "sha256",
            "--salt", str(avb["salt"]), "--do_not_generate_fec",
            "--prop", "com.ubox10.candidate.id:" + self.candidate_id,
            "--prop", "com.ubox10.avb.fec:none", "--key", str(REPO / str(avb["key_relative"])),
            "--algorithm", "SHA256_RSA2048",
        ])
        if system.stat().st_size != avb["partition_size"]:
            raise RuntimeError("signed r12 system_a size mismatch")
        return system

    def validate_system_diff(self, before_image: Path, after_image: Path) -> dict[str, object]:
        before_path = self.inventory_system(before_image, "r8-system")
        after_path = self.inventory_system(after_image, "r9-system")
        before, after = self._manifest_map(before_path), self._manifest_map(after_path)
        artifacts = self.config["remote_artifacts"]
        assert isinstance(artifacts, list)
        allowed = {str(item["destination_path"]) for item in artifacts if isinstance(item, dict)}
        unexpected = [path for path in sorted(set(before) | set(after)) if path not in allowed and before.get(path) != after.get(path)]
        if unexpected:
            raise RuntimeError("unexpected r12 system filesystem differences: " + ", ".join(unexpected[:16]))

        observed: list[dict[str, object]] = []
        for item in artifacts:
            assert isinstance(item, dict)
            path = str(item["destination_path"])
            expected = {
                "type": "regular", "mode": item["mode"], "uid": item["uid"], "gid": item["gid"],
                "size": item["size"], "sha256": item["sha256"],
            }
            value = after.get(path)
            if value is None or any(value.get(key) != wanted for key, wanted in expected.items()):
                raise RuntimeError("r12 remote artifact metadata mismatch: " + path)
            label = (str(item["selinux"]) + "\0").encode().hex().upper()
            if value.get("xattrs", {}).get("security.selinux") != label:
                raise RuntimeError("r12 remote artifact SELinux mismatch: " + path)
            if path == "/system/lib/libinput.so":
                old = before.get(path)
                if old is None or old.get("sha256") != item["replaces_sha256"]:
                    raise RuntimeError("r11 libinput replacement source mismatch")
            elif before.get(path) is not None:
                raise RuntimeError("r11 unexpectedly contains remote artifact: " + path)
            observed.append({"path": path, **expected, "selinux": item["selinux"]})

        for item in self.config["protected_files"]:
            assert isinstance(item, dict)
            path = str(item["path"])
            if before.get(path) != after.get(path):
                raise RuntimeError("protected r11 file changed: " + path)
            value = after.get(path)
            if value is None or value.get("size") != item["size"] or value.get("sha256") != item["sha256"]:
                raise RuntimeError("protected r11 file identity mismatch: " + path)

        vendor = after.get("/vendor")
        system_vendor = after.get("/system/vendor")
        if vendor is None or vendor.get("type") != "directory":
            raise RuntimeError("canonical /vendor topology changed")
        if system_vendor is None or system_vendor.get("type") != "symlink" or system_vendor.get("target") != "/vendor":
            raise RuntimeError("/system/vendor compatibility link changed")

        result = {
            "base": "m8a-initial-atv-r11",
            "changed_files": observed,
            "unexpected_system_differences": unexpected,
            "projectivy_unchanged": True,
            "r10_compatibility_libraries_unchanged": True,
            "canonical_vendor_topology_preserved": True,
            "policy_files_unchanged": True,
        }
        (self.stage / "remote-validation.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

        launcher = self.config["launcher"]
        assert isinstance(launcher, dict)
        launcher_path = str(launcher["destination_path"])
        launcher_value = after.get(launcher_path)
        if launcher_value is None or launcher_value.get("size") != launcher["size"] or launcher_value.get("sha256") != launcher["sha256"]:
            raise RuntimeError("protected r11 Launcher identity mismatch")
        launcher_report = {
            "base": "m8a-initial-atv-r11",
            "preserved_file": {"path": launcher_path, "size": launcher["size"], "sha256": launcher["sha256"]},
            "manifest": {
                "package": launcher["package"], "activity": launcher["activity"], "exported": True,
                "direct_boot_aware": False, "categories": launcher["categories"],
                "min_sdk": launcher["min_sdk"], "target_sdk": launcher["target_sdk"],
                "tv_feature_required": True, "privileged": False, "shared_user_id": None,
                "required_shared_libraries": [], "optional_shared_libraries": launcher["optional_shared_libraries"],
            },
            "package_manager_scan": {
                "partition": launcher["partition"], "path_class": "system/app", "presigned": True,
                "privapp_allowlist_required": False, "scan_eligible": True,
            },
            "r11_manifest_validation_inherited_by_exact_apk_identity": True,
            "r10_compatibility_libraries_unchanged": True,
            "canonical_vendor_topology_preserved": True,
        }
        (self.stage / "launcher-validation.json").write_text(json.dumps(launcher_report, indent=2) + "\n", encoding="utf-8")
        return result

    @staticmethod
    def _read_ext4_file(auditor, image: Path, path: str) -> bytes:
        source = auditor.RawByteSource(image)
        try:
            ext4 = auditor.Ext4Reader(source)
            return ext4.read_inode_data(ext4.lookup(path.lstrip("/")))
        finally:
            source.close()

    def verify_selinux(self) -> None:
        logical = self.stage / "validation-logical"
        auditor = load_module(AUDITOR, "m8a_r12_policy_auditor")
        contract = self.config["existing_policy_contract"]
        assert isinstance(contract, dict)
        files = {
            "system_ueventd_sha256": (logical / "system_a.img", "/system/etc/ueventd.rc"),
            "plat_file_contexts_sha256": (logical / "system_a.img", "/system/etc/selinux/plat_file_contexts"),
            "vendor_sepolicy_sha256": (logical / "vendor_a.img", "/etc/selinux/vendor_sepolicy.cil"),
            "vendor_file_contexts_sha256": (logical / "vendor_a.img", "/etc/selinux/vendor_file_contexts"),
            "vendor_ueventd_sha256": (logical / "vendor_a.img", "/ueventd.rc"),
        }
        data: dict[str, bytes] = {}
        for key, (image, path) in files.items():
            data[key] = self._read_ext4_file(auditor, image, path)
            if self._sha256(data[key]) != contract[key]:
                raise RuntimeError("existing SELinux/ueventd contract changed: " + path)

        system_ueventd = data["system_ueventd_sha256"].decode("utf-8")
        vendor_policy = data["vendor_sepolicy_sha256"].decode("utf-8")
        vendor_contexts = data["vendor_file_contexts_sha256"].decode("utf-8")
        required = [
            "(type multi_ir)", "(type multi_ir_exec)",
            "(allow multi_ir uhid_device_31_0 (chr_file (ioctl read write open)))",
            "(allow multi_ir input_device_31_0 (chr_file (ioctl read write open)))",
            "(allow multi_ir servicemanager_31_0 (binder (call transfer)))",
            "(allow multi_ir softwinner_service (service_manager (add find)))",
        ]
        if any(value not in vendor_policy for value in required):
            raise RuntimeError("vendor multi_ir policy contract incomplete")
        if "/system/bin/multi_ir      u:object_r:multi_ir_exec:s0" not in vendor_contexts:
            raise RuntimeError("multi_ir_exec file_context missing")
        if "/dev/uinput               0660   uhid       uhid" not in system_ueventd:
            raise RuntimeError("/dev/uinput ueventd contract missing")

        shell = self.stage / "validate-r12-sepolicy.sh"
        output_bin = self.stage / "r12-sepolicy.bin"
        shell.write_text(
            "#!/usr/bin/env bash\nset -euo pipefail\n"
            f"system='{self.wsl_path(logical / 'system_a.img')}'\n"
            f"vendor='{self.wsl_path(logical / 'vendor_a.img')}'\n"
            f"product='{self.wsl_path(logical / 'product_a.img')}'\n"
            f"base='{self.wsl_path(self.stage / 'policy-mounts')}'\n"
            "mkdir -p \"$base/system\" \"$base/vendor\" \"$base/product\"\n"
            "cleanup(){ for p in \"$base/vendor\" \"$base/product\" \"$base/system\"; do mountpoint -q \"$p\" && umount \"$p\" || true; done; }\n"
            "trap cleanup EXIT INT TERM\n"
            "mount -o loop,ro \"$system\" \"$base/system\"\n"
            "mount -o loop,ro \"$vendor\" \"$base/vendor\"\n"
            "mount -o loop,ro \"$product\" \"$base/product\"\n"
            "args=(\n"
            "  \"$base/system/system/etc/selinux/plat_sepolicy.cil\" -m -M true -G -N -c 30\n"
            "  \"$base/system/system/etc/selinux/mapping/31.0.cil\"\n"
            f"  -o '{self.wsl_path(output_bin)}' -f /dev/null\n"
            "  \"$base/system/system_ext/etc/selinux/system_ext_sepolicy.cil\"\n"
            "  \"$base/system/system_ext/etc/selinux/mapping/31.0.cil\"\n"
            "  \"$base/vendor/etc/selinux/plat_pub_versioned.cil\"\n"
            "  \"$base/vendor/etc/selinux/vendor_sepolicy.cil\"\n"
            ")\n"
            "odm=\"$base/vendor/odm/etc/selinux/odm_sepolicy.cil\"\n"
            "[[ ! -f $odm ]] || args+=(\"$odm\")\n"
            "/home/tianyi/ubox10-aosp/out/host/linux-x86/bin/secilc \"${args[@]}\"\n",
            encoding="utf-8", newline="\n",
        )
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "bash", self.wsl_path(shell)], output=self.stage / "selinux-compile.txt")
        compiled = r11.r10.base.record(output_bin)
        output_bin.unlink()
        shell.unlink()
        mounts = self.stage / "policy-mounts"
        if mounts.exists():
            for item in mounts.iterdir():
                item.rmdir()
            mounts.rmdir()
        report = {
            "existing_policy_files_unchanged": True,
            "multi_ir_domain": "u:r:multi_ir:s0",
            "multi_ir_exec": "u:object_r:multi_ir_exec:s0",
            "uinput": {"path": "/dev/uinput", "mode": "0660", "owner": "uhid:uhid", "selinux": "u:object_r:uhid_device:s0"},
            "input_device_access": True,
            "binder_and_service_manager_access": True,
            "split_policy_compile": {"passed": True, "bytes": compiled["size"], "sha256": compiled["sha256"]},
        }
        (self.stage / "selinux-validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    def validate_elf(self) -> None:
        r11.r10.BuildR10.validate_elf(self)
        with (self.stage / "elf-inventory.csv").open("r", encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        available = {Path(row["path"].split("!", 1)[0]).name for row in rows}
        available.update(row["soname"] for row in rows if row["soname"])

        launcher = self.config["launcher"]
        assert isinstance(launcher, dict)
        launcher_prefix = str(launcher["destination_path"]) + "!/lib/armeabi-v7a/"
        launcher_native = []
        for name in launcher["native_arm32_libraries"]:
            row = next((value for value in rows if value["path"] == launcher_prefix + str(name)), None)
            if row is None or row["class"] != "ELF32" or row["machine"] != "ARM":
                raise RuntimeError("missing ARM32 Projectivy native library: " + str(name))
            needed = [value for value in row["needed"].split(";") if value]
            missing = [value for value in needed if value not in available]
            if missing:
                raise RuntimeError("unresolved Projectivy native dependency: " + str(name) + " -> " + ",".join(missing))
            launcher_native.append({"name": name, "class": row["class"], "machine": row["machine"], "needed": needed, "missing": missing})
        launcher_path = self.stage / "launcher-validation.json"
        launcher_report = json.loads(launcher_path.read_text(encoding="utf-8"))
        launcher_report["native_arm32"] = launcher_native
        launcher_report["native_dependencies_resolved"] = True
        launcher_path.write_text(json.dumps(launcher_report, indent=2) + "\n", encoding="utf-8")

        targets: dict[str, object] = {}
        for item in self.config["remote_artifacts"]:
            assert isinstance(item, dict)
            if not item["elf"]:
                continue
            path = str(item["destination_path"])
            row = next((value for value in rows if value["path"] == path), None)
            if row is None or row["class"] != "ELF32" or row["machine"] != "ARM":
                raise RuntimeError("missing ARM32 remote ELF: " + path)
            if item.get("soname") and row["soname"] != item["soname"]:
                raise RuntimeError("remote ELF SONAME mismatch: " + path)
            needed = [name for name in row["needed"].split(";") if name]
            missing = [name for name in needed if name not in available]
            if missing:
                raise RuntimeError("unresolved remote ELF dependency: " + path + " -> " + ",".join(missing))
            targets[path] = {
                "class": row["class"], "machine": row["machine"], "soname": row["soname"],
                "needed": needed, "missing": missing, "build_id": item.get("build_id"),
            }
        multi = targets.get("/system/bin/multi_ir", {})
        if "libmultiirservice.so" not in multi.get("needed", []):
            raise RuntimeError("multi_ir no longer depends on libmultiirservice")
        if "libmultiir_jni.so" in multi.get("needed", []):
            raise RuntimeError("unexpected multi_ir JNI dependency")
        report = {
            "targets": targets,
            "system_linker_search_path": "/system/lib",
            "all_dt_needed_resolved": True,
            "libinput_compatibility": {
                "r11_sha256": "D82DBA765CAB4CA6BE42DBE8B6673FF34D97B80CD56D461A89468156CAF9FFC2",
                "test8r2_sha256": "764069A044E639A5567803FE530602A525FC66857413C6BC0E4C515040B1F557",
                "same_soname": True,
                "same_dt_needed": True,
                "same_undefined_symbol_set_sha256": "14EAEA9006F7FC198E166542415A85AD6429C852E3C4170EC831CF7CCB9A0341",
            },
        }
        (self.stage / "remote-elf-validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    def finish(self, firmware: Path, super_image: Path, vbmeta_system: Path) -> None:
        assert self.reference_remote is not None and self.reference_remote_before is not None
        if r11.r10.base.record(self.reference_remote) != self.reference_remote_before:
            raise RuntimeError("protected Test8r2 remote reference changed")
        source_path = self.stage / "remote-source.json"
        source_report = json.loads(source_path.read_text(encoding="utf-8"))
        source_report["reference_super"]["path"] = str(self.reference_remote) + "#super.fex"
        source_path.write_text(json.dumps(source_report, indent=2) + "\n", encoding="utf-8")
        shutil.rmtree(self.stage / "test8r2-remote-source")
        shutil.rmtree(self.stage / "test8r2-remote-files")
        super().finish(firmware, super_image, vbmeta_system)

        result_path = self.final / "build-result.json"
        result = json.loads(result_path.read_text(encoding="utf-8"))
        result["repair"] = "Restore the exact Test8r2 Allwinner multi_ir-to-uinput stack required by the ff40 remote, including DPAD and mouse mode."
        result["remote_source"] = json.loads((self.final / "remote-source.json").read_text(encoding="utf-8"))
        result["remote_validation"] = json.loads((self.final / "remote-validation.json").read_text(encoding="utf-8"))
        result["remote_elf_validation"] = json.loads((self.final / "remote-elf-validation.json").read_text(encoding="utf-8"))
        result["selinux_validation"] = json.loads((self.final / "selinux-validation.json").read_text(encoding="utf-8"))
        result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        sums = [
            r11.r10.base.digest(path) + "  " + path.name
            for path in sorted(self.final.iterdir()) if path.is_file() and path.name != "SHA256SUMS"
        ]
        (self.final / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")

    def build(self) -> None:
        started = time.time()
        try:
            self.setup()
            source_super, raw_super, source_system, _old_vbmeta = self.extract_r8()
            system = self.repair_system(source_system)
            vbmeta_system = self.make_vbmeta_system(system)
            super_image = self.make_super(raw_super, system)
            validated_system = self.validate_super(source_super, super_image, source_system)
            self.verify_avb(validated_system, vbmeta_system)
            self.verify_filesystems()
            self.verify_selinux()
            self.validate_elf()
            firmware = self.pack(super_image, vbmeta_system)
            self.finish(firmware, super_image, vbmeta_system)
            print("SUCCESS: " + str(self.final) + " in %.1fs" % (time.time() - started))
        except Exception:
            if self.stage.exists() and not self.keep_failed:
                shutil.rmtree(self.stage)
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--keep-failed", action="store_true")
    args = parser.parse_args()
    BuildR12(json.loads(args.config.read_text(encoding="utf-8")), args.keep_failed).build()


if __name__ == "__main__":
    main()
