# Android 16 Prototype B r7

离线状态：**OFFLINE CHECKED / PASS**。物理状态：**PHYSICAL PASS — ARM64
MIXED-ARCHITECTURE BOOT / DUAL ZYGOTE / SYSTEM_SERVER / SURFACEFLINGER /
MAPPER-GRALLOC / MALI UI GATE CLOSED**。

R7 现为 **ACCEPTED ANDROID 16 ARM64 MIXED-ARCHITECTURE ARCHITECTURE BASELINE /
FROZEN AGAINST ARCHITECTURE CHANGES / PENDING GATE 3 FUNCTIONAL PRESERVATION**。这不是 daily-use
release 或 final functional baseline；Gate 3 必须在 exact r7 上验证 retained ARM32 hardware-facing
stack 的核心 TV 功能，且不授权 r8 或镜像重建。

R6 已物理证明 canonical mixed ABI、BoringSSL64 gate、`app_process64`/`app_process32`、ART64/ART32
和 primary zygote preload。Zygote 的 restart 不是独立 failure：ARM64 SurfaceFlinger 连续四次
SIGABRT 后触发 updatable-process health action，init 随后明确 SIGKILL primary zygote。R6 的唯一
primary blocker 是：

```text
Cmdline: /system/bin/surfaceflinger
ABI: arm64
SIGABRT
Abort message: gralloc-mapper is missing
```

R7 不换 graphics stack，也不修改 SurfaceFlinger。它只关闭 exact r7 HIDL mapper factory 在 retained
VNDK31 `libc++.so` 上的一个已证明 back-deploy relocation contract。

## Candidate identity

| 项目 | 值 |
|---|---|
| ID | `a16-prototype-b-r7` |
| exact base | `a16-prototype-b-r6`, 1,641,773,056 bytes / `2AAF8E2C...B2DBD53` |
| IMG | `out/candidates/a16-prototype-b-r7/x12-a16-prototype-b-r7.img` |
| 大小 | 1,641,773,056 bytes |
| SHA-256 | `A1F58668AEFFC9DC83CFFD8A49A309839332B6616C02153DCC00A71136A7AA27` |
| Android | `android-security-16.0.0_r7`; manifest `ebea28d151539ecf0730b1a4ab92ac33edc17ac9` |
| build | targeted `android.hardware.graphics.mapper@2.0-impl-2.1` and `gralloc.apollo`; no system/kernel rebuild |
| physical | `PHYSICAL ARCHITECTURE PASS`; exact r7 tested 2026-08-29; pending Gate 3 functional preservation |

## Exact runtime lookup and root cause

Exact r7 `GraphicBufferMapper` tries Gralloc5, 4, 3 and 2 in order, then emits
`gralloc-mapper is missing` only when all are unloaded. The retained path is Gralloc2:

```text
SurfaceFlinger / GraphicBufferMapper
  -> Gralloc2Mapper
  -> android.hardware.graphics.mapper@2.0::IMapper::getService("default")
  -> hwservicemanager returns the retained @2.1 passthrough/default entry
  -> PassthroughServiceManager scans /vendor/lib64/hw
  -> android.hardware.graphics.mapper@2.0-impl-2.1.so
  -> android_load_sphal_library() in the sphal namespace
  -> HIDL_FETCH_IMapper
  -> GrallocLoader::load()
  -> hw_get_module(GRALLOC_HARDWARE_MODULE_ID)
  -> /vendor/lib64/hw/gralloc.apollo.so
```

The filename, `HIDL_FETCH_IMapper`, manifest `2.1/default/passthrough/arch=32+64`, `apollo` property,
SELinux label and `/vendor/lib64/hw` SP-HAL search path are correct. The failure occurs earlier:
both r6 ARM64 DSOs have one direct, strong, unresolved import:

```text
_ZNSt3__122__libcpp_verbose_abortEPKcz
std::__1::__libcpp_verbose_abort(char const*, ...)
```

The isolated `sphal` namespace resolves `libc++.so` from `com.android.vndk.v31`, whose exact file does
not export that newer symbol. Current system libc++ does export it, but is not the `libc++.so` selected
for this vendor DSO. Bionic performs eager relocation and rejects the unresolved strong symbol, so the
mapper fails at `dlopen` before its fetch function can run. If only the mapper were corrected, its fetch
function would immediately load the old ARM64 gralloc with `RTLD_NOW`, which fails on the same sole
symbol. Thus the two replacements form one mapper-instantiation causal closure.

The working ARM32 control has the same filenames, manifest, fetch/HMI exports, board property and
private-handle contract, but neither ARM32 DSO imports this symbol and both have zero unmatched strong
imports. This is the smallest architecture-dependent explanatory difference.

## Single-cause source and vendor delta

Libc++ explicitly provides `_LIBCPP_VERBOSE_ABORT` as a back-deployment customization hook. The
bounded header keeps the path fatal while avoiding an unavailable shared-library diagnostic symbol:

```c
#define _LIBCPP_VERBOSE_ABORT(...) __builtin_abort()
```

It is pre-included for ARM64 only in the exact r7 AOSP passthrough mapper and the pinned gralloc-1.x
module. No ARM32 candidate file is rebuilt or changed. Relative to exact r6, the signed vendor tree is:

```text
added   []
removed []
changed [
  lib64/hw/android.hardware.graphics.mapper@2.0-impl-2.1.so,
  lib64/hw/gralloc.apollo.so
]
```

| runtime file | size | SHA-256 | Build ID | exact SP-HAL closure |
|---|---:|---|---|---|
| `/vendor/lib64/hw/android.hardware.graphics.mapper@2.0-impl-2.1.so` | 36,056 | `D0FC49B3C216441BDEA66C015CE17B494523E3EB4D1659DE9BBA31693C7461E8` | `2f99ba222f5d3eaf2e6217f8b3670537` | 45 strong imports / 0 unmatched; `HIDL_FETCH_IMapper` present |
| `/vendor/lib64/hw/gralloc.apollo.so` | 77,248 | `B03BFE24802C73E158A365CB5D15E1BC7598BB73C98DEF86533183678837CFE7` | `4ea9accdddd3f88f1787aa22de09f009` | 47 strong imports / 0 unmatched; `HMI` present |

Both use mode 0644, owner 0:0 and `same_process_hal_file`. ARM64 Mali remains exact
`03333D49...C7F8`; both ARM32 provider files and both BoringSSL tests remain byte-identical.

## Offline acceptance

- System_a, active mixed ABI triplet, product_a, boot, vendor_dlkm, vbmeta_system, root `/metadata`,
  canonical `/vendor`, `/product -> /system/product`, BoringSSL32/64, Mali and ARM32 graphics control
  are exact r6.
- Candidate mapper/gralloc have their required exports, exact DT_NEEDED lists, no verbose-abort import,
  no missing dependency and zero unmatched strong symbols in the generated r7 `sphal` namespace.
- Vendor semantic tree diff is exactly the two approved changed files; no provider was added, removed or
  converted. Manifest/transport and linker namespace are byte-preserved.
- `e2fsck -fn`, system/vendor AVB, vbmeta signatures and rollback locations, exact LP geometry/no shrink,
  sparse/raw super roundtrip and IMAGEWTY PASS.
- Outer delta is only `super.fex`, `Vsuper.fex`, `vbmeta_vendor.fex`, `Vvbmeta_vendor.fex`; 46/50
  payloads are byte-preserved.
- Mixed ELF census PASS: 1,471 system AArch64, 701 system ARM; app_process64/32 and `zygote64_32`
  remain present. Vendor AArch64 set remains BoringSSL64 plus the same three planned graphics paths.
- 35/35 APEX, both-arch VNDK31, linkerconfig, ARM64 SP-HAL, Mali 297/0, split SELinux compile and
  system VINTF PASS offline.
- Full VINTF remains **exit 65 / inherited `CONFIG_NFS_FS=y` versus FCM-6 `n` only / NOT PASS**.
- Kernel 5.4.302+, six Path-A configs, exact 22 modules, AIC FMAC contract and non-target hardware
  authority are preserved.
- Focused r1-r7 candidate/prebuild tests 64/64 PASS; full lightweight suite 170/170 PASS with 34 declared
  missing-fixture skips. Python compilation, 79 JSON parses and `git diff --check` PASS.

The first audit invocation exposed and fail-closed on a missing inherited active-product contract in
the r7 audit config. The candidate was not changed; the audit contract was completed, covered by a
focused test, and the full audit then passed from the beginning. Persistent logs are under
`/work/build-logs/a16-prototype-b-r7-20260828T170500Z/`.

Machine records: `a16-prototype-b-r7-mapper-root-cause-audit.json`,
`a16-prototype-b-r7-arm32-arm64-mapper-control.json`,
`a16-prototype-b-r7-offline-result.json` and `a16-prototype-b-r7-preservation.json`.

## Physical architecture result

The user physically validated the exact hash-pinned candidate on 2026-08-29. Runtime reports Android
16/API 36, `zygote64_32`, canonical mixed ABI lists, `sys.boot_completed=1`, both zygotes running,
ARM64 SurfaceFlinger running and `system_server` PID 786 parented by primary `zygote64` PID 494.
The validated crash-buffer query found no recurrence of `gralloc-mapper is missing`; real 1920x1080
gralloc allocations and Mali-G31 OpenGL ES 3.2 composition are present. Therefore the bounded r7
mapper/gralloc back-deploy correction is **PHYSICAL PASS** and the r6 blocker is **CLOSED**.

Basic Wi-Fi association/DHCP/L3/DNS/network ADB and three physical remote paths
(`DPAD_DOWN`/108, `DPAD_CENTER`/352, `BACK`/158) also pass. Those bounded observations do not prove
Wi-Fi OFF→ON recovery or the full TV key matrix. Vulkan, HDR, 4K60, every HWC/media buffer path and
protected DRM playback remain outside the architecture claim.

The r7 boot still records the known legacy vendor audio-service null-address SIGSEGV and audioserver
restart activity; AudioFlinger later remains alive. The supplied r7 excerpt does not independently
establish a more specific sub-cause. This remains **KNOWN / UNFIXED / POST-ARCHITECTURE P1** under the
existing policy, not fixed. Full VINTF remains **exit 65 / inherited `CONFIG_NFS_FS=y` versus FCM-6
`n` / NOT PASS**.

Tracked physical evidence is intentionally bounded: the full raw ADB/runtime capture remains outside
Git and was not present on this VM, so no raw path or hash is invented. See
`a16-prototype-b-r7-physical-result.json` and
`../device-tests/20260829-a16-prototype-b-r7-physical-validation/`.

## Gate 3 and freeze

Exact r7 is now the frozen Android 16 ARM64 mixed-architecture architecture control. The only active
P0 is **Gate 3 — Android 16 Mixed-Architecture Functional Preservation**, executed read-only on this
same image. It must cover architecture regression, real H.264/HEVC/VP9 playback with bounded audible
HDMI checks, the physical TV-key matrix, Wi-Fi OFF→ON recovery, basic storage/platform sanity and a
before/after crash census. Exact criteria are in `docs/DEVICE_TEST.md`.

Rollback hierarchy remains frozen Android 12 `m8b-remote-r1`, frozen Android 16 ARM32
`a16-prototype-a-r4`, then this frozen architecture baseline. The intended future
`codex/m8-a16-development` line may be created only after Gate 3 PASS and a final functional freeze;
it was not created here.
