#!/usr/bin/env python3
"""Convert the generated M8B keylayout against the locked Android 12 parser tables."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


KEY_LINE = re.compile(r"^\s*key\s+(\d+)\s+(\S+)(?:\s+(.*?))?\s*$")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def macro_labels(source: str, macro: str, end_marker: str) -> set[str]:
    block = source.split("#define " + macro, 1)[1].split(end_marker, 1)[0]
    function = "DEFINE_KEYCODE" if macro == "KEYCODES_SEQUENCE" else "DEFINE_FLAG"
    return set(re.findall(function + r"\(([^)]+)\)", block))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--input-event-labels", required=True, type=Path)
    parser.add_argument("--key-layout-map", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()

    document = json.loads(args.config.read_text(encoding="utf-8"))
    spec = document["android_keylayout_parser"]
    if digest(args.input_event_labels) != spec["input_event_labels_sha256"]:
        raise RuntimeError("InputEventLabels.cpp identity mismatch")
    if digest(args.key_layout_map) != spec["key_layout_map_sha256"]:
        raise RuntimeError("KeyLayoutMap.cpp identity mismatch")

    labels_source = args.input_event_labels.read_text(encoding="utf-8")
    parser_source = args.key_layout_map.read_text(encoding="utf-8")
    keycodes = macro_labels(labels_source, "KEYCODES_SEQUENCE", "// NOTE:")
    flags = macro_labels(labels_source, "FLAGS_SEQUENCE", "// --- InputEventLookup ---")
    for required in ("Expected key code label", "Expected key flag label", "getKeyFlagByLabel"):
        if required not in parser_source:
            raise RuntimeError("unexpected KeyLayoutMap parser implementation")

    keycode_conversions = spec["keycode_conversions"]
    flag_conversions = spec["flag_conversions"]
    linux_keycode_overrides = spec.get("linux_keycode_overrides", {})
    output = [
        f"# {document['id']} Android 12 parser-compatible device keylayout.",
        "# Derived from the generated r2/r3 sunxi-ir.kl; Linux rc-map is unchanged.",
    ]
    seen_codes: set[int] = set()
    input_keycodes: set[str] = set()
    input_flags: set[str] = set()
    final_keycodes: set[str] = set()
    final_flags: set[str] = set()
    conversions: list[dict[str, object]] = []
    applied_overrides: set[str] = set()
    entries = 0

    for line_number, line in enumerate(args.input.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = KEY_LINE.match(line)
        if match is None:
            raise RuntimeError(f"unsupported keylayout syntax at input line {line_number}")
        code = int(match.group(1))
        if code in seen_codes:
            raise RuntimeError(f"duplicate Linux keycode {code}")
        seen_codes.add(code)
        keycode = match.group(2)
        entry_flags = match.group(3).split() if match.group(3) else []
        if len(set(entry_flags)) != len(entry_flags):
            raise RuntimeError(f"duplicate flag at input line {line_number}")
        input_keycodes.add(keycode)
        input_flags.update(entry_flags)

        final_keycode = keycode
        if keycode not in keycodes:
            final_keycode = keycode_conversions.get(keycode)
            if final_keycode is None:
                raise RuntimeError("unsupported Android keycode label without conversion: " + keycode)
            conversions.append({"line": line_number, "linux_code": code, "kind": "keycode", "from": keycode, "to": final_keycode})
        if final_keycode not in keycodes:
            raise RuntimeError("converted Android keycode label is unsupported: " + final_keycode)
        override = linux_keycode_overrides.get(str(code))
        if override is not None:
            if final_keycode != override["from"]:
                raise RuntimeError(f"Linux keycode {code} override source mismatch")
            replacement = override["to"]
            if replacement == final_keycode or replacement not in keycodes:
                raise RuntimeError(f"Linux keycode {code} override target is invalid")
            conversions.append({
                "line": line_number, "linux_code": code, "kind": "linux_keycode_override",
                "from": final_keycode, "to": replacement,
            })
            final_keycode = replacement
            applied_overrides.add(str(code))

        converted_flags: list[str] = []
        for flag in entry_flags:
            final_flag = flag
            if flag not in flags:
                final_flag = flag_conversions.get(flag)
                if final_flag is None:
                    raise RuntimeError("unsupported Android key flag without conversion: " + flag)
                conversions.append({"line": line_number, "linux_code": code, "kind": "flag", "from": flag, "to": final_flag})
            if final_flag not in flags:
                raise RuntimeError("converted Android key flag is unsupported: " + final_flag)
            if final_flag in converted_flags:
                raise RuntimeError(f"conversion produced duplicate flag at input line {line_number}")
            converted_flags.append(final_flag)

        final_keycodes.add(final_keycode)
        final_flags.update(converted_flags)
        suffix = " " + " ".join(converted_flags) if converted_flags else ""
        output.append(f"key {code:3d}   {final_keycode:<20}{suffix}")
        entries += 1

    if applied_overrides != set(linux_keycode_overrides):
        missing = sorted(set(linux_keycode_overrides) - applied_overrides)
        raise RuntimeError("configured Linux keycode override was not applied: " + ", ".join(missing))

    args.output.write_text("\n".join(output) + "\n", encoding="utf-8", newline="\n")
    report = {
        "input": {"path": str(args.input), "sha256": digest(args.input)},
        "output": {"path": str(args.output), "sha256": digest(args.output)},
        "parser_sources": {
            "input_event_labels": {"path": str(args.input_event_labels), "sha256": digest(args.input_event_labels)},
            "key_layout_map": {"path": str(args.key_layout_map), "sha256": digest(args.key_layout_map)},
            "frameworks_native_commit": spec["frameworks_native_commit"],
            "frameworks_base_commit": spec["frameworks_base_commit"],
        },
        "validatekeymaps_prebuilt_available": False,
        "validation_method": "complete syntax and label/flag-table audit against exact InputEventLabels.cpp and KeyLayoutMap.cpp",
        "parser_supported_keycode_count": len(keycodes),
        "parser_supported_flags": sorted(flags),
        "input_keycodes": sorted(input_keycodes),
        "input_flags": sorted(input_flags),
        "unsupported_input_keycodes": sorted(input_keycodes - keycodes),
        "unsupported_input_flags": sorted(input_flags - flags),
        "final_keycodes": sorted(final_keycodes),
        "final_flags": sorted(final_flags),
        "conversions": conversions,
        "linux_keycode_overrides": linux_keycode_overrides,
        "applied_linux_keycode_overrides": sorted(applied_overrides, key=int),
        "parsed_entries": entries,
        "complete_parse_audit": True,
        "omitted_entries": [],
    }
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
