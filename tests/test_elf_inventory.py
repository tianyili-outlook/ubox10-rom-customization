from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zipfile


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "inventory-elf.py"
FIXTURE = REPO / "tests" / "fixtures" / "m8_elf" / "fixture-spec.json"

spec = importlib.util.spec_from_file_location("inventory_elf", SCRIPT)
assert spec is not None and spec.loader is not None
inventory = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = inventory
spec.loader.exec_module(inventory)


def build_elf(fixture: dict[str, object]) -> bytes:
    bits = int(fixture["class"])
    machine = int(fixture["machine"])
    interpreter = str(fixture["interpreter"]).encode("ascii") + b"\0"
    soname = str(fixture["soname"])
    needed = [str(item) for item in fixture["needed"]]

    strings = bytearray(b"\0")
    offsets: dict[str, int] = {}
    for value in needed + [soname]:
        if value not in offsets:
            offsets[value] = len(strings)
            strings.extend(value.encode("ascii") + b"\0")

    if bits == 32:
        header_size = 52
        ph_entry_size = 32
        base = 0x1000
        interp_offset = 0x100
        dynamic_offset = 0x180
        strings_offset = 0x280
        dynamic_entries = (
            [(5, base + strings_offset), (10, len(strings))]
            + [(1, offsets[value]) for value in needed]
            + [(14, offsets[soname]), (0, 0)]
        )
        dynamic = b"".join(struct.pack("<iI", tag, value) for tag, value in dynamic_entries)
        image = bytearray(0x400)
        ident = b"\x7fELF" + bytes((1, 1, 1, 0)) + b"\0" * 8
        struct.pack_into(
            "<16sHHIIIIIHHHHHH",
            image,
            0,
            ident,
            3,
            machine,
            1,
            0,
            header_size,
            0,
            0,
            header_size,
            ph_entry_size,
            3,
            0,
            0,
            0,
        )
        program_headers = (
            (1, 0, base, 0, len(image), len(image), 5, 0x1000),
            (3, interp_offset, base + interp_offset, 0, len(interpreter), len(interpreter), 4, 1),
            (2, dynamic_offset, base + dynamic_offset, 0, len(dynamic), len(dynamic), 4, 4),
        )
        for index, values in enumerate(program_headers):
            struct.pack_into("<IIIIIIII", image, header_size + index * ph_entry_size, *values)
    else:
        header_size = 64
        ph_entry_size = 56
        base = 0x400000
        interp_offset = 0x180
        dynamic_offset = 0x200
        strings_offset = 0x300
        dynamic_entries = (
            [(5, base + strings_offset), (10, len(strings))]
            + [(1, offsets[value]) for value in needed]
            + [(14, offsets[soname]), (0, 0)]
        )
        dynamic = b"".join(struct.pack("<qQ", tag, value) for tag, value in dynamic_entries)
        image = bytearray(0x500)
        ident = b"\x7fELF" + bytes((2, 1, 1, 0)) + b"\0" * 8
        struct.pack_into(
            "<16sHHIQQQIHHHHHH",
            image,
            0,
            ident,
            3,
            machine,
            1,
            0,
            header_size,
            0,
            0,
            header_size,
            ph_entry_size,
            3,
            0,
            0,
            0,
        )
        program_headers = (
            (1, 5, 0, base, 0, len(image), len(image), 0x1000),
            (3, 4, interp_offset, base + interp_offset, 0, len(interpreter), len(interpreter), 1),
            (2, 4, dynamic_offset, base + dynamic_offset, 0, len(dynamic), len(dynamic), 8),
        )
        for index, values in enumerate(program_headers):
            struct.pack_into("<IIQQQQQQ", image, header_size + index * ph_entry_size, *values)

    image[interp_offset : interp_offset + len(interpreter)] = interpreter
    image[dynamic_offset : dynamic_offset + len(dynamic)] = dynamic
    image[strings_offset : strings_offset + len(strings)] = strings
    return bytes(image)


class ElfInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_parses_arm32_dynamic_metadata(self) -> None:
        record = inventory.parse_elf(
            build_elf(self.fixture["elf32"]),
            partition="vendor",
            path="/vendor/lib/libfixture32.so",
        )
        self.assertEqual("ELF32", record.elf_class)
        self.assertEqual("ARM", record.machine)
        self.assertEqual("/system/bin/linker", record.interpreter)
        self.assertEqual("libfixture32.so", record.soname)
        self.assertEqual(("libc.so", "libdl.so"), record.needed)

    def test_parses_aarch64_dynamic_metadata(self) -> None:
        record = inventory.parse_elf(
            build_elf(self.fixture["elf64"]),
            partition="system",
            path="/system/lib64/libfixture64.so",
        )
        self.assertEqual("ELF64", record.elf_class)
        self.assertEqual("AArch64", record.machine)
        self.assertEqual("/system/bin/linker64", record.interpreter)
        self.assertEqual("libfixture64.so", record.soname)
        self.assertEqual(("libc.so",), record.needed)

    def test_scans_elf_members_inside_apk(self) -> None:
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as output:
            output.writestr("classes.dex", b"dex\n")
            output.writestr("lib/armeabi-v7a/libfixture32.so", build_elf(self.fixture["elf32"]))
            output.writestr("lib/arm64-v8a/libfixture64.so", build_elf(self.fixture["elf64"]))

        records = inventory.scan_archive(
            archive.getvalue(),
            partition="system",
            path="/system/app/Fixture/Fixture.apk",
        )
        self.assertEqual(["ELF32", "ELF64"], sorted(record.elf_class for record in records))
        self.assertTrue(all("!/" in record.path for record in records))

    def test_csv_has_no_per_file_hash_column(self) -> None:
        records = [
            inventory.parse_elf(
                build_elf(self.fixture["elf32"]),
                partition="vendor",
                path="/vendor/lib/libfixture32.so",
            )
        ]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "inventory.csv"
            inventory.write_csv(records, output)
            header = output.read_text(encoding="utf-8").splitlines()[0]
        self.assertEqual(
            "partition,path,class,machine,interpreter,soname,needed",
            header,
        )
        self.assertNotIn("sha", header.lower())

    def test_summary_reports_class_specific_unresolved_dependencies(self) -> None:
        consumer = inventory.parse_elf(
            build_elf(self.fixture["elf64"]),
            partition="system",
            path="/system/bin/fixture64",
        )
        text = inventory.render_summary([consumer])
        self.assertIn("ELF64", text)
        self.assertIn("libc.so", text)
        self.assertNotIn("SHA-256", text)

    def test_rejects_truncated_elf(self) -> None:
        with self.assertRaises(inventory.InventoryError):
            inventory.parse_elf(
                b"\x7fELF\x01\x01\x01",
                partition="vendor",
                path="/vendor/bin/broken",
            )


if __name__ == "__main__":
    unittest.main()
