# a16-prototype-b-r7-hevc-abi-compat1-sdr-shadow

Status: **PHYSICAL BOOT PASS / AVC PASS / HEVC FAIL — SHADOW FD IMPLEMENTATION BLOCKER / ABI TRANSLATION NOT PHYSICALLY TESTED / SUPERSEDED BY COMPAT1A**

This candidate is based on exact `a16-prototype-b-r7-diag3a-private-buffer-metadata`. It tests one
production-boundary compatibility repair for the physically proven Allwinner-producer versus Mali
r20p0-consumer metadata ABI collision. Canonical r7 remains frozen and Gate 3 remains HOLD.

## Proven boundary and exact implementation

The active 24,576-byte metadata fd stores the extended Allwinner `sunxi_metadata` at bytes
0..23,479 and the active 56-byte `attr_region` at 23,544..23,599. ARM64 Mali r20p0 instead reads a
legacy 56-byte attr block at byte `0x80`. Its first four signed words are crop top/left/height/width,
but those offsets are HDR10+ `divLut` data in the active producer ABI. AVC leaves the words negative
and imports successfully; HEVC intentionally initializes them, Mali misreads a non-negative invalid
crop, and `eglCreateImageKHR` returns `EGL_BAD_ALLOC`.

The separate overlay is
`configs/aosp/architecture-ceiling-a16/diagnostics/r7-hevc-abi-compat1-sdr-shadow/`. In
`external/skia/src/gpu/ganesh/gl/AHardwareBufferGL.cpp`, immediately before
`eglGetNativeClientBufferANDROID`, an exact eligible buffer receives a consumer-only view:

1. mmap the original fd2 `PROT_READ` and validate the public/private/sidecar contract;
2. create an independent 0x6000-byte `ashmem_create_region` fd;
3. copy all 0x6000 original bytes into the shadow;
4. copy the complete active 56-byte attr block from 23,544 to legacy offset `0x80`;
5. clone the native handle, replace only cloned fd2, and import it through
   `AHARDWAREBUFFER_CREATE_FROM_HANDLE_METHOD_CLONE`;
6. give only that temporary AHardwareBuffer view to Mali EGL and release the caller reference after
   `eglCreateImageKHR` has taken its own reference.

The original producer handle and fd2 are never written. On any guard, allocation, mapping, clone, or
AHardwareBuffer import failure, the original AHardwareBuffer follows the unchanged EGL/fatal path.
The shadow is created on the existing backend-texture import/cache-miss path, not once per rendered
frame.

The physical run disproved the assumption that `ashmem_create_region` always supplies an
`fstat`-sized object on this runtime. Libcutils selected legacy `/dev/ashmem`; its
`ASHMEM_SET_SIZE` state is ioctl-private while the character-device inode reports `st_size=0`.
Compat1 therefore failed closed before translation. This is corrected only in compat1a.
AHardwareBuffer `CLONE`
duplicates/imports the handle and its fds; the mapper carries and owns its imported fd2, while Mali
maps that fd. The outer cloned handle is closed/deleted after `createFromHandle`; successful
`eglCreateImageKHR` retains the AHardwareBuffer view, and the local AHardwareBuffer reference is then
released. The implementation adds no DT_NEEDED library and has no fd leak, double close, or
use-after-close in this ownership chain.

## Eligibility guard

Compat1 activates only when every condition matches:

- AHardwareBuffer: 1920x1088, one layer, stride 1920, YV12 `0x32315659`, usage `0x402d00`;
- non-protected and non-AFBC;
- native handle: version 12 bytes, exactly 2 fds + 53 ints, magic `0x03141592`, flags 4;
- requested/allocation format YV12, producer and consumer usage each `0x400900`;
- exact three-plane YV12 geometry and total allocation size 3,133,504 bytes;
- fd2 size 0x6000, metadata flag 0, yuv info 3, `sunxi_flag=0`;
- active attr crop/yuv-transform/sparse values all -1 and dataspace `0x10010000`;
- legacy crop collision words all non-negative and not logical 0,0,1088,1920.

This is deliberately the proven **SDR / YV12 / non-AFBC / non-protected** 1920x1088 gate only.
Main10, HDR, AFBC, protected playback and 4K are not supported or claimed by this candidate.

## Complete 56-byte translation

| Legacy destination | Active source-relative | Field | Bytes |
|---:|---:|---|---:|
| `0x80` | 0 | crop top | 4 |
| `0x84` | 4 | crop left | 4 |
| `0x88` | 8 | crop height | 4 |
| `0x8c` | 12 | crop width | 4 |
| `0x90` | 16 | use YUV transform | 4 |
| `0x94` | 20 | use sparse allocation | 4 |
| `0x98..0xb3` | 24..51 | complete legacy HDR-info block | 28 |
| `0xb4` | 52 | dataspace | 4 |

`UBOXR7Compat1Metadata.h` statically asserts the struct size, each field offset, `0x80 + 56 =
0xb8`, and `23544 + 56 = 23600`. The implementation intentionally copies all 56 bytes, not just the
four crop words.

## Exact diag3a to compat1 runtime delta

| Runtime path | diag3a SHA-256 | compat1 SHA-256 | Result |
|---|---|---|---|
| `/system/bin/surfaceflinger` | `5BD92DAB98969B774469ED6581E9CD32D9C57E93D63A4CF0E126414B568CE838` | `97A476E550015C50CA92302418B6625171995192161A37EBB3EBD7AF7102745C` | only semantic runtime delta |
| `/system/lib64/libstagefright.so` | `3FDE0D408ED26CE76C7CAE2DB3DD41E38B1783B982CFAB251518D778C39F13CF` | same | byte-identical |
| `/vendor/lib/hw/gralloc.apollo.so` | `7E654E0F9D968C5FA9C9F31893E0E60DCF6605E41A82783E6376A1D7D66194D5` | same | byte-identical |
| `/vendor/lib64/hw/gralloc.apollo.so` | `1F91BF6FA547DA11E42068C1A0C612E41B5C800AEE9CDAB2D320DD469295CB19` | same | byte-identical |

The signed-filesystem comparison has exactly `changed=[system/bin/surfaceflinger]`; vendor has no
changed file. SurfaceFlinger remains ELF64/AArch64 and preserves SONAME, DT_NEEDED and all strong
exports. It adds exactly three already-provided strong imports: `AHardwareBuffer_createFromHandle`,
`AHardwareBuffer_release`, and `native_handle_clone`. Mali, OMX/Cedar, gralloc, mapper, HWC, audio,
Wi-Fi, product, boot, kernel and vendor_dlkm remain byte-identical to diag3a.

All `UBOX_R7_DIAG1` and `UBOX_R7_DIAG3` records remain. New bounded records use
`UBOX_R7_COMPAT1`: `eligible`, `shadow_created`, `translated`, `view_created`, and
`egl_import_result`. The original RenderEngine invalid-texture fatal remains present.

## Candidate and offline result

- Image: `out/candidates/a16-prototype-b-r7-hevc-abi-compat1-sdr-shadow/x12-a16-prototype-b-r7-hevc-abi-compat1-sdr-shadow.img`
- Size: 1,641,822,208 bytes
- SHA-256: `D4FAFE24FE2A743764DA50769FDBD8D6B6C7152646017C3C4F0B09C8FBBEFAAB`
- Source: Android 16/API36, `BP2A.250805.034`, external/skia
  `4c18a9680d52c2cd5e35cfef2f548635a445fafe`; only SurfaceFlinger was rebuilt; kernel was not.

The host test compiles the exact translation helper under ASan+UBSan and proves all fields, exact
56-byte copy, preservation of every other shadow byte, and byte-identical original input. Ext4,
sparse/raw integrity, AVB, exact diag3a LP geometry/extents, Android/API identity, mixed ABI and
`zygote64_32`, app_process32/64, VNDK31 dual arch, BoringSSL32/64, mapper/gralloc/Mali SP-HAL
closure, boot/kernel 5.4.302+ and the 22-module vendor_dlkm inventory pass. ARM32 and ARM64 graphics
closures have zero unmatched strong imports. System-only VINTF passes. Full VINTF remains exit 65
for inherited `CONFIG_NFS_FS=y` versus FCM-6 `n`; it is **NOT PASS** and was not changed.

## Physical gate

Use `scripts/capture-a16-prototype-b-r7-hevc-abi-compat1-sdr-shadow.ps1` under PowerShell 7. The
default endpoint is `192.168.1.9:7896`, and the default executable is
`C:\platform-tools\adb.exe`. Run each phase separately:

1. `BootGate`.
2. `AVCPre`, `AVCLive`, one manual known-good AVC playback, then `AVCPost`; stop and review.
3. Only after AVC passes: `HEVCPre`, `HEVCLive`, one manual SDR YV12 HEVC playback, then `HEVCPost`.
4. If stable, manually test pause/resume/seek/back and run `InteractionPost`.
5. Repeat AVC through `AVCRegressionPre`, `AVCRegressionLive`, and `AVCRegressionPost`; finish with
   `Final`.

Success requires compat1 activation only on the HEVC collision, unchanged original-sidecar proof,
Mali EGL import success, valid BackendTexture, no SurfaceFlinger abort/framework restart, and AVC
preservation before and after. Stop after SDR YV12. Do not test Main10, HDR, AFBC, protected content,
or 4K without a separate gate. No physical PASS is claimed by this document.
