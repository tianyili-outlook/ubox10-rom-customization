#!/usr/bin/env python3
"""Build the CRC-repaired M8A r3 candidate.

Extracts r2 dlinfo.fex, updates its first 4 bytes to little-endian zlib.crc32(dlinfo[4:]),
and repacks it as the sole replacement over r2 while preserving all 47 other payloads.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time
import uuid
import zlib

REPO = Path(__file__).resolve().parents[1]
TOOLS = REPO / "tools"
DEFAULT_CONFIG = REPO / "configs" / "candidates" / "m8a-initial-atv-r3.json"
CHUNK = 8 * 1024 * 1024


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(CHUNK), b""):
            h.update(part)
    return h.hexdigest().upper()


def record(path: Path) -> dict:
    return {"path": str(path), "size": path.stat().st_size, "sha256": digest(path)}


def rewrite_published_paths(value: object, *, stage: Path, final: Path) -> object:
    if isinstance(value, dict):
        return {rewrite_published_paths(k, stage=stage, final=final): rewrite_published_paths(v, stage=stage, final=final) for k, v in value.items()}
    if isinstance(value, list):
        return [rewrite_published_paths(v, stage=stage, final=final) for v in value]
    if isinstance(value, str):
        return value.replace(str(stage), str(final))
    return value


class BuildR3:
    def __init__(self, cfg: dict, keep_failed: bool) -> None:
        self.cfg = cfg
        self.keep_failed = keep_failed
        self.final = REPO / "out" / "candidates" / cfg["id"]
        self.stage = self.final.parent / ("." + cfg["id"] + ".staging-" + uuid.uuid4().hex)
        self.log_file = self.stage / "logs" / "01-commands.log"
        self.r2_img = (REPO / cfg["base_candidate_relative"]).resolve()
        self.protected: dict[str, Path] = {}
        self.before: dict[str, dict] = {}

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

    def protect(self, path: Path, size: int | None = None, sha: str | None = None) -> None:
        if not path.is_file():
            raise RuntimeError("missing protected input: " + str(path))
        val = record(path)
        if size is not None and val["size"] != size:
            raise RuntimeError(f"size mismatch for {path}: expected {size}, got {val['size']}")
        if sha is not None and val["sha256"] != sha:
            raise RuntimeError(f"SHA256 mismatch for {path}: expected {sha}, got {val['sha256']}")
        self.protected[str(path)] = path
        self.before[str(path)] = val

    def setup(self) -> None:
        if self.final.exists():
            raise RuntimeError("refusing to overwrite final output: " + str(self.final))
        self.stage.mkdir(parents=True)
        self.protect(self.r2_img, self.cfg["base_candidate_size"], self.cfg["base_candidate_sha256"])
        (self.stage / "input-provenance-before.json").write_text(json.dumps(self.before, indent=2) + "\n", encoding="utf-8")

    def prepare_repaired_dlinfo(self) -> tuple[Path, int, int]:
        sys.path.insert(0, str(TOOLS))
        from sunxi_image_tool import parse_main_header, parse_file_headers

        with self.r2_img.open("rb") as f:
            main_hdr = parse_main_header(f)
            files = parse_file_headers(f, main_hdr["num_files"])
            dlinfo_file = [e for e in files if e["filename"] == "dlinfo.fex"][0]
            f.seek(dlinfo_file["offset"])
            dlinfo_bytes = bytearray(f.read(dlinfo_file["orig_len"]))

        old_crc = struct.unpack_from("<I", dlinfo_bytes, 0)[0]
        new_crc = zlib.crc32(dlinfo_bytes[4:])

        struct.pack_into("<I", dlinfo_bytes, 0, new_crc)

        dlinfo_out = self.stage / "dlinfo.fex"
        dlinfo_out.write_bytes(dlinfo_bytes)
        return dlinfo_out, old_crc, new_crc

    def preserve_metadata_img(self) -> Path:
        r2_meta = self.r2_img.parent / "metadata.img"
        if not r2_meta.is_file():
            raise RuntimeError(f"r2 metadata.img not found: {r2_meta}")
        if r2_meta.stat().st_size != self.cfg["metadata"]["size_bytes"]:
            raise RuntimeError(f"metadata.img size mismatch: {r2_meta.stat().st_size}")
        stage_meta = self.stage / "metadata.img"
        shutil.copyfile(r2_meta, stage_meta)
        return stage_meta

    def pack_and_verify(self, dlinfo_path: Path) -> Path:
        firmware = self.stage / ("x12-" + self.cfg["id"] + ".img")
        audit_path = self.stage / "outer-payload-audit.json"

        self.run([
            sys.executable, str(TOOLS / "pack_image_preserving.py"),
            "--source", str(self.r2_img),
            "--output", str(firmware),
            "--replace", f"dlinfo.fex={dlinfo_path}",
            "--audit", str(audit_path)
        ])

        if firmware.stat().st_size != self.r2_img.stat().st_size:
            raise RuntimeError(f"r3 size {firmware.stat().st_size} != r2 size {self.r2_img.stat().st_size}")

        self.run([sys.executable, str(TOOLS / "sunxi_image_tool.py"), "verify", str(firmware)])
        return firmware

    def finish(self, firmware: Path, meta_img: Path, old_crc: int, new_crc: int) -> None:
        after = {name: record(path) for name, path in self.protected.items()}
        if after != self.before:
            raise RuntimeError("protected input changed during r3 candidate assembly")
        (self.stage / "input-provenance-after.json").write_text(json.dumps(after, indent=2) + "\n", encoding="utf-8")

        meta_spec = self.cfg["metadata"]
        (self.stage / "metadata-manifest.json").write_text(json.dumps({
            "metadata_image": record(meta_img),
            "gpt_partition_name": meta_spec["partition_name"],
            "gpt_partition_index": meta_spec["gpt_partition_index"],
            "dlinfo_download_sector": meta_spec["dlinfo_download_sector"],
            "card_boot_offset_sectors": meta_spec["card_boot_offset_sectors"],
            "gpt_first_lba_sector": meta_spec["gpt_first_lba_sector"],
            "size_sectors": meta_spec["size_sectors"],
            "size_bytes": meta_spec["size_bytes"],
            "fs_type": meta_spec["fs_type"],
            "fs_label": meta_spec["fs_label"]
        }, indent=2) + "\n", encoding="utf-8")

        (self.stage / "rollback-metadata.json").write_text(json.dumps({
            "declared_rollback": self.cfg["declared_rollback"],
            "declared_stock": self.cfg["declared_stock"],
            "risk": "The testkey root differs from stock trust; offline validation cannot prove device acceptance."
        }, indent=2) + "\n", encoding="utf-8")

        (self.stage / "build-result.json").write_text(json.dumps({
            "id": self.cfg["id"],
            "status": "BUILT",
            "firmware": record(firmware),
            "base_candidate": record(self.r2_img),
            "metadata_image": record(meta_img),
            "old_dlinfo_crc": hex(old_crc),
            "new_dlinfo_crc": hex(new_crc),
            "outer_payload_preservation": "47 preserved payloads from r2 remain exact; 1 replacement (dlinfo.fex). Total 48 entries.",
            "action_counts": {
                "preserved": 47,
                "replacement": 1,
                "addition": 0,
                "companion": 0,
                "total": 48
            },
            "source_after_unchanged": True
        }, indent=2) + "\n", encoding="utf-8")

        for metadata_file in ("build-result.json", "metadata-manifest.json", "outer-payload-audit.json",
                              "input-provenance-before.json", "input-provenance-after.json", "rollback-metadata.json"):
            p = self.stage / metadata_file
            if p.exists():
                p.write_text(json.dumps(rewrite_published_paths(
                    json.loads(p.read_text(encoding="utf-8")), stage=self.stage, final=self.final
                ), indent=2) + "\n", encoding="utf-8")

        # Cleanup transient working dlinfo temp, KEEP metadata.img!
        (self.stage / "dlinfo.fex").unlink(missing_ok=True)

        sums = [digest(p) + "  " + p.name for p in sorted(self.stage.iterdir())
                if p.is_file() and p.name != "SHA256SUMS"]
        (self.stage / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")

        os.replace(self.stage, self.final)

    def build(self) -> None:
        started = time.time()
        try:
            self.setup()
            dlinfo_path, old_crc, new_crc = self.prepare_repaired_dlinfo()
            meta_img = self.preserve_metadata_img()
            firmware = self.pack_and_verify(dlinfo_path)
            self.finish(firmware, meta_img, old_crc, new_crc)
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
    BuildR3(json.loads(args.config.read_text(encoding="utf-8")), args.keep_failed).build()


if __name__ == "__main__":
    main()
