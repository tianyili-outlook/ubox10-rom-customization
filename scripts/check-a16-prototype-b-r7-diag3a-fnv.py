#!/usr/bin/env python3
"""Prove the diag3a FNV-1a helper is exact and UBSan-transparent."""
from __future__ import annotations

import argparse
from pathlib import Path
import resource
import subprocess
import sys
import tempfile


DEFAULT_AOSP = Path("/work/src/ubox10-a16-ceiling")
HEADER = Path("frameworks/av/media/libstagefright/UBOXR7Diag3PrivateHandle.h")


def extract_function(text: str) -> str:
    marker = "static inline uint64_t ubox_r7_diag3_fnv1a64"
    start = text.index(marker)
    opening = text.index("{", start)
    depth = 0
    for offset in range(opening, len(text)):
        if text[offset] == "{":
            depth += 1
        elif text[offset] == "}":
            depth -= 1
            if depth == 0:
                return text[start : offset + 1]
    raise RuntimeError("unterminated FNV helper")


def disable_core() -> None:
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def compile_source(clang: Path, source: str, output: Path) -> None:
    completed = subprocess.run(
        [
            str(clang), "-x", "c++", "-", "-std=gnu++17", "-O2", "-o", str(output),
            "-fsanitize=signed-integer-overflow,unsigned-integer-overflow",
            "-fsanitize-minimal-runtime", "-fno-sanitize-recover=integer,undefined",
        ],
        input=source,
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"host compile failed:\n{completed.stderr}")


def corrected_program(helper: str) -> str:
    return f"""
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <vector>
{helper}

static bool check(const char *name, const std::vector<uint8_t>& bytes, uint64_t expected) {{
    const uint64_t actual = ubox_r7_diag3_fnv1a64(bytes.data(), bytes.size());
    printf("%s size=%zu fnv=0x%016llx expected=0x%016llx\\n", name, bytes.size(),
           (unsigned long long)actual, (unsigned long long)expected);
    return actual == expected;
}}

int main() {{
    bool ok = true;
    ok &= check("empty", {{}}, UINT64_C(0xcbf29ce484222325));
    ok &= check("a", {{'a'}}, UINT64_C(0xaf63dc4c8601ec8c));
    ok &= check("foobar", {{'f','o','o','b','a','r'}}, UINT64_C(0x85944171f73967e8));
    std::vector<uint8_t> ascending(256);
    for (size_t i = 0; i < ascending.size(); ++i) ascending[i] = (uint8_t)i;
    ok &= check("bytes_0_255", ascending, UINT64_C(0x4242dc5249c33625));
    std::vector<uint8_t> ff(24576, 0xff);
    ok &= check("ff_24576", ff, UINT64_C(0x720923c139c50325));
    std::vector<uint8_t> pattern(24576);
    for (size_t i = 0; i < pattern.size(); ++i) pattern[i] = (uint8_t)(i * 37 + 11);
    ok &= check("pattern_24576", pattern, UINT64_C(0xb988de2317596325));
    return ok ? 0 : 1;
}}
"""


LEGACY_PROGRAM = r"""
#include <stdint.h>
int main(int argc, char **argv) {
    const uint8_t byte = argc > 1 ? (uint8_t)argv[1][0] : (uint8_t)'a';
    uint64_t hash = UINT64_C(14695981039346656037);
    hash ^= byte;
    hash *= UINT64_C(1099511628211);
    return hash == 0;
}
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aosp", type=Path, default=DEFAULT_AOSP)
    args = parser.parse_args()
    header = args.aosp / HEADER
    clang = args.aosp / "prebuilts/clang/host/linux-x86/clang-r547379/bin/clang++"
    if not header.is_file() or not clang.is_file():
        raise RuntimeError("exact diag3a AOSP header or Android Clang is unavailable")

    helper = extract_function(header.read_text(encoding="utf-8"))
    if "__builtin_mul_overflow" not in helper or "hash *= " in helper:
        raise RuntimeError("diag3a helper does not express intentional wrapping via builtin")
    if "no_sanitize" in helper:
        raise RuntimeError("diag3a unexpectedly disables sanitizer coverage")

    with tempfile.TemporaryDirectory(prefix="ubox-r7-diag3a-fnv-") as temporary:
        root = Path(temporary)
        corrected = root / "corrected"
        legacy = root / "legacy"
        compile_source(clang, corrected_program(helper), corrected)
        compile_source(clang, LEGACY_PROGRAM, legacy)

        good = subprocess.run(
            [str(corrected)], text=True, capture_output=True, preexec_fn=disable_core
        )
        if good.returncode != 0 or "ubsan:" in (good.stdout + good.stderr):
            raise RuntimeError(
                f"corrected FNV failed equivalent UBSan build (rc={good.returncode}):\n"
                f"{good.stdout}{good.stderr}"
            )

        bad = subprocess.run(
            [str(legacy), "a"], text=True, capture_output=True, preexec_fn=disable_core
        )
        if bad.returncode == 0 or "ubsan: mul-overflow" not in (bad.stdout + bad.stderr):
            raise RuntimeError("equivalent UBSan control did not reproduce legacy mul-overflow")

    print(good.stdout, end="")
    print("PASS_DIAG3A_FNV64_EQUIVALENCE_AND_UBSAN_TRANSPARENCY")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
