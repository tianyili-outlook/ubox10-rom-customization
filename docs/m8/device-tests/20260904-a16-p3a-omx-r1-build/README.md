# a16-dev-p3a-omx-r1 offline build record

Date: 2026-09-04

Status: **OFFLINE CHECKED / RC-A PATCH IMPLEMENTED / PHYSICAL VALIDATION PENDING**

Classification: **P3-A RC-A REPAIR CANDIDATE / DEVELOPMENT ONLY / NOT r8 / NOT RELEASE**

This candidate implements only the approved Allwinner ARM32 OMX copy-path operand correction. It
does not implement RC-B/compat1b, enable 4K, expand the proven compat1a scope, or alter Main10, HDR,
AFBC or protected playback. P3-A remains **PHYSICAL FAIL / FORENSICS COMPLETE** until one bounded
hardware retest proves otherwise.

## Baseline and exact input

The repository started at `4ca27333b3b845864bd19de03f82e0cf51c70b5d` (`m8: assess P3-A OMX
drain repair readiness`). The image baseline is exact `a16-dev-audio-r1`, size 1,641,830,400 bytes,
SHA-256 `270B5D822AB3BB13D8EDCD9BE374DA1D6ED512D6D60063E123046C23B8AF9D62`.
The deterministic builder extracts the input from that candidate's `vendor_a.img`; it does not use a
donor copy.

| Property | Exact value |
|---|---|
| Installed path | `/vendor/lib/libOmxVdec.so` |
| ELF | ELF32 little-endian ARM |
| Input size | 83,780 bytes |
| Input SHA-256 | `29F500E3089651C41A4C2A88C1F82B99EE389AF7A83101CE929516018D5CEA87` |
| Input Build ID | `2042d7e0112320dc855cccee324af569` |
| Symbol / fault | `__anDrain+1212`, virtual address `0xe138` |
| Fault | `ldrd r3, r1, [r0, #0x9c]` with `r0 == NULL` |

The canonical readiness analysis is
[`../20260904-a16-p3a-omx-drain-repair-readiness/README.md`](../20260904-a16-p3a-omx-drain-repair-readiness/README.md).

## Exact machine-code correction

The patcher is `scripts/patch-a16-p3a-omx-r1.py`. It requires the exact input size, SHA-256 and
original bytes; uses one fixed offset; refuses an existing output; verifies the output hash and that
all bytes outside the approved instruction are unchanged; and never searches for an ambiguous byte
pattern.

| | Original | Patched |
|---|---|---|
| File offset | `0xd130` | `0xd130` |
| Virtual address | `0xe130` | `0xe130` |
| Bytes | `d8 f8 00 00` | `4f ea 0c 00` |
| Thumb-2 instruction | `ldr.w r0, [r8]` | `mov.w r0, r12` |
| Width / flags | 4 bytes / unchanged | 4 bytes / unchanged |

The AOSP `clang-r547379` assembler independently emitted `4f ea 0c 00` for `mov.w r0, r12`.
Both `clang-r547379` and `clang-r530567` LLVM disassemblers decode the patched bytes as that same
instruction. There is no relocation or branch target inside the replaced instruction. Because its
fourth byte was already `00`, the exact byte diff is three offsets: `0xd130`, `0xd131`, `0xd132`.

### Lifecycle proof

Before the patched instruction, `NextPictureInfo(decoder, 0)` returns in `r0`, is saved in `r6`, is
explicitly compared with NULL at `0xde7a`, and is retained as `r12` at `0xdea0`. The live value is
preserved through the geometry/port comparisons and spilled at `0xe128` where required. The original
instruction nevertheless reloaded `OmxDecoder+0x58e0` through `r8`; that current-display slot is not
populated until the later `RequestPicture` call.

The replacement only selects the already checked peek as the base of the existing
`VideoPicture+0x9c/+0xa0/+0xa4/+0xa8` color-aspect reads. It does not set flags, move a branch, call a
helper, acquire ownership or change stack/unwind state. The existing later sequence remains byte
identical:

```text
NextPictureInfo -> NULL check -> geometry/color/port evaluation using peek
                -> request OMX output buffer
                -> RequestPicture -> store current display picture -> NULL check
                -> copy/FBD -> ReturnPicture -> clear current slot
```

Thus `RequestPicture` still dequeues exactly once, FBD ordering is unchanged, and `ReturnPicture`
still releases the owned frame. The zero-copy branch does not pass through this instruction. No
resolution/4K predicate, early return, retry, frame drop or speculative fallback was added.

## Patched ELF identity and closure

| Property | Value |
|---|---|
| Patched size | 83,780 bytes |
| Patched SHA-256 | `5FE74A28EB9E083959FDAC9CFDE870FAA2AF4447DADB7776C1E7F4CFC6D1EE8B` |
| Changed bytes | exactly 3, all within the one 4-byte instruction |
| Build ID note | retained original `2042d7e0112320dc855cccee324af569` |

The proprietary GNU Build ID note is intentionally not rewritten, so it is no longer a sufficient
identity for the patched object. The patched SHA-256 above is canonical. ELF header, program headers,
section layout, dynamic section, SONAME/DT_NEEDED, dynamic imports/exports, relocations, ARM
attributes, permissions/ownership/SELinux label and mini-debug data are unchanged. The exact ARM32
vendor/VNDK31 strong-import closure has zero unmatched imports and no
`__libcpp_verbose_abort` import.

## Candidate construction and differential

The existing audio-r1 pipeline was reused without an Android or kernel build. Only a copied
`vendor_a` filesystem was edited, with original inode metadata restored before AVB/LP/outer
repacking.

| Artifact | Exact identity |
|---|---|
| Candidate | `a16-dev-p3a-omx-r1` |
| Flash image | `out/candidates/a16-dev-p3a-omx-r1/x12-a16-dev-p3a-omx-r1.img` |
| Image size | 1,641,830,400 bytes |
| Image SHA-256 | `B970A69C7670C4AE6DFFA3E06EA2317FAA7585B29EE5FA9F7D4740377A17C4A6` |

The signed-filesystem semantic delta from exact `a16-dev-audio-r1` is one file only:

```text
/vendor/lib/libOmxVdec.so
```

No file was added or removed. `system_a`, `product_a`, `vendor_dlkm_a`, boot/kernel and all other LP
partition contents remain byte-identical. The mechanically necessary outer payload changes are only
`Vsuper.fex`, `Vvbmeta_vendor.fex`, `super.fex` and `vbmeta_vendor.fex`; 44 other outer payloads,
including boot and top-level vbmeta, remain byte-identical.

## Preserved accepted runtime identities

| Runtime | Size | SHA-256 |
|---|---:|---|
| `/system/bin/surfaceflinger` | 8,577,592 | `06C960E672863AD557AF921565621997CB9B113BA2290049AF91028A405CD0A5` |
| `/vendor/lib/hw/android.hardware.audio@7.0-impl.so` | 170,476 | `E2F3D49D757AA4132180C3D247857FC9725D7113E92A079E10181AADBCC062ED` |
| `/system/lib64/libstagefright.so` | 2,079,968 | `3FDE0D408ED26CE76C7CAE2DB3DD41E38B1783B982CFAB251518D778C39F13CF` |
| `/vendor/lib/hw/gralloc.apollo.so` | 64,852 | `7E654E0F9D968C5FA9C9F31893E0E60DCF6605E41A82783E6376A1D7D66194D5` |
| `/vendor/lib64/hw/gralloc.apollo.so` | 93,664 | `1F91BF6FA547DA11E42068C1A0C612E41B5C800AEE9CDAB2D320DD469295CB19` |

This preserves the physically accepted compat1a SurfaceFlinger lineage and audio-r1 HIDL repair.
It does not reopen either physical gate.

## Offline gates

- deterministic patcher negative/positive tests and dual-disassembler proof: PASS;
- ext4/e2fsck for system, vendor, product and vendor_dlkm: PASS;
- exact one-file filesystem delta and exact three-byte ELF delta: PASS;
- system/vendor/vbmeta AVB, LP metadata/extents and sparse-to-raw roundtrip: PASS;
- IMAGEWTY outer integrity and exact payload-delta classification: PASS;
- system-side VINTF: PASS, exit 0;
- full VINTF: **NOT PASS**, inherited `CONFIG_NFS_FS=y` versus FCM-6 `n`, exit 65 only;
- canonical r7, Gate 3, compat1a, audio P1 and P2 governance regression: PASS.

## One bounded future physical validation contract

No flash or device action is authorized by this record. A later explicitly authorized session must
make exactly one manual HEVC Main 8-bit SDR 3840x2160p30 attempt—no loop, stress, autoplay or Main10.

Before playback, preserve the fixture independently: filename, exact byte size, SHA-256, complete
`ffprobe` transcript, 3840x2160 dimensions, exact 30 fps rational, HEVC Main profile/level, 8-bit
`yuv420p`, SDR BT.709 color tags, duration and audio codec.

The evidence window must establish:

1. stable boot ID and baseline PIDs, including `vendor.media.omx`;
2. exact SPS/output geometry and port-settings-change sequence;
3. `NextPictureInfo` → `RequestPicture` → output/FBD → `ReturnPicture` progression;
4. no `__anDrain` SIGSEGV and continuous OMX service PID;
5. exact 4K format, usage, stride, planes, allocation, native handle and sidecar state;
6. AHardwareBuffer/native-client-buffer and EGL/Skia results before any framework restart;
7. crash/tombstone and critical-PID census afterward.

If RC-A progresses to the known 3840x2160 YV12 graphics boundary, stop after capturing that first
failure. Do not implement or test compat1b in the same experiment. Visible picture success is not
required to establish RC-A success, but P3-A itself cannot pass without the later graphics/display,
system-continuity and user-visible gates.

## Governance and limitations

- Canonical r7 remains **PASS / FROZEN / UNCHANGED**.
- Gate 3 remains **PASS_WITH_EXPLICIT_USER_WAIVER / CLOSED**.
- Compat1a remains **PHYSICAL PASS for authorized SDR 1080p YV12 only / UNCHANGED**.
- Audio P1 remains **CLOSED**; P2 remains **COMPLETE**.
- P3-A remains **PHYSICAL FAIL / FORENSICS COMPLETE**.
- RC-A is **PATCH IMPLEMENTED OFFLINE / CANDIDATE BUILT / PHYSICAL VALIDATION PENDING**.
- RC-B/compat1b: DEFERRED / EXPECTED NEXT BOUNDARY / UNCHANGED.
- P3-B Main10: NOT AUTHORIZED. HDR, AFBC and protected playback are also not authorized.
- Full VINTF remains inherited exit 65 and is not PASS.
- `r8` remains **NOT AUTHORIZED / NOT BUILT**.

No ADB command, physical device access, flash, reboot, playback or physical test occurred while
building and auditing this candidate.
