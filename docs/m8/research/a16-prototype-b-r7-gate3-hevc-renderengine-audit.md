# Android 16 Prototype B r7 Gate 3 HEVC RenderEngine audit

Date: 2026-08-29

## Decision

`a16-prototype-b-r7` remains a **PHYSICAL ARCHITECTURE PASS / FROZEN ANDROID 16 ARM64
MIXED-ARCHITECTURE BASELINE**. Gate 3 functional preservation is **HOLD**:

- H.264 + AAC is a physical **PASS** through the exact Allwinner AVC/Cedar path, visible video,
  continuous playback, pause/resume/BACK, and audible HDMI output.
- The HEVC test is **FAIL / BLOCKED** by an ARM64 SurfaceFlinger RenderEngine SIGABRT.
- The event was a SurfaceFlinger/zygote/framework restart, **not a Linux kernel reboot**.
- The smallest **PROVEN** failure boundary is a 1920x1088, non-protected, readable YV12
  `AHardwareBuffer` advertised as GPU-texturable that cannot become a valid Ganesh GL backend
  texture.
- The exact HEVC-only buffer-contract delta and exact failing EGL/GL operation are **NOT PROVEN**.
  Requested/internal format, full producer/consumer usage, planes, modifier/AFBC state, and private
  handle metadata were not captured.
- The hypothesis that AVC survives only because DEVICE/overlay composition prevents RenderEngine
  import is contradicted by the Android 16 source ordering. Import is eager and precedes the
  eventual HWC composition decision.
- The post-restart quarter-screen is a separate, **STRONGLY SUPPORTED** display-recovery defect:
  the retained display stack selects HDMI mode 34/`0x22`, proven to be 3840x2160p60, while
  Android/SurfaceFlinger continue composing 1920x1080.

Therefore:

```text
R8_AUDIT_DECISION = HOLD_FOR_MORE_EVIDENCE
```

No r8 image, repair, development branch, Android build, kernel build, or device mutation was
performed.

## Scope, baseline, and evidence standard

The repository started clean on `codex/m8-architecture-ceiling` at
`4affb0b304ba51e4acaa7063c7c15a8f18c2ccf6`. The fetched remote branch resolved to the same commit.
The audited image is `a16-prototype-b-r7`, 1,641,773,056 bytes, SHA-256
`A1F58668AEFFC9DC83CFFD8A49A309839332B6616C02153DCC00A71136A7AA27`.

The three local forensic inputs were verified before use:

| Input | Bytes | SHA-256 | Provenance |
|---|---:|---|---|
| `gate3-h264-physical-validation-20260829-142314.txt` | 493,236 | `844c928d44f0b79d3aa55c7b7be3869ec1cf184bb6d014dca9d7ed6941e3fa31` | User-supplied exact-r7 physical validation capture under ignored `out/forensics/r7-gate3-hevc/` |
| `r7-hevc-reboot-quarter-screen-forensics.txt` | 2,916,649 | `4c650fda2180f74131f476cb0312063f2ad4d43e97415dc487894a0bddac4d60` | User-supplied post-failure log, tombstone, dumps, properties, sysfs and recovery capture |
| `post-reboot-quarter-screen-screencap.png` | 49,375 | `4e2d31f57eabb707a0b9f6c57faf28975ce888f0b17a448c179c6f392651f6e7` | User-supplied post-restart Android screencap; PNG IHDR is 1920x1080 |

The raw files remain outside Git. Exact timestamps and line numbers below refer to those hash-pinned
files. “PROVEN” requires direct runtime/source/binary evidence; “STRONGLY SUPPORTED” joins multiple
independent observations without the missing discriminating field; “NOT PROVEN” or “NOT
OBSERVABLE” means the current evidence cannot decide it.

Source revisions used by this audit:

| Tree | Revision / provenance |
|---|---|
| `frameworks/native` | `d862b53356dc26794fb5451782806979c46e6769` |
| `external/skia` | `4c18a9680d52c2cd5e35cfef2f548635a445fafe` |
| `hardware/interfaces` | `b553275c84253b074a8532a6ff0f4406c43e606e` plus the already-recorded r7 mapper back-deploy integration |
| ARM64 gralloc source | Tracked Apache-2.0 BPI donor copy pinned from `316cd80ca43fa17b0385eacd7f6f3652bbd66b2a`, gralloc tree `8a231b4f821fc0e30fd9010fb6b51ab01325d616` |
| Kernel control | `/work/src/ubox10-kernel-5.4.302-common` at `027ef79e8facb73cb2419b4a08c0bd3f13a2206e` |

The checked-in H616/sun50iw9p1 platform evidence remains authoritative. Donor H618 labeling is not
promoted to exact-device hardware evidence.

## Exact runtime timelines

### H.264 + AAC control — PASS

| Time | Evidence |
|---|---|
| 06:19:20.871–06:19:20.910 | VLC `StartActivity` and `VideoPlayerActivity` launch (H.264 file lines 399, 401). |
| 06:19:21.740 | VLC selects `OMX.allwinner.video.decoder.avc` (line 633). |
| 06:19:21.833–06:19:21.844 | `OMXStore` instantiates that exact component; Cedar clock is enabled (lines 758, 762). |
| 06:19:21.878 | Native window is configured 1920x1080, format `0x32315659`, usage `0x402d00` (line 789). |
| 06:19:21.916–06:19:21.923 | MediaCodec NDK opens; AAC uses VLC/FFmpeg `avcodec` (lines 790, 796). |
| 06:19:21.931–06:19:21.945 | CedarC v1.3.0; VE reaches 696 MHz; AFBC flag is 0; FBM is 1920x1088, align 32, 12 buffers, pixel-format enum 4 (lines 822, 851, 869–871). |
| 06:19:21.946–06:19:21.960 | Display crop remains 1920x1080; component reports usage `0x400400`; final native window is 1920x1088 YV12 with `0x402d00` (lines 878, 902–906). |
| 06:19:22.012–06:19:22.018 | VLC reports format 842094169, 1920x1088, stride 1920, visible height 1080, then receives the first picture (lines 931–950). |
| 06:19:22.037 onward | `sunxihwc` repeatedly inspects the video handle and reports `ion_metadata_flag = 0` (first at line 956). |

The physical observations establish visible normal video, audible HDMI audio, continuous playback,
pause, resume, BACK, and no new playback-attributable fatal. The exact control chain is:

```text
ARM64 VLC
  -> MediaCodec NDK
  -> retained ARM32 OMXStore / OMX.allwinner.video.decoder.avc
  -> Allwinner CedarC / VE at 696 MHz
  -> 1920x1088 linear, non-AFBC YV12 native-window buffers
  -> SurfaceFlinger / retained SUNXI HWC / display
  -> visible HDMI video

AAC
  -> VLC/FFmpeg software avcodec
  -> Android AudioTrack
  -> retained ARM32 Apollo audio HAL
  -> audible HDMI
```

### HEVC trigger — first fatal

| Time | Evidence |
|---|---|
| 06:27:53.503–06:27:53.544 | VLC `StartActivity` and `VideoPlayerActivity` launch (HEVC file lines 5252–5274). |
| 06:27:53.700–06:27:53.705 | Two VLC SurfaceViews are created at 1920x1080 (lines 5318–5326). |
| 06:27:53.929–06:27:53.981 | Cedar clock is enabled and VE reaches 696 MHz (lines 5345, 5347). |
| 06:27:54.070 | ARM64 SurfaceFlinger RenderEngine thread receives SIGABRT (line 5352). |
| 06:27:54.085–06:27:54.103 | SurfaceView layout/callback records 1920x1088 after signal delivery (lines 5353–5357). These later log timestamps do not establish when the failing buffer was queued. |
| 06:27:54.450–06:27:54.451 | Tombstone records the invalid 1920x1088 YV12 texture and Ganesh/Skia/RenderEngine backtrace (lines 5375, 5390–5397). |
| 06:27:54.567–06:27:54.640 | Init observes SurfaceFlinger signal 6, kills SurfaceFlinger and primary zygote, and successfully runs the SurfaceFlinger `onrestart` zygote restart (lines 5414–5420). |
| 06:27:55.135 | Cedar clock is disabled (line 5439). |

The exact HEVC OMX component name is **NOT OBSERVABLE**. The retained codec registry contains
`OMX.allwinner.video.decoder.hevc`, but registration plus Cedar/VE activity is not proof that this
test selected it. The proven first-fatal chain is:

```text
VLC HEVC launch
  -> retained hardware-media activity (Cedar clock + VE 696 MHz)
  -> a GPU-sampleable 1920x1088 YV12 GraphicBuffer reaches ARM64 SurfaceFlinger
  -> SkiaRenderEngine eagerly maps it as a readable external texture
  -> Ganesh GL backend texture is invalid
  -> LOG_ALWAYS_FATAL / SIGABRT in RenderEngine
  -> init restarts SurfaceFlinger and zygote/framework
```

### No kernel reboot

This was **PROVEN not to be a Linux/kernel reboot**:

- the 06:34 capture reports uptime 7,902.54 seconds (2:11), spanning the 06:27 failure;
- the SurfaceFlinger tombstone reports process uptime 7,526 seconds;
- `/sys/fs/pstore` is empty;
- there is no last_kmsg and no DropBox `SYSTEM_LAST_KMSG` or `SYSTEM_SERVER_WATCHDOG` entry;
- the recovery creates `SYSTEM_RESTART`, not a new `SYSTEM_BOOT`;
- init explicitly logs the userspace SurfaceFlinger/zygote restart;
- `shutdown,userrequested` boot-reason properties predate this event and do not establish a reboot.

## Pixel format

`842094169` decimal is `0x32315659`. In little-endian byte order the FourCC characters are `YV12`.
The exact Android definitions are `HAL_PIXEL_FORMAT_YV12 = 842094169` in
`system/core/libsystem/include/system/graphics-base-v1.0.h:32` and
`AHARDWAREBUFFER_FORMAT_YV12 = 0x32315659` in
`frameworks/native/libs/nativewindow/include/vndk/hardware_buffer.h:71-72`.

This nominal format is not by itself the defect: the successful AVC control uses the same nominal
format and the same aligned 1920x1088 geometry.

## Strict H.264 versus HEVC differential

| Field | H.264 PASS | HEVC FAIL | Classification / conclusion |
|---|---|---|---|
| A. Decoder selection | `OMX.allwinner.video.decoder.avc` | Exact decoder name absent | AVC **PROVEN**; HEVC component **NOT OBSERVABLE** |
| B. MediaCodec / OMX | MediaCodec NDK opens; exact OMX component instantiated | VLC activity plus media hardware activity; codec setup logs absent | AVC **PROVEN**; HEVC exact OMX handoff **NOT PROVEN** |
| C. Cedar / VE | CedarC v1.3.0, clock on, VE 696 MHz | Cedar clock on, VE 696 MHz | Both **PROVEN** hardware-media activity; not exact HEVC component proof |
| D. Decoder output dimensions | Port begins 1920x1080, FBM/native output becomes 1920x1088 | Failing AHB and SurfaceView are 1920x1088; decoder port report absent | Shared aligned geometry **PROVEN** at consumer; HEVC decoder contract incomplete |
| E. Crop dimensions | OMX crop 1920x1080 throughout | Not logged | HEVC **NOT OBSERVABLE** |
| F. Native-window dimensions | 1920x1080 then 1920x1088 | SurfaceView 1920x1080 then 1920x1088 around fatal; no `SurfaceUtils` setup line | Nominal sequence similar; exact HEVC native-window allocation **NOT PROVEN** |
| G. Android pixel format | `0x32315659` / YV12 | 842094169 / YV12 in fatal | Same public format **PROVEN** |
| H. Gralloc requested format | Native-window setup explicitly requests YV12 | Fatal AHB reports YV12 but requested format is not separately captured | AVC **PROVEN**; HEVC requested-vs-reported **NOT OBSERVABLE** |
| I. Gralloc internal / allocation format | Not captured | Not captured | **NOT OBSERVABLE**; public YV12 does not disclose `internal_format`/`alloc_format` |
| J. Stride / plane layout | VLC reports luma stride 1920 and visible height 1080; FBM align 32; per-plane offsets/strides absent | No stride or plane metadata | Exact plane differential **NOT OBSERVABLE** |
| K. Combined usage flags | Native-window usage `0x402d00`; includes GPU texture, legacy 2D, composer overlay, external display, and video decoder bits in this gralloc contract | Full mask absent; entry into `mapExternalTextureBuffer` proves GPU-texture/sampleable bit | AVC **PROVEN**; HEVC only GPU sampling **PROVEN**, remaining mask unknown |
| L. Producer usage | Video-decoder bit is present in combined AVC mask; producer/consumer split not dumped | Not dumped | Exact split **NOT OBSERVABLE** |
| M. Consumer usage | Component logs `0x400400`; final combined allocation mask is `0x402d00` | Not dumped; GPU-texture consumption inferred directly from the map guard | Exact split **NOT OBSERVABLE** |
| N. AFBC / modifier | `VeSetEnableAfbcFlag: 0`; HWC sees metadata flag 0 | Not dumped | AVC linear/non-AFBC **PROVEN**; HEVC modifier **NOT OBSERVABLE** |
| O. Private handle metadata | `ion_metadata_flag = 0` observed; `aw_format`, requested/internal/alloc formats and planes not dumped | None dumped | Candidate divergence **NOT OBSERVABLE** |
| P. GraphicBuffer / AHB description | No full `AHardwareBuffer_Desc` dump; native-window public fields are known | Width 1920, height 1088, YV12, non-protected, non-writeable; full usage/stride/layers absent | HEVC public description **PROVEN**, private contract incomplete |
| Q. HWC composition type | `sunxihwc` inspects every video buffer | Fatal precedes any captured video-layer HWC decision | Inspection **PROVEN**; eventual type **NOT OBSERVABLE** |
| R. CLIENT versus DEVICE | Not logged | Not logged; post-restart launcher CLIENT state is unrelated | **NOT OBSERVABLE** for both video runs |
| S. RenderEngine imports video | AOSP eager-map ordering plus AVC `GPU_TEXTURE` usage and absence of fatal strongly support successful import | Backtrace directly proves import attempt | AVC **STRONGLY SUPPORTED**; HEVC **PROVEN** |
| T. EGLImage / GL texture import | Successful Ganesh mapping is strongly supported; lower calls not logged | Ganesh backend invalid; which lower call failed is not logged | Exact EGL/GL delta **NOT PROVEN** |
| U. Mali import result | Same-source mapping survives with paired ARM64 Mali | No valid backend texture is returned; the capture does not prove whether Mali was invoked and rejected the handle or an earlier guard failed | AVC success **STRONGLY SUPPORTED**; exact HEVC Mali result **NOT PROVEN** |
| V. First observable divergence | Valid texture/no fatal, first picture delivered | Invalid texture/SIGABRT before visible playback | **PROVEN** divergence at backend-texture validity; earlier causal field **NOT OBSERVABLE** |

## HWC overlay hypothesis

The proposed explanation—AVC is DEVICE-composed, so Mali RenderEngine never imports its YV12
buffer—is not supported:

1. `SurfaceFlinger::getExternalTextureFromBufferData` constructs a readable
   `renderengine::impl::ExternalTexture` as buffer state is resolved
   (`frameworks/native/services/surfaceflinger/SurfaceFlinger.cpp:8518-8563`).
2. `ExternalTexture` immediately calls `mapExternalTextureBuffer`
   (`frameworks/native/libs/renderengine/ExternalTexture.cpp:25-30`).
3. The threaded Skia engine maps every non-protected buffer carrying
   `GRALLOC_USAGE_HW_TEXTURE` (`SkiaRenderEngine.cpp:417-452`).
4. This happens while processing the incoming transaction, before a later HWC validate/present
   result can establish CLIENT or DEVICE composition.
5. The AVC allocation mask `0x402d00` includes `GPU_TEXTURE` (`0x100`). The donor gralloc explicitly
   defines the legacy decoder mask as GPU texture + composer + external display
   (`hardware/aw/gpu/mali-bifrost/gralloc/src/mali_gralloc_usages.h:244-248`).

Therefore a DEVICE decision could still be the eventual AVC composition type, but it would not
avoid this eager import. `sunxihwc` handle inspection is not proof of DEVICE composition, and the
HEVC import attempt is not proof of CLIENT composition. Neither video composition type was captured.

The better-fitting model is that AVC supplies an importable linear YV12 handle while HEVC supplies a
publicly similar handle with an unobserved contract difference—or encounters an unobserved
lower-level import failure. The evidence cannot yet choose among usage, internal format, planes,
modifier/AFBC, private metadata, or an import-stage state/error.

## Exact AOSP failure trace

The crash matches the exact Android 16 source:

| Stage | Exact source behavior |
|---|---|
| Buffer receipt | `SurfaceFlinger.cpp:5035-5055` resolves buffer changes and obtains an external texture. |
| Eager map | `ExternalTexture.cpp:25-30` calls `mapExternalTextureBuffer`. `RenderEngineThreaded.cpp:178-190` queues it to the RenderEngine thread. |
| Eligibility | `SkiaRenderEngine.cpp:417-452` skips protected/non-sampleable buffers. Reaching the fatal proves this buffer was non-protected and had `GRALLOC_USAGE_HW_TEXTURE`. It calls `makeBackendTexture` with non-writeable/readable use. |
| AHB description | `GaneshBackendTexture.cpp:40-58` calls `AHardwareBuffer_describe`, derives protected state from `desc.usage`, gets a GL backend format from `desc.format`, and passes the AHB plus `desc.width`/`desc.height` to Skia. |
| Public-format mapping | `external/skia/src/gpu/ganesh/gl/AHardwareBufferGL.cpp:33-62` has no explicit YV12 case. With `requireKnownFormat=false` it uses an RGBA8 backend-format placeholder with external-texture semantics. This fallback alone is not an error. |
| EGL/GL import | `AHardwareBufferGL.cpp:113-176` calls `eglGetNativeClientBufferANDROID`, `eglCreateImageKHR(...EGL_NATIVE_BUFFER_ANDROID...)`, `glGenTextures`, `glBindTexture` and `glEGLImageTargetTexture2DOES`. Because `isWriteable=0`, the target is `GL_TEXTURE_EXTERNAL`. |
| Fatal | `GaneshBackendTexture.cpp:72-76` aborts if the resulting `GrBackendTexture` is invalid or dimensions are zero. Width and height are nonzero here, so the backend texture is invalid. |

The fatal message is therefore caused exactly by an invalid `GrBackendTexture`, not merely by the
integer format being YV12. On the active OpenGL path, invalidity can result from an abandoned
context guard, failed EGL image creation, a zero texture name, a `glBindTexture` error, or a
`glEGLImageTargetTexture2DOES` error. Protected-content rejection is excluded by
`isProtected:0`.

No `Could not create EGL image`, `glBindTexture failed`,
`glEGLImageTargetTexture2DOES failed`, EGL error, or GL error attributable to the fatal exists in
the forensic capture. The source's debug messages did not survive into the evidence. Thus no exact
lower GL/EGL operation is proven to have failed.

The AHB fields directly visible to this source are width, height, format and usage/protection.
`eglGetNativeClientBufferANDROID` also transports the underlying native handle, so the Mali driver
can consume private gralloc fields that the fatal does not print: requested/internal/allocation
format, producer/consumer usage, per-plane offsets/strides/allocation dimensions, modifier/AFBC
state, `aw_format`, metadata flags and FDs.

The minimum discriminating logging for one AVC control and one HEVC reproduction is:

- exact selected codec/component, stream profile/bit depth, decoder output and crop;
- the allocation descriptor before and after gralloc format selection;
- full producer and consumer usage masks;
- requested, internal and allocation formats;
- every plane's offset, byte stride and allocation dimensions;
- modifier/AFBC, `aw_format` and `ion_metadata_flag`;
- complete `AHardwareBuffer_Desc` including usage, stride and layers;
- `eglGetNativeClientBufferANDROID` result, `eglCreateImageKHR` result plus `eglGetError`, texture
  name, chosen target/backend format, and `glGetError` after bind and image attachment;
- HWC validate composition type as corroboration, not as a substitute for the import trace.

Suppressing `LOG_ALWAYS_FATAL` would leave an invalid texture and is not a repair.

## ARM64 gralloc / mapper / Mali contract

The exact r7 same-process providers are:

| Runtime provider | Bytes | SHA-256 | Build ID |
|---|---:|---|---|
| `/vendor/lib64/hw/android.hardware.graphics.mapper@2.0-impl-2.1.so` | 36,056 | `d0fc49b3c216441bdea66c015ce17b494523e3eb4d1659de9bba31693c7461e8` | `2f99ba222f5d3eaf2e6217f8b3670537` |
| `/vendor/lib64/hw/gralloc.apollo.so` | 77,248 | `b03bfe24802c73e158a365cb5d15e1bc7598bb73c98def86533183678837cfe7` | `4ea9accdddd3f88f1787aa22de09f009` |
| `/vendor/lib64/egl/libGLES_mali.so` | 18,145,112 | `03333d495e3566c7d85ca2e000da569a16ce8f022ea25c0ea61950c891d5c7f8` | `281008657ed1f606be382d076fe69918` |

The mapper is the exact AOSP passthrough adapter. The gralloc is not a generic AOSP allocator: it is
the pinned Arm/SUNXI gralloc-1.x donor source from the same public provider lineage as the ARM64
Mali blob. The donor's ARM32 Mali is byte-identical to the accepted UBOX10 ARM32 Mali. There is no
evidence that r7 accidentally paired a generic allocator with a vendor Mali requiring a wholly
different handle ABI.

Relevant source contract:

- `format_info.cpp:49-53,116-120` defines YV12 as three-plane, 8-bit, linear and GPU-readable,
  DPU-readable and VPU-readable.
- `mali_gralloc_buffer.h:173-228` carries requested format, separate producer/consumer usage,
  `internal_format`, `alloc_format` and fixed-width plane metadata.
- `mali_gralloc_formats.cpp:1629-1633` selects the SUNXI `AW_WRAP` internal format when the private
  AFBC usage flag is present.
- `mali_gralloc_bufferallocation.cpp:788-903` applies SUNXI YV12 alignment, plane offsets/strides,
  allocation format and `aw_format = 1`. Its comment explicitly says this fixes image creation
  because SurfaceFlinger creates the image in advance and Mali maps the format to a FourCC.

The ARM64 Mali binary contains YV12/multiplane import machinery and diagnostics for private-handle
version mismatches, zero/invalid plane strides or dimensions, invalid offsets, and unsupported
modifiers. This confirms that a public YV12 code alone is insufficient; Mali relies on the private
allocation contract.

The exact conclusion is:

- r7's RGB/UI mapper/gralloc/Mali closure remains physically proven;
- source ordering plus the AVC control strongly supports successful ARM64 Mali import of at least
  the AVC run's linear 8-bit YV12 handle;
- the graphics closure is not proven for every HEVC-specific 10-bit, AFBC, second-FBM, modifier or
  private-metadata variant;
- no captured HEVC handle metadata proves that any such variant was actually used;
- an inherent r7 gralloc/Mali mismatch is therefore **NOT PROVEN**.

## Allwinner media / buffer handoff

Read-only extraction from the exact r7 vendor image found the retained ARM32 media closure:

| Object | SHA-256 | Relevant evidence |
|---|---|---|
| `libOmxVdec.so` | `29f500e3089651c41a4c2a88c1f82b99ee389af7a83101ce929516018d5cea87` | Contains AVC and HEVC component names, native-buffer setup, FBM handoff and AFBC-header query strings |
| `libvdecoder.so` | `ad14bb28db804ed9f939cba39a911132ad8b358c397842e13eed1fdcb6af36ad` | Depends on both `libawh264.so` and `libawh265.so` plus `libVE.so`, `libvideoengine.so` and `libfbm.so` |
| `libawh264.so` | `4c99a97c14adc0397695cf1370fd31715208417a0e5bc14d4c24fc43818f7b16` | AVC backend; runtime control proves AFBC disabled |
| `libawh265.so` | `cc6f2ee2d8a535548a033d1c87ecaaba3677367a4e295c96f06a42a7d8e40823` | Contains HEVC 10-bit, AFBC, lower-2-bit and second-FBM branches |
| `libfbm.so` | `e8977f921254556f6e97525487c34f0d196c0735cd00cd11fb6c1430fa8b81da` | Common frame-buffer manager with AFBC/10-bit/stride handling |

`media_codecs.xml` registers both `OMX.allwinner.video.decoder.avc` and
`OMX.allwinner.video.decoder.hevc`. The common OMX front end and FBM/native-window plumbing support
both, while codec-specific libraries provide distinct decode paths. Binary strings prove that HEVC
*can* select AFBC, 10-bit conversion, lower-two-bit storage or a second FBM; they do not prove the
test did so. The current evidence does not reveal stream profile/bit depth, exact HEVC component,
AFBC state, second-FBM use, output allocator branch, requested/internal format, usages, or plane
layout.

The Android 12 `m8b-audio-r2` control physically passed known HEVC+AAC with HDMI audio, and
`m8b-rc-core-r5` records accepted AVC/HEVC Cedar playback. Those controls used the all-ARM32
graphics path. Prototype A r4 physically passed ARM32 VLC H.264/AAC, but its record does not add an
HEVC differential. None of the historical controls captured video CLIENT/DEVICE type or proved
whether YV12 entered GLES RenderEngine, so they establish retained-stack capability but do not
identify the r7 failure field.

## Secondary quarter-screen recovery defect

This track begins only after SurfaceFlinger death and remains separate from the primary import
fatal.

### Proven observations

- At 06:27:55.694 the restarting display path receives TV mode `0xa`, format `0x1`.
- At 06:28:03.834 it receives TV mode `0x22`, format `0x3`.
- At 06:28:05.013 it reports `type:4,mode:34,fmt:yuv420,bits:8bits`.
- A 06:28:05.004 permissive SELinux audit identifies PID 510,
  `hal_graphics_composer_default`, setting `persist.disp.device_config.hdmi`.
- Post-restart values are:
  `persist.disp.device_config.hdmi=4,34,3,0,4,257`,
  `vendor.sys.disp_config=4,34 - 3,0,257,4`, and
  `vendor.sys.disp_rsl_fex=4,34@`.
- H616 kernel `include/video/sunxi_display2.h:205-227` defines `0xa` as 1920x1080p60 and
  `0x22`/34 as `DISP_TV_MOD_3840_2160P_60HZ`. `hdmi_core.c:59` maps it to
  `HDMI_VIC_3840x2160P60`.
- WindowManager, DisplayManager and SurfaceFlinger continue reporting a 1920x1080 logical,
  physical, layer-stack and framebuffer space with no size override.
- The hash-pinned Android screencap is a normal full 1920x1080 UI, while the user physically
  observed it in the upper-left quarter of the television.

The extracted `libdisplayd.so` (SHA-256
`bbbe2c511dd68dc4224d9bb89b197424206ebd6b8ce5a60379e8712b0337fa89`, Build ID
`44276b294e127f9500ac39d745add28f`) exports
`PersistProperty::read/write`, `PersistAttr<disp_device_config>::save`,
`HdmiDevice::performOptimalMode/performOptimalConfig` and
`HardwareCtrl::setDeviceConfig`; its strings include all three properties and branches for saved
versus optimal HDMI mode. Together with the property-service audit, this strongly assigns mode
read/write/reinitialization ownership to the retained composer/display service. Closed binaries and
the current log do not reveal why its restart path preferred saved/optimal mode 34 at that moment.

A 1920x1080 composition placed unscaled in a 3840x2160 physical timing occupies one-half of each
axis, or one-quarter of the screen area, exactly matching the physical geometry. This makes the
mode/reinitialization explanation **STRONGLY SUPPORTED**, not fully proven: the missing fact is the
exact scaling-programming omission and saved-versus-optimal selection branch. A fresh cold-boot
control was not captured, although the pre-failure AVC control was full-screen.

Post-restart `fb0` reports `virtual_size=1280,1440`, mode `U:1280x720p-0`, stride 5120 and 32 bpp.
Those values conflict with both the modern 1920x1080 SF space and proven 3840x2160 HDMI timing.
Without source showing the modern HWC path consumes this legacy framebuffer metadata, it is not
treated as authoritative or causal.

Classification:

```text
PRIMARY   = HEVC-triggered external-buffer RenderEngine fatal
SECONDARY = display recovery / HDMI mode-and-scaling reinitialization defect
```

No evidence makes them one exact cause.

## Audio causality

SurfaceFlinger receives SIGABRT at 06:27:54.070. The retained ARM32
`android.hardware.audio.service` receives its known null-address SIGSEGV at 06:28:08.572 with
process uptime zero—about 14.5 seconds later, after the framework restart. Therefore:

```text
AUDIO STARTUP CRASH IS NOT THE HEVC FIRST FATAL
```

It remains `KNOWN / UNFIXED / POST-ARCHITECTURE P1` and was not investigated as a repair target.

## Root-cause adjudication

| Required link | Status | Finding |
|---|---|---|
| Trigger | **PROVEN** | HEVC test launch followed by Cedar/VE activation |
| Exact changed contract versus AVC | **NOT PROVEN** | Public geometry/format overlap; hidden usage/format/plane/modifier/private metadata absent |
| Exact failing consumer | **PROVEN** | ARM64 SurfaceFlinger Skia/Ganesh OpenGL RenderEngine |
| Exact observed failure | **PROVEN** | A readable, non-protected, GPU-sampleable 1920x1088 YV12 AHB returns an invalid Ganesh backend texture |
| Exact lower EGL/GL mechanism | **NOT PROVEN** | No discriminating EGL/GL error survived |
| Fatal consequence | **PROVEN** | `LOG_ALWAYS_FATAL` -> SIGABRT -> SurfaceFlinger/zygote/framework restart |

The **first-fatal boundary is PROVEN**, but the full root cause is **NOT PROVEN** because the
required “exact changed contract” and lower import error are missing. The smallest proven contract
failure is:

> A buffer presented to SurfaceFlinger as GPU-texturable cannot satisfy the ARM64
> gralloc/Mali/GLES external-texture import contract.

That statement does not identify which producer field is wrong or whether the producer contract is
valid and the consumer support is incomplete.

## Minimum-fix analysis — no implementation

The next safe boundary is a bounded, control-paired diagnostic reproduction on exact r7 that adds
only the logging listed above. It must capture AVC and HEVC through the same points and stop at the
first lower import error. It is an evidence step, not an r8 repair.

Potential repair classes are ranked conditionally:

| Rank | Conditional repair class | Likely layer/files | Why / architectural fit | Regression boundary |
|---:|---|---|---|---|
| 1 | Correct the HEVC decoder output allocation/usage/format/metadata contract | Retained OMX/Cedar native-window/FBM handoff and the exact gralloc allocation descriptor | Smallest producer-side correction **if** instrumentation proves HEVC alone emits an invalid usage/internal-format/plane/AFBC/private-handle combination | Must leave AVC bytes/behavior and RGB/UI r7 gates unchanged; retest future VP9; proprietary media assumptions likely |
| 2 | Correct the targeted ARM64 gralloc/Mali import contract for the proven HEVC buffer | `hardware/aw/gpu/mali-bifrost/gralloc` and/or the paired ARM64 provider boundary | Appropriate **if** the producer descriptor is valid and a specific Mali-required metadata field or supported layout is missing | Higher graphics risk; preserve AVC linear YV12 and all RGB/UI paths; proprietary Mali behavior involved |
| 3 | Add an explicit YUV-to-importable conversion boundary only for buffers that cannot legally be sampled | Media output adapter/native-window boundary | Valid fallback **if** the decoder output is intentionally overlay-only and a client-readable texture is unavoidable | Bandwidth/latency risk; must not force all AVC/VP9 or UI through conversion |
| 4 | Restore/force HWC DEVICE composition | Retained HWC planner only if paired with a corrected buffer usage contract | DEVICE alone cannot prevent Android 16's eager import, so it is not a standalone causal repair | Could destabilize overlay allocation and does not address the current pre-validation fatal |

No repair boundary is selected yet because ranks 1 and 2 require mutually discriminating evidence.

Explicitly rejected:

- suppressing or downgrading the RenderEngine fatal while retaining an invalid texture;
- forcing all video to software decode;
- replacing the entire graphics stack;
- migrating or replacing the kernel;
- rewriting all vendor HALs or the media/display stack;
- upgrading to an unrelated BSP;
- changing multiple independent subsystems in one candidate;
- merging the quarter-screen recovery work into the primary HEVC experiment without new causal
  evidence.

## Remaining unknowns required before r8 design

1. Exact HEVC decoder/component, stream profile and bit depth.
2. HEVC output crop and the precise allocation moment relative to the fatal.
3. Full AVC-versus-HEVC producer/consumer usage masks.
4. Requested, internal and allocation formats for both paths.
5. Per-plane offsets, byte strides, allocation dimensions, total size and FDs.
6. `aw_format`, `ion_metadata_flag`, AFBC/modifier and second-FBM state.
7. Exact `eglCreateImageKHR`/GL call and error code that makes the HEVC backend invalid.
8. Runtime video composition type, useful only as corroboration.
9. Exact retained display-service branch that selects mode 34 and fails to scale after restart.
10. Cold-boot recovery control for the quarter-screen state.

Until those fields are captured, a single smallest causal correction cannot be chosen while
preserving every r7 gate.
