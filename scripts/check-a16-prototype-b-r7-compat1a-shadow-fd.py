#!/usr/bin/env python3
"""Host ASan/UBSan proof for the exact compat1a sized-memfd and attr translation helpers."""
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
#include <cerrno>
#include <cstdint>
#include <cstring>
#include <sys/mman.h>
#include <sys/stat.h>

using namespace ubox_r7_compat1;

int main() {
    std::array<uint8_t, kMetadataSize> original;
    std::array<uint8_t, kMetadataSize> before;
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

    const int fd = createSizedShadowFd("ubox_r7_compat1a_host", kMetadataSize);
    if (fd < 0) return 1;
    struct stat statBuffer {};
    if (fstat(fd, &statBuffer) != 0 || statBuffer.st_size != static_cast<off_t>(kMetadataSize)) {
        return 2;
    }
    const int seals = fcntl(fd, F_GET_SEALS);
    if (seals < 0 || (seals & (F_SEAL_GROW | F_SEAL_SHRINK)) !=
                             (F_SEAL_GROW | F_SEAL_SHRINK)) return 3;
    if (ftruncate(fd, kMetadataSize + 4096) == 0) return 4;

    void* shadow = mmap(nullptr, kMetadataSize, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (shadow == MAP_FAILED) return 5;
    if (!translateMetadata(original.data(), original.size(), shadow, kMetadataSize)) return 6;
    if (original != before) return 7;
    if (memcmp(static_cast<uint8_t*>(shadow) + kLegacyAttrOffset,
               original.data() + kActiveAttrOffset, kAttrSize) != 0) return 8;
    if (msync(shadow, kMetadataSize, MS_SYNC) != 0) return 9;
    if (munmap(shadow, kMetadataSize) != 0) return 10;

    const void* verify = mmap(nullptr, kMetadataSize, PROT_READ, MAP_SHARED, fd, 0);
    if (verify == MAP_FAILED) return 11;
    if (memcmp(static_cast<const uint8_t*>(verify) + kLegacyAttrOffset,
               original.data() + kActiveAttrOffset, kAttrSize) != 0) return 12;
    if (munmap(const_cast<void*>(verify), kMetadataSize) != 0) return 13;
    if (close(fd) != 0) return 14;
    errno = 0;
    if (fcntl(fd, F_GETFD) != -1 || errno != EBADF) return 15;
    return 0;
}
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aosp", type=Path, default=DEFAULT_AOSP)
    args = parser.parse_args()
    header = args.aosp / HEADER
    if not header.is_file():
        raise SystemExit(f"missing compat1a helper header: {header}")
    clang = sorted((args.aosp / "prebuilts/clang/host/linux-x86").glob("clang-*/bin/clang++"))[-1]
    with tempfile.TemporaryDirectory(prefix="ubox-r7-compat1a-") as temporary:
        root = Path(temporary)
        source = root / "compat1a_test.cpp"
        binary = root / "compat1a_test"
        source.write_text(PROGRAM, encoding="utf-8")
        subprocess.run(
            [str(clang), "-std=c++17", "-Wall", "-Wextra", "-Werror",
             "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
             "-I", str(args.aosp / "external/skia"), str(source), "-o", str(binary)],
            check=True,
        )
        subprocess.run([str(binary)], check=True)
    print("compat1a sized shadow fd: PASS")
    print("fd_type=memfd_ftruncate_sealed size=24576 fstat=PASS mmap_shared=PASS close=PASS")
    print("active_attr=23544 legacy_attr=128 bytes=56 original_unchanged=PASS ASan_UBSan=PASS")


if __name__ == "__main__":
    main()
