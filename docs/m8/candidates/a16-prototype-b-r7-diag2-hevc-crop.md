# a16-prototype-b-r7-diag2-hevc-crop

Status: **OFFLINE CHECKED / READY FOR PHYSICAL VALIDATION / DIAGNOSTIC ONLY / NOT r8 / NOT A RELEASE**

This exact `a16-prototype-b-r7-diag1a` derivative runs one causal experiment: keep the HEVC
coded/allocation buffer at 1920x1088 while retaining the stream-visible 1920x1080 crop. It does not
claim that HEVC is fixed; Gate 3 remains HOLD until physical validation.

## Evidence and source audit

The read-only evidence under `/work/evidence/ubox10/r7-diag2-hevc-crop/` was independently hashed
and reconstructed before source modification. Its `SHA256SUMS.txt` is
`6FD308B77A4D19234E3EE33584EE01DC515F701AFC7EEB6E96270091CBBE39C5`; per-file hashes are locked in
the machine record. It remains external and uncommitted.

| Stage | AVC control | HEVC reproduction |
|---|---|---|
| Component | `OMX.allwinner.video.decoder.avc` | `OMX.allwinner.video.decoder.hevc` |
| Initial output/crop | 1920x1080 YV12; `(0,0)-(1919,1079)` | same |
| Post-change coded / native crop | 1920x1088 / 1920x1080 | 1920x1088 / 1920x1088 |
| Usage / allocation | `0x402d00`; linear 3-plane YV12; 3,133,504 bytes; modifier 0; AFBC 0 | same |
| Import | remote import, AHB and native client buffer succeed | same |
| EGL / backend | EGL and GL succeed; valid=1 | crop warning; `EGL_BAD_ALLOC 0x3003`; GL not reached; valid=0 |
| Terminal event | visible playback survives | unchanged RenderEngine fatal / SurfaceFlinger SIGABRT |

`ACodec::getPortFormat()` obtains `OMX_IndexConfigCommonOutputCrop` from the component through the
direct `OMXNodeInstance`/`OMX_GetConfig` transport. The Allwinner implementation is proprietary
ARM32 `libOmxVdec.so`. On port-settings change, `onOutputFormatChanged()` retains the initial
1920x1080 base format, then re-queries the aligned port and crop. `SurfaceUtils` sets coded size,
format and usage but not visible crop; `onOutputBufferDrained()` passes the format crop to the native
window. The precise hypothesis is that the HEVC component incorrectly promotes visible crop to its
aligned coded height, producing the first proven semantic difference immediately before EGL fails.

## Exact delta

The isolated overlay is
`configs/aosp/architecture-ceiling-a16/diagnostics/r7-hevc-diag2-hevc-crop/`. Its sole patch changes
`frameworks/av/media/libstagefright/ACodec.cpp`. One `setRect("crop", ...)` executes only for exact
Allwinner HEVC, base 1920x1080/full-visible YV12, and new 1920x1088/full-coded YV12. A non-match keeps
diag1a behavior. Coded/allocation dimensions remain 1920x1088.

| Runtime path | diag1a | diag2 | ELF contract |
|---|---|---|---|
| `/system/lib64/libstagefright.so` | 2,067,648 / `B0D1E7D7...B16F` | 2,071,728 / `BD48A769...D113` | ELF64 AArch64; SONAME, DT_NEEDED, strong exports and undefined strong imports identical |

This is the only diag1a filesystem delta. SurfaceFlinger, ARM32/ARM64 gralloc and the full vendor
tree are byte-identical. All `UBOX_R7_DIAG1` stages and the original fatal remain.

## Image and gates

- Image: `out/candidates/a16-prototype-b-r7-diag2-hevc-crop/x12-a16-prototype-b-r7-diag2-hevc-crop.img`
- Size: **1,641,785,344 bytes**
- SHA-256: **`6F67CAE0B8A445D4597DECE9D684A7099ADF3E4E046D54E635D269C9E9E483EE`**
- Packaging consequences: only `super.fex`, `Vsuper.fex`, `vbmeta_system.fex` and
  `Vvbmeta_system.fex`; the other 46 payloads are byte-preserved.
- Android 16/API36, mixed ABI/`zygote64_32`, app_process32/64, VNDK31/BoringSSL dual arch,
  ARM32/64 graphics/SP-HAL closure, AVB, LP, 5.4.302+ boot/kernel and 22 vendor_dlkm modules pass.
- System-only VINTF passes. Full VINTF remains **exit 65**, solely inherited
  `CONFIG_NFS_FS=y` versus FCM-6 `n`; **NOT PASS**.

Next: flash this exact hash, confirm normal boot, then run one AVC control and one HEVC reproduction.
Only physical evidence may determine whether EGL import now succeeds. HEVC remains blocked.
