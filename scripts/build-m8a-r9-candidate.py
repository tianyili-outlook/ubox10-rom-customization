#!/usr/bin/env python3
"""Build r9 by correcting only the canonical /vendor mount-point topology."""
from __future__ import annotations

import argparse
import hashlib
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
DEFAULT_CONFIG = REPO / "configs" / "candidates" / "m8a-initial-atv-r9.json"
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


class BuildR9:
    def __init__(self, config: dict[str, object], keep_failed: bool) -> None:
        self.config, self.keep_failed = config, keep_failed
        self.candidate_id = str(config["id"])
        self.final = REPO / "out" / "candidates" / self.candidate_id
        self.stage = self.final.parent / ("." + self.candidate_id + ".staging-" + uuid.uuid4().hex)
        self.log_file = self.stage / "logs" / "01-commands.log"
        self.base = REPO / str(config["base_candidate_relative"])
        self.before: dict[str, object] | None = None
        self.logical_before: dict[str, dict[str, object]] = {}
        self.logical_after: dict[str, dict[str, object]] = {}

    @staticmethod
    def wsl_path(path: Path) -> str:
        value = path.resolve()
        return "/mnt/" + value.drive[0].lower() + value.as_posix()[2:]

    def log(self, message: str) -> None:
        print(message, flush=True)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with self.log_file.open("a", encoding="utf-8") as stream:
            stream.write(message + "\n")

    def run(self, command: list[str], *, output: Path | None = None) -> None:
        self.log("$ " + subprocess.list2cmdline(command))
        destination = output if output is not None else self.log_file
        with destination.open("w" if output is not None else "a", encoding="utf-8", newline="\n") as stream:
            done = subprocess.run(command, cwd=REPO, stdout=stream, stderr=subprocess.STDOUT, text=True)
        if done.returncode:
            raise RuntimeError("failed command: " + command[0])

    def setup(self) -> None:
        if self.final.exists():
            raise RuntimeError("refusing to overwrite final output: " + str(self.final))
        if not self.base.is_file():
            raise RuntimeError("missing r8 base candidate: " + str(self.base))
        self.stage.mkdir(parents=True)
        self.before = record(self.base)
        if self.before["size"] != self.config["base_candidate_size"] or self.before["sha256"] != self.config["base_candidate_sha256"]:
            raise RuntimeError("r8 base candidate identity mismatch")
        (self.stage / "input-provenance-before.json").write_text(json.dumps({"base_candidate": self.before}, indent=2) + "\n", encoding="utf-8")

    def extract_r8(self) -> tuple[Path, Path, Path, Path]:
        outer = self.stage / "r8-outer"
        outer.mkdir()
        for name in ("super.fex", "vbmeta_system.fex"):
            self.run([sys.executable, str(TOOLS / "sunxi_image_tool.py"), "extract", "-o", str(outer), "-f", name, str(self.base)])
        source_super = outer / "super.fex"
        if source_super.stat().st_size != self.config["source_super_size"] or digest(source_super) != self.config["source_super_sha256"]:
            raise RuntimeError("r8 super identity mismatch")

        raw_super = self.stage / "r8-super.raw.img"
        logical = self.stage / "r8-logical"
        logical.mkdir()
        self.run([str(TOOLS / "simg2img.exe"), str(source_super), str(raw_super)])
        self.run([sys.executable, str(TOOLS / "lpunpack.py"), str(raw_super), str(logical)])
        specs = self.config["logical_partitions"]
        assert isinstance(specs, dict)
        for name, expected in specs.items():
            assert isinstance(expected, dict)
            path = logical / (name + ".img")
            value = record(path)
            if value["size"] != expected["size"] or value["sha256"] != expected["sha256"]:
                raise RuntimeError("r8 logical identity mismatch: " + name)
            self.logical_before[name] = value
        return source_super, raw_super, logical / "system_a.img", outer / "vbmeta_system.fex"

    def repair_system(self, source: Path) -> Path:
        system = self.stage / "system_a.img"
        shutil.copyfile(source, system)
        self.run([sys.executable, str(TOOLS / "avbtool.py"), "erase_footer", "--image", str(system)])
        work_size = str(self.config["system_work_size"])
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "truncate", "-s", work_size, self.wsl_path(system)])
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "resize2fs", self.wsl_path(system), work_size])
        mount_dir = self.stage / "system-mount"
        mount_dir.mkdir()
        self.run([
            "wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "bash",
            self.wsl_path(REPO / "scripts" / "fix-m8-system-vendor-topology.sh"),
            self.wsl_path(system), self.wsl_path(mount_dir),
        ])
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "resize2fs", "-M", self.wsl_path(system)])
        mount_dir.rmdir()

        avb = self.config["avb"]
        assert isinstance(avb, dict)
        key = REPO / str(avb["key_relative"])
        self.run([
            sys.executable, str(TOOLS / "avbtool.py"), "add_hashtree_footer",
            "--image", str(system), "--partition_name", "system",
            "--partition_size", str(avb["partition_size"]), "--hash_algorithm", "sha256",
            "--salt", str(avb["salt"]), "--do_not_generate_fec",
            "--prop", "com.ubox10.candidate.id:" + self.candidate_id,
            "--prop", "com.ubox10.avb.fec:none", "--key", str(key), "--algorithm", "SHA256_RSA2048",
        ])
        if system.stat().st_size != avb["partition_size"]:
            raise RuntimeError("signed r9 system_a size mismatch")
        return system

    def make_vbmeta_system(self, system: Path) -> Path:
        avb = self.config["avb"]
        assert isinstance(avb, dict)
        output = self.stage / "vbmeta_system.fex"
        self.run([
            sys.executable, str(TOOLS / "avbtool.py"), "make_vbmeta_image", "--output", str(output),
            "--key", str(REPO / str(avb["key_relative"])), "--algorithm", "SHA256_RSA2048",
            "--rollback_index", str(avb["rollback_index"]),
            "--rollback_index_location", str(avb["rollback_index_location"]),
            "--include_descriptors_from_image", str(system),
        ])
        return output

    def make_super(self, raw_super: Path, system: Path) -> Path:
        offset = int(self.config["system_a_physical_offset"])
        with raw_super.open("r+b") as destination, system.open("rb") as source:
            destination.seek(offset)
            shutil.copyfileobj(source, destination, CHUNK)
        output = self.stage / "super.img"
        self.run([str(TOOLS / "img2simg.exe"), str(raw_super), str(output)])
        return output

    def inventory_system(self, image: Path, label: str) -> Path:
        mount_dir = self.stage / (label + "-mount")
        mount_dir.mkdir()
        output = self.stage / (label + "-filesystem-manifest.json")
        shell = self.stage / ("inventory-" + label + ".sh")
        shell.write_text(
            "#!/usr/bin/env bash\nset -euo pipefail\n"
            f"image='{self.wsl_path(image)}'\nroot='{self.wsl_path(mount_dir)}'\n"
            "cleanup() { mountpoint -q \"$root\" && umount \"$root\" || true; }\n"
            "trap cleanup EXIT INT TERM\nmount -o loop,ro \"$image\" \"$root\"\n"
            f"python3 '{self.wsl_path(REPO / 'scripts' / 'inventory-ext4-tree.py')}' \"$root\" --output '{self.wsl_path(output)}'\n",
            encoding="utf-8",
            newline="\n",
        )
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "bash", self.wsl_path(shell)])
        mount_dir.rmdir()
        shell.unlink()
        return output

    @staticmethod
    def _manifest_map(path: Path) -> dict[str, dict[str, object]]:
        document = json.loads(path.read_text(encoding="utf-8"))
        return {item["path"]: item for item in document["entries"]}

    def validate_system_diff(self, before_image: Path, after_image: Path) -> dict[str, object]:
        before_path = self.inventory_system(before_image, "r8-system")
        after_path = self.inventory_system(after_image, "r9-system")
        before, after = self._manifest_map(before_path), self._manifest_map(after_path)
        topology = lambda path: path == "/vendor" or path.startswith("/vendor/") or path == "/system/vendor" or path.startswith("/system/vendor/")
        unexpected: list[str] = []
        for path in sorted(set(before) | set(after)):
            if topology(path):
                continue
            left, right = before.get(path), after.get(path)
            if path in {"/", "/system"} and left is not None and right is not None:
                left, right = dict(left), dict(right)
                left.pop("nlink", None); right.pop("nlink", None)
            if left != right:
                unexpected.append(path)
        if unexpected:
            raise RuntimeError("unexpected system filesystem differences: " + ", ".join(unexpected[:16]))

        expected = {
            "/vendor": {"type": "directory", "mode": "0755", "uid": 0, "gid": 2000},
            "/system/vendor": {"type": "symlink", "mode": "0644", "uid": 0, "gid": 0, "target": "/vendor"},
        }
        for path, fields in expected.items():
            actual = after.get(path)
            if actual is None or any(actual.get(key) != value for key, value in fields.items()):
                raise RuntimeError("r9 topology mismatch: " + path)
        for path in ("/product", "/vendor_dlkm", "/oem"):
            actual = after.get(path)
            if actual is None or actual.get("type") != "directory":
                raise RuntimeError("non-canonical early mount target: " + path)

        label = "753A6F626A6563745F723A76656E646F725F66696C653A733000"
        for path in expected:
            if after[path].get("xattrs", {}).get("security.selinux") != label:
                raise RuntimeError("vendor SELinux label mismatch: " + path)
        result = {
            "reference_test8r2": {
                "/vendor": {"lstat": expected["/vendor"], "readlink": None, "realpath": "/vendor"},
                "/system/vendor": {"lstat": expected["/system/vendor"], "stat": expected["/vendor"], "readlink": "/vendor", "realpath": "/vendor"},
            },
            "r9": {
                "/vendor": {"lstat": after["/vendor"], "readlink": None, "realpath": "/vendor", "mountable": True},
                "/system/vendor": {"lstat": after["/system/vendor"], "stat": after["/vendor"], "readlink": "/vendor", "realpath": "/vendor"},
            },
            "other_early_mount_points": {path: {"type": after[path]["type"], "realpath": path, "canonical": True} for path in ("/product", "/vendor_dlkm", "/oem")},
            "unexpected_system_differences": unexpected,
            "allowed_difference_scope": ["/vendor", "/system/vendor/**", "parent directory link counts"],
        }
        (self.stage / "topology-validation.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return result

    def validate_super(self, source_super: Path, candidate_super: Path, source_system: Path) -> Path:
        raw = self.stage / "validation-super.raw.img"
        logical = self.stage / "validation-logical"
        logical.mkdir()
        self.run([str(TOOLS / "simg2img.exe"), str(candidate_super), str(raw)])
        self.run([str(TOOLS / "lpdumps.exe"), "-j", str(raw)], output=self.stage / "super-metadata.json")
        json.loads((self.stage / "super-metadata.json").read_text(encoding="utf-8"))
        self.run([sys.executable, str(TOOLS / "lpunpack.py"), str(raw), str(logical)])
        specs = self.config["logical_partitions"]
        assert isinstance(specs, dict)
        for name in specs:
            path = logical / (name + ".img")
            self.logical_after[name] = record(path)
            if name != "system_a" and self.logical_after[name]["sha256"] != self.logical_before[name]["sha256"]:
                raise RuntimeError("non-system logical partition changed: " + name)
        self.validate_system_diff(source_system, logical / "system_a.img")
        return logical / "system_a.img"

    def verify_avb(self, system: Path, vbmeta_system: Path) -> None:
        avb = self.config["avb"]
        assert isinstance(avb, dict)
        key = self.wsl_path(REPO / str(avb["key_relative"]))
        tool = self.wsl_path(TOOLS / "avbtool.py")
        view = self.stage / "avb-validation"
        view.mkdir()
        os.link(system, view / "system.img")
        shutil.copyfile(vbmeta_system, view / "vbmeta_system.img")
        self.run([
            "wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "python3", tool,
            "verify_image", "--image", self.wsl_path(view / "vbmeta_system.img"), "--key", key,
        ])
        self.run([sys.executable, str(TOOLS / "avbtool.py"), "info_image", "--image", str(system)], output=self.stage / "system-avb-info.txt")
        self.run([sys.executable, str(TOOLS / "avbtool.py"), "info_image", "--image", str(vbmeta_system)], output=self.stage / "vbmeta-system-avb-info.txt")

    def pack(self, super_image: Path, vbmeta_system: Path) -> Path:
        firmware = self.stage / ("x12-" + self.candidate_id + ".img")
        audit = self.stage / "outer-payload-audit.json"
        self.run([
            sys.executable, str(TOOLS / "pack_image_preserving.py"), "--source", str(self.base), "--output", str(firmware),
            "--replace", "super.fex=" + str(super_image), "--replace", "vbmeta_system.fex=" + str(vbmeta_system), "--audit", str(audit),
        ])
        self.run([sys.executable, str(TOOLS / "sunxi_image_tool.py"), "verify", str(firmware)])
        actions = {item["filename"]: item["action"] for item in json.loads(audit.read_text(encoding="utf-8"))["payloads"]}
        container = self.config["container"]
        assert isinstance(container, dict)
        if len(actions) != container["total_entries"] or sum(value == "preserved" for value in actions.values()) != container["preserved_entries"]:
            raise RuntimeError("outer preservation count mismatch")
        for name in container["replacements"]:
            if actions.get(name) != "replacement": raise RuntimeError("missing outer replacement: " + name)
        for name in container["companions"]:
            if actions.get(name) != "companion": raise RuntimeError("missing regenerated companion: " + name)
        for name in ("Vsuper.fex", "Vvbmeta_system.fex"):
            self.run([sys.executable, str(TOOLS / "sunxi_image_tool.py"), "extract", "-o", str(self.stage), "-f", name, str(firmware)])
        return firmware

    def finish(self, firmware: Path, super_image: Path, vbmeta_system: Path) -> None:
        after = record(self.base)
        if after != self.before:
            raise RuntimeError("protected r8 base changed")
        (self.stage / "input-provenance-after.json").write_text(json.dumps({"base_candidate": after}, indent=2) + "\n", encoding="utf-8")
        logical_before = {
            name: {"partition": name, "container": str(self.base) + "#super.fex", "size": value["size"], "sha256": value["sha256"]}
            for name, value in self.logical_before.items()
        }
        logical_after = {
            name: {"partition": name, "container": str(super_image), "size": value["size"], "sha256": value["sha256"]}
            for name, value in self.logical_after.items()
        }
        result = {
            "id": self.candidate_id,
            "status": "BUILT",
            "firmware": record(firmware),
            "base_candidate": after,
            "system_a": logical_after["system_a"],
            "super": record(super_image),
            "vbmeta_system": record(vbmeta_system),
            "derived_checks": {name: record(self.stage / name) for name in ("Vsuper.fex", "Vvbmeta_system.fex")},
            "logical_before": logical_before,
            "logical_after": logical_after,
            "repair": "Reverse the system-root vendor topology to canonical /vendor directory plus /system/vendor -> /vendor.",
            "payload_delta": ["system_a", "super.fex", "Vsuper.fex", "vbmeta_system.fex", "Vvbmeta_system.fex"],
            "protected_contract": self.config["protected_contract"],
            "physical_device_actions_performed": False,
        }
        (self.stage / "build-result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

        for directory in ("r8-logical", "validation-logical", "r8-outer"):
            shutil.rmtree(self.stage / directory)
        shutil.rmtree(self.stage / "avb-validation")
        for name in ("r8-super.raw.img", "validation-super.raw.img", "system_a.img", "r8-system-filesystem-manifest.json", "r9-system-filesystem-manifest.json"):
            (self.stage / name).unlink()
        for name in ("build-result.json", "outer-payload-audit.json", "input-provenance-before.json", "input-provenance-after.json"):
            path = self.stage / name
            path.write_text(json.dumps(rewrite_paths(json.loads(path.read_text(encoding="utf-8")), self.stage, self.final), indent=2) + "\n", encoding="utf-8")
        sums = [digest(path) + "  " + path.name for path in sorted(self.stage.iterdir()) if path.is_file() and path.name != "SHA256SUMS"]
        (self.stage / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
        os.replace(self.stage, self.final)

    def build(self) -> None:
        started = time.time()
        try:
            self.setup()
            source_super, raw_super, source_system, _old_vbmeta = self.extract_r8()
            system = self.repair_system(source_system)
            vbmeta_system = self.make_vbmeta_system(system)
            super_image = self.make_super(raw_super, system)
            validated_system = self.validate_super(source_super, super_image, source_system)
            self.verify_avb(validated_system, vbmeta_system)
            firmware = self.pack(super_image, vbmeta_system)
            self.finish(firmware, super_image, vbmeta_system)
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
    BuildR9(json.loads(args.config.read_text(encoding="utf-8")), args.keep_failed).build()


if __name__ == "__main__":
    main()
