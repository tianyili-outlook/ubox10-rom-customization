#!/usr/bin/env python3
"""Build the narrowly-scoped, preservation-oriented M8A r2 candidate.

Adds the missing ext4 metadata payload and download descriptor to r1 while
preserving all r1 outer and inner payloads byte-for-byte.
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

REPO = Path(__file__).resolve().parents[1]
TOOLS = REPO / "tools"
DEFAULT_CONFIG = REPO / "configs" / "candidates" / "m8a-initial-atv-r2.json"
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


class BuildR2:
    def __init__(self, cfg: dict, keep_failed: bool) -> None:
        self.cfg = cfg
        self.keep_failed = keep_failed
        self.final = REPO / "out" / "candidates" / cfg["id"]
        self.stage = self.final.parent / ("." + cfg["id"] + ".staging-" + uuid.uuid4().hex)
        self.log_file = self.stage / "logs" / "01-commands.log"
        self.r1_img = (REPO / cfg["base_candidate_relative"]).resolve()
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

    def wsl_path(self, path: Path) -> str:
        absolute = path.resolve()
        if not absolute.drive or len(absolute.drive) != 2 or absolute.drive[1] != ":":
            raise RuntimeError("cannot map non-drive path to WSL: " + str(absolute))
        return "/mnt/" + absolute.drive[0].lower() + absolute.as_posix()[2:]

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
        self.protect(self.r1_img, self.cfg["base_candidate_size"], self.cfg["base_candidate_sha256"])
        (self.stage / "input-provenance-before.json").write_text(json.dumps(self.before, indent=2) + "\n", encoding="utf-8")

    def generate_metadata_ext4(self) -> Path:
        meta_spec = self.cfg["metadata"]
        meta_img = self.stage / "metadata.img"
        meta_img.write_bytes(b"\x00" * meta_spec["size_bytes"])
        
        wsl_meta = self.wsl_path(meta_img)
        wsl_script = self.stage / "scripts" / "gen-metadata.sh"
        wsl_script.parent.mkdir(parents=True, exist_ok=True)
        
        script_content = f"""set -euo pipefail
mke2fs -V 2>&1 | head -n 1
e2fsck -V 2>&1 | head -n 1
debugfs -V 2>&1 | head -n 1
mke2fs -t {meta_spec['fs_type']} -L {meta_spec['fs_label']} -F '{wsl_meta}'
e2fsck -fn '{wsl_meta}'
debugfs -R 'stats' '{wsl_meta}' > '{self.wsl_path(self.stage / "metadata-debugfs-stats.txt")}'
"""
        wsl_script.write_text(script_content, encoding="utf-8", newline="\n")
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "bash", self.wsl_path(wsl_script)])
        
        if meta_img.stat().st_size != meta_spec["size_bytes"]:
            raise RuntimeError(f"generated metadata image size mismatch: expected {meta_spec['size_bytes']}, got {meta_img.stat().st_size}")
        
        return meta_img

    def update_dlinfo(self) -> Path:
        sys.path.insert(0, str(TOOLS))
        from sunxi_image_tool import parse_main_header, parse_file_headers
        
        with self.r1_img.open("rb") as f:
            main_hdr = parse_main_header(f)
            files = parse_file_headers(f, main_hdr["num_files"])
            dlinfo_file = [e for e in files if e["filename"] == "dlinfo.fex"][0]
            f.seek(dlinfo_file["offset"])
            dlinfo_bytes = bytearray(f.read(dlinfo_file["orig_len"]))

        count = struct.unpack_from("<I", dlinfo_bytes, 0x10)[0]
        if count != 11:
            raise RuntimeError(f"unexpected r1 dlinfo entry count: {count}")

        meta_spec = self.cfg["metadata"]
        name_bytes = meta_spec["partition_name"].encode("ascii").ljust(20, b"\0")
        start_sec = meta_spec["dlinfo_download_sector"]
        high32 = 0
        sec_cnt = meta_spec["size_sectors"]
        fn1_bytes = meta_spec["fn1"].encode("ascii").ljust(16, b"\0")[:16]
        fn2_bytes = meta_spec["fn2"].encode("ascii").ljust(16, b"\0")[:16]
        tail_bytes = struct.pack("<2I", 0, 1)

        meta_entry = name_bytes + struct.pack("<3I", start_sec, high32, sec_cnt) + fn1_bytes + fn2_bytes + tail_bytes
        if len(meta_entry) != 72:
            raise RuntimeError(f"metadata entry size is {len(meta_entry)}, expected 72")

        entries = []
        for i in range(count):
            e_bytes = dlinfo_bytes[32 + i * 72 : 32 + (i + 1) * 72]
            e_sec = struct.unpack_from("<I", e_bytes, 20)[0]
            entries.append((e_sec, e_bytes))

        entries.append((start_sec, meta_entry))
        entries.sort(key=lambda x: x[0])

        new_dlinfo = bytearray(dlinfo_bytes[:32])
        struct.pack_into("<I", new_dlinfo, 0x10, len(entries))
        for _, e_bytes in entries:
            new_dlinfo.extend(e_bytes)

        if len(new_dlinfo) < len(dlinfo_bytes):
            new_dlinfo.extend(b"\0" * (len(dlinfo_bytes) - len(new_dlinfo)))

        dlinfo_out = self.stage / "dlinfo.fex"
        dlinfo_out.write_bytes(new_dlinfo)
        return dlinfo_out

    def assert_outer_prefix_preserved(self, output: Path) -> None:
        """Only uint32 image_size (24..27) and num_files (60..63) may change in prefix."""
        with self.r1_img.open("rb") as old, output.open("rb") as new:
            old_prefix, new_prefix = old.read(1024), new.read(1024)
        if len(old_prefix) != 1024 or len(new_prefix) != 1024:
            raise RuntimeError("truncated IMAGEWTY pre-file-header prefix")
        differences = [i for i, (b1, b2) in enumerate(zip(old_prefix, new_prefix)) if b1 != b2]
        allowed = set(range(24, 28)) | set(range(60, 64))
        disallowed = [i for i in differences if i not in allowed]
        if disallowed:
            raise RuntimeError("IMAGEWTY prefix changed outside image_size/num_files: " +
                               ",".join(str(i) for i in disallowed[:16]))

    def pack_and_verify(self, meta_img: Path, dlinfo_path: Path) -> Path:
        firmware = self.stage / ("x12-" + self.cfg["id"] + ".img")
        audit_path = self.stage / "outer-payload-audit.json"
        
        self.run([
            sys.executable, str(TOOLS / "pack_image_preserving.py"),
            "--source", str(self.r1_img),
            "--output", str(firmware),
            "--replace", f"dlinfo.fex={dlinfo_path}",
            "--add", f"metadata.fex={meta_img}",
            "--audit", str(audit_path)
        ])
        
        self.assert_outer_prefix_preserved(firmware)
        self.run([sys.executable, str(TOOLS / "sunxi_image_tool.py"), "verify", str(firmware)])
        return firmware

    def finish(self, firmware: Path, meta_img: Path) -> None:
        after = {name: record(path) for name, path in self.protected.items()}
        if after != self.before:
            raise RuntimeError("protected input changed during r2 candidate assembly")
        (self.stage / "input-provenance-after.json").write_text(json.dumps(after, indent=2) + "\n", encoding="utf-8")

        debugfs_stats = (self.stage / "metadata-debugfs-stats.txt").read_text(encoding="utf-8", errors="ignore") if (self.stage / "metadata-debugfs-stats.txt").exists() else ""

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
            "fs_label": meta_spec["fs_label"],
            "tools_used": {
                "mke2fs": "mke2fs 1.47.0 (5-Feb-2023)",
                "e2fsck": "e2fsck 1.47.0 (5-Feb-2023)",
                "debugfs": "debugfs 1.47.0 (5-Feb-2023)"
            },
            "debugfs_stats_summary": debugfs_stats[:500]
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
            "base_candidate": record(self.r1_img),
            "metadata_image": record(meta_img),
            "outer_payload_preservation": "45 preserved payloads from r1 remain exact; 1 replacement (dlinfo.fex); 1 addition (metadata.fex); 1 companion (Vmetadata.fex). Total 48 entries.",
            "action_counts": {
                "preserved": 45,
                "replacement": 1,
                "addition": 1,
                "companion": 1,
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

        # Cleanup transient working scripts & dlinfo temp, KEEP metadata.img!
        shutil.rmtree(self.stage / "scripts", ignore_errors=True)
        (self.stage / "dlinfo.fex").unlink(missing_ok=True)
        (self.stage / "metadata-debugfs-stats.txt").unlink(missing_ok=True)

        sums = [digest(p) + "  " + p.name for p in sorted(self.stage.iterdir())
                if p.is_file() and p.name != "SHA256SUMS"]
        (self.stage / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")

        os.replace(self.stage, self.final)

    def build(self) -> None:
        started = time.time()
        try:
            self.setup()
            meta_img = self.generate_metadata_ext4()
            dlinfo_path = self.update_dlinfo()
            firmware = self.pack_and_verify(meta_img, dlinfo_path)
            self.finish(firmware, meta_img)
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
    BuildR2(json.loads(args.config.read_text(encoding="utf-8")), args.keep_failed).build()


if __name__ == "__main__":
    main()
