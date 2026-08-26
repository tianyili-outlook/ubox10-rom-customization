#!/usr/bin/env python3
"""Audit the strict two-delta Android 16 Prototype A r4 candidate."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys


REPO = Path(__file__).resolve().parents[1]
R3_PATH = REPO / "scripts/audit-a16-prototype-a-r3.py"
SPEC = importlib.util.spec_from_file_location("a16_prototype_a_r3_auditor", R3_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import r3 candidate auditor: {R3_PATH}")
R3 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = R3
SPEC.loader.exec_module(R3)

DEFAULT_CANDIDATE = REPO / "out/candidates/a16-prototype-a-r4"
DEFAULT_CONFIG = REPO / "configs/candidates/a16-prototype-a-r4.json"
DEFAULT_AOSP = Path("/work/src/ubox10-a16-ceiling")


def privileged_text(path: Path) -> str:
    return subprocess.check_output(["sudo", "cat", str(path)]).decode(
        "utf-8", errors="replace"
    )


def privileged_record(path: Path) -> dict[str, object]:
    size = int(
        subprocess.check_output(
            ["sudo", "stat", "--format=%s", str(path)], text=True
        ).strip()
    )
    sha256 = subprocess.check_output(
        ["sudo", "sha256sum", str(path)], text=True
    ).split()[0].upper()
    return {"path": str(path), "size": size, "sha256": sha256}


def tree_manifest(root: Path) -> dict[str, dict[str, object]]:
    """Return a content/type manifest without following image symlinks."""
    # Android images deliberately contain root-only directories.  Run only the
    # read-only inventory under sudo; the audit process and output stay unprivileged.
    inventory = subprocess.check_output(
        [
            "sudo", "find", str(root), "-xdev", "-printf",
            r"%P\t%y\t%m\t%s\t%l\0",
        ]
    )
    hashes = subprocess.check_output(
        [
            "sudo", "find", str(root), "-xdev", "-type", "f",
            "-exec", "sha256sum", "--zero", "{}", "+",
        ]
    )
    by_path: dict[str, str] = {}
    for item in hashes.split(b"\0"):
        if not item:
            continue
        if len(item) < 67 or item[64:66] != b"  ":
            raise RuntimeError(f"unparseable sha256sum record: {item[:100]!r}")
        path = Path(os.fsdecode(item[66:]))
        by_path[path.relative_to(root).as_posix()] = item[:64].decode().upper()

    result: dict[str, dict[str, object]] = {}
    kinds = {"d": "directory", "f": "file", "l": "symlink"}
    for item in inventory.split(b"\0"):
        if not item:
            continue
        relative_raw, kind_raw, mode_raw, size_raw, target_raw = item.split(b"\t", 4)
        relative = os.fsdecode(relative_raw)
        kind = kinds.get(kind_raw.decode(), "other")
        record: dict[str, object] = {"type": kind, "mode": mode_raw.decode()}
        if kind == "file":
            record.update({"size": int(size_raw), "sha256": by_path[relative]})
        elif kind == "symlink":
            record["target"] = os.fsdecode(target_raw)
        result[relative] = record
    return dict(sorted(result.items()))


def exact_property_lines(text: str, name: str) -> list[str]:
    prefix = name + "="
    return [line for line in text.splitlines() if line.startswith(prefix)]


class R4Auditor(R3.Auditor):
    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__(args)
        self.cfg = json.loads(args.config.read_text(encoding="utf-8"))
        if self.cfg["id"] != "a16-prototype-a-r4":
            raise RuntimeError("r4 auditor received the wrong candidate contract")
        if self.build_result["id"] != self.cfg["id"]:
            raise RuntimeError("candidate/build contract ID mismatch")
        self.r3_system_mount = self.mounts / "r3-system"

    def mount_r3_system(self) -> None:
        self.r3_system_mount.mkdir(parents=True, exist_ok=True)
        image = Path(str(self.cfg["base_candidate"]["path"])).parent / "system_a.img"
        expected = self.cfg["r3_baseline"]["system"]
        actual = R3.record(image)
        if actual["size"] != expected["size"] or actual["sha256"] != expected["sha256"]:
            raise RuntimeError(f"r3 system baseline identity changed: {actual}")
        self.run(["sudo", "mount", "-o", "loop,ro,noload", str(image), str(self.r3_system_mount)])
        self.mounted.append(self.r3_system_mount)

    def audit_two_fixes(self) -> dict[str, object]:
        system_prop = self.root / "system/build.prop"
        vendor_prop = self.root / "vendor/build.prop"
        system_text = privileged_text(system_prop)
        vendor_text = privileged_text(vendor_prop)
        if exact_property_lines(system_text, "ro.hardware.egl") != ["ro.hardware.egl=mali"]:
            raise RuntimeError("final system property does not select exactly EGL suffix mali")
        if exact_property_lines(vendor_text, "ro.board.platform") != ["ro.board.platform=apollo"]:
            raise RuntimeError("accepted vendor board platform is not exactly apollo")

        prop_files: list[Path] = []
        for partition in ("system", "system_ext", "product", "vendor"):
            root = self.root / partition
            if root.is_dir():
                output = subprocess.check_output(
                    [
                        "sudo", "find", "-H", str(root), "-xdev", "-type", "f",
                        "(", "-name", "*.prop", "-o", "-name", "build.prop", ")",
                        "-print0",
                    ]
                )
                prop_files.extend(
                    Path(os.fsdecode(value)) for value in output.split(b"\0") if value
                )
        prop_files = sorted(set(prop_files))
        persisted = []
        board_mali = []
        for path in prop_files:
            text = privileged_text(path)
            if exact_property_lines(text, "persist.graphics.egl"):
                persisted.append(str(path.relative_to(self.root)))
            if "ro.board.platform=mali" in text.splitlines():
                board_mali.append(str(path.relative_to(self.root)))
        if persisted:
            raise RuntimeError(f"formal image config contains persist.graphics.egl: {persisted}")
        if board_mali:
            raise RuntimeError(f"formal image changed board platform to mali: {board_mali}")

        blobs = {
            "mali_egl": self.root / "vendor/lib/egl/libGLES_mali.so",
            "gralloc_apollo": self.root / "vendor/lib/hw/gralloc.apollo.so",
            "hwcomposer_apollo": self.root / "vendor/lib/hw/hwcomposer.apollo.so",
        }
        for label, path in blobs.items():
            if subprocess.run(["sudo", "test", "-f", str(path)], check=False).returncode:
                raise RuntimeError(f"required accepted graphics blob is missing: {label}: {path}")

        layout = self.root / "system/usr/keylayout/sunxi-ir.kl"
        tracked = REPO / "configs/aosp/architecture-ceiling-a16/device/ubox/ceiling/sunxi-ir.kl"
        generic = self.args.aosp / "frameworks/base/data/keyboards/Generic.kl"
        final_text = privileged_text(layout)
        if final_text != tracked.read_text(encoding="utf-8"):
            raise RuntimeError("installed sunxi-ir layout differs from the tracked source")
        generic_lines = generic.read_text(encoding="utf-8").splitlines()
        layout_lines = final_text.splitlines()
        if len(generic_lines) != len(layout_lines):
            raise RuntimeError("sunxi-ir layout changed Generic.kl line count")
        differences = [
            {"line": index, "generic": before, "sunxi_ir": after}
            for index, (before, after) in enumerate(zip(generic_lines, layout_lines), start=1)
            if before != after
        ]
        if differences != [{
            "line": 311,
            "generic": '# key 352 "KEY_OK"',
            "sunxi_ir": "key 352   DPAD_CENTER",
        }]:
            raise RuntimeError(f"sunxi-ir layout is not the exact one-line delta: {differences}")
        mappings = [
            re.split(r"\s+", line.strip())
            for line in layout_lines
            if line.strip() and not line.lstrip().startswith("#")
        ]
        scan_352 = [parts for parts in mappings if len(parts) >= 3 and parts[:2] == ["key", "352"]]
        if scan_352 != [["key", "352", "DPAD_CENTER"]]:
            raise RuntimeError(f"scanCode 352 mapping is not exact: {scan_352}")

        return {
            "egl": {
                "ro_hardware_egl": "mali",
                "ro_board_platform": "apollo",
                "persist_graphics_egl_default": "ABSENT",
                "loader_precedence": [
                    "persist.graphics.egl", "ro.hardware.egl", "ro.board.platform",
                ],
                "accepted_graphics_blobs": {
                    label: privileged_record(path) for label, path in blobs.items()
                },
                "result": "PASS_OFFLINE_ASSERTION",
            },
            "remote_ok": {
                "input_device": "sunxi-ir",
                "installed_keylayout": str(layout.relative_to(self.root)),
                "scan_code": 352,
                "android_key_symbol": "DPAD_CENTER",
                "android_key_code": 23,
                "generic_equivalence_except_scan_352": True,
                "other_keylayout_lines_changed": 0,
                "result": "PASS_OFFLINE_ASSERTION",
            },
        }

    def audit_system_tree_delta(self) -> dict[str, object]:
        before = tree_manifest(self.r3_system_mount)
        after = tree_manifest(self.mounts / "system")
        before_names = set(before)
        after_names = set(after)
        added = sorted(after_names - before_names)
        removed = sorted(before_names - after_names)
        changed = sorted(name for name in before_names & after_names if before[name] != after[name])
        actual = {"added": added, "removed": removed, "changed": changed}
        expected = self.cfg.get("system_tree_delta")
        if expected is None:
            raise RuntimeError(
                "system_tree_delta is not pinned in the r4 candidate config; actual="
                + json.dumps(actual, sort_keys=True)
            )
        expected_sets = {
            key: sorted(str(value) for value in expected[key])
            for key in ("added", "removed", "changed")
        }
        if actual != expected_sets:
            raise RuntimeError(
                "r4 system file-content/type delta changed: "
                f"actual={actual} expected={expected_sets}"
            )
        detail = {
            name: {"r3": before.get(name), "r4": after.get(name)}
            for name in sorted(set(added + removed + changed))
        }
        report = {**actual, "detail": detail}
        (self.audit / "system-tree-delta.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return {
            **actual,
            "machine_readable": R3.record(self.audit / "system-tree-delta.json"),
            "classification": expected["classification"],
            "functional_delta": [
                "ro.hardware.egl=mali",
                "sunxi-ir scanCode 352 -> DPAD_CENTER",
            ],
            "result": "PASS_EXACT_PINNED_R3_TO_R4_TREE_DELTA",
        }

    def audit_preservation(self, images: dict[str, Path]) -> dict[str, object]:
        expected = self.cfg["accepted"]["logical"]
        preserved_images = {}
        for label, image_key in (("vendor_a", "vendor"), ("product_a", "product")):
            actual = R3.record(images[image_key])
            spec = expected[label]
            if actual["size"] != spec["size"] or actual["sha256"] != spec["sha256"]:
                raise RuntimeError(f"r4 changed accepted {label}: {actual}")
            preserved_images[label] = actual
        for label, relative in (("boot", "boot.fex"), ("vendor_dlkm", "vendor_dlkm_a.img")):
            actual = R3.record(self.candidate / relative)
            spec = self.cfg["r3_baseline"][label]
            if actual["size"] != spec["size"] or actual["sha256"] != spec["sha256"]:
                raise RuntimeError(f"r4 changed r3 {label}: {actual}")
            preserved_images[label] = actual
        kernel = Path(str(self.build_result["kernel"]["path"]))
        kernel_expected = self.cfg["kernel_build"]["image"]
        kernel_actual = R3.record(kernel)
        if (
            kernel_actual["size"] != kernel_expected["size"]
            or kernel_actual["sha256"] != kernel_expected["sha256"]
            or self.build_result.get("kernel_rebuilt") is not False
        ):
            raise RuntimeError("r4 kernel is not the byte-preserved r3 Path-A kernel")
        outer = self.build_result["outer"]
        if (
            outer["changed_payloads"]
            != sorted(self.cfg["container"]["replacements"] + self.cfg["container"]["companions"])
            or outer["preserved_payload_count"] != 46
            or outer.get("all_other_payload_bytes_exact") is not True
        ):
            raise RuntimeError("r4 outer preservation inventory changed")
        super_audit = self.build_result["super"]
        if (
            super_audit.get("bytes_outside_system_a_extent_exact") is not True
            or super_audit.get("vendor_dlkm_extent_byte_preserved_from_r3") is not True
            or super_audit.get("metadata_geometry_exact") is not True
        ):
            raise RuntimeError("r4 super preservation/geometry evidence is incomplete")
        rollback = Path(str(self.cfg["rollback"]["path"]))
        rollback_actual = R3.record(rollback)
        if (
            rollback_actual["size"] != self.cfg["rollback"]["size"]
            or rollback_actual["sha256"] != self.cfg["rollback"]["sha256"]
        ):
            raise RuntimeError("rollback authority identity changed")
        return {
            "byte_preserved_images": preserved_images,
            "kernel": kernel_actual,
            "kernel_rebuilt": False,
            "vendor_dlkm_module_count": 22,
            "vendor_dlkm_rebuilt": False,
            "super_metadata_geometry": "EXACT_R3",
            "super_bytes_outside_system_a": "EXACT_R3",
            "outer_changed_payloads": outer["changed_payloads"],
            "outer_preserved_payload_count": 46,
            "rollback": rollback_actual,
            "subsystems": {
                "HDMI": "UNCHANGED_OPEN",
                "audio": "UNCHANGED_OPEN",
                "Wi-Fi": "UNCHANGED_ASSOCIATION_REQUIRES_PHYSICAL_VALIDATION",
                "Ethernet": "UNCHANGED_PRESERVATION_EXPECTED",
            },
            "result": "PASS",
        }

    def finish_r4(
        self,
        images: dict[str, Path],
        apex: dict[str, object],
        compatibility: dict[str, object],
        elf: dict[str, object],
        fixes: dict[str, object],
        system_delta: dict[str, object],
        preservation: dict[str, object],
    ) -> None:
        super().finish(images, apex, compatibility, elf)
        audit_path = self.audit / "offline-audit.json"
        result = json.loads(audit_path.read_text(encoding="utf-8"))
        result["gate2"] = "NOT_CLOSED_PENDING_R4_PHYSICAL_VALIDATION"
        result["physical_status"] = "NOT_YET_VALIDATED"
        result["bounded_fixes"] = fixes
        result["system_tree_delta"] = system_delta
        result["preservation"] = preservation
        result["limitations"] = [
            "No physical UBOX action occurred or is authorized by this audit.",
            "The EGL and Remote OK results are offline assertions, not r4 physical passes.",
            "HDMI is unchanged and remains physically open (approximately 1 s picture / 5 s black loop on r3).",
            "Audio is unchanged and its legacy HIDL null-pointer root cause remains unproven/open.",
            "Wi-Fi is unchanged; association/DHCP/L3/DNS still require physical validation.",
            "Ethernet is unchanged; preservation is expected but not newly physically tested on r4.",
            "Offline SELinux compilation does not prove enforcing runtime compatibility.",
            "Full VINTF remains incompatible only for the inherited CONFIG_NFS_FS exception.",
        ]
        audit_path.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        self.build_result["status"] = "OFFLINE_CHECKED"
        self.build_result["decision"] = result["decision"]
        self.build_result["gate2"] = result["gate2"]
        self.build_result["physical_status"] = result["physical_status"]
        self.build_result["offline_audit"] = R3.record(audit_path)
        (self.candidate / "build-result.json").write_text(
            json.dumps(self.build_result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        sums = []
        for path in sorted(self.candidate.iterdir()):
            if path.is_file() and path.name != "SHA256SUMS":
                sums.append(f"{R3.digest(path)}  {path.name}")
        (self.candidate / "SHA256SUMS").write_text(
            "\n".join(sums) + "\n", encoding="utf-8"
        )

    def execute(self) -> None:
        images = self.setup()
        try:
            self.mount_images(images)
            self.mount_r3_system()
            fixes = self.audit_two_fixes()
            system_delta = self.audit_system_tree_delta()
            preservation = self.audit_preservation(images)
            apex = self.audit_apex()
            compatibility = self.audit_vintf_linker_selinux()
            elf = self.audit_elf(images)
        finally:
            for point in reversed(self.mounted):
                self.run(["sudo", "umount", str(point)], allowed={0, 32})
        self.finish_r4(images, apex, compatibility, elf, fixes, system_delta, preservation)
        print("OFFLINE CHECKED / READY TO REQUEST PHYSICAL VALIDATION", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--aosp", type=Path, default=DEFAULT_AOSP)
    parser.add_argument(
        "--kernel-evidence", type=Path,
        help="Path-A evidence directory; default derives from build-result.json",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="resume an incomplete audit after a bounded harness correction",
    )
    R4Auditor(parser.parse_args()).execute()


if __name__ == "__main__":
    main()
