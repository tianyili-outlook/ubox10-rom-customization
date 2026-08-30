# Android 16 Prototype B r7-diag1a

Status: **OFFLINE CHECKED / READY FOR PHYSICAL BOOT GATE**.

This is the bounded boot-compatibility correction for failed diagnostic candidate r7-diag1. It is
**instrumentation only, not an HEVC repair, not r8, not a release**. Canonical r7 remains the exact
physical architecture pass and frozen baseline. Gate 3 remains HOLD; H.264 remains PASS and HEVC
remains BLOCKED. HEVC is not fixed, and the first discriminating AVC-versus-HEVC buffer/import field
is still unproven.

## Candidate identity

| Item | Value |
|---|---|
| ID | `a16-prototype-b-r7-diag1a` |
| exact base | failed r7-diag1, 1,641,781,248 bytes, `A68E7BD75D9819794BE22E9E05BE76969B2883DF8965DC277482E8C99231C6A4` |
| image | `out/candidates/a16-prototype-b-r7-diag1a/x12-a16-prototype-b-r7-diag1a.img` |
| size | 1,641,781,248 bytes |
| SHA-256 | `C08F61D326BB49E2F27EEE4A2E38DF0843DA27EB3119F1712C26E2ECC035C765` |
| Android | `android-security-16.0.0_r7`, BP2A.250805.034, API 36 |
| diagnostic prefix | `UBOX_R7_DIAG1` (unchanged) |
| physical result | not yet validated |

Source revisions are manifest `ebea28d151539ecf0730b1a4ab92ac33edc17ac9`, frameworks/native
`d862b53356dc26794fb5451782806979c46e6769`, external/skia
`4c18a9680d52c2cd5e35cfef2f548635a445fafe`, frameworks/av
`d1137ad4b24b686d9b00fd1b7be1b520f7b6ee2b`, hardware/interfaces
`b553275c84253b074a8532a6ff0f4406c43e606e`, and unchanged kernel source
`027ef79e8facb73cb2419b4a08c0bd3f13a2206e`.

## Proven diag1 boot failure

Exact diag1 UART/runtime evidence proves `/vendor/lib/hw/gralloc.apollo.so` cannot complete eager
dynamic linking:

```text
dlopen failed: cannot locate symbol
"_ZNSt3__122__libcpp_verbose_abortEPKcz"
referenced by "/vendor/lib/hw/gralloc.apollo.so"
```

The failed ELF32 gralloc has that strong undefined import; exact retained ARM32 VNDK31 `libc++.so`
(`024166A8D757124C2C6F32BA7B3F2425C29206971D0A243A2783B1607ED590CC`) does not export it.
The gralloc service restart prevents composer from obtaining a gralloc module. SurfaceFlinger's
repeated `failed to create composer client` abort is downstream. Conditional YV12 logging was never
reached, so this evidence is not an HEVC/RenderEngine result.

## Exact compatibility mechanism

Diag1a reuses the documented r7 libc++ back-deploy boundary. A separate overlay at
`configs/aosp/architecture-ceiling-a16/diagnostics/r7-hevc-diag1a/` adds the existing gralloc
preinclude to `LOCAL_CPPFLAGS_32` and extends its architecture guard to ARM:

```c
#define _LIBCPP_VERBOSE_ABORT(...) __builtin_abort()
```

This preserves fatal abort semantics while avoiding a post-VNDK31 diagnostic-symbol import. The
one patch changes only donor `Android.mk` and `vndk31_libcpp_backdeploy.h`; it does not change
allocator, format, usage, plane, AFBC, codec, native-window, RenderEngine, EGL/GL, HWC, or fatal-path
source. It applies only after the isolated diag1 instrumentation overlay, so canonical r7 and closed
diag1 remain reproducible.

Only `device_gralloc.apollo_32_all_targets` was rebuilt. The ARM64 gralloc output was hash-checked
before packaging and was not rebuilt.

## ELF proof and permanent closure guard

| Field | failed diag1 ARM32 gralloc | corrected diag1a ARM32 gralloc |
|---|---|---|
| size | 57,660 | 57,388 |
| SHA-256 | `2833B9B8115D2516891CCD295D97E5BDBDB014F7EC8E336868E575D3BDFF36B5` | `F0BE5076BF4607F15691CFBB60D12F988E798ED92E0C4E0C5FBBB6F19D148089` |
| Build ID | `230481b4434fbbb4c8bfa062d277f208` | `6026336ccf642f3a10c356176da48c98` |
| ELF / machine | ELF32 / ARM | ELF32 / ARM |
| SONAME | `gralloc.apollo.so` | `gralloc.apollo.so` |
| DT_NEEDED | same ordered 12 entries | same ordered 12 entries |
| strong exports / HMI | identical / present | identical / present |
| strong undefined count | 47 | 47 |
| unmatched in exact namespace | `_ZNSt3__122__libcpp_verbose_abortEPKcz` | none |
| abort boundary | unavailable verbose-abort import | ordinary `abort` import, resolved by retained bionic libc |

`scripts/check-a16-prototype-b-r7-graphics.py` now performs the same generic undefined-strong-import
closure for ARM32 or ARM64. It resolves every DT_NEEDED provider through the exact generated SP-HAL
linker namespace, collects providers' strong exports, and fails on the set difference. The diag1a
builder runs it before packaging; the auditor reruns it on the mounted signed image. Both checks also
deliberately run against failed diag1 and reproduce its single unmatched symbol. This checks imports,
not merely exports or a binary string.

## Exact diag1 to diag1a delta

The signed filesystem comparison is:

```text
system added=[] removed=[] changed=[]
vendor added=[] removed=[] changed=[lib/hw/gralloc.apollo.so]
product changed=[]
vendor_dlkm changed=[]
```

Only `/vendor/lib/hw/gralloc.apollo.so` changes semantically. It remains ELF32 ARM, retains the exact
diag1 allocator instrumentation and `GRALLOC_ALLOC`/`GRALLOC_HANDLE` records, and preserves mode,
owner, SELinux label, SONAME, DT_NEEDED order, strong exports, and HMI.

These other diagnostic runtime files are byte-identical to diag1:

| Path | Size | SHA-256 |
|---|---:|---|
| `/system/bin/surfaceflinger` | 8,565,352 | `E2B780E955FC87356533FC9B50C0F9D78561070681C5D2D4DAD877AC777A2A73` |
| `/system/lib64/libstagefright.so` | 2,067,648 | `B0D1E7D72DFCEA20B72088AC9F3BC3E57AE983FD2DC5470494C6AB7404A5B16F` |
| `/vendor/lib64/hw/gralloc.apollo.so` | 81,344 | `F12C8F1B3CA3F967367E32A44EF043BF0EE660B1D36B175D3736B059A31947F8` |

The outer packaging consequence is exactly `super.fex`, `Vsuper.fex`, `vbmeta_vendor.fex`, and
`Vvbmeta_vendor.fex`; 46 of 50 outer payloads are byte-identical to diag1. `system_a` and
`vbmeta_system` are byte-identical. Vendor AVB/vbmeta and the containing sparse super bytes change
only because the corrected signed vendor filesystem is repackaged. LP geometry, metadata slots,
partition extents and empty B slots remain exact.

## Diagnostic preservation

All original stage strings remain present in the four diagnostic runtimes:

```text
CODEC_SELECT CODEC_OUTPUT NATIVE_WINDOW GRALLOC_ALLOC GRALLOC_HANDLE
AHB_DESC RENDERENGINE_MAP NATIVE_CLIENT_BUFFER EGL_CREATE_IMAGE
GL_GEN_TEXTURE GL_BIND_TEXTURE GL_EGL_IMAGE_TARGET BACKEND_TEXTURE
```

The original `LOG_ALWAYS_FATAL` texture failure text remains. EGL/GL error-query and control-flow
semantics are unchanged from diag1. No diagnostic stage was added or removed, and the allocator
logging fields—including formats, usages, allocation geometry, planes, modifier/AFBC, `aw_format`,
`ion_metadata_flag`, and backing-store ID—remain intact.

## Offline preservation result

- Android 16/API36, mixed ABI lists, `zygote64_32`, ARM64 `app_process64`, ARM32 `app_process32`, and
  active product-property derivation pass.
- VNDK31 dual-arch/APEX, BoringSSL32/64, ARM32 and ARM64 mapper/gralloc SP-HAL closure, proprietary
  ARM64 Mali closure, and linker namespace checks pass. Corrected ARM32 gralloc has zero unmatched
  strong imports.
- Ext4 integrity, AVB, vbmeta, IMAGEWTY, LP metadata/geometry, sparse/raw round trip, boot/kernel
  checkpoint, 5.4.302+ Path-A config, and exact 22-module vendor_dlkm inventory pass.
- System-only VINTF is **PASS / exit 0**. Full VINTF remains **exit 65 / inherited
  `CONFIG_NFS_FS=y` versus FCM-6 `n` / NOT PASS**.
- Kernel, boot, vendor_dlkm, product, BoringSSL32/64, both mappers, proprietary Mali, OMX/Cedar,
  audio, Wi-Fi and display/quarter-screen implementation are unchanged.

The machine audit is in the ignored candidate directory at
`out/candidates/a16-prototype-b-r7-diag1a/offline-audit/offline-audit.json`; the tracked record is
`docs/m8/candidates/a16-prototype-b-r7-diag1a.json`.

## Repository validation

Python compileall, JSON parsing, both diagnostic static checkers, source-overlay state checks,
candidate `SHA256SUMS`, and `git diff --check` pass. Focused r7/diag1/diag1a tests pass 28/28. The
full lightweight suite passes **164 tests with 52 explicit skips** for absent ignored historical
candidate/binary/generated fixtures; unavailable fixtures are not reported as passing. PowerShell
is not installed on this Linux VM, so no native PowerShell parser/runtime invocation was claimed;
the unchanged historical helper remains covered by repository structural/safety tests.

## Decision and next step

Diag1 remains **PHYSICAL BOOT FAIL / ROOT CAUSE PROVEN / CLOSED**. Diag1a is **OFFLINE CHECKED /
READY FOR PHYSICAL BOOT GATE**, not a physical pass and not yet authorized for media conclusions.
Flash exact diag1a and verify a normal boot first. Only after that boot gate passes should one AVC
control and one HEVC reproduction be captured on diag1a. R8 remains not authorized and the intended
`codex/m8-a16-development` branch does not exist.
