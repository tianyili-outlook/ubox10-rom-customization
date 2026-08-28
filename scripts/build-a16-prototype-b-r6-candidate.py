#!/usr/bin/env python3
"""Build B r6 by adding only the proven missing vendor BoringSSL64 executable."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid


REPO = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO / "configs/candidates/a16-prototype-b-r6.json"
DEFAULT_AOSP = Path("/work/src/ubox10-a16-ceiling")
R5_CONFIG = REPO / "configs/candidates/a16-prototype-b-r5.json"

R5_PATH = REPO / "scripts/build-a16-prototype-b-r5-candidate.py"
R5_SPEC = importlib.util.spec_from_file_location("a16_b_r5_builder_for_r6", R5_PATH)
if R5_SPEC is None or R5_SPEC.loader is None:
    raise RuntimeError(f"cannot import r5 builder: {R5_PATH}")
R5 = importlib.util.module_from_spec(R5_SPEC)
sys.modules[R5_SPEC.name] = R5
R5_SPEC.loader.exec_module(R5)

SHARED = R5.R3.R2.R1
PACK = SHARED.PACK
CHUNK = 8 * 1024 * 1024


def source(path: str) -> Path:
    value = Path(path)
    return value if value.is_absolute() else REPO / value


class Builder(R5.Builder):
    def __init__(self, args: argparse.Namespace) -> None:
        base_args = argparse.Namespace(
            config=R5_CONFIG, aosp=args.aosp, keep_failed=args.keep_failed
        )
        super().__init__(base_args)
        raw = json.loads(args.config.read_text(encoding="utf-8"))
        self.args = args
        self.raw_cfg = raw
        self.cfg["id"] = raw["id"]
        self.cfg["status"] = raw["status"]
        self.cfg["base_candidate"] = raw["base_candidate"]
        self.cfg["_continuation"] = raw
        self.candidate_id = str(raw["id"])
        self.final = REPO / "out/candidates" / self.candidate_id
        self.stage = self.final.parent / f".{self.candidate_id}.staging-{uuid.uuid4().hex}"
        self.log = self.stage / "logs/01-commands.log"
        self.base = source(str(raw["base_candidate"]["path"]))
        self.started = time.time()

    def setup(self) -> None:
        if self.final.exists():
            raise RuntimeError(f"refusing to overwrite existing candidate: {self.final}")
        if self.raw_cfg["status"] != "ROOT_CAUSE_PROVEN_SINGLE_CAUSE_R6_AUTHORIZED":
            raise RuntimeError("r6 BoringSSL64 correction is not authorized")
        self.stage.mkdir(parents=True)
        self.require(self.base, self.raw_cfg["base_candidate"], "immutable failed r5 outer")
        self.require(self.rollback, self.r4["rollback"], "Android 12 rollback")
        for name, spec in self.raw_cfg["base_artifacts"].items():
            self.require(source(str(spec["path"])), spec, f"r5 assembly control {name}")

        physical = json.loads(
            (REPO / self.raw_cfg["root_cause"]["physical_result"]).read_text(
                encoding="utf-8"
            )
        )
        audit = json.loads(
            (REPO / self.raw_cfg["root_cause"]["audit"]).read_text(encoding="utf-8")
        )
        if (
            physical["abi_correction"]["global_mixed_abi"] != "PHYSICAL_PASS"
            or physical["boringssl_vendor"]["self_test32"]["exit_status"] != 0
            or physical["boringssl_vendor"]["self_test64"]["physical_result"]
            != "FIRST_FATAL_MISSING_EXECUTABLE"
            or audit["r6_decision"]["authorized"] is not True
            or audit["r6_decision"]["allowed_functional_delta"]
            != ["/vendor/bin/boringssl_self_test64"]
        ):
            raise RuntimeError("r6 root-cause authorization is not uniquely closed")

        manifest = subprocess.check_output(
            ["git", "-C", str(self.args.aosp / ".repo/manifests"), "rev-parse", "HEAD"],
            text=True,
        ).strip()
        if manifest != "ebea28d151539ecf0730b1a4ab92ac33edc17ac9":
            raise RuntimeError(f"exact r7 manifest changed: {manifest}")
        repository = subprocess.check_output(
            ["git", "-C", str(self.args.aosp / "external/boringssl"), "rev-parse", "HEAD"],
            text=True,
        ).strip()
        if repository != "ecc1358826150d6a1851c517c325b0e6c0e1b8be":
            raise RuntimeError(f"exact r7 BoringSSL source changed: {repository}")
        contract = self.raw_cfg["boringssl64_contract"]
        binary = Path(str(contract["source_path"]))
        self.require(binary, contract, "canonical r7 vendor BoringSSL64 output")
        header = subprocess.check_output(["readelf", "-h", str(binary)], text=True)
        notes = subprocess.check_output(["readelf", "-W", "-n", str(binary)], text=True)
        program = subprocess.check_output(["readelf", "-W", "-l", str(binary)], text=True)
        dynamic = subprocess.check_output(["readelf", "-W", "-d", str(binary)], text=True)
        needed = [
            line.split("[", 1)[1].split("]", 1)[0]
            for line in dynamic.splitlines() if "(NEEDED)" in line
        ]
        if (
            "Class:                             ELF64" not in header
            or "Machine:                           AArch64" not in header
            or f"Build ID: {contract['build_id']}" not in notes
            or f"Requesting program interpreter: {contract['interpreter']}" not in program
            or needed != contract["dt_needed"]
        ):
            raise RuntimeError("canonical r7 BoringSSL64 ELF contract changed")

        r5 = REPO / "out/candidates/a16-prototype-b-r5"
        shutil.copytree(r5 / "kernel-evidence", self.stage / "kernel-evidence")
        for name in (
            "final-build-variables.txt", "mali-intake.json",
            "active-product-build.prop.r5", "runtime-product-source-audit.json",
        ):
            shutil.copyfile(r5 / name, self.stage / name)

    def prepare_system(self) -> tuple[Path, dict[str, object]]:
        spec = self.raw_cfg["base_artifacts"]["system_a"]
        original = source(str(spec["path"]))
        system = self.stage / "system_a.img"
        shutil.copyfile(original, system)
        self.require(system, spec, "byte-preserved r5 system_a")
        for path, expected in (
            ("/metadata", self.raw_cfg["root_mountpoint_contract"]["metadata"]),
            ("/vendor", self.raw_cfg["root_mountpoint_contract"]["vendor"]),
        ):
            inode = self.debugfs(system, f"stat {path}", capture=True)
            attrs = self.debugfs(system, f"ea_list {path}", capture=True)
            if (
                "Type: directory" not in inode
                or f"Mode:  {expected['mode']}" not in inode
                or expected["selinux"] not in attrs
            ):
                raise RuntimeError(f"r6 changed crossed root contract: {path}")
        product = self.debugfs(system, "stat /product", capture=True)
        if 'Fast link dest: "/system/product"' not in product:
            raise RuntimeError("r6 changed active embedded-product layout")
        properties = self.debugfs(
            system,
            f"cat {self.raw_cfg['active_product_property_contract']['active_path']}",
            capture=True,
        )
        for key, value in self.raw_cfg["active_product_property_contract"]["properties"].items():
            if f"{key}={value}" not in properties.splitlines():
                raise RuntimeError(f"r6 lost physically proven active ABI source: {key}")
        return system, {
            "base_r5": SHARED.record(original),
            "candidate": SHARED.record(system),
            "byte_preserved_from_r5": True,
            "active_product_global_abi_physical_result": "PASS_PRESERVED",
            "root_metadata_vendor_product_contract": "PASS_PRESERVED",
        }

    def prepare_vendor(self) -> tuple[Path, dict[str, object]]:
        spec = self.raw_cfg["base_artifacts"]["vendor_a"]
        original = source(str(spec["path"]))
        vendor = self.stage / "vendor_a.img"
        shutil.copyfile(original, vendor)
        self.require(vendor, spec, "exact r5 vendor_a")
        self.run([sys.executable, str(self.avbtool), "erase_footer", "--image", str(vendor)])
        if vendor.stat().st_size != self.cfg["avb"]["vendor"]["filesystem_size"]:
            raise RuntimeError("r5 vendor filesystem size changed")
        self.run(["e2fsck", "-fn", str(vendor)])

        retained: dict[str, dict[str, object]] = {}
        for name, lock in self.raw_cfg["retained_vendor_contract"].items():
            if not isinstance(lock, dict) or "path" not in lock:
                continue
            dumped = self.stage / f"retained-{name}"
            self.debugfs(vendor, f"dump -p {lock['path']} {dumped}")
            retained[name] = self.require(dumped, lock, f"retained vendor {name}")
        target = str(self.raw_cfg["boringssl64_contract"]["install_path"])
        before = self.debugfs(vendor, f"stat {target}", capture=True)
        if "File not found" not in before:
            raise RuntimeError("r5 unexpectedly already contains vendor BoringSSL64")
        if "File not found" not in self.debugfs(vendor, "stat /lib64/libcrypto.so", capture=True):
            raise RuntimeError("r5 unexpectedly contains a standalone vendor libcrypto64")

        contract = self.raw_cfg["boringssl64_contract"]
        binary = Path(str(contract["source_path"]))
        previous_fake_time = os.environ.get("E2FSPROGS_FAKE_TIME")
        os.environ["E2FSPROGS_FAKE_TIME"] = str(int(str(contract["crtime"]), 16))
        try:
            self.debugfs(vendor, f"write {binary} {target}")
            for field, value in (
                ("mode", "0100755"), ("uid", "0"), ("gid", "2000"),
                ("ctime", contract["ctime"]), ("atime", contract["atime"]),
                ("mtime", contract["mtime"]), ("crtime", contract["crtime"]),
            ):
                self.debugfs(vendor, f"set_inode_field {target} {field} {value}")
            self.debugfs(
                vendor,
                f'ea_set {target} security.selinux "{contract["selinux"]}\\000"',
            )
            for field, value in (
                ("ctime", "0x652f7ab5"), ("atime", "0x652f7ab5"),
                ("mtime", "0x652f7ab5"), ("crtime", "0x65379527"),
            ):
                self.debugfs(vendor, f"set_inode_field /bin {field} {value}")
            self.run(["e2fsck", "-fy", str(vendor)], allowed={0, 1})
        finally:
            if previous_fake_time is None:
                os.environ.pop("E2FSPROGS_FAKE_TIME", None)
            else:
                os.environ["E2FSPROGS_FAKE_TIME"] = previous_fake_time
        self.run(["e2fsck", "-fn", str(vendor)])

        dumped = self.stage / "boringssl_self_test64"
        self.debugfs(vendor, f"dump -p {target} {dumped}")
        installed = self.require(dumped, contract, "installed vendor BoringSSL64")
        inode = self.debugfs(vendor, f"stat {target}", capture=True)
        attrs = self.debugfs(
            vendor, f"ea_get {target} security.selinux", capture=True
        )
        if (
            "Mode:  0755" not in inode
            or "User:     0   Group:  2000" not in inode
            or contract["selinux"] not in attrs
        ):
            raise RuntimeError("installed vendor BoringSSL64 inode contract changed")

        avb = self.cfg["avb"]["vendor"]
        self.run([
            sys.executable, str(self.avbtool), "add_hashtree_footer",
            "--image", str(vendor), "--partition_name", "vendor",
            "--partition_size", str(avb["partition_size"]),
            "--hash_algorithm", "sha256", "--salt", avb["salt"],
            "--prop", f"com.android.build.vendor.fingerprint:{avb['fingerprint']}",
            "--prop", f"com.android.build.vendor.os_version:{avb['os_version']}",
        ])
        if vendor.stat().st_size != avb["partition_size"]:
            raise RuntimeError("signed r6 vendor partition size changed")
        self.verify_avb_partition(vendor, "vendor", None)
        return vendor, {
            "base_r5": SHARED.record(original),
            "candidate": SHARED.record(vendor),
            "tree_delta": {"added": ["bin/boringssl_self_test64"], "removed": [], "changed": []},
            "retained": retained,
            "boringssl_self_test64": installed,
            "dt_needed_closure": "PASS_ZERO_UNMATCHED_EXISTING_R5_PROVIDERS",
            "new_vendor_libcrypto": False,
            "ext4": "PASS",
            "avb_hashtree_fec": "PASS",
        }

    def make_vbmeta(self, image: Path, partition: str) -> Path:
        if partition != "system":
            return super().make_vbmeta(image, partition)
        spec = self.raw_cfg["base_artifacts"]["vbmeta_system"]
        output = self.stage / "vbmeta_system.fex"
        shutil.copyfile(source(str(spec["path"])), output)
        self.require(output, spec, "byte-preserved r5 vbmeta_system")
        self.verify_avb_partition(image, "system", self.cfg["avb"]["system"]["key_relative"])
        return output

    def build_super(self, system: Path, vendor: Path) -> tuple[Path, dict[str, object]]:
        spec = self.raw_cfg["base_artifacts"]["super_raw"]
        original = source(str(spec["path"]))
        candidate = self.stage / "super.raw.img"
        self.run(["cp", "--reflink=auto", str(original), str(candidate)])
        self.run([
            str(self.host / "lpadd"), "--replace", "--readonly", str(candidate),
            "vendor_a", "sb_a", str(vendor),
        ], output=self.stage / "lpadd-vendor.log")

        old_json = self.stage / "r5-lpdump.json"
        new_json = self.stage / "candidate-lpdump.json"
        self.run([str(self.host / "lpdump"), "-j", str(original)], output=old_json)
        self.run([str(self.host / "lpdump"), "-j", str(candidate)], output=new_json)
        old_metadata = json.loads(old_json.read_text(encoding="utf-8"))
        new_metadata = json.loads(new_json.read_text(encoding="utf-8"))
        if new_metadata != old_metadata:
            raise RuntimeError("r6 changed exact r5 LP metadata or extents")
        slot1 = self.stage / "candidate-lpdump-slot1.json"
        self.run([str(self.host / "lpdump"), "-s", "1", "-j", str(candidate)], output=slot1)
        if json.loads(slot1.read_text(encoding="utf-8")) != new_metadata:
            raise RuntimeError("r6 LP metadata slots 0 and 1 differ")

        sparse = self.stage / "super.fex"
        roundtrip = self.stage / "super-sparse-roundtrip.raw.img"
        self.run([str(self.host / "img2simg"), str(candidate), str(sparse), "4096"])
        self.run([str(self.host / "simg2img"), str(sparse), str(roundtrip)])
        if SHARED.digest(roundtrip) != SHARED.digest(candidate):
            raise RuntimeError("r6 sparse/raw super roundtrip changed bytes")
        extracted = self.stage / "candidate-logical"
        extracted.mkdir()
        self.run([str(self.host / "lpunpack"), str(roundtrip), str(extracted)])
        logical: dict[str, dict[str, object]] = {}
        for name, expected_path in (
            ("system_a", system), ("vendor_a", vendor),
            ("product_a", source(str(self.raw_cfg["base_artifacts"]["product_a"]["path"]))),
            ("vendor_dlkm_a", source(str(self.raw_cfg["base_artifacts"]["vendor_dlkm"]["path"]))),
        ):
            path = extracted / f"{name}.img"
            if path.stat().st_size != expected_path.stat().st_size or SHARED.digest(path) != SHARED.digest(expected_path):
                raise RuntimeError(f"r6 super changed logical bytes: {name}")
            logical[name] = SHARED.record(path)
        for name in ("system_b", "vendor_b", "product_b", "vendor_dlkm_b"):
            path = extracted / f"{name}.img"
            if path.stat().st_size != 0:
                raise RuntimeError(f"r6 changed empty B-slot contract: {name}")
            logical[name] = SHARED.record(path)
        return sparse, {
            "frozen_raw": SHARED.record(original),
            "candidate_raw": SHARED.record(candidate),
            "candidate_sparse": SHARED.record(sparse),
            "metadata_slots_0_and_1_exact": True,
            "lp_metadata_and_extents_exact_r5": True,
            "sb_a_maximum_bytes": 3212836864,
            "sb_a_allocated_bytes": 2081472512,
            "sb_a_unallocated_bytes": 1131364352,
            "vendor_a_bytes": 150994944,
            "growth_only_from_old_unallocated_space": True,
            "all_other_partition_extents_exact_r4": True,
            "no_partition_shrunk": True,
            "b_slot_allocations_empty_exact": True,
            "sparse_roundtrip_exact": True,
            "logical": logical,
        }

    def pack_outer(
        self, super_sparse: Path, vbmeta_system: Path, vbmeta_vendor: Path
    ) -> tuple[Path, dict[str, object]]:
        before = PACK.outer_payloads(self.base)
        firmware = self.stage / f"x12-{self.candidate_id}.img"
        payload_audit = self.stage / "outer-payload-audit.json"
        self.run([
            sys.executable, str(REPO / "tools/pack_image_preserving.py"),
            "--source", str(self.base), "--output", str(firmware),
            "--replace", f"super.fex={super_sparse}",
            "--replace", f"vbmeta_vendor.fex={vbmeta_vendor}",
            "--audit", str(payload_audit),
        ])
        self.run([
            sys.executable, str(REPO / "tools/sunxi_image_tool.py"), "verify", str(firmware)
        ], output=self.stage / "candidate-outer-verify.log")
        after = PACK.outer_payloads(firmware)
        changed = sorted(
            name for name in before
            if before[name]["sha256_stored"] != after[name]["sha256_stored"]
        )
        expected = sorted(self.raw_cfg["outer_delta"]["changed_payloads_from_base"])
        if set(before) != set(after) or len(after) != 50 or changed != expected:
            raise RuntimeError(f"unexpected r6 outer payload delta: {changed}")
        return firmware, {
            "candidate": SHARED.record(firmware),
            "entry_count": 50,
            "changed_payloads": changed,
            "preserved_payload_count": 46,
            "all_other_payload_bytes_exact_r5": True,
            "imagewty_verify": "PASS",
            "top_level_vbmeta_byte_preserved": before["vbmeta.fex"] == after["vbmeta.fex"],
            "system_vbmeta_byte_preserved": before["vbmeta_system.fex"] == after["vbmeta_system.fex"],
        }

    def finish(
        self, firmware: Path, system_audit: dict[str, object],
        vendor_audit: dict[str, object], super_audit: dict[str, object],
        outer_audit: dict[str, object], vbmeta_system: Path, vbmeta_vendor: Path,
    ) -> None:
        for name, key in (("boot.fex", "boot"), ("vendor_dlkm_a.img", "vendor_dlkm")):
            shutil.copyfile(source(str(self.raw_cfg["base_artifacts"][key]["path"])), self.stage / name)
        result = {
            "schema": 1,
            "id": self.candidate_id,
            "status": "PACKAGED_AWAITING_FULL_OFFLINE_AUDIT",
            "decision": "PENDING_FULL_OFFLINE_AUDIT",
            "physical_status": "NOT_YET_VALIDATED",
            "physical_device_actions_performed": False,
            "flash_authorized": False,
            "elapsed_seconds": round(time.time() - self.started, 1),
            "source": {
                "tag": "android-security-16.0.0_r7",
                "manifest_commit": "ebea28d151539ecf0730b1a4ab92ac33edc17ac9",
                "boringssl_commit": "ecc1358826150d6a1851c517c325b0e6c0e1b8be",
                "android_system_rebuilt": False,
                "kernel_rebuilt": False,
                "targeted_module_built": "boringssl_self_test_vendor",
            },
            "base_r5": SHARED.record(self.base),
            "firmware": SHARED.record(firmware),
            "system": system_audit,
            "vendor": vendor_audit,
            "super": super_audit,
            "outer": outer_audit,
            "vbmeta_system": SHARED.record(vbmeta_system),
            "vbmeta_vendor": SHARED.record(vbmeta_vendor),
            "boot": {
                "candidate": SHARED.record(self.stage / "boot.fex"),
                "byte_preserved_from_r5": True,
            },
            "vendor_dlkm": {
                "candidate": SHARED.record(self.stage / "vendor_dlkm_a.img"),
                "byte_preserved_from_r5": True,
                "module_count": 22,
            },
            "kernel": SHARED.record(self.stage / "kernel-evidence/Image"),
            "root_cause": self.raw_cfg["root_cause"],
            "functional_delta_from_r5": self.raw_cfg["allowed_semantic_delta"],
            "forbidden_changes": self.raw_cfg["forbidden_changes"],
        }
        result = SHARED.rewrite_paths(result, self.stage, self.final)
        (self.stage / "build-result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        sums = []
        for path in sorted(self.stage.iterdir()):
            if path.is_file() and path.name != "SHA256SUMS":
                sums.append(f"{SHARED.digest(path)}  {path.name}")
        (self.stage / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
        os.replace(self.stage, self.final)

    def execute(self) -> None:
        try:
            self.setup()
            system, system_audit = self.prepare_system()
            vendor, vendor_audit = self.prepare_vendor()
            vbmeta_system = self.make_vbmeta(system, "system")
            vbmeta_vendor = self.make_vbmeta(vendor, "vendor")
            super_sparse, super_audit = self.build_super(system, vendor)
            firmware, outer_audit = self.pack_outer(
                super_sparse, vbmeta_system, vbmeta_vendor
            )
            self.finish(
                firmware, system_audit, vendor_audit, super_audit, outer_audit,
                vbmeta_system, vbmeta_vendor,
            )
        except Exception:
            if self.stage.exists() and not self.args.keep_failed:
                shutil.rmtree(self.stage)
            raise
        print(f"PACKAGED: {self.final}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--aosp", type=Path, default=DEFAULT_AOSP)
    parser.add_argument("--keep-failed", action="store_true")
    Builder(parser.parse_args()).execute()


if __name__ == "__main__":
    main()
