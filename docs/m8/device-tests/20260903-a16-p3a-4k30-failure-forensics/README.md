# Android 16 P3-A HEVC Main 8-bit SDR 4K30 failure forensics

Status: **P3-A PHYSICAL FAIL / FORENSICS COMPLETE; P3-B MAIN10 NOT AUTHORIZED**.
This is an offline forensic and repair-design record. It does not change Android, build an image,
authorize `compat1b`, authorize Main10, or create `r8`. Canonical r7, closed Gate 3, the closed audio
P1, P2, and compat1a's authorized 1080p result remain unchanged.

## Evidence integrity and scope

The user-supplied archive remains outside Git:

`/work/physical-evidence/ubox10/a16-p3a-4k30/UBOX10-A16-P3-THERMAL-20260903-225409.zip`

Its adjacent manifest verifies the archive as SHA-256
`69c9fdfccd2546a96752dda21af9d969e1a1e8641e3bad309073121354676c78`.
The archive was extracted read-only for analysis under
`/work/tmp/ubox10-p3a-forensics.dlQQqh/UBOX10-A16-P3-THERMAL-20260903-225409`.
The original collector manifest passes **73/73**, and the post-capture `P3A-SHA256SUMS.txt` passes
**89/89**, with zero failures. Thermal discovery/samples, `Post/logcat-all.txt`, both crash windows,
post-crash process state, crash buffer, SurfaceFlinger/audio dumps and tombstone listing are present.
No raw evidence is checked into this repository.

The authorized attempt was one manually started HEVC Main, 8-bit, SDR, 3840x2160p30,
non-HDR/non-protected playback. The evidence bundle does not retain a fixture filename, byte size,
SHA-256 or ffprobe transcript, so those details cannot be independently recovered from the bundle;
the stream contract is the operator-supplied physical-test input, not a new Main10/HDR claim.

## Bottom line

P3-A exposed two distinct 4K blockers:

1. The first decoder instance dies in the ARM32 Allwinner OMX wrapper. Exact machine code loads the
   `OmxDecoder` field at offset `0x58e0`, obtains NULL, and executes
   `ldrd r3, r1, [r0, #0x9c]` before the later `RequestPicture()` call populates that same field.
   The fields are the current display `VideoPicture`'s extended color-aspect inputs. This is a
   real ordering/lifecycle defect in the closed wrapper path, not a Mali crash.
2. A subsequent decoder instance reaches ARM64 SurfaceFlinger with a 3840x2160 YV12 AHardwareBuffer.
   Compat1a cannot activate because both its public and private gates require exact 1920x1088
   geometry. The original vendor view produces an invalid Ganesh backend texture and SurfaceFlinger
   aborts. The fixed-size sidecar ABI makes recurrence of the known Allwinner/Mali metadata collision
   the leading explanation, but the 4K handle/usage/planes/sidecar and exact EGL error were not logged.
   A separate 4K import/format limit therefore remains possible.

The failures share the 4K stimulus but no causal edge is proven between them. The decoder crash
precedes any confirmed 4K SurfaceFlinger import; after init restarts only the OMX service, the formal
playback independently reaches the graphics failure. The repair order is therefore **OMX drain first,
then retest and capture the exact 4K buffer contract, then consider compat1b**. No safe OMX patch is
authorized without the exact matching source or equivalent state evidence.

## Physical timeline

All times are UTC on 2026-09-03. The kernel boot ID remains
`ea8d0b54-0a47-44b5-ad38-f74d4b8b6a15` throughout.

| Time | Event | Evidence / interpretation |
|---|---|---|
| 14:54:03 | Read-only discovery begins | `10-Identity/identity.stdout.txt`; original critical PIDs are zygote64 488, zygote32 489, audio HIDL 500, audioserver 526, SurfaceFlinger 541, system_server 778. |
| 14:54:14–14:55:12 | 24 host-timed samples | CPU 55,061–58,220 m°C, mean 56,181.5 m°C; cooling states remain zero. This interval mostly precedes playback. |
| 14:55:15 | Sampling post snapshot | Same boot ID and all original critical PIDs. |
| 14:55:17.902 | VLC media-library parsing active | `MediaParsingService` starts. The bundle does not identify the exact URI used by this background decoder request. |
| 14:55:19.324 | First Cedar clock enable | PID 589 `enable_cedar_hw_clk`. |
| 14:55:19.407 | Active VE path | `VE real_freq=696000000`. |
| 14:55:19.583890 | OMX drain fault timestamp | ARM32 `media.codec`, PID 589/TID 3045 `drain`, SIGSEGV/SEGV_MAPERR at file PC `0xe138`. |
| 14:55:19.814 | Tombstone printed | `__anDrain(OmxDecoder*)+1212`; exact Build ID `2042d7e0112320dc855cccee324af569`. |
| 14:55:19.854–19.865 | OMX death/restart | init observes signal 11 and restarts `vendor.media.omx` as PID 3049. No framework restart yet. |
| 14:55:24.705 | User input in VLC main UI | Occurs after the background drain crash. |
| 14:55:30.681–31.329 | Formal playback launch | VLC PlaybackService and VideoPlayerActivity start; the player surfaces are created. |
| 14:55:32.034 | Second Cedar/VE instance active | VE again reports 696 MHz. |
| 14:55:32.867 | SurfaceFlinger fatal signal | PID 541 RenderEngine receives SIGABRT. |
| 14:55:32.973806 | SurfaceFlinger tombstone timestamp | Fatal texture is 3840x2160, non-protected, non-writeable, format 842094169/YV12. |
| 14:55:33.264 | SurfaceFlinger tombstone printed | GaneshBackendTexture → GaneshGpuContext → SkiaRenderEngine external-texture map. |
| 14:55:33.371–33.447 | Framework userspace restart begins | init reports SurfaceFlinger signal 6 and restarts zygote; this is not a kernel reboot. |
| 14:55:38.094 | New system_server starts | PID 3273. |
| 14:55:53.571 | Launcher recovery visible in logs | Sample leanback launcher displayed after restart. The 1920x1080 HEVC probe at 14:55:53.630 is recovery activity, not a 4K PASS. |
| 15:45:35 | Final after-crash census | Same boot ID; stable replacement PIDs: zygote32 3113, zygote64 3114, audioserver 3115, SurfaceFlinger 3119, audio HIDL 3121, system_server 3273. |

The first fault is temporally correlated with VLC media-library parsing, before the formal
VideoPlayerActivity launch. It is not safe to call it the formal visible playback itself or identify
its exact URI from these logs. The second attempt is the formal player path.

## RC-A: exact ARM32 OMX drain crash

### Runtime ELF identity

The analyzed file was extracted from the exact `a16-dev-audio-r1` `vendor_a.img` at
`/vendor/lib/libOmxVdec.so`:

| Property | Value |
|---|---|
| Size | 83,780 bytes |
| SHA-256 | `29f500e3089651c41a4c2a88c1f82b99ee389af7a83101ce929516018d5cea87` |
| ELF | ELF32, little-endian, ARM, shared object |
| Build ID | `2042d7e0112320dc855cccee324af569` |
| Dynamic symbol | `__anDrain` is not exported in `.dynsym` |
| Mini-debug symbol | `.gnu_debugdata` identifies `_ZL9__anDrainP10OmxDecoder`, Thumb start `0xdc7d`, size 6,824 bytes; code range `0xdc7c..0xf724` |

This identity exactly matches the physical tombstone. The fault offset is
`0xe138 - 0xdc7c = 0x4bc = 1212` bytes.

### Exact instruction and object

The decisive instructions are:

```text
e120  movw  r0, #0x58e0
e124  add.w r8, r4, r0
e130  ldr.w r0, [r8]             ; *(OmxDecoder + 0x58e0)
e134  mov.w r12, #0x0c
e138  ldrd  r3, r1, [r0, #0x9c] ; fault: r0 == NULL
e13c  ldr.w r2, [r0, #0xa4]
e140  ldrb.w r5, [r0, #0xa8]
e150  bl    adapteColorAspects(...)
```

The crash registers independently prove the base calculation:
`r4=0xeded1440`, `r8=0xeded6d20`, and `r4+0x58e0=r8`; `[r8]` is NULL and the
faulting load dereferences it. The zero `r0` is therefore the directly dereferenced object, not merely
an unrelated function argument.

Exact control-flow facts identify the object and ordering:

- Earlier, `NextPictureInfo(decoder, 0)` returns a non-NULL pointer, checked at `0xddaa`; the wrapper
  safely reads that object's same `+0x9c..+0xa8` color-aspect fields and calls
  `adapteColorAspects`.
- The wrapper then computes visible dimensions from the picture prefix fields at
  `+0x18..+0x24`, compares geometry/alignment/output state, and reaches the faulty second
  color-aspect block.
- Only later, at `0xe426`, it calls `RequestPicture(decoder, 0)`, stores the return value into
  `OmxDecoder+0x58e0` at `0xe42c`, and explicitly checks that slot for NULL at `0xe460`.
- `__anReturnBuffer` loads the same slot, calls `ReturnPicture(decoder, picture)` when non-NULL, and
  clears it. Binary strings call the object `pPicture`, including the existing later diagnostic
  "the pPicture is null when request displayer picture".

The public Allwinner `VideoPicture`/FBM API is only source-correlated, not the exact vendor source.
Its older prefix maps `+0x18/+0x1c/+0x20/+0x24` to top/left/bottom/right and defines
`NextPictureInfo`, `RequestPicture`, and `ReturnPicture`, matching the exact binary call pattern.
The newer color-aspect extension at `+0x9c..+0xa8` is established by binary dataflow into
`adapteColorAspects`, not by that older header.

### 1080p differential and causality

The exact 1080p Allwinner HEVC path physically passes, while this 4K attempt enters a geometry/
color-aspect branch that dereferences the not-yet-acquired current-picture slot. The binary proves a
peekable FBM picture existed (`NextPictureInfo != NULL`) but does not prove a FillBufferDone reached
ACodec before the crash. No first-instance port-settings-change, SPS, output-count, stride, or FBD
records survived in the log window. Consequently:

- fixed 1080-sized array, memory exhaustion, integer overflow, and allocation failure are not proven;
- a NULL `ANativeWindow`, output header, GraphicBuffer, or metadata pointer is contradicted by the
  fault dataflow—the direct NULL object is the `VideoPicture*` slot;
- exactly why 4K activates this ordering/state combination, and whether the correct source fix is to
  use the already-peeked picture or defer the update until after `RequestPicture`, remains unproven.

**ROOT CAUSE:** the closed ARM32 OMX wrapper dereferences its current display `VideoPicture*` field at
`OmxDecoder+0x58e0` in a pre-acquisition color-aspect/geometry path; the field is NULL, and
`ldrd [r0,#0x9c]` faults before the later guarded `RequestPicture` assignment.

**EVIDENCE:** exact candidate ELF identity, mini-debug symbol range, physical registers, instruction
dataflow, and the later store/null-check plus return/clear lifecycle for the same slot.

**CONFIDENCE:** high for the exact faulting object and bad ordering; medium for the 4K-specific
state trigger and intended source-level correction.

**REMAINING UNCERTAINTY:** exact matching wrapper source is unavailable; the proper state-machine
action—use peeked picture, defer color-aspect evaluation, wait for port reconfiguration, or return an
OMX error—cannot be selected safely from this binary alone.

### Narrow codec repair boundary

The eventual repair class should be **source-level lifecycle/state ordering (with a null-safe guard),
not a blind binary guard**. The target is the `__anDrain` block corresponding to `0xe120..0xe150` in
the exact wrapper generation. Correct behavior must preserve FBM ownership, port-settings events,
FBD ordering and `ReturnPicture`; simply dropping a frame, retrying, or skipping state transitions
could leak a picture or deadlock OMX.

Until matching source is obtained or an observation-only reconstruction establishes the intended
branch semantics, binary patching/interposition is **HOLD**. A future diagnostic should record the
peeked picture, current slot, geometry comparison, port-reconfiguration state, and subsequent
RequestPicture outcome around this block. It must not turn a NULL guard into silent state corruption.

## RC-B: 3840x2160 YV12 RenderEngine import crash

The exact physical fatal is:

```text
Failed to create a valid texture. [3840,2160]
isProtected:0 isWriteable:0 format:842094169
```

`842094169 == 0x32315659 == YV12`. The ARM64 stack is
`GaneshBackendTexture(AHardwareBuffer*)` → `GaneshGpuContext::makeBackendTexture` →
`SkiaRenderEngine::mapExternalTextureBuffer`; the invalid backend causes the retained fatal and
SurfaceFlinger SIGABRT. The P3-A log does not contain a 4K `EGL_CREATE_IMAGE` marker, EGL error code,
`Crop rectangle...` line, or 4K `UBOX_R7_DIAG3/COMPAT1` private-state records. It therefore proves the
invalid texture boundary, but not the exact failing EGL call/error for this 4K buffer.

### Why compat1a does not apply

The actual compat1a helper first requires all of:

- public 1920x1088, one layer, stride 1920, YV12, usage `0x402d00`, non-protected;
- 2-fd/53-int Allwinner handle, exact 1920x1088 private geometry, exact three-plane offsets/sizes,
  YV12 allocation format and non-AFBC usage;
- 0x6000 metadata fd and the proven SDR active-attribute/collision values.

The helper is called for YV12 buffers at least 1280x720, but a 3840x2160 descriptor necessarily
fails the public width/height requirements before sidecar translation; its private dimension/plane
requirements cannot match either. The helper returns NULL and `make_gl_backend_texture` selects
`view=original`. No shadow sidecar can be created for this buffer regardless of its unknown stride or
usage. This is source-control-flow proof, even though the corresponding info marker is absent from
the capture.

### What is known and what is projected

| Field | Physical evidence | Source projection (not physical proof) |
|---|---|---|
| Logical width/height | 3840x2160 | same |
| Format | YV12 / `0x32315659` | retained gralloc supports linear YV12 |
| Protected/writeable | 0 / 0 | compat1b must require non-protected |
| AHardwareBuffer | reached GaneshBackendTexture | original view is used |
| Stride / private dimensions | not logged | for linear decoder YV12, width/height are already 16-aligned: luma stride 3840, chroma stride 1920 |
| Planes | not logged | Y: offset 0, 3840x2160; V: offset 8,294,400, 1920x1080; U: offset 10,368,000, 1920x1080 |
| Total allocation | not logged | 12,441,600 plane bytes plus source's 64-byte VE burst tail = 12,441,664 bytes |
| Usage / producer / consumer | not logged | must not be assumed to equal the 1080p `0x402d00` / `0x400900` values |
| AFBC / modifier / handle slots | not logged | linear/non-AFBC was intended by the test, but must be confirmed before a guard expands |
| Sidecar size/state | not logged | active gralloc allocates `ALIGN(sizeof(sunxi_metadata)+64+sizeof(attr_region), PAGE_SIZE)` = fixed 0x6000, independent of resolution |

The source-projected geometry follows `SUNXI_YUV_PLANE_ALIGN=16`, the explicit YV12 plane setup and
the unconditional 64-byte video-decoder allocation tail. It is not a substitute for actual
`GRALLOC_ALLOC/GRALLOC_HANDLE/AHB_DESC/EGL_PREIMPORT` records.

### Metadata ABI collision assessment

The layout itself is resolution-independent:

| fd2 range | Active Allwinner meaning | Mali r20p0 legacy interpretation |
|---:|---|---|
| `0x80..0x8f` | HDR10+ `divLut[0][3..6]` | signed crop top/left/height/width |
| `0x90` | later extended metadata | use YUV transform |
| `0x94` | later extended metadata | sparse allocation |
| `0x98..0xb3` | later extended metadata | 28-byte legacy HDR info |
| `0xb4` | later extended metadata | dataspace |
| `0..23479` | complete extended `sunxi_metadata` | Mali expects its legacy attr near the beginning |
| `23544..23599` | active 56-byte attr region | not where r20p0 reads it |

At 1080p, HEVC initializes extended metadata, making `0x80..0x8c` non-negative LUT values; Mali
misreads them as an invalid crop and returns `EGL_BAD_ALLOC`. Compat1a physically proves that copying
all 56 active attr bytes from 23544 to `0x80` in an isolated shadow makes that path import correctly.

For 4K, the fixed ABI and bypassed translation make the **same collision the leading mechanism**.
However, this capture does not show the actual four legacy words, active attr, `sunxi_flag`, EGL error,
usage, AFBC state or planes. Mali may also have a separate 4K YV12 stride/size/import limitation.
The defensible classification is therefore **C — BOTH POSSIBLE**, with medium confidence and the
known metadata collision ranked first. It is not yet a physical proof of the 4K collision.

**ROOT CAUSE:** a 3840x2160 YV12 AHardwareBuffer follows compat1a's untranslated original-view path
and Mali/Skia returns an invalid backend texture; the retained fatal then aborts SurfaceFlinger.
The most likely lower cause is recurrence of the fixed-layout Allwinner/Mali metadata ABI collision,
but a distinct 4K import limit is not excluded.

**EVIDENCE:** exact compat1a predicate/control flow, physical dimensions/format/protection state,
Ganesh/Skia stack, and the previously proven resolution-independent sidecar mismatch.

**CONFIDENCE:** high for compat1a bypass and the invalid-texture/SF chain; medium for attributing the
4K invalid texture specifically to metadata rather than another 4K import constraint.

**REMAINING UNCERTAINTY:** exact 4K usage, stride, planes, allocation size, handle fields, AFBC/
modifier, sidecar values and first EGL error operation.

## Failure matrix

| Layer | Physical status | Evidence | Failure? | Confidence |
|---|---|---|---|---|
| BITSTREAM | PASS | Operator-authorized Main 8-bit SDR 4K30 input reaches two hardware attempts | No rejection observed | Medium; fixture hash/probe absent |
| OMX COMPONENT SELECT | PASS | ARM32 vendor OMX service and HEVC/Cedar lineage; later recovery log names `OMX.allwinner.video.decoder.hevc` | No | Medium for first-instance exact component log |
| OMX CONFIG | PARTIAL | Cedar starts; first-instance port/config records absent | Possible state-path issue | Medium |
| CEDAR/VE INIT | PASS | two clock activations, VE 696 MHz at 14:55:19.407 and 14:55:32.034 | No | High |
| CEDAR DECODE | PARTIAL | exact drain path has `NextPictureInfo != NULL`; second attempt delivers a video buffer to SF, but no explicit 4K FBD marker | Not the demonstrated fatal | Medium-high |
| OMX DRAIN | FAIL | ARM32 SIGSEGV at `__anDrain+1212` | Yes, first fatal | High |
| OUTPUT BUFFER FORMAT | PASS | SF fatal identifies 3840x2160 YV12 | No format negotiation rejection | High |
| BUFFER ALLOCATION | PARTIAL | at least one 4K AHardwareBuffer exists; exact geometry/size/count unavailable | No allocation fatal proven | Medium |
| GRALLOC / MAPPER | PARTIAL | buffer reaches SF; no exact 4K handle/import record | Could contribute to EGL failure | Medium-low |
| AHARDWAREBUFFER | PASS | object reaches GaneshBackendTexture with correct public dimensions/format | No null object | High |
| SKIA / EGL | FAIL | invalid Ganesh backend texture; exact EGL operation/error not captured | Yes | High for boundary |
| HWC | NOT ESTABLISHED | eager RenderEngine import fails before final composition decision | Unknown | High |
| SURFACEFLINGER | FAIL | RenderEngine SIGABRT and init restart | Yes | High |
| HDMI / VISIBLE | NOT ESTABLISHED | no stable, correct full-frame 4K playback result; launcher later recovers | Not separately isolated | High |
| AUDIO | NOT ESTABLISHED | playback audio result is not preserved as a PASS; audio services are recreated after SF restart | Not primary | Medium |
| THERMAL | PARTIAL | discovery/baseline plausible; samples mostly pre-playback | Not supported as cause | High |
| SYSTEM CONTINUITY | FAIL | same kernel boot ID but framework/audio PIDs replaced | Userspace restart | High |

## Repair designs and order

### Codec boundary

Do not ship a raw `cbz` around `0xe138`. The minimally correct source repair must keep the current
picture lifecycle coherent: either consume the already validated `NextPictureInfo` for the
color-aspect comparison or defer that comparison until after the mutex-protected `RequestPicture`
and its existing NULL check. Which is correct depends on the missing exact source/state machine.
Returning, dropping, retrying, or emitting `OMX_ErrorHardware` without that proof can strand FBM/
output buffers or corrupt port reconfiguration.

The next codec step is therefore source recovery or a narrowly instrumented reconstruction of this
one branch—not an image in this task. If exact source cannot be recovered, a binary shim/patch remains
unsafe and the codec repair is classified **unsupported without matching source**.

### Compat1b concept (design only)

Compat1b may reuse the physically proven compat1a shadow algorithm only after a subsequent run records
the real 4K contract. Its eligibility gate must require:

- exact 3840x2160 Main 8-bit SDR output and one layer;
- exact physically observed YV12 format, public/private stride, allocation dimensions, plane offsets,
  plane sizes, total size, producer usage and consumer usage;
- exact 2-fd/53-int Allwinner handle ABI and YV12 allocation format;
- non-AFBC/modifier-free, non-protected, non-HDR and no 10-bit/P010/private format;
- fd2 exactly 0x6000 with the same active layout, `sunxi_flag`, active SDR attr values and a proven
  non-negative legacy collision.

Unknown numeric values must not be filled from the source projection. When those predicates are
proven, the minimal code delta is to add a second exact contract branch to the existing compat1a
eligibility calculation. The translation itself remains byte-for-byte the same: create one 24,576-byte
sealed memfd per imported buffer/cache miss, copy the full sidecar, copy 56 bytes from 23544 to
`0x80`, clone only fd2, and retain all ownership/fail-closed behavior. Metadata size does not grow
with 4K; the extra memory is 24 KiB per translated buffer, not a copy of the 12.4 MiB pixel planes.
Plane fields stay in the cloned handle and must not be translated.

### Recommended order

**ORDER 1: repair the OMX drain state/lifecycle first, retest once, then decide compat1b from the newly
captured 4K contract.** This honors the earliest independent fatal and one-variable-at-a-time policy.
A graphics-first candidate would knowingly leave an ARM32 codec-service SIGSEGV. A combined candidate
would obscure whether the drain correction changes which frame/metadata reaches SurfaceFlinger.
Implementation remains HOLD until the codec source semantics above are established.

The future bounded retest should capture the exact OMX pre-peek/current-slot/request/FBD sequence and
all existing gralloc/handle/AHB/compat/EGL markers, then stop at the first failure. If drain is stable,
the observed 4K handle contract decides whether the existing shadow is safely extensible. No Main10,
HDR, AFBC, protected playback, loop, soak, or automatic retry belongs in that test.

## Thermal classification

- **THERMAL DISCOVERY: PASS.** Four plausible CPU/DDR/GPU/VE zones, CPU trips 70/90/115°C, CPUfreq,
  GPU devfreq and cooling states are readable.
- **THERMAL BASELINE: PLAUSIBLE.** CPU range 55.061–58.220°C, average 56.1815°C.
- **UNDER-LOAD THERMAL QUALIFICATION: NOT ESTABLISHED.** The 60-second sampler ended before the
  decisive formal playback failure and overlapped neither failure adequately.
- **THERMAL AS CAUSE OF CURRENT CRASH: NOT SUPPORTED.** The exact failures are a NULL dereference and
  an invalid texture import; no trip, cooling-state transition or thermal warning is recorded.

## Governance and preserved scope

- P3-A: **PHYSICAL FAIL / FORENSICS COMPLETE**.
- P3-B Main10: **NOT AUTHORIZED**.
- Compat1a: **PHYSICAL PASS only for authorized SDR 1080p YV12 / unchanged**.
- Canonical r7: **PASS / FROZEN / unchanged**.
- Gate 3: **`PASS_WITH_EXPLICIT_USER_WAIVER` / CLOSED**.
- Audio startup P1: **CLOSED**; this P3 media failure does not reopen it.
- P2: **COMPLETE**.
- Full VINTF remains inherited exit 65 for `CONFIG_NFS_FS=y` versus FCM-6 `n`; NOT PASS.
- Main10/HDR/AFBC/protected playback remain untested and unauthorized.
- `r8`: **NOT AUTHORIZED / NOT BUILT**.

No physical retest, ADB/device action, Android build, candidate creation, runtime/vendor/kernel repair,
SELinux change, or image change was performed by this forensic closure.
