#!/usr/bin/env python3
"""Generate the M8B ff40 kernel rc-map and physical Android keylayout."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def parse_customer(path: Path) -> list[tuple[int, str, str]]:
    entries: list[tuple[int, str, str]] = []
    pattern = re.compile(r"\s*key\s+(\d+)\s+(\S+)\s+(\S+)")
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("#"):
            continue
        match = pattern.match(line)
        if match:
            entries.append((int(match.group(1)), match.group(2), match.group(3)))
    return entries


def validate(document: dict[str, object], customer: Path | None) -> list[dict[str, object]]:
    entries = document.get("entries")
    if not isinstance(entries, list) or len(entries) != 49:
        raise RuntimeError("ff40 source must contain exactly 49 active entries")
    typed = [item for item in entries if isinstance(item, dict)]
    if len(typed) != len(entries):
        raise RuntimeError("invalid ff40 entry")
    scans = [int(item["scan"]) for item in typed]
    if len(set(scans)) != 49:
        raise RuntimeError("ff40 scancodes must be unique")
    inert = [item for item in typed if item.get("include_in_rc_map", True) is False]
    if len(inert) != 1 or inert[0].get("android") != "MOUSE" or inert[0].get("result") != "INERT":
        raise RuntimeError("the only excluded mapping must be the intentional MOUSE drop")
    for item in typed:
        included = item.get("include_in_rc_map", True)
        if included and (not item.get("linux_symbol") or not isinstance(item.get("linux_code"), int)):
            raise RuntimeError("active native mapping lacks Linux keycode")
    if customer is not None:
        source = document["source"]
        assert isinstance(source, dict)
        if sha256(customer) != source["sha256"]:
            raise RuntimeError("customer_ir_ff40 source identity mismatch")
        observed = parse_customer(customer)
        expected = [(int(item["scan"]), str(item["android"]), str(item["flag"])) for item in typed]
        if observed != expected:
            raise RuntimeError("49-entry ff40 semantic mapping mismatch")
    return typed


def render_c(entries: list[dict[str, object]]) -> str:
    rows = []
    for item in entries:
        if item.get("include_in_rc_map", True) is False:
            continue
        scancode = 0xFF4000 | int(item["scan"])
        rows.append(f"\t{{ 0x{scancode:08x}, {item['linux_symbol']} }},")
    table = "\n".join(rows)
    return f'''/* Sunxi Remote Controller
 *
 * ff40 keymap generated from the exact Test8r2 customer_ir_ff40.kl.
 * Mouse mode is intentionally excluded from M8B rc-core-r1.
 */

#include <media/rc-map.h>
#include "sunxi-ir-rx.h"

/* It is used for sunxi legacy ir addr mapping in kernel mode. */
#ifdef CONFIG_SUNXI_KEYMAPPING_SUPPORT
static u32 match_addr[MAX_ADDR_NUM];
static u32 match_num;
#endif

static struct rc_map_table sunxi_nec_scan[] = {{
{table}
}};

#ifdef CONFIG_SUNXI_KEYMAPPING_SUPPORT
static u32 sunxi_key_mapping(u32 code)
{{
\tu32 i;

\tfor (i = 0; i < match_num; i++) {{
\t\tif (match_addr[i] == ((code >> 8) & 0xffffUL))
\t\t\treturn code;
\t}}
\treturn KEY_RESERVED;
}}
#endif

static struct rc_map_list sunxi_map = {{
\t.map = {{
\t\t.scan = sunxi_nec_scan,
\t\t.size = ARRAY_SIZE(sunxi_nec_scan),
#ifdef CONFIG_SUNXI_KEYMAPPING_SUPPORT
\t\t.mapping = (void *)sunxi_key_mapping,
#endif
\t\t.rc_proto = RC_PROTO_NEC,
\t\t.name = RC_MAP_SUNXI,
\t}}
}};

#ifdef CONFIG_SUNXI_KEYMAPPING_SUPPORT
static void init_addr(u32 *addr, u32 addr_num)
{{
\tu32 *temp_addr = match_addr;

\tif (addr_num > MAX_ADDR_NUM)
\t\taddr_num = MAX_ADDR_NUM;
\tmatch_num = addr_num;
\twhile (addr_num--)
\t\t*temp_addr++ = (*addr++) & 0xffffUL;
}}

int init_sunxi_ir_map_ext(void *addr, int num)
{{
\tinit_addr(addr, num);
\treturn rc_map_register(&sunxi_map);
}}
#else
int init_sunxi_ir_map(void)
{{
\treturn rc_map_register(&sunxi_map);
}}
#endif

void exit_sunxi_ir_map(void)
{{
\trc_map_unregister(&sunxi_map);
}}
'''


def render_kl(entries: list[dict[str, object]]) -> str:
    output = [
        "# M8B rc-core-r1 physical sunxi-ir keylayout.",
        "# Generated from exact Test8r2 ff40 semantics; mouse mode is intentionally inert.",
    ]
    seen: dict[int, tuple[str, str]] = {}
    for item in entries:
        if item.get("include_in_rc_map", True) is False:
            continue
        code = int(item["linux_code"])
        value = (str(item["android"]), str(item["flag"]))
        if code in seen:
            if seen[code] != value:
                raise RuntimeError(f"Linux keycode {code} has conflicting Android results")
            continue
        seen[code] = value
        output.append(f"key {code:3d}   {value[0]:<20} {value[1]}")
    return "\n".join(output) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", required=True, type=Path)
    parser.add_argument("--customer", type=Path)
    parser.add_argument("--c-output", required=True, type=Path)
    parser.add_argument("--kl-output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()

    document = json.loads(args.map.read_text(encoding="utf-8"))
    entries = validate(document, args.customer)
    args.c_output.parent.mkdir(parents=True, exist_ok=True)
    args.kl_output.parent.mkdir(parents=True, exist_ok=True)
    args.c_output.write_text(render_c(entries), encoding="utf-8", newline="\n")
    args.kl_output.write_text(render_kl(entries), encoding="utf-8", newline="\n")
    report = {
        "factory_id": document["factory_id"],
        "source": document["source"],
        "audited_entries": len(entries),
        "native_rc_entries": sum(item.get("include_in_rc_map", True) is not False for item in entries),
        "intentionally_inert": [item for item in entries if item.get("include_in_rc_map", True) is False],
        "kernel_source": {"path": str(args.c_output), "sha256": sha256(args.c_output)},
        "android_keylayout": {"path": str(args.kl_output), "sha256": sha256(args.kl_output)},
        "entries": entries,
    }
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
