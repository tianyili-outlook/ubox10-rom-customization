#!/usr/bin/env python3
"""Package the single-variable r7-diag2 HEVC visible-crop diagnostic."""
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
DEFAULT_CONFIG = REPO / "configs/candidates/a16-prototype-b-r7-diag2-hevc-crop.json"
DEFAULT_AOSP = Path("/work/src/ubox10-a16-ceiling")
DIAG1A_CONFIG = REPO / "configs/candidates/a16-prototype-b-r7-diag1a.json"
DIAG1A_PATH = REPO / "scripts/build-a16-prototype-b-r7-diag1a-candidate.py"
SPEC = importlib.util.spec_from_file_location("r7_diag1a_builder_for_diag2_crop", DIAG1A_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import diag1a builder: {DIAG1A_PATH}")
DIAG1A = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = DIAG1A
SPEC.loader.exec_module(DIAG1A)

SHARED = DIAG1A.SHARED
PACK = DIAG1A.PACK
DIAG1 = DIAG1A.DIAG1


def source(path: str) -> Path:
    value = Path(path)
    return value if value.is_absolute() else REPO / value


def strong_undefined(path: Path) -> list[str]:
    output = subprocess.check_output(
        ["nm", "-D", "--undefined-only", "--format=posix", str(path)], text=True
    )
    return sorted(
        fields[0].split("@", 1)[0]
        for line in output.splitlines()
        if len(fields := line.split()) >= 2 and fields[1] == "U"
    )


class Builder(DIAG1A.Builder):
    def __init__(self, args: argparse.Namespace) -> None:
        base_args = argparse.Namespace(
            config=DIAG1A_CONFIG, aosp=args.aosp, keep_failed=args.keep_failed
        )
        super().__init__(base_args)
        self.args = args
        self.diag2 = json.loads(args.config.read_text(encoding="utf-8"))
        self.candidate_id = self.diag2["id"]
        self.cfg["id"] = self.candidate_id
        self.final = REPO / "out/candidates" / self.candidate_id
        self.stage = self.final.parent / f".{self.candidate_id}.staging-{uuid.uuid4().hex}"
        self.log = self.stage / "logs/01-commands.log"
        self.base = source(self.diag2["base_candidate"]["path"])
        self.started = time.time()

    def setup(self) -> None:
        if self.final.exists():
            raise RuntimeError(f"refusing to overwrite existing candidate: {self.final}")
        if self.diag2["status"] != "DIAGNOSTIC_SINGLE_VARIABLE_CROP_CANDIDATE_AUTHORIZED":
            raise RuntimeError("diag2 crop candidate is not authorized")
        governance = self.diag2["governance"]
        if governance["gate3"] != "HOLD" or governance["r8_authorized"] is not False:
            raise RuntimeError("diag2 must retain Gate 3 HOLD and must not authorize r8")
        self.stage.mkdir(parents=True)
        self.require(self.base, self.diag2["base_candidate"], "exact diag1a outer")
        for name, record in self.diag2["base_artifacts"].items():
            self.require(source(record["path"]), record, f"exact diag1a artifact {name}")

        contract = self.diag2["source_contract"]
        revision = subprocess.check_output(
            ["git", "-C", str(self.args.aosp / "frameworks/av"), "rev-parse", "HEAD"],
            text=True,
        ).strip()
        if revision != contract["frameworks_av_revision"]:
            raise RuntimeError(f"frameworks/av revision changed: {revision}")
        manifest = subprocess.check_output(
            ["git", "-C", str(self.args.aosp / ".repo/manifests"), "rev-parse", "HEAD"],
            text=True,
        ).strip()
        if manifest != contract["manifest_commit"]:
            raise RuntimeError(f"manifest revision changed: {manifest}")
        overlay = REPO / contract["overlay"]
        state = subprocess.check_output(
            [str(overlay / "prepare.sh"), "check", str(self.args.aosp)], text=True
        )
        if "source state: PATCHED" not in state:
            raise RuntimeError("diag2 crop overlay is not exactly applied")
        acodec = self.args.aosp / "frameworks/av/media/libstagefright/ACodec.cpp"
        self.require(acodec, {"size": acodec.stat().st_size,
                             "sha256": contract["acodec_diag2_sha256"]}, "diag2 ACodec")

        runtime = self.diag2["runtime_delta"]
        new_lib = Path(runtime["source_path"])
        self.require(new_lib, runtime["candidate"], "built diag2 libstagefright64")
        old_lib = source("out/candidates/a16-prototype-b-r7-diag1a/diag1a-libstagefright64")
        before = DIAG1.elf_contract(old_lib)
        after = DIAG1.elf_contract(new_lib)
        for field in ("elf_class", "architecture", "soname", "dt_needed",
                      "strong_exports"):
            if before[field] != after[field]:
                raise RuntimeError(f"libstagefright ELF contract changed: {field}")
        if strong_undefined(old_lib) != strong_undefined(new_lib):
            raise RuntimeError("libstagefright undefined strong imports changed")
        data = new_lib.read_bytes()
        if b"UBOX_R7_DIAG1" not in data or b"OMX.allwinner.video.decoder.hevc" not in data:
            raise RuntimeError("diag2 libstagefright lost instrumentation or exact component guard")

        for path, record in self.diag2["preserved_runtime"].items():
            preserved = source(record["path"])
            self.require(preserved, record, f"preserved diag1a runtime {path}")
        surfaceflinger = source(
            self.diag2["preserved_runtime"]["/system/bin/surfaceflinger"]["path"]
        )
        if b"Failed to create a valid texture." not in surfaceflinger.read_bytes():
            raise RuntimeError("original RenderEngine fatal is absent")

        diag1a = REPO / "out/candidates/a16-prototype-b-r7-diag1a"
        shutil.copytree(diag1a / "kernel-evidence", self.stage / "kernel-evidence")
        for name in ("final-build-variables.txt", "mali-intake.json",
                     "active-product-build.prop.r5", "runtime-product-source-audit.json",
                     "boringssl_self_test64"):
            shutil.copyfile(diag1a / name, self.stage / name)
        shutil.copyfile(old_lib, self.stage / "diag1a-libstagefright64")
        for name in ("surfaceflinger", "gralloc32", "gralloc64"):
            shutil.copyfile(diag1a / f"diag1a-{name}", self.stage / f"diag2-{name}")

    def replace_libstagefright(self, system: Path) -> dict[str, object]:
        runtime = self.diag2["runtime_delta"]
        internal = "/system/lib64/libstagefright.so"
        parent = str(Path(internal).parent)
        parent_times = self.inode_times(self.debugfs(system, f"stat {parent}", capture=True))
        old = self.stage / "installed-diag1a-libstagefright64"
        new = self.stage / "diag2-libstagefright64"
        self.debugfs(system, f"dump -p {internal} {old}")
        self.require(old, runtime["base"], "installed diag1a libstagefright64")
        old_elf = DIAG1.elf_contract(old)
        new_elf = DIAG1.elf_contract(Path(runtime["source_path"]))
        for field in ("elf_class", "architecture", "soname", "dt_needed",
                      "strong_exports"):
            if old_elf[field] != new_elf[field]:
                raise RuntimeError(f"installed libstagefright contract changed: {field}")
        if strong_undefined(old) != strong_undefined(Path(runtime["source_path"])):
            raise RuntimeError("installed libstagefright undefined strong imports changed")
        self.debugfs(system, f"rm {internal}")
        self.debugfs(system, f"write {runtime['source_path']} {internal}")
        self.debugfs(system, f"set_inode_field {internal} mode 010{runtime['mode']}")
        self.debugfs(system, f"set_inode_field {internal} uid {runtime['uid']}")
        self.debugfs(system, f"set_inode_field {internal} gid {runtime['gid']}")
        for field in ("ctime", "atime", "mtime", "crtime"):
            self.debugfs(system, f"set_inode_field {internal} {field} {runtime[field]}")
        self.debugfs(system, f'ea_set {internal} security.selinux "{runtime["selinux"]}\\000"')
        self.restore_times(system, parent, parent_times)
        self.debugfs(system, f"dump -p {internal} {new}")
        self.require(new, runtime["candidate"], "installed diag2 libstagefright64")
        return {
            "partition_path": internal,
            "diag1a": SHARED.record(old),
            "diag2": SHARED.record(new),
            "elf_class": runtime["elf_class"],
            "architecture": runtime["architecture"],
            "soname_preserved": True,
            "dt_needed_preserved": True,
            "strong_exports_preserved": True,
            "undefined_strong_imports_preserved": True,
            "semantic_reason": "exact HEVC 1920x1080 visible crop retained across 1920x1088 coded alignment",
        }

    def prepare_system(self) -> tuple[Path, dict[str, object]]:
        record = self.diag2["base_artifacts"]["system_a"]
        original = source(record["path"])
        system = self.stage / "system_a.img"
        shutil.copyfile(original, system)
        self.require(system, record, "exact diag1a system_a")
        with self.deterministic_ext4_time():
            self.run([sys.executable, str(self.avbtool), "erase_footer", "--image", str(system)])
            self.run(["e2fsck", "-fn", str(system)])
            replacement = self.replace_libstagefright(system)
            self.run(["e2fsck", "-fy", str(system)], allowed={0, 1})
            self.run(["e2fsck", "-fn", str(system)])
        avb = self.cfg["avb"]["system"]
        self.run([
            sys.executable, str(self.avbtool), "add_hashtree_footer", "--image", str(system),
            "--partition_name", "system", "--partition_size", str(avb["partition_size"]),
            "--hash_algorithm", "sha256", "--salt", avb["salt"], "--do_not_generate_fec",
            "--prop", f"com.ubox10.candidate.id:{self.candidate_id}",
            "--prop", "com.ubox10.avb.fec:none", "--key", str(REPO / avb["key_relative"]),
            "--algorithm", avb["algorithm"],
        ])
        self.verify_avb_partition(system, "system", avb["key_relative"])
        return system, {
            "base_diag1a": SHARED.record(original), "candidate": SHARED.record(system),
            "tree_delta": {"added": [], "removed": [],
                           "changed": ["system/lib64/libstagefright.so"]},
            "replaced": {"libstagefright64": replacement},
            "ext4": "PASS", "avb_hashtree_no_fec": "PASS",
        }

    def prepare_vendor(self) -> tuple[Path, dict[str, object]]:
        record = self.diag2["base_artifacts"]["vendor_a"]
        original = source(record["path"])
        vendor = self.stage / "vendor_a.img"
        shutil.copyfile(original, vendor)
        self.require(vendor, record, "byte-identical diag1a vendor_a")
        return vendor, {"base_diag1a": SHARED.record(original),
                        "candidate": SHARED.record(vendor),
                        "byte_preserved_from_diag1a": True,
                        "tree_delta": {"added": [], "removed": [], "changed": []}}

    def make_vbmeta(self, image: Path, partition: str) -> Path:
        if partition == "vendor":
            record = self.diag2["base_artifacts"]["vbmeta_vendor"]
            output = self.stage / "vbmeta_vendor.fex"
            shutil.copyfile(source(record["path"]), output)
            self.require(output, record, "byte-identical diag1a vbmeta_vendor")
            return output
        return SHARED.Builder.make_vbmeta(self, image, partition)

    def build_super(self, system: Path, vendor: Path) -> tuple[Path, dict[str, object]]:
        record = self.diag2["base_artifacts"]["super_raw"]
        original = source(record["path"])
        candidate = self.stage / "super.raw.img"
        self.run(["cp", "--reflink=auto", str(original), str(candidate)])
        old_text = self.stage / "diag1a-lpdump.txt"
        self.run([str(self.host / "lpdump"), str(original)], output=old_text)
        extents = DIAG1.lpdump_linear_extents(old_text.read_text(encoding="utf-8"))
        system_extents = extents["system_a"]
        capacity = sum(end - start for start, end in system_extents) * 512
        if capacity != system.stat().st_size:
            raise RuntimeError("system bytes do not fill frozen diag1a extents")
        with candidate.open("r+b", buffering=0) as output, system.open("rb", buffering=0) as src:
            for start, end in system_extents:
                remaining = (end - start) * 512
                output.seek(start * 512)
                while remaining:
                    chunk = src.read(min(8 * 1024 * 1024, remaining))
                    if not chunk:
                        raise RuntimeError("short read while copying diag2 system")
                    output.write(chunk)
                    remaining -= len(chunk)
            if src.read(1):
                raise RuntimeError("trailing diag2 system bytes")
        old_json = self.stage / "diag1a-lpdump.json"
        new_json = self.stage / "candidate-lpdump.json"
        slot1 = self.stage / "candidate-lpdump-slot1.json"
        self.run([str(self.host / "lpdump"), "-j", str(original)], output=old_json)
        self.run([str(self.host / "lpdump"), "-j", str(candidate)], output=new_json)
        self.run([str(self.host / "lpdump"), "-s", "1", "-j", str(candidate)], output=slot1)
        base_meta = json.loads(old_json.read_text())
        if base_meta != json.loads(new_json.read_text()) or base_meta != json.loads(slot1.read_text()):
            raise RuntimeError("diag2 changed LP metadata/extents")
        sparse = self.stage / "super.fex"
        roundtrip = self.stage / "super-sparse-roundtrip.raw.img"
        self.run([str(self.host / "img2simg"), str(candidate), str(sparse), "4096"])
        self.run([str(self.host / "simg2img"), str(sparse), str(roundtrip)])
        if SHARED.digest(roundtrip) != SHARED.digest(candidate):
            raise RuntimeError("diag2 sparse roundtrip changed bytes")
        roundtrip.unlink()
        extracted = self.stage / "candidate-logical"
        extracted.mkdir()
        self.run([str(self.host / "lpunpack"), str(candidate), str(extracted)])
        expected = {"system_a": system, "vendor_a": vendor,
                    "product_a": source(self.diag2["base_artifacts"]["product_a"]["path"]),
                    "vendor_dlkm_a": source(self.diag2["base_artifacts"]["vendor_dlkm"]["path"])}
        logical = {}
        for name, expected_path in expected.items():
            path = extracted / f"{name}.img"
            self.require(path, SHARED.record(expected_path), f"diag2 logical {name}")
            logical[name] = SHARED.record(path)
        for name in ("system_b", "vendor_b", "product_b", "vendor_dlkm_b"):
            path = extracted / f"{name}.img"
            if path.stat().st_size != 0:
                raise RuntimeError(f"diag2 changed empty partition {name}")
            logical[name] = SHARED.record(path)
        # system_a is already retained at candidate root; keep only the compact
        # detached vendor/product inputs needed by the standard offline auditor.
        (extracted / "system_a.img").unlink()
        return sparse, {"base_diag1a_raw": SHARED.record(original),
                        "candidate_raw": SHARED.record(candidate),
                        "candidate_sparse": SHARED.record(sparse),
                        "lp_metadata_and_extents_exact_diag1a": True,
                        "system_written_to_frozen_extents": [list(x) for x in system_extents],
                        "bytes_outside_system_extents_exact_diag1a": True,
                        "sparse_roundtrip_exact": True, "logical": logical}

    def pack_outer(self, super_sparse: Path, vbmeta_system: Path,
                   vbmeta_vendor: Path) -> tuple[Path, dict[str, object]]:
        before = PACK.outer_payloads(self.base)
        firmware = self.stage / f"x12-{self.candidate_id}.img"
        audit = self.stage / "outer-payload-audit.json"
        self.run([sys.executable, str(REPO / "tools/pack_image_preserving.py"),
                  "--source", str(self.base), "--output", str(firmware),
                  "--replace", f"super.fex={super_sparse}",
                  "--replace", f"vbmeta_system.fex={vbmeta_system}",
                  "--audit", str(audit)])
        self.run([sys.executable, str(REPO / "tools/sunxi_image_tool.py"),
                  "verify", str(firmware)], output=self.stage / "candidate-outer-verify.log")
        after = PACK.outer_payloads(firmware)
        changed = sorted(name for name in before
                         if before[name]["sha256_stored"] != after[name]["sha256_stored"])
        expected = sorted(self.diag2["outer_delta"]["changed_payloads_from_base"])
        if set(before) != set(after) or len(after) != 50 or changed != expected:
            raise RuntimeError(f"unexpected diag2 outer delta: {changed}")
        return firmware, {"candidate": SHARED.record(firmware), "entry_count": 50,
                          "changed_payloads": changed, "preserved_payload_count": 46,
                          "all_other_payload_bytes_exact_diag1a": True,
                          "imagewty_verify": "PASS",
                          "boot_payload_byte_preserved": before["boot.fex"] == after["boot.fex"],
                          "vbmeta_vendor_byte_preserved": before["vbmeta_vendor.fex"] == after["vbmeta_vendor.fex"]}

    def finish(self, firmware: Path, system_audit: dict[str, object],
               vendor_audit: dict[str, object], super_audit: dict[str, object],
               outer_audit: dict[str, object], vbmeta_system: Path,
               vbmeta_vendor: Path) -> None:
        for name, key in (("boot.fex", "boot"), ("vendor_dlkm_a.img", "vendor_dlkm")):
            shutil.copyfile(source(self.diag2["base_artifacts"][key]["path"]), self.stage / name)
        result = {
            "schema": 1, "id": self.candidate_id, "label": self.diag2["label"],
            "status": "PACKAGED_AWAITING_FULL_OFFLINE_AUDIT",
            "decision": "PENDING_FULL_OFFLINE_AUDIT", "physical_status": "NOT_YET_VALIDATED",
            "physical_device_actions_performed": False, "flash_authorized": False,
            "elapsed_seconds": round(time.time() - self.started, 1),
            "source": {**self.diag2["source_contract"],
                       "targeted_modules_built": ["libstagefright"],
                       "packaged_architecture": "AArch64_ONLY", "kernel_rebuilt": False},
            "base_diag1a": SHARED.record(self.base), "firmware": SHARED.record(firmware),
            "system": system_audit, "vendor": vendor_audit, "super": super_audit,
            "outer": outer_audit, "vbmeta_system": SHARED.record(vbmeta_system),
            "vbmeta_vendor": SHARED.record(vbmeta_vendor),
            "boot": {"candidate": SHARED.record(self.stage / "boot.fex"),
                     "byte_preserved_from_diag1a": True},
            "vendor_dlkm": {"candidate": SHARED.record(self.stage / "vendor_dlkm_a.img"),
                            "byte_preserved_from_diag1a": True, "module_count": 22},
            "kernel": SHARED.record(self.stage / "kernel-evidence/Image"),
            "semantic_delta": self.diag2["semantic_delta"],
            "preserved_runtime": self.diag2["preserved_runtime"],
            "governance": self.diag2["governance"],
        }
        result = SHARED.rewrite_paths(result, self.stage, self.final)
        (self.stage / "build-result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        sums = [f"{SHARED.digest(path)}  {path.name}" for path in sorted(self.stage.iterdir())
                if path.is_file() and path.name != "SHA256SUMS"]
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
