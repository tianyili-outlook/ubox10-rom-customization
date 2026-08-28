#!/usr/bin/env python3
"""Build B r5 by correcting only the normal-boot product property source."""
from __future__ import annotations

import argparse
import difflib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time


REPO = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO / "configs/candidates/a16-prototype-b-r5.json"
DEFAULT_AOSP = Path("/work/src/ubox10-a16-ceiling")

R3_PATH = REPO / "scripts/build-a16-prototype-b-r3-candidate.py"
R3_SPEC = importlib.util.spec_from_file_location("a16_b_r3_builder_for_r5", R3_PATH)
if R3_SPEC is None or R3_SPEC.loader is None:
    raise RuntimeError(f"cannot import r3 builder: {R3_PATH}")
R3 = importlib.util.module_from_spec(R3_SPEC)
sys.modules[R3_SPEC.name] = R3
R3_SPEC.loader.exec_module(R3)

CHECK_PATH = REPO / "scripts/check-a16-prototype-b-runtime-product-source.py"
CHECK_SPEC = importlib.util.spec_from_file_location("a16_b_runtime_product_check", CHECK_PATH)
if CHECK_SPEC is None or CHECK_SPEC.loader is None:
    raise RuntimeError(f"cannot import runtime product checker: {CHECK_PATH}")
CHECK = importlib.util.module_from_spec(CHECK_SPEC)
sys.modules[CHECK_SPEC.name] = CHECK
CHECK_SPEC.loader.exec_module(CHECK)


class Builder(R3.Builder):
    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__(args)
        contract = self.raw_cfg["active_product_property_contract"]
        relative = str(contract["source_relative"])
        source_input = self.cfg["tracked_source_inputs"].get(relative)
        if source_input is None or source_input["aosp_relative"] != contract["aosp_relative"]:
            raise RuntimeError("shared B1 product input path contract changed")
        # r4 added the already-audited PRODUCT_PRODUCT_PROPERTIES source after
        # B1. Preserve every other shared B1 input hash and replace only this
        # one stale r1 hash with r5's explicit source identity.
        source_input["sha256"] = contract["source_sha256"]

    def setup(self) -> None:
        if self.final.exists():
            raise RuntimeError(f"refusing to overwrite existing candidate: {self.final}")
        if self.raw_cfg["status"] != "ROOT_CAUSE_PROVEN_SINGLE_CAUSE_R5_AUTHORIZED":
            raise RuntimeError("r5 active-source correction is not authorized")
        R3.R2.R1.Builder.setup(self)
        self.require(self.base, self.raw_cfg["base_candidate"], "immutable failed r4 outer")
        for name, spec in self.raw_cfg["base_artifacts"].items():
            self.require(R3.source(str(spec["path"])), spec, f"r5 assembly control {name}")

        audit = json.loads(
            (REPO / self.raw_cfg["root_cause"]["audit"]).read_text(encoding="utf-8")
        )
        if (
            audit["result"]
            != "PROVEN_PATCHED_INACTIVE_LOGICAL_PRODUCT_A_RUNTIME_SOURCE_IS_EMBEDDED_SYSTEM_PRODUCT"
            or audit["r5_decision"]["authorized"] is not True
        ):
            raise RuntimeError("r5 root-cause audit is not uniquely closed")
        contract = self.raw_cfg["active_product_property_contract"]
        tracked = REPO / contract["source_relative"]
        installed = self.args.aosp / contract["aosp_relative"]
        for path in (tracked, installed):
            if R3.digest(path) != contract["source_sha256"]:
                raise RuntimeError(f"r5 product source identity mismatch: {path}")
        manifest = subprocess_check(
            ["git", "-C", str(self.args.aosp / ".repo/manifests"), "rev-parse", "HEAD"]
        ).strip()
        if manifest != "ebea28d151539ecf0730b1a4ab92ac33edc17ac9":
            raise RuntimeError(f"exact r7 manifest changed: {manifest}")

    def prepare_system(self) -> tuple[Path, dict[str, object]]:
        spec = self.raw_cfg["base_artifacts"]["system_a"]
        original = R3.source(str(spec["path"]))
        system = self.stage / "system_a.img"
        shutil.copyfile(original, system)
        contract = self.raw_cfg["active_product_property_contract"]

        root = self.debugfs(system, "stat /product", capture=True)
        if "Type: symlink" not in root or 'Fast link dest: "/system/product"' not in root:
            raise RuntimeError("assembly control is not the proven embedded-product root layout")
        for path, expected in (
            ("/metadata", self.raw_cfg["root_mountpoint_contract"]["metadata"]),
            ("/vendor", self.raw_cfg["root_mountpoint_contract"]["vendor"]),
        ):
            inode = self.debugfs(system, f"stat {path}", capture=True)
            attrs = self.debugfs(system, f"ea_list {path}", capture=True)
            if (
                "Type: directory" not in inode
                or f'Mode:  {expected["mode"]}' not in inode
                or expected["selinux"] not in attrs
            ):
                raise RuntimeError(f"physically crossed root contract changed: {path}")

        self.run([sys.executable, str(self.avbtool), "erase_footer", "--image", str(system)])
        avb = self.cfg["avb"]["system"]
        if system.stat().st_size != avb["original_filesystem_size"]:
            raise RuntimeError("r3/r4 system AVB original size changed")
        self.run(["e2fsck", "-fn", str(system)])

        before_file = self.stage / "active-product-build.prop.r4"
        after_file = self.stage / "active-product-build.prop.r5"
        self.debugfs(system, f'dump -p {contract["active_path"]} {before_file}')
        if (
            before_file.stat().st_size != contract["base_size"]
            or R3.digest(before_file) != contract["base_sha256"]
        ):
            raise RuntimeError("r4 runtime-active embedded product property source changed")
        before = before_file.read_text(encoding="utf-8")
        if any(re.search(rf"^{re.escape(key)}=", before, re.MULTILINE) for key in CHECK.ABI_KEYS):
            raise RuntimeError("r4 active source unexpectedly already contains the ABI triplet")

        variables, dumpvars_text = CHECK.run_dumpvars(self.args.aosp)
        (self.stage / "final-build-variables.txt").write_text(
            dumpvars_text, encoding="utf-8"
        )
        expected = CHECK.expected_from_build_variables(contract, variables)
        if variables["TARGET_COPY_OUT_PRODUCT"] != contract["target_copy_out_product"]:
            raise RuntimeError("final build no longer embeds product content in system/product")
        generated = Path(contract["generated_path"])
        generated_props = CHECK.parse_properties(generated.read_text(encoding="utf-8"))
        if {key: generated_props.get(key) for key in CHECK.ABI_KEYS} != expected:
            raise RuntimeError("source-generated product properties diverge from final variables")

        additions = [f"{key}={expected[key]}" for key in CHECK.ABI_KEYS]
        marker = "# end of file\n"
        if before.count(marker) != 1:
            raise RuntimeError("active product build.prop end marker changed")
        after = before.replace(marker, "\n".join(additions) + "\n" + marker, 1)
        after_file.write_text(after, encoding="utf-8", newline="\n")
        delta = list(difflib.unified_diff(before.splitlines(), after.splitlines(), lineterm=""))
        added = [line[1:] for line in delta if line.startswith("+") and not line.startswith("+++")]
        removed = [line[1:] for line in delta if line.startswith("-") and not line.startswith("---")]
        if added != additions or removed:
            raise RuntimeError(f"r5 active build.prop delta expanded: added={added}, removed={removed}")

        previous_fake_time = os.environ.get("E2FSPROGS_FAKE_TIME")
        os.environ["E2FSPROGS_FAKE_TIME"] = str(int("6a8ffae9", 16))
        try:
            self.debugfs(system, f'rm {contract["active_path"]}')
            self.debugfs(system, f'write {after_file} {contract["active_path"]}')
            for field, value in (
                ("mode", "0100644"), ("uid", "0"), ("gid", "0"),
                ("ctime", "0x6a8ffadc"), ("atime", "0x6a8ffadc"),
                ("mtime", "0x6a8ffadc"), ("crtime", "0x6a8ffae9"),
            ):
                self.debugfs(system, f'set_inode_field {contract["active_path"]} {field} {value}')
            self.debugfs(
                system,
                f'ea_set {contract["active_path"]} security.selinux '
                '"u:object_r:system_file:s0\\000"',
            )
            self.run(["e2fsck", "-fy", str(system)], allowed={0, 1})
        finally:
            if previous_fake_time is None:
                os.environ.pop("E2FSPROGS_FAKE_TIME", None)
            else:
                os.environ["E2FSPROGS_FAKE_TIME"] = previous_fake_time
        self.run(["e2fsck", "-fn", str(system)])

        installed = CHECK.parse_properties(
            self.debugfs(system, f'cat {contract["active_path"]}', capture=True)
        )
        if {key: installed.get(key) for key in CHECK.ABI_KEYS} != expected:
            raise RuntimeError("installed active product ABI triplet changed")
        inode = self.debugfs(system, f'stat {contract["active_path"]}', capture=True)
        attrs = self.debugfs(system, f'ea_list {contract["active_path"]}', capture=True)
        if (
            "Mode:  0644" not in inode or "User:     0   Group:     0" not in inode
            or "u:object_r:system_file:s0" not in attrs
        ):
            raise RuntimeError("active product build.prop inode contract changed")

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
            raise RuntimeError("r5 signed system size mismatch")
        self.verify_avb_partition(system, "system", avb["key_relative"])

        inactive = R3.source(str(self.raw_cfg["base_artifacts"]["product_a"]))
        active_audit = CHECK.audit(
            self.args.config, self.args.aosp, system, inactive, dumpvars_text
        )
        (self.stage / "runtime-product-source-audit.json").write_text(
            json.dumps(active_audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return system, {
            "base_r3_r4": R3.record(original),
            "candidate": R3.record(system),
            "filesystem_bytes_before_avb": avb["original_filesystem_size"],
            "tree_delta": {"added": [], "removed": [], "changed": ["system/product/etc/build.prop"]},
            "property_before_sha256": R3.digest(before_file),
            "property_after_sha256": R3.digest(after_file),
            "property_lines_added": additions,
            "active_runtime_source": contract["active_path"],
            "runtime_alias": "/product/etc/build.prop",
            "root_product_symlink": "/product -> /system/product",
            "final_build_variables": variables,
            "runtime_source_guard": active_audit["result"],
            "ext4": "PASS",
            "avb_hashtree_no_fec": "PASS",
            "all_other_b1_system_semantics_expected_preserved": True,
        }

    def finish(
        self, firmware: Path, system_audit: dict[str, object],
        vendor_audit: dict[str, object], super_audit: dict[str, object],
        outer_audit: dict[str, object], vbmeta_system: Path, vbmeta_vendor: Path,
    ) -> None:
        for name, key in (("boot.fex", "boot"), ("vendor_dlkm_a.img", "vendor_dlkm")):
            shutil.copyfile(R3.source(str(self.raw_cfg["base_artifacts"][key]["path"])), self.stage / name)
        product = R3.source(str(self.raw_cfg["base_artifacts"]["product_a"]["path"]))
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
                "build_number": "UBOX10_A16_QPR0_B5",
                "lunch": self.cfg["android16"]["lunch"],
                "android_system_rebuilt": False,
                "product_build_prop_regenerated": True,
            },
            "base_r4": R3.record(self.base),
            "assembly_control_r3": self.raw_cfg["assembly_control"],
            "firmware": R3.record(firmware),
            "system": system_audit,
            "product": {"candidate": R3.record(product), "restored_exact_r3_bytes": True},
            "vendor": vendor_audit,
            "super": super_audit,
            "outer": outer_audit,
            "vbmeta_system": R3.record(vbmeta_system),
            "vbmeta_vendor": R3.record(vbmeta_vendor),
            "boot": {"candidate": R3.record(self.stage / "boot.fex"), "byte_preserved": True},
            "vendor_dlkm": {
                "candidate": R3.record(self.stage / "vendor_dlkm_a.img"),
                "byte_preserved": True, "module_count": 22,
            },
            "kernel": R3.record(self.stage / "kernel-evidence/Image"),
            "kernel_rebuilt": False,
            "root_cause": self.raw_cfg["root_cause"],
            "functional_delta_from_r4": self.raw_cfg["allowed_semantic_delta"],
            "forbidden_changes": self.raw_cfg["forbidden_changes"],
            "preserved": [
                "r2 /metadata and r3 /vendor physically crossed root contracts",
                "vendor_a, vendor_dlkm_a, boot, vendor_boot, fstab and kernel",
                "Mali, mapper, gralloc and every retained hardware-facing service",
                "LP geometry and 46 of 50 r4 outer payloads",
                "inactive logical product_a restored to exact r3 bytes",
            ],
        }
        result = R3.R2.R1.rewrite_paths(result, self.stage, self.final)
        (self.stage / "build-result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        sums = []
        for path in sorted(self.stage.iterdir()):
            if path.is_file() and path.name != "SHA256SUMS":
                sums.append(f"{R3.digest(path)}  {path.name}")
        (self.stage / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
        os.replace(self.stage, self.final)


def subprocess_check(command: list[str]) -> str:
    import subprocess
    return subprocess.check_output(command, text=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--aosp", type=Path, default=DEFAULT_AOSP)
    parser.add_argument("--keep-failed", action="store_true")
    Builder(parser.parse_args()).execute()


if __name__ == "__main__":
    main()
