# a16-prototype-b-r7-diag3-private-buffer-metadata

Status: **PHYSICAL BOOT PASS / AVC BLOCKED BY PROVEN DIAGNOSTIC UBSAN REGRESSION / CLOSED / NOT r8**

Physical follow-up on exact diag3 proved a normal boot, but two independent AVC attempts aborted the
ARM64 VLC CodecLooper in `ubox_r7_diag3_snapshot()` at `CODEC_PRE_USE`, before OMX `useBuffer` or
decoder/FBM use. Both report `ubsan: mul-overflow`. The helper's direct FNV-1a unsigned multiplication
intentionally wraps modulo 2^64, while `libstagefright` enables non-recovering unsigned-overflow UBSan.
This is an instrumentation regression, not an AVC/HEVC result. HEVC was not tested. The read-only
evidence is preserved under
`/work/evidence/ubox10/r7-diag3a-instrumentation-regression/input/unpacked/`; repeated audio tombstone
turnover is unrelated. Diag3 is closed and superseded only by the diagnostic-transparency candidate
`a16-prototype-b-r7-diag3a-private-buffer-metadata`.

This candidate is based on exact `a16-prototype-b-r7-diag2-hevc-crop`. It observes, but never
changes, private gralloc-handle state transported between the ARM64 framework, retained ARM32
Allwinner decoder, ARM32/ARM64 gralloc users, SurfaceFlinger, and Mali EGL import. Canonical r7 is
frozen and Gate 3 remains HOLD.

## Phase A: physical evidence and source audit

All files under
`/work/evidence/ubox10/r7-diag3-private-buffer-metadata/input/unpacked/` were read without mutation;
all entries in `SHA256SUMS` verified. The manifest SHA-256 is
`A362E9D63F8B669D3A2339AAE6D8D8F25DB9C40331401DC91213C5F53E60C25F`.

The paired trace mechanically establishes this public contract:

| Field/stage | successful AVC | failing HEVC | Result |
|---|---|---|---|
| OMX component | `OMX.allwinner.video.decoder.avc` | `OMX.allwinner.video.decoder.hevc` | differs by design |
| initial output | 1920x1080 YV12, crop 1920x1080 | same | identical |
| aligned output | 1920x1088 | 1920x1088 | identical |
| final diag2 native crop | 1920x1080 | 1920x1080 | identical |
| producer usage | `0x402d00` | `0x402d00` | identical |
| allocation | 3,133,504 bytes, 1920x1088 | same | identical |
| planes | offsets 0/2088960/2611200; strides 1920/960/960; heights 1088/544/544 | same | identical |
| modifier / AFBC | 0 / disabled | 0 / disabled | identical |
| remote import / AHB / native client | success | success | identical |
| EGL image | success | `EGL_BAD_ALLOC` (`0x3003`) | first observed failure |
| backend texture | valid | invalid, then unchanged fatal/SIGABRT | consequence |

The warning `Crop rectangle dimensions not equal to logical buffer dimensions` remains, but diag2
proves that ACodec visible crop alone is not causal: the same 1920x1080 crop over a 1920x1088 YV12
allocation survives in AVC and fails in HEVC.

The active gralloc ABI is `private_handle_t` from
`hardware/aw/gpu/mali-bifrost/gralloc/src/mali_gralloc_buffer.h`: 232 bytes, two transported fds and
53 transported integer slots. Compiler layout checks show identical serialized offsets on ARM32 and
ARM64; pointer-sized local fields are represented by fixed eight-byte unions. File-descriptor numbers,
mapped addresses, remote PID and refcount remain process-local and must not be compared as content.
The older 200-byte/45-int declaration in `hardware/aw/gpu/include/hal_public/hal_mali_midgard.h` is
not used by the active gralloc build. Its presence is an ABI-provenance ambiguity, not proof that the
closed decoder uses that declaration.

The serialized slot map is fixed-width on both ABIs: 0 magic, 1 flags, 2..4 logical width/height/
requested format, 5..10 producer/consumer usage and internal format, 11..14 stride/byte stride/
internal dimensions, 15..16 allocation format, 17..28 three plane records, 29 size, 30 layer count,
31..34 process-local base plus backing-store ID, 35 backing-store size, 36..40 CPU lock/producer PID/
remote PID/refcount state, 41..45 local attribute mapping plus metadata size/flag/YUV info, 46..48
framebuffer fd/offset, and 49..52 page/alignment values. `aw_format` exists only in the allocation
descriptor and is already observed by DIAG1 before handle creation; it is not transported in
`private_handle_t`. `ion_metadata_flag` is transported at slot 44. No second-FBM field exists in the
active open handle ABI, so that closed-decoder concept remains observable only through vendor logs.

The second transported fd is a real shared sidecar. Active source allocates and initializes a
24,576-byte region containing:

- `sunxi_metadata` at offset 0, size 23,480 (HDR static/dynamic fields, AFBC header, metadata flag);
- a 64-byte vendor gap at offsets 23,480..23,543;
- packed `attr_region` at offset 23,544, size 56 (crop, YUV transform, sparse flag, HDR and dataspace).

Current `UBOX_R7_DIAG1` records neither the 53 raw slots nor any sidecar byte. The retained decoder is
closed ELF32 code; `SetVideoFbmBufAddress(...)` is observable in its logs, but the blob cannot be
instrumented. The nearest open boundaries are therefore immediately before `OMX::useBuffer`, the
first fill-buffer-done after decoder use, remote gralloc import in each process, and immediately
before Mali's `eglGetNativeClientBufferANDROID`/`eglCreateImageKHR` path.

## Exact hypothesis and planned source delta

Diag3 tests one hypothesis: the retained ARM32 decoder modifies, or causes a decoder-specific value
in, a transported private-handle integer slot or fd-backed sidecar field that is absent from the
public GraphicBuffer/AHardwareBuffer contract; the first AVC/HEVC divergence should appear between
initial allocation, post-decoder fill-buffer-done, and SurfaceFlinger pre-EGL snapshots.

Planned observation points are:

| Boundary | Source | Runtime binary |
|---|---|---|
| `ALLOC_INITIAL`, `REMOTE_IMPORT` | gralloc allocation/reference source | ARM32 and ARM64 `gralloc.apollo.so` |
| `CODEC_PRE_USE`, `CODEC_POST_FBD` | `frameworks/av/media/libstagefright/ACodec.cpp` | `/system/lib64/libstagefright.so` |
| `EGL_PREIMPORT` | `external/skia/.../AHardwareBufferGL.cpp` | `/system/bin/surfaceflinger` |

Each `UBOX_R7_DIAG3` snapshot will report process bitness/PID, GraphicBuffer ID when available,
backing-store ID, all named handle fields, split raw-slot records, fd `fstat` identity, and a bounded
sidecar view. The sidecar is mapped with `PROT_READ | MAP_SHARED`, hashed in place, decoded only at
source-proven offsets, and immediately unmapped. It performs no write, ioctl, lseek, allocation-policy
change, format/usage/crop change, error query, retry, sleep, or control-flow change. Numeric fd values
are logged only alongside device/inode/size identity for cross-process correlation.

Possible outcomes are intentionally discriminating:

- divergence already at `ALLOC_INITIAL`: decoder-specific allocation request is hidden in the
  private contract;
- first divergence at ARM32 import or `CODEC_POST_FBD`: decoder/FBM use mutates transported state;
- first divergence at ARM64 import or `EGL_PREIMPORT`: serialization/import-side interpretation is
  implicated;
- no divergence at any snapshot: the next boundary lies inside closed Mali EGL import or content/
  synchronization state not represented by this handle/sidecar; no metadata repair is justified.

## Implemented observation contract

The strict overlay is
`configs/aosp/architecture-ceiling-a16/diagnostics/r7-hevc-diag3-private-buffer-metadata/`.
Its three patches have revision guards, exact pre/post hashes, and verified
`check`/`apply`/`revert` behavior. The identical 12,063-byte snapshot helper is compiled at each
subsystem boundary. It accepts only the proven `version=12`, `numFds=2`, `numInts=53` ABI; an
unexpected handle is logged as `HANDLE_ABI_REJECT` and is not decoded.

The five boundaries are `ALLOC_INITIAL`, `REMOTE_IMPORT`, `CODEC_PRE_USE`, `CODEC_POST_FBD`, and
`EGL_PREIMPORT`. Each can emit `HANDLE_ABI`, `HANDLE_NAMED`, `HANDLE_PLANES`, `HANDLE_LOCAL`,
`HANDLE_RAW`, `FD_ID`, `SIDECAR`, `SIDECAR_ATTR`, `SIDECAR_GAP`, `SIDECAR_DIFF`, and
`SIDECAR_DIFF_END`. All inherited `UBOX_R7_DIAG1` stages remain present. No additional EGL/GL error
query was added: the snapshot completes before the existing native-client-buffer operation, so it
cannot consume or replace EGL/GL error state. The existing `Failed to create a valid texture.` fatal
remains in the final SurfaceFlinger binary.

## Exact diag2 to diag3 runtime delta

| Runtime path | ELF | diag2 SHA-256 | diag3 SHA-256 | Purpose |
|---|---|---|---|---|
| `/system/bin/surfaceflinger` | ELF64 AArch64 | `E2B780E955FC87356533FC9B50C0F9D78561070681C5D2D4DAD877AC777A2A73` | `5BD92DAB98969B774469ED6581E9CD32D9C57E93D63A4CF0E126414B568CE838` | pre-EGL handle/sidecar snapshot |
| `/system/lib64/libstagefright.so` | ELF64 AArch64 | `BD48A7691A42C86916120940A95F2FF4B082836258D60B463D7AD87D90A5D113` | `4C1382C512867E5CE3CC324D927D871B200E6A352179FCE34AF27B4699CBA2C7` | pre-OMX and first post-FBD snapshots |
| `/vendor/lib/hw/gralloc.apollo.so` | ELF32 ARM | `F0BE5076BF4607F15691CFBB60D12F988E798ED92E0C4E0C5FBBB6F19D148089` | `7E654E0F9D968C5FA9C9F31893E0E60DCF6605E41A82783E6376A1D7D66194D5` | allocation/ARM32 import snapshots |
| `/vendor/lib64/hw/gralloc.apollo.so` | ELF64 AArch64 | `F12C8F1B3CA3F967367E32A44EF043BF0EE660B1D36B175D3736B059A31947F8` | `1F91BF6FA547DA11E42068C1A0C612E41B5C800AEE9CDAB2D320DD469295CB19` | allocation/ARM64 import snapshots |

The signed-filesystem comparison contains exactly those two system and two vendor changes; there
are no additions or removals. SONAME, DT_NEEDED, strong exports, modes, ownership and SELinux labels
are preserved. Added strong imports are limited to the observation implementation
(`AHardwareBuffer_getNativeHandle`, `mmap`, `fstat`, and formatting support). Complete checks against
the installed VNDK31 namespaces pass for ARM32 and ARM64 with zero unmatched strong imports. The
ARM32 `_ZNSt3__122__libcpp_verbose_abortEPKcz` regression remains absent.

## Candidate identity and offline result

- Image: `out/candidates/a16-prototype-b-r7-diag3-private-buffer-metadata/x12-a16-prototype-b-r7-diag3-private-buffer-metadata.img`
- Size: 1,641,814,016 bytes
- SHA-256: `385BA2FEDAC0C8726885781693017C7DD4A62D35D50C6494B905D4A2812E958E`
- Source: `android-security-16.0.0_r7`, `BP2A.250805.034`, API 36; manifest
  `ebea28d151539ecf0730b1a4ab92ac33edc17ac9`
- Targeted modules only: `surfaceflinger`, `libstagefright`, multilib `gralloc.apollo`; kernel was
  not rebuilt.

Ext4, sparse/raw roundtrip and extracted logical images pass; AVB and frozen LP geometry/extents
pass; Android 16/API36, `zygote64_32`, mixed ABI, app_process32/64, VNDK31 dual arch, BoringSSL32/64,
mapper/gralloc/Mali SP-HAL closure, boot/kernel 5.4.302+, and 22-module `vendor_dlkm` inventory are
preserved. System-only VINTF passes. Full VINTF remains exit 65 solely for inherited
`CONFIG_NFS_FS=y` versus FCM-6 `n`; it is **NOT PASS** and was not changed.

Canonical r7, product, boot, kernel, vendor_dlkm, proprietary Mali, OMX/Cedar, audio, Wi-Fi, HWC,
display/quarter-screen behavior, and the diag2 crop semantics are unchanged. HEVC remains blocked;
this offline result is not a physical or functional pass.

## Physical protocol

Use PowerShell 7 helper
`scripts/capture-a16-prototype-b-r7-diag3-private-buffer-metadata.ps1` with its explicit
`C:\platform-tools\adb.exe` default and `192.168.1.9:7896`. Run `BootGate` first and confirm a normal
full-screen boot. Then run `AVCPre`, start `AVCLive` in a PC terminal, play the known AVC fixture once,
stop live capture with Ctrl+C, and run `AVCPost`. Repeat `HEVCPre` and `HEVCLive` for exactly one HEVC
attempt; after userspace recovery run `HEVCPostRestart`. Live full logcat must already be streaming
before playback. Do not reboot, loop playback, clear post-failure logs, or alter HDMI/wm state.

Interpret the paired `UBOX_R7_DIAG3` trace mechanically:

- first AVC/HEVC difference at `ALLOC_INITIAL`: allocation-request/private initialization boundary;
- first difference at ARM32 `REMOTE_IMPORT` or `CODEC_POST_FBD`: closed decoder/FBM use boundary;
- first difference at ARM64 import or `EGL_PREIMPORT`: serialization/import interpretation boundary;
- no handle/sidecar difference: the next hypothesis must move inside closed Mali import or to buffer
  content/synchronization state; no metadata mutation is authorized from a null result.
