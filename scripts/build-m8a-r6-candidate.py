#!/usr/bin/env python3
"""Build r6 with stock-compatible interleaved LP partition-table order."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time
import uuid

REPO = Path(__file__).resolve().parents[1]
TOOLS = REPO / "tools"
DEFAULT_CONFIG = REPO / "configs" / "candidates" / "m8a-initial-atv-r6.json"
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
    if isinstance(value, str):
        return value.replace(str(stage), str(final))
    return value


def reorder_lp_partition_tables(raw_super: Path, expected_order: list[str], metadata_size: int, slots: int) -> dict[str, object]:
    """Reorder every valid primary/backup LP partition table and rehash it."""
    primary_base = 4096 + 2 * 4096
    backup_base = primary_base + metadata_size * slots
    patched: list[dict[str, object]] = []
    with raw_super.open("r+b") as stream:
        for copy_name, base in (("primary", primary_base), ("backup", backup_base)):
            for slot in range(slots):
                offset = base + slot * metadata_size
                stream.seek(offset)
                fixed = stream.read(256)
                if len(fixed) < 128 or struct.unpack_from("<I", fixed, 0)[0] != 0x414C5030:
                    continue
                header_size = struct.unpack_from("<I", fixed, 8)[0]
                tables_size = struct.unpack_from("<I", fixed, 44)[0]
                if header_size < 128 or header_size > metadata_size or tables_size > metadata_size - header_size:
                    raise RuntimeError("invalid LP metadata geometry during reorder")
                stream.seek(offset)
                header = bytearray(stream.read(header_size))
                table_offset, count, entry_size = struct.unpack_from("<3I", header, 80)
                if count != len(expected_order) or entry_size < 52:
                    raise RuntimeError("unexpected LP partition descriptor during reorder")
                stream.seek(offset + header_size)
                tables = bytearray(stream.read(tables_size))
                entries = [bytes(tables[table_offset + index * entry_size:table_offset + (index + 1) * entry_size]) for index in range(count)]
                names = [entry[:36].split(b"\0", 1)[0].decode("ascii") for entry in entries]
                by_name = dict(zip(names, entries))
                if set(by_name) != set(expected_order):
                    raise RuntimeError("LP partition-name set mismatch during reorder")
                reordered = b"".join(by_name[name] for name in expected_order)
                tables[table_offset:table_offset + count * entry_size] = reordered
                header[48:80] = hashlib.sha256(tables).digest()
                header[12:44] = b"\0" * 32
                header[12:44] = hashlib.sha256(header).digest()
                stream.seek(offset)
                stream.write(header)
                stream.write(tables)
                patched.append({"copy": copy_name, "slot": slot, "offset": offset, "before": names, "after": expected_order})
    if not patched:
        raise RuntimeError("no valid LP metadata copy was patched")
    return {"patched_metadata_copies": patched, "expected_partition_order": expected_order}


def read_primary_lp_partition_order(raw_super: Path) -> list[str]:
    """Read table order directly; lpdumps groups A/B in its presentation."""
    offset = 4096 + 2 * 4096
    with raw_super.open("rb") as stream:
        stream.seek(offset)
        header = stream.read(256)
        header_size = struct.unpack_from("<I", header, 8)[0]
        tables_size = struct.unpack_from("<I", header, 44)[0]
        table_offset, count, entry_size = struct.unpack_from("<3I", header, 80)
        stream.seek(offset + header_size)
        tables = stream.read(tables_size)
    return [
        tables[table_offset + index * entry_size:table_offset + index * entry_size + 36]
        .split(b"\0", 1)[0]
        .decode("ascii")
        for index in range(count)
    ]


class BuildR6:
    def __init__(self, config: dict[str, object], keep_failed: bool) -> None:
        self.config = config
        self.keep_failed = keep_failed
        self.candidate_id = str(config["id"])
        self.final = REPO / "out" / "candidates" / self.candidate_id
        self.stage = self.final.parent / ("." + self.candidate_id + ".staging-" + uuid.uuid4().hex)
        self.log_file = self.stage / "logs" / "01-commands.log"
        self.base = (REPO / str(config["base_candidate_relative"])).resolve()
        self.source_super = (REPO / str(config["source_super_relative"])).resolve()
        self.before: dict[str, dict[str, object]] = {}

    def log(self, message: str) -> None:
        print(message, flush=True)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with self.log_file.open("a", encoding="utf-8") as stream:
            stream.write(message + "\n")

    def run(self, command: list[str], *, output: Path | None = None) -> None:
        self.log("$ " + subprocess.list2cmdline(command))
        destination = output if output is not None else self.log_file
        with destination.open("a" if output is None else "w", encoding="utf-8", newline="\n") as stream:
            completed = subprocess.run(command, cwd=REPO, stdout=stream, stderr=subprocess.STDOUT, text=True)
        if completed.returncode:
            raise RuntimeError("failed command: " + command[0])

    def protect(self, name: str, path: Path, size: int, sha256: str) -> None:
        if not path.is_file():
            raise RuntimeError("missing protected input: " + str(path))
        value = record(path)
        if value["size"] != size or value["sha256"] != sha256:
            raise RuntimeError(name + " identity mismatch")
        self.before[name] = value

    def setup(self) -> None:
        if self.final.exists():
            raise RuntimeError("refusing to overwrite final output: " + str(self.final))
        self.stage.mkdir(parents=True)
        self.protect("base_candidate", self.base, int(self.config["base_candidate_size"]), str(self.config["base_candidate_sha256"]))
        self.protect("source_super", self.source_super, int(self.config["source_super_size"]), str(self.config["source_super_sha256"]))
        (self.stage / "input-provenance-before.json").write_text(json.dumps(self.before, indent=2) + "\n", encoding="utf-8")

    def extract_logical_inputs(self) -> dict[str, Path]:
        raw_super = self.stage / "source-super.raw.img"
        extracted = self.stage / "source-logical"
        extracted.mkdir()
        self.run([str(TOOLS / "simg2img.exe"), str(self.source_super), str(raw_super)])
        self.run([sys.executable, str(TOOLS / "lpunpack.py"), str(raw_super), str(extracted)])

        logical = self.config["logical_partitions"]
        assert isinstance(logical, dict)
        images: dict[str, Path] = {}
        manifest: dict[str, object] = {}
        for name, expected_size in logical.items():
            path = extracted / (name + ".img")
            if not path.is_file() or path.stat().st_size != expected_size:
                raise RuntimeError("logical source size mismatch: " + name)
            images[name] = path
            manifest[name] = record(path)
        (self.stage / "logical-inputs.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        return images

    def make_super(self, images: dict[str, Path]) -> Path:
        spec = self.config["super"]
        logical = self.config["logical_partitions"]
        expected_order = self.config["expected_partition_order"]
        assert isinstance(spec, dict) and isinstance(logical, dict) and isinstance(expected_order, list)
        unordered_sparse = self.stage / "unordered-super.img"
        output = self.stage / "super.img"
        command = [
            str(TOOLS / "lpmake.exe"),
            "--metadata-size", str(spec["metadata_size"]),
            "--metadata-slots", str(spec["metadata_slots"]),
            "--super-name", "super",
            "--device-size", str(spec["device_size"]),
            "--alignment", str(spec["alignment"]),
            "--virtual-ab",
            "--group", "sb_a:" + str(spec["group_size"]),
            "--group", "sb_b:" + str(spec["group_size"]),
        ]
        for name, size in logical.items():
            command += ["--partition", f"{name}:readonly:{size}:sb_a", "--image", f"{name}={images[name]}"]
            command += ["--partition", f"{name[:-1]}b:readonly:0:sb_b"]
        command += ["--sparse", "--output", str(unordered_sparse)]
        self.run(command)

        validation_raw = self.stage / "validation-super.raw.img"
        metadata_json = self.stage / "super-metadata.json"
        self.run([str(TOOLS / "simg2img.exe"), str(unordered_sparse), str(validation_raw)])
        reorder = reorder_lp_partition_tables(
            validation_raw,
            [str(item) for item in expected_order],
            int(spec["metadata_size"]),
            int(spec["metadata_slots"]),
        )
        (self.stage / "lp-order-repair.json").write_text(json.dumps(reorder, indent=2) + "\n", encoding="utf-8")
        self.run([str(TOOLS / "img2simg.exe"), str(validation_raw), str(output)])
        unordered_sparse.unlink()
        self.run([str(TOOLS / "lpdumps.exe"), "-j", str(validation_raw)], output=metadata_json)
        json.loads(metadata_json.read_text(encoding="utf-8"))
        actual_order = read_primary_lp_partition_order(validation_raw)
        if actual_order != expected_order:
            raise RuntimeError("LP partition-table order mismatch: " + repr(actual_order))

        validation_dir = self.stage / "validation-logical"
        validation_dir.mkdir()
        self.run([sys.executable, str(TOOLS / "lpunpack.py"), str(validation_raw), str(validation_dir)])
        for name, source in images.items():
            extracted = validation_dir / (name + ".img")
            if record(extracted)["sha256"] != record(source)["sha256"]:
                raise RuntimeError("rebuilt logical payload mismatch: " + name)

        shutil.rmtree(validation_dir)
        validation_raw.unlink()
        return output

    def pack(self, super_image: Path) -> Path:
        firmware = self.stage / ("x12-" + self.candidate_id + ".img")
        audit = self.stage / "outer-payload-audit.json"
        self.run([
            sys.executable, str(TOOLS / "pack_image_preserving.py"),
            "--source", str(self.base),
            "--output", str(firmware),
            "--replace", "super.fex=" + str(super_image),
            "--audit", str(audit),
        ])
        self.run([sys.executable, str(TOOLS / "sunxi_image_tool.py"), "verify", str(firmware)])

        container = self.config["container"]
        assert isinstance(container, dict)
        data = json.loads(audit.read_text(encoding="utf-8"))
        actions = {item["filename"]: item["action"] for item in data["payloads"]}
        if len(actions) != container["total_entries"]:
            raise RuntimeError("unexpected IMAGEWTY entry count")
        if actions.get(container["replacement"]) != "replacement" or actions.get(container["companion"]) != "companion":
            raise RuntimeError("unexpected IMAGEWTY replacement set")
        if sum(action == "preserved" for action in actions.values()) != container["preserved_entries"]:
            raise RuntimeError("unexpected IMAGEWTY preservation count")
        return firmware

    def finish(self, firmware: Path, super_image: Path) -> None:
        after = {"base_candidate": record(self.base), "source_super": record(self.source_super)}
        if after != self.before:
            raise RuntimeError("protected input changed")
        (self.stage / "input-provenance-after.json").write_text(json.dumps(after, indent=2) + "\n", encoding="utf-8")
        result = {
            "id": self.candidate_id,
            "status": "BUILT",
            "firmware": record(firmware),
            "base_candidate": after["base_candidate"],
            "source_super": after["source_super"],
            "super": record(super_image),
            "repair": "LP partition table reordered to stock interleaved A/B order; logical payload bytes unchanged.",
            "outer_payload_preservation": "48 payloads exact; super.fex replaced; Vsuper.fex regenerated.",
            "physical_device_actions_performed": False,
        }
        (self.stage / "build-result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

        shutil.rmtree(self.stage / "source-logical")
        (self.stage / "source-super.raw.img").unlink()
        for name in ("build-result.json", "outer-payload-audit.json", "input-provenance-before.json", "input-provenance-after.json", "logical-inputs.json"):
            path = self.stage / name
            data = json.loads(path.read_text(encoding="utf-8"))
            path.write_text(json.dumps(rewrite_paths(data, self.stage, self.final), indent=2) + "\n", encoding="utf-8")

        sums = [digest(path) + "  " + path.name for path in sorted(self.stage.iterdir()) if path.is_file() and path.name != "SHA256SUMS"]
        (self.stage / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
        os.replace(self.stage, self.final)

    def build(self) -> None:
        started = time.time()
        try:
            self.setup()
            images = self.extract_logical_inputs()
            super_image = self.make_super(images)
            firmware = self.pack(super_image)
            self.finish(firmware, super_image)
            print(f"SUCCESS: {self.final} in {time.time() - started:.1f}s")
        except Exception:
            if self.stage.exists() and not self.keep_failed:
                shutil.rmtree(self.stage)
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--keep-failed", action="store_true")
    args = parser.parse_args()
    BuildR6(json.loads(args.config.read_text(encoding="utf-8")), args.keep_failed).build()


if __name__ == "__main__":
    main()
