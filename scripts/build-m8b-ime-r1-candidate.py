#!/usr/bin/env python3
"""Build the LeanbackIME-only M8B candidate on accepted m8b-audio-r2."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


REPO = Path(__file__).resolve().parents[1]
BASE_BUILDER = REPO / "scripts" / "build-m8b-audio-r2-candidate.py"
DEFAULT_CONFIG = REPO / "configs" / "candidates" / "m8b-ime-r1.json"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load module: " + str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


audio2 = load_module(BASE_BUILDER, "m8b_audio_r2_for_ime")
base = audio2.base
TOOLS = base.TOOLS


class BuildM8BImeR1(audio2.BuildM8BAudioR2):
    def setup(self) -> None:
        # This milestone consumes the already accepted image and does not
        # rematerialize its system/audio/input changes.
        base.BuildR9.setup(self)
        ime = self.config["ime"]
        assert isinstance(ime, dict)
        patch = REPO / str(ime["integration_patch_relative"])
        if not patch.is_file() or base.digest(patch) != ime["integration_patch_sha256"]:
            raise RuntimeError("IME integration patch identity mismatch")

        checks = {
            str(ime["product_config_path"]): ime["product_config_sha256"],
            str(ime["product_image_path"]): ime["product_image_sha256"],
            str(ime["apk_path"]): ime["apk_sha256"],
        }
        hashes = self.stage / "aosp-ime-sha256.txt"
        self.run(["wsl.exe", "-d", "Ubuntu-24.04", "--", "sha256sum", *checks], output=hashes)
        observed = {line.split("  ", 1)[1]: line.split()[0].upper() for line in hashes.read_text(encoding="utf-8").splitlines()}
        for path, expected in checks.items():
            if observed.get(path) != expected:
                raise RuntimeError("AOSP IME artifact identity mismatch: " + path)

        source_commit = subprocess.check_output([
            "wsl.exe", "-d", "Ubuntu-24.04", "--", "git", "-C", str(ime["source_path"]), "rev-parse", "HEAD"
        ], text=True, encoding="utf-8").strip()
        if source_commit != ime["source_commit"]:
            raise RuntimeError("LeanbackIME source commit mismatch")

    def prepare_product(self, source_product: Path) -> Path:
        ime = self.config["ime"]
        assert isinstance(ime, dict)
        sparse = self.stage / "aosp-product.img"
        self.run([
            "wsl.exe", "-d", "Ubuntu-24.04", "--", "cp", str(ime["product_image_path"]), self.wsl_path(sparse)
        ])
        if sparse.stat().st_size != ime["product_image_size"] or base.digest(sparse) != ime["product_image_sha256"]:
            raise RuntimeError("copied AOSP product image identity mismatch")
        product = self.stage / "product_a.img"
        self.run([str(TOOLS / "simg2img.exe"), str(sparse), str(product)])
        base_mount = self.stage / "base-product-mount"
        candidate_mount = self.stage / "candidate-product-mount"
        base_mount.mkdir()
        candidate_mount.mkdir()
        self.run([
            "wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--", "bash",
            self.wsl_path(REPO / "scripts" / "prepare-m8b-ime-r1-product.sh"),
            self.wsl_path(source_product), self.wsl_path(product),
            self.wsl_path(base_mount), self.wsl_path(candidate_mount),
        ])
        base_mount.rmdir()
        candidate_mount.rmdir()

        avb = self.config["product_avb"]
        assert isinstance(avb, dict)
        self.run([
            sys.executable, str(TOOLS / "avbtool.py"), "add_hashtree_footer", "--image", str(product),
            "--partition_name", "product", "--partition_size", str(avb["partition_size"]),
            "--hash_algorithm", "sha256", "--salt", str(avb["salt"]), "--do_not_generate_fec",
            "--prop", "com.ubox10.candidate.id:" + self.candidate_id,
            "--prop", "com.ubox10.avb.fec:none", "--key", str(REPO / str(avb["key_relative"])),
            "--algorithm", "SHA256_RSA2048",
        ])
        if product.stat().st_size != avb["partition_size"]:
            raise RuntimeError("signed product_a size mismatch")
        self.run([sys.executable, str(TOOLS / "avbtool.py"), "info_image", "--image", str(product)], output=self.stage / "product-avb-info.txt")
        return product

    def make_super_with_product(self, product: Path) -> Path:
        layout = self.config["super_layout"]
        specs = self.config["logical_partitions"]
        assert isinstance(layout, dict) and isinstance(specs, dict)
        logical = self.stage / "r8-logical"
        output = self.stage / "super.img"
        args = [
            str(TOOLS / "lpmake.exe"), "--metadata-size", str(layout["metadata_size"]),
            "--metadata-slots", str(layout["slots"]), "--super-name", "super",
            "--device-size", str(layout["device_size"]), "--alignment", str(layout["alignment"]),
            "--virtual-ab", "--group", "sb_a:" + str(layout["group_size"]),
            "--group", "sb_b:" + str(layout["group_size"]),
        ]
        for name, spec in specs.items():
            assert isinstance(spec, dict)
            image = product if name == "product_a" else logical / (name + ".img")
            args += ["--partition", name + ":readonly:" + str(spec["size"]) + ":sb_a", "--image", name + "=" + str(image)]
            args += ["--partition", name[:-1] + "b:readonly:0:sb_b"]
        args += ["--sparse", "--output", str(output)]
        self.run(args)
        return output

    def validate_product_diff(self, before_image: Path, after_image: Path) -> dict[str, object]:
        before = self._manifest_map(self.inventory_system(before_image, "audio-r2-product"))
        after = self._manifest_map(self.inventory_system(after_image, "ime-product"))
        prefix = "/app/LeanbackIME"
        allowed_exact = {"/app", "/etc/NOTICE.xml.gz"}
        changed = [path for path in sorted(set(before) | set(after)) if before.get(path) != after.get(path)]
        unexpected = [path for path in changed if path not in allowed_exact and path != prefix and not path.startswith(prefix + "/")]
        if unexpected:
            raise RuntimeError("unexpected product filesystem differences: " + ", ".join(unexpected[:16]))
        if before.get("/etc/build.prop") != after.get("/etc/build.prop"):
            raise RuntimeError("accepted product build.prop was not preserved exactly")
        apk_path = prefix + "/LeanbackIME.apk"
        ime = self.config["ime"]
        assert isinstance(ime, dict)
        if after.get(apk_path, {}).get("sha256") != ime["apk_sha256"]:
            raise RuntimeError("final LeanbackIME APK identity mismatch")
        app_paths = [path for path in after if path == prefix or path.startswith(prefix + "/")]
        if not app_paths or any(path in before for path in app_paths):
            raise RuntimeError("LeanbackIME product tree was not newly added")
        report = {
            "base": "m8b-audio-r2 (DEVICE ACCEPTED / AUDIO PASS)",
            "changed_paths": changed,
            "unexpected_paths": unexpected,
            "accepted_product_build_prop_preserved": True,
            "leanback_apk": after[apk_path],
            "normal_product_module_integration": True,
            "notice_update_attributable_to_added_Apache_2_0_module": "/etc/NOTICE.xml.gz" in changed,
        }
        (self.stage / "ime-product-filesystem-validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return report

    def validate_super_with_product(self, candidate_super: Path, source_product: Path) -> Path:
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
            self.logical_after[name] = base.record(path)
            if name != "product_a" and self.logical_after[name]["sha256"] != self.logical_before[name]["sha256"]:
                raise RuntimeError("protected non-product logical partition changed: " + name)
        self.validate_product_diff(source_product, logical / "product_a.img")
        return logical / "product_a.img"

    def verify_product_avb(self, product: Path) -> None:
        avb = self.config["product_avb"]
        assert isinstance(avb, dict)
        view = self.stage / "product-avb-validation"
        view.mkdir()
        conventional = view / "product.img"
        os.link(product, conventional)
        self.run([
            "wsl.exe", "-d", "Ubuntu-24.04", "--", "python3", self.wsl_path(TOOLS / "avbtool.py"),
            "verify_image", "--image", self.wsl_path(conventional),
            "--key", self.wsl_path(REPO / str(avb["key_relative"])),
        ])

    def pack_product_candidate(self, super_image: Path) -> Path:
        firmware = self.stage / ("x12-" + self.candidate_id + ".img")
        audit = self.stage / "outer-payload-audit.json"
        self.run([
            sys.executable, str(TOOLS / "pack_image_preserving.py"), "--source", str(self.base),
            "--output", str(firmware), "--replace", "super.fex=" + str(super_image), "--audit", str(audit),
        ])
        self.run([sys.executable, str(TOOLS / "sunxi_image_tool.py"), "verify", str(firmware)])
        actions = {item["filename"]: item["action"] for item in json.loads(audit.read_text(encoding="utf-8"))["payloads"]}
        container = self.config["container"]
        assert isinstance(container, dict)
        if len(actions) != container["total_entries"] or sum(value == "preserved" for value in actions.values()) != container["preserved_entries"]:
            raise RuntimeError("outer preservation count mismatch")
        for name in container["replacements"]:
            if actions.get(name) != "replacement":
                raise RuntimeError("missing outer replacement: " + str(name))
        for name in container["companions"]:
            if actions.get(name) != "companion":
                raise RuntimeError("missing outer companion: " + str(name))
            self.run([sys.executable, str(TOOLS / "sunxi_image_tool.py"), "extract", "-o", str(self.stage), "-f", str(name), str(firmware)])
        return firmware

    def finish_ime(self, firmware: Path, super_image: Path, old_vbmeta: Path, report: dict[str, object]) -> None:
        if base.record(self.base) != self.before:
            raise RuntimeError("protected m8b-audio-r2 base changed")
        logical_before = {name: {"partition": name, "container": str(self.base) + "#super.fex", **{k: value[k] for k in ("size", "sha256")}} for name, value in self.logical_before.items()}
        logical_after = {name: {"partition": name, "container": str(super_image), **{k: value[k] for k in ("size", "sha256")}} for name, value in self.logical_after.items()}
        result = {
            "id": self.candidate_id,
            "status": "OFFLINE CHECKED / DEVICE PERSISTENCE PENDING",
            "firmware": base.record(firmware), "base_candidate": self.before,
            "super": base.record(super_image), "vbmeta_system_preserved": base.record(old_vbmeta),
            "logical_before": logical_before, "logical_after": logical_after,
            "product_a": logical_after["product_a"], "ime": self.config["ime"],
            "ime_product_validation": report,
            "payload_delta": ["product_a", "super.fex", "Vsuper.fex"],
            "protected_partitions_unchanged": ["system_a", "vendor_a", "vendor_dlkm_a"],
            "boot_and_outer_payloads_preserved": True,
            "physical_device_actions_performed": False,
            "first_boot_enablement": "Offline source inspection supports default enable/select through android:isDefault=true; fresh-data/reboot persistence awaits physical validation.",
        }
        (self.stage / "build-result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        (self.stage / "input-provenance-after.json").write_text(json.dumps({"base_candidate": base.record(self.base)}, indent=2) + "\n", encoding="utf-8")

        for directory in ("r8-logical", "validation-logical", "r8-outer"):
            shutil.rmtree(self.stage / directory)
        shutil.rmtree(self.stage / "product-avb-validation")
        for name in ("r8-super.raw.img", "validation-super.raw.img", "aosp-product.img", "product_a.img"):
            (self.stage / name).unlink()
        for name in ("build-result.json", "outer-payload-audit.json", "input-provenance-before.json", "input-provenance-after.json"):
            path = self.stage / name
            path.write_text(json.dumps(base.rewrite_paths(json.loads(path.read_text(encoding="utf-8")), self.stage, self.final), indent=2) + "\n", encoding="utf-8")
        sums = [base.digest(path) + "  " + path.relative_to(self.stage).as_posix() for path in sorted(self.stage.rglob("*")) if path.is_file() and path.name != "SHA256SUMS"]
        (self.stage / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
        os.replace(self.stage, self.final)

    def build(self) -> None:
        started = time.time()
        try:
            self.setup()
            _source_super, _raw_super, source_system, old_vbmeta = base.BuildR9.extract_r8(self)
            source_product = self.stage / "r8-logical" / "product_a.img"
            product = self.prepare_product(source_product)
            super_image = self.make_super_with_product(product)
            validated_product = self.validate_super_with_product(super_image, source_product)
            self.verify_product_avb(validated_product)
            base.BuildR9.verify_avb(self, source_system, old_vbmeta)
            firmware = self.pack_product_candidate(super_image)
            report = json.loads((self.stage / "ime-product-filesystem-validation.json").read_text(encoding="utf-8"))
            self.finish_ime(firmware, super_image, old_vbmeta, report)
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
    BuildM8BImeR1(audio2.audio1.rc.merged_config(args.config), args.keep_failed).build()


if __name__ == "__main__":
    main()
