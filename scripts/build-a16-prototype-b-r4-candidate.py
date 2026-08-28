#!/usr/bin/env python3
"""Build the bounded Prototype B r4 product-scoped ABI-property candidate."""
from __future__ import annotations

import argparse
import difflib
import importlib.util
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
DEFAULT_CONFIG = REPO / "configs/candidates/a16-prototype-b-r4.json"
DEFAULT_AOSP = Path("/work/src/ubox10-a16-ceiling")
BUILD_PATH = REPO / "scripts/build-a16-prototype-b-r1-candidate.py"
SPEC = importlib.util.spec_from_file_location("a16_b_r1_build_helpers_for_r4", BUILD_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import B1 build helpers: {BUILD_PATH}")
B1 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = B1
SPEC.loader.exec_module(B1)


class Builder:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.cfg = json.loads(args.config.read_text(encoding="utf-8"))
        self.candidate_id = self.cfg["id"]
        self.final = REPO / "out/candidates" / self.candidate_id
        self.stage = self.final.parent / f".{self.candidate_id}.staging-{uuid.uuid4().hex}"
        self.log = self.stage / "logs/01-commands.log"
        self.base_dir = REPO / "out/candidates/a16-prototype-b-r3"
        self.host = args.aosp / "out-ceiling-b1/host/linux-x86/bin"
        self.avbtool = args.aosp / "external/avb/avbtool.py"
        self.started = time.time()

    def run(self, command: list[str], *, output: Path | None = None,
            allowed: set[int] | None = None) -> int:
        line = "$ " + subprocess.list2cmdline(command)
        print(line, flush=True)
        self.log.parent.mkdir(parents=True, exist_ok=True)
        with self.log.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")
        destination = output or self.log
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w" if output else "a", encoding="utf-8", newline="\n") as stream:
            done = subprocess.run(command, cwd=REPO, stdout=stream,
                                  stderr=subprocess.STDOUT, text=True, check=False)
        if done.returncode not in ({0} if allowed is None else allowed):
            raise RuntimeError(f"command failed ({done.returncode}): {command}")
        return done.returncode

    def debugfs(self, image: Path, command: str, *, capture: bool = False) -> str:
        argv = ["debugfs", "-w", "-R", command, str(image)]
        if capture:
            return subprocess.check_output(argv, text=True, stderr=subprocess.STDOUT)
        self.run(argv)
        return ""

    @staticmethod
    def resolve(path: str) -> Path:
        value = Path(path)
        return value if value.is_absolute() else REPO / value

    def require(self, spec: dict[str, object], label: str) -> Path:
        path = self.resolve(str(spec["path"]))
        if not path.is_file():
            raise RuntimeError(f"missing {label}: {path}")
        actual = B1.record(path)
        if actual["size"] != spec["size"] or actual["sha256"] != spec["sha256"]:
            raise RuntimeError(f"{label} identity mismatch: {actual}")
        return path

    def setup(self) -> None:
        if self.final.exists():
            raise RuntimeError(f"refusing to overwrite existing candidate: {self.final}")
        if self.cfg["status"] != "ROOT_CAUSE_PROVEN_SINGLE_CAUSE_R4_AUTHORIZED":
            raise RuntimeError("r4 is not authorized by a proven ABI root cause")
        self.stage.mkdir(parents=True)
        self.require(self.cfg["base_candidate"], "immutable failed r3 outer image")
        for name, spec in self.cfg["base_artifacts"].items():
            self.require(spec, f"r3 {name}")
        source = REPO / self.cfg["generated_product_property_contract"]["source_relative"]
        installed = self.args.aosp / self.cfg["generated_product_property_contract"]["aosp_relative"]
        expected = self.cfg["generated_product_property_contract"]["source_sha256"]
        if B1.digest(source) != expected or B1.digest(installed) != expected:
            raise RuntimeError("tracked/AOSP r4 product source identity mismatch")
        generated = Path(self.cfg["generated_product_property_contract"]["generated_path"])
        contract = self.cfg["generated_product_property_contract"]
        if B1.record(generated) != {
            "path": str(generated), "size": contract["generated_size"],
            "sha256": contract["generated_sha256"],
        }:
            raise RuntimeError("source-generated product build.prop identity mismatch")
        manifest = subprocess.check_output(
            ["git", "-C", str(self.args.aosp / ".repo/manifests"), "rev-parse", "HEAD"],
            text=True,
        ).strip()
        if manifest != "ebea28d151539ecf0730b1a4ab92ac33edc17ac9":
            raise RuntimeError(f"r7 manifest identity changed: {manifest}")
        for tool in ("lpdump", "lpunpack", "img2simg", "simg2img"):
            if not (self.host / tool).is_file():
                raise RuntimeError(f"missing exact-r7 host tool: {tool}")

    def prepare_product(self) -> tuple[Path, dict[str, object]]:
        source = self.require(self.cfg["base_artifacts"]["product_a"], "r3 product_a")
        product = self.stage / "product_a.img"
        shutil.copyfile(source, product)
        self.run([sys.executable, str(self.avbtool), "erase_footer", "--image", str(product)])
        avb = self.cfg["avb_product"]
        if product.stat().st_size != avb["original_filesystem_size"]:
            raise RuntimeError("r3 product filesystem size changed")
        self.run(["e2fsck", "-fy", str(product)], allowed={0, 1})

        before_file = self.stage / "product-build.prop.r3"
        after_file = self.stage / "product-build.prop.r4"
        self.debugfs(product, f"dump -p /etc/build.prop {before_file}")
        if B1.digest(before_file) != "62745843C6E22B2168E72055D931CF523ECF74D112B38AC6BFFFC6D99CABA4F1":
            raise RuntimeError("r3 product build.prop identity changed")
        before = before_file.read_text(encoding="utf-8")
        generated = Path(self.cfg["generated_product_property_contract"]["generated_path"])
        generated_lines = generated.read_text(encoding="utf-8").splitlines()
        properties = self.cfg["generated_product_property_contract"]["properties"]
        additions = [f"{name}={value}" for name, value in properties.items()]
        for line in additions:
            if generated_lines.count(line) != 1:
                raise RuntimeError(f"source-generated ABI property is not exact: {line}")
        if any(re.match(r"^ro\.product\.product\.cpu\.abilist(?:32|64)?=", line)
               for line in before.splitlines()):
            raise RuntimeError("r3 product unexpectedly already defines the ABI triplet")
        marker = "# from variable PRODUCT_PRODUCT_PROPERTIES\n"
        if before.count(marker) != 1:
            raise RuntimeError("r3 product property section marker changed")
        after = before.replace(marker, marker + "\n".join(additions) + "\n", 1)
        after_file.write_text(after, encoding="utf-8", newline="\n")
        diff = list(difflib.unified_diff(before.splitlines(), after.splitlines(), lineterm=""))
        added = [line[1:] for line in diff if line.startswith("+") and not line.startswith("+++")]
        removed = [line[1:] for line in diff if line.startswith("-") and not line.startswith("---")]
        if added != additions or removed:
            raise RuntimeError(f"product build.prop delta expanded: added={added}, removed={removed}")

        self.debugfs(product, "rm /etc/build.prop")
        self.debugfs(product, f"write {after_file} /etc/build.prop")
        self.debugfs(product, "set_inode_field /etc/build.prop mode 0100644")
        self.debugfs(product, "set_inode_field /etc/build.prop uid 0")
        self.debugfs(product, "set_inode_field /etc/build.prop gid 0")
        self.debugfs(product, 'ea_set /etc/build.prop security.selinux "u:object_r:system_file:s0\\000"')
        installed = self.debugfs(product, "cat /etc/build.prop", capture=True)
        for line in additions:
            if installed.splitlines().count(line) != 1:
                raise RuntimeError(f"installed product ABI property changed: {line}")
        inode = self.debugfs(product, "stat /etc/build.prop", capture=True)
        if "Mode:  0644" not in inode or "User:     0   Group:     0" not in inode:
            raise RuntimeError("product build.prop mode/owner contract changed")
        attrs = self.debugfs(product, "ea_list /etc/build.prop", capture=True)
        if "u:object_r:system_file:s0" not in attrs:
            raise RuntimeError("product build.prop SELinux xattr changed")
        self.run(["e2fsck", "-fy", str(product)], allowed={0, 1})
        self.run(["e2fsck", "-fn", str(product)])
        self.run([
            sys.executable, str(self.avbtool), "add_hashtree_footer",
            "--image", str(product), "--partition_name", "product",
            "--partition_size", str(avb["partition_size"]),
            "--hash_algorithm", "sha256", "--salt", avb["salt"],
            "--do_not_generate_fec", "--key", str(REPO / avb["key_relative"]),
            "--algorithm", avb["algorithm"],
            "--prop", f"com.ubox10.candidate.id:{self.candidate_id}",
            "--prop", "com.ubox10.avb.fec:none",
        ])
        if product.stat().st_size != avb["partition_size"]:
            raise RuntimeError("signed product partition size changed")
        view = self.stage / "product-avb-view"
        view.mkdir()
        os.link(product, view / "product.img")
        self.run([
            sys.executable, str(self.avbtool), "verify_image", "--image",
            str(view / "product.img"), "--key", str(REPO / avb["key_relative"]),
        ], output=self.stage / "product-avb-verify.log")
        self.run([
            sys.executable, str(self.avbtool), "info_image", "--image", str(product),
        ], output=self.stage / "product-avb-info.txt")
        (view / "product.img").unlink()
        view.rmdir()
        return product, {
            "base": B1.record(source), "candidate": B1.record(product),
            "tree_delta": {"added": [], "removed": [], "changed": ["etc/build.prop"]},
            "property_lines_added": additions,
            "property_before_sha256": B1.digest(before_file),
            "property_after_sha256": B1.digest(after_file),
            "mode_uid_gid_selinux_preserved": True,
            "ext4": "PASS", "avb_hashtree_no_fec": "PASS",
        }

    def prepare_super(self, product: Path) -> tuple[Path, Path, dict[str, object]]:
        source = self.require(self.cfg["base_artifacts"]["super_raw"], "r3 raw super")
        raw = self.stage / "super.raw.img"
        self.run(["cp", "--reflink=auto", str(source), str(raw)])
        extent = self.cfg["product_extent"]
        expected = extent["sector_count"] * extent["sector_size"]
        if product.stat().st_size != expected:
            raise RuntimeError("signed product no longer fits exact LP extent")
        with raw.open("r+b") as destination, product.open("rb") as payload:
            destination.seek(extent["first_sector"] * extent["sector_size"])
            shutil.copyfileobj(payload, destination, B1.CHUNK)
        old_dump = self.stage / "r3-lpdump.json"
        new_dump = self.stage / "candidate-lpdump.json"
        self.run([str(self.host / "lpdump"), "-j", str(source)], output=old_dump)
        self.run([str(self.host / "lpdump"), "-j", str(raw)], output=new_dump)
        if old_dump.read_bytes() != new_dump.read_bytes():
            raise RuntimeError("r4 changed LP metadata/geometry")
        slot1 = self.stage / "candidate-lpdump-slot1.json"
        self.run([str(self.host / "lpdump"), "-s", "1", "-j", str(raw)], output=slot1)
        if json.loads(slot1.read_text()) != json.loads(new_dump.read_text()):
            raise RuntimeError("LP metadata slots differ")
        sparse = self.stage / "super.fex"
        roundtrip = self.stage / "super-sparse-roundtrip.raw.img"
        self.run([str(self.host / "img2simg"), str(raw), str(sparse), "4096"])
        self.run([str(self.host / "simg2img"), str(sparse), str(roundtrip)])
        if B1.digest(roundtrip) != B1.digest(raw):
            raise RuntimeError("super sparse/raw roundtrip changed bytes")
        logical = self.stage / "candidate-logical"
        logical.mkdir()
        self.run([str(self.host / "lpunpack"), str(roundtrip), str(logical)])
        expected_images = {
            "system_a": self.cfg["base_artifacts"]["system_a"],
            "vendor_a": self.cfg["base_artifacts"]["vendor_a"],
            "vendor_dlkm_a": self.cfg["base_artifacts"]["vendor_dlkm_a"],
        }
        for name, spec in expected_images.items():
            if B1.record(logical / f"{name}.img")["sha256"] != spec["sha256"]:
                raise RuntimeError(f"r4 changed preserved logical image: {name}")
        if B1.digest(logical / "product_a.img") != B1.digest(product):
            raise RuntimeError("super changed r4 product bytes")
        for name in ("system_b", "vendor_b", "product_b", "vendor_dlkm_b"):
            if (logical / f"{name}.img").stat().st_size != 0:
                raise RuntimeError(f"B-slot allocation changed: {name}")
        return raw, sparse, {
            "frozen_raw": B1.record(source), "candidate_raw": B1.record(raw),
            "candidate_sparse": B1.record(sparse),
            "growth_only_from_old_unallocated_space": True,
            "all_other_partition_extents_exact_r4": True,
            "no_partition_shrunk": True,
            "b_slot_allocations_empty_exact": True,
            "sparse_roundtrip_exact": True,
            "product_extent_exact": True,
            "lp_metadata_byte_preserved_from_r3": True,
        }

    def pack_outer(self, sparse: Path) -> tuple[Path, dict[str, object]]:
        base = self.require(self.cfg["base_candidate"], "r3 outer")
        firmware = self.stage / f"x12-{self.candidate_id}.img"
        self.run([
            sys.executable, str(REPO / "tools/pack_image_preserving.py"),
            "--source", str(base), "--output", str(firmware),
            "--replace", f"super.fex={sparse}",
            "--audit", str(self.stage / "outer-payload-audit.json"),
        ])
        self.run([
            sys.executable, str(REPO / "tools/sunxi_image_tool.py"), "verify", str(firmware),
        ], output=self.stage / "candidate-outer-verify.log")
        before = B1.PACK.outer_payloads(base)
        after = B1.PACK.outer_payloads(firmware)
        changed = sorted(name for name in before
                         if before[name]["sha256_stored"] != after[name]["sha256_stored"])
        expected = sorted(self.cfg["outer_delta"]["changed_payloads_from_base"])
        if changed != expected or set(before) != set(after) or len(after) != 50:
            raise RuntimeError(f"outer delta expanded: {changed}")
        return firmware, {
            "candidate": B1.record(firmware), "entry_count": 50,
            "changed_payloads": changed, "preserved_payload_count": 48,
            "all_unlisted_payloads_byte_preserved_from_r3": True,
            "imagewty_verify": "PASS",
            "top_level_vbmeta_byte_preserved": before["vbmeta.fex"] == after["vbmeta.fex"],
            "vbmeta_system_byte_preserved": before["vbmeta_system.fex"] == after["vbmeta_system.fex"],
            "vbmeta_vendor_byte_preserved": before["vbmeta_vendor.fex"] == after["vbmeta_vendor.fex"],
            "boot_byte_preserved": before["boot.fex"] == after["boot.fex"],
        }

    def finish(self, product: Path, raw: Path, sparse: Path, firmware: Path,
               product_audit: dict[str, object], super_audit: dict[str, object],
               outer_audit: dict[str, object]) -> None:
        copies = {
            "system_a.img": self.cfg["base_artifacts"]["system_a"],
            "vendor_a.img": self.cfg["base_artifacts"]["vendor_a"],
            "vendor_dlkm_a.img": self.cfg["base_artifacts"]["vendor_dlkm_a"],
            "boot.fex": self.cfg["base_artifacts"]["boot"],
            "vbmeta_system.fex": self.cfg["base_artifacts"]["vbmeta_system"],
            "vbmeta_vendor.fex": self.cfg["base_artifacts"]["vbmeta_vendor"],
        }
        for name, spec in copies.items():
            shutil.copyfile(self.resolve(spec["path"]), self.stage / name)
        shutil.copytree(self.base_dir / "kernel-evidence", self.stage / "kernel-evidence")
        result = {
            "schema": 1, "id": self.candidate_id,
            "status": "PACKAGED_AWAITING_FULL_OFFLINE_AUDIT",
            "decision": "PENDING_FULL_OFFLINE_AUDIT",
            "physical_status": "NOT_YET_VALIDATED",
            "physical_device_actions_performed": False, "flash_authorized": False,
            "elapsed_seconds": round(time.time() - self.started, 1),
            "source": {
                "tag": "android-security-16.0.0_r7",
                "manifest_commit": "ebea28d151539ecf0730b1a4ab92ac33edc17ac9",
                "build_id": "BP2A.250805.034",
                "build_number": "UBOX10_A16_QPR0_B4",
                "lunch": "ubox10_ceiling_arm64-bp2a-userdebug",
                "generated_product_build_prop": self.cfg["generated_product_property_contract"],
            },
            "firmware": B1.record(firmware),
            "system": {"candidate": B1.record(self.stage / "system_a.img"),
                       "byte_preserved_from_r3": True},
            "vendor": {"candidate": B1.record(self.stage / "vendor_a.img"),
                       "byte_preserved_from_r3": True},
            "product": product_audit, "super": super_audit, "outer": outer_audit,
            "vbmeta_system": B1.record(self.stage / "vbmeta_system.fex"),
            "vbmeta_vendor": B1.record(self.stage / "vbmeta_vendor.fex"),
            "boot": {"candidate": B1.record(self.stage / "boot.fex"),
                     "byte_preserved_from_r3": True},
            "vendor_dlkm": {"candidate": B1.record(self.stage / "vendor_dlkm_a.img"),
                            "byte_preserved_from_r3": True, "module_count": 22},
            "kernel": B1.record(self.stage / "kernel-evidence/Image"),
            "kernel_rebuilt": False,
            "functional_delta": [
                "source-generated product-scoped mixed ABI triplet overrides retained ARM32 ODM metadata during exact r7 global ABI derivation"
            ],
            "graphics_delta": "NONE_READ_ONLY_AUDIT_ONLY",
            "preserved": [
                "r3 system_a including /metadata and canonical /vendor root contracts",
                "r3 vendor_a including exact Mali, mapper, gralloc and all vendor HALs",
                "kernel, boot, vendor_boot/fstab, vendor_dlkm and all 22 modules",
                "LP geometry, subordinate/top-level vbmeta and 48 unrelated outer payloads",
            ],
        }
        result = B1.rewrite_paths(result, self.stage, self.final)
        (self.stage / "build-result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        sums = []
        for path in sorted(self.stage.iterdir()):
            if path.is_file() and path.name != "SHA256SUMS":
                sums.append(f"{B1.digest(path)}  {path.name}")
        (self.stage / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
        os.replace(self.stage, self.final)

    def execute(self) -> None:
        try:
            self.setup()
            product, product_audit = self.prepare_product()
            raw, sparse, super_audit = self.prepare_super(product)
            firmware, outer_audit = self.pack_outer(sparse)
            self.finish(product, raw, sparse, firmware, product_audit, super_audit, outer_audit)
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
