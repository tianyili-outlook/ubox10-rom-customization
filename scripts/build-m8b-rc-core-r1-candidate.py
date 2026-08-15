#!/usr/bin/env python3
"""Build an M8B native rc-core candidate from the accepted r13 baseline."""
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
R13_BUILDER = REPO / "scripts" / "build-m8a-r13-candidate.py"
R13_CONFIG = REPO / "configs" / "candidates" / "m8a-initial-atv-r13.json"
DEFAULT_CONFIG = REPO / "configs" / "candidates" / "m8b-rc-core-r1.json"
R1_CONFIG = DEFAULT_CONFIG
AUDITOR = REPO / "scripts" / "audit-logical-system-init.py"
MKBOOTIMG = "/home/tianyi/ubox10-aosp/system/tools/mkbootimg/mkbootimg.py"
UNPACK_BOOTIMG = "/home/tianyi/ubox10-aosp/system/tools/mkbootimg/unpack_bootimg.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load module: " + str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


r13 = load_module(R13_BUILDER, "m8a_r13_for_m8b")
base = r13.r12.r11.r10.base


class BuildM8BRcCoreR1(r13.BuildR13):
    def __init__(self, config: dict[str, object], keep_failed: bool) -> None:
        super().__init__(config, keep_failed)
        self.stock_boot: Path | None = None
        self.stock_kernel: Path | None = None
        self.stock_ramdisk: Path | None = None
        self.candidate_boot: Path | None = None
        self.generated_keymap_c: Path | None = None
        self.generated_kl: Path | None = None
        self.device_keylayout_kl: Path | None = None
        self.keylayout_parser_report: Path | None = None
        self.mapping_report: dict[str, object] | None = None

    @staticmethod
    def _hash_bytes(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest().upper()

    def setup(self) -> None:
        base.BuildR9.setup(self)
        for key in ("mapping", "disabled_multi_ir_rc"):
            spec = self.config[key]
            assert isinstance(spec, dict)
            path = REPO / str(spec["relative"])
            if not path.is_file() or base.digest(path) != spec["sha256"]:
                raise RuntimeError("M8B source identity mismatch: " + str(path))
        patch = self.config.get("kernel_repeat_patch")
        if patch is not None:
            assert isinstance(patch, dict)
            path = REPO / str(patch["relative"])
            if not path.is_file() or base.digest(path) != patch["sha256"]:
                raise RuntimeError("M8B kernel patch identity mismatch: " + str(path))

    def extract_r8(self) -> tuple[Path, Path, Path, Path]:
        result = base.BuildR9.extract_r8(self)
        outer = self.stage / "r8-outer"
        for name in ("boot.fex", "vendor_boot.fex"):
            self.run([sys.executable, str(base.TOOLS / "sunxi_image_tool.py"), "extract", "-o", str(outer), "-f", name, str(self.base)])
        kernel = self.config["kernel"]
        boot_identity = self.config.get("base_boot", kernel)
        protected = self.config["protected_contract"]
        assert isinstance(kernel, dict) and isinstance(boot_identity, dict) and isinstance(protected, dict)
        self.stock_boot = outer / "boot.fex"
        vendor_boot = outer / "vendor_boot.fex"
        if base.record(self.stock_boot)["size"] != boot_identity["boot_size"] or base.digest(self.stock_boot) != boot_identity["boot_sha256"]:
            raise RuntimeError("M8B base boot identity mismatch")
        if vendor_boot.stat().st_size != protected["vendor_boot_size"] or base.digest(vendor_boot) != protected["vendor_boot_sha256"]:
            raise RuntimeError("r13 vendor_boot identity mismatch")

        unpacked = self.stage / "boot-unpacked"
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "--", "python3", UNPACK_BOOTIMG,
                  "--boot_img", self.wsl_path(self.stock_boot), "--out", self.wsl_path(unpacked), "--format=mkbootimg"],
                 output=self.stage / "boot-mkbootimg-args.txt")
        self.stock_kernel, self.stock_ramdisk = unpacked / "kernel", unpacked / "ramdisk"
        if self.stock_kernel.stat().st_size != boot_identity["kernel_size"] or base.digest(self.stock_kernel) != boot_identity["kernel_sha256"]:
            raise RuntimeError("M8B base kernel identity mismatch")
        if self.stock_ramdisk.stat().st_size != boot_identity["ramdisk_size"] or base.digest(self.stock_ramdisk) != boot_identity["ramdisk_sha256"]:
            raise RuntimeError("M8B base boot ramdisk identity mismatch")
        return result

    def generate_inputs(self, source_system: Path) -> None:
        auditor = load_module(AUDITOR, "m8b_rc_map_source_auditor")
        customer = self.stage / "customer_ir_ff40.kl"
        customer.write_bytes(self._read_ext4_file(auditor, source_system, "/system/usr/keylayout/customer_ir_ff40.kl"))
        generated = self.stage / "generated-input"
        generated.mkdir()
        self.generated_keymap_c = generated / "rc-sunxi-keymaps.c"
        self.generated_kl = generated / "sunxi-ir.kl"
        report = self.stage / "ff40-map-report.json"
        mapping = self.config["mapping"]
        assert isinstance(mapping, dict)
        self.run([
            sys.executable, str(REPO / "scripts" / "generate-m8b-rc-core-input.py"),
            "--map", str(REPO / str(mapping["relative"])), "--customer", str(customer),
            "--c-output", str(self.generated_keymap_c), "--kl-output", str(self.generated_kl), "--report", str(report),
        ])
        self.mapping_report = json.loads(report.read_text(encoding="utf-8"))
        if self.mapping_report["audited_entries"] != mapping["entries"] or self.mapping_report["native_rc_entries"] != mapping["native_entries"]:
            raise RuntimeError("generated ff40 mapping count mismatch")
        self.device_keylayout_kl = self.generated_kl
        parser_spec = self.config.get("android_keylayout_parser")
        if parser_spec is not None:
            assert isinstance(parser_spec, dict)
            self.device_keylayout_kl = generated / "android12-device.kl"
            self.keylayout_parser_report = self.stage / "keylayout-parser-validation.json"
            self.run([
                "wsl.exe", "-d", "Ubuntu-24.04", "--", "python3",
                self.wsl_path(REPO / "scripts" / "convert-m8b-android12-keylayout.py"),
                "--input", self.wsl_path(self.generated_kl), "--output", self.wsl_path(self.device_keylayout_kl),
                "--config", self.wsl_path(REPO / str(parser_spec["config_relative"])),
                "--input-event-labels", str(parser_spec["input_event_labels_path"]),
                "--key-layout-map", str(parser_spec["key_layout_map_path"]),
                "--report", self.wsl_path(self.keylayout_parser_report),
            ])

    def build_kernel(self) -> Path:
        if self.stock_kernel is None or self.generated_keymap_c is None:
            raise RuntimeError("kernel inputs were not prepared")
        output = self.stage / "kernel-build"
        output.mkdir()
        kernel = self.config["kernel"]
        assert isinstance(kernel, dict)
        # Keep the absolute Kbuild source/output path stable. The kernel embeds
        # source paths in several objects, so a staging UUID would make an
        # otherwise identical candidate produce a different Image hash.
        build_id = self.candidate_id
        command = [
            "wsl.exe", "-d", "Ubuntu-24.04", "--", "bash", self.wsl_path(REPO / "scripts" / "build-m8b-rc-core-kernel.sh"),
            self.wsl_path(self.stock_kernel), self.wsl_path(self.generated_keymap_c), self.wsl_path(output),
            build_id, str(kernel["commit"]),
        ]
        patch = self.config.get("kernel_repeat_patch")
        if patch is not None:
            assert isinstance(patch, dict)
            command.append(self.wsl_path(REPO / str(patch["relative"])))
        self.run(command, output=self.stage / "kernel-build.log")
        image = output / "Image"
        if image.stat().st_size != kernel["kernel_size"]:
            raise RuntimeError("M8B kernel size no longer matches r13 boot contract")
        config = (output / "candidate.config").read_text(encoding="utf-8")
        if "# CONFIG_SUNXI_MULTI_IR_SUPPORT is not set" not in config or "CONFIG_SUNXI_KEYMAPPING_SUPPORT=y" in config:
            raise RuntimeError("M8B native rc-core config mismatch")
        return image

    def build_boot(self, image: Path) -> Path:
        if self.stock_ramdisk is None:
            raise RuntimeError("stock boot ramdisk was not prepared")
        kernel = self.config["kernel"]
        assert isinstance(kernel, dict)
        unsigned = self.stage / "boot-unsigned.img"
        self.run([
            "wsl.exe", "-d", "Ubuntu-24.04", "--", "python3", MKBOOTIMG,
            "--header_version", str(kernel["header_version"]), "--os_version", str(kernel["os_version"]),
            "--os_patch_level", str(kernel["os_patch_level"]), "--kernel", self.wsl_path(image),
            "--ramdisk", self.wsl_path(self.stock_ramdisk), "--cmdline", str(kernel["cmdline"]), "--output", self.wsl_path(unsigned),
        ])
        self.run([
            sys.executable, str(base.TOOLS / "avbtool.py"), "add_hash_footer", "--image", str(unsigned),
            "--partition_name", str(kernel["avb_partition_name"]), "--partition_size", str(kernel["avb_partition_size"]),
            "--hash_algorithm", "sha256", "--salt", str(kernel["avb_salt"]),
            "--prop", "com.android.build.boot.fingerprint:" + str(kernel["boot_fingerprint"]),
            "--prop", "com.android.build.boot.os_version:" + str(kernel["boot_os_version_prop"]),
        ])
        self.candidate_boot = self.stage / "boot.fex"
        unsigned.replace(self.candidate_boot)
        if self.candidate_boot.stat().st_size != kernel["boot_size"]:
            raise RuntimeError("signed M8B boot size mismatch")
        self.run([sys.executable, str(base.TOOLS / "avbtool.py"), "info_image", "--image", str(self.candidate_boot)],
                 output=self.stage / "boot-avb-info.txt")

        unpacked = self.stage / "boot-validation-unpacked"
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "--", "python3", UNPACK_BOOTIMG,
                  "--boot_img", self.wsl_path(self.candidate_boot), "--out", self.wsl_path(unpacked), "--format=mkbootimg"],
                 output=self.stage / "boot-validation-mkbootimg-args.txt")
        ramdisk = unpacked / "ramdisk"
        candidate_kernel = unpacked / "kernel"
        if base.digest(ramdisk) != kernel["ramdisk_sha256"] or base.digest(candidate_kernel) != base.digest(image):
            raise RuntimeError("repacked boot kernel/ramdisk identity mismatch")
        component = lambda path: {"size": path.stat().st_size, "sha256": base.digest(path)}
        report = {
            "header_version": kernel["header_version"], "cmdline": kernel["cmdline"],
            "stock_ramdisk_unchanged": True, "stock_ramdisk": component(ramdisk),
            "stock_kernel": component(self.stock_kernel), "candidate_kernel": component(candidate_kernel),
            "candidate_boot": base.record(self.candidate_boot), "vendor_boot_unchanged": True,
            "dts_dtbo_changed": False, "persistent_bootargs_changed": False,
        }
        (self.stage / "boot-validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        shutil.rmtree(unpacked)
        return self.candidate_boot

    def reuse_base_boot(self) -> Path:
        if self.stock_boot is None or self.stock_kernel is None or self.stock_ramdisk is None:
            raise RuntimeError("base boot components were not prepared")
        boot_identity = self.config["base_boot"]
        assert isinstance(boot_identity, dict)
        self.candidate_boot = self.stage / "boot.fex"
        shutil.copyfile(self.stock_boot, self.candidate_boot)
        component = lambda path: {"size": path.stat().st_size, "sha256": base.digest(path)}
        if component(self.candidate_boot) != {"size": boot_identity["boot_size"], "sha256": boot_identity["boot_sha256"]}:
            raise RuntimeError("reused r2 boot identity mismatch")
        kernel_component = component(self.stock_kernel)
        report = {
            "header_version": boot_identity["header_version"], "cmdline": boot_identity["cmdline"],
            "stock_ramdisk_unchanged": True, "stock_ramdisk": component(self.stock_ramdisk),
            "stock_kernel": kernel_component, "candidate_kernel": kernel_component,
            "candidate_boot": base.record(self.candidate_boot), "base_boot_reused_byte_for_byte": True,
            "vendor_boot_unchanged": True, "dts_dtbo_changed": False, "persistent_bootargs_changed": False,
        }
        (self.stage / "boot-validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return self.candidate_boot

    def repair_system(self, source: Path) -> Path:
        assert self.generated_kl is not None and self.device_keylayout_kl is not None
        system = self.stage / "system_a.img"
        shutil.copyfile(source, system)
        self.run([sys.executable, str(base.TOOLS / "avbtool.py"), "erase_footer", "--image", str(system)])
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "truncate", "-s", str(self.config["system_work_size"]), self.wsl_path(system)])
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "resize2fs", self.wsl_path(system), str(self.config["system_work_size"])])
        mount_dir = self.stage / "system-mount"
        mount_dir.mkdir()
        disabled = self.config["disabled_multi_ir_rc"]
        assert isinstance(disabled, dict)
        command = [
            "wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "bash",
            self.wsl_path(REPO / "scripts" / "install-m8b-rc-core-input.sh"), self.wsl_path(system), self.wsl_path(mount_dir),
            self.wsl_path(REPO / str(disabled["relative"])), self.wsl_path(self.generated_kl),
        ]
        device_keylayout_filename = self.config.get("device_keylayout_filename")
        if device_keylayout_filename is not None:
            command.append(str(device_keylayout_filename))
            if self.device_keylayout_kl != self.generated_kl:
                command.append(self.wsl_path(self.device_keylayout_kl))
                base_keylayout_sha256 = self.config.get("base_device_keylayout_sha256")
                if base_keylayout_sha256 is not None:
                    command.append(str(base_keylayout_sha256))
        self.run(command)
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "resize2fs", "-M", self.wsl_path(system)])
        mount_dir.rmdir()
        avb = self.config["avb"]
        assert isinstance(avb, dict)
        self.run([
            sys.executable, str(base.TOOLS / "avbtool.py"), "add_hashtree_footer", "--image", str(system),
            "--partition_name", "system", "--partition_size", str(avb["partition_size"]), "--hash_algorithm", "sha256",
            "--salt", str(avb["salt"]), "--do_not_generate_fec", "--prop", "com.ubox10.candidate.id:" + self.candidate_id,
            "--prop", "com.ubox10.avb.fec:none", "--key", str(REPO / str(avb["key_relative"])), "--algorithm", "SHA256_RSA2048",
        ])
        return system

    def validate_system_diff(self, before_image: Path, after_image: Path) -> dict[str, object]:
        before = self._manifest_map(self.inventory_system(before_image, "r13-system"))
        after = self._manifest_map(self.inventory_system(after_image, "m8b-system"))
        device_keylayout_filename = self.config.get("device_keylayout_filename")
        device_keylayout_path = "/system/usr/keylayout/" + str(device_keylayout_filename) if device_keylayout_filename else None
        allowed = {device_keylayout_path} if device_keylayout_path else {"/system/etc/init/multi_ir.rc", "/system/usr/keylayout/sunxi-ir.kl"}
        changed = [path for path in sorted(set(before) | set(after)) if before.get(path) != after.get(path)]
        unexpected = [path for path in changed if path not in allowed]
        if unexpected or set(changed) != allowed:
            raise RuntimeError("unexpected M8B system differences: " + ", ".join(unexpected or changed))
        assert self.generated_kl is not None and self.device_keylayout_kl is not None
        disabled = REPO / str(self.config["disabled_multi_ir_rc"]["relative"])
        expected_label = b"u:object_r:system_file:s0\0".hex().upper()
        targets = {device_keylayout_path: self.device_keylayout_kl} if device_keylayout_path else {
            "/system/etc/init/multi_ir.rc": disabled, "/system/usr/keylayout/sunxi-ir.kl": self.generated_kl,
        }
        for path, source in targets.items():
            actual = after[path]
            if actual.get("type") != "regular" or actual.get("mode") != "0644" or actual.get("uid") != 0 or actual.get("gid") != 0:
                raise RuntimeError("M8B system target metadata mismatch: " + path)
            if actual.get("sha256") != base.digest(source) or actual.get("xattrs", {}).get("security.selinux") != expected_label:
                raise RuntimeError("M8B system target identity mismatch: " + path)
        legacy = [
            "/system/bin/multi_ir", "/system/usr/keylayout/customer_ir_ff40.kl", "/system/usr/keylayout/sunxi-ir-uinput.kl",
            "/system/lib/libmultiirservice.so", "/system/lib/libinput.so",
        ]
        if any(before.get(path) != after.get(path) for path in legacy):
            raise RuntimeError("legacy rollback artifact changed")
        if device_keylayout_path:
            for path in ("/system/etc/init/multi_ir.rc", "/system/usr/keylayout/sunxi-ir.kl"):
                if before.get(path) != after.get(path):
                    raise RuntimeError("r2 native input file changed: " + path)
            expected_identical = base.digest(self.device_keylayout_kl) == base.digest(self.generated_kl)
            observed_identical = after[device_keylayout_path]["sha256"] == after["/system/usr/keylayout/sunxi-ir.kl"]["sha256"]
            if observed_identical != expected_identical:
                raise RuntimeError("device-specific keylayout compatibility identity mismatch")
        for item in self.config["frozen_files"]:
            path = str(item["path"])
            if path in allowed:
                continue
            if before.get(path) != after.get(path):
                raise RuntimeError("r13 golden component changed: " + path)
        rc_text = disabled.read_text(encoding="utf-8")
        kl_text = self.generated_kl.read_text(encoding="utf-8")
        if "\n        disabled\n" not in rc_text or "MOUSE" in kl_text or "sunxi-ir-uinput" in kl_text:
            raise RuntimeError("native runtime isolation contract mismatch")
        vendor = after.get("/vendor")
        system_vendor = after.get("/system/vendor")
        if vendor is None or vendor.get("type") != "directory" or system_vendor is None or system_vendor.get("target") != "/vendor":
            raise RuntimeError("r13 canonical /vendor topology changed")
        launcher = self.config["launcher"]
        assert isinstance(launcher, dict)
        launcher_report = {
            "preserved_file": next(item for item in self.config["frozen_files"] if item["path"] == launcher["destination_path"]),
            "r13_hardware_accepted_home_preserved": True,
        }
        (self.stage / "launcher-validation.json").write_text(json.dumps(launcher_report, indent=2) + "\n", encoding="utf-8")
        result = {
            "base": "m8a-initial-atv-r13 (GOLDEN BASELINE)", "changed_system_files": sorted(allowed),
            "unexpected_system_differences": unexpected, "physical_input_device": "sunxi-ir",
            "multi_ir_init_state": "disabled", "uinput_runtime_dependency": False,
            "legacy_artifacts_retained_inert": legacy, "mouse_mode": "intentionally dropped/inert",
            "projectivy_provisioning_power_policy_frozen": True, "canonical_vendor_topology_preserved": True,
            "device_keylayout_path": device_keylayout_path,
            "device_keylayout_identical_to_sunxi_ir": bool(device_keylayout_path and base.digest(self.device_keylayout_kl) == base.digest(self.generated_kl)),
        }
        (self.stage / "native-input-validation.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return result

    def pack(self, super_image: Path, vbmeta_system: Path) -> Path:
        if self.candidate_boot is None:
            raise RuntimeError("candidate boot was not built")
        firmware = self.stage / ("x12-" + self.candidate_id + ".img")
        audit = self.stage / "outer-payload-audit.json"
        command = [
            sys.executable, str(base.TOOLS / "pack_image_preserving.py"), "--source", str(self.base), "--output", str(firmware),
        ]
        if not self.config.get("reuse_base_boot"):
            command.extend(["--replace", "boot.fex=" + str(self.candidate_boot)])
        command.extend([
            "--replace", "super.fex=" + str(super_image), "--replace", "vbmeta_system.fex=" + str(vbmeta_system),
            "--audit", str(audit),
        ])
        self.run(command)
        self.run([sys.executable, str(base.TOOLS / "sunxi_image_tool.py"), "verify", str(firmware)])
        actions = {item["filename"]: item["action"] for item in json.loads(audit.read_text(encoding="utf-8"))["payloads"]}
        container = self.config["container"]
        assert isinstance(container, dict)
        if len(actions) != container["total_entries"] or sum(value == "preserved" for value in actions.values()) != container["preserved_entries"]:
            raise RuntimeError("outer preservation count mismatch")
        for name in container["replacements"]:
            if actions.get(name) != "replacement":
                raise RuntimeError("missing outer replacement: " + str(name))
        for name in container["companions"]:
            if actions.get(name) != "companion":
                raise RuntimeError("missing outer companion: " + str(name))
            self.run([sys.executable, str(base.TOOLS / "sunxi_image_tool.py"), "extract", "-o", str(self.stage), "-f", str(name), str(firmware)])
        return firmware

    def finish(self, firmware: Path, super_image: Path, vbmeta_system: Path) -> None:
        if base.record(self.base) != self.before:
            raise RuntimeError("protected r13 golden candidate changed")
        assert self.candidate_boot is not None
        (self.stage / "input-provenance-after.json").write_text(json.dumps({"base_candidate": base.record(self.base)}, indent=2) + "\n", encoding="utf-8")
        logical_before = {name: {"partition": name, "container": str(self.base) + "#super.fex", "size": value["size"], "sha256": value["sha256"]} for name, value in self.logical_before.items()}
        logical_after = {name: {"partition": name, "container": str(super_image), "size": value["size"], "sha256": value["sha256"]} for name, value in self.logical_after.items()}
        result = {
            "id": self.candidate_id, "status": "OFFLINE CHECKED", "firmware": base.record(firmware),
            "base_candidate": base.record(self.base), "boot": base.record(self.candidate_boot),
            "system_a": logical_after["system_a"], "super": base.record(super_image), "vbmeta_system": base.record(vbmeta_system),
            "derived_checks": {name: base.record(self.stage / name) for name in self.config["container"]["companions"]},
            "logical_before": logical_before, "logical_after": logical_after,
            "repair": str(self.config.get("repair", "Replace the Allwinner MSC-only compatibility path with the existing native rc-core key lifecycle and exact ff40 semantics; keep legacy multi_ir artifacts inert.")),
            "payload_delta": (["system_a", "super.fex", "Vsuper.fex", "vbmeta_system.fex", "Vvbmeta_system.fex"]
                              if self.config.get("reuse_base_boot") else
                              ["boot/kernel", "boot.fex", "Vboot.fex", "system_a", "super.fex", "Vsuper.fex", "vbmeta_system.fex", "Vvbmeta_system.fex"]),
            "mapping": self.mapping_report, "boot_validation": json.loads((self.stage / "boot-validation.json").read_text(encoding="utf-8")),
            "native_input_validation": json.loads((self.stage / "native-input-validation.json").read_text(encoding="utf-8")),
            "protected_contract": self.config["protected_contract"],
            "kernel_repeat_patch": self.config.get("kernel_repeat_patch"),
            "keylayout_parser_validation": (json.loads(self.keylayout_parser_report.read_text(encoding="utf-8"))
                                            if self.keylayout_parser_report is not None else None),
            "physical_device_actions_performed": False,
        }
        (self.stage / "build-result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        for directory in ("r8-logical", "validation-logical", "r8-outer", "boot-unpacked"):
            shutil.rmtree(self.stage / directory)
        shutil.rmtree(self.stage / "avb-validation")
        for name in ("r8-super.raw.img", "validation-super.raw.img", "system_a.img", "r13-system-filesystem-manifest.json", "m8b-system-filesystem-manifest.json", "customer_ir_ff40.kl"):
            (self.stage / name).unlink()
        kernel_image = self.stage / "kernel-build" / "Image"
        if kernel_image.exists():
            kernel_image.unlink()
        rewrite_names = ["build-result.json", "outer-payload-audit.json", "input-provenance-before.json", "input-provenance-after.json", "boot-validation.json"]
        if self.keylayout_parser_report is not None:
            rewrite_names.append("keylayout-parser-validation.json")
        for name in rewrite_names:
            path = self.stage / name
            path.write_text(json.dumps(base.rewrite_paths(json.loads(path.read_text(encoding="utf-8")), self.stage, self.final), indent=2) + "\n", encoding="utf-8")
        sums = [base.digest(path) + "  " + path.relative_to(self.stage).as_posix() for path in sorted(self.stage.rglob("*")) if path.is_file() and path.name != "SHA256SUMS"]
        (self.stage / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
        os.replace(self.stage, self.final)

    def build(self) -> None:
        started = time.time()
        try:
            self.setup()
            source_super, raw_super, source_system, _old_vbmeta = self.extract_r8()
            self.generate_inputs(source_system)
            if self.config.get("reuse_base_boot"):
                self.reuse_base_boot()
            else:
                kernel_image = self.build_kernel()
                self.build_boot(kernel_image)
            system = self.repair_system(source_system)
            vbmeta_system = self.make_vbmeta_system(system)
            super_image = self.make_super(raw_super, system)
            validated_system = self.validate_super(source_super, super_image, source_system)
            self.verify_avb(validated_system, vbmeta_system)
            self.verify_filesystems()
            self.verify_selinux()
            r13.r12.BuildR12.validate_elf(self)
            firmware = self.pack(super_image, vbmeta_system)
            self.finish(firmware, super_image, vbmeta_system)
            print("SUCCESS: " + str(self.final) + " in %.1fs" % (time.time() - started))
        except Exception:
            if self.stage.exists() and not self.keep_failed:
                shutil.rmtree(self.stage)
            raise


def load_overlay(path: Path, stack: tuple[Path, ...] = ()) -> dict[str, object]:
    resolved = path.resolve()
    if resolved in stack:
        raise RuntimeError("candidate config parent cycle")
    document = json.loads(resolved.read_text(encoding="utf-8"))
    parent = document.get("parent_config_relative")
    if parent is None:
        return document
    result = load_overlay(REPO / str(parent), stack + (resolved,))
    result.update(document)
    return result


def merged_config(path: Path) -> dict[str, object]:
    document = json.loads(R13_CONFIG.read_text(encoding="utf-8"))
    document.update(json.loads(R1_CONFIG.read_text(encoding="utf-8")))
    if path.resolve() != R1_CONFIG.resolve():
        document.update(load_overlay(path))
    return document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--keep-failed", action="store_true")
    args = parser.parse_args()
    BuildM8BRcCoreR1(merged_config(args.config), args.keep_failed).build()


if __name__ == "__main__":
    main()
