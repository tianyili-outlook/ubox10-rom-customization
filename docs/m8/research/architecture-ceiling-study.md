# UBOX10 Architecture Ceiling Study

Study date: 2026-08-17

Study branch/base: `codex/m8-architecture-ceiling` / `c30c8d0bbbcab5667a9aeaaf9cbfadbdf168d401`

Runtime baseline: accepted `m8b-remote-r1` on the physical UBOX10, observed over read-only ADB
Scope: architecture decision and bounded offline prototype configuration/attempt; no device mutation or flash

Confidence labels in this report have the following strict meanings: **PROVEN** is direct
binary, build, runtime, repository, or authoritative-source evidence; **HIGH CONFIDENCE**
is converging evidence with no material contradiction; **MEDIUM CONFIDENCE** retains one
meaningful provider or runtime dependency; **LOW CONFIDENCE** is speculative. A capability
declaration is not called physically verified unless the physical device exercised it.

## 1. Executive architecture decision

The best architecture worth formally developing is **Android 16 for TV, mixed ARM64/ARM32
userspace, `zygote64_32`, the existing Allwinner 5.4 kernel and hardware-facing vendor stack,
plus only the minimum matched ARM64 graphics client provider and bounded vendor
zygote/AVB metadata changes**. This is **CONDITIONAL GO, MEDIUM confidence** pending the
bounded gates in section 15.

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

The isolated source tree is `/home/tianyi/ubox10-a16-ceiling`. Its source baseline is the
official `android-16.0.0_r4` tag / `BP4A.251205.006`; the retained pinned manifest is
`out-study/provenance/android-16.0.0_r4-pinned-manifest.xml`, SHA-256
`4e8beb5d1b590dff3d631b1dbb957138dbda4e608a3183c625683da4bc84918f`. The large output
container is the fixed-size, labeled ext4 image
`D:\ubox10-ceiling-study-storage\a16-out.ext4`. None of these paths is in Git.

Prototype A is a minimal Android 16 TV GSI-style ARM32 product. It inherits the official ATV
GSI base, uses the generic ARM board, models an Android 12/API-31 field upgrade, retains only
VNDK 31, disables pKVM and requests only `systemimage`; it intentionally produces no boot,
vendor, super or userdata image. Prototype B is configuration only: the generic ARM64 board
provides AArch64 primary plus ARM32 secondary ABI and `core_64_bit.mk` selects
`zygote64_32`. Neither product contains an Allwinner or donor binary.

### Recorded build result

**INCOMPLETE — HOST-LIMITED; no target image exists.** Prototype A product discovery,
release-config/dumpvars processing and Soong host bootstrap succeeded far enough to compile
and invoke `soong_build`. Three bounded observations followed:

1. An absolute `OUT_DIR` exposed an Android 16 `test_package` path-classification failure in
   `continuous_native_tests`. Exporting the same directory as relative `out-ceiling` removed
   that mechanical host-path error without changing target code.
2. A memory-constrained graph-generation attempt ended in a Go-runtime `SIGBUS`; this is a
   host resource failure, not a UBOX target ABI, VINTF, kernel or graphics result.
3. The corrected relative-path retry rebuilt the Soong host tool and spent approximately
   three hours in Android.bp graph analysis. It was terminated with the foreground execution
   session before a product Ninja graph was emitted. The ext4 image is clean, but
   `/soong/build.ubox10_ceiling_arm.ninja`, the product output directory and `system.img` are
   absent.

The surviving partial log is
`/home/tianyi/ubox10-a16-ceiling/out-study/logs/prototype-a-arm32-systemimage.log`, 37,699
bytes, SHA-256 `66ed74362f6bf7f6cbe190d1811c07c7d54a1c32a7797e348d9a8f1315617b6d`.
The Study build helper was then tightened to a fixed ext4 output, cgroup memory/swap limits,
relative `OUT_DIR`, a forwarded Go memory limit and a restricted CPU set. Its final resource
profile is syntax-checked but was not executed. The user explicitly directed that no further
disposable Android 16 build be run before this report was completed.

Prototype B was not built. Static evidence makes the mixed architecture credible, but lawful
availability and A16 closure of the required AArch64 Mali/mapper provider remain unresolved;
the explicit no-build direction independently ends the prototype budget here.

There is therefore no prototype image path, image size or image SHA-256, and no artifact is
flashable. This outcome neither proves nor disproves Android 16 bootability on the UBOX10; it
does prove that the checked-in minimal products reach the official A16 build machinery and
that this 16 GiB host cannot complete full Soong graph generation reliably under the bounded
foreground setup used in the Study. More host time/memory or a persistent bounded build is
required before target-level failures can be observed.

## 11. Static boot-readiness analysis

The furthest offline-proven point is **pre-image product configuration and Soong host-tool
bootstrap**. No Android boot stage is proven because no `system.img` exists. The table keeps
artifact/packaging blockers separate from structural architecture blockers.

| Area | Status | Evidence and boundary |
|---|---|---|
| 1. Boot/kernel contract | **LIKELY** | The accepted AArch64 5.4 kernel has ARM32 compat, Binder/binderfs and the relevant Android facilities, while A16 officially retains FCM 6. No A16 init binary has executed on it. |
| 2. First-stage init | **UNKNOWN UNTIL BOOT** | The GSI shape deliberately reuses the accepted boot/vendor_boot first-stage path. No A16 system image exists to test its userspace handoff. |
| 3. First-stage mount | **LIKELY** | The accepted first-stage fstab and A/B LP geometry are proven, and a GSI-style system replacement preserves them. No A16 system image was available for offline pairing. |
| 4. AVB | **KNOWN BLOCKER** for this output | No A16 image was assembled or signed. Mixed mode also changes vendor-owned `ro.zygote` and therefore requires a regenerated, verified AVB chain. |
| 5. Dynamic partitions | **LIKELY** | The accepted system/vendor/product/vendor_dlkm LP layout is proven and the A16 GSI uses dynamic sizing, but no combined A16 super was assembled. |
| 6. `apexd` | **UNKNOWN UNTIL BOOT** | Official A16 APEX composition is available in source; no product image or runtime exists. |
| 7. `servicemanager` | **UNKNOWN UNTIL BOOT** | Binder capability is proven on 5.4; the A16 binary/runtime contract is unexercised. |
| 8. `hwservicemanager` | **UNKNOWN UNTIL BOOT** | Current ARM32 HIDL services and FCM 6 are proven; A16 registration is not. |
| 9. VINTF | **LIKELY** | A16 officially supports target FCM 6 and the current device manifest uses 6. Exact system/product/device matrix matching was not generated. |
| 10. Linker namespaces | **UNKNOWN UNTIL BOOT** | VNDK 31 retention is configured, but even the offline generated namespace closure is absent. Mixed mode additionally requires the AArch64 graphics SP-HAL/mapper closure. |
| 11. Zygote | **LIKELY** for A; **KNOWN BLOCKER** for mixed packaging | Accepted vendor selects `zygote32`, matching Prototype A. A16 `core_64_bit.mk` selects `zygote64_32`, but the retained vendor property must be changed for Prototype B. |
| 12. `system_server` | **UNKNOWN UNTIL BOOT** | No A16 zygote or framework process has executed. |
| 13. SurfaceFlinger | **LIKELY** for A; provider-gated for mixed | ARM32 can in principle load the accepted ARM32 Mali/mapper. AArch64 SurfaceFlinger requires the matched AArch64 in-process provider. |
| 14. HWC/composer | **UNKNOWN UNTIL BOOT** | The accepted 32-bit binderized composer can be retained, but mixed buffer exchange and A16 client compatibility are unproven. |
| 15. Media services | **UNKNOWN UNTIL BOOT** | Accepted 32-bit OMX/Cedar services are process-isolatable; A16 framework compatibility is untested. |
| 16. Audio service/HAL | **UNKNOWN UNTIL BOOT** | Accepted Apollo HAL is process-isolatable; A16 policy/service compatibility is untested. |
| 17. Wi-Fi | **UNKNOWN UNTIL BOOT** | Accepted AIC8800 kernel/HAL path is proven only on Android 12. |
| 18. Bluetooth | **UNKNOWN UNTIL BOOT** | Accepted binderized 32-bit service/HAL path is proven only on Android 12. |
| 19. Input | **UNKNOWN UNTIL BOOT** | Kernel rc-core/input evidence transfers, but A16 framework, keylayout and TV-policy integration are absent. |
| 20. DRM | **UNKNOWN UNTIL BOOT** | The 32-bit L3 service is process-isolatable; A16 MediaDrm/HIDL compatibility and playback are untested. No higher security claim is made. |

A flash-gate package was not prepared: without an exact prototype image and SHA-256 there is
nothing safe to flash. After a successful offline image/integration pass, one physical boot
remains the smallest decisive test, but it still requires separate explicit authorization.

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
| Target C — Modern Hybrid | **MEDIUM** | API 36 plus AArch64 apps while preserving working 32-bit HALs/kernel | Paired ARM64 graphics SP-HAL/mapper must close and run on exact H616; A16 image build is incomplete | Medium-high but bounded | **Recommended final target; conditional GO** |
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

**Overall confidence: MEDIUM.** The decision is evidence-backed and the blocker set is small,
but no Android 16 image completed and the exact-board boot/provider gates remain.

## 15. Go / No-Go decisions and remaining decisive gates

### Required decisions

| Question | Decision | Reason |
|---|---|---|
| Recommended modern Android target | **CONDITIONAL GO — Android 16 for TV** | Best TV/API life and FCM-6 support; exact-board boot remains |
| Android 16 specifically | **CONDITIONAL GO** | Official stable TV/source target; Prototype A build and exact-board boot remain open |
| Mixed ARM64/ARM32 userspace | **CONDITIONAL GO** | Exact paired Mali provider exists; mapper/gralloc and runtime still gate |
| Full ARM64 userspace | **NO-GO** | Would convert/replace working proprietary service stack for little user value |
| Kernel 5.4 as final architecture | **CONDITIONAL GO** | Technically credible for upgraded FCM 6; outside current ACK support and must pass A16 runtime |
| Kernel 5.10+ migration | **NOT ECONOMICALLY JUSTIFIED** | No complete exact-SoC/board Android provider; regression surface is disproportionate |
| >1080p media target | **PLAUSIBLE** | Physical 4K60 output and 4K codec declarations exist; sustained physical 4K decode is not proven |
| Netflix above current basic/L3 class | **STRUCTURALLY BLOCKED** | L3, HDCP NONE, no secure decoder/protected path; service certification remains an additional gate |

### Remaining decisive gates (maximum five)

1. Complete Prototype A `systemimage` in an adequately resourced, persistent build and prove
   its APEX, VINTF, linker, SELinux and image composition offline; the current host-limited
   attempt did not reach target analysis.
2. Establish lawful, reproducible availability of the exact paired AArch64 Mali and multilib
   mapper/gralloc provider, then complete its A16 DT_NEEDED/linker closure and mixed image.
3. With separate authorization, perform one rollback-controlled physical boot and prove
   first-stage mount through `apexd`, `zygote64_32`, `system_server`, AArch64 GLES,
   SurfaceFlinger and retained 32-bit SUNXI HWC; failure selects Target B, not a graphics rewrite.
4. Prove retained 32-bit media/audio/Wi-Fi/Bluetooth/input/DRM services reach functional parity.
5. Prove sustained physical 4K30 HEVC/VP9, A/V sync and thermal behavior before calling 4K30
   accepted; failure keeps the architecture but lowers the media target to 1080p-class.

## 16. Direct route to the target

1. **Freeze the accepted baseline and provider contract:** keep `m8b-remote-r1` rollback,
   exact hashes, hardware evidence and donor/provider rights/hash manifest.
2. **Architecture proof:** complete the ARM32 A16 isolation image, then the minimal
   `zygote64_32` product with VNDK 31/FCM 6, paired graphics provider and offline
   VINTF/linker/AVB/LP validation.
3. **One authorized flash-gate boot:** capture UART/ADB milestones; stop on first reproducible
   failure and roll back rather than broad-porting.
4. **Minimum viable parity:** retain and validate the 32-bit hardware services, TV home/input,
   network/Bluetooth, HDMI audio, hardware media and legitimate L3 DRM.
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
