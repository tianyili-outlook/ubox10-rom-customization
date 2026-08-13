#!/usr/bin/env python3
"""Build the narrowly-scoped, preservation-oriented M8A candidate.

This script is intentionally Windows-hosted: the checked-in Windows LP/sparse
tools assemble the super image, while WSL is used only to copy immutable AOSP
outputs and mount staging copies of ext4 images.
"""
from __future__ import annotations

import argparse
import hashlib
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
TOOLS = REPO / "tools"
DEFAULT_CONFIG = REPO / "configs" / "candidates" / "m8a-initial-atv-r1.json"
CHUNK = 8 * 1024 * 1024
AVB_PUBLICATION_SUMMARY = (
    "dm-verity enabled; flags 0; rebuilt system/product omit FEC "
    "(corruption recovery unavailable); retained stock vendor/vendor_dlkm retain stock FEC."
)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(CHUNK), b""):
            h.update(part)
    return h.hexdigest().upper()


def record(path: Path) -> dict:
    return {"path": str(path), "size": path.stat().st_size, "sha256": digest(path)}


def rewrite_published_paths(value: object, *, stage: Path, final: Path,
                            aosp_wsl_directory: str, provenance: bool = False) -> object:
    """Publish staging references as stable candidate or canonical WSL paths."""
    if isinstance(value, dict):
        return {rewrite_published_paths(key, stage=stage, final=final,
                                        aosp_wsl_directory=aosp_wsl_directory, provenance=provenance):
                rewrite_published_paths(item, stage=stage, final=final,
                                        aosp_wsl_directory=aosp_wsl_directory, provenance=provenance)
                for key, item in value.items()}
    if isinstance(value, list):
        return [rewrite_published_paths(item, stage=stage, final=final,
                                        aosp_wsl_directory=aosp_wsl_directory, provenance=provenance)
                for item in value]
    if not isinstance(value, str):
        return value
    aosp_prefix = str(stage / "inputs" / "aosp")
    if provenance and value.startswith(aosp_prefix):
        suffix = value[len(aosp_prefix):].lstrip("\\/").replace("\\", "/")
        return "wsl:" + aosp_wsl_directory.rstrip("/") + "/" + suffix
    artifacts_prefix = str(stage / "artifacts")
    if value.startswith(artifacts_prefix):
        suffix = value[len(artifacts_prefix):].lstrip("\\/")
        return str(final / suffix)
    return value.replace(str(stage), str(final))


class Build:
    def __init__(self, cfg: dict, keep_failed: bool) -> None:
        self.cfg = cfg
        self.keep_failed = keep_failed
        self.stock_root = (REPO / cfg["stock_root"]).resolve()
        self.final = REPO / "out" / "candidates" / cfg["id"]
        self.stage = self.final.parent / ("." + cfg["id"] + ".staging-" + uuid.uuid4().hex)
        self.log_file = self.stage / "logs" / "01-commands.log"
        self.before: dict[str, dict] = {}
        self.protected: dict[str, Path] = {}

    def log(self, text: str) -> None:
        print(text, flush=True)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with self.log_file.open("a", encoding="utf-8") as f:
            f.write(text + "\n")

    def run(self, cmd: list[str], cwd: Path | None = None) -> None:
        self.log("$ " + subprocess.list2cmdline(cmd))
        with self.log_file.open("a", encoding="utf-8") as f:
            done = subprocess.run(cmd, cwd=cwd, stdout=f, stderr=subprocess.STDOUT, text=True)
        if done.returncode:
            raise RuntimeError("failed command: " + cmd[0])

    def tool(self, name: str) -> Path:
        path = TOOLS / name
        if not path.is_file():
            raise RuntimeError("missing tool: " + str(path))
        return path

    def wsl_path(self, path: Path) -> str:
        # Avoid routing a Unicode Windows path through the active console code
        # page (which makes ``wslpath`` fail for this repository's name).
        absolute = path.resolve()
        if not absolute.drive or len(absolute.drive) != 2 or absolute.drive[1] != ":":
            raise RuntimeError("cannot map non-drive path to WSL: " + str(absolute))
        return "/mnt/" + absolute.drive[0].lower() + absolute.as_posix()[2:]

    def wsl_script(self, name: str, text: str) -> None:
        script = self.stage / "scripts" / name
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(text, encoding="utf-8", newline="\n")
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "bash", self.wsl_path(script)])

    def protect(self, path: Path, size: int | None = None, sha: str | None = None) -> None:
        if not path.is_file():
            raise RuntimeError("missing protected input: " + str(path))
        value = record(path)
        if size is not None and value["size"] != size:
            raise RuntimeError("size mismatch: " + str(path))
        if sha is not None and value["sha256"] != sha:
            raise RuntimeError("SHA256 mismatch: " + str(path) + ": " + value["sha256"])
        self.protected[str(path)] = path
        self.before[str(path)] = value

    def setup(self) -> None:
        if self.final.exists():
            raise RuntimeError("refusing to overwrite final output: " + str(self.final))
        self.stage.mkdir(parents=True)
        stock = self.stock_root / self.cfg["stock_container"]
        self.protect(stock, self.cfg["stock_container_size"], self.cfg["stock_container_sha256"])
        extracted = self.stock_root / "firmware" / "extracted"
        caches = self.stock_root / "out"
        locked = {
            "vbmeta.fex": extracted / "vbmeta.fex",
            "vbmeta_vendor.fex": extracted / "vbmeta_vendor.fex",
            "boot.fex": extracted / "boot.fex",
            "dtbo.fex": extracted / "dtbo.fex",
            "vendor_boot.fex": extracted / "vendor_boot.fex",
            "vendor_a.img": caches / "official-vendor-a" / "20260726-r1" / "vendor_a.img",
            "vendor_dlkm_a.img": caches / "official-vendor-dlkm-a" / "20260726-r1" / "vendor_dlkm_a.img",
        }
        expected = {
            "vendor_a.img": (119066624, "BB91A8B7ED4AC0145F434F89FD76865EB4311F234AA46D67C8373A7CD5B4929A"),
            "vendor_dlkm_a.img": (6680576, "C589DC0B12E150469F179738F127F36F6321943577453A7DB335AB9E647B8FE5"),
        }
        for name, path in locked.items():
            self.protect(path, *expected.get(name, (None, None)))
        rollback = caches / "candidates" / "test8r2-restore-contacts-provider-r1" / "x12-test8r2-restore-contacts-provider.img"
        self.protect(rollback, 2005954560, "6A52F3388E9ABF6AFA8A701CFD7198FE6C0090F16531F6E3BD3949E760892EC8")
        key = self.tool("testkey_rsa2048.pem")
        self.protect(key)
        local = self.stage / "inputs" / "stock"
        local.mkdir(parents=True)
        for name, path in locked.items():
            shutil.copyfile(path, local / name)
        shutil.copyfile(key, self.stage / "inputs" / key.name)
        aosp_local = self.stage / "inputs" / "aosp"
        aosp_local.mkdir()
        remote = self.cfg["aosp_wsl_directory"]
        lines = ["set -euo pipefail", "umask 077"]
        for name, spec in self.cfg["aosp"].items():
            source = remote + "/" + name + ".img"
            target = self.wsl_path(aosp_local / (name + ".img"))
            lines += [
                "test -f '" + source + "'",
                "test \"$(stat -c %s '" + source + "')\" = '" + str(spec["size"]) + "'",
                "test \"$(sha256sum '" + source + "' | awk '{print toupper($1)}')\" = '" + spec["sha256"] + "'",
                "cp --preserve=mode,timestamps '" + source + "' '" + target + "'",
            ]
        self.wsl_script("copy-aosp-inputs.sh", "\n".join(lines) + "\n")
        for name, spec in self.cfg["aosp"].items():
            self.protect(aosp_local / (name + ".img"), spec["size"], spec["sha256"])
        (self.stage / "input-provenance-before.json").write_text(json.dumps(self.before, indent=2) + "\n", encoding="utf-8")

    def verify_aosp_sources_after(self) -> None:
        """Re-hash the immutable WSL AOSP sources after candidate assembly."""
        remote = self.cfg["aosp_wsl_directory"]
        lines = ["set -euo pipefail"]
        for name, spec in self.cfg["aosp"].items():
            source = remote + "/" + name + ".img"
            lines += [
                "test \"$(stat -c %s '" + source + "')\" = '" + str(spec["size"]) + "'",
                "test \"$(sha256sum '" + source + "' | awk '{print toupper($1)}')\" = '" + spec["sha256"] + "'",
            ]
        self.wsl_script("verify-aosp-inputs-after.sh", "\n".join(lines) + "\n")

    def make_logical_images(self) -> tuple[Path, Path]:
        raw = self.stage / "raw"
        raw.mkdir()
        sparse = self.stage / "inputs" / "aosp"
        system, product, ext = (raw / "system_a.raw.img", raw / "product_a.raw.img", raw / "system_ext.raw.img")
        for src, dst in ((sparse / "system.img", system), (sparse / "product.img", product), (sparse / "system_ext.img", ext)):
            self.run([str(self.tool("simg2img.exe")), str(src), str(dst)])
        # The source system_ext is mounted read-only; system is a staging copy
        # mounted writable. resize2fs -M leaves room for AVB's final tree.
        target, source_ext, mounts = self.wsl_path(system), self.wsl_path(ext), self.wsl_path(raw / "mounts")
        merge = """set -euo pipefail
target='%s'
source_ext='%s'
mounts='%s'
target_mount="$mounts/target"
ext_mount="$mounts/ext"
cleanup() { umount "$target_mount" 2>/dev/null || true; umount "$ext_mount" 2>/dev/null || true; rmdir "$target_mount" "$ext_mount" 2>/dev/null || true; }
trap cleanup EXIT INT TERM
mkdir -p "$target_mount" "$ext_mount"
e2fsck -fy "$target"
resize2fs -M "$target"
# The minimized source is about 574 MiB.  Grow only this staging copy before
# merging the 256 MiB system_ext filesystem, then minimize again below so AVB
# retains ample room for its hashtree in the fixed logical partition.
resize2fs "$target" 1500M
mount -o loop,rw "$target" "$target_mount"
mount -o loop,ro "$source_ext" "$ext_mount"
test "$(readlink "$target_mount/system/system_ext")" = /system_ext
mkdir -p "$target_mount/system_ext"
cp -a --preserve=all "$ext_mount"/. "$target_mount/system_ext"/
sync
umount "$ext_mount"; umount "$target_mount"
bash "%s" "$target" "$target_mount"
e2fsck -fy "$target"
resize2fs -M "$target"
debugfs -R 'stat /system/system_ext' "$target" | grep -q 'Fast link dest: "/system_ext"'
""" % (target, source_ext, mounts, self.wsl_path(REPO / "scripts" / "fix-m8-system-vendor-topology.sh"))
        self.wsl_script("merge-system-ext.sh", merge)
        check_product = """set -euo pipefail
image='%s'
e2fsck -fy "$image"
resize2fs -M "$image"
e2fsck -fy "$image"
""" % self.wsl_path(product)
        self.wsl_script("check-product.sh", check_product)
        return system, product

    def avb(self, *args: str, cwd: Path | None = None) -> None:
        self.run([sys.executable, str(self.tool("avbtool.py")), *args], cwd=cwd)

    def avb_wsl(self, *args: str) -> None:
        """Run AVB verification in WSL, where OpenSSL is available."""
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "python3",
                  self.wsl_path(self.tool("avbtool.py")), *args])

    @staticmethod
    def assert_preserved_outer_prefix(source: Path, output: Path) -> None:
        """Only IMAGEWTY's uint32 image_size (24..27) may change in prefix."""
        with source.open("rb") as old, output.open("rb") as new:
            old_prefix, new_prefix = old.read(1024), new.read(1024)
        if len(old_prefix) != 1024 or len(new_prefix) != 1024:
            raise RuntimeError("truncated IMAGEWTY pre-file-header prefix")
        differences = [index for index, pair in enumerate(zip(old_prefix, new_prefix))
                       if pair[0] != pair[1]]
        if any(index < 24 or index > 27 for index in differences):
            raise RuntimeError("IMAGEWTY prefix changed outside image_size: " +
                               ",".join(str(index) for index in differences[:16]))

    def stock_public_blob(self, source: Path, destination: Path) -> None:
        spec = importlib.util.spec_from_file_location("candidate_avbtool", self.tool("avbtool.py"))
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        data = source.read_bytes()
        header = module.AvbVBMetaHeader(data[:256])
        start = 256 + header.authentication_data_block_size + header.public_key_offset
        destination.write_bytes(data[start:start + header.public_key_size])

    def sign_and_make_super(self, system: Path, product: Path) -> tuple[Path, Path, Path, Path]:
        signed = self.stage / "signed"
        artifacts = self.stage / "artifacts"
        signed.mkdir()
        artifacts.mkdir()
        logical = self.cfg["logical_partitions"]
        key = self.stage / "inputs" / "testkey_rsa2048.pem"
        salt = self.cfg["hash_tree"]["salt"]
        output: list[Path] = []
        for source, name, avb_name, size in ((system, "system_a", "system", logical["system_a"]), (product, "product_a", "product", logical["product_a"])):
            image = signed / (name + ".img")
            shutil.copyfile(source, image)
            self.avb("add_hashtree_footer", "--image", str(image), "--partition_name", avb_name,
                     "--partition_size", str(size), "--hash_algorithm", "sha256", "--salt", salt,
                     "--do_not_generate_fec", "--prop", "com.ubox10.candidate.id:m8a-initial-atv-r1",
                     "--prop", "com.ubox10.avb.fec:none", "--key", str(key), "--algorithm", "SHA256_RSA2048")
            if image.stat().st_size != size:
                raise RuntimeError("AVB result does not fill partition: " + str(image))
            sparse = artifacts / (name + ".img")
            self.run([str(self.tool("img2simg.exe")), str(image), str(sparse)])
            output.append(image)
        stock = self.stage / "inputs" / "stock"
        super_image = artifacts / "super.img"
        s = self.cfg["super"]
        args = [str(self.tool("lpmake.exe")), "--metadata-size", str(s["metadata_size"]), "--metadata-slots", str(s["slots"]),
                "--super-name", "super", "--device-size", str(s["device_size"]), "--alignment", str(s["alignment"]),
                "--virtual-ab", "--group", "sb_a:" + str(s["group_size"]), "--group", "sb_b:" + str(s["group_size"])]
        images = {"system_a": output[0], "vendor_a": stock / "vendor_a.img", "product_a": output[1], "vendor_dlkm_a": stock / "vendor_dlkm_a.img"}
        for name, size in logical.items():
            args += ["--partition", name + ":readonly:" + str(size) + ":sb_a", "--image", name + "=" + str(images[name])]
            args += ["--partition", name[:-1] + "b:readonly:0:sb_b"]
        args += ["--sparse", "--output", str(super_image)]
        self.run(args)
        return output[0], output[1], super_image, artifacts

    def make_vbmeta(self, system: Path, product: Path, artifacts: Path) -> tuple[Path, Path]:
        stock = self.stage / "inputs" / "stock"
        key = self.stage / "inputs" / "testkey_rsa2048.pem"
        test_blob, stock_blob = artifacts / "testkey_rsa2048.avbpubkey", artifacts / "stock-vbmeta-vendor.avbpubkey"
        self.avb("extract_public_key", "--key", str(key), "--output", str(test_blob))
        self.stock_public_blob(stock / "vbmeta_vendor.fex", stock_blob)
        if test_blob.stat().st_size != 520 or stock_blob.stat().st_size != 520:
            raise RuntimeError("AVB public-key blob length is not 520")
        if digest(stock_blob) != "525EB7A9E64E805A270C3210FF53155211242725F0226DDA084324BD1F27CE6A":
            raise RuntimeError("stock vbmeta_vendor AVB public-key blob mismatch")
        system_meta = artifacts / "vbmeta_system.img"
        self.avb("make_vbmeta_image", "--output", str(system_meta), "--key", str(key), "--algorithm", "SHA256_RSA2048",
                 "--rollback_index", str(self.cfg["rollback"]["vbmeta_system"]), "--rollback_index_location", "1",
                 "--include_descriptors_from_image", str(system))
        root = artifacts / "vbmeta.img"
        self.avb("make_vbmeta_image", "--output", str(root), "--key", str(key), "--algorithm", "SHA256_RSA2048",
                 "--rollback_index", "0", "--flags", "0",
                 "--chain_partition", "vbmeta_system:1:" + test_blob.name,
                 "--chain_partition", "vbmeta_vendor:2:" + stock_blob.name,
                 "--include_descriptors_from_image", str(stock / "boot.fex"),
                 "--include_descriptors_from_image", str(stock / "dtbo.fex"),
                 "--include_descriptors_from_image", str(stock / "vendor_boot.fex"),
                 "--include_descriptors_from_image", str(product),
                 "--include_descriptors_from_image", str(stock / "vendor_dlkm_a.img"), cwd=artifacts)
        return root, system_meta

    def validate_and_pack(self, super_image: Path, root: Path, system_meta: Path, artifacts: Path) -> None:
        validation_raw = self.stage / "validation-super.raw.img"
        self.run([str(self.tool("simg2img.exe")), str(super_image), str(validation_raw)])
        metadata = subprocess.check_output([str(self.tool("lpdumps.exe")), "-j", str(validation_raw)], text=True, encoding="utf-8")
        (artifacts / "super-metadata.json").write_text(metadata, encoding="utf-8")
        # avbtool verifies included descriptors by looking for conventional
        # partition filenames beside the supplied vbmeta image.  Build a
        # disposable, hard-linked validation view; this neither copies nor
        # opens any immutable source writable.
        view = self.stage / "avb-validation"
        view.mkdir()
        stock = self.stage / "inputs" / "stock"
        links = {
            "system.img": self.stage / "signed" / "system_a.img",
            "product.img": self.stage / "signed" / "product_a.img",
            "vendor.img": stock / "vendor_a.img",
            "vendor_dlkm.img": stock / "vendor_dlkm_a.img",
            "boot.img": stock / "boot.fex",
            "dtbo.img": stock / "dtbo.fex",
            "vendor_boot.img": stock / "vendor_boot.fex",
            "vbmeta.img": root,
            "vbmeta_system.img": system_meta,
            "vbmeta_vendor.img": stock / "vbmeta_vendor.fex",
        }
        for name, source in links.items():
            os.link(source, view / name)
        key = self.stage / "inputs" / "testkey_rsa2048.pem"
        self.avb_wsl("verify_image", "--image", self.wsl_path(view / "vbmeta_system.img"), "--key", self.wsl_path(key))
        self.avb_wsl("verify_image", "--image", self.wsl_path(view / "vbmeta_vendor.img"))
        self.avb_wsl("verify_image", "--image", self.wsl_path(view / "vbmeta.img"), "--key", self.wsl_path(key),
                     "--expected_chain_partition", "vbmeta_system:1:" + self.wsl_path(artifacts / "testkey_rsa2048.avbpubkey"),
                     "--expected_chain_partition", "vbmeta_vendor:2:" + self.wsl_path(artifacts / "stock-vbmeta-vendor.avbpubkey"))
        firmware = self.stage / ("x12-" + self.cfg["id"] + ".img")
        self.run([sys.executable, str(self.tool("pack_image_preserving.py")), "--source", str(self.stock_root / self.cfg["stock_container"]),
                  "--output", str(firmware), "--replace", "super.fex=" + str(super_image),
                  "--replace", "vbmeta.fex=" + str(root), "--replace", "vbmeta_system.fex=" + str(system_meta),
                  "--audit", str(self.stage / "outer-payload-audit.json")])
        self.assert_preserved_outer_prefix(self.stock_root / self.cfg["stock_container"], firmware)
        self.run([sys.executable, str(self.tool("sunxi_image_tool.py")), "verify", str(firmware)])
        self.verify_aosp_sources_after()
        after = {name: record(path) for name, path in self.protected.items()}
        if after != self.before:
            raise RuntimeError("protected input changed during assembly")
        (self.stage / "input-provenance-after.json").write_text(json.dumps(after, indent=2) + "\n", encoding="utf-8")
        usage = sum(self.cfg["logical_partitions"].values())
        (self.stage / "partition-manifest.json").write_text(json.dumps({
            "super": record(super_image), "system_a": record(artifacts / "system_a.img"),
            "product_a": record(artifacts / "product_a.img"), "group_a_usage": usage,
            "group_a_free": self.cfg["super"]["group_size"] - usage}, indent=2) + "\n", encoding="utf-8")
        (self.stage / "rollback-metadata.json").write_text(json.dumps({
            "reference_only": record(self.stock_root / "out" / "candidates" / "test8r2-restore-contacts-provider-r1" / "x12-test8r2-restore-contacts-provider.img"),
            "candidate_rollback_indexes": self.cfg["rollback"],
            "risk": "The testkey root differs from stock trust; offline validation cannot prove device acceptance."}, indent=2) + "\n", encoding="utf-8")

    def finish(self) -> None:
        # Keep useful sparse/signature evidence, never raw or mounted staging state.
        artifacts = self.stage / "artifacts"
        shutil.copyfile(self.log_file, artifacts / "01-commands.log")
        for path in artifacts.iterdir():
            shutil.move(str(path), self.stage / path.name)
        for transient in ("raw", "signed", "inputs", "scripts", "logs", "artifacts", "avb-validation"):
            shutil.rmtree(self.stage / transient, ignore_errors=True)
        (self.stage / "validation-super.raw.img").unlink(missing_ok=True)
        firmware = self.stage / ("x12-" + self.cfg["id"] + ".img")
        (self.stage / "build-result.json").write_text(json.dumps({
            "id": self.cfg["id"], "status": "BUILT", "firmware": record(firmware),
            "avb": AVB_PUBLICATION_SUMMARY,
            "source_after_unchanged": True}, indent=2) + "\n", encoding="utf-8")
        # The package is staged under a randomized name, but published records
        # must point at the final, stable candidate directory.
        for metadata in ("build-result.json", "partition-manifest.json", "outer-payload-audit.json",
                         "input-provenance-before.json", "input-provenance-after.json"):
            path = self.stage / metadata
            path.write_text(json.dumps(rewrite_published_paths(
                json.loads(path.read_text(encoding="utf-8")), stage=self.stage, final=self.final,
                aosp_wsl_directory=self.cfg["aosp_wsl_directory"],
                provenance=metadata.startswith("input-provenance")), indent=2) + "\n", encoding="utf-8")
        sums = [digest(p) + "  " + p.name for p in sorted(self.stage.iterdir())
                if p.is_file() and p.name != "SHA256SUMS"]
        (self.stage / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
        os.replace(self.stage, self.final)

    def build(self) -> None:
        started = time.time()
        try:
            self.setup()
            system, product = self.make_logical_images()
            signed_system, signed_product, super_image, artifacts = self.sign_and_make_super(system, product)
            root, system_meta = self.make_vbmeta(signed_system, signed_product, artifacts)
            self.validate_and_pack(super_image, root, system_meta, artifacts)
            self.finish()
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
    Build(json.loads(args.config.read_text(encoding="utf-8")), args.keep_failed).build()


if __name__ == "__main__":
    main()
