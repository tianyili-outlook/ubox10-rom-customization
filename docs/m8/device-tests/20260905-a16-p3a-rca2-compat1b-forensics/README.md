# P3-A RC-A2 / RC-B parallel forensics

Date: 2026-09-05

Status: **P3-A PHYSICAL FAIL / PARALLEL FORENSICS COMPLETE**

This report separates two events observed on `a16-dev-p3a-omx-r1`. Incident A is a VLC
medialibrary preparse teardown crash in the ARM32 decoder service. Incident B is the later formal
manual 4K playback and its SurfaceFlinger import crash. They do not share a process, allocation or
failure instruction and must not be merged.

No device command or physical retest was run for this analysis. No Android image was built and no
runtime, proprietary ELF, kernel, SELinux, RC-A2 or compat1b change was made.

## Evidence integrity and scope

The read-only input is external to Git:

```text
/work/physical-evidence/ubox10/a16-p3a-omx-r1/
  UBOX10-A16-P3A-OMX-R1-20260905-001143.zip
```

| Check | Result |
|---|---|
| Outer SHA-256 | `62ce8f1623bbc4569a14f2c90bb5e9011657ee6765781e93e30b317d4e6f7921` — PASS against adjacent `.sha256` |
| Internal manifest | `P3A-OMX-R1-SHA256SUMS.txt`: **7/7 PASS, 0 FAIL** |
| Read-only extraction | `/work/tmp/ubox-p3a-rca2-compat1b-z3qmdR/UBOX10-A16-P3A-OMX-R1-20260905-001143` |
| Boot ID | `38bac882-1c49-478a-8fcd-5379879b092f`, unchanged across formal graphics restart |

The fixture name in the log is `ubox10-hevc-main8-sdr-3840x2160p30-aac.mp4`. This archive still
does not independently retain the fixture bytes/hash/ffprobe transcript, so its codec properties
remain bounded by the captured runtime identification and the operator's controlled-test record.

## Two independent incidents

| Incident | Time | Process | Boundary | Result |
|---|---|---|---|---|
| A — medialibrary preparse | 16:06:57.739–16:06:59.233 | `media.codec`, PID 596 | FBM teardown | Scudo SIGABRT; service restarts as PID 2503 |
| B — formal manual playback | 16:13:12.732–16:13:15 | `surfaceflinger`, PID 541 | Mali EGL import | EGL_BAD_ALLOC / RenderEngine SIGABRT; media.codec PID 2503 survives |

The original `__anDrain` NULL crash does not recur in either event. In the formal attempt the
patched decoder reaches FBD and SurfaceFlinger, so the original RC-A operand repair is physically
effective for that path. This does not make the overall OMX path or P3-A pass because RC-A2 exists.

## RC-A2 — exact preparse teardown timeline

| UTC timestamp | Event |
|---|---|
| 16:06:57.739 | VLC medialibrary `ParserWorker` starts a preparse task for the 4K fixture. |
| 16:06:58.509 | PID 596 creates `OMX.allwinner.video.decoder.hevc`. |
| 16:06:58.556 | OMX copy path configures 3840x2160 YV12, changes output size to 12,441,600 and reports native-buffer extensions unsupported. |
| 16:06:58.594 | `CreateVideoDecoder(0xe8085fb0)`; CedarC v1.3.0, commit string `3b65bf7287aea23c2abfbc626c3f606e3b9def1c`. |
| 16:06:58.596–.600 | Stream identified as 8-bit; VE enters the hardware path at 696 MHz. |
| 16:06:58.610 | HEVC selects AFBC for the >=4K internal path and requests 10 FBM pictures at 3840x2160. |
| 16:06:58.611–.723 | `FbmAllocatePictureBuffer` allocates ten internal pictures (`bEnableAfbcFlag=1`). |
| 16:06:58.729 | Internal FBM creation completes. |
| 16:06:58.745 | `TransformYV12ToYUV420`: real 3840x2160, internal source 3840x2176, destination 3840x2160. |
| 16:06:58.930 | VLC/MediaCodec teardown requests OMX **Executing -> Idle**; a final copy is in flight. |
| 16:06:58.941–.956 | Drain, decode and submit threads are suspended in that order. |
| 16:06:58.956 | `__anClose` calls `DestroyVideoDecoder`. |
| 16:06:58.961 | Scudo detects a zero/corrupt chunk header at `0xe7dc30a0`. |
| 16:06:58.973 | ARM32 PID 596 / TID 2494 aborts in `FbmFreePictureBuffer`. |
| 16:06:59.223–.233 | init records signal 6 and restarts `vendor.media.omx` as PID 2503. |

The close is therefore the normal end/cancellation of VLC preparsing expressed as an OMX
Executing-to-Idle transition. It is not a drain-thread fault, port-disable crash or formal playback
event.

## Exact runtime ELF closure

All objects below were extracted from the exact candidate `vendor_a.img`; all are ELF32 ARM.

| Runtime object | Size | SHA-256 | Build ID | Relevant location |
|---|---:|---|---|---|
| `/vendor/lib/libOmxVdec.so` | 83,780 | `5fe74a28eb9e083959fdac9cfde870faa2af4447dadb7776c1e7f4cfc6d1ee8b` | `2042d7e0112320dc855cccee324af569` | `__anClose+108` / `0xd3b5` |
| `/vendor/lib/libvdecoder.so` | 36,956 | `ad14bb28db804ed9f939cba39a911132ad8b358c397842e13eed1fdcb6af36ad` | `d689bc889a8425e7d092ac117aaa0608` | `DestroyVideoDecoder+52` / `0x5261` |
| `/vendor/lib/libvideoengine.so` | 16,572 | `1c40c0079847c79bbae8fc8f6d1208522572c7a66fe52d131f824acf0d285d15` | `b8fd7d725a38e3b9c505df9427ef8c7e` | `VideoEngineDestroy+232` / `0x337d` |
| `/vendor/lib/libawh265.so` | 127,272 | `cc6f2ee2d8a535548a033d1c87ecaaba3677367a4e295c96f06a42a7d8e40823` | `3701f119be0076252e2b5d82c48687d9` | `HevcDecDestroy+220` / `0xdbbd`; `HevcSetNewRef` `0x188a5` |
| `/vendor/lib/libfbm.so` | 20,980 | `e8977f921254556f6e97525487c34f0d196c0735cd00cd11fb6c1430fa8b81da` | `dcbeaa9e1d25cc5ff2a33c5d314894c2` | `FbmFreePictureBuffer+34` / `0x3a93`; `FbmDestroy+184` / `0x3c85` |

The exact teardown stack is:

```text
__anClose -> DestroyVideoDecoder -> VideoEngineDestroy -> libawh265 Destroy
          -> HevcDecDestroy -> FbmDestroy -> FbmFreePictureBuffer
          -> scudo_free -> SIGABRT
```

## RC-A2 — object and ownership reconstruction

### Exact binary facts

`FbmAllocatePictureBuffer` contains this internal-picture allocation sequence:

```text
0x3934  mov.w r0, #0x1000       ; 4,096 bytes
0x3942  blx   cdc_malloc
0x3948  str.w r0, [picture,#0x98]
```

`VideoPicture+0x98` is `pMetaData`. `FbmFreePictureBuffer` later does:

```text
0x3a88  ldr.w r0, [picture,#0x98]
0x3a8c  cbz   r0, ...
0x3a8e  ldr   r1, [fbm,#0x28]   ; bUseGpuBuf
0x3a90  cbnz  r1, ...
0x3a92  blx   cdc_free          ; crash return PC 0x3a93
0x3a98  str.w 0, [picture,#0x98]
```

Thus the pointer handed to Scudo is the FBM-owned heap `pMetaData`, not image data, an fd-backed
gralloc sidecar, a `VideoPicture` object, a plane pointer or an interior pointer. The crash address
reported by Scudo is `0xe7dc30a0`. The archive does not identify the owning frame index or expose
the corresponding `VideoPicture*`; those values must not be invented.

The exact `libawh265.so::HevcSetNewRef` binary loads the same `VideoPicture+0x98` field. It uses the
constant `0x5bb8` (23,480) for both initialization and the final copy into that pointer:

```text
0x191de  ldr.w r0, [picture,#0x98]
0x191e6  movw  r1, #0x5bb8
          ... zero 23,480 bytes ...
0x192a8  movw  r2, #0x5bb8
0x192ac  ldr.w r0, [picture,#0x98]
          ... copy 23,480 bytes ...
```

The writer therefore exceeds the FBM allocation by **19,384 bytes**. Scudo reports the damage only
when the first owned metadata pointer is freed; the failure is not proof that the pointer was freed
twice.

### Source archaeology

| Source | Commit | Match class | Relevance |
|---|---|---|---|
| `https://github.com/jeasonzs/tina_multimedia.git` | `63344eadfbab18195046678079d2f3d32d0c61cc` | **NEAR-EXACT SAME OWNERSHIP MODEL** | `fbm.c` has the matching runtime log strings/line lineage, allocates `malloc(4*1024)` into `pMetaData`, frees it only for `bUseGpuBuf==0`, and models internal vs external FBM. |
| `https://github.com/aodzip/libcedarc.git` | `e4246be521203adb2d93d52482239044a7f9b6fe` | OLDER RELATED | Matching Android OMX copy/transform family, but no matching FBM implementation in this tree. |
| `https://github.com/CalvinXu17/libcedarc.git` | `e68d4a727085d02d4622d85b5234304349d4e448` | OLDER RELATED | Related `TransformYV12ToYUV420` / AFBC-control wrapper generation. |
| `https://github.com/rhodesepass/libcedarx.git` | `92a060decd558cf7368c9df4fbfc472d22169fad` | OLDER RELATED | Playback-side `ENABLE_AFBC_JUST_BIG_SIZE`, not the exact FBM implementation. |
| `https://github.com/lineageos-on-allwinner/android_hardware_aw.git` | `4b3faf7253da69b6084ad0f9a07d89948ef6d466` | NEAR-EXACT GRALLOC/METADATA GENERATION | Correlates the 24 KiB sidecar ABI and 4K AFBC-big-buffer allocation, not the proprietary HEVC teardown. |

The Tina source sets `bUseGpuBuf=0` for internally allocated pictures, makes FBM their owner, and
calls `FbmFreePictureBuffer` for each frame during `FbmDestroy`. External GPU/native buffers use the
other ownership branch and are not heap-freed here. Its structure offsets and logs correlate with
the exact binary, while compiler/library substitutions and absent exact HEVC source prevent calling
the entire drop exact.

### Ownership verdict

The supported classification is **C — HEAP HEADER OVERWRITTEN BEFORE FIRST FREE**, caused by a
metadata-capacity ABI mismatch:

```text
internal FBM picture
  -> FBM owns cdc_malloc(0x1000) pMetaData
  -> HEVC owns metadata content and writes/copies 0x5bb8 bytes
  -> adjacent Scudo heap metadata/chunks are overwritten
  -> normal FbmDestroy first exposes the damage at cdc_free(pMetaData)
```

There is no address trace proving same-pointer double-free, no evidence that the pointer is an
interior pointer, and no ownership transfer to gralloc. `TransformYV12ToYUV420` copies picture pixels
into the OMX output destination; it does not transfer ownership of `pMetaData`.

The original RC-A patch cannot cause this chain. It changes only one read operand
(`ldr.w r0,[r8]` -> `mov.w r0,r12`) before color-aspect reads, adds no store/branch/call and leaves
FBM allocation, `RequestPicture`, `ReturnPicture`, close and free counts byte-identical.

### RC-A2 repair readiness

Classification: **READY_FOR_NARROW_BINARY_PATCH** (high confidence).

The semantically correct repair is to make the internal FBM allocation satisfy the active extended
metadata ABI while retaining FBM ownership and its existing single free:

```text
before: pPicture->pMetaData = cdc_malloc(0x1000)
after:  pPicture->pMetaData = cdc_malloc(0x6000)
```

`0x6000` is the active allocation contract already used by the gralloc sidecar; it covers the exact
23,480-byte `sunxi_metadata` write with bounded spare capacity. A future guarded patcher should
require the exact `libfbm.so` SHA/size/bytes and alter the allocation immediate at `0x3934`; the
associated failure-log size immediate at `0x3980` may be changed in the same instruction-local patch
only to keep diagnostics truthful. It must not skip the free, change ownership, suppress Scudo or
touch image planes. The resulting lifecycle remains allocate once -> write -> free once, so it does
not leak and does not affect external `bUseGpuBuf=1` buffers. This is an internal-copy-path metadata
capacity correction, not a claim of general 4K/Main10/HDR support.

## RC-B — formal 4K buffer populations

The formal manual action begins at 16:13:12.732. `OMX.allwinner.video.decoder.hevc` configures
3840x2160 YV12 and first allocates eight ordinary linear buffers. After HEVC parses the stream, its
>=4K mode requests AFBC-big-buffer usage and a 14-buffer output-port population replaces them.

| Population | Buffer IDs / backing stores | Usage and metadata | Size | Role |
|---|---|---|---:|---|
| Initial | `9891309682700..2707` / `2229088026696..6703` | handle `0x400900`; private usage 0; metadata flag 0 | 12,441,664 | Pre-port-change population; never reaches the fatal EGL import |
| Replacement | `9891309682708..2721` / `2229088026704..6717` | AHB `0x40402d00`; handle `0x40400900`; private `0x40000000`; metadata flag `0x80000010` | 19,489,120 | Post-port-change, decoder-registered population; one buffer reaches FBD/SF/EGL |

These are different buffer populations, not handles mutated from 12.44 MB to 19.49 MB. The source
formula for the replacement reservation is:

```text
((3840+15)>>4) * ((2160*3/2+4+15)>>4) * (384+16) + 32 + 1024 + 64
= 19,489,120
```

The last 64 bytes are the VE burst allowance. The exact gralloc source sets
`GRALLOC_USAGE_AFBC_MODE` and `SUNXI_METADATA_FLAG_AFBC_HEADER | AFBC_BIG_BUFFER` for this path while
still exporting YV12, `internal_format=0`, `modifier=0` and diagnostic `afbc=0`. This is an
Allwinner auto-AFBC-big backing reservation hidden behind a linear-looking public YV12 contract; it
does not authorize general AFBC testing. `second_fbm` is not represented in this handle and is not
needed to explain the two populations.

## Exact fatal buffer lineage

The first replacement buffer is the fatal one:

```text
buffer_id       = 9891309682708
backing_store_id= 2229088026704
image inode     = 15952
metadata inode  = 15953
```

| Boundary / time | Exact evidence |
|---|---|
| ALLOC_INITIAL 16:13:13.508 | 32-bit gralloc allocates the replacement handle and two fds. |
| REMOTE_IMPORT 16:13:13.523 | ARM64 VLC imports the same backing store/inodes. |
| CODEC_PRE_USE 16:13:13.538–.557 | ACodec assigns buffer ID `9891309682708`; sidecar still initial. |
| ARM32 REMOTE_IMPORT 16:13:13.558 | PID 2503 imports the same handle. |
| BUFFER_REGISTER 16:13:13.574 | OMX buffer ID 11, 3840x2160 YV12, AHB usage `0x40402d00`. |
| FBM registration 16:13:14.226 | `SetVideoFbmBufAddress` registers the first replacement picture/fd. |
| CODEC_POST_FBD 16:13:14.237–.250 | Same buffer/backing store/inodes; HEVC sidecar initialized. |
| SF REMOTE_IMPORT / EGL_PREIMPORT 16:13:14.253–.279 | Same backing store/inodes; exact handle and sidecar state retained. |
| EGL 16:13:14.279–.283 | compat1 ineligible -> original view -> crop mismatch -> EGL_BAD_ALLOC -> invalid backend texture -> SIGABRT. |

Exact fatal handle at EGL import:

| Field | Value |
|---|---|
| Handle ABI | version 12; 2 fds; 53 ints; magic `0x03141592`; ION flags `0x4` |
| Logical/allocation geometry | 3840x2160; stride 3840; one layer |
| Requested/allocation format | `842094169 == 0x32315659 == YV12`; `internal_format=0`; `modifier=0` |
| AHB usage | `0x40402d00` |
| Producer/consumer handle usage | both `0x40400900`; private component `0x40000000` |
| Plane 0 | offset 0; stride 3840; 3840x2160; 8,294,400 bytes |
| Plane 1 | offset 8,294,400; stride 1920; 1920x1080; 2,073,600 bytes |
| Plane 2 | offset 10,368,000; stride 1920; 1920x1080; 2,073,600 bytes |
| Handle total / image fd | 19,489,120 / 19,492,864 bytes (page-rounded fd) |
| Metadata fd | 24,576 (`0x6000`) bytes |
| Handle metadata flag | `0x80000010` (`AFBC_BIG_BUFFER | AFBC_HEADER`) |
| `sunxi_metadata.flag` after FBD | `0x00000010` (`AFBC_HEADER`) |
| YUV info | 3 |

The active 56-byte attr at 23,544 is byte-stable from allocation through EGL: crop and the two
controls are `-1`, dataspace is `0x10010000`. The decoder changes 5,871 words in the extended
metadata; its full hash becomes `0x45e57b8488e57106`, while the gap and active attr hashes remain
unchanged.

## RC-B metadata ABI comparison

| Offset | Active Allwinner meaning | Old Mali r20p0 meaning |
|---:|---|---|
| `0x80..0x8f` | `hdr10_plus_metadata.divLut` words | crop top/left/height/width |
| `0x90` | more extended HDR10+ data | YUV transform |
| `0x94` | more extended HDR10+ data | sparse allocation |
| `0x98..0xb3` | more extended HDR10+ data | legacy HDR info |
| `0xb4` | more extended metadata data | dataspace |
| `0..23479` | complete active `sunxi_metadata` | not the expected legacy attr placement |
| `23480..23543` | 64-byte vendor gap | — |
| `23544..23599` | active packed 56-byte attr | not read there by this Mali generation |
| `23600..24575` | padding | — |

At 4K, `HevcSetNewRef` again initializes/copies the extended 23,480-byte object, the active attr
remains valid, and Mali emits the same decisive `Crop rectangle dimensions not equal to logical
buffer dimensions` before EGL error `0x3003`. Compat1 logs `eligible=0`,
`reason=sdr_yv12_contract`, `public=0 private=0`, then `view=original`; no shadow is created.

The bounded logger prints only the first 24 changed words (byte offsets 0..92), not the individual
words at legacy offsets `0x80..0xb7`. Their exact physical values therefore cannot be recovered from
this archive and are not fabricated here. Exact Mali disassembly and the active layout establish
that it reads extended HDR/LUT data there, while the identical crop rejection establishes that the
first consumer-boundary failure is the same class.

RC-B classification: **B — SAME METADATA ABI COLLISION, VERY HIGH CONFIDENCE**. A separate
4K/auto-AFBC import limitation can exist after translation, but the current attempt cannot reach it
until the crop ABI collision is removed.

The fatal chain is exact:

```text
AHardwareBuffer 3840x2160 YV12
 -> UBOX_R7_COMPAT1 eligible=0 / view=original
 -> native client buffer non-null
 -> Mali: crop dimensions != logical dimensions
 -> eglCreateImage = 0 / EGL_BAD_ALLOC 0x3003
 -> Ganesh BackendTexture invalid
 -> RenderEngine fatal / SurfaceFlinger SIGABRT
```

`media.codec` PID 2503 survives. The kernel boot ID remains unchanged, while SurfaceFlinger 541 and
the zygotes/system_server/audio services receive new PIDs, proving a userspace framework restart.

## compat1b exact design

Classification: **READY_FOR_EXACT_COMPAT1B_IMPLEMENTATION**.

### Stable contract fields

A 4K view is eligible only when all captured stable fields match:

```text
AHB: width=3840, height=2160, layers=1, format=YV12,
     stride=3840, usage=0x40402d00, not protected
handle: version=12, numFds=2, numInts=53, magic=0x03141592, flags=0x4,
        width=3840, height=2160, requested=YV12,
        producerUsage=consumerUsage=0x40400900,
        internalFormat=0, allocationFormat=YV12,
        pixelStride=3840, layers=1, totalSize=19489120,
        exact three plane offsets/strides/extents above,
        metadataSize=24576, metadataFlag=0x80000010, yuvInfo=3,
        image-fd size=19492864, metadata-fd size=24576
```

This exact contract includes the vendor's captured >=4K auto-AFBC-big private usage while requiring
exported modifier/internal format 0. It excludes every other AFBC/modifier/format contract and does
not claim general AFBC support.

### Mutable observation gate

At EGL import, additionally require the exact post-decoder SDR state:

```text
sunxi_metadata.flag == 0x10
active attr at 23544: crop/control=-1 and dataspace=0x10010000
legacy crop words at 0x80 are all non-negative and are not 0,0,2160,3840
```

The sunxi flag and legacy words are deliberately treated as mutable post-use evidence, not stable
allocation identity. Fd numbers, pointers, PIDs, refcounts, buffer/backing IDs and hashes are never
predicates.

### Translation

The translation is exactly the physically proven compat1a mechanism:

```text
map original metadata fd read-only (0x6000)
create sealed 0x6000 memfd shadow
copy all 0x6000 bytes to shadow
copy exactly 56 bytes: original[23544..23599] -> shadow[0x80..0xb7]
verify source unchanged and destination exact
clone native handle; replace only metadata fd in clone
create temporary AHardwareBuffer CLONE view; import only that view into Mali
```

No 4K-specific field needs translation beyond the same 56-byte attr. Image fd, all planes, total
size, usage, handle metadata flags, decoder AFBC header/content and original sidecar remain
byte-identical. The design must not rewrite crop, plane geometry, allocation size, usage or AFBC
metadata, and must not synthesize a modifier. Existing compat1a ownership, seal, clone, lifetime and
fail-closed behavior are reused unchanged.

Main10, P010, HDR10, HLG, protected/DRM buffers, unknown formats, other dimensions, other metadata
sizes/handle ABIs and any other AFBC/modifier contract are excluded. Passing the translated crop
gate would test the next boundary; it would not by itself prove that old Mali can render the
captured vendor auto-AFBC-big backing.

## Relationship and next candidate

RC-A2 and RC-B are **INDEPENDENT** at the demonstrated failure mechanisms:

- RC-A2 is a 32-bit process-local heap overflow in an internally allocated copy-path
  `VideoPicture::pMetaData`, exposed during preparse teardown.
- RC-B is a 64-bit Mali import of a distinct fd-backed external gralloc buffer during formal
  playback; its OMX service PID remains alive.

They share the extended Allwinner metadata generation and the 4K trigger, but neither pointer nor
ownership crosses between the two incidents. The evidence therefore does not support one common
free/import repair.

Recommended next strategy: **A — RC-A2-only candidate first**. Correct the memory-safety violation
in exact `libfbm.so`, then use one bounded session to confirm that preparsing/Executing-to-Idle no
longer restarts `vendor.media.omx`. The subsequent single formal playback may still stop at the
known RC-B crop rejection; that is expected and keeps causal isolation. Only after RC-A2 is
physically closed should a separate compat1b candidate translate the exact 4K contract.

## Governance

- Original RC-A `__anDrain` NULL: **PHYSICAL REPAIR EFFECTIVE FOR FORMAL PLAYBACK PATH**.
- RC-A2: **NEW PHYSICAL FAIL / FORENSICS COMPLETE / READY_FOR_NARROW_BINARY_PATCH**.
- RC-B: **PHYSICAL FAIL / EXACT 4K CONTRACT CAPTURED / READY_FOR_EXACT_COMPAT1B_IMPLEMENTATION**.
- P3-A: **PHYSICAL FAIL**.
- P3-B Main10: **NOT AUTHORIZED**.
- compat1a: **AUTHORIZED SDR 1080P YV12 PHYSICAL PASS / UNCHANGED**.
- Audio P1: **CLOSED**. P2: **COMPLETE**.
- Main10, HDR, general AFBC and protected playback remain **NOT AUTHORIZED**.
- `r8`: **NOT AUTHORIZED / NOT BUILT**.
