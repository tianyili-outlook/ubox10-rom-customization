#!/usr/bin/env python3
"""Build the M8A r5 candidate with a keyless AVB verification bypass.

Replaces only top-level vbmeta.fex over r4. The new image uses AVB algorithm
NONE and flags=2; pack_image_preserving regenerates only Vvbmeta.fex.
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
DEFAULT_CONFIG = REPO / "configs" / "candidates" / "m8a-initial-atv-r5.json"
CHUNK = 8 * 1024 * 1024


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(CHUNK), b""):
            hasher.update(block)
    return hasher.hexdigest().upper()


def record(path: Path) -> dict[str, object]:
    return {"path": str(path), "size": path.stat().st_size, "sha256": digest(path)}


def rewrite_published_paths(value: object, *, stage: Path, final: Path) -> object:
    if isinstance(value, dict):
        return {key: rewrite_published_paths(item, stage=stage, final=final) for key, item in value.items()}
    if isinstance(value, list):
        return [rewrite_published_paths(item, stage=stage, final=final) for item in value]
    if isinstance(value, str):
        return value.replace(str(stage), str(final))
    return value


class BuildR5:
    def __init__(self, config: dict[str, object], keep_failed: bool) -> None:
        self.config = config
        self.keep_failed = keep_failed
        self.candidate_id = str(config["id"])
        self.final = REPO / "out" / "candidates" / self.candidate_id
        self.stage = self.final.parent / ("." + self.candidate_id + ".staging-" + uuid.uuid4().hex)
        self.log_file = self.stage / "logs" / "01-commands.log"
        self.base = (REPO / str(config["base_candidate_relative"])).resolve()
        self.before: dict[str, object] | None = None

    def log(self, message: str) -> None:
        print(message, flush=True)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with self.log_file.open("a", encoding="utf-8") as stream:
            stream.write(message + "\n")

    def run(self, command: list[str], *, output: Path | None = None) -> None:
        self.log("$ " + subprocess.list2cmdline(command))
        if output is None:
            with self.log_file.open("a", encoding="utf-8") as stream:
                completed = subprocess.run(command, cwd=REPO, stdout=stream, stderr=subprocess.STDOUT, text=True)
        else:
            with output.open("w", encoding="utf-8", newline="\n") as stream:
                completed = subprocess.run(command, cwd=REPO, stdout=stream, stderr=subprocess.STDOUT, text=True)
        if completed.returncode:
            raise RuntimeError("failed command: " + command[0])

    def setup(self) -> None:
        if self.final.exists():
            raise RuntimeError("refusing to overwrite final output: " + str(self.final))
        if not self.base.is_file():
            raise RuntimeError("missing r4 base candidate: " + str(self.base))
        self.stage.mkdir(parents=True)
        self.before = record(self.base)
        if self.before["size"] != self.config["base_candidate_size"]:
            raise RuntimeError("r4 base size mismatch")
        if self.before["sha256"] != self.config["base_candidate_sha256"]:
            raise RuntimeError("r4 base SHA-256 mismatch")
        (self.stage / "input-provenance-before.json").write_text(
            json.dumps({"base_candidate": self.before}, indent=2) + "\n", encoding="utf-8"
        )

    def make_vbmeta(self) -> Path:
        spec = self.config["vbmeta"]
        assert isinstance(spec, dict)
        vbmeta = self.stage / "vbmeta.img"
        self.run([
            sys.executable,
            str(TOOLS / "avbtool.py"),
            "make_vbmeta_image",
            "--output", str(vbmeta),
            "--algorithm", str(spec["algorithm"]),
            "--rollback_index", str(spec["rollback_index"]),
            "--flags", str(spec["flags"]),
            "--padding_size", str(spec["padding_size"]),
            "--prop", str(spec["property"]),
        ])
        self.run(
            [sys.executable, str(TOOLS / "avbtool.py"), "info_image", "--image", str(vbmeta)],
            output=self.stage / "avb-info.txt",
        )
        self.run(
            [sys.executable, str(TOOLS / "avbtool.py"), "verify_image", "--image", str(vbmeta)],
            output=self.stage / "avb-verify.txt",
        )

        module_spec = importlib.util.spec_from_file_location("m8a_r5_avbtool", TOOLS / "avbtool.py")
        if module_spec is None or module_spec.loader is None:
            raise RuntimeError("cannot load repo-local avbtool")
        avbtool = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(avbtool)
        header = avbtool.AvbVBMetaHeader(vbmeta.read_bytes()[:256])
        if vbmeta.stat().st_size != spec["padding_size"]:
            raise RuntimeError("keyless vbmeta size mismatch")
        if header.algorithm_type != spec["algorithm_type"] or header.flags != spec["flags"]:
            raise RuntimeError("keyless vbmeta header mismatch")
        return vbmeta

    def pack(self, vbmeta: Path) -> Path:
        firmware = self.stage / ("x12-" + self.candidate_id + ".img")
        audit = self.stage / "outer-payload-audit.json"
        self.run([
            sys.executable,
            str(TOOLS / "pack_image_preserving.py"),
            "--source", str(self.base),
            "--output", str(firmware),
            "--replace", "vbmeta.fex=" + str(vbmeta),
            "--audit", str(audit),
        ])
        self.run([sys.executable, str(TOOLS / "sunxi_image_tool.py"), "verify", str(firmware)])

        container = self.config["container"]
        assert isinstance(container, dict)
        audit_data = json.loads(audit.read_text(encoding="utf-8"))
        entries = audit_data["payloads"]
        actions = {entry["filename"]: entry["action"] for entry in entries}
        if len(entries) != container["total_entries"]:
            raise RuntimeError("unexpected IMAGEWTY entry count")
        if actions.get(container["replacement"]) != "replacement":
            raise RuntimeError("vbmeta.fex was not the sole replacement")
        if actions.get(container["companion"]) != "companion":
            raise RuntimeError("Vvbmeta.fex was not regenerated")
        preserved = [name for name, action in actions.items() if action == "preserved"]
        unexpected = [name for name, action in actions.items() if action not in {"preserved", "replacement", "companion"}]
        if len(preserved) != container["preserved_entries"] or unexpected:
            raise RuntimeError("payload preservation invariant failed")
        return firmware

    def finish(self, firmware: Path, vbmeta: Path) -> None:
        after = record(self.base)
        if after != self.before:
            raise RuntimeError("protected r4 base changed during assembly")
        (self.stage / "input-provenance-after.json").write_text(
            json.dumps({"base_candidate": after}, indent=2) + "\n", encoding="utf-8"
        )
        result = {
            "id": self.candidate_id,
            "status": "BUILT",
            "firmware": record(firmware),
            "base_candidate": after,
            "vbmeta": record(vbmeta),
            "avb": {
                "algorithm": "NONE",
                "flags": 2,
                "verification": "disabled",
                "private_key_used": False,
            },
            "outer_payload_preservation": "48 payloads exact; vbmeta.fex replaced; Vvbmeta.fex regenerated.",
            "source_after_unchanged": True,
            "physical_device_actions_performed": False,
        }
        (self.stage / "build-result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

        for name in ("build-result.json", "outer-payload-audit.json", "input-provenance-before.json", "input-provenance-after.json"):
            path = self.stage / name
            data = json.loads(path.read_text(encoding="utf-8"))
            path.write_text(
                json.dumps(rewrite_published_paths(data, stage=self.stage, final=self.final), indent=2) + "\n",
                encoding="utf-8",
            )

        sums = [digest(path) + "  " + path.name for path in sorted(self.stage.iterdir()) if path.is_file() and path.name != "SHA256SUMS"]
        (self.stage / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
        os.replace(self.stage, self.final)

    def build(self) -> None:
        started = time.time()
        try:
            self.setup()
            vbmeta = self.make_vbmeta()
            firmware = self.pack(vbmeta)
            self.finish(firmware, vbmeta)
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
    BuildR5(json.loads(args.config.read_text(encoding="utf-8")), args.keep_failed).build()


if __name__ == "__main__":
    main()
