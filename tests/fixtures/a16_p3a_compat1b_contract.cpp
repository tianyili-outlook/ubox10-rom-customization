#include "UBOXP3Compat1b.h"
#include <array>
#include <cassert>
#include <sys/mman.h>
#include <sys/stat.h>

struct Desc { uint32_t width, height, layers, format, stride; uint64_t usage; };
int main() {
    Desc d{3840, 2160, 1, 0x32315659, 3840, 0x40402d00};
    std::array<int, 53> s{};
    const std::pair<int, uint32_t> fixed[] = {
        {0,0x03141592},{1,4},{2,3840},{3,2160},{4,0x32315659},
        {5,0x40400900},{7,0x40400900},{11,3840},{15,0x32315659},
        {18,3840},{19,3840},{20,2160},{21,8294400},{22,1920},{23,1920},{24,1080},
        {25,10368000},{26,1920},{27,1920},{28,1080},{29,19489120},{30,1},
        {43,24576},{44,0x80000010},{45,3}};
    for (auto [i,v] : fixed) s[i] = static_cast<int>(v);
    assert(ubox_p3_compat1b::contract(d, false, s.data()));
    // Every fixed field and the upper words/zero modifier must fail closed when changed.
    for (int i=0; i<53; ++i) {
        if ((i>=0 && i<=30) || i==43 || i==44 || i==45) {
            auto bad=s; bad[i]^=1;
            assert(!ubox_p3_compat1b::contract(d, false, bad.data()));
        }
    }
    assert(!ubox_p3_compat1b::contract(d, true, s.data()));
    for (auto member : {&Desc::width,&Desc::height,&Desc::layers,&Desc::format,&Desc::stride}) {
        auto bad=d; bad.*member ^= 1;
        assert(!ubox_p3_compat1b::contract(bad, false, s.data()));
    }
    for (uint64_t usage : {UINT64_C(0x402d00),UINT64_C(0x40406d00),UINT64_C(0)}) {
        auto bad=d; bad.usage=usage;
        assert(!ubox_p3_compat1b::contract(bad, false, s.data()));
    }
    // IDs, fds, PIDs, local mappings, refcounts are not stable predicate inputs.
    for (int i : {31,32,33,34,35,36,37,38,39,40,41,42,46,47,48,49,50,51,52}) {
        auto changed=s; changed[i]=42;
        assert(ubox_p3_compat1b::contract(d, false, changed.data()));
    }
    using namespace ubox_r7_compat1;
    LegacyAttrRegion a; memset(&a,0xff,sizeof(a)); a.dataspace=0x10010000;
    int32_t crop[4]={0,0,0,0};
    assert(ubox_p3_compat1b::metadata(0x10,a,crop));
    for (uint32_t flag : {0u,0xffffffffu,0x11u,0x12u})
        assert(!ubox_p3_compat1b::metadata(flag,a,crop));
    for (size_t i=0;i<sizeof(a);++i) {
        auto bad=a; reinterpret_cast<uint8_t*>(&bad)[i]^=1;
        assert(!ubox_p3_compat1b::metadata(0x10,bad,crop));
    }
    int32_t noCollision[4]={0,0,2160,3840};
    assert(!ubox_p3_compat1b::metadata(0x10,a,noCollision));
    int32_t avc[4]={-1,-1,-1,-1};
    assert(!ubox_p3_compat1b::metadata(0x10,a,avc));
    std::array<uint8_t,kMetadataSize> original{}, shadow{};
    for (size_t i=0;i<original.size();++i) original[i]=uint8_t(i % 251);
    memcpy(original.data()+kActiveAttrOffset,&a,sizeof(a));
    auto saved=original;
    assert(translateMetadata(original.data(),original.size(),shadow.data(),shadow.size()));
    assert(saved==original);
    for (size_t i=0;i<shadow.size();++i) {
        auto expected=(i>=kLegacyAttrOffset && i<kLegacyAttrOffset+kAttrSize)
            ? original[i-kLegacyAttrOffset+kActiveAttrOffset] : original[i];
        assert(shadow[i]==expected);
    }
    assert(!translateMetadata(original.data(),0,shadow.data(),shadow.size()));
    assert(!translateMetadata(original.data(),original.size(),original.data(),original.size()));
    for (int i=0;i<100;++i) {
        int fd=createSizedShadowFd("compat1b-host-test",kMetadataSize); assert(fd>=0);
        struct stat st{}; assert(fstat(fd,&st)==0 && st.st_size==int64_t(kMetadataSize));
        void* map=mmap(nullptr,kMetadataSize,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);
        assert(map!=MAP_FAILED); memcpy(map,shadow.data(),shadow.size());
        int clone=dup(fd); assert(clone>=0); assert(close(fd)==0);
        assert(memcmp(map,shadow.data(),shadow.size())==0);
        assert(ftruncate(clone,kMetadataSize+4096)<0);
        assert(munmap(map,kMetadataSize)==0); assert(close(clone)==0);
    }
}
