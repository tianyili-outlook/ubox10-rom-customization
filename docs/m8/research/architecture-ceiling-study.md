# UBOX10 Architecture Ceiling Study

Study date: 2026-08-17; build/runtime evidence updated: 2026-08-22

Study branch/base: `codex/m8-architecture-ceiling` / `c30c8d0bbbcab5667a9aeaaf9cbfadbdf168d401`

Accepted runtime baseline: `m8b-remote-r1`; last flashed image: failing `a16-prototype-a-r1`
Scope: architecture decision, bounded offline prototype, and the single separately authorized r1 physical boot; no further device mutation is authorized

Confidence labels in this report have the following strict meanings: **PROVEN** is direct
binary, build, runtime, repository, or authoritative-source evidence; **HIGH CONFIDENCE**
is converging evidence with no material contradiction; **MEDIUM CONFIDENCE** retains one
meaningful provider or runtime dependency; **LOW CONFIDENCE** is speculative. A capability
declaration is not called physically verified unless the physical device exercised it.

## 1. Executive architecture decision

The best architecture worth formally developing is **Android 16 for TV, mixed ARM64/ARM32
userspace, `zygote64_32`, the existing Allwinner 5.4 kernel and hardware-facing vendor stack,
plus only the minimum matched ARM64 graphics client provider and bounded vendor
zygote/AVB metadata changes**. This remains a candidate end architecture, but the current
decision is **HOLD before Prototype B**: r1 reproducibly fails before ueventd/apexd exec because
the retained kernel cannot establish A16's required cgroup hierarchy. The minimal boot-only r2
is offline checked, but must advance that runtime boundary before mixed-mode work.

This is a modern hybrid, not a full port. Framework, `system_server`, SurfaceFlinger, and
eligible apps become AArch64; legacy Allwinner media, audio, HWC/composer, DRM, Wi-Fi,
Bluetooth, TEE and other HAL processes remain ARM32 behind stable Binder/HwBinder
interfaces. The current vendor, vendor_dlkm, TEE, boot and board-specific display/media
implementation remain the hardware authority. The paired ARM64 Mali-G31 client library and
multilib mapper/gralloc implementation found in the public Allwinner `apollo`/`sun50iw9p1`
H618 BSP are the only new proprietary-provider class justified by present evidence.

The decisive change from the earlier M8B ARM64 no-go is exact provenance evidence: the
public donor's ARM32 `libGLES_mali.so` is byte-for-byte identical to the accepted UBOX10
library, and the same donor directory supplies its paired AArch64 library while the donor
product itself selects `zygote64_32`. This does not prove a boot on H616, but it replaces a
missing-provider structural blocker with a small, testable provider gate.

The practical quality target is a 1080p-rendered TV UI with **4K30-class local media as the
reliability target and 4K60 HDMI output capability retained**. The live accepted firmware
currently drives the attached display at 3840x2160@60 while composing a 1920x1080
framebuffer. H.264, HEVC and VP9 hardware paths exist, but only 1080p H.264/HEVC and a small
VP9 asset have runtime playback acceptance. HDR, Main10/Profile 2, high-bitrate 4K and
frame-perfect 4K playback remain unproven.

The legitimate DRM target remains **Widevine L3/basic protected playback only**. Netflix
above that class is structurally blocked by the current L3 plugin, HDCP `NONE`, absent secure
decoder exposure and absent protected-composition proof; Netflix entitlement is additionally
service/certification dependent. No key, provisioning, bypass, spoofing or certification work
is part of this architecture.

## 2. Current Architecture Contract

The accepted outer image is
`m8-development/out/candidates/m8b-remote-r1/x12-m8b-remote-r1.img`, 1,031,723,008 bytes,
SHA-256 `F3B09E5565AC4ED4E5EE326D392622E7B036A8519B8444B966E77CC4751B814A`.
The copied Study super image was re-hashed before inspection. Its SHA-256 is
`6374231FECBA80294D0BEDB97F265068C88C193788E1048FD0894B5C854398B2`.

| Contract area | Verified accepted state | Confidence / boundary |
|---|---|---|
| SoC and board | Device tree model `sun50iw9`, compatible `allwinner,h616` / `arm,sun50iw9p1`; board platform `apollo`; hardware `sun50iw9p1` | **PROVEN**. H616 is authoritative; an H618 sales/donor label is not substituted for it. |
| CPU | Four Cortex-A53 cores, ARMv8 | **PROVEN** from `/proc/cpuinfo` |
| Kernel | AArch64 `CONFIG_ARM64=y`, release `5.4.125+`; live `uname -m` reports `armv8l` because the querying userspace is 32-bit | **PROVEN** from runtime and `/proc/config.gz` |
| Android | Android 12 / API 31, 2021-11-05 patch level, `userdebug` | **PROVEN** |
| Userspace ABI | `armeabi-v7a,armeabi`; no 64-bit ABI; `/system/lib64` and `/vendor/lib64` absent | **PROVEN** |
| Zygote | `ro.zygote=zygote32` in `/vendor/build.prop`; bionic primary `arm`; no second architecture | **PROVEN** |
| Binder | 64-bit Binder wire protocol configured; binder, hwbinder and vndbinder enabled; 32-bit clients/services | **PROVEN** from BoardConfig, kernel config and runtime |
| Treble/VNDK | Treble enabled; device manifest target FCM 6; `ro.vndk.version=31`; VNDK 31 APEX/linker namespace active | **PROVEN** |
| Partitions | A/B dynamic partitions in super: system, vendor, product and vendor_dlkm; ext4 logical filesystems; boot/vendor_boot/TEE and outer Allwinner container remain separate | **PROVEN** from LP metadata, first-stage history and exact image extraction |
| System layout | Separate `/system`, `/system_ext` content within system, `/product`, `/vendor`, `/vendor_dlkm` | **PROVEN** |
| Graphics | Mali-G31, `mali_kbase`; ARM32 Mali EGL/GLES and Vulkan; ARM32 HIDL mapper 2.1/gralloc; allocator and composer 2.2 service; SUNXI HWC | **PROVEN** |
| Media | ARM32 Allwinner OMX/Cedar hardware services for AVC, HEVC, VP9 and legacy formats; software Codec2 fallbacks | **PROVEN** for inventory; accepted runtime proves AVC/HEVC and VP9 component use |
| Audio | ARM32 Apollo audio HAL 7.0; AudioFlinger primary path to ALSA `ahubhdmi`; HDMI TV audio accepted | **PROVEN** |
| DRM/TEE | Widevine HIDL 1.4 lazy service and ClearKey; Widevine 16.1.0 opens at L3; `tee_supplicant` present | **PROVEN**; no secret-bearing material inspected |
| Wireless | AIC8800 kernel modules and binderized Wi-Fi/Bluetooth services; accepted Wi-Fi, Ethernet, Bluetooth and HID | **PROVEN** |

Exact extracted logical-image hashes are:

| Logical partition | Bytes | SHA-256 |
|---|---:|---|
| system | 1,651,167,232 | `5992972F35EAFEB722C482A83D5B555F023DEAEA45EABFA282AB3379C8C3056B` |
| vendor | 119,066,624 | `BB91A8B7ED4AC0145F434F89FD76865EB4311F234AA46D67C8373A7CD5B4929A` |
| product | 272,629,760 | `6E2D0AF3E80DCCC488D73E1A7F483C96075E9F60588DDB7DCBBC42C64FCD8974` |
| vendor_dlkm | 6,680,576 | `C589DC0B12E150469F179738F127F36F6321943577453A7DB335AB9E647B8FE5` |

The live process census used root only to read `/proc/<pid>/exe` metadata: all 92 observed
userspace processes were ELF32, including zygote, `system_server`, SurfaceFlinger,
servicemanagers, graphics services, OMX, audio, Wi-Fi, Bluetooth and TEE. No service was
stopped and no property, setting, log buffer, package, mount or file on the device was changed.

Relevant kernel facilities already present include Binder/binderfs, 32-bit compat, cgroups,
cgroup BPF, BPF syscall/JIT, namespaces, seccomp filter, PSI, uclamp, io_uring, dm-verity,
dm-bow, fs-verity, ext4, f2fs, overlayfs, SELinux, CFI and LTO. Notable omissions are MEMCG,
PID namespaces, user namespaces, cgroup-pids, fanotify and IMA/EVM. These omissions are
runtime risks to test, not proof that Android 16 init cannot execute.

## 3. ABI/ELF census and true 64-bit blockers

The exact accepted images were scanned recursively, including ELF files inside APEX payloads
and APK/JAR containers. The census identified 1,451 ELF objects: 1,403 platform/APEX files,
26 packaged native objects and 22 AArch64 kernel modules.

| Partition | ARM32 userspace | AArch64 userspace | Other platform ELF | Packaged ELF | Kernel modules |
|---|---:|---:|---:|---:|---:|
| system | 1,095 | 0 | 6 | 23 | 0 |
| product | 2 | 0 | 0 | 3 | 0 |
| vendor | 300 | 0 | 0 | 0 | 0 |
| vendor_dlkm | 0 | 0 | 0 | 0 | 22 |

Graphics contributes 17 ARM32 and zero AArch64 platform ELF objects; media contributes 68
and zero; Wi-Fi/Bluetooth contributes 43 and zero. Same-class SONAME/filename closure found
zero unresolved names, which proves inventory consistency but not linker-namespace runtime
success.

### Classification

| Class | Component set | Reasoning and result |
|---|---|---|
| A — already ARM64-capable | ARM64 kernel and modules; Binder wire contract; open-source framework/native/JNI rebuilt from AOSP; apps with AArch64 payloads such as Projectivy | No proprietary same-process blocker. Current AOSP framework files are ARM32 because of the product target, not because their source is ARM32-only. |
| B — ARM32-only but process-isolatable | SUNXI HWC/composer service, graphics allocator service, Allwinner OMX/Cedar, Apollo audio HAL, Wi-Fi HAL, Bluetooth HAL, Widevine/ClearKey DRM service, `tee_supplicant`, power/thermal/USB/lights and most other vendor services | These execute in dedicated vendor processes and communicate over stable Binder/HwBinder/HIDL. They may remain ELF32 under a mixed product. Each still needs interface/runtime regression testing. |
| C — ARM32-only and loaded into a mandatory 64-bit consumer | Mali EGL/GLES SP-HAL; HIDL graphics mapper 2.1 and its gralloc implementation; Vulkan driver for 64-bit Vulkan clients | SurfaceFlinger and 64-bit apps load graphics SP-HALs in-process. An ELF64 process cannot load the accepted ELF32 libraries. These are the minimum real blockers to `zygote64_32`; HWC itself is not one. |

### Minimum blocker/provider table

| Mandatory function | Accepted implementation | Why mandatory in mixed mode | Provider evidence | Residual gate |
|---|---|---|---|---|
| EGL/GLES client | `/vendor/lib/egl/libGLES_mali.so`, ELF32, SHA-256 `fbffe5601a58d1f8d624ee37129f73b76d0a73eb21fc8a2487368d9ab47f14b7` | Loaded by AArch64 SurfaceFlinger/apps | Public BPI H618 donor has the exact same ARM32 hash and paired ELF64 AArch64 library, SHA-256 `03333d495e3566c7d85ca2e000da569a16ce8f022ea25c0ea61950c891d5c7f8` | Static DT_NEEDED/linker closure, distribution right, then one exact-board boot/graphics test |
| Mapper/gralloc | `android.hardware.graphics.mapper@2.0-impl-2.1.so` plus `gralloc.apollo.so`, ELF32; manifest claims passthrough `arch="32+64"` although no `lib64` implementation exists | Mapper is an SP-HAL loaded in SurfaceFlinger/apps; buffer layout must match 32-bit HWC/media users | Same donor publishes the Mali-Bifrost gralloc/mapper source with `LOCAL_MULTILIB := both`, explicit `/vendor/lib64/egl` paths, platform `apollo`, GPU G31 and chip family `sun50iw9p1` | Build or obtain the paired ELF64 output, verify handle/layout ABI and A16 SP-HAL namespace |
| Vulkan client | `/vendor/lib/hw/vulkan.apollo.so`, ELF32 and byte-identical to current Mali library | Needed only by AArch64 Vulkan apps, not by first UI boot | Donor supplies the paired AArch64 Mali library, but its product makefile does not independently prove a `/vendor/lib64/hw/vulkan.apollo.so` install | Treat Vulkan as a post-boot provider validation, not a boot gate |

No other mandatory proprietary same-process ARM64 dependency was found. Vendor JNI or current
system-native customizations that are source/rebuildable belong to reintegration, not to the
proprietary blocker set.

There is also one mandatory non-ELF mixed-mode change: the accepted vendor owns
`ro.zygote=zygote32`. A `zygote64_32` image must update that vendor property, preserve both
zygote init scripts, and regenerate/verify the affected vendor/root AVB chain. The official
A16 generic ARM64 board is genuinely mixed (`arm64` primary, `arm` secondary), and
`core_64_bit.mk` selects `zygote64_32`; merely flashing its system image cannot override the
accepted vendor property.

## 4. Android-version analysis

Android 16 is the current released Android TV generation relevant to this decision. Google's
official TV page documents Android 16 for TV and its media, HDMI-CEC and performance changes.
The official TV release navigation has Android 12, 13, 14 and 16 pages; there is no separate
Android 15 TV destination that improves the engineering return here. Android 17 AOSP/API 37
is released, but no official Android 17 for TV release is currently published.
Selecting phone/AOSP 17 would therefore add platform churn without a TV support advantage.

The reproducible source baseline is `android-16.0.0_r4`, build `BP4A.251205.006`, manifest
tag object `6a0aa432c646cef4c76b276c9a0f38ecaa6e0c59`, manifest commit
`15128c9e27cfa599c48d294babd39286ee8f1426`.

Android 16 explicitly supports Android 12 target FCM level 6. The current device manifest is
target-level 6. Official FCM policy now retains the current and six previous levels for modern
frameworks and says deprecated levels remain supported for existing devices. This is strong
evidence that an Android 16 framework/Android 12 vendor pairing is an intended Treble upgrade
shape, not merely a linker hack. The exact VINTF match still has to be checked with the built
product because UBOX vendor/product matrices contain device-specific requirements.

VNDK deprecation in Android 15 removes a current-release VNDK APEX for newly built vendors,
but official documentation explicitly preserves older VNDK APEXes needed by existing vendor
images. The current vendor requests VNDK 31, and accepted M8 history already proves that exact
VNDK payload and generated linker namespaces matter.

Google Play's August 31, 2026 TV target requirement is Android 14/API 34 or newer for new apps
and updates. This does not make Android 12 unable to run an app whose `minSdk` remains lower,
but it increases the long-term framework/API gap. Likewise, the Play 64-bit requirement means
native apps must publish 64-bit variants; it does not by itself exclude every 32-bit device.
Mixed ABI nevertheless buys meaningful app longevity because a 64-bit-only native package can
run while legacy vendor services remain 32-bit.

**Decision: Android 16 for TV is the best modern destination.** Android 14 is the conservative
fallback if the A16 boot gate fails for a framework/vendor reason that is absent on 14; Android
12 remains the rollback and mature reference, not the final investment ceiling.

## 5. Kernel ceiling

### 5A. Can 5.4 technically carry Android 16 userspace?

**HIGH CONFIDENCE: yes for a field-upgraded FCM-6 device, subject to boot validation; no claim
of a new Android 16 launch-device certification.**

The accepted kernel has the important Android mechanisms listed in section 2 and already runs
the exact Android 12 vendor contract. Android 16's official FCM list retains level 6, and VINTF
kernel matching selects the kernel requirements associated with the device/kernel FCM rather
than blindly applying the newest launch kernel contract. That is the relevant technical
upgrade model.

Separately, Google's Android common-kernel documentation lists 5.10 and newer branches for
Android 16 support and does not list 5.4. The current kernel is also an Allwinner BSP kernel,
not GKI. Therefore 5.4 is outside the contemporary ACK support/security envelope even if it
boots. Retaining it accepts vendor maintenance debt and requires project-owned patch triage;
it must not be described as an officially supported Android 16 launch kernel.

The missing MEMCG/PID_NS/USER_NS/cgroup-pids features are the most concrete runtime concerns.
The kernel does have PSI and other lmkd-era mechanisms. Passive evidence cannot prove how A16
`init`, `apexd`, process groups and memory management behave; those are explicit boot gates,
not justification for a speculative kernel replacement.

### 5B. Is a newer complete H616 kernel realistically obtainable?

No public source examined combines a 5.10+ H616 kernel with this board's complete Android TV
display engine, Mali-G31 integration, Cedar/VPU, HDMI/audio, IR, AIC8800, thermal/DVFS,
suspend and DRM/TEE contracts. The strongest adjacent Android BSP—the BPI H618 Android 12
source—also uses Linux 5.4 and `sun50iw9p1`. Orange Pi and mainline trees establish ongoing
H616/H618 kernel work and useful device support, but not a drop-in Android hardware stack.

A mainline/Panfrost direction would replace, rather than upgrade, the present display,
allocator/HWC, media overlay and likely protected-content integration. It is a multi-subsystem
port with high regression risk and poor return for this box. No source met the study's
"unusually credible and closely matched" threshold, so no exploratory kernel build was
started.

**Kernel decision: retain 5.4 for the final UBOX architecture, conditional on the A16 boot
gate; a 5.10+ migration is not economically justified.** Revisit only if a complete, licensed,
same-lineage Android BSP appears—not merely a kernel that reaches a shell.

## 6. Donor/BSP archaeology

Downloaded material stays outside Git under `/home/tianyi/ubox10-ceiling-donors`; no donor
host binary was executed and no proprietary binary is redistributed by this report.

| Candidate | Board/SoC | Android / kernel / userspace | Relevant contents | Provenance and local identity | Compatibility confidence |
|---|---|---|---|---|---|
| BPI M4Zero/M4Berry public BSP | Banana Pi boards, H618; platform `apollo`, chip family `sun50iw9p1`, Mali-G31 | Android 12, Linux 5.4; product explicitly supports ARM64 primary + ARM32 secondary and `zygote64_32` | Paired 32/64 Mali client blobs; multilib Mali gralloc/mapper source; Allwinner display/HWC, media, audio, wireless, Widevine/OP-TEE integration; BSP/bootloader/kernel | [Official board wiki](https://wiki.banana-pi.org/Banana_Pi_BPI-M4_Zero), [BPI-SINOVOIP source](https://github.com/BPI-SINOVOIP/BPI-H618-Android12); shallow metadata checkout commit `316cd80ca43fa17b0385eacd7f6f3652bbd66b2a` | **HIGH** for the minimum graphics-provider lineage because its ARM32 Mali blob exactly matches UBOX; **MEDIUM** for use on the exact board until H616 runtime and rights are resolved |
| Orange Pi Zero 2 material | Orange Pi Zero 2, H616 | Public Android/Linux images and board support; older Android generation | Direct H616 board/kernel/display evidence; potential comparison source | [Official Orange Pi wiki](http://www.orangepi.org/orangepiwiki/index.php/Orange_Pi_Zero_2), [official build repository](https://github.com/orangepi-xunlong/orangepi-build) | **LOW-MEDIUM**: SoC is exact but no audited Android 16/multilib provider set was established |
| Orange Pi Zero 2W material | Orange Pi Zero 2W, H618 | Android 12 offerings on adjacent silicon | Additional H618 Android BSP/firmware family | [Official Orange Pi wiki](http://www.orangepi.org/orangepiwiki/index.php/Orange_Pi_Zero_2W) | **LOW-MEDIUM**: corroborating donor family, weaker than the source-audited BPI tree |
| Linux mainline / linux-sunxi | H616/H618 upstream support | Newer mainline kernels, ARM64 | SoC basics, DRM/KMS and Panfrost direction; useful for source/reference and long-term repairs | [Linux kernel source](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/), [linux-sunxi](https://linux-sunxi.org/) | **LOW** as an Android replacement stack: no complete equivalent of accepted media/HWC/DRM/board integration |

The BPI repository is adjacent-H618 evidence, not permission to relabel the UBOX as H618.
Its value is narrower and stronger: same Allwinner platform/chip family, same GPU, the exact
accepted ARM32 userspace driver, its paired ARM64 binary, and multilib source integration.
The donor GPU README labels the binary stack confidential/proprietary and usable only under
an Allwinner licensing agreement; public Git availability is therefore **not** a proven right
to redistribute it. The gralloc source carries a separate Apache-2.0 notice. This Study uses
the binary only for local static prototype evidence and keeps lawful binary availability as a
release gate.

## 7. Graphics ceiling

**G1 — retain the accepted proprietary stack unchanged:** viable for ARM32 Android 16, but
not for `zygote64_32`. HWC and allocator can stay in 32-bit services; EGL/GLES and mapper
cannot because they are SP-HALs loaded into AArch64 consumers.

**G2 — add the matched ARM64 proprietary provider:** recommended. Preserve the kernel driver,
display engine, HWC/composer and buffer conventions. Add only the paired AArch64 Mali client,
AArch64 mapper/gralloc and, after boot, Vulkan provider. Keep the exact accepted 32-bit files
for legacy apps/services. Pin every provider hash and audit all DT_NEEDED/linker namespaces.
This path has the smallest change surface that unlocks 64-bit apps.

**G3 — open Mesa/Panfrost stack:** technically conceivable, not economically justified for
this architecture. It needs a coherent DRM/KMS kernel, Android gralloc/mapper, HWC or client
composition strategy, sync/fence and video-buffer integration. It would put display and Cedar
zero-copy/overlay behavior at risk and is a subsystem program, not a bounded provider change.

The graphics recommendation is therefore G2, with G1/ARM32 as the fallback and G3 rejected.

## 8. Media/display ceiling

The live physical device reports SUNXI HWC output `3840x2160 60 Hz`, a 1920x1080 framebuffer
and a 3840x2160 screen transform. This **PROVES >1080p HDMI output on the currently attached
display**, while also showing that the normal UI is rendered at 1080p and scaled. It does not
prove native-resolution 4K video frames, 10-bit output or HDR.

Current codec declarations and measured-performance metadata state:

| Decoder | Declared maximum | Declared/measured 4K performance | Physical/runtime proof |
|---|---|---|---|
| Allwinner AVC | 4096x2160, 60 Mb/s | 4096x2048: 15-35 fps | Accepted hardware playback at 1080p; 4K not yet exercised |
| Allwinner HEVC | 6144x3160, 60 Mb/s | 4096x2048: 20-90 fps | Accepted hardware playback at 1080p with HDMI audio; 4K not yet exercised |
| Allwinner VP9 | 4096x2160; profile list unavailable | 4096x2048: 15-35 fps | Hardware component/Cedar runtime accepted with 640x480 test asset; 4K/profile 2 unproven |

The declarations, 4K60 output path and known H616 class make **4K30-class playback a
plausible and worthwhile target**, not a proven acceptance result. 4K60 decoding, HEVC
Main10, VP9 Profile 2, HDR/color-space correctness, high-bitrate behavior, frame drops, A/V
sync and sustained thermal behavior require controlled media assets. Reliability policy is:
keep the 1080p UI, prove 4K30 HEVC and VP9 first, and call 4K60 a stretch result only if it
passes sustained physical testing. HDMI audio and the accepted Apollo path are retained.

## 9. DRM/Netflix ceiling

The current architecture exposes Widevine 16.1.0 through DRM HIDL 1.4 and MediaDrm opens it,
but reports `securityLevel=L3`, connected/max HDCP `NONE`, and no secure-decoder requirement
for AVC, HEVC or VP9. The codec inventory exposes no secure component name. The secure AVC
codec entry in vendor XML is commented out. SurfaceFlinger does not prove a protected
composition context. Kernel configuration symbols for HDCP/HDCP2.2 only prove compiled
driver code, not an authenticated runtime protection chain.

Therefore:

1. codec/display hardware capability is good enough for high-resolution unprotected media;
2. the current secure hardware/TEE/DRM path proves only operational L3, not L1;
3. the current runtime HDCP gate is absent;
4. Netflix quality and entitlement remain service/device-certification decisions even after
   technical gates.

The legitimate ceiling is **Widevine L3/basic protected playback**, with actual commercial
app availability/playback still to be tested under normal credentials. Netflix above the
current basic/L3 class is **STRUCTURALLY BLOCKED on the observed stack and additionally
SERVICE/CERTIFICATION DEPENDENT**. Preserve TEE/factory/security partitions untouched; do not
invest in key extraction, leaked provisioning, app patches, spoofing or HDCP bypass.

## 10. Android 16 disposable prototype evidence

The authoritative native source tree is `/work/src/ubox10-a16-ceiling`. Its source baseline
is the official `android-16.0.0_r4` tag / `BP4A.251205.006`, manifest commit
`15128c9e27cfa599c48d294babd39286ee8f1426`. Regenerating the pinned manifest from all
1,011 clean repo projects produced SHA-256
`4e8beb5d1b590dff3d631b1dbb957138dbda4e608a3183c625683da4bc84918f`.
The copied Prototype A definitions matched the tracked files byte-for-byte and the old
`SOONG_GOMEMLIMIT` patch was absent. Earlier WSL/output-loop observations remain historical
host evidence; they are not part of the successful native build.

Prototype A is a minimal Android 16 TV GSI-style ARM32 product. It inherits the official ATV
GSI base, uses the generic ARM board, models an Android 12/API-31 field upgrade, retains only
VNDK 31, disables pKVM and requests only `systemimage`; it intentionally produces no boot,
vendor, super or userdata image. Prototype B is configuration only: the generic ARM64 board
provides AArch64 primary plus ARM32 secondary ABI and `core_64_bit.mk` selects
`zygote64_32`. Neither product contains an Allwinner or donor binary.

### Recorded build result

**OFFLINE CHECKED / SUCCESS — complete Prototype A `system.img`; no device integration or
runtime claim.** The native GCP host was Ubuntu 24.04 on ext4 with 8 vCPU, approximately
62.8 GiB usable RAM and no swap. The exact build environment was relative
`OUT_DIR=out-ceiling`, `BUILD_NUMBER=DISPOSABLE_CEILING_R4`, unset `SOONG_GOMEMLIMIT` and
`GOMEMLIMIT`, lunch `ubox10_ceiling_arm-bp4a-userdebug`, then `m -j8 systemimage`. No cgroup,
taskset, swap, WSL wrapper or Soong patch was used.

The build returned status 0 after all 123,197 actions and 30,314 seconds wall time
(8:25:14). Whole-log inspection found no `FAILED:`, Ninja stop, OOM, no-space or I/O failure.
The nsjail fallback and inherited TV-GSI debug-policy messages were non-blocking warnings.
Available RAM never fell below 12,295,132 KiB; swap I/O stayed zero. `vmstat` averaged
88.05% user CPU, 9.48% system CPU, 0.93% idle, 0.05% I/O wait and 1.35% steal. `/work` free
space never fell below 231,671,357,440 bytes. The complete log and 30-second resource samples
remain outside Git under
`/work/build-logs/ubox10-a16-gate1/20260821T035000Z/`.

The only top-level image is
`/work/src/ubox10-a16-ceiling/out-ceiling/target/product/generic/system.img`,
946,765,824 bytes, SHA-256
`fd349f1d8073dfeb71e2cea28915f1c755fa54e3eba85616fcaa279063f3edbe`.
Focused offline closure established:

1. The image is raw ext4, `e2fsck -fn` clean. Its embedded SHA256_RSA2048 AVB footer and
   system hashtree verify. This is the AOSP test-key standalone image, not the UBOX device
   AVB chain.
2. The staging filesystem has 2,277 regular files and 256 symlinks. It contains 997 ARM32
   userspace ELF files; the only seven ELF64 objects are `Machine: Linux BPF`, not AArch64
   userspace. `init`, the bootstrap linker, app_process32, SurfaceFlinger and servicemanager
   are ARM32; linker64, app_process64 and lib64 are absent. The runtime APEX likewise has an
   ARM32 linker/libc and no lib64 payload.
3. All 36 installed APEX containers parse. The VNDK payload is correctly installed at
   `/system_ext/apex/com.android.vndk.v31.apex`, 17,743,872 bytes, SHA-256
   `fb94b4e2ba84bdefddfaf59729fdae87b0195d2eefd972fd69235dd7a12d705e`.
   Its manifest name is `com.android.vndk.v31`; its 144 listed entries include the v31
   LLNDK/VNDK lists and ARM32 `libaudioroute.so`.
4. The A16 host linkerconfig built incrementally from the same tree generated a vendor
   section, VNDK search path `/apex/com.android.vndk.v31/${LIB}`, and
   `default` to `vndk` exposure of `libaudioroute.so` from the actual built system/VNDK
   inputs. The generated configuration has 1,155 lines and SHA-256
   `64543f7254c0acff3cb3738f83ab270c21dda4bf4f9ae6cebdad4fa3234c8de7`.
5. A16 `checkvintf --check-one` accepted the system manifest/matrix set. The framework
   contains level-6 matrices and 5.4 kernel branches. At the Gate-1 checkpoint the accepted
   vendor/product inputs were not yet present, so full compatibility was deliberately deferred
   to the subsequent exact-board audit below.
6. SELinux xattrs on init, the linker, platform policy and VNDK APEX are present; compiled
   platform policy and 31.0 mapping/compat files exist. No boot, vendor, product, system_ext,
   super or userdata image, Allwinner outer container or flashable firmware was built.

The A16 VNDK 31 `libaudioroute.so` is ABI-versioned but not byte-identical to the accepted
Android 12 file: 11,620 bytes / SHA-256
`9750f133e24a4b889a3bc4f2aeacd120d48a4a764705a6ef8a340f29e7d5a6a2` versus 11,640 bytes /
`bb5393ce70cd1a4ad9ed62814339ca3695788532242708b0d46daed87d603623`.
Its SONAME, direct dependency set, v31 membership, ABI build checks and generated namespace
closure are correct; exact Apollo runtime behavior remains a device gate.

This closes Gate 1 as an Android 16 ARM32 product/build/composition result. Gate 1 by itself
does not prove first-stage handoff, exact accepted vendor/product compatibility, device
AVB/LP integration, `apexd`, zygote, system_server, graphics, media, audio, wireless or DRM
runtime. Prototype B was not built.

### Exact-board offline integration

The exact accepted inputs were subsequently transferred to GCP and verified before use. The
accepted `m8b-remote-r1` outer image is 1,031,723,008 bytes / SHA-256
`f3b09e5565ac4ed4e5ee326d392622e7b036a8519b8444b966e77cc4751b814a`; the retained
Test8r2 rollback image is 2,005,954,560 bytes /
`6a52f3388e9abf6afa8a701cfd7198fe6c0090f16531f6e3bd3949e760892ec8`. Exact extraction
reproduced the accepted system, vendor, product and vendor_dlkm hashes, the 3,221,225,472-byte
raw super, and the accepted boot, vendor_boot, vbmeta_system and top-level vbmeta payloads.
Inputs remained read-only and the accepted outer hash was unchanged after construction.

The first full exact VINTF run identified three concrete differences. The accepted vendor
manifest exposes `vendor.display.config@1.0::IDisplayConfig/default` and
`vendor.display.output.IDisplayOutputManager/default (@2)`, neither of which was declared in
the generic A16 device matrix. A bounded matrix fragment now declares exactly those two HALs.
The only remaining VINTF incompatibility is the actual 5.4.125 kernel's `CONFIG_NFS_FS=y`
against FCM-6's required `n`. The device-accepted Android 12 framework matrix also rejects the
same kernel for this same setting, and changing only the captured config to `n` makes the A16
full exact check pass. It is therefore an inherited BSP conformance deviation, not evidence of
a new A16 binary mismatch. It remains explicitly recorded as exit 65 / `INCOMPATIBLE`; this
study does **not** call full VINTF a pass.

The first exact split-SELinux compile failure was one duplicate `genfscon` ownership rule:
A16 platform labels `fuseblk /` as `fuseblk`, while the accepted API-31 vendor policy labels
the identical filesystem/path as `vfat`. Removing only the platform duplicate retains the
device-accepted vendor label and makes the complete A16 platform/system_ext plus accepted
vendor policy compile. Exact linkerconfig then generates the vendor/VNDK-31 namespace and
the `libaudioroute.so` link. A combined inventory finds 1,769 ELF objects, no AArch64
userspace ELF, and zero unresolved ELF32/ELF64 names. These are offline closure results, not
runtime library-loading or SELinux-enforcement proof.

Official LP tools confirm three identical metadata slots, metadata 10.2,
`virtual_ab_device`, the original 3,221,225,472-byte super and a 1,651,167,232-byte system
allocation. The Gate-1 image had 704,401,408 bytes of allocation headroom. The exact candidate
uses the existing allocation and preserves vendor, product, vendor_dlkm and all empty B-slot
bytes. System/vbmeta_system SHA256_RSA2048 verification passes with the project test key,
rollback index 1644019200 at location 1 is preserved, and the accepted top-level vbmeta is
unchanged. The outer audit preserves 46 of 50 payload entries; only super and vbmeta_system
are replaced and their two V checksum companions regenerated. Boot/kernel, vendor_boot,
DTBO, TEE, metadata, media_data and every other outer payload remain byte-identical.

The resulting single candidate is
`out/candidates/a16-prototype-a-r1/x12-a16-prototype-a-r1.img`, 1,261,038,592 bytes,
SHA-256 `a034c8193236c93746e5962cb3e7f26a1d56cec1435d5ad9d95f653b60bebd83`. Its
`system_a.img` is 1,651,167,232 bytes /
`24cf6c9109cfdbbc8db3a068e73eb5cd090440f58540ae6d62b8b667db7da2b5`; its filesystem
semantic delta from the accepted Gate-1 output is exactly the device matrix and platform CIL
files above, with ownership, mode and SELinux xattrs preserved. Ext4, SHA256SUMS, AVB, LP,
IMAGEWTY, exact compatibility checks, focused tests and all 70 repository tests pass (25
expected skips for absent ignored historical fixtures). The final detached construction took
130 seconds, used no swap, and left about 181 GiB free on `/work`.

This evidence raised Prototype A from a standalone system image to an **OFFLINE CHECKED
CANDIDATE eligible for one separately authorized UART-first boot**. That authorization was
subsequently granted and consumed by the physical result below. Gate 2 remains closed and
Prototype B remains untouched.

### Gate 2 r1 physical result and superseding pre-exec cgroup boundary

The PhoenixCard capture `logs/20260822-a-r1/uart-putty.log` is 44,206 bytes, SHA-256
`c4823f59f09fa2ed60e5f35251641b0b0e9abfafef1318f065dafbed901e4d0c`. All 13 download
parts and 26 MBR parts completed, the payload checksums matched, and the writer ended with
`sprite success` and `CARD OK`. The pre-rewrite fallback from an old primary GPT and alignment
warnings are not write failures and cannot explain the deterministic Android restart.

The UART boot capture `logs/20260822-a-r1/boot.log` is 78,275 bytes, SHA-256
`18bf7217afa25cab2b7443b17a801d8825932fa4eb15adcfc87d6fe1c3f46c7f`. It contains seven
kernel starts and six complete failure cycles. Every complete cycle reaches the Android 16
second-stage init cgroup setup, then 10.03 seconds later enters the failure reboot path and
ends with `reboot: Restarting system with command 'bootloader,bootstrap-apexd-failed'`.
The seventh capture stops after the same cgroup point. This repeatability rules out a one-off
write, power or transient boot observation. That original capture did not reveal the internal
service-start error, but the later devkmsg diagnostic below does.

The diagnostic capture `logs/20260822-a-r1-devkmsg/boot-devkmsg-on.log` is 35,625 bytes,
SHA-256 `e3ef999e109b837c5dbb3390e110ec80ad3d9defe02f0b0caf581c46c4c2a517`.
`printk.devkmsg=on` was appended only to the U-Boot RAM environment after `run setargs_mmc`,
was read back in `bootargs` before `run boot_normal`, and was not persisted. Its first cycle
exposes the actual failure sequence at 5.204791–5.313805 seconds.

The exact first reproducible runtime boundary is therefore:

1. the accepted 5.4.125 kernel starts and the accepted first-stage init maps the logical
   partitions;
2. `/system` is usable because its `secilc` executes, while the exact vendor and system_ext
   CIL inputs are consumed and the split policy compilation succeeds;
3. SELinux setup completes sufficiently to enter Android 16 second-stage init and `early-init`;
4. A16 `CgroupSetup()` fails its required v1 blkio mount before creating the cgroup-v2
   `apps` and `system` subhierarchies;
5. init forks ueventd PID 163 and apexd-bootstrap PID 164, but parent-side process-group setup
   fails for both and the children fatal-exit before `execv()`;
6. the declared `reboot_on_failure reboot,bootloader,bootstrap-apexd-failed` action then runs.

Neither ueventd nor apexd is executed, so bootstrap APEX activation is not attempted. No
capture proves that a bootstrap APEX mounted. `servicemanager`, `zygote32`,
`system_server`, SurfaceFlinger and HWC/composer do not appear and were not reached. The kernel
command line selects SELinux permissive, so successful split-policy loading is not enforcing
compatibility proof.

The four conspicuous messages have distinct control-flow meanings:

- `Could not update logical partition` is emitted by `MountMissingSystemPartitions()` when it
  cannot create a separate logical `system_ext` mapping. The code continues, and this candidate
  deliberately supplies `/system_ext -> /system/system_ext`; it is a non-fatal fallback.
- secilc warns that `/linkerconfig/ld.config.txt` does not exist during first-stage split-policy
  compilation. Android 16 creates and bind-mounts the bootstrap linker configuration later in
  `early-init`; the compiler returns success and second-stage init executes. The warning is not
  the bootstrap failure.
- `cgroup1: Unknown subsys name 'blkio'` matches the exact kernel's disabled
  `CONFIG_BLK_CGROUP` and is the first causal error. It makes the required blkio mount return
  `EINVAL`; the following missing `/sys/fs/cgroup/system/uid_0` is its direct consequence.
- retries for `/dev/block/by-name/misc` begin only after init has selected the
  `bootstrap-apexd-failed` bootloader reboot. They prevent persistence of the bootloader message
  but neither select nor cause the failure.

The earlier APEX audit remains useful negative evidence but is no longer the root-cause path:
had `apexd --bootstrap` executed, it would scan preinstalled APEXes, reserve loop/device-mapper
resources and activate the bootstrap set. The exact build uses the legacy two-namespace path
(`RELEASE_APEX_MOUNT_BEFORE_DATA` false) and requires five bootstrap containers: i18n, runtime,
tzdata, virt and VNDK 31. All five are uncompressed APEXes, parse with the exact
`host_apex_verifier`, and contain clean 4 KiB-block ext4 payloads. Their on-image sizes and
SHA-256 values are respectively 35,864,576 / `9451a568822aa459c4f602f41fb48fa15e9e14cce3e25fcfde60456511fc12e5`,
4,554,752 / `d650bbcc87a7c986de211483958465263766cb47ca94fa9b660a08e8686fcef1`,
950,272 / `4fa24e4d5a723f19b4bd3d80c99f3a71e7ca1e2069875ae7ed45920f5263febf`,
1,036,288 / `742d9e06ba9a7b3c400efcb9302fcb6883709b246236808d160f3069330916c6`,
and 17,743,872 / `fb94b4e2ba84bdefddfaf59729fdae87b0195d2eefd972fd69235dd7a12d705e`.

The ARM32 apexd executable, bootstrap linker, direct libraries and SELinux labels are present.
The exact H616/sun50iw9 5.4.125 configuration and source provide built-in loop,
`LOOP_CONFIGURE` plus the legacy loop fallback, device mapper/uevent/verity/FEC, ext4,
fs-verity, mount namespaces, SELinux, seccomp and the required SHA/RSA crypto. EROFS is absent,
but these bootstrap payloads are ext4. These facts eliminate simple container corruption,
missing executable/interpreter and wholly absent loop/DM/ext4 support; they do not prove that
device nodes, coldboot, a particular loop/DM ioctl, namespace mount, AVB verification or an
SELinux operation succeeds at runtime. Unlike r1, the accepted Android 12 image uses flattened
APEX directories, so the accepted baseline did not exercise this container activation path.

The A16 source trace explains why no apexd line exists. In exact r4,
`system/core/init/init.cpp:647-654,1205-1207` queues `SetupCgroupsAction` before `early-init`.
`system/core/libprocessgroup/setup/cgroup_map_write.cpp:272-314` loads system/API/vendor
descriptors and returns false at lines 293-295 as soon as a required controller setup fails;
its later `CreateV2SubHierarchy(.../apps)` and `.../system` calls at lines 299-310 never run.
`system/core/init/service.cpp:551-581,734-745` shows that `Service::Start()` forks and makes each
child wait on a FIFO while the parent calls `createProcessGroup(0, pid, false)`. The flag-aware
UID mapping selects `/sys/fs/cgroup/system/uid_0`; mkdir fails in
`system/core/libprocessgroup/processgroup.cpp:685-719`, so the parent writes
`kActivatingCgroupsFailed`. The child logs `Service '<name>' failed to start due to a fatal
error` and exits before task profiles, credentials/capabilities and `ExpandArgsAndExecv()`.
The missing `pid_163`/`pid_164/cgroup.procs` lines are cleanup cascade, not independent causes.

The effective A16 `/system/etc/cgroups.json` (SHA-256
`ab2ed667ff45958843fb0c6ee953a5512def0ae87470c4358aa9576a6a4b2e22`) requires v1
blkio, cpu and cpuset; none is optional. Its cgroup-v2 root is `/sys/fs/cgroup`, freezer is
required, and memory is `NeedsActivation` but optional. `/system/etc/task_profiles.json`
(`f230763e7676dfb39397c2d909def41ddd59d73ff7b334718b885ce24095bf21`) uses all of these,
including blkio membership profiles. With first API level 31, the loaders would overlay
`cgroups_31.json` and `task_profiles_31.json`, then vendor files, but both API-specific system
files and exact accepted `/vendor/etc/cgroups.json` plus `/vendor/etc/task_profiles.json` are
absent. The accepted A12 system files (hashes
`8898401625cc4bd524a024104c9277382e03926b32ee5bec1ad548d1cf8a2e1f` and
`ab6afdd8975620300781d283344af6acf036145c73311353d2da54522f39f933`) also require
blkio/cpu/cpuset; A12 additionally described optional v1 memory. There is no hidden vendor
override that could make the A16 required mounts optional.

The retained exact kernel config has `CONFIG_CGROUPS=y`, `CONFIG_CGROUP_SCHED=y`,
`CONFIG_CGROUP_CPUACCT=y`, `CONFIG_CGROUP_FREEZER=y` and `CONFIG_CGROUP_BPF=y`, but both
`CONFIG_BLK_CGROUP` and `CONFIG_CPUSETS` are disabled; `CONFIG_MEMCG` is also disabled. The
exact 5.4 source implements Android's required cpuset `noprefix,cpuset_v2_mode` mount options.
Enabling BLK_CGROUP alone is insufficient because the next required cpuset mount would fail.
The source-proven minimum is `CONFIG_BLK_CGROUP=y` plus `CONFIG_CPUSETS=y`, with Kconfig adding
`CONFIG_PROC_PID_CPUSET=y`; generic blkio membership does not require enabling a throttling or
I/O-cost policy. MEMCG remains out of the bounded delta because the effective A16 memory-v2
descriptor is explicitly optional.

The complete relevant kernel-config comparison is:

| Capability | retained r1 | r2 | A16 role in this exact product |
|---|---:|---:|---|
| `CONFIG_CGROUPS` | y | y | fundamental v1/v2 hierarchy support |
| `CONFIG_BLK_CGROUP` | n | y | required v1 `blkio`; first r1 failure |
| `CONFIG_CGROUP_SCHED` / `FAIR_GROUP_SCHED` | y / y | y / y | required v1 `cpu` mount and memberships |
| `CONFIG_CPUSETS` / `PROC_PID_CPUSET` | n / absent | y / y | required v1 `cpuset` and Android mount behavior; next r1 blocker |
| `CONFIG_CGROUP_CPUACCT` | y | y | retained Android CPU-accounting contract |
| `CONFIG_CGROUP_FREEZER` | y | y | required controller on the declared cgroup-v2 root |
| `CONFIG_MEMCG` | n | n | declared v2 `NeedsActivation`, but explicitly optional |
| `CONFIG_CGROUP_BPF` / `BPF` / `BPF_SYSCALL` | y / y / y | y / y / y | retained v2/BPF attachment capability |
| `CONFIG_CGROUP_PIDS`, `CGROUP_DEVICE`, `CGROUP_PERF` | n / n / n | n / n / n | not declared by the effective A16 cgroups/task-profile set |
| `CONFIG_CGROUP_NET_PRIO`, `CGROUP_NET_CLASSID` | n / n | n / n | not declared by the effective set |

The generic cgroup-v2 mount itself is provided by `CONFIG_CGROUPS`; this 5.4 tree has no
separate `CONFIG_CGROUP_V2` switch. The declared v2 controllers are freezer plus optional
memory, so r2 supplies every required v2 controller without pretending that absent optional
MEMCG is enabled.

The build flag is consistent: exact
`out-ceiling/soong/soong.ubox10_ceiling_arm.variables:970` sets
`cgroup_v2_sys_app_isolation=true`. `system/core/libprocessgroup/Android.bp:18-26,86` applies
the corresponding `libprocessgroup_build_flags_cc` to path selection/process-group creation,
and `system/core/libprocessgroup/setup/Android.bp:21-43` applies the same default to early
hierarchy creation. The present classification is therefore **bounded
retained-kernel cgroup integration defect before apexd exec**, not an APEX activation failure
and not an architecture-level no-go. One boot-only r2 with the minimum config delta was
justified and has been constructed offline; no further physical action is authorized and
rollback inputs remain unchanged.

## 11. Boot-readiness analysis after r1

The furthest runtime-proven point is **Android 16 second-stage init at required cgroup
initialization, before ueventd or apexd exec**. The table keeps packaging evidence, runtime proof and
unreached stages separate.

| Area | Status | Evidence and boundary |
|---|---|---|
| 1. Boot/kernel contract | **PROVEN TO INIT** | The accepted 5.4.125 kernel boots r1 repeatedly and reaches Android init; this does not prove later Android 16 services. |
| 2. First-stage init | **PROVEN** | The accepted boot/vendor_boot first stage executes, maps logical partitions and hands off to the new system. |
| 3. First-stage mount | **PROVEN FOR CURRENT BOUNDARY** | `/system` executes A16 secilc; vendor and system_ext policy inputs are consumed. Direct metadata mount details are not all printed and are not overclaimed. |
| 4. AVB | **RUNTIME ACCEPTED TO INIT** | The candidate passes the boot chain far enough to execute the verified system; mixed mode would still change vendor-owned `ro.zygote`. |
| 5. Dynamic partitions | **RUNTIME PROVEN TO SYSTEM HANDOFF** | LP mapping and current system handoff succeed; the missing separate system_ext update is a tolerated fallback to the system-root symlink. |
| 6. `apexd` | **NOT EXEC'D** | Init forks the service child, but parent-side `createProcessGroup()` fails and the child exits before `ExpandArgsAndExecv()`; APEX activation is not attempted. |
| 7. `servicemanager` | **NOT REACHED** | It starts after bootstrap activation; it is absent from all cycles. |
| 8. `hwservicemanager` | **NOT REACHED** | No registration appears before bootstrap apexd selects the reboot path. |
| 9. VINTF | **EXACT CHECKED; INHERITED EXCEPTION** | Exact system/product/vendor/device checks leave only `CONFIG_NFS_FS=y` versus FCM-6 `n`, the same deviation already present against the device-accepted A12 matrix. The two accepted display HALs are declared. Full check remains exit 65, not PASS. |
| 10. Linker namespaces | **OFFLINE CHECKED; RUNTIME NOT REACHED** | Exact linkerconfig generates ARM32 vendor/VNDK-31 closure. The early secilc warning predates linkerconfig creation and is non-fatal; apexd never execs. |
| 11. Zygote | **NOT REACHED** for A; **KNOWN BLOCKER** for mixed packaging | Accepted vendor selects `zygote32`, matching Prototype A, but r1 fails before zygote. Prototype B would additionally require the retained vendor property change. |
| 12. `system_server` | **NOT REACHED** | No A16 zygote or framework process starts. |
| 13. SurfaceFlinger | **NOT REACHED** | r1 stops before servicemanager/zygote; the prior ARM32 provider likelihood is not runtime proof. |
| 14. HWC/composer | **NOT REACHED** | No composer/HWC registration appears. |
| 15. Media services | **NOT REACHED** | Accepted 32-bit OMX/Cedar services are process-isolatable, but r1 stops before their A16 compatibility can be exercised. |
| 16. Audio service/HAL | **NOT REACHED** | Accepted Apollo HAL is process-isolatable, but r1 stops before audio framework/HAL startup. |
| 17. Wi-Fi | **NOT REACHED** | Accepted AIC8800 kernel/HAL path is proven only on Android 12. |
| 18. Bluetooth | **NOT REACHED** | Accepted binderized 32-bit service/HAL path is proven only on Android 12. |
| 19. Input | **NOT REACHED AT FRAMEWORK LEVEL** | Kernel/UART evidence transfers, but A16 input framework and TV policy never start. |
| 20. DRM | **NOT REACHED** | The 32-bit L3 service is process-isolatable, but A16 MediaDrm/HIDL compatibility and playback are unexercised. No higher security claim is made. |

The one r1 authorization has been consumed and the RAM-only devkmsg diagnostic has established
the pre-exec cgroup root cause above. Gate 2 is closed. The smallest next experiment is the one
offline boot-only r2 described above; it has now been constructed and audited without a physical
action.

### Prototype A r2 offline result

The one r2 candidate changes only the retained kernel and its boot/Vboot outer payloads. Its
effective config delta is `CONFIG_BLK_CGROUP=y`, `CONFIG_CPUSETS=y` and Kconfig-generated
`CONFIG_PROC_PID_CPUSET=y`; MEMCG and the newly visible blkio throttling/IOLATENCY/IOCOST
policies remain disabled. Kernel source is pinned to Orange Pi commit
`9ab7a758149d3c9b721878a0c18b3f9c5d6c93e6` and built with AOSP `clang-r416183b1`.
The r1 system/APEX/super/LP, accepted vendor_boot/ramdisk, vendor/product/vendor_dlkm,
vbmeta/vbmeta_system and all other 48/50 outer payloads are byte-identical.

The final IMAGEWTY image is 1,261,038,592 bytes, SHA-256
`114df8677cd6984eb1431377723edf61c80acf26c15d8770bae47dcfe7d1b6d0`; boot is
67,108,864 bytes / `4f0db0070e294dea93319f4b21335e6725dbb7b70066e7c1e6bf55cfeb09c10c`,
and kernel is 23,232,520 bytes /
`5d7d7f84a8e3cbcc4a4af78a9eb4decac846e62ba4c681e85b438b69b196ebf3`.
Boot AVB, IMAGEWTY, ext4, cgroup-contract and SHA checks pass. Full exact VINTF still returns
65 only for the inherited `CONFIG_NFS_FS=y` versus FCM-6 `n`; the cgroup delta adds no new
incompatibility. Linker/ELF, split SELinux, APEX and LP evidence transfers only because the
containing partitions were proven byte-identical.

This is the smallest evidence-backed correction and is coherent enough to request a separate
authorization for one UART-first ARM32 exact-board boot. It is not physical boot evidence,
does not close Gate 2, and does not authorize Prototype B.

## 12. Target A/B/C/D comparison

All scores use 1 (poor) through 5 (strong); for effort/risk, a higher score means lower cost or
lower risk. They are decision aids grounded in the evidence above, not synthetic precision.

| Decision criterion | A: Android 12 ARM32 | B: Android 16 ARM32 | C: Android 16 mixed | D: full modern ARM64/kernel |
|---|---:|---:|---:|---:|
| Daily-use stability now | 5 | 3 | 2 | 1 |
| Accepted-function preservation | 5 | 4 | 3 | 1 |
| Modern app/API compatibility | 2 | 4 | 5 | 5 |
| 64-bit native-app support | 1 | 1 | 5 | 5 |
| Expected useful lifetime | 2 | 4 | 5 | 5 |
| Graphics viability | 5 | 5 | 3 | 1 |
| Media quality preservation | 5 | 4 | 4 | 2 |
| Netflix/commercial-streaming potential | 2 | 2 | 2 | 2 |
| HDMI/audio preservation | 5 | 4 | 4 | 2 |
| Exact hardware support | 5 | 4 | 3 | 1 |
| Donor/provider availability | 2 | 3 | 4 | 1 |
| Kernel risk | 5 | 4 | 4 | 1 |
| Engineering return / low effort | 5 | 4 | 3 | 1 |
| Regression and recovery control | 5 | 4 | 3 | 1 |
| Maintainability/security potential | 2 | 3 | 4 | 4 |
| **Unweighted total / 75** | **56** | **53** | **54** | **32** |

The similar raw totals for A/B/C expose the actual trade: A wins stability and cost but loses
future usefulness; B gains platform life but not 64-bit apps; C has the best long-term value if
the small graphics-provider gate passes. The project objective weights app longevity and
avoiding a second architecture replacement more than the unweighted table does, which makes C
the preferred formal target. D is dominated on engineering economics.

| Family | Viability | Main advantage | Decisive blocker/limit | Engineering risk | Verdict |
|---|---|---|---|---|---|
| Target A — Mature Legacy | **PROVEN now** | Accepted stability and hardware completeness | API 31 age and no 64-bit native apps; security/platform life is short | Low | Keep as rollback/reference, not final investment ceiling |
| Target B — Modern Framework / Legacy Architecture | **HIGH** if A16 ARM32 boots | Maximum vendor reuse and no new graphics provider | Still excludes 64-bit-only native apps and invites another later architecture migration | Medium | Fallback architecture, not primary |
| Target C — Modern Hybrid | **MEDIUM** | API 36 plus AArch64 apps while preserving working 32-bit HALs/kernel | Paired ARM64 graphics SP-HAL/mapper must close and run on exact H616; the A16 ARM32 base is built but unbooted | Medium-high but bounded | **Recommended final target; conditional GO** |
| Target D — Full Modern Port | **LOW** | Clean contemporary architecture in theory | No complete H616 5.10+ graphics/media/display/DRM provider; becomes multiple subsystem rewrites | Extreme | **NO-GO** |

## 13. Reuse versus rewrite map

### Reusable unchanged or nearly unchanged

- Stock/accepted boot chain, AArch64 5.4 kernel, DT/DTBO, vendor_boot, vendor, vendor_dlkm,
  TEE/factory/security partitions and dynamic-partition topology, except for the bounded
  addition of matched ARM64 graphics client files in the mixed target.
- Working 32-bit HWC/composer, media/Cedar, audio, Wi-Fi/Bluetooth, DRM/TEE and remaining HAL
  services behind stable IPC.
- Native rc-core work, AIC8800 kernel modules/firmware, input key evidence, HDMI/audio and
  codec acceptance evidence.
- Stock and accepted rollback assets, PhoenixCard/recovery practice, outer-container
  preservation, LP extraction/repack, AVB verification, ext4 checks and candidate-audit tools.
- Current architecture inventories, read-only device capture practices and reproducible ELF
  census tooling.

These are safe investments now: exact hardware regression tests, recovery, kernel-driver fixes
that preserve ABI, remote/wake reliability, audio/media test assets and hardware evidence.

### Reusable conceptually, requiring A16 reintegration and revalidation

- UBOX device/product configuration, TV characteristics, partition sizing and FCM/VNDK
  declarations.
- Projectivy/TV-home integration, Leanback IME, provisioning, remote provider/service,
  permissions, RROs and power/input policies.
- System-side SELinux, init, linker namespace and compatibility-library work. Policies and
  module names change across releases even when the behavior remains valuable.
- Build orchestration and system-image assembly logic. The preservation invariants remain;
  A16 Soong/product rules and image composition must be native to A16.
- Functional acceptance suites for boot, graphics, audio, network, Bluetooth, input, media and
  DRM.

### Likely replaced or not worth deep optimization before migration

- Android 12 `system`/`system_ext`/`product` binaries, ARM32 framework artifacts, WebView and
  A12-specific generated linker/APEX state.
- Framework-version-specific overlays, compatibility shims and direct image edits whose only
  purpose is polishing the current API-31 system rather than preserving a hardware contract.
- A full A12 UI/app cleanup program and any attempt to make the current 32-bit product the
  permanent endpoint.
- A speculative mainline kernel, Mesa/Panfrost, full Codec2 conversion or DRM "upgrade" before
  the A16 hybrid boot/graphics gate is answered.

## 14. Recommended Final Target

### Architecture

| Element | Final target |
|---|---|
| Android generation | Android 16 for TV / API 36, based on stable `android-16.0.0_r4` |
| Userspace | Mixed AArch64 primary + ARM32 secondary |
| Zygote | `zygote64_32` |
| Kernel | Retain exact Allwinner H616 AArch64 5.4.125 lineage; no GKI claim |
| Vendor | Preserve accepted vendor/vendor_dlkm and all working ARM32 hardware services; add hash-pinned matched ARM64 graphics files, set `ro.zygote=zygote64_32`, correct the mapper bitness contract, and revalidate vendor/root AVB |
| Graphics | Paired ARM64 Mali-G31 EGL/GLES plus AArch64 mapper/gralloc; retain 32-bit counterparts and 32-bit SUNXI HWC/composer |
| Media | Retain 32-bit Allwinner OMX/Cedar service path; do not rewrite to Codec2 merely for elegance |
| Audio | Retain 32-bit Apollo HAL and accepted HDMI route |
| DRM/Netflix | Preserve current Widevine/TEE state; target only legitimate L3/basic playback; no HD/4K promise |
| Display/media | 1080p rendered UI; retain 4K60 HDMI output; target reliable 4K30 hardware video, with 4K60 decode/HDR as optional evidence-led stretch |
| App ecosystem | AArch64 apps preferred with ARM32 fallback; API 36 framework; no GMS/Play claim from the prototype |
| Intentionally legacy | Kernel, boot/vendor boundary and most hardware-facing services remain 32-bit/BSP-derived |
| Must change | Framework/system/product; vendor-owned zygote selection and affected AVB metadata; AArch64 graphics SP-HAL/mapper path; product/VINTF/linker/SELinux integration; release-specific TV components |

### Why this target?

1. Android 16 is the current official TV generation; Android 17 currently has no official TV
   destination. **PROVEN**.
2. Android 16 officially supports the current vendor's FCM level 6 upgrade contract.
   **PROVEN**.
3. The device has an ARMv8 CPU, AArch64 kernel, 32-bit compat and 64-bit Binder contract.
   **PROVEN**.
4. The accepted runtime has no AArch64 userspace, but almost all proprietary HAL code is in
   isolatable 32-bit services. **PROVEN/HIGH CONFIDENCE**.
5. The minimum mandatory mixed-mode blockers are graphics SP-HAL/mapper, not all 300 vendor
   ELF files. **HIGH CONFIDENCE**.
6. The public same-lineage donor's ARM32 Mali file exactly matches UBOX and it supplies the
   paired AArch64 library plus multilib mapper/gralloc source. **PROVEN provider existence;
   MEDIUM exact-board runtime confidence**.
7. The current 5.4 stack already preserves the hardest hardware assets; no complete newer
   H616 Android BSP justifies replacing it. **HIGH CONFIDENCE**.
8. The box already exposes a live 4K60 HDMI output and hardware media path, so keeping the
   vendor stack has more user value than a clean port that regresses acceleration. **PROVEN
   output; MEDIUM 4K media confidence**.

### Why not stay on Android 12 forever?

Android 12 remains the strongest rollback and near-term daily image, but API 31, an old patch
level and ARM32-only native-app support impose a real ecosystem ceiling. Continued framework
polish cannot add AArch64 app execution or close the growing target-API gap. It is rational to
finish only hardware/recovery work that transfers to the hybrid and avoid making API 31 the
long-term endpoint.

### Why not choose the more ambitious architecture?

A full ARM64 vendor conversion or 5.10+/mainline port replaces working graphics, media,
display, audio, wireless and DRM integration without a complete provider. It has no evidence
of better Netflix capability and may lose the current 4K/audio path. The modern hybrid captures
the application/framework benefit of ARM64 without paying that subsystem-rewrite cost.

**Overall confidence: MEDIUM.** The Android 16 ARM32 build/offline integration, r1 pre-exec
cgroup trace and bounded r2 correction are strong evidence. Runtime still has not proved the
corrected cgroup hierarchy, apexd execution or any later framework/graphics stage. The
end-state hybrid remains plausible; starting Prototype B before closing this base would not be
justified.

## 15. Go / No-Go decisions and remaining decisive gates

### Required decisions

| Question | Decision | Reason |
|---|---|---|
| Recommended modern Android target | **HOLD — Android 16 for TV remains preferred if r2 runtime advances** | r1 reaches A16 init; pre-exec cgroup root cause is bounded and r2 is offline checked |
| Android 16 specifically | **HOLD FOR ONE R2 PHYSICAL AUTHORIZATION** | r2 closes the source-proven kernel config defect offline; cgroup setup, apexd exec and later stages remain untested |
| Mixed ARM64/ARM32 userspace | **CLOSED PENDING PROTOTYPE A** | Exact paired Mali provider exists, but the common A16 ARM32 bootstrap base has not passed |
| Full ARM64 userspace | **NO-GO** | Would convert/replace working proprietary service stack for little user value |
| Kernel 5.4 as final architecture | **CONDITIONAL GO** | Technically credible for upgraded FCM 6; outside current ACK support and must pass A16 runtime |
| Kernel 5.10+ migration | **NOT ECONOMICALLY JUSTIFIED** | No complete exact-SoC/board Android provider; regression surface is disproportionate |
| >1080p media target | **PLAUSIBLE** | Physical 4K60 output and 4K codec declarations exist; sustained physical 4K decode is not proven |
| Netflix above current basic/L3 class | **STRUCTURALLY BLOCKED** | L3, HDCP NONE, no secure decoder/protected path; service certification remains an additional gate |

### Remaining decisive gates (maximum four)

1. With separate explicit authorization, boot exactly `a16-prototype-a-r2` once UART-first,
   append `printk.devkmsg=on` in U-Boot RAM only, and prove required cgroup mounts,
   `/sys/fs/cgroup/system`, ueventd/apexd exec and the next first runtime boundary.
2. If Prototype A passes, establish lawful, reproducible availability of the paired AArch64
   Mali and multilib mapper/gralloc provider, then complete its A16 DT_NEEDED/linker closure and
   mixed image.
3. With separate authorization, boot the mixed candidate and prove AArch64 GLES/SurfaceFlinger
   plus retained 32-bit HWC/media/audio/Wi-Fi/Bluetooth/input/DRM service parity.
4. Prove sustained physical 4K30 HEVC/VP9, A/V sync and thermal behavior before calling 4K30
   accepted; failure keeps the architecture but lowers the media target to 1080p-class.

## 16. Direct route to the target

1. **Completed — freeze the accepted baseline and provider contract:** keep `m8b-remote-r1` rollback,
   exact hashes, hardware evidence and donor/provider rights/hash manifest.
2. **Completed — exact ARM32 integration:** pair the completed Prototype A system image with the accepted
   partitions, close VINTF/linker/SELinux/AVB/LP checks and audit one rollback-safe candidate.
3. **Current — corrected ARM32 base runtime proof:** the RAM-only devkmsg diagnostic proved r1
   fails before ueventd/apexd exec, and the minimal boot-only r2 is offline checked. Wait for
   separate one-cycle r2 physical authorization; no flash is currently authorized.
4. **Conditional mixed proof:** only after the ARM32 base passes, build the minimal
   `zygote64_32` product with the lawful paired graphics provider, close its offline checks and
   perform a separately authorized boot/parity test.
5. **Final acceptance:** sustained daily-use regression, 4K30-or-1080p evidence-led media
   ceiling, recovery rehearsal and a hash-locked accepted architecture image.

## 17. Sources and provenance

Web sources were accessed on 2026-08-17. Primary/official sources are used for platform,
kernel and board claims.

- [Android 16 for TV](https://developer.android.com/tv/release/16)
- [AOSP codenames, tags and build numbers](https://source.android.com/docs/setup/reference/build-numbers)
- [`android-16.0.0_r4` manifest tag](https://android.googlesource.com/platform/manifest/+/refs/tags/android-16.0.0_r4)
- [Android common kernels](https://source.android.com/docs/core/architecture/kernel/android-common)
- [Android kernel architecture/GKI](https://source.android.com/docs/core/architecture/kernel)
- [FCM lifecycle and Android 16 supported levels](https://source.android.com/docs/core/architecture/vintf/fcm)
- [VINTF match rules](https://source.android.com/docs/core/architecture/vintf/match-rules)
- [VNDK overview and Android 15 deprecation exceptions](https://source.android.com/docs/core/architecture/vndk)
- [Android 17 platform release](https://developer.android.com/about/versions/17/)
- [Google Play target API requirements](https://developer.android.com/google/play/requirements/target-sdk)
- [Google Play 64-bit requirement](https://developer.android.com/google/play/requirements/64-bit)
- [Banana Pi M4 Zero official wiki](https://wiki.banana-pi.org/Banana_Pi_BPI-M4_Zero)
- [BPI H618 Android 12 public source](https://github.com/BPI-SINOVOIP/BPI-H618-Android12)
- [Orange Pi Zero 2 official wiki](http://www.orangepi.org/orangepiwiki/index.php/Orange_Pi_Zero_2)
- [Orange Pi Zero 2W official wiki](http://www.orangepi.org/orangepiwiki/index.php/Orange_Pi_Zero_2W)
- [Orange Pi official build source](https://github.com/orangepi-xunlong/orangepi-build)
- [Linux mainline](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/)

Local primary evidence includes the accepted-image hashes and logical partitions, generated
ELF inventory, live read-only ADB capture in `work/architecture-ceiling/device-evidence/`,
the read-only Android 12 UBOX product, current repository candidate/device-test records, the
isolated Android 16 tree and donor metadata cache. Raw evidence and large artifacts remain
ignored or outside Git; no DRM secret material was collected.
