# a16-prototype-b-r7-hevc-abi-compat1a-sdr-shadow-fd

Status: **OFFLINE CHECKED / READY FOR PHYSICAL BOOT GATE / EXPERIMENTAL REPAIR / NOT r8 / NOT RELEASE**

This candidate is based on exact compat1 (`D4FAFE24...EFAAB`). Canonical r7 remains frozen and
Gate 3 remains HOLD. It corrects only the shadow-fd implementation blocker observed physically in
compat1; it does not broaden the SDR YV12 ABI repair hypothesis.

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

## Mandatory physical order

Use `scripts/capture-a16-prototype-b-r7-hevc-abi-compat1a-sdr-shadow-fd.ps1` with PowerShell 7,
explicit `C:\platform-tools\adb.exe`, and the current device LAN IP. The helper enforces state
tokens and this order:

1. flash → normal boot → `BootGate` → stop and review → `ReviewBootGate -ConfirmBootGatePass`;
2. only after BootGate PASS: `PrepareMedia` installs/verifies ARM64 VLC, creates
   `/sdcard/Movies/UBOX10-COMPAT1A/`, pushes both fixtures, verifies them, and first-launches VLC;
3. complete onboarding/permissions/media scan, verify both files visible without playback, then
   `ConfirmMediaReady -ConfirmMediaReady`;
4. `AVCPre` → `AVCLive` → one manual AVC → `AVCPost` → stop/review → explicit `ReviewAVC`;
5. only after AVC PASS: `HEVCPre` → `HEVCLive` → exactly one manual SDR HEVC → `HEVCPost` → stop;
6. only after reviewed stable: interaction, AVC regression, then `Final`.

No VLC install, media copy, first launch or playback is permitted before BootGate review PASS. No
formal capture starts before VLC first-run setup is complete. Playback remains manual; no reboot,
player input or HEVC repeat is automated. Main10, HDR, AFBC, protected playback and 4K remain
unauthorized. No physical PASS is claimed.
