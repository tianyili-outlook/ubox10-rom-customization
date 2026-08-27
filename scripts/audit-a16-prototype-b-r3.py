#!/usr/bin/env python3
"""Run the full B1 audit plus the B r3 root /vendor single-cause gate."""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import re
import subprocess
import sys


REPO = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE = REPO / "out/candidates/a16-prototype-b-r3"
DEFAULT_CONFIG = REPO / "configs/candidates/a16-prototype-b-r3.json"
DEFAULT_AOSP = Path("/work/src/ubox10-a16-ceiling")

AUDIT_PATH = REPO / "scripts/audit-a16-prototype-b-r1.py"
AUDIT_SPEC = importlib.util.spec_from_file_location("a16_b_shared_auditor_for_r3", AUDIT_PATH)
if AUDIT_SPEC is None or AUDIT_SPEC.loader is None:
    raise RuntimeError(f"cannot import shared Prototype B auditor: {AUDIT_PATH}")
AUDIT = importlib.util.module_from_spec(AUDIT_SPEC)
sys.modules[AUDIT_SPEC.name] = AUDIT
AUDIT_SPEC.loader.exec_module(AUDIT)


class Auditor(AUDIT.Auditor):
    @staticmethod
    def symlink_target(image: Path, path: str) -> str | None:
        output = subprocess.check_output(
            ["debugfs", "-R", f"stat {path}", str(image)],
            text=True, stderr=subprocess.STDOUT,
        )
        match = re.search(r'Fast link dest: "([^"]+)"', output)
        return match.group(1) if match else None

    @staticmethod
    def file_text(image: Path, path: str) -> str:
        return subprocess.check_output(
            ["debugfs", "-R", f"cat {path}", str(image)],
            text=True, stderr=subprocess.DEVNULL,
        )

    def audit_root_mountpoint_delta(self, images: dict[str, Path]) -> dict[str, object]:
        continuation = self.cfg["_continuation"]
        base_spec = continuation["base_artifacts"]["system_a"]
        base_path = Path(str(base_spec["path"]))
        if not base_path.is_absolute():
            base_path = REPO / base_path
        base_record = AUDIT.R3.record(base_path)
        if (
            base_record["size"] != base_spec["size"]
            or base_record["sha256"] != base_spec["sha256"]
        ):
            raise RuntimeError("frozen r2 system identity changed")
        self.r1_system_mount.mkdir(parents=True)
        self.run([
            "sudo", "mount", "-o", "loop,ro,noload", str(base_path),
            str(self.r1_system_mount),
        ])
        self.mounted.append(self.r1_system_mount)

        before = AUDIT.R4.tree_manifest(self.r1_system_mount)
        after = AUDIT.R4.tree_manifest(self.mounts / "system")
        added = sorted(set(after) - set(before))
        removed = sorted(set(before) - set(after))
        changed = sorted(
            name for name in set(before) & set(after) if before[name] != after[name]
        )
        if added or removed or changed != ["vendor"]:
            raise RuntimeError(
                f"r3 system semantic delta expanded: added={added} "
                f"removed={removed} changed={changed}"
            )

        r4_system = REPO / "out/candidates/a16-prototype-a-r4/system_a.img"
        contract = continuation["root_mountpoint_contract"]
        expected_vendor = {
            "type": contract["r4"]["type"],
            "mode": contract["r4"]["mode"],
            "uid": contract["r4"]["uid"],
            "gid": contract["r4"]["gid"],
            "selinux": contract["r4"]["selinux"],
        }
        r4_vendor = self.inode_contract(r4_system, "/vendor")
        r2_vendor = self.inode_contract(base_path, "/vendor")
        r3_vendor = self.inode_contract(images["system"], "/vendor")
        if (
            r4_vendor != expected_vendor
            or r3_vendor != expected_vendor
            or r2_vendor is None
            or r2_vendor["type"] != "symlink"
            or self.symlink_target(base_path, "/vendor") != "/system/vendor"
            or self.symlink_target(images["system"], "/vendor") is not None
        ):
            raise RuntimeError("r4/r2/r3 /vendor contracts do not prove the single-cause restoration")

        root_objects: dict[str, object] = {}
        for path in contract["audited_root_objects"]:
            values = {
                "r4": self.inode_contract(r4_system, path),
                "r2": self.inode_contract(base_path, path),
                "r3": self.inode_contract(images["system"], path),
            }
            if path == "/vendor":
                values["r2_target"] = self.symlink_target(base_path, path)
                values["r3_target"] = self.symlink_target(images["system"], path)
            elif values["r2"] != values["r4"] or values["r3"] != values["r4"]:
                raise RuntimeError(f"peer root object contract differs from accepted r4: {path}")
            root_objects[path] = values

        skip_path = "/system/system_ext/etc/init/config/skip_mount.cfg"
        skip = {
            "r4": self.file_text(r4_system, skip_path),
            "r2": self.file_text(base_path, skip_path),
            "r3": self.file_text(images["system"], skip_path),
        }
        if len(set(skip.values())) != 1:
            raise RuntimeError("r3 changed GSI skip-mount configuration")
        patterns = [
            line for line in skip["r3"].splitlines()
            if line and not line.startswith("#")
        ]
        for required in ("/oem", "/product", "/system_ext"):
            if required not in patterns:
                raise RuntimeError(f"GSI skip-mount pattern missing: {required}")

        return {
            "result": "PASS_SINGLE_CAUSE_VENDOR_ROOT_MOUNTPOINT_RESTORED",
            "r2_system": AUDIT.R3.record(base_path),
            "r3_system": AUDIT.R3.record(images["system"]),
            "tree_delta_from_r2": {"added": added, "removed": removed, "changed": changed},
            "vendor_contract": {"r4": r4_vendor, "r2": r2_vendor, "r3": r3_vendor},
            "r2_vendor_symlink_target": "/system/vendor",
            "r3_vendor_symlink_target": None,
            "root_objects": root_objects,
            "fstab_vendor_entry": continuation["root_cause"]["fstab"]["vendor_entry"],
            "fstab_sha256": continuation["root_cause"]["fstab"]["sha256"],
            "first_stage_init_sha256": continuation["root_cause"]["first_stage_init"]["r2_sha256"],
            "skip_mount_path": skip_path,
            "skip_mount_patterns": patterns,
            "canonical_mount_contract": "realpath(/vendor) must equal /vendor before required vendor mount",
            "proven_r2_failure": "realpath(/vendor) resolved to /system/vendor because /vendor was a symlink",
            "result_scope": "OFFLINE ROOT-CAUSE CORRECTION; PHYSICAL BOOT NOT YET VALIDATED",
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--aosp", type=Path, default=DEFAULT_AOSP)
    parser.add_argument("--kernel-evidence", type=Path)
    parser.add_argument("--resume", action="store_true")
    Auditor(parser.parse_args()).execute()


if __name__ == "__main__":
    main()
