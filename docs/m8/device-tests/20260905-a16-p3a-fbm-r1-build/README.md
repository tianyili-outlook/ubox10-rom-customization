# a16-dev-p3a-fbm-r1

P3-A RC-A2 REPAIR CANDIDATE / DEVELOPMENT ONLY / NOT r8 / NOT RELEASE.

Status: **PHYSICAL TESTED / RC-A2 PHYSICAL PASS / CLOSED; RC-B STILL FAILS**.

September 5 follow-up evidence independently verifies normal 4K preparse/TransformYV12ToYUV420
and Executing→Idle→DestroyVideoDecoder→Idle→Loaded completion, same boot ID and media.codec PID592.
Formal playback then fails separately at the original Mali import, while PID592 survives.
Archive SHA256 `6f332f683bcdc59656d11a202db9e97dfe5187ae747b4145d0cea113c32577df`,
12/12 internal entries PASS. Provenance and timeline are in the
[current compat1b candidate record](../20260905-a16-p3a-compat1b-r1-build/README.md).
The image and historical build/audit artifacts below are unchanged; the original offline
handoff status was PHYSICAL VALIDATION PENDING, not a claim of physical success at build time.

Image: `out/candidates/a16-dev-p3a-fbm-r1/x12-a16-dev-p3a-fbm-r1.img`

Size: **1,641,830,400 bytes**. SHA256:
`092DD3960136A086C7F9E60065A6C88D3984B0ACCA9FB7E57247D48370904535`.

Base repository commit: `559bf0dfebca3447c1e8eebacdd1c06794531c29` on
`codex/m8-a16-development`. Base image: exact `a16-dev-p3a-omx-r1`, 1,641,830,400
bytes, SHA256 `B970A69C7670C4AE6DFFA3E06EA2317FAA7585B29EE5FA9F7D4740377A17C4A6`.
The accepted repair basis is the [RC-A2 forensic report](../20260905-a16-p3a-rca2-compat1b-forensics/README.md).

## Exact correction and ownership proof

Internal FBM allocates only 4,096 bytes for `VideoPicture::pMetaData`, but the retained
HEVC implementation initializes/copies 23,480 bytes. This candidate increases that
allocation to 24,576 bytes. It preserves allocate once -> use -> free once.

| Item | Original | Candidate |
|---|---|---|
| Runtime path | `/vendor/lib/libfbm.so` | Same |
| ELF | ELF32 ARM, 20,980 bytes | Same |
| SHA256 | `E8977F921254556F6E97525487C34F0D196C0735CD00CD11FB6C1430FA8B81DA` | `786264793BB16083CD62BC3BC0B6A2AE4673DBC75504A79EAC189DB943840E9F` |
| Virtual address / file offset | `0x3934` / `0x2934` | Same |
| Four-byte instruction | `4f f4 80 50` — `mov.w r0, #0x1000` | `4f f4 c0 40` — `mov.w r0, #0x6000` |
| Actual changed bytes | — | **2**, at file offsets `0x2936`, `0x2937` |
| GNU Build ID note | `dcbeaa9e1d25cc5ff2a33c5d314894c2` | Retained; patched SHA256 is canonical identity |

The executable PT_LOAD has virtual address minus file offset `0x1000`, establishing
the patch's file mapping. AOSP clang-r547379 assembles both instructions from source;
llvm-objdump in clang-r547379 and clang-r530567 independently decodes the replacement.
Both instructions are four-byte Thumb-2 non-flag-setting MOV immediates. The patch
changes no boundary, branch target, register destination, stack or unwind state.

```text
3934  mov.w r0, #0x6000     only changed instruction
3938  add   r1, pc          retained allocation diagnostic context
393a  movw  r2, #0x655      retained source-line argument
393e  str.w r9, [r8,#0xc0]  retained picture field store
3942  blx   cdc_malloc      unchanged call, now receives r0=24576
3946  cbz   r0, 0x3978      unchanged allocation failure path
3948  str.w r0, [r8,#0x98]  unchanged pMetaData assignment

3a88  ldr.w r0, [r4,#0x98]  unchanged pMetaData read
3a8c  cbz   r0, 0x3a9c
3a8e  ldr   r1, [r5,#0x28]  bUseGpuBuf
3a90  cbnz  r1, 0x3a9c      external-buffer ownership remains excluded
3a92  blx   cdc_free
3a96  movs  r0, #0
3a98  str.w r0, [r4,#0x98]  clear after the existing free
```

Every byte outside that immediate is identical, including `FbmFreePictureBuffer`,
`FbmDestroy`, allocation failure handling, and `.gnu_debugdata` if present. No metadata
length, image plane, HEVC writer, FBM owner, RequestPicture/ReturnPicture or 4K branch
changes. Internal pictures gain 20,480 bytes each (200 KiB for ten pictures); external
GPU-backed buffers do not acquire a new allocation. The allocation-failure log's old
4,096-byte size argument at `0x3980` remains untouched to keep this two-byte patch exact;
if allocation fails, that diagnostic size is stale but error/ownership behavior is unchanged.

## Reproduction and audit

```sh
python3 scripts/build-a16-dev-p3a-fbm-r1-candidate.py --keep-failed
python3 scripts/audit-a16-dev-p3a-fbm-r1.py
python3 scripts/check-a16-dev-p3a-fbm-r1.py
PYTHONPATH=. pytest -q tests/test_a16_dev_p3a_fbm_r1.py
```

The deterministic patcher requires exact input size/SHA256 and original bytes at the
fixed offset, refuses existing output, and verifies exact output SHA256 and byte delta.
The builder reuses the existing vendor/ext4/AVB/super/IMAGEWTY pipeline; no Android
module or kernel compilation is involved. It refuses to overwrite an existing candidate.

Only `/vendor/lib/libfbm.so` may differ semantically from OMX-r1. Vendor hash tree,
`vbmeta_vendor`, super/sparse representation and outer payload checksums are mechanical
consequences. Signed vendor tree comparison also checks file metadata and SELinux labels.
System, product, boot, kernel, vendor_dlkm, partition extents and all other outer payloads
must retain their baseline content. Canonical r7 and all prior candidates are inputs only.

Completed audit: exactly one signed vendor-tree delta, `lib/libfbm.so`, with no added or
removed files. Mechanical outer changes are exactly `super.fex`, `Vsuper.fex`,
`vbmeta_vendor.fex`, `Vvbmeta_vendor.fex`; `vbmeta_system` and every other payload remain
identical. ELF headers/segments/sections, SONAME, DT_NEEDED, dynamic symbols, relocations,
notes and ARM attributes are unchanged. ARM32 namespace closure has zero unresolved
strong imports. Two independent disassemblers verify the changed malloc argument and
retained ownership instructions. ext4, AVB, both LP metadata slots, sparse/raw roundtrip
and IMAGEWTY integrity pass. System VINTF exits 0; full VINTF exits 65 solely for inherited
`CONFIG_NFS_FS=y` versus required `n`, and remains NOT PASS. Test8r2 rollback SHA256
`6A52F3388E9ABF6AFA8A701CFD7198FE6C0090F16531F6E3BD3949E760892EC8` is verified.

Machine-readable build/audit records, before/after disassembly, command logs and generated
SHA256SUMS remain in the ignored candidate directory. Focused tests cover independently
assembled bytes, both disassemblers, exact two-byte delta, unchanged free path, wrong
size/SHA/bytes refusal, repeated-patch refusal and existing-output preservation. The
Combined FBM/OMX/readiness/forensic/compat1a/audio/Gate3/P2 regression set passes
(59 passed, 2 environment-dependent skips). Candidate checker, compileall, tracked JSON
validation and diff checks pass. Candidate SHA256SUMS verifies 42/42 files; all seven
base image/partition inputs and canonical r7 have been rehashed unchanged after the build.

Preserved SHA256 identities:

| Prior repair | SHA256 |
|---|---|
| OMX RC-A `/vendor/lib/libOmxVdec.so` | `5FE74A28EB9E083959FDAC9CFDE870FAA2AF4447DADB7776C1E7F4CFC6D1EE8B` |
| compat1a `/system/bin/surfaceflinger` | `06C960E672863AD557AF921565621997CB9B113BA2290049AF91028A405CD0A5` |
| audio-r1 `/vendor/lib/hw/android.hardware.audio@7.0-impl.so` | `E2F3D49D757AA4132180C3D247857FC9725D7113E92A079E10181AADBCC062ED` |

## Original physical validation contract (completed on FBM-r1)

Preparation only; this build task performs no ADB, device access, flash or playback.
After separate authorization: flash exact image -> normal boot -> **BootGate -> REVIEW
BOOTGATE** -> only then VLC installation/verification, fixture transfer and first launch.
Before making the 4K fixture visible to VLC, start host live log capture: medialibrary
preparse itself previously triggered RC-A2. Preserve the first-launch/preparse window
separately from formal playback. Complete onboarding/permissions/scan before formal
media capture begins. Review preparse/Executing-to-Idle teardown first; no Scudo abort
or OMX PID restart is permitted. Stop for review if it fails.

Preserve fixture filename, byte size, SHA256 and complete ffprobe transcript proving HEVC
Main 8-bit yuv420p, 3840x2160, 30 fps, SDR BT.709, duration and audio codec. Reuse accepted
manual 1080p AVC control and review before one authorized short 4K attempt. Capture live
OMX creation, FBM allocation, FBD and teardown, boot ID/PID continuity, crash/tombstone
baseline/post state and thermal samples overlapping the bounded window. No playback or
boot loops. Retain all evidence outside Git.

RC-B is unchanged: the known 4K Mali crop/EGL failure may still restart SurfaceFlinger
and the framework. That outcome is not an RC-A2 failure unless the FBM heap/teardown
fault recurs; distinguish service resets caused by the graphics fatal. Stop at that first
boundary and review. Full 4K playback and under-load thermal qualification remain unproven.

## Governance

- Original RC-A: PHYSICAL REPAIR EFFECTIVE.
- RC-A2: PHYSICAL PASS / CLOSED on the subsequent verified physical evidence.
- RC-B: COMPAT1B IMPLEMENTATION READY / UNCHANGED; no compat1b patch included.
- P3-A: PHYSICAL FAIL. Main10/HDR/AFBC/protected: NOT AUTHORIZED.
- Canonical r7: PASS / FROZEN / UNCHANGED; Gate3: PASS_WITH_EXPLICIT_USER_WAIVER / CLOSED.
- Audio P1: CLOSED. P2: COMPLETE. r8: NOT AUTHORIZED / NOT BUILT.
- Full VINTF: inherited CONFIG_NFS_FS mismatch, exit 65, NOT PASS.
