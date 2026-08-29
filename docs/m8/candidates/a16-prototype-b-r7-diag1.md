# Android 16 Prototype B r7-diag1

Status: **OFFLINE CHECKED / READY FOR PAIRED PHYSICAL DIAGNOSTIC VALIDATION**.

This is an instrumentation-only derivative of exact frozen r7. It is **not a repair, not r8,
not a release**, and it does not change the Gate 3 decision. Its only purpose is to run the same
build once with the known-good AVC fixture and once with the failing HEVC fixture, then identify the
first buffer/import field or EGL/GL operation that differs.

The architecture result remains **PASS / FROZEN**. Gate 3 remains **HOLD**; H.264 remains a physical
pass and HEVC remains a blocker. HEVC is not fixed and its exact earlier contract delta is not yet
proven.

## Candidate identity

| Item | Value |
|---|---|
| ID | `a16-prototype-b-r7-diag1` |
| exact base | `a16-prototype-b-r7`, 1,641,773,056 bytes, `A1F58668AEFFC9DC83CFFD8A49A309839332B6616C02153DCC00A71136A7AA27` |
| image | `out/candidates/a16-prototype-b-r7-diag1/x12-a16-prototype-b-r7-diag1.img` |
| size | 1,641,781,248 bytes |
| SHA-256 | `A68E7BD75D9819794BE22E9E05BE76969B2883DF8965DC277482E8C99231C6A4` |
| Android | `android-security-16.0.0_r7`, BP2A.250805.034, API 36 |
| manifest | `ebea28d151539ecf0730b1a4ab92ac33edc17ac9` |
| kernel | exact r7 5.4.302+; not rebuilt or modified |
| prefix | `UBOX_R7_DIAG1` |

Source revisions are frameworks/native `d862b53356dc26794fb5451782806979c46e6769`, external/skia
`4c18a9680d52c2cd5e35cfef2f548635a445fafe`, frameworks/av
`d1137ad4b24b686d9b00fd1b7be1b520f7b6ee2b`, hardware/interfaces
`b553275c84253b074a8532a6ff0f4406c43e606e`, and kernel
`027ef79e8facb73cb2419b4a08c0bd3f13a2206e`.

## Reproducible diagnostic overlay

Canonical r7 remains isolated. Its normal patch path does not include this prefix or any diagnostic
patch. Diag1 is a separate, mechanically applicable/revertible overlay under
`configs/aosp/architecture-ceiling-a16/diagnostics/r7-hevc-diag1/`:

1. `0001-frameworks-native-renderengine-trace.patch`
2. `0002-external-skia-egl-gl-trace.patch`
3. `0003-frameworks-av-media-native-window-trace.patch`
4. `0004-gralloc-private-contract-trace.patch`

`prepare.sh check` verifies exact source revisions and hashes and reports either the exact base or
exact patched state. The ordinary architecture-ceiling patch series is untouched. Every patch is
marked `DIAGNOSTIC ONLY` and `NO FUNCTIONAL REPAIR`.

Targeted builds used the frozen `ubox10_ceiling_arm64-bp2a-userdebug` lineage and rebuilt only
`surfaceflinger`, `libstagefright`, and both architectures of `gralloc.apollo`. The ARM32 gralloc is
required because the retained allocator service is ELF32; the ARM64 gralloc is required to observe
the imported private handle inside ARM64 SurfaceFlinger.

## Instrumentation points and stages

- `frameworks/av/media/libstagefright/MediaCodec.cpp` emits `CODEC_SELECT` and configured
  `CODEC_OUTPUT`: MIME, the actually selected component, encoder/decoder, profile, level, bit depth,
  coded dimensions, color format, crop, and native-window presence.
- `frameworks/av/media/libstagefright/ACodec.cpp` emits OMX-port and unique registered-buffer
  `CODEC_OUTPUT` plus changed `NATIVE_WINDOW` crop state: component, GraphicBuffer ID, OMX buffer ID,
  dimensions, stride, layers, format, usage, crop, and the existing crop-call result.
- `frameworks/av/media/libstagefright/SurfaceUtils.cpp` emits the `NATIVE_WINDOW` configuration:
  requested dimensions/format, producer usage, consumer usage, final combined usage, rotation, and
  reconnect state before the unchanged usage handoff.
- donor `mali_gralloc_bufferallocation.cpp` emits `GRALLOC_ALLOC` after allocation decisions:
  backing-store ID, requested/internal/allocation formats, modifier/AFBC, producer/consumer/combined
  and private usages, logical/allocation dimensions, total size, layers, three-plane layout,
  `aw_format`, `ion_metadata_flag`, flags/version/fd/int counts, and Allwinner alignments.
- donor `mali_gralloc_reference.cpp` emits `GRALLOC_HANDLE` only on first remote import, after the
  existing mutex unlock, with the transported private-handle contract. `aw_format` is not transported
  in that handle, plane pixel stride is unavailable, and second-FBM state is not represented; the log
  states those limitations instead of inventing values.
- `frameworks/native/libs/renderengine/skia/SkiaRenderEngine.cpp` emits `RENDERENGINE_MAP` before the
  unchanged mapping call: GraphicBuffer ID, dimensions, stride, layers, format, usage, protected and
  readable/writeable intent, generation, and the fact that a gralloc2 name is unavailable.
- `frameworks/native/libs/renderengine/skia/compat/GaneshBackendTexture.cpp` emits complete
  `AHB_DESC`, GL backend-format validity, and final `BACKEND_TEXTURE` validity immediately before the
  original fatal check.
- `external/skia/src/gpu/ganesh/gl/AHardwareBufferGL.cpp` emits `NATIVE_CLIENT_BUFFER`,
  `EGL_CREATE_IMAGE`, `GL_GEN_TEXTURE`, `GL_BIND_TEXTURE`, and `GL_EGL_IMAGE_TARGET`, including native
  buffer result, EGLImage, texture target/name, and the first already-checked EGL/GL error.

The complete emitted stage set is:

```text
CODEC_SELECT CODEC_OUTPUT NATIVE_WINDOW GRALLOC_ALLOC GRALLOC_HANDLE
AHB_DESC RENDERENGINE_MAP NATIVE_CLIENT_BUFFER EGL_CREATE_IMAGE
GL_GEN_TEXTURE GL_BIND_TEXTURE GL_EGL_IMAGE_TARGET BACKEND_TEXTURE
```

Logging is conditional: AVC/HEVC configuration, large video state, and YV12 buffers at least
1280x720. Gralloc records allocation and first remote import rather than frames; ACodec buffer records
occur on registration of a new GraphicBuffer. HWC was deliberately not touched because its eventual
composition decision is corroborative and follows the proven eager RenderEngine import boundary.

## Correlation and error-state preservation

Codec, GraphicBuffer, AHardwareBuffer, RenderEngine, and Skia records use the existing 64-bit
GraphicBuffer/AHardwareBuffer ID. Gralloc allocation/import uses the existing private-handle
`backing_store_id`. These are separate identifier domains, bridged by timestamp, dimensions, format,
usage, allocation dimensions, plane layout, and private metadata. No ioctl, syscall, global registry,
lock, or expensive correlation mechanism was added.

The EGL/GL trace does not consume new production error state:

- The existing failed `eglCreateImageKHR` branch still calls `eglGetError()` exactly once; diag1
  stores that value, conditionally logs it, and passes it to the existing debug message.
- The existing post-`glBindTexture` and post-`glEGLImageTargetTexture2DOES` `glGetError()` calls
  remain exactly one each. Their saved values are logged before the unchanged tests.
- `eglGetNativeClientBufferANDROID`, successful `eglCreateImageKHR`, and `glGenTextures` do not gain
  an error query; their records say `not_queried_preserve_state` where applicable.
- Cleanup, return paths, mapping eligibility, and `LOG_ALWAYS_FATAL("Failed to create a valid
  texture...")` remain unchanged.

## Exact runtime delta from frozen r7

| Runtime path | r7 size / SHA-256 | diag1 size / SHA-256 | ELF | Reason |
|---|---|---|---|---|
| `/system/bin/surfaceflinger` | 8,565,296 / `582E1B0B...F3C61` | 8,565,352 / `E2B780E9...A2A73` | ELF64 AArch64 | RenderEngine/AHB/Skia EGL-GL/backend trace |
| `/system/lib64/libstagefright.so` | 2,067,672 / `F765E063...FDC4` | 2,067,648 / `B0D1E7D7...B16F` | ELF64 AArch64 | codec/native-window trace |
| `/vendor/lib/hw/gralloc.apollo.so` | 56,588 / `7325BD8B...8AAC` | 57,660 / `2833B9B8...36B5` | ELF32 ARM | allocator/private-contract trace |
| `/vendor/lib64/hw/gralloc.apollo.so` | 77,248 / `B03BFE24...CFE7` | 81,344 / `F12C8F1B...47F8` | ELF64 AArch64 | imported-handle/private-contract trace |

Complete signed filesystem diffs are exactly:

```text
system added=[] removed=[]
system changed=[system/bin/surfaceflinger, system/lib64/libstagefright.so]

vendor added=[] removed=[]
vendor changed=[lib/hw/gralloc.apollo.so, lib64/hw/gralloc.apollo.so]

product changed=[]
vendor_dlkm changed=[]
```

All four replacements preserve ELF class, architecture, SONAME where applicable, DT_NEEDED order,
strong dynamic exports, mode/owner/SELinux inode contract, and required HMI/loader entry points. The
frozen ARM32 donor exposes nine incidental weak libc++ template instantiations that are absent in both
the diagnostic build and a separately saved no-instrumentation rebuild with the current exact
toolchain. No importing consumer exists, all strong exports are preserved, and the gralloc HMI/SP-HAL
closure passes. This provenance-only visibility difference is recorded explicitly rather than hidden.

System/vendor AVB and subordinate vbmeta are necessarily regenerated. The outer delta is exactly
`super.fex`, `Vsuper.fex`, `vbmeta_system.fex`, `Vvbmeta_system.fex`, `vbmeta_vendor.fex`, and
`Vvbmeta_vendor.fex`; the other 44/50 payloads are byte-identical to r7. Logical bytes were written
into the frozen r7 extents in place, including both fragmented vendor extents. LP metadata, both
metadata slots, group maximum, partition sizes, empty B slots, and geometry remain exact r7.

## Unchanged critical r7 assets

- boot `527CF878...8063`, kernel Image `287A82F7...4F40`, 5.4.302+ Path-A config
  `2A159B7E...4F29`, and the exact 22-module vendor_dlkm `488EE1E1...C07`;
- product_a `6E2D0AF3...8974` and every unrelated system/product file;
- proprietary ARM64 Mali `03333D49...C7F8`, ARM64 mapper `D0FC49B3...61E8`, ARM32 mapper
  `5D18BB59...8BE3`, and all unrelated vendor files;
- BoringSSL32 `CD2BCD98...1166`, BoringSSL64 `E8F3B67A...058F`, and init rc
  `459FEA4E...FE1D`;
- proprietary OMX/Cedar, ARM32 legacy services, audio, Wi-Fi, HDMI/display configuration, AVB policy,
  root mount semantics, and LP geometry.

No kernel, proprietary Mali/media/audio blob, audio source, HWC policy, HDMI mode, quarter-screen,
SELinux, VINTF, Wi-Fi, GMS, or Vulkan change is present.

## Offline preservation result

- Android 16/API 36 identity and active mixed ABI properties pass: `arm64-v8a,armeabi-v7a,armeabi`,
  `abilist64=arm64-v8a`, `abilist32=armeabi-v7a,armeabi`.
- `zygote64_32`, ARM64 `app_process64`, ARM32 `app_process32`, 1,471 system AArch64 objects, and 701
  system ARM objects remain present.
- All APEX validation passes; VNDK31 contains both ARM and ARM64 `libaudioroute.so` closure.
- BoringSSL32/64 remain exact. ARM64 mapper, diagnostic gralloc, and proprietary Mali each retain
  zero unmatched strong SP-HAL imports.
- Ext4, system/vendor AVB, subordinate vbmeta signatures/rollback locations, exact LP geometry,
  sparse/raw round-trip, outer IMAGEWTY, boot/kernel checkpoint, Path-A configs, 22-module inventory,
  and AIC FMAC preservation pass.
- System-only VINTF is **PASS / exit 0**. Full VINTF remains **exit 65 / inherited
  `CONFIG_NFS_FS=y` versus FCM-6 `n` only / NOT PASS**.
- Split SELinux compilation passes offline; no enforcing-runtime claim is made.
- Static isolation proves canonical r7 has no diag1 marker, all four diag1 binaries contain it, all
  expected stage strings are present, no repair decision mutation was added, and the fatal remains.

The machine-readable build and audit outputs remain in the ignored candidate directory; the tracked
record is `docs/m8/candidates/a16-prototype-b-r7-diag1.json`.

Focused diag1+r7 metadata/isolation tests pass 21/21. The full lightweight repository suite passes
157 tests with 52 explicit skips for absent ignored historical candidate, binary, or generated
fixtures; none of those unavailable fixture checks is reported as a pass. Python compileall, all new
JSON parses, the built-binary marker/fatal checker, and PowerShell structural/safety checks pass.
PowerShell itself is not installed on this Linux build VM, so a native PowerShell parser/runtime
syntax invocation is accurately classified as not run; the helper is intended for Windows
PowerShell 7.

## Paired Windows capture

Use Windows PowerShell 7 and the helper
`scripts/capture-a16-prototype-b-r7-diag1-media-paired.ps1`. Supply a hostname/IP without hard-coding
it in the script; TCP port 7896 is the default:

```powershell
$Endpoint = 'DEVICE-IP-OR-HOSTNAME'
pwsh .\scripts\capture-a16-prototype-b-r7-diag1-media-paired.ps1 -DeviceEndpoint $Endpoint -Phase Baseline
pwsh .\scripts\capture-a16-prototype-b-r7-diag1-media-paired.ps1 -DeviceEndpoint $Endpoint -Phase AVCPre -ClearLogcat
# Manually play the known-good H.264 fixture once; confirm visible video and audible HDMI.
pwsh .\scripts\capture-a16-prototype-b-r7-diag1-media-paired.ps1 -DeviceEndpoint $Endpoint -Phase AVCPost
pwsh .\scripts\capture-a16-prototype-b-r7-diag1-media-paired.ps1 -DeviceEndpoint $Endpoint -Phase HEVCPre -ClearLogcat
# Manually launch the known HEVC fixture once; do not loop it.
pwsh .\scripts\capture-a16-prototype-b-r7-diag1-media-paired.ps1 -DeviceEndpoint $Endpoint -Phase HEVCPostRestart
pwsh .\scripts\capture-a16-prototype-b-r7-diag1-media-paired.ps1 -DeviceEndpoint $Endpoint -Phase Final
```

Each invocation creates a timestamped directory under
`Downloads\UBOX10-r7-diag1-paired`. Pre phases capture evidence before offering an explicit typed
confirmation to clear logcat. Nothing clears logcat after failure; pstore and tombstones are never
cleared. `HEVCPostRestart` waits for ADB to return without assuming a kernel reboot, then immediately
captures full/all+crash logcat, diag lines, media/codec, SurfaceFlinger/RenderEngine, gralloc/HWC,
properties, services, uptime/boot ID, restart evidence, and tombstones. The helper never reboots,
changes HDMI/wm state, or starts/loops playback.

## Decision and next boundary

Physical status is **OFFLINE CHECKED / READY FOR PAIRED PHYSICAL DIAGNOSTIC VALIDATION**, not PASS.
Flash this diag1 image, capture one AVC control and one HEVC reproduction on the same boot lineage,
then diff the first `UBOX_R7_DIAG1` field or EGL/GL operation that diverges. Only that evidence may
select a minimum repair boundary. R8 remains not authorized and was not built; the intended
`codex/m8-a16-development` branch was not created.
