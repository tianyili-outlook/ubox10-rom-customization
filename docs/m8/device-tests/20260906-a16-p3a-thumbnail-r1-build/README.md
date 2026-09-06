# a16-dev-p3a-thumbnail-r1

DEVELOPMENT THUMBNAIL COMPATIBILITY CANDIDATE / NOT r8 / NOT RELEASE.
**BUILT / OFFLINE CHECKED / PHYSICAL VALIDATION PENDING**.
This is not a new claim of Main10, HDR or generic AFBC support.

Starting revision: `5fb27b9be69b8b788839c23f7c5a6e4e85bf08fe`, clean
`codex/m8-a16-development`, local/tracking/GitHub equal. Base is exact physically tested
`a16-dev-p3a-compat1b-r1`. Its bounded Main8 SDR 4K Surface playback and compat1b remain PASS;
RC-A2 and audio P1 remain CLOSED; P2 COMPLETE; r7/Gate3 frozen; r8 NOT AUTHORIZED / NOT BUILT.

## Supplemental evidence closes the storage question

Evidence is read-only and outside Git under
`/work/physical-evidence/ubox10/a16-p3a-compat1b-r1/thumbnail-forensics/`.
The previously verified core archive has SHA256
`ffa5fa0a9a17c1ee265f95a203f1e29f6f77a04fb72dcafa8e8db6f7d0746154`, 9/9 manifest entries PASS.
The two newly supplied excerpts have these independently recorded provenance hashes;
they have no separate supplied checksum manifest, so these are not claimed as upstream verification:

| Supplemental file | SHA256 |
|---|---|
| `vlc-swthumb2-raw-5180-5450.txt` | `a635fa92fe03b89ecda1ecac6d96f7cb475d351145ba0c1aaddd2827c1be131e` |
| `vlc-swthumb2-afbc-layout-key.txt` | `80a7d4bedb42b4e146cf5a312ba498ad041e23493a8abec898ff417a613b5e29` |

Use the contiguous raw excerpt, not incidental `afbc` substrings inside VLC pointer values.
All events below are September 6 UTC, codec PID594, client PID589, same fresh swthumb2 extraction:

| Original line / time | Fact |
|---|---|
| 5245–5247 / 02:56:12.669 | describeColorFormat/2 unsupported; ACodec substitutes planar0x13 for flexible0x7f420888 |
| 5261 / .670 | output capacity38016→12441600 for3840x2160 |
| 5262–5264 | native-buffer/ANW extensions unsupported in this request path |
| 5286–5313 / .694–.695 | `__anPrepare`; InitializeVideoDecoder; VE IP33010; **eCtlAfcbMode=1** |
| 5318–5319 / .695 | HEVC PTL parser explicitly identifies **8 bit**, after the configuration was supplied |
| 5340–5342 / .708 | VE AFBC enabled, HEVC bEnableAfbcFlag=1, b10BitStreamFlag=0 |
| 5343–5364 / .708–.798 | ten3840x2160 FBM pictures; all ten allocation records explicitly AFBC=1 |
| 5366 / .811; 5372 / .994 | linear TransformYV12ToYUV420: source3840x2176, output/copy3840x2160 |
| 5370–5406 / .993–13.087 | Executing→Idle, synchronized drain/decode/submit stop, decoder destroyed, component unloaded |

**Root cause: AFBC-compressed internal HEVC pictures are consumed by a linear-only CPU copy.**
Confidence is high: positive storage flags, exact binary allocation branches and memcpy-only
consumer agree. The fix's visible result remains unproven until a fresh thumbnail is captured.
The output color-aspect report T66 at line5369 is retained as an observation, not evidence that
the independently identified Main8/BT.709 fixture is HDR, and not something this repair rewrites.

## Contract and repair boundary

The [preceding forensic record](../20260905-a16-p3a-compat1b-r1-build/README.md#thumbnail-forensics--2026-09-06)
contains exact binary identities, Android source references and the source-match limitations.
Related source is CalvinXu17/libcedarc revision `e68d4a727085d02d4622d85b5234304349d4e448`,
`openmax/vdec/src/omx_vdec_aw_decoder_android.cpp`, not an exact complete replacement wrapper.
Runtime identifies CedarC-v1.3.0/stable_v1.3.0_common, commit
`3b65bf7287aea23c2abfbc626c3f606e3b9def1c`.

Exact `__anPrepare` starts at ELF VA0xcf28. At0xcf9e–0xcfba, `pOutPort->bAllocBySelfFlags`
(port+0x128) and secure state determine native/zero-copy configuration. Context fields:
secure+0x58a4, Android/native buffer+0x58b0, zero-copy+0x58bc, output-port pointer+0x58cc.
`__anSetExtPara` native-buffer cases write+0x58b0; this is distinct from zero-copy.
Preparation sets bGpuBufValid(ctx+0x98) and zero-copy for externally allocated or secure output.
The existing config store atVA0xd068 nevertheless always writes mode1 toctx+0xc8
(VConfig+0x84). InitializeVideoDecoder at0xd15e receives this config before HEVC FBM allocation.

HEVC's exact mode1 branch enables AFBC on this VE IP when SPS width>=3840 or height>=2160.
Mode0 selects the existing uncompressed branch. FBM's existing linear allocation then provides
the storage that the existing CPU conversion assumes. No post-allocation AFBC bit clearing,
decompression shim, color swap, frame-drop or ownership change is appropriate.

Pre-initialization state can identify codec family, coded dimensions, output color format,
native/zero-copy mode and security. Actual SPS bit depth/profile is parsed *inside* initialization;
it is not a trustworthy Main8 gate at the earlier config store. Likewise later color/HDR metadata
cannot be claimed as a proven early SDR discriminator. The repair selects the exact observed
HEVC3840x2160 planar CPU-output contract, not an encoded-profile emulator. Physical authorization
remains the identified Main8 SDR fixture only; an untested stream converted to the identical
CPU contract is not thereby certified or authorized.

Android0x13 is I420: Y/U/V, not native YV12. The unsupported describeColorFormat extensions
leave Android's standard planar description in use. Exact OMX SetParameter stores width3840
and height2160 into stride/slice-height; output nFilledLen is12441600. The excerpt independently
confirms size and crop, but contains no full final MediaImage2 dump; stride/slice/image-data are
therefore source/binary-backed, not falsely presented as fully logged physical fields.

| Plane | Linear source assumption3840x2176 | Destination I4203840x2160 |
|---|---|---|
| Y | offset0; stride3840 | offset0; stride3840 |
| U | offset10444800; stride1920 | offset8294400; stride1920 |
| V | offset8355840; stride1920 | offset10368000; stride1920 |

The existing memcpy loops crop the padded rows correctly for a *linear* source. They neither
decode AFBC nor inspect its plane representation. Padding, U/V swap and ARM32 size overflow
are not supported as the primary cause. Android's final image-data remains a secondary check
if corruption persists after the explicit compressed-source violation is removed.

## Exact implementation and offline proof

`scripts/patch-a16-p3a-thumbnail-r1.py` requires the exact83780-byte compat1b OMX ELF,
SHA256 `5fe74a28eb9e083959fdac9cfde870faa2af4447dadb7776c1e7f4cfc6d1ee8b`.
It refuses wrong input, wrong hook bytes, assembler drift and repeat/overwrite attempts.
The decision is **READY_FOR_NARROW_BINARY_PATCH**, implemented on an artifact copy only.

```text
mode = 1;                         // preserve original default
if (codec == 0x116 /* HEVC */ && codedWidth == 3840 && codedHeight == 2160
    && secure == 0 && useAndroidBuffer == 0 && useZeroCopyBuffer == 0
    && outputPort != NULL
    && outputPort.colorFormat == 0x13 && outputPort.portFormatColor == 0x13)
    mode = 0;
// original alignment/WMV/error-frame setup and InitializeVideoDecoder follow
```

Both color fields are exact port+0xac/+0xd0 (`__anUpdateFormat`0x10360/0x10364 and
related `setPortColorFormat` agree). No profile is fabricated. Encoded Main10/HDR cannot be
identified here; the guard constrains the output contract, while physical authorization remains
Main8 SDR only. Native/nonzero-copy Surface paths are explicitly excluded independently.

Original VA0xd068/file0xc068 `c5 f8 c0 60` (`str.w r6,[r5,#0xc0]`) becomes
`06 f0 4a bf` (`b.w 0x13f00`). A90-byte Thumb stub performs the original store then the guard,
preserves r2/r3/APSR NZCVQ using16 temporary stack bytes, and branches back toVA0xd06c.
No call, ownership operation, port notification, delay or loop is added. r6 remains1 for
the later bDispErrorFrame store; the previous RC-A operand correction and all drain code remain
byte-identical. Hardware decoding and existing allocate/use/free/teardown ordering are retained.

There is no proven existing executable cave large enough for these guards. Rather than overwrite
unrelated instructions, insert one4096-byte file page at0x12f00, mapped atVA0x13f00 in the existing
RX segment gap. Original allocated-section virtual addresses, dynamic addresses, relocations and
contents remain identical except the four-byte hook. Later file offsets shift4096; section-name
and section-header tables are appended/repointed, with `.ubox_thumbnail_linear` describing the stub.
No RWX segment or new import is introduced. The stub itself lies wholly in the RX page before
the next writable mapping. This is an intentional ELF-container change, not a four-byte-only file.
Existing ARM unwind data is unchanged: asynchronous unwinding while inside the new no-call stub
may stop rather than recover the original frame. Normal execution restores SP and all registers;
this diagnostic/backtrace limitation remains explicit pending hardware validation.

Patched ELF: **89192 bytes**, SHA256
**`4916c492dd6b7f1ca8948d2b14394baeeacd1e01cc8c0a7af616975d19551b0f`**.
GNU Build ID `2042d7e0112320dc855cccee324af569` is retained proprietary provenance only;
patched SHA256 is the canonical identity. Stub SHA256
`ef8c98452315150861e2e9de6bb99e6347fca3464699c527c26e7664bcb9dc81`.
Every old allocated section and nonloaded mini-debug payload is independently compared after
file-offset relocation. Host Unicorn2.1.4 executes the assembled bytes across256 guard combinations,
checking mode, PC, all integer registers/SP/LR and branch flags. This is not vendor decoder execution.

## Candidate and completed audit

Image: `out/candidates/a16-dev-p3a-thumbnail-r1/x12-a16-dev-p3a-thumbnail-r1.img`

**1641838592 bytes**; SHA256
**`30BF0B0D4E8484C3C414CD6CDC17616C6F8896BE34579D2F5408476E072D2D4D`**.

Reproduce with `scripts/build-a16-dev-p3a-thumbnail-r1-candidate.py`, then
`scripts/audit-a16-dev-p3a-thumbnail-r1.py`. Both refuse to overwrite existing candidate/audit
outputs. The builder uses copies of exact compat1b partition/container inputs, not an Android
module rebuild. No original firmware or evidence is modified.

Signed vendor manifests contain1110 entries each; exactly `lib/libOmxVdec.so` changes, no
addition/removal. System image is byte-identical. Exact ELF dynamic symbols,81 strong imports,
DT_NEEDED, relocations, ARM attributes and existing section contents/virtual addresses pass;
direct-needed ARM32/VNDK31 closure has zero unmatched imports. Two retained LLVM assemblers
produce identical hook/stub bytes; both disassemblers verify the prior RC-A correction and guard.

| Retained repair | SHA256 |
|---|---|
| SurfaceFlinger/compat1b | `CC64B466C15C4E78917E4BED2BB61E59C9A3C90E816E85BE306BF73B19EB2A45` |
| libfbm/RC-A2 | `786264793BB16083CD62BC3BC0B6A2AE4673DBC75504A79EAC189DB943840E9F` |
| audio HIDL | `E2F3D49D757AA4132180C3D247857FC9725D7113E92A079E10181AADBCC062ED` |

Mechanical differences: vendor ext4/AVB, vendor vbmeta, super raw/sparse and IMAGEWTY/checksums.
Changed outer payloads exactly `super.fex`, `Vsuper.fex`, `vbmeta_vendor.fex`,
`Vvbmeta_vendor.fex`; system vbmeta, boot/kernel, product, vendor_dlkm and other payloads unchanged.
ext4/e2fsck, AVB, LP metadata/extents, sparse/raw roundtrip and IMAGEWTY checks PASS.
System VINTF PASS/exit0; full VINTF remains **NOT PASS/exit65**, inherited
`CONFIG_NFS_FS=y` versus FCM-6 required`n` only. Canonical r7 and Test8r2 rollback SHA identities
reverified unchanged. SELinux/thermal/display debt is not altered.

Final focused/prior-repair/governance suite: **51 PASS, 1 SKIP** (existing unavailable PowerShell
parser; static checks pass). This includes actual Thumb execution over256 cases and both retained
assemblers. Python compileall, all104 tracked JSON files, staged diff whitespace checks and the
candidate top-level SHA256 manifest pass. Host emulator is optional for other environments;
this run used Unicorn2.1.4 installed only under `/work/tmp`, with no package/binary committed.

Remaining uncertainty: actual fresh-thumbnail colors and conditional activation require physical
validation; no final physical MediaImage2 dump yet. The no-call trampoline's asynchronous unwind
limitation above is explicit. This candidate does not certify all HEVC files, other sizes, encoded
Main10/HDR, protected content, or sustained load. VM stays running; no ADB/device action occurred.

## Physical validation contract — future authorization only

No device command is part of this offline task. After separate flashing authorization:
normal boot → **BootGate FIRST → REVIEW BOOTGATE** → VLC installation/verification and fixture
transfer/identity verification → first-launch/onboarding/scan → formal testing. Start host-side
live capture before VLC can discover/preparse the new4K fixture; retain preparse separately.
Use explicit `C:\platform-tools\adb.exe` and current operator-provided `<IP>:7896`, never a stale IP.

Preserve fresh filename, bytes, SHA256 and full ffprobe (Main8/yuv420p3840x2160p30/BT.709/AAC).
One fresh thumbnail extraction should show mode0, HEVC/FBM AFBC0, ordinary linear source storage,
normal Transform/FBD/teardown and a visibly correct thumbnail. Preserve final OMX stride/slice,
image-data and nFilledLen if available. No cache-only old thumbnail may count as the result.
Review before proceeding. Pair with the known1080 thumbnail control and one short manual4K
Surface playback regression: compat1b activation/import success, full correct picture/audio,
unchanged critical PIDs/boot ID, empty crash/no new tombstone. Bound load to the existing short
fixture and thermal guardrails. No playback loops, auto player control, Main10/HDR/protected
probe, stress qualification, or automatic retry/reboot. Stop on the first new failing boundary.
