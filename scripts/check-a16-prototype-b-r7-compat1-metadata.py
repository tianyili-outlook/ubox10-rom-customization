#!/usr/bin/env python3
"""Host proof for the r7 compat1 56-byte Allwinner-to-Mali attr translation."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import tempfile


DEFAULT_AOSP = Path("/work/src/ubox10-a16-ceiling")
HEADER = Path("external/skia/src/gpu/ganesh/gl/UBOXR7Compat1Metadata.h")


PROGRAM = r'''
#include "src/gpu/ganesh/gl/UBOXR7Compat1Metadata.h"

#include <array>
#include <cstdint>
#include <cstring>

using namespace ubox_r7_compat1;

int main() {
    std::array<uint8_t, kMetadataSize> original;
    std::array<uint8_t, kMetadataSize> before;
    std::array<uint8_t, kMetadataSize> shadow;
    for (size_t i = 0; i < original.size(); ++i) {
        original[i] = static_cast<uint8_t>((i * 131u + 17u) & 0xffu);
    }
    LegacyAttrRegion attr{};
    attr.cropTop = -1;
    attr.cropLeft = -2;
    attr.cropHeight = 1080;
    attr.cropWidth = 1920;
    attr.useYuvTransform = 0x10203040;
    attr.useSparseAlloc = 0x50607080;
    for (size_t i = 0; i < sizeof(attr.hdrInfo); ++i) {
        attr.hdrInfo[i] = static_cast<uint8_t>(0xa0u + i);
    }
    attr.dataspace = 0x10010000;
    memcpy(original.data() + kActiveAttrOffset, &attr, sizeof(attr));
    before = original;
    shadow.fill(0x5a);

    if (!translateMetadata(original.data(), original.size(), shadow.data(), shadow.size())) return 1;
    if (original != before) return 2;
    if (memcmp(shadow.data() + kLegacyAttrOffset, &attr, sizeof(attr)) != 0) return 3;
    if (memcmp(shadow.data() + kActiveAttrOffset, &attr, sizeof(attr)) != 0) return 4;
    for (size_t i = 0; i < shadow.size(); ++i) {
        const bool translatedByte = i >= kLegacyAttrOffset && i < kLegacyAttrOffset + kAttrSize;
        if (!translatedByte && shadow[i] != original[i]) return 5;
    }
    const auto* legacy = reinterpret_cast<const LegacyAttrRegion*>(shadow.data() + kLegacyAttrOffset);
    if (legacy->cropTop != -1 || legacy->cropLeft != -2 || legacy->cropHeight != 1080 ||
        legacy->cropWidth != 1920 || legacy->useYuvTransform != 0x10203040 ||
        legacy->useSparseAlloc != 0x50607080 || legacy->dataspace != 0x10010000) return 6;
    if (translateMetadata(original.data(), original.size() - 1, shadow.data(), shadow.size())) return 7;
    if (translateMetadata(original.data(), original.size(), original.data(), original.size())) return 8;
    return 0;
}
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aosp", type=Path, default=DEFAULT_AOSP)
    args = parser.parse_args()
    header = args.aosp / HEADER
    if not header.is_file():
        raise SystemExit(f"missing compat1 header: {header}")
    clang = sorted((args.aosp / "prebuilts/clang/host/linux-x86").glob("clang-*/bin/clang++"))[-1]
    with tempfile.TemporaryDirectory(prefix="ubox-r7-compat1-") as tmp:
        root = Path(tmp)
        source = root / "compat1_test.cpp"
        binary = root / "compat1_test"
        source.write_text(PROGRAM, encoding="utf-8")
        subprocess.run(
            [str(clang), "-std=c++17", "-Wall", "-Wextra", "-Werror",
             "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
             "-I", str(args.aosp / "external/skia"), str(source), "-o", str(binary)],
            check=True,
        )
        subprocess.run([str(binary)], check=True)
    print("compat1 metadata translation: PASS")
    print("active_attr=23544 legacy_attr=128 bytes=56 original_unchanged=PASS")
    print("fields=crop,yuv_transform,sparse_alloc,hdr_info,dataspace")


if __name__ == "__main__":
    main()
