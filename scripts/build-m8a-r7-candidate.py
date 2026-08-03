#!/usr/bin/env python3
"""Build r7: add the missing /metadata switch-root destination to system_a."""
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
DEFAULT_CONFIG = REPO / "configs" / "candidates" / "m8a-initial-atv-r7.json"
CHUNK = 8 * 1024 * 1024


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(CHUNK), b""):
            value.update(block)
    return value.hexdigest().upper()


def record(path: Path) -> dict[str, object]:
    return {"path": str(path), "size": path.stat().st_size, "sha256": digest(path)}


def rewrite_paths(value: object, stage: Path, final: Path) -> object:
    if isinstance(value, dict):
        return {key: rewrite_paths(item, stage, final) for key, item in value.items()}
    if isinstance(value, list):
        return [rewrite_paths(item, stage, final) for item in value]
    return value.replace(str(stage), str(final)) if isinstance(value, str) else value


class BuildR7:
    def __init__(self, config: dict[str, object], keep_failed: bool) -> None:
        self.config, self.keep_failed = config, keep_failed
        self.candidate_id = str(config["id"])
        self.final = REPO / "out" / "candidates" / self.candidate_id
        self.stage = self.final.parent / ("." + self.candidate_id + ".staging-" + uuid.uuid4().hex)
        self.log_file = self.stage / "logs" / "01-commands.log"
        self.base = REPO / str(config["base_candidate_relative"])
        self.source_super = REPO / str(config["source_super_relative"])
        self.before: dict[str, dict[str, object]] = {}

    def log(self, text: str) -> None:
        print(text, flush=True)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with self.log_file.open("a", encoding="utf-8") as stream:
            stream.write(text + "\n")

    def run(self, command: list[str]) -> None:
        self.log("$ " + subprocess.list2cmdline(command))
        with self.log_file.open("a", encoding="utf-8") as stream:
            done = subprocess.run(command, cwd=REPO, stdout=stream, stderr=subprocess.STDOUT, text=True)
        if done.returncode:
            raise RuntimeError("failed command: " + command[0])

    def protect(self, name: str, path: Path, size: int, sha256: str) -> None:
        if not path.is_file():
            raise RuntimeError("missing protected input: " + str(path))
        actual = record(path)
        if actual["size"] != size or actual["sha256"] != sha256:
            raise RuntimeError(name + " identity mismatch")
        self.before[name] = actual

    @staticmethod
    def wsl_path(path: Path) -> str:
        absolute = path.resolve()
        return "/mnt/" + absolute.drive[0].lower() + absolute.as_posix()[2:]

    def setup(self) -> None:
        if self.final.exists():
            raise RuntimeError("refusing to overwrite final output: " + str(self.final))
        self.stage.mkdir(parents=True)
        self.protect("base_candidate", self.base, int(self.config["base_candidate_size"]), str(self.config["base_candidate_sha256"]))
        self.protect("source_super", self.source_super, int(self.config["source_super_size"]), str(self.config["source_super_sha256"]))
        (self.stage / "input-provenance-before.json").write_text(json.dumps(self.before, indent=2) + "\n", encoding="utf-8")

    def patch_system_root(self) -> Path:
        raw_super = self.stage / "super.raw.img"
        logical = self.stage / "logical"
        self.run([str(TOOLS / "simg2img.exe"), str(self.source_super), str(raw_super)])
        logical.mkdir()
        self.run([sys.executable, str(TOOLS / "lpunpack.py"), str(raw_super), str(logical)])
        system = logical / "system_a.img"
        spec = self.config["system_a"]
        assert isinstance(spec, dict)
        if system.stat().st_size != int(spec["size"]):
            raise RuntimeError("system_a logical size mismatch")
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "debugfs", "-w", "-R", "mkdir /" + str(spec["add_directory"]), self.wsl_path(system)])

        with raw_super.open("r+b") as destination, system.open("rb") as source:
            destination.seek(int(spec["physical_offset"]))
            shutil.copyfileobj(source, destination, CHUNK)
        output = self.stage / "super.img"
        self.run([str(TOOLS / "img2simg.exe"), str(raw_super), str(output)])
        return output

    def validate_super(self, image: Path) -> None:
        spec = importlib.util.spec_from_file_location("m8a_r7_audit", REPO / "scripts" / "audit-logical-system-init.py")
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        source = module.open_super_source(image)
        original = module.open_super_source(self.source_super)
        try:
            metadata = module.parse_lp_metadata(source)
            old_metadata = module.parse_lp_metadata(original)
            if [item.name for item in metadata.partitions] != [item.name for item in old_metadata.partitions]:
                raise RuntimeError("LP partition table changed")
            system = module.LogicalPartitionSource(source, metadata, "system_a")
            reader = module.Ext4Reader(system)
            root = reader.directory(reader.inode(2))
            if str(self.config["system_a"]["add_directory"]) not in root:
                raise RuntimeError("system root metadata directory is absent")
            for name in ("vendor_a", "product_a", "vendor_dlkm_a"):
                left = module.LogicalPartitionSource(source, metadata, name)
                right = module.LogicalPartitionSource(original, old_metadata, name)
                if left.size != right.size:
                    raise RuntimeError(name + " size changed")
                value_left, value_right = hashlib.sha256(), hashlib.sha256()
                for offset in range(0, left.size, CHUNK):
                    size = min(CHUNK, left.size - offset)
                    value_left.update(left.read_at(offset, size)); value_right.update(right.read_at(offset, size))
                if value_left.digest() != value_right.digest():
                    raise RuntimeError(name + " bytes changed")
        finally:
            original.close(); source.close()

    def pack(self, super_image: Path) -> Path:
        firmware, audit = self.stage / ("x12-" + self.candidate_id + ".img"), self.stage / "outer-payload-audit.json"
        self.run([sys.executable, str(TOOLS / "pack_image_preserving.py"), "--source", str(self.base), "--output", str(firmware), "--replace", "super.fex=" + str(super_image), "--audit", str(audit)])
        self.run([sys.executable, str(TOOLS / "sunxi_image_tool.py"), "verify", str(firmware)])
        actions = {item["filename"]: item["action"] for item in json.loads(audit.read_text(encoding="utf-8"))["payloads"]}
        container = self.config["container"]
        assert isinstance(container, dict)
        if len(actions) != container["total_entries"] or actions.get(container["replacement"]) != "replacement" or actions.get(container["companion"]) != "companion" or sum(action == "preserved" for action in actions.values()) != container["preserved_entries"]:
            raise RuntimeError("outer payload preservation mismatch")
        return firmware

    def finish(self, firmware: Path, super_image: Path) -> None:
        after = {"base_candidate": record(self.base), "source_super": record(self.source_super)}
        if after != self.before:
            raise RuntimeError("protected inputs changed")
        (self.stage / "input-provenance-after.json").write_text(json.dumps(after, indent=2) + "\n", encoding="utf-8")
        (self.stage / "system-root-manifest.json").write_text(json.dumps({"added": "/metadata", "super": record(super_image), "firmware": record(firmware), "source_after_unchanged": True}, indent=2) + "\n", encoding="utf-8")
        shutil.rmtree(self.stage / "logical"); (self.stage / "super.raw.img").unlink()
        for name in ("input-provenance-before.json", "input-provenance-after.json", "outer-payload-audit.json", "system-root-manifest.json"):
            path = self.stage / name
            path.write_text(json.dumps(rewrite_paths(json.loads(path.read_text(encoding="utf-8")), self.stage, self.final), indent=2) + "\n", encoding="utf-8")
        sums = [digest(path) + "  " + path.name for path in sorted(self.stage.iterdir()) if path.is_file() and path.name != "SHA256SUMS"]
        (self.stage / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
        os.replace(self.stage, self.final)

    def build(self) -> None:
        started = time.time()
        try:
            self.setup(); super_image = self.patch_system_root(); self.validate_super(super_image); firmware = self.pack(super_image); self.finish(firmware, super_image)
            print("SUCCESS: " + str(self.final) + " in %.1fs" % (time.time() - started))
        except Exception:
            if self.stage.exists() and not self.keep_failed: shutil.rmtree(self.stage)
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG); parser.add_argument("--keep-failed", action="store_true")
    args = parser.parse_args(); BuildR7(json.loads(args.config.read_text(encoding="utf-8")), args.keep_failed).build()


if __name__ == "__main__": main()
