# a16-prototype-b-r7-hevc-abi-compat1a-sdr-shadow-fd

Status: **PHYSICAL PASS — AUTHORIZED SDR 1080P YV12 SCOPE ONLY / EXPERIMENTAL REPAIR / NOT r8 / NOT RELEASE**

This candidate is based on exact compat1 (`D4FAFE24...EFAAB`). Canonical r7 remains frozen and
The later Gate 3 governance result is `PASS_WITH_EXPLICIT_USER_WAIVER`; this candidate itself still
proves only the bounded media subgate. It corrects only the shadow-fd
implementation blocker observed physically in compat1; the completed physical result does not
broaden the SDR YV12 ABI repair scope.

## Physical compat1 result and exact cause

The read-only bundle `/work/evidence/ubox10/r7-compat1-physical-fail/unpacked` verifies 49/49 files
against the uploaded `SHA256SUMS.linux`. BootGate and AVC passed. HEVC reached the exact compat1
eligibility gate, then `ashmem_create_region(...,24576)` returned a legacy `/dev/ashmem<boot_id>`
character-device fd whose `fstat().st_size` was 0. Translation and the cloned AHardwareBuffer view
were never reached; fail-closed use of the original view reproduced the established
`EGL_BAD_ALLOC`, invalid BackendTexture and SurfaceFlinger userspace restart.

Android libcutils enables its memfd branch only when Treble is enabled, `sys.use_memfd=true`, and
the kernel passes the ashmem-on-memfd ioctl probe. Otherwise it opens `/dev/ashmem<boot_id>` and
stores the region length through `ASHMEM_SET_SIZE`. Kernel 5.4 keeps that length in
`ashmem_area::size`; the character-device inode observed by `fstat` remains size zero. The proper
legacy ashmem query is `ASHMEM_GET_SIZE`, but using it would not satisfy this candidate's required
ordinary-file size proof.

## Minimal source delta

The separate overlay is
`configs/aosp/architecture-ceiling-a16/diagnostics/r7-hevc-abi-compat1a-sdr-shadow-fd/`.
Only these exact compat1 Skia sources change:

- `external/skia/src/gpu/ganesh/gl/UBOXR7Compat1Metadata.h`: add a small helper matching
  libcutils's internal memfd path: `memfd_create` syscall with `MFD_CLOEXEC|MFD_ALLOW_SEALING`,
  `ftruncate(0x6000)`, then `F_SEAL_GROW|F_SEAL_SHRINK`;
- `external/skia/src/gpu/ganesh/gl/AHardwareBufferGL.cpp`: replace only
  `ashmem_create_region` with that helper and emit `fd_type=memfd_ftruncate_sealed`.

Eligibility, original-fd2 read-only mapping, full-sidecar copy, the complete 56-byte attr copy
23544..23599 → `0x80..0xb7`, verification, handle clone, fd2-only replacement,
`AHARDWAREBUFFER_CREATE_FROM_HANDLE_METHOD_CLONE`, EGL flow and fail-closed fatal behavior are
unchanged. No global property or sanitizer changed.

The bounded memfd is appropriate because this consumer-only view remains inside ARM64
SurfaceFlinger's mapper/Mali import path. The open-source mapper maps fd2 with `MAP_SHARED` and does
not issue ashmem ioctls. Mali's proven consumer behavior is mmap/read. The fd does not return to the
legacy ARM32 decoder, avoiding the cross-vendor ashmem-ioctl concern documented by libcutils.

Ownership is unchanged: the helper owns the initial fd; every pre-clone failure closes it. The
temporary native-handle clone takes that fd after its duplicated old fd2 is closed.
`AHardwareBuffer_createFromHandle(CLONE)` duplicates/imports it; the temporary handle is then
closed/deleted exactly once. The AHardwareBuffer owns the imported clone and is released after
`eglCreateImageKHR`, which holds its own reference on success. Host tests prove close/EBADF and
sealed size; static and ELF checks prove no new ownership/import surface.

## Runtime delta

| Runtime path | compat1 SHA-256 | compat1a SHA-256 | Result |
|---|---|---|---|
| `/system/bin/surfaceflinger` | `97A476E550015C50CA92302418B6625171995192161A37EBB3EBD7AF7102745C` | `06C960E672863AD557AF921565621997CB9B113BA2290049AF91028A405CD0A5` | only semantic runtime delta |
| `/system/lib64/libstagefright.so` | `3FDE0D408ED26CE76C7CAE2DB3DD41E38B1783B982CFAB251518D778C39F13CF` | same | byte-identical |
| `/vendor/lib/hw/gralloc.apollo.so` | `7E654E0F9D968C5FA9C9F31893E0E60DCF6605E41A82783E6376A1D7D66194D5` | same | byte-identical |
| `/vendor/lib64/hw/gralloc.apollo.so` | `1F91BF6FA547DA11E42068C1A0C612E41B5C800AEE9CDAB2D320DD469295CB19` | same | byte-identical |

SurfaceFlinger remains ELF64/AArch64 and preserves SONAME, DT_NEEDED, strong exports and the full
strong-undefined set relative to compat1. All `UBOX_R7_DIAG1`, `UBOX_R7_DIAG3`,
`UBOX_R7_COMPAT1` stages and the original RenderEngine fatal remain. Vendor, Mali, OMX/Cedar,
mapper/gralloc, HWC/display, audio, Wi-Fi, product, boot, kernel and vendor_dlkm are unchanged.

## Image and offline gates

- Image: `out/candidates/a16-prototype-b-r7-hevc-abi-compat1a-sdr-shadow-fd/x12-a16-prototype-b-r7-hevc-abi-compat1a-sdr-shadow-fd.img`
- Size: **1,641,822,208 bytes**
- SHA-256: **`9E9592BF420F40A386BC347B027A85B2F9ED0A44DDB132BDBAB9882905F75722`**
- Source identity: Android 16/API36, BP2A.250805.034, external/skia
  `4c18a9680d52c2cd5e35cfef2f548635a445fafe`; only `surfaceflinger` was rebuilt.

The exact shared header passes host ASan/UBSan tests for fstat size 24576, shared RW/RO mappings,
grow/shrink seals, close/no stale fd, exact 56-byte copy and unchanged original. Ext4,
sparse/raw, signed filesystem, AVB, exact LP geometry/extents, Android/API identity, mixed ABI,
`zygote64_32`, app_process32/64, VNDK31 dual arch, BoringSSL32/64, ARM32/ARM64 graphics closure,
SP-HAL, boot/kernel 5.4.302+ and 22-module vendor_dlkm checks pass. System-only VINTF passes. Full
VINTF remains **exit 65 / inherited `CONFIG_NFS_FS=y` versus FCM-6 `n` / NOT PASS**.

## Physical validation result

The exact image above, produced by commit
`a4c621f952a5ad3a724a44e411236922c4507f54`, was physically validated on 2026-08-31. The external,
read-only evidence under `/work/evidence/ubox10/r7-compat1a-physical-pass/unpacked` verifies
**107/107** entries against its original `SHA256SUMS`; raw evidence and the uploaded ZIP remain
outside Git. The machine-readable result is
`a16-prototype-b-r7-hevc-abi-compat1a-sdr-shadow-fd-physical-result.json`.

The executed order was BootGate and explicit review first; only then VLC install, both fixture
transfers, size verification, first-launch/onboarding/permissions/scan, formal AVC control and
review, and the primary single SDR HEVC test. A playback after the first HEVC run is retained only
as **SUPPLEMENTAL / UNPLANNED AVC AFTER HEVC**, not the formal regression because it lacked
`AVCRegressionPre`. A second authorized HEVC session covered pause/resume, seek and back, followed
by the separately captured formal AVC regression and Final census.

Both the primary and interaction HEVC sessions contain 14 distinct buffers with the complete path:

```text
eligible=1
shadow_created=1 fd_type=memfd_ftruncate_sealed size=24576
translated=1 src_offset=23544 dst_offset=128 bytes=56
original_prot=read original_unchanged=1 attr_copy=1
view_created=1 method=CLONE original_fd2_unchanged=1
egl_import_result=1 view=sdr_shadow client_buffer_null=0
EGL_CREATE_IMAGE result=1
BACKEND_TEXTURE valid=1
```

The formal initial AVC and formal AVC regression each contain nine buffers with
`eligible=0 reason=metadata_gate`, `sunxi_flag=0xffffffff`, all four legacy crop words `-1`,
`view=original`, successful EGL import and valid backend textures. Operator observations record
normal picture and HDMI audio for both AVC runs, primary HEVC and the interaction session;
pause/resume, seek and back all pass.

BootGate through Final retains boot ID `3dd67a8e-fe9f-46f7-b35d-fb34bd264217`, SurfaceFlinger PID
543, zygote PIDs 493/494 and system_server PID 782. HEVCPost and Final crash buffers are empty; the
BootGate and Final tombstone listings are byte-identical and contain only the pre-existing boot-time
ARM32 audio-service crash. No `EGL_BAD_ALLOC`, invalid texture, SurfaceFlinger SIGABRT, framework/
zygote restart, recovery screen or quarter-screen recovery occurs after formal capture begins.

Therefore **COMPAT1A SDR YV12 REPAIR = PHYSICAL PASS** and authorized SDR AVC+HEVC functional
preservation is PASS. This proves that the decoder-owned extended metadata can remain untouched
while an isolated, read-only-derived 56-byte legacy shadow at the ARM64 Mali boundary imports
successfully. It does **not** validate Main10, HDR, AFBC, protected content or 4K.

The subsequent 2026-09-01 Gate 3 session is recorded separately in
`a16-prototype-b-r7-gate3-physical-result.json`: 3A/3B/3D/3E pass, and 3C closes with the explicit
user waiver for POWER current-session revalidation. Overall Gate 3 is therefore
**`PASS_WITH_EXPLICIT_USER_WAIVER` / CLOSED**, not bare PASS. This does not broaden compat1a beyond
authorized SDR 1080p YV12. Canonical r7 remains frozen, r8 remains unauthorized/unbuilt, and
`codex/m8-a16-development` remains uncreated.

The formal helper already creates `crash-buffer.txt` even when `logcat -b crash` is empty, as proven
by the zero-byte AVCPost/HEVCPost/InteractionPost/regression/Final artifacts; no helper code change is
needed. Fixture verification compares host and device **file sizes only**. It is not SHA-256 or
byte-for-byte content verification.

## Reproducible physical order

Use `scripts/capture-a16-prototype-b-r7-hevc-abi-compat1a-sdr-shadow-fd.ps1` with PowerShell 7,
explicit `C:\platform-tools\adb.exe`, and the current device LAN IP. The helper enforces state
tokens and this order:

1. flash → normal boot → `BootGate` → stop and review → `ReviewBootGate -ConfirmBootGatePass`;
2. only after BootGate PASS: `PrepareMedia` installs/verifies ARM64 VLC, creates
   `/sdcard/Movies/UBOX10-COMPAT1A/`, pushes both fixtures, verifies host/device sizes, and
   first-launches VLC;
3. complete onboarding/permissions/media scan, verify both files visible without playback, then
   `ConfirmMediaReady -ConfirmMediaReady`;
4. `AVCPre` → `AVCLive` → one manual AVC → `AVCPost` → stop/review → explicit `ReviewAVC`;
5. only after AVC PASS: `HEVCPre` → `HEVCLive` → exactly one manual SDR HEVC → `HEVCPost` → stop;
6. only after reviewed stable: interaction, AVC regression, then `Final`.

No VLC install, media copy, first launch or playback is permitted before BootGate review PASS. No
formal capture starts before VLC first-run setup is complete. Playback remains manual; no reboot,
player input or HEVC repeat is automated. Main10, HDR, AFBC, protected playback and 4K remain
unauthorized and not physically validated by this session.
