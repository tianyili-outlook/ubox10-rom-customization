# a16-prototype-b-r7-diag3a-private-buffer-metadata

Status: **PHYSICAL AVC PASS / HEVC REPRODUCED / METADATA ABI ROOT CAUSE PROVEN / DIAGNOSTIC CLOSED / NOT r8 / NOT A RELEASE**

Diag3a is based on exact diag3 and corrects only diag3's own ARM64 libstagefright hashing regression.
It does not change the private-buffer hypothesis, codec, crop, dimensions, usage, allocator, sidecar,
OMX/Cedar, Mali EGL, HWC, or RenderEngine fatal behavior. Canonical r7 remains frozen and Gate 3
remains HOLD.

## Proven physical regression and exact correction

The read-only files under
`/work/evidence/ubox10/r7-diag3a-instrumentation-regression/input/unpacked/` verify against manifest
SHA-256 `F7154E0B73095428E7DE79DCE451F1404BA157E43D32D389A8E0BCB7FC866029`.
Diag3 booted normally, but two AVC attempts produced the same ARM64 VLC CodecLooper SIGABRT:
`__ubsan_handle_mul_overflow_minimal_abort -> ubox_r7_diag3_snapshot ->
ACodec::allocateOutputBuffersFromNativeWindow`. Register values include FNV offset basis
`0xcbf29ce484222325` and sidecar length `0x6000` (24,576 bytes). The failure is before OMX
`useBuffer`, decoder/FBM use, and `CODEC_POST_FBD`; HEVC was not tested.

The actual compiler contracts are:

| Target | Actual integer-overflow sanitizer |
|---|---|
| ARM64 `libstagefright` / ACodec | signed + unsigned, minimal runtime, non-recovering |
| SurfaceFlinger's Skia `AHardwareBufferGL.cpp` | none |
| ARM32 `gralloc.apollo` | none; r7 VNDK31 libc++ preinclude retained |
| ARM64 `gralloc.apollo` | none; r7 VNDK31 libc++ preinclude retained |

FNV-1a requires unsigned modulo-2^64 multiplication. A function-only
`no_sanitize("unsigned-integer-overflow")` was validated as technically effective, but rejected
because it suppresses checking. The selected three-line replacement uses
`__builtin_mul_overflow(hash, FNV_PRIME, &wrapped_hash)` and assigns the wrapped result. It preserves
the exact FNV value, disables no sanitizer, and adds no branch to the diagnostic hash path.

The mechanically separate overlay is
`configs/aosp/architecture-ceiling-a16/diagnostics/r7-hevc-diag3a-private-buffer-metadata/`. It has
revision and exact pre/post hash guards plus verified apply/check/revert behavior. Its only changed
source is `frameworks/av/media/libstagefright/UBOXR7Diag3PrivateHandle.h`; the helper changes from
12,063 bytes / `DEF12B...` to 12,154 bytes /
`B5FC7A29869836E35A8A4F9B31E0D9386609DA013336C04EBB93DF01DAE5EA47`.

## FNV and UBSan proof

`scripts/check-a16-prototype-b-r7-diag3a-fnv.py` extracts the actual corrected AOSP helper and builds
it with the same Android Clang and equivalent signed/unsigned non-recovering minimal UBSan flags.
The old control aborts with `ubsan: mul-overflow`; the corrected helper produces no UBSan record and
matches these fixed values:

| Input | Bytes | FNV-1a 64 |
|---|---:|---|
| empty | 0 | `CBF29CE484222325` |
| `a` | 1 | `AF63DC4C8601EC8C` |
| `foobar` | 6 | `85944171F73967E8` |
| bytes 0..255 | 256 | `4242DC5249C33625` |
| all `FF` sidecar | 24,576 | `720923C139C50325` |
| deterministic sidecar pattern | 24,576 | `B988DE2317596325` |

The unstripped AArch64 helper contains ordinary `mul` instructions and no call to
`__ubsan_handle_mul_overflow*` within `ubox_r7_diag3_snapshot`; libstagefright's unrelated sanitizer
coverage remains present.

## Exact diag3 to diag3a runtime delta

| Runtime path | diag3 SHA-256 | diag3a SHA-256 | Result |
|---|---|---|---|
| `/system/bin/surfaceflinger` | `5BD92DAB98969B774469ED6581E9CD32D9C57E93D63A4CF0E126414B568CE838` | same | byte-identical |
| `/system/lib64/libstagefright.so` | `4C1382C512867E5CE3CC324D927D871B200E6A352179FCE34AF27B4699CBA2C7` | `3FDE0D408ED26CE76C7CAE2DB3DD41E38B1783B982CFAB251518D778C39F13CF` | only semantic runtime delta |
| `/vendor/lib/hw/gralloc.apollo.so` | `7E654E0F9D968C5FA9C9F31893E0E60DCF6605E41A82783E6376A1D7D66194D5` | same | byte-identical |
| `/vendor/lib64/hw/gralloc.apollo.so` | `1F91BF6FA547DA11E42068C1A0C612E41B5C800AEE9CDAB2D320DD469295CB19` | same | byte-identical |

The signed-filesystem comparison reports exactly `system/lib64/libstagefright.so`; the vendor tree
has no changed file. SONAME, DT_NEEDED, strong exports and undefined strong imports are identical.
All `UBOX_R7_DIAG1` records and the five `UBOX_R7_DIAG3` boundaries `ALLOC_INITIAL`,
`REMOTE_IMPORT`, `CODEC_PRE_USE`, `CODEC_POST_FBD`, and `EGL_PREIMPORT` remain. The original
RenderEngine fatal is byte-preserved in SurfaceFlinger.

## Candidate and offline result

- Image: `out/candidates/a16-prototype-b-r7-diag3a-private-buffer-metadata/x12-a16-prototype-b-r7-diag3a-private-buffer-metadata.img`
- Size: 1,641,818,112 bytes
- SHA-256: `666099016529032EEB80A49BBDACF1BF4FDC86859D9538B84C8F9660D1F232D9`
- Source: Android 16/API36, `BP2A.250805.034`; only `libstagefright` was rebuilt; kernel was not.

Ext4, sparse/raw integrity, AVB, exact LP geometry/extents, Android identity, mixed ABI and
`zygote64_32`, app_process32/64, VNDK31 dual arch, BoringSSL32/64, mapper/gralloc/Mali closure,
SP-HAL, boot/kernel 5.4.302+, and the 22-module vendor_dlkm inventory pass. ARM32 and ARM64 graphics
closures have zero unmatched strong imports. System-only VINTF passes. Full VINTF remains exit 65
for inherited `CONFIG_NFS_FS=y` versus FCM-6 `n`; it is **NOT PASS** and was not changed.

## Subsequent physical result

The read-only paired evidence at `/work/evidence/ubox10/r7-diag3a-avc-hevc/unpacked/` verifies
against SHA256SUMS file SHA-256
`D08322A1F8A3945B9008D3F24D4E35C382708903C7C38D20805AE113E934FA89`.
AVC picture/audio and every diagnostic boundary passed without the former UBSan abort or
`EGL_BAD_ALLOC`. One HEVC run localized a deliberate 23,480-byte Allwinner metadata initialization
between ARM32 codec import and `CODEC_POST_FBD`. Static proprietary-ELF analysis then proved the
consumer ABI collision: Mali r20p0 treats active extended-metadata HDR10+ LUT words at fd2 offsets
`0x80..0x8c` as a legacy signed crop. AVC leaves them negative; HEVC initializes them to
non-negative LUT values, causing Mali crop rejection and `EGL_BAD_ALLOC`.

This is intentional producer metadata, not random corruption. Diag3a completed its diagnostic
purpose; HEVC remains blocked because no repair candidate has yet passed physical validation.

## Historical AVC-only gate plan

Use `scripts/capture-a16-prototype-b-r7-diag3a-private-buffer-metadata.ps1` with PowerShell 7 and
`C:\platform-tools\adb.exe`. Run phases separately: `BootGate`, `AVCPre` (optionally
`-ClearLogcat` after its saved baseline), `AVCLive`, manually play the known-good AVC fixture once,
then `AVCPost`. Stop there; do not test HEVC until AVC preservation is reviewed.

AVC succeeded under these criteria. The later HEVC reproduction did not fix HEVC and did not change
Gate 3 from HOLD.
