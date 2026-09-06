# a16-dev-p3a-compat1b-r1

P3-A RC-B COMPAT1B CANDIDATE / DEVELOPMENT ONLY / NOT r8 / NOT RELEASE.

Physical validation status (September 6): **PHYSICAL PASS — BOUNDED MAIN8 SDR 4K30 SURFACE PLAYBACK**.
RC-B / compat1b is **PHYSICAL PASS**; separate **4K non-surface thumbnail PHYSICAL FAIL**.
This does not qualify sustained load, every 4K file, Main10 or HDR. RC-A remains **PHYSICAL REPAIR EFFECTIVE**;
RC-A2 is now **PHYSICAL PASS / CLOSED** on the independently checked FBM-r1 evidence below.
Audio P1 remains CLOSED; P2 COMPLETE; canonical r7 PASS / FROZEN / UNCHANGED;
Gate 3 PASS_WITH_EXPLICIT_USER_WAIVER / CLOSED. r8 NOT AUTHORIZED / NOT BUILT.

Starting repository commit: `5b11e8aefb1bdd0190f40411fdbde2e6347ebd46`, branch
`codex/m8-a16-development`; local, tracking and GitHub HEAD agreed and worktree was clean.
Base: exact physically tested `a16-dev-p3a-fbm-r1`, 1,641,830,400 bytes,
SHA256 `092DD3960136A086C7F9E60065A6C88D3984B0ACCA9FB7E57247D48370904535`.

Image: `out/candidates/a16-dev-p3a-compat1b-r1/x12-a16-dev-p3a-compat1b-r1.img`

Size: **1,641,834,496 bytes**. SHA256:
**`9A23D1457E8B25BBAEBFB70F2095C5300F90B3A517C0768A808AB1B2174FA6E4`**.

## New physical evidence: RC-A2 closure, RC-B reproduction

Read-only archive outside Git:
`/work/physical-evidence/ubox10/a16-p3a-fbm-r1/UBOX10-A16-P3A-FBM-R1-RCA2-PASS-RCB-FAIL.zip`.
Outer SHA256 **`6f332f683bcdc59656d11a202db9e97dfe5187ae747b4145d0cea113c32577df`**,
verified against the adjacent original checksum. Extraction:
`/work/tmp/ubox-compat1b-evidence-zyTy8R`; internal `SHA256SUMS.txt`: **12/12 PASS, 0 FAIL**.
Raw ZIP, logs and transcripts remain outside Git. These are filtered captures retaining original
Windows source filenames/line references, not full live log files; claims below use the actual
provided captures and operator observation, not an invented exhaustive log census.

| Phase | Decisive supplied evidence / UTC on September 5 |
|---|---|
| Installed identity | `bootgate-runtime-sha256.txt`: exact patched FBM, OMX, audio and compat1a SurfaceFlinger identities |
| Preparse | `preparse-key-signatures.txt`: 04:00:23.013 FBM 3840x2160; .169 and .353 TransformYV12ToYUV420, source 3840x2176 / destination 3840x2160 |
| Normal teardown | 04:00:23.353 Executing→Idle; .378 DestroyVideoDecoder; .419 transition OK; .420 Idle→Loaded; .430 transition OK |
| Continuity | `pre-vlc-critical.txt` and `post-preparse-critical.txt`: boot `160a1748-736f-4dfa-bb89-9bf323834049`, media.codec PID **592**, SF542/system_server783/zygotes491+493 unchanged; operator saw no preparse failure |
| Formal 4K | `4k-key-signatures.txt`: buffer **10226317131793**, backing store **2207613190241** at EGL_PREIMPORT 04:01:56.575; image inode17999, metadata inode18000 |
| RC-B | 04:01:56.589 compat1 eligible=0/sdr_yv12_contract, original view; .591 crop dimensions mismatch; .592 eglCreateImage=0/error0x3003; .593 RenderEngine SIGABRT |
| After crash | `post-4k-critical.txt` / `post-4k-crash.txt`: same boot and media.codec592, but SF2655, zygotes2650+2648, system_server2808, audioserver2651, audio HIDL2657; userspace restart, not reboot |

The old drain NULL and Scudo/FbmFreePictureBuffer signatures did not recur in the retained
preparse/teardown sequence; positive completion through Idle→Loaded plus service continuity
supports **RC-A2 PHYSICAL PASS / CLOSED**. It does not mark the entire P3-A media path PASS.
The formal attempt still failed visibly (black/Android/quarter-screen recovery), with codec PID592
surviving the separate graphics fatal.

Fixture provenance is now retained: filename
`ubox10-hevc-main8-sdr-3840x2160p30-aac.mp4`, **108,484,632 bytes**,
SHA256 **`9ba96f96f1e1266501e0f5c42b109ce0e76b1728d04216ad5e8624a734b80dc7`**.
Host/device identity transcripts agree. `fixture-ffprobe.txt`: HEVC Main, level150,
yuv420p, 3840x2160, 30/1 fps, 900 frames, 30 seconds, limited-range BT.709
primaries/transfer/matrix; AAC LC stereo, 48 kHz. This is not Main10/HDR.

## Exact consumer predicate

The [accepted forensic design](../20260905-a16-p3a-rca2-compat1b-forensics/README.md)
is implemented additively in `AHardwareBufferGL.cpp`, with host-testable
`UBOXP3Compat1b.h`. Existing compat1a 1080p predicate expressions remain unchanged.

| Stable field | Required value |
|---|---|
| Native handle | version12, 2 fds, 53 ints, magic0x03141592, flags4 |
| AHardwareBuffer | width3840, height2160, stride3840, layers1, formatYV12 (0x32315659), usage0x40402d00; not protected |
| Private handle | width3840, height2160, pixelStride3840; producer=consumer usage0x40400900; internalFormat0; allocationFormatYV12; byteStride/internalWidth/internalHeight0 |
| Plane0 | offset0, stride3840, 3840x2160 |
| Plane1 | offset8294400, stride1920, 1920x1080 |
| Plane2 | offset10368000, stride1920, 1920x1080 |
| Capacity | handle total19489120; layers1; image fd fstat19492864; metadata field/fd fstat24576 |
| Private metadata | metadataFlag0x80000010, yuvInfo3 |

This explicitly recognizes the **observed private auto-AFBC-big reservation behind exported
YV12/internalFormat0**, not a generic linear-only/no-private-AFBC buffer. The ordinary 12,441,664-byte
initial population is ineligible. Private usage is constrained by exact producer/consumer usage,
not rewritten. No buffer IDs, inode/fd numbers, pointers, PIDs, refcounts or hashes are predicates.

Additional **mutable consumer-time** gate: sunxi flag exactly0x10 (no HDR bits); active crop and
YUV/sparse controls all -1; all 28 active HDR-info bytes0xff; dataspace0x10010000; four legacy crop
words nonnegative but not `(0,0,2160,3840)`. The extra HDR sentinel restriction is supported by the
physical full attr hash `e7e2d4496502c218` and independently tested. The old logger did not capture
individual legacy crop words at0x80, so their exact values remain unknown until future activation.
Unknown state fails closed to original import with existing EGL/RenderEngine failure behavior.

Main10/P010/vendor10-bit formats, HDR/HLG flags/dataspaces, protected/DRM usage, other modifiers,
other resolutions, capacities, usages and handle ABIs are excluded. The consumer cannot infer an
encoded profile from a buffer alone (e.g. hypothetical prior conversion to the identical 8-bit
contract); physical authorization therefore remains tied to the exact Main8 fixture. No Main10
or general AFBC capability is claimed or tested.

## Translation and ownership — unchanged compat1a mechanism

Original metadata mmap remains `PROT_READ`. Create a 24 KiB memfd with CLOEXEC/ALLOW_SEALING,
ftruncate to24576, seal GROW/SHRINK, verify size, mmap RW; copy all24576 bytes and then copy exactly56:

| Active Allwinner source | Legacy Mali destination | Content |
|---|---|---|
| 23544..23559 | 0x80..0x8f | crop top/left/height/width |
| 23560..23563 | 0x90..0x93 | YUV transform |
| 23564..23567 | 0x94..0x97 | sparse allocation |
| 23568..23595 | 0x98..0xb3 | complete 28-byte HDR-info block |
| 23596..23599 | 0xb4..0xb7 | dataspace |

No synthesized crop, no pixel conversion, no plane/size/usage change. Original image fd and sidecar
are untouched. Existing copy verification and full host byte-comparison tests remain; the runtime
`original_unchanged` marker checks the original legacy attr region, not an atomic full-sidecar
snapshot against concurrent producer activity. All original mappings are read-only.

Clone original handle; close only clone fd2 and replace it with shadow; create AHB using CLONE;
close/delete the intermediate cloned handle. The new AHB owns duplicated fds. EGLImage acquires
its own AHB reference on successful import; local AHB reference is released on either outcome;
existing GLTextureHelper destroys EGLImage and its reference on retirement. Error paths keep the
existing close/unmap behavior. There is no sampling daemon or per-rendered-frame fd generator:
shadow creation occurs only on the existing buffer/EGL import path, whose texture is reused.

`UBOX_P3_COMPAT1B eligible=1` identifies the exact new contract. Existing `UBOX_R7_COMPAT1`
shadow_created/translated/view_created/egl_import_result and DIAG1/DIAG3 markers remain.
4K success is **not** inferred from eligibility or successful allocation alone.

## Reproduction and offline acceptance

Use `configs/aosp/architecture-ceiling-a16/development/p3a-compat1b-r1/prepare.py`
`check|apply|revert` on the exact compat1a source; revision/hash checks refuse unexpected input.
The shared `UBOXR7Compat1Metadata.h` remains SHA256
`98228a9599eedfcd6c073124c31a48e105e3360e7c62ed05c4c77d2300951294`.

Run `scripts/build-a16-p3a-compat1b-surfaceflinger.py --output <new-external-proof-directory>`.
It uses pinned A16 FMQ only during the ARM64 graphics build, restoring the exact legacy audio-r1
build input afterward. First it rebuilds compat1a without this overlay and requires the physical
SurfaceFlinger SHA to match exactly; then it reapplies the overlay and builds only SurfaceFlinger.
This prevents unrelated audio-wrapper reconstruction inputs from entering the graphics payload.
No audio/vendor build output is used in this candidate.

Next use the candidate JSON's exact source/artifact identities with:

```sh
python3 scripts/build-a16-dev-p3a-compat1b-r1-candidate.py
python3 scripts/audit-a16-dev-p3a-compat1b-r1.py
python3 scripts/check-a16-dev-p3a-compat1b-r1.py
```

The established pipeline replaces only `/system/bin/surfaceflinger` inside a copy of the exact
FBM-r1 system image, preserves inode mode/uid/gid/SELinux label, regenerates system AVB and its
vbmeta, inserts the fixed LP extent and repacks IMAGEWTY. Vendor is copied byte-for-byte.
Canonical r7 and Test8r2 rollback remain immutable. Artifacts/logs/hashes stay under ignored `out/`.

### Completed offline results

The exact control build reproduced SurfaceFlinger size8,577,592/SHA
`06C960E672863AD557AF921565621997CB9B113BA2290049AF91028A405CD0A5`.
Compat1b is size**8,581,800**, SHA
`CC64B466C15C4E78917E4BED2BB61E59C9A3C90E816E85BE306BF73B19EB2A45`,
Build ID `7b634810ca8ff86b5d7d120a54199ae3`; ELF64 AArch64.
Both have identical SONAME/DT_NEEDED, all1317 strong imports and710 defined dynamic symbols
(including weak exports). Exact ARM64 direct-needed provider closure has zero unmatched imports.
The final overlay-only rebuild required8 build actions after the exact control.
The preliminary build with the audio-specific FMQ projection was not packaged.

Signed-system manifests include all**3,381** entries on each side. Exactly
`system/bin/surfaceflinger` changes; no files added/removed. Vendor is byte-identical,
SHA `231F0D2108AA709B8BDDA2E88E4C776E2B4CFA56BAED6E35A7DB5C992D903181`.
The manifest reader uses privileged **host-only read** of read-only mounted images because
Android's `/system/bin` is root:shell0751; traversal errors now fail closed rather than silently
skipping that directory. Historical compat1a source checking reverses only the verified successor
patch in a temporary copy, then enforces the complete original source sizes/hashes unchanged.

| Preserved repair | Exact SHA256 |
|---|---|
| `/vendor/lib/libfbm.so` | `786264793BB16083CD62BC3BC0B6A2AE4673DBC75504A79EAC189DB943840E9F` |
| `/vendor/lib/libOmxVdec.so` | `5FE74A28EB9E083959FDAC9CFDE870FAA2AF4447DADB7776C1E7F4CFC6D1EE8B` |
| `/vendor/lib/hw/android.hardware.audio@7.0-impl.so` | `E2F3D49D757AA4132180C3D247857FC9725D7113E92A079E10181AADBCC062ED` |

Mechanical deltas: system ext4/AVB, system vbmeta, super raw/sparse and IMAGEWTY/checksums.
Outer changed payloads are exactly `super.fex`, `Vsuper.fex`, `vbmeta_system.fex`,
`Vvbmeta_system.fex`; vendor vbmeta, top vbmeta, boot, product, vendor_dlkm and other payloads
remain unchanged. Canonical r7 SHA `A1F58668AEFFC9DC83CFFD8A49A309839332B6616C02153DCC00A71136A7AA27`
and Test8r2 rollback SHA `6A52F3388E9ABF6AFA8A701CFD7198FE6C0090F16531F6E3BD3949E760892EC8` reverify unchanged.

System/vendor/product/vendor_dlkm e2fsck, AVB, LP metadata/extent equality, sparse/raw roundtrip,
IMAGEWTY integrity and source/ELF checks PASS. System VINTF **PASS / exit0**.
Full VINTF remains **NOT PASS / exit65**, only inherited `CONFIG_NFS_FS=y` vs FCM-6 required`n`.
SELinux permissive/enforcing debt, Thermal HAL/calibration debt and display ceiling are unchanged.

Focused tests exercise all stable-field mutations, excluded usage/protection/format/metadata states,
exact56-byte/full-sidecar preservation, the physical attr hash, memfd sizing/seals/mmap/dup/close100
iterations under ASan/UBSan/integer sanitizers, exact control build contract and fail-closed tree
enumeration. The existing compat1a translation/fd tests also PASS. Final regression:
**68 passed, 2 skipped** (PowerShell unavailable for the two inherited parser checks; static
checks pass). Candidate checker PASS; candidate SHA256SUMS **40/40 PASS**; compileall,
all103 tracked/new JSON documents and `git diff --check` PASS. No device/ADB/flash/playback action
was performed, and the VM remains running.

## Original build-time physical contract (historical; subsequent result below)

After separate flash authorization: flash exact image → normal boot → **BootGate FIRST → REVIEW
BOOTGATE**. Stop on failure. Only then install/verify VLC, create the media directory, transfer and
verify fixtures, and first-launch VLC/onboard/permissions/scan. Start live PC-side capture before
VLC can preparse the 4K fixture; preserve that preparse window separately. Finish all first-run
preparation before formal AVCPre. Use the existing accepted capture/thermal tools, explicit
`C:\platform-tools\adb.exe` and operator-supplied current `<IP>:7896`; no stale fixed IP.

Formal AVC 1080p control first, then review; verify original metadata path and normal picture/audio.
Preserve fixture filename/bytes/SHA/full ffprobe before one manual Main8 SDR 4K30 attempt. Capture
thermal baseline, boot ID, critical PID/PPID/name census, crash/tombstone baseline, and stream logs
live to the PC before playback. Thermal sampling must overlap playback this time. No loops, auto
player control, automatic reboot or automatic retry. Short smoke only, maximum one 30-second fixture;
abort manually for corruption, freeze/stall, audio collapse, thermal warnings/trip approach,
unexplained frequency collapse or process restart. This is not sustained thermal qualification.

Required new path on the **same buffer/backing ID**: COMPAT1B eligible1 → COMPAT1 shadow_created1
(memfd_ftruncate_sealed,size24576) → translated1(src23544,dst128,bytes56,original_unchanged1,attr_copy1)
→ view_created1(CLONE) → view=sdr_shadow/egl_import_result1 → EGL_CREATE_IMAGE1 → BackendTexture1.
Require correct full-frame geometry/motion/colors/AAC HDMI audio, hardware Allwinner/Cedar decode,
same boot and critical service PIDs, no new tombstone/crash, no EGL_BAD_ALLOC/SF abort. Stop and
review either result; if explicitly stable, return/back and one AVC regression. No Main10, HDR,
HLG, other AFBC contracts, protected/DRM, 4K stress or other resolutions.

Build-time uncertainty: the same metadata collision was very-high-confidence, not prior physical
proof of 4K translation. A further pixel-storage/Mali/HWC limitation may appear after removing
the crop collision. Preserve the first failing boundary; do not widen this predicate automatically.

## Thumbnail forensics — 2026-09-06

Research baseline: `ca6fd9dc37630dec2d0a71162eface046053446d`, local/tracking/GitHub equal,
clean `codex/m8-a16-development`. It includes compat1b commit `f508b5a` and the two subsequent
skill edits. The updated fast-track guidance keeps this result in the current candidate record;
no new report hierarchy, candidate, runtime patch or device action is created.

### Evidence and distinct physical results

Archive outside Git:
`/work/physical-evidence/ubox10/a16-p3a-compat1b-r1/thumbnail-forensics/UBOX10-A16-P3A-COMPAT1B-R1-THUMBNAIL-FORENSIC-CORE.zip`.
SHA256 **`ffa5fa0a9a17c1ee265f95a203f1e29f6f77a04fb72dcafa8e8db6f7d0746154`** matches the
adjacent checksum. Extraction `/work/tmp/ubox-thumbnail-HK5Vk7`; original `SHA256SUMS.txt`
**9/9 PASS, 0 FAIL**, including `vlc-swthumb2.png`. Originals remain untouched.
The key files are filtered transcripts retaining original Windows filenames/line numbers, not
complete live logs. Empty crash buffer is an operator-reported result; no independent full crash
artifact is included. Do not turn absence in a filtered file into an exhaustive crash census.

| Event / September 6 UTC | Decisive evidence |
|---|---|
| Installed identity | `bootgate-runtime-sha256.txt`: exact FBM/OMX/SF/audio SHA values above |
| Formal playback baseline 02:32:40 | boot `d951d73a-57cf-43b0-a792-13ce37f8943b`; SF538, codec594, audio531/HIDL505, system_server782, zygotes493/494 |
| First successful import 02:32:54.776–.778 | `4k-compat1b-key-signatures.txt`, original lines22901–22934: buffer10075993276433/backing2211908157522; eligible1, sealed24576 shadow, translated56(src23544,dst128), original read-only, CLONE, EGL success |
| Repeated imports | 14 distinct buffer IDs10075993276433..446 each carry compat1b activation, translation/import success and valid backend texture |
| Post 02:33:28 | exact boot and critical PID/PPID/name set unchanged; operator full-frame, smooth >10 seconds, audio, no recovery; crash buffer reported empty |
| Fresh thumbnail 02:56:12.009–.249 | `vlc-swthumb2-key.txt`, original4161..4608: newly discovered swthumb2 identity; VLC preparse and metadata task finish |
| Non-surface codec 02:56:12.644–.708 | original5227..5343: OMX HEVC in codec594; ACodec in PID589 selects0x13 for flexible420, requests one output buffer; 12441600 bytes; FBM3840x2160 |
| Pixel copy 02:56:12.811 and .994 | original5366/5372: TransformYV12ToYUV420 source3840x2176, destination/copy3840x2160; component unload13.087 |
| Corruption | screenshot independently shows stable green/red stripes and repeated blocks; operator confirms HW preference Disabled and new file introduced after force-stop |
| 1080 control 03:06:36.962–37.221 | `vlc-1080-thumb-control-key.txt`, original5495..5696: CCodec/FrameDecoder, ordinary YV12 1920x1080, stride1920, size3110400, private_usage0; operator thumbnail normal |

This closes RC-B for the authorized short Surface playback, not the unrelated thumbnail path.
RC-A2 stays CLOSED. The normal 1080 control is **a different codec/storage path**, not a proof that
the same Allwinner CPU copy works at1080. The retained control filter does not name its exact C2
component; do not invent one. Old boot/UI lines also appear in filtered files: they are not new
thumbnail decoder events.

Fixture identities from the supplied transcript (media bytes/full new ffprobe are not in this core):

| Filename suffix (prefix `ubox10-hevc-main8-sdr-`) | Bytes | SHA256 |
|---|---:|---|
| `3840x2160p30-aac.mp4` |108484632|`9ba96f96f1e1266501e0f5c42b109ce0e76b1728d04216ad5e8624a734b80dc7`|
| `3840x2160p30-aac-swthumb2.mp4` |108484701|`3ae8705dc4953ed5ea83d0f24a537dbb1f6858a75a35c1383fe21ccb384fca38`|
| `1920x1080p30-thumb-control.mp4` |5118268|`14d9d975ca2f1985c5766e9011c3def4d17227fba97bdc2bbcc2213eeae55d1a`|

### Android consumer contract: 0x13 is I420, not native YV12

Pinned A16 `frameworks/av` revision `d1137ad4b24b686d9b00fd1b7be1b520f7b6ee2b`, under
`/work/src/ubox10-a16-ceiling`:

- `frameworks/native/headers/media_plugin/media/openmax/OMX_IVCommon.h:90,125`: 0x13 is
  `OMX_COLOR_FormatYUV420Planar`, Y then U then V. Native YV12 instead stores Y then V then U.
- `media/libstagefright/ACodec.cpp:3469`: flexible-format substitution is negotiation, **not** a
  pixel conversion. `:5311` forwards OMX stride/slice-height and creates image-data.
- `media/libstagefright/omx/OMXUtils.cpp:211–325`: default0x13 describes Y at0, U atS*H,
  V at5*S*H/4, row incrementsS/S/2/S/2, pixel increments1. Vendor describeColorFormat may override.
- `MediaCodec.cpp:7357`, `FrameDecoder.cpp:632,980,1025–1041`: transfer image-data with the
  buffer; use positive slice-height and image-data/ColorConverter for CPU extraction.
- `FrameDecoder.cpp:783–812`: C2 instead maps the actual graphic view and derives plane layout
  and stride. `:861–880` requests flexible420 and one OMX input/output buffer for thumbnail use.
- `media/libmediaplayerservice/StagefrightMetadataRetriever.cpp:396–436` and
  `MediaCodecList.cpp:427,462–545`: system retriever has its own codec selection and software
  preference, filtered by supported format/size. A returned non-null but corrupted frame need not
  trigger another codec. VLC's playback setting does not control this observed system path.
  The core does not preserve the exact reason 4K chose OMX rather than C2; no codec whitelist or
  property change is justified from that omission.

### Exact vendor copy contract and 2176 padding

Exact candidate `/vendor/lib/libOmxVdec.so`: ELF32 ARM,83780 bytes,
SHA `5fe74a28eb9e083959fdac9cfde870faa2af4447dadb7776c1e7f4cfc6d1ee8b`, retained
Build ID `2042d7e0112320dc855cccee324af569`. Reverified candidate `preserved-omx_r1` against the
analyzed copy `/work/tmp/p3a-rca2-elf/libOmxVdec.so` and the device identity transcript.
Addresses below are **ELF virtual addresses**, not assumed file offsets.

| Exact code | Meaning |
|---|---|
| SetParameter0x82d2..82da | loads port width/height(+0x8c/+0x90), stores stride/slice(+0x94/+0x98) |
| 0x82de..8318 | output size=width*height*3/2; matches physical12441600 |
| drain0xe77a..e794 | loads output width/height and buffer pointer; source pixel enum4 + output0x13 selects planar transform |
| 0xe7a6..e7ea | picture width/height(+0xc/+0x10), crop(+0x18..24); round source dimensions up16; pData0 from+0x50 |
| 0xe822..e832 | memcpy copyWidth bytes per Y row; source increments aligned sourceWidth, destination outputWidth |
| 0xe834..e860, e87e..e88e | source U=pData0+5*sourceWidth*sourceHeight/4; half strides; ceil(copyHeight/2) rows |
| 0xe890..e8aa | source V=pData0+sourceWidth*sourceHeight; same chroma strides; appended after U |
| 0xe976..e99a | timestamp, nOffset0, nFilledLen=outputWidth*outputHeight*3/2; existing lifecycle unchanged |

All three copy calls resolve to `__aeabi_memcpy` at0x13538. There is **no decompression**,
detiling, or AFBC flag check in the selected transform. It does not use pData1/pData2 to discover
planes. Source-correlated function:
`libcedarc-calvin/openmax/vdec/src/omx_vdec_aw_decoder_android.cpp:1284–1370,1536–1605`,
repo `https://github.com/CalvinXu17/libcedarc`, commit `e68d4a727085d02d4622d85b5234304349d4e448`.
This is **OLDER RELATED SOURCE / matching transform arithmetic**, not an exact complete wrapper.
Its `omx_vdec.c:1498–1505` matches the exact output stride/size stores above.

| Plane | Assumed linear source YV12 (3840x2176) | Written destination I420 (3840x2160) |
|---|---|---|
| Y |offset0, stride3840, copy2160 rows|offset0, stride3840,8294400 bytes|
| U |offset10444800, stride1920, copy1080 rows|offset8294400, stride1920,2073600 bytes|
| V |offset8355840, stride1920, copy1080 rows|offset10368000, stride1920,2073600 bytes|
| Span |padded12533760 bytes|compact12441600 bytes|

These calculations are internally correct **if the source actually is linear YV12**. Padded Y
has16 unused rows; each chroma plane8. Tests use different Y/U/V/padding sentinels and reproduce
the exact compact output without swapping chroma or copying padding. Even the intermediate5*Y
is only41779200: no ARM32 overflow. This is **not a proven U/V swap** and2176 alone is not a bug.
If Android instead received slice2176 for compact2160, chroma offsets would be displaced61440/
76800 bytes; final physical 4K MediaImage2/stride/slice is absent, so this remains a lesser hypothesis.

### Strongest failure boundary and hypotheses

The leading defect is **compressed internal HEVC storage fed to a linear-only CPU output copy**,
not the repaired SurfaceFlinger sidecar translation. Exact wrapper `__anPrepare`0xd05a adjusts
r5=ctx+8;0xd05e loads1;0xd068 stores it atctx+0xc8 (`VConfig+0x84`, eCtlAfbcMode).
The store is unconditional with respect to native/zero-copy selection. Related source `:2752–2754`
names that mode `ENABLE_AFBC_JUST_BIG_SIZE`. In exact `libawh265.so::HevcSetNewRef`,
0x193ea reads config+0x84; mode1 uses width>=3840 **OR** height>=2160 at0x19436/19440;
0x19446/19448 sets the FBM AFBC flag. Mode0 has an explicit disable branch. Hardware-generation
gating precedes this selection; earlier exact-device 4K preparse evidence already records AFBC
selection/internal FBM allocations, so this is not inferred only from a sales SoC label.

Related Tina FBM source `libcedarc/vdecoder/fbm/fbm.c:1589–1628` explicitly distinguishes storage:
AFBC picture gets pData0 and nAfbcSize, not linear chroma-plane bases; linear8-bit gets
separate pData0/1/2 plane bases.
Repository `https://github.com/jeasonzs/tina_multimedia`, commit
`63344eadfbab18195046678079d2f3d32d0c61cc`, **NEAR-EXACT OWNERSHIP/STORAGE MODEL**.
The metadata allocation repair changes capacity only; it does not convert this image storage.
Exact candidate `libfbm.so` (20980 bytes, SHA above, retained Build ID
`dcbeaa9e1d25cc5ff2a33c5d314894c2`) confirms this split at0x378a (picture+0xbc AFBC),
0x37aa (pData0 store),0x3806..3810 (8-bit AFBC stores nAfbcSize at+0xc4 and skips linear
pData1/2 setup), versus0x3914..3928 (linear chroma pointers). Exact `libawh265.so` is ELF32 ARM,
127272 bytes, SHA `cc6f2ee2d8a535548a033d1c87ecaaba3677367a4e295c96f06a42a7d8e40823`,
Build ID `3701f119be0076252e2b5d82c48687d9`; no change to either ELF in this investigation.

Reproduce disassembly offline using AOSP clang-r547379 `llvm-objdump -d
--triple=thumbv7-linux-gnueabi --start-address=<VA> --stop-address=<VA> <exact-ELF>`.
The OMX `.gnu_debugdata` symbol table (extract with llvm-objcopy and decompress with xz outside
Git) identifies `__anPrepare`, `__anDrain`, and `__aeabi_memcpy`. Do not use the stripped
objdump nearest-export label `OmxDestroyDecoder+...` as the real function identity. Executable
PT_LOAD VA minus file offset is0x1000; all addresses in this section are VA. The tests validate
the exact OMX SHA and three memcpy call sites as well as source-only planar-copy arithmetic.

| Hypothesis | Supports | Contradicts / limitation | Confidence |
|---|---|---|---|
| Internal AFBC treated as linear pixels | unconditional large-frame mode; exact HEVC size selector; internal FBM storage model; memcpy-only consumer; stable block/stripe screenshot | new core omits source bEnableAfbcFlag/pData bytes; no bit-exact screenshot reconstruction | **HIGH**, strongest source/binary-backed mechanism |
| Wrong U/V order | green/red colors are compatible with bad chroma | exact transform intentionally converts YV12 to I420 in correct order; swapping U/V does not explain repeated luma structure | LOW |
| Padded-height/stride error |2176 differs from2160; final MediaImage2 absent|exact copy skips padded rows and writes compact planes; initial port advertises2160|LOW–MEDIUM residual |
| Output allocation too small / arithmetic overflow |large frame|12441600 exactly fits compact I420; relevant32-bit arithmetic does not overflow|LOW |
| Stale thumbnail cache / VLC setting |thumbnail machinery separate from playback|fresh filename/hash after force-stop still fails; hardware path recorded despite Disabled|not primary; setting independence established|
| compat1b / original metadata / FBM heap regression |same video family|14 successful Surface imports, normal playback, prior repaired identities; CPU copy does not use Skia shadow|not supported|
| Cache coherence / secondary output / other format |possible in proprietary stack|cache callback precedes copy0xe4ac..e4c8; no positive evidence of another conversion|NEEDS_MORE_EVIDENCE, not ruled out by log absence|

Do not describe compressed bytes as decoded planar Y/U/V just because the public pixel enum is4
(YV12) or OMX says0x13. The passed Surface path can import vendor-aware compressed storage with
its sidecar; the CPU FrameDecoder requires actual linear pixels and never uses compat1b.

### Narrow repair design and remaining evidence

Design boundary: `libOmxVdec` decoder preparation, before `InitializeVideoDecoder`/FBM allocation,
not Skia, ColorConverter, gralloc, libfbm, or a thumbnail-color shader. Preserve AFBC for every
existing native/Surface path. Only the non-protected, non-native, non-zero-copy HEVC Main8 SDR
path requesting0x13 should select disabled compression and retain YV12 internal output:

```text
mode = existing ENABLE_AFBC_JUST_BIG_SIZE
if verified non_surface && !zero_copy && !secure && HEVC && Main8_SDR
   && output_color == OMX_COLOR_FormatYUV420Planar:
    mode = DISABLE_AFBC
InitializeVideoDecoder(existing_config_with_that_mode)
// same FBM ownership, RequestPicture, copy, FBD, ReturnPicture and teardown
```

No global mode1→0 replacement: that would alter physically passing Surface playback. No change
to AFBC bits after a compressed picture exists, no UV swap, no size/crop lie, no suppression of
metadata initialization/free. The existing0x6000 FBM metadata fix must remain.

Readiness is **NEEDS_MORE_EVIDENCE for a final exact binary patch**, with a high-confidence narrow
repair design. The provided filtered core does not directly capture the offending picture's AFBC
flag/planes or final OMX image description. Also the safe location/representation of the Main8/SDR
and non-surface checks in the exact prepare path must be verified before choosing machine bytes;
an unconditional immediate patch is not approved by this report. This is not merely an unavoidable
VLC limitation: the vendor contract has an actionable engineering boundary.

Next smallest step: offline derive/prove that conditional preparation change and its exact branch
scope; reuse any retained full `vlc-swthumb2-live.txt` around original5227–5406 to recover omitted
AFBC/port/format lines before asking for a new run. If still ambiguous, one bounded observation of
the same fresh Main8 file should record (without frame dumps) source pixel enum/bEnableAfbcFlag/
nAfbcSize/nLineStride/pData-relative offsets, output0x13/stride/slice/nFilledLen/MediaImage2 and
consumer identity. Do not build a candidate just to guess a UV/slice fix. Subsequent authorized
repair validation must pair fresh4K thumbnail correctness with unchanged4K Surface playback and
1080 thumbnail control; preserve file/hash/ffprobe and no-restart/teardown evidence. No Main10,
HDR, generic AFBC, protected expansion, repeat/stress campaign or physical action in this task.

Closure checks: **45 passed, 1 skipped** across thumbnail/compat1b/FBM/OMX/compat1a/audio/Gate3/P2
regressions; skip is the existing unavailable PowerShell parser. New tests verify the9-file manifest,
14 per-buffer successful imports, boot/PID comparison, exact ELF memcpy sites and padding/U/V model.
Candidate checker, JSON parse, Python compileall and `git diff --check` pass. The initial regression
found a removed documentation phrase (`physical validation`); wording was corrected and the full
selected suite rerun successfully. No decoder execution, ADB, new image, runtime edit, evidence
modification or VM shutdown occurred. Full VINTF inherited exit65/NOT PASS, audio P1 CLOSED,
P2 COMPLETE, r7/Gate3 frozen and r8 NOT AUTHORIZED / NOT BUILT remain unchanged.
