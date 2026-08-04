#!/usr/bin/env python3
"""Build r8 with an explicit runtime UART console for first-stage init diagnosis."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
import uuid

REPO = Path(__file__).resolve().parents[1]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))
from sunxi_image_tool import parse_file_headers, parse_main_header

DEFAULT_CONFIG = REPO / "configs" / "candidates" / "m8a-initial-atv-r8.json"
CHUNK = 8 * 1024 * 1024
CMDLINE_OFFSET, CMDLINE_BYTES = 44, 1536


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


class BuildR8:
    def __init__(self, config: dict[str, object], keep_failed: bool) -> None:
        self.config, self.keep_failed = config, keep_failed
        self.candidate_id = str(config["id"])
        self.final = REPO / "out" / "candidates" / self.candidate_id
        self.stage = self.final.parent / ("." + self.candidate_id + ".staging-" + uuid.uuid4().hex)
        self.log_file = self.stage / "logs" / "01-commands.log"
        self.base = REPO / str(config["base_candidate_relative"])
        self.before: dict[str, object] | None = None

    def log(self, text: str) -> None:
        print(text, flush=True)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with self.log_file.open("a", encoding="utf-8") as stream: stream.write(text + "\n")

    def run(self, command: list[str]) -> None:
        self.log("$ " + __import__("subprocess").list2cmdline(command))
        with self.log_file.open("a", encoding="utf-8") as stream:
            done = __import__("subprocess").run(command, cwd=REPO, stdout=stream, stderr=stream, text=True)
        if done.returncode: raise RuntimeError("failed command: " + command[0])

    def setup(self) -> None:
        if self.final.exists(): raise RuntimeError("refusing to overwrite final output: " + str(self.final))
        if not self.base.is_file(): raise RuntimeError("missing r7 input: " + str(self.base))
        self.stage.mkdir(parents=True)
        self.before = record(self.base)
        if self.before["size"] != self.config["base_candidate_size"] or self.before["sha256"] != self.config["base_candidate_sha256"]:
            raise RuntimeError("r7 input identity mismatch")
        (self.stage / "input-provenance-before.json").write_text(json.dumps({"base_candidate": self.before}, indent=2) + "\n", encoding="utf-8")

    def extract_and_patch_boot(self) -> Path:
        with self.base.open("rb") as source:
            main = parse_main_header(source)
            entries = {item["filename"]: item for item in parse_file_headers(source, main["num_files"])}
            boot = entries.get("boot.fex")
            if boot is None: raise RuntimeError("r7 container has no boot.fex")
            source.seek(boot["offset"])
            data = bytearray(source.read(boot["stored_len"]))
        if len(data) != boot["stored_len"] or data[:8] != b"ANDROID!": raise RuntimeError("invalid r7 boot payload")
        if int.from_bytes(data[40:44], "little") != 3: raise RuntimeError("unexpected boot header version")
        existing = bytes(data[CMDLINE_OFFSET:CMDLINE_OFFSET + CMDLINE_BYTES]).split(b"\0", 1)[0]
        if existing: raise RuntimeError("r7 boot cmdline must remain empty for this bounded diagnostic")
        cmdline = str(self.config["boot_cmdline"]).encode("ascii")
        if len(cmdline) >= CMDLINE_BYTES: raise RuntimeError("boot cmdline too long")
        data[CMDLINE_OFFSET:CMDLINE_OFFSET + CMDLINE_BYTES] = b"\0" * CMDLINE_BYTES
        data[CMDLINE_OFFSET:CMDLINE_OFFSET + len(cmdline)] = cmdline
        output = self.stage / "boot.fex"
        output.write_bytes(data)
        (self.stage / "boot-console.json").write_text(json.dumps({"old_cmdline": existing.decode("ascii"), "new_cmdline": cmdline.decode("ascii"), "boot_payload_bytes": len(data)}, indent=2) + "\n", encoding="utf-8")
        return output

    def pack(self, boot: Path) -> Path:
        firmware, audit = self.stage / ("x12-" + self.candidate_id + ".img"), self.stage / "outer-payload-audit.json"
        self.run([sys.executable, str(TOOLS / "pack_image_preserving.py"), "--source", str(self.base), "--output", str(firmware), "--replace", "boot.fex=" + str(boot), "--audit", str(audit)])
        self.run([sys.executable, str(TOOLS / "sunxi_image_tool.py"), "verify", str(firmware)])
        actions = {item["filename"]: item["action"] for item in json.loads(audit.read_text(encoding="utf-8"))["payloads"]}
        container = self.config["container"]
        assert isinstance(container, dict)
        if len(actions) != container["total_entries"] or actions.get(container["replacement"]) != "replacement" or actions.get(container["companion"]) != "companion" or sum(action == "preserved" for action in actions.values()) != container["preserved_entries"]:
            raise RuntimeError("outer payload preservation mismatch")
        return firmware

    def finish(self, firmware: Path) -> None:
        after = record(self.base)
        if after != self.before: raise RuntimeError("r7 input changed")
        (self.stage / "input-provenance-after.json").write_text(json.dumps({"base_candidate": after}, indent=2) + "\n", encoding="utf-8")
        result = {"id": self.candidate_id, "status": "BUILT", "firmware": record(firmware), "base_candidate": after, "repair": "Set boot cmdline to console=ttyS0,115200n8 ignore_loglevel for first-stage init diagnostics.", "outer_payload_preservation": "48 payloads exact; boot.fex replaced; Vboot.fex regenerated.", "physical_device_actions_performed": False}
        (self.stage / "build-result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        for name in ("build-result.json", "boot-console.json", "outer-payload-audit.json", "input-provenance-before.json", "input-provenance-after.json"):
            path = self.stage / name
            path.write_text(json.dumps(rewrite_paths(json.loads(path.read_text(encoding="utf-8")), self.stage, self.final), indent=2) + "\n", encoding="utf-8")
        sums = [digest(path) + "  " + path.name for path in sorted(self.stage.iterdir()) if path.is_file() and path.name != "SHA256SUMS"]
        (self.stage / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
        os.replace(self.stage, self.final)

    def build(self) -> None:
        started = time.time()
        try:
            self.setup(); boot = self.extract_and_patch_boot(); firmware = self.pack(boot); self.finish(firmware)
            print("SUCCESS: " + str(self.final) + " in %.1fs" % (time.time() - started))
        except Exception:
            if self.stage.exists() and not self.keep_failed: shutil.rmtree(self.stage)
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG); parser.add_argument("--keep-failed", action="store_true")
    args = parser.parse_args(); BuildR8(json.loads(args.config.read_text(encoding="utf-8")), args.keep_failed).build()


if __name__ == "__main__": main()
