# a16-dev-p3a-compat1b-r1

P3-A RC-B COMPAT1B CANDIDATE / DEVELOPMENT ONLY / NOT r8 / NOT RELEASE.

Status: **OFFLINE CHECKED / CANDIDATE BUILT / PHYSICAL VALIDATION PENDING**.
Physical validation has **not** been executed for this candidate.
P3-A remains **PHYSICAL FAIL**. RC-A remains **PHYSICAL REPAIR EFFECTIVE**;
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

## First physical test — prepare only, no device action in this task

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

Remaining uncertainty: the same metadata collision is very-high-confidence, not prior physical
proof of 4K translation. A further pixel-storage/Mali/HWC limitation may appear after removing
the crop collision. Preserve the first failing boundary; do not widen this predicate automatically.
