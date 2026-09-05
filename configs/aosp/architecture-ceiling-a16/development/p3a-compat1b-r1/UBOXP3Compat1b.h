// UBOX10: exact physically captured SDR 4K replacement-buffer contract only.
// This recognizes the vendor's private big reservation, not general AFBC support.
#ifndef UBOX_P3_COMPAT1B_H
#define UBOX_P3_COMPAT1B_H
#include "UBOXR7Compat1Metadata.h"

namespace ubox_p3_compat1b {
constexpr int64_t kImageFdSize = 19492864;
inline uint64_t slot64(const int* s, size_t i) {
    return uint64_t(uint32_t(s[i])) | (uint64_t(uint32_t(s[i + 1])) << 32);
}
template <typename Desc>
inline bool contract(const Desc& d, bool protectedContent, const int* s) {
    return !protectedContent && d.width == 3840 && d.height == 2160 &&
        d.layers == 1 && d.format == 0x32315659u && d.stride == 3840 &&
        d.usage == UINT64_C(0x40402d00) &&
        uint32_t(s[0]) == 0x03141592u && s[1] == 4 &&
        s[2] == 3840 && s[3] == 2160 && uint32_t(s[4]) == 0x32315659u &&
        slot64(s, 5) == UINT64_C(0x40400900) &&
        slot64(s, 7) == UINT64_C(0x40400900) && slot64(s, 9) == 0 &&
        s[11] == 3840 && s[12] == 0 && s[13] == 0 && s[14] == 0 &&
        slot64(s, 15) == UINT64_C(0x32315659) &&
        s[17] == 0 && s[18] == 3840 && s[19] == 3840 && s[20] == 2160 &&
        s[21] == 8294400 && s[22] == 1920 && s[23] == 1920 && s[24] == 1080 &&
        s[25] == 10368000 && s[26] == 1920 && s[27] == 1920 && s[28] == 1080 &&
        s[29] == 19489120 && s[30] == 1 &&
        s[43] == int(ubox_r7_compat1::kMetadataSize) && uint32_t(s[44]) == 0x80000010u &&
        s[45] == 3;
}
inline bool metadata(uint32_t sunxiFlag, const ubox_r7_compat1::LegacyAttrRegion& a,
                     const int32_t (&crop)[4]) {
    // Dynamic consumer-time gate: unknown/HDR/control states remain on the original path.
    for (uint8_t byte : a.hdrInfo) {
        if (byte != 0xff) return false;
    }
    return sunxiFlag == 0x10 && a.cropTop == -1 && a.cropLeft == -1 &&
        a.cropHeight == -1 && a.cropWidth == -1 && a.useYuvTransform == -1 &&
        a.useSparseAlloc == -1 && uint32_t(a.dataspace) == 0x10010000u &&
        crop[0] >= 0 && crop[1] >= 0 && crop[2] >= 0 && crop[3] >= 0 &&
        (crop[0] != 0 || crop[1] != 0 || crop[2] != 2160 || crop[3] != 3840);
}
}  // namespace ubox_p3_compat1b
#endif
