"""Tests for the independent read-only ext4 fixture parser."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from ubox10_rom.ext4_image import (  # noqa: E402
    Ext4Error,
    Ext4Image,
    read_manifest,
    validate_fixture_contract,
)


CONTRACT = json.loads(
    (REPO / "tests" / "fixtures" / "m6b_ext4" / "positive-contract.json").read_text(encoding="utf-8")
)
KNOWN_FIXTURE_SHA = "6CA8B1E2B64690B480ECF45DF6B0F2C1270658E39FBFB2265E872A38B82AB1EA"


def fixture_path() -> Path | None:
    candidates = sorted((REPO / "out" / "m6b-fixture").glob("*-m6b-positive-fixture/positive.ext4"))
    return candidates[-1] if candidates else None


class Ext4ImageTests(unittest.TestCase):
    def test_decodes_compact_ext4_acl(self) -> None:
        value = bytes.fromhex("01 00 00 00 01 00 06 00 04 00 04 00 20 00 00 00")
        self.assertEqual(
            [
                {"tag": 1, "permissions": 6, "id": None},
                {"tag": 4, "permissions": 4, "id": None},
                {"tag": 32, "permissions": 0, "id": None},
            ],
            Ext4Image._decode_acl(value),
        )

    def test_contract_comparator_reports_semantic_loss(self) -> None:
        manifest = {
            "filesystem": CONTRACT["filesystem"],
            "entries": [{"path": "/system/etc/selinux-test", "type": "regular", "xattrs": []}],
            "hardlink_groups": [],
        }
        errors = validate_fixture_contract(manifest, CONTRACT)
        self.assertTrue(any("security.selinux" in item for item in errors))
        self.assertTrue(any("hardlink group missing" in item for item in errors))

    @unittest.skipUnless(fixture_path(), "generated positive fixture is not present")
    def test_generated_fixture_matches_independent_contract(self) -> None:
        manifest = read_manifest(fixture_path())  # type: ignore[arg-type]
        self.assertEqual([], validate_fixture_contract(manifest, CONTRACT))
        self.assertEqual(KNOWN_FIXTURE_SHA, manifest["source"]["ext4_image_sha256"])

    @unittest.skipUnless(fixture_path(), "generated positive fixture is not present")
    def test_unknown_incompat_feature_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mutated = Path(directory) / "unknown-feature.ext4"
            shutil.copyfile(fixture_path(), mutated)  # type: ignore[arg-type]
            with mutated.open("r+b") as image:
                image.seek(1024 + 96)
                value = struct.unpack("<I", image.read(4))[0]
                image.seek(1024 + 96)
                image.write(struct.pack("<I", value | 0x80000000))
            with self.assertRaisesRegex(Ext4Error, "unsupported incompat"):
                read_manifest(mutated)

    @unittest.skipUnless(fixture_path(), "generated positive fixture is not present")
    def test_changed_selinux_xattr_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mutated = Path(directory) / "semantic-loss.ext4"
            shutil.copyfile(fixture_path(), mutated)  # type: ignore[arg-type]
            data = mutated.read_bytes()
            old = b"u:object_r:system_file:s0\x00"
            new = b"u:object_r:system_fail:s0\x00"
            self.assertEqual(1, data.count(old))
            mutated.write_bytes(data.replace(old, new))
            manifest = read_manifest(mutated)
            errors = validate_fixture_contract(manifest, CONTRACT)
            self.assertTrue(any("security.selinux" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
