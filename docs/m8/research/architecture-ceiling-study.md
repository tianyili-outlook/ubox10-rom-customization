# UBOX10 Architecture Ceiling Study

Study date: 2026-08-17; build/runtime/source evidence updated: 2026-08-26

Study branch/evidence base: `codex/m8-architecture-ceiling` / starting commit
`f40a37b6fd488800b5a1ada89f2ce2cf687e8e33`, plus the hash-locked Linux 5.4.302
checkpoint inputs and results recorded below

Accepted rollback/runtime baseline: frozen `m8b-remote-r1`; latest physically accepted kernel
checkpoint: `m8-kernel-5.4.302-r5`
Scope: architecture decision, bounded offline prototypes, completed physical evidence through
Linux 5.4.302 r5, exact QPR0 r7 source audit, the Prototype A r3 build/full offline audit,
2026-08-25 r3 local physical validation, and the strict two-delta Prototype A r4 build/full
offline audit. No Prototype B or mixed-ABI work was performed.

Confidence labels in this report have the following strict meanings: **PROVEN** is direct
binary, build, runtime, repository, or authoritative-source evidence; **HIGH CONFIDENCE**
is converging evidence with no material contradiction; **MEDIUM CONFIDENCE** retains one
meaningful provider or runtime dependency; **LOW CONFIDENCE** is speculative. A capability
declaration is not called physically verified unless the physical device exercised it.

## 1. Executive architecture decision

The selected Android 16 direction is **Path A: official `android-security-16.0.0_r7` 25Q2/QPR0
on the retained Allwinner 5.4.302 BSP lineage**. Its same-lineage kernel/wireless preservation
checkpoint is now **CLOSED / PASS**: r5 physically passes Android boot, HDMI, remote, Wi-Fi,
Wi-Fi ADB and one Wi-Fi OFF→ON reinitialization after restoring the working BSP FMAC contract
from r1-r4's wrong `0x00110000` placement to `0x00120000`. The old 1037→1038 timeout did not
recur, including after the cycle; two exact filtered results were empty.

The exact r7 source-only audit is also complete. Official source identifies
`BP2A.250805.034`, API 36.0, REL and SPL 2025-08-05 at manifest commit
`ebea28d151539ecf0730b1a4ab92ac33edc17ac9`. QPR0 fatally requires kernel 5.4+, while netd's
exact non-GKI 5.4 floor is 5.4.277; physical-pass 5.4.302 satisfies it. The Path-A cgroup/netd
config contract is six bounded additions and r7 retains explicit 5.4 BPF variants, API-31
cgroup overlay behavior, bootstrap APEX/VNDK31, FCM6, linker/SELinux and ARM32 TV product paths.
That audit issued **GO FOR ONE PROTOTYPE A r3 BUILD**; the bounded build and offline audit are
now complete.

Local physical validation proves the ARM32 QPR0 base through Android 16 boot, `zygote32`,
system_server and Mali-G31 composition, but r3 required the user's pre-existing runtime
`persist.graphics.egl=mali` override and mapped IR scanCode 352 to UNKNOWN. Strict successor
`a16-prototype-a-r4` is now fully offline checked with exactly two source-level functional
deltas: read-only `ro.hardware.egl=mali` while preserving `ro.board.platform=apollo`, and a
device-specific scanCode 352→`DPAD_CENTER` layout. Kernel, vendor/product and unrelated hardware
authority are preserved. Gate 2 remains **NOT CLOSED / PENDING r4 PHYSICAL VALIDATION**: neither
r4 fix has a physical result, physical HDMI remains unstable, the legacy vendor audio HAL is
unstable, Wi-Fi association was not tested, full VINTF carries the inherited NFS exception, and
enforcing SELinux remains unproven. Prototype B, mixed ARM64/ARM32 userspace, `zygote64_32` and
ARM64 graphics/mapper integration remain closed.

The possible final architecture still worth investigating remains **Android 16 for TV, mixed
ARM64/ARM32 userspace, `zygote64_32`, the Allwinner 5.4 hardware-facing BSP lineage, plus only
the minimum matched ARM64 graphics client provider and bounded vendor zygote/AVB metadata
changes**. That is a later conditional target, not the Prototype A contract. Keeping Android tag
`android-16.0.0_r4`/25Q4 and backporting a 5.10-class BPF stack into a kernel still reporting 5.4
remains NO-GO; adopting a public H616
5.10+ tree remains a new BSP port.

This is a modern hybrid, not a full port. Framework, `system_server`, SurfaceFlinger, and
eligible apps become AArch64; legacy Allwinner media, audio, HWC/composer, DRM, Wi-Fi,
Bluetooth, TEE and other HAL processes remain ARM32 behind stable Binder/HwBinder
interfaces. The current vendor, vendor_dlkm, TEE, boot and board-specific display/media
implementation remain the hardware authority. The paired ARM64 Mali-G31 client library and
multilib mapper/gralloc implementation found in the public Allwinner `apollo`/`sun50iw9p1`
H618 BSP are the only new proprietary-provider class justified by present evidence.

The still-useful change from the earlier M8B ARM64 no-go is exact provenance evidence: the
public donor's ARM32 `libGLES_mali.so` is byte-for-byte identical to the accepted UBOX10
library, and the same donor directory supplies its paired AArch64 library while the donor
product itself selects `zygote64_32`. This does not prove a boot on H616, but it replaces a
missing-provider structural blocker with a small, testable provider gate.

If the ARM32 base eventually passes, the practical quality target remains a 1080p-rendered TV UI with **4K30-class local media as the
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
subsequently granted and consumed by the physical result below. At that historical r1 point,
Gate 2 remained closed and Prototype B remained untouched; the current r5/r7 decision supersedes
that state without rewriting the r1 result.

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
hierarchy creation. The r1 classification therefore remains **bounded retained-kernel cgroup
integration defect before apexd exec**, not an APEX activation failure and not an
architecture-level no-go. The separately authorized r2 physical test below proves that this
minimum config correction advances the boundary; it also supersedes cgroups as the current
first blocker. No further physical action is authorized and rollback inputs remain unchanged.

## 11. Boot-readiness and kernel-path decision after r2

### Prototype A r2 artifact and physical result

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
incompatibility. Linker/ELF, split SELinux, APEX and LP evidence transfers because the
containing partitions were proven byte-identical.

The user separately authorized and performed one r2 physical test. The PhoenixCard capture
`logs/20260822-a-r2/uart-flash-r2.log` is 44,451 bytes, SHA-256
`832e3bedc7bd50e3d9b562ffee375189825ee3eca1a3e67d8026157e4545dd2e`; all 13 download
parts completed and the writer ended with `CARD OK` and `sprite success`. The boot capture
`logs/20260822-a-r2/boot-r2-devkmsg-on.log` is 67,394 bytes, SHA-256
`bf3196e9db99af4f70b5f7cea5cba166a40a92299e9670ed517357f2eee5c4ac`. The RAM-only
`printk.devkmsg=on` addition was read back in bootargs before `run boot_normal`. It contains
five kernel starts and four complete, identical failure cycles.

The furthest runtime-proven point is now **NetBpfLoad execution after cgroup initialization,
APEX init import and the three service managers, but before zygote32**:

| Area | Status | Evidence and boundary |
|---|---|---|
| Kernel / boot / first-stage init | **PROVEN** | Exact 5.4.125 r2 kernel starts repeatedly; retained boot/vendor_boot maps LP and hands off to A16 system. |
| Mount / split SELinux | **PROVEN TO CURRENT BOUNDARY** | A16 secilc consumes system/vendor/system_ext inputs and second-stage init runs; cmdline is permissive, so enforcing compatibility is not claimed. |
| Required cgroups | **PROVEN FIXED** | The r1 blkio error and `/sys/fs/cgroup/system/uid_0` creation failure disappear. Required blkio/cpuset and the v2 system hierarchy support live service process groups. |
| ueventd | **EXECUTED** | Shutdown identifies live ueventd PID 164; the r1 pre-exec fatal is gone. |
| APEX activation boundary | **ADVANCED / PARTIALLY PROVEN** | `bootstrap-apexd-failed` never appears and init consumes `/apex/com.android.uprobestats/etc/init.rc`, proving mounted APEX init content. This does not prove every APEX service healthy. |
| servicemanager / hwservicemanager / vndservicemanager | **EXECUTED** | Live PIDs 267/268/269 and interface-control traffic are present before the failure. |
| NetBpfLoad | **FIRST REPRODUCIBLE FATAL** | Every complete cycle logs `Android 25Q4 requires kernel 5.10`; init then follows bpfloader `reboot_on_failure` and reboots with `bpfloader-failed`. The check returns before any BPF object load. |
| VINTF | **EXACT CHECKED; INHERITED EXCEPTION** | Full offline check remains exit 65 only for accepted `CONFIG_NFS_FS=y` versus FCM-6 `n`; this is not relabeled PASS. |
| Linker namespaces | **BOOTSTRAP EXECUTION PROVEN; FULL HAL PATH UNPROVEN** | Dynamic system/APEX services execute and offline ARM32 vendor/VNDK-31 closure passes; no later vendor HAL registration has been reached. |
| zygote32 / system_server | **NOT REACHED** | bpfloader is a core boot dependency and selects shutdown first. |
| SurfaceFlinger / HWC / media / audio / Wi-Fi / Bluetooth / input / DRM | **NOT REACHED** | r2 does not establish any of these A16 runtime contracts. Accepted A12 behavior is only rollback/reference evidence. |

### Newly exposed compatibility signals

| Signal | Exact source/config result | Classification |
|---|---|---|
| cgroup2 `memory_recursiveprot` | A16 `MountV2CgroupController()` documents that the option arrived in 5.7 and retries the same cgroup2 mount without it. r2 continues to service execution. | **Non-fatal compatibility fallback**, not the current blocker. |
| Remaining cgroup/task profiles | r2 has all required effective r4 controllers. `CONFIG_MEMCG=n` leaves the optional v2 memory controller unavailable. The `/dev/stune/foreground/tasks` line occurs after bpfloader has selected shutdown; most missing `cgroup.procs` lines are exit cleanup. | **No second pre-bpfloader fatal observed**; later workload behavior remains untested. |
| `CAP_PERFMON` | Retained 5.4 ends at `CAP_AUDIT_READ`; it has neither PERFMON nor BPF capabilities. A16 init rejects the capability in the disabled UprobeStats service stanza. | **Not boot-causal now**, but a real UprobeStats/perf isolation deficit if that feature is enabled. |
| IncFS | Exact config has `CONFIG_INCREMENTAL_FS=n` and vendor has no requested `incrementalfs.ko`. `readIncFsFeatures()` explicitly returns v1/none when the feature directory is absent. | **Non-fatal boot fallback**; incremental APK installation/streaming cannot be claimed. |
| BPF/BTF already present | Exact kernel is AArch64 and has CGROUP_BPF, BPF_SYSCALL, BPF_JIT, BPF_JIT_ALWAYS_ON and its `BPF_BTF_LOAD` path. Program objects carry `.BTF`; `CONFIG_DEBUG_INFO_BTF=n` specifically removes vmlinux BTF/sysfs, not basic object BTF loading. | Enough to justify a 25Q2 loader experiment, not proof that all programs verify/load. |
| BPF/BTF absent | Kernel has no ring-buffer map/helpers, BPF link or batch-map API, CAP_PERFMON/CAP_BPF split, kprobes/uprobes/ftrace, or vmlinux BTF. Android marks ringbuf and BTF-dependent socket storage as 5.10-minimum facilities. | Real functionality gaps; not erased by bypassing a version check. |
| netd rate limiting | Exact config has BPF JIT but lacks `CONFIG_NET_CLS_MATCHALL`, `CONFIG_NET_ACT_POLICE` and `CONFIG_NET_ACT_BPF`, all asserted by the A16 netd test. | Bounded config additions exist in the 5.4 source, but must accompany any Path-A kernel validation. |

### Path A — earlier Android 16 with retained 5.4 lineage

The release boundary is source-defined rather than inferred from the r2 reboot reason:

| Tag | Build/source identity | Release contract | Kernel result |
|---|---|---|---|
| `android-16.0.0_r1` | `BP2A.250605.031.A2`; manifest `2e764235335a27ee8cc8efc16baef4c0f6a5b3fe` | API 36.0, 25Q2/QPR0, SPL 2025-06-05 | NetBpfLoad and netd accept 5.4 base; netd requires 5.4.277. |
| `android-16.0.0_r2` | `BP2A.250605.031.A3`; manifest `6650f1e0458a5450156c0348fe0dc96acb958eb8` | API 36.0, 25Q2/QPR0, SPL 2025-06-05 | Same 5.4 policy. |
| `android-security-16.0.0_r7` | official build table `15180164`; source `BUILD_ID=BP2A.250805.034`; manifest `ebea28d151539ecf0730b1a4ab92ac33edc17ac9` | API 36.0, 25Q2/QPR0, SPL 2025-08-05 | Latest official QPR0 security tag available; relevant NetBpfLoad/netd files retain the 5.4 policy and 5.4.277 floor. **Preferred Path-A source baseline.** |
| `android-16.0.0_r3` | `BP3A.250905.014`; manifest `551f738e53bda3d969e6a0d2022d29ab4c9d47de` | API 36.0, 25Q3/QPR1, SPL 2025-09-05 | Its runtime 25Q4 check does not fire, but netd explicitly says 25Q3 requires 5.10; not a legitimate 5.4 baseline. |
| `android-16.0.0_r4` | `BP4A.251205.006`; manifest `15128c9e27cfa599c48d294babd39286ee8f1426` | API 36.1, 25Q4/QPR2, SPL 2025-12-05 | NetBpfLoad hard-fails below 5.10; netd requires 5.10 and at least 5.10.210. Physically proven incompatible with exact r2. |

The official 25Q2 netd commit `7004c06cc45208ae8860057205fa41e7bb6eb47f`
chooses **5.4.277** as the minimum non-GKI 5.4 LTS and explicitly notes that Google had no
5.4 test coverage and considered it shaky. Exact 5.4.125 is therefore 152 patch releases below
the minimum even though the top-level NetBpfLoad `uname` check would accept it. Kernel.org no
longer lists 5.4 as active and the upstream series ends at 5.4.302. A responsible Path A
therefore required a same-lineage vendor-BSP move to final 5.4.302 while preserving exact-board
drivers, module ABI, DT and boot behavior. The checkpoint below closes source/build preservation;
r5 now physically closes boot/UI/Wi-Fi/reinitialization after correcting the FMAC address
contract. This is materially smaller than a 5.10 port, but it is not a config-only change.

QPR0 remains Android 16/API 36 and therefore preserves the project's primary platform/API
objective and the Android 16 TV framework direction. It gives up QPR1/QPR2 platform and TV
fixes/features, and the preferred tag declares only the 2025-08-05 SPL. Its 2026 tag publication
date must not be relabeled as a later device SPL; future security coverage would require a
separate patch provenance program. No GMS, Play, certification or commercial-service status
follows from choosing it.

**Path A verdict: selected; CORE ARCHITECTURE VIABILITY PHYSICALLY PROVEN / r4 OFFLINE CHECKED.**
The same-lineage kernel/wireless preservation checkpoint is **CLOSED / PASS**, the exact r7 source
audit finds no architecture blocker, and r3 physically reaches Android 16/zygote32/system_server/
Mali-G31 with a pre-existing runtime EGL override. r4 now contains the formal EGL selector and
Remote OK mapping but has no physical result. Gate 2 is **NOT CLOSED / PENDING r4 PHYSICAL
VALIDATION**; HDMI/audio/Wi-Fi-association remain incomplete and Prototype B remains closed.

#### QPR0 r7 source-only closure

The audit preserved the clean r4 checkout and its exact pinned manifest/output, then inspected
immutable r7 tag objects through the existing Repo object store rather than consuming the roughly
50.8 GiB remaining `/work` space with another checkout/output tree. Official r7 identity is
manifest commit/tree `ebea28d151539ecf0730b1a4ab92ac33edc17ac9` /
`e4641ccf8e59e0028248d32e5a7fd212760b7a22`, `BP2A.250805.034`, API 36.0 and SPL
2025-08-05.

Exact findings are:

- 25Q2 NetBpfLoad fatal floor 5.4 and non-GKI 5.4 release/VTS floor 5.4.277; 5.4.302 passes.
  The r4 25Q4 5.10 fatal is absent because r7 self-identifies and validates as Q2/API36.0, not
  because a check was removed locally.
- Minimum kernel additions are only BLK_CGROUP, CPUSETS, PROC_PID_CPUSET, NET_CLS_MATCHALL,
  NET_ACT_POLICE and NET_ACT_BPF. MEMCG remains optional. Explicit 5.4 network BPF objects exist;
  BTF, ringbuf, link/batch, CAP split, tracing and IncFS are not minimum boot/netd requirements.
- cgroup/API31/vendor overlay order adds no controller beyond the r2 fix. QPR0 retains
  bootstrap-before-data APEX, fixed `mount_before_data=false`, the five-member bootstrap set and
  frozen ARM32 VNDK31 including `libaudioroute.so` plus vendor `default→vndk`.
- FCM6 and its 5.4 config are byte-identical to r4. The exact two display HAL declarations remain
  bounded. Full VINTF remains exit 65 solely for inherited `CONFIG_NFS_FS=y` versus required `n`;
  this is non-boot-causal on current evidence but still a release-conformance exception.
- QPR0 platform still duplicates the accepted vendor's `fuseblk /` ownership; the one-line
  platform deferral remains the minimum split-policy delta. No enforcing-mode claim is made.
- TV GSI base is byte-identical; Prototype A ports with `bp4a→bp2a` plus contained TV package
  deltas while retaining ARM32/no secondary ABI/`zygote32`/shipping API31/VNDK31.

The exact source commits, file hashes and future r3 contract are in
`docs/m8/research/android-16-qpr0-r7-source-audit.md`.

#### Prototype A r3 build and exact-board offline closure

The source workspace was transitioned reproducibly to exact
`android-security-16.0.0_r7` at manifest
`ebea28d151539ecf0730b1a4ab92ac33edc17ac9`; the 246,298-byte pinned manifest hashes to
`F52BA4A04957CEC7EEE7C9DCDD1525533156A0B5A1F0ADFC31A8155F48FB087E`. The source audit
passes before and after the build. Relative `OUT_DIR=out-ceiling`, build number
`UBOX10_A16_QPR0_R3` and `m -j8 systemimage` completed all 121,285 actions with exit 0. The
actual output identifies as BP2A/API36/SPL 2025-08-05 and remains ARMv7-A NEON with no secondary
architecture, empty 64-bit ABI list, zygote32, shipping API31 and VNDK31.

The matching `5.4.302+` Image and all 22 modules were clean-built from retained integration
commit `027ef79e...` using the exact Path-A config. Its only preservation-config additions are
BLK_CGROUP/CPUSETS/PROC_PID_CPUSET for process groups and
NET_CLS_MATCHALL/NET_ACT_POLICE/NET_ACT_BPF for QPR0 netd. MODVERSIONS/import CRCs, dependency
graph and hardware config close. The final BSP preserves the r5 FMAC upload/patch-read/START_APP
contract `0x00120000`/`0x00120180`/`0x00120000`; generic MMC/SDIO, 70 MHz, firmware and DT
authority remain unchanged.

The single exact-board firmware is 1,239,738,368 bytes / SHA-256
`FA47939654B4E2A7E14FE963C7819296157338D33355E75D89E8086356071F1B`. The offline audit
closes all four ext4 filesystems, system/boot/vendor_dlkm AVB, vbmeta_system rollback metadata,
LP 10.2 geometry/three slots/sparse round trip/empty B slots, IMAGEWTY, ARM32 ELF/name closure,
all 35 r7 APEXes, VNDK31 `libaudioroute.so`, generated vendor `default→vndk`, split SELinux and
kernel preservation. Full VINTF remains exit 65 / INCOMPATIBLE solely for inherited
`CONFIG_NFS_FS=y` versus FCM-6 `n`; no new incompatibility appears and this is not called PASS.
Only boot/super/vbmeta_system and their three checksum companions change in the outer container;
the other 44 entries, accepted vendor/product and all unrelated hardware authority are exact.

This establishes offline eligibility only. No boot, zygote32, system_server, SurfaceFlinger/HWC,
enforcing SELinux or hardware runtime result follows. The full record and machine-readable
preservation inventory are `docs/m8/candidates/a16-prototype-a-r3.md` and
`docs/m8/candidates/a16-prototype-a-r3-preservation.json`.

#### Prototype A r3 local physical result

The 2026-08-25 Ethernet-ADB session did not flash, reboot, rebuild or mutate an image. Its raw and
reviewable evidence is in
`docs/m8/device-tests/20260825-a16-prototype-a-r3-physical-validation/`.

Direct runtime evidence proves Android 16/API36/BP2A, ARM32-only `zygote32`, Linux 5.4.302+, all
six Path-A config additions, boot completion, active runtime/VNDK APEX mounts, service managers,
system_server/SystemUI, TV/Leanback/IME and Ethernet. The original r3 lacked both
`persist.graphics.egl` and `ro.hardware.egl`; user-provided pre-validation evidence records
SurfaceFlinger failing driver selection through `ro.board.platform=apollo`. With the user's
already-present `persist.graphics.egl=mali` override, current SurfaceFlinger reports Mali-G31 /
GLES 3.2 and valid layer composition. The core architecture boundary is therefore proven, while
formal `ro.hardware.egl=mali` integration remains not implemented or validated.

Hardware evidence prevents an unqualified PASS. The monitor repeatedly shows about one second
of picture followed by about five seconds black. SurfaceFlinger and system_server remain alive;
bounded extcon and display-engine sampling stays connected/unblanked at 3840x2160 YUV444 mode 34
with advancing interrupts, while kernel history also records HDMI disconnect/connect transitions.
The exact black-cycle cause is not proven. The legacy HIDL audio service repeatedly
null-dereferences in `Device::getAudioPortImpl` after observed HDMI status transitions and then
recovers automatically. The attached monitor has no audio output, so audible output is not
tested. Wi-Fi modules/framework/scan and OFF-to-ON reinitialization pass, but association/DHCP/L3
are not tested because credentials could not be entered. Linux IR events pass; Android OK fails
because scanCode 352 is unmapped while Generic.kl maps 353 to DPAD_CENTER.

The evidence-led successor direction was bounded to preserving `ro.board.platform=apollo`, adding
`ro.hardware.egl=mali` and mapping scanCode 352 to DPAD_CENTER. HDMI and HIDL `getAudioPort`
remain separate open investigations; no display/audio or Wi-Fi BSP/HAL change was justified for
r4. Gate 2 remains open until a no-runtime-intervention candidate passes the required physical
gates.

#### Prototype A r4 strict two-delta offline closure

On 2026-08-26 the exact r7 source product added only `ro.hardware.egl=mali` and a
device-specific `sunxi-ir.kl` whose only difference from r7 Generic is scanCode
352→`DPAD_CENTER` / keyCode 23. `ro.board.platform=apollo` remains in accepted vendor; the formal
image contains no `persist.graphics.egl`. The `UBOX10_A16_QPR0_R4` ARM32/no-secondary/zygote32
system build completed 43/43 actions. The single exact-board firmware is 1,239,746,560 bytes /
SHA-256 `E125DD8FFB9F5B4A7B2B9B86DD8377367409AB00D1B29BE1E719CE25768E2111`.

Full ext4/AVB/LP/IMAGEWTY/APEX/VNDK31/linker/split-SELinux/ELF/kernel-preservation audit closes.
Full VINTF remains exit 65 solely for inherited NFS; no new incompatibility appears. Boot,
5.4.302+ Image, 22 modules/vendor_dlkm, vendor/product and all unrelated hardware authority are
r3 exact. Only super/vbmeta_system and their checksum companions change in the outer container;
46/50 payloads are preserved. The system tree adds only the layout and changes three generated
build-property files plus NOTICE; its only functional semantics are the two authorized fixes.

This is **OFFLINE CHECKED / READY TO REQUEST PHYSICAL VALIDATION**, not a physical pass. HDMI,
audio, Wi-Fi and Ethernet are unchanged. Gate 2 is **NOT CLOSED / PENDING r4 PHYSICAL
VALIDATION** and Prototype B remains closed. Exact artifact and preservation evidence is in
`docs/m8/candidates/a16-prototype-a-r4.md` and its preservation JSON.

#### Same-lineage Linux 5.4.302 preservation checkpoint

The retained Orange Pi source is commit `9ab7a758149d3c9b721878a0c18b3f9c5d6c93e6`
(tree `d37d590a1e61c8e099e72170bf36e54091aa4820`, release `5.4.125+`). It is a
seven-commit BSP import with no Git merge-base to upstream Linux. The exact upstream anchors
are v5.4.125 commit `3909e2374335335c9504467caabc906d3f7487e4` and final v5.4.302
commit `9e3157c56ec7917e6a80ea53a8bd752e0037f2cb`. Android-common anchors
`6cb0d5ef8b388d0249d96060e9ef31b466f88c7d` and
`2443acb8671f5eaeac985e70446726278ed014ae` preserve the Android 12 kernel delta while
moving across the same stable range.

A direct rebase would invent ancestry, while rebuilding 4,603 vendor-delta files over vanilla
v5.4.302 would maximize lost-BSP risk. The selected bounded hybrid uses exact vendor content as
the `ours` side of a synthetic three-way merge, Android-common 5.4.125 as the base, and
Android-common 5.4.302 as `theirs`. It exposes the 384 overlapping paths for review while
preserving non-overlapping vendor content. The result has commit/tree
`027ef79e8facb73cb2419b4a08c0bd3f13a2206e` /
`b328c32712d65f8da98e013bc74944d68c05552b`; an independent clean replay reproduced
both identities in 17 seconds.

The machine inventory covers H616/sun50iw9 DT, display/HDMI, Mali-G31, Cedar/VIN, G2D and
vendor heaps, audio, AIC8800/XR819/RTL wireless, Ethernet, USB, IR, thermal/DVFS, suspend,
TEE and block/AVB-facing code. It found 434 source-level exports in hardware-critical vendor
delta. There were 46 textual conflicts: 31 maintained stable/common implementations win, 12
vendor implementations are preserved, and 3 are semantic merges (`drivers/char/Kconfig`,
sun50i cpufreq-nvmem and SUNXI pinctrl). The exact per-path decisions are machine-readable.
Critical DTS, display, Mali, Cedar/VIN, G2D/DI/gralloc/heap, AIC and SUNXI USB subtrees are
byte-identical to the retained tree; the accepted rc-core repeat/keymap changes and exact donor
identities for the out-of-tree wireless modules are pinned and reapplied.

`olddefconfig` from the exact accepted Android 12 Image config produces 32 fully accounted
effective changes: Android-common ABI padding, two stable ARM64 errata mitigations, compiler
probes/internal helpers, `/proc/pid/mem` choice normalization, and disabled/removed Kconfig
symbols. It does not enable a broad new hardware subsystem. A separate, non-candidate Path-A
config proves clean closure of `BLK_CGROUP`, `CPUSETS`, `PROC_PID_CPUSET`,
`NET_CLS_MATCHALL`, `NET_ACT_POLICE` and `NET_ACT_BPF`; none is smuggled into the Android
12 preservation Image.

A clean clang-r416183b1 build produced release `5.4.302+`, a 23,492,616-byte ARM64 Image
with SHA-256 `9B781ABEA51DEF9AE1FEBB9011CFA630AC267C794FBA0E066674F0EAE2509DCC`,
and all 22 accepted module roles rebuilt with consistent 5.4.302 vermagic. Required module
names, dependency/alias/firmware/version/license metadata, exported symbol names and import
CRC resolution close offline. Old 5.4.125 modules are explicitly not reused.

The single Android 12 kernel-only candidate is
`m8-kernel-5.4.302-r1`, 1,031,739,392 bytes, SHA-256
`C93FC8A54391E091E0F95CFE63E4F6DA9AE90D55AA0163D91D42586B48BFEE2B`.
It preserves system/vendor/product, boot ramdisk, LP geometry, accepted board DTBO and 46/50
outer payloads byte-for-byte. Only boot, vendor_dlkm, their AVB data, the containing sparse
super and IMAGEWTY checksum companions change. IMAGEWTY, boot AVB, vendor_dlkm AVB/FEC,
ext4, sparse round-trip and LP audits pass; the fixed vendor_dlkm filesystem has only one 4 KiB
block free, which is recorded as a physical-test risk.

The separately authorized r1 physical test subsequently proved Linux 5.4.302 boot,
`sys.boot_completed=1`, HDMI/UI, remote, Ethernet and ADB. It did not prove full BSP
preservation: Wi-Fi repeatedly reaches `mmc2` SDIO enumeration, matches `aic8800d` U04 and
enters firmware init, then logs `Set SDIO Clock 66 MHz`, times out command 1037 waiting for
confirmation 1038, reports `wifi start fail`, removes the BSP and removes the card.

Pinned-source control flow proves `FEATURE_SDIO_CLOCK=70000000` is copied by
`aicbsp_get_feature()` and programmed in `aicwf_sdio_func_init()` through direct
`host->ios.clock` plus host `set_ios`. Exact sunxi-mmc-v4p1x SDR clocking doubles the logical
request, rounds the module clock to about 133.333 MHz, and writes about 66.666 MHz back to the
logged logical value. This occurs before `aicbsp_8800d_fw_init()` and remains effective through
`rwnx_send_dbg_start_app_req()`'s two-second confirmation wait. The timeout proves missing
`DBG_START_APP_CFM`; it does not by itself prove a clock-integrity cause.

The offline `m8-kernel-5.4.302-r2` diagnostic changes only that feature constant from 70 MHz
to 50 MHz. Clean clang-r416183b1 build succeeds in 548 seconds; the resulting BSP module is
127,752 bytes / SHA-256
`D3BA64E43FCD708B4EB7628576D83A01581023181271E0CF76613DD9BC4528F3` with unchanged
vermagic/dependencies/normalized symbols. To exclude absolute-path/ThinLTO private-ID rebuild
noise, the candidate reuses r1 Image and 21 modules and replaces only `aic8800_bsp.ko`.
The 1,031,739,392-byte outer image has SHA-256
`A2963FD46685829774DBF5EA2E899ED5844BF44329BC8F46788F1D14D09AA036`; AVB, ext4,
LP, sparse round-trip, IMAGEWTY and 48/50 outer preservation checks pass. It is not Wi-Fi PASS.

The authorized physical test reports `Set SDIO Clock 50 MHz` and then repeats
`tkn[476] flags:0012 ... cmd:1037 - reqcfm(1038)`, `wifi start fail` and card removal on every
attempt. Android 12, Ethernet and ADB remain working; fdrv does not remain loaded and `wlan0`
does not appear. This rejects frequency as the root cause and leaves HAL/framework failure
downstream.

The exact retained-vendor→integration diff shows `sdio_irq.c`, `sdio_io.c`, `sdio_ops.c`, MMC
host/card/function headers and all retained `sunxi-mmc*` controller sources unchanged.
Request completion/wait and host claim/release functions also have no changed hunk. The
remaining ranked deltas are: corrected cold-init OCR mask (`076712ff...` / upstream
`39a72dbf...`, weak but the only potentially reachable setup delta); initial max-rate quirk
(`ea7e57d...`, physically rejected by r2); retune fixes (`2d95959...`, `894b678...`, inactive
because this host has no tuning op and the run is not resume); SDIO refcount/error removal
(`761db46...`, `7a09c64...`, after failure); host-cap validation (`95d65bc...`, passed at host
registration); and NONSTD/shutdown/SPI paths, which are inactive. Copying the old MMC subtree
or reverting these as a group would not be a controlled experiment.

The AIC receive chain is SUNXI IRQ → `ksdioirqd` → AIC IRQ handler → block-count CMD52 →
CMD53 read → RX thread → config message → ID match → completion. Token 476 proves 476 earlier
blocking confirmations completed over that machinery before START_APP. Existing logs do not
show the final 1037 TX return, IRQ entry, RX length/header/id, or 1038 dispatcher match, so they
could not then select among final-TX, firmware-IRQ, RX and dispatch boundaries. At that historical
point the smallest proposed experiment was a START_APP-gated diagnostic-only BSP module. r3 and
r4 later executed that diagnostic sequence, and r5 superseded it by correcting the earlier FMAC
placement divergence and physically passing Wi-Fi; no further START_APP diagnostic is current.

### Path B — r4/25Q4 on a kernel still identified as 5.4

r4 has two independent policy expressions: NetBpfLoad returns 7 for any kernel below 5.10
before loading objects, and netd unconditionally asserts 5.10 plus a 5.10.210 LTS floor. The
retained kernel already satisfies the 64-bit, BPF syscall, cgroup-BPF and forced-JIT basics, and
Connectivity still contains some 5.4-compatible CLAT/tethering/netd program variants. Those
variants preserve Mainline-module backward compatibility; they do not override the 25Q4
platform floor.

Legitimate conformance would require more than `CONFIG_BLK_CGROUP`: at minimum the rate-limit
configs above, a 5.10-class verifier/helper/map surface including ringbuf, modern perf/BPF
capability separation, required tracing hooks and their security fixes, plus an auditable BTF
contract. IncFS and memory-recursive protection have explicit fallbacks and are not evidence
that every later facility is mandatory for this boot, while UprobeStats is disabled here; the
point is that real feature gaps exist in addition to the hard policy check. A kernel that still
reports 5.4 fails r4 regardless of backports. Editing the check, spoofing `uname`, or disabling
the reboot would diagnose around policy rather than satisfy it. Moving a comprehensive 5.10
BPF/perf/security subsystem into this vendor 5.4 fork would be a large, high-risk kernel port
with no upstream Android 5.4 validation.

**Path B verdict: NO-GO in bounded Gate 2.** It may be a separate kernel research program,
but it is not a justified Prototype A integration fix.

### Path C — move the H616 BSP to 5.10+

The official Orange Pi `orange-pi-5.10` head is
`e39ff11e2e6fe0df19c54fbd0eb6804eba5b0f18` and reports 5.10.75. It has a mainline-style
`sun50i-h616.dtsi` and Zero2 board file, but zero files at the retained vendor paths audited for
SUNXI fb/display, Mali vendor driver, Cedar/VIN, G2D/gralloc, SUNXI DRM heap, SUNXI USB and the
vendor `arch/arm64/boot/dts/sunxi` layout; the exact 5.4 tree has 1,019 files across those paths.
The newer `orange-pi-6.1-sun50iw9` head
`71144529b0334d1488624c41d0d3ba0cb03dd4c1` is similarly mainline-style, not a preserved
Android BSP provider.

A major/minor kernel change invalidates the accepted vendor module contract. All 22 AArch64
vendor_dlkm modules—including Mali-G31, AIC8800 Wi-Fi/Bluetooth, SUNXI USB/rfkill and alternate
wireless modules—must be rebuilt or replaced. Proprietary HWC/gralloc/Mali, Cedar/media,
Apollo audio, TEE/DRM and board power/thermal userspace also depends on vendor ioctls, heaps,
fences, DT bindings and timing behavior. Exact-board display/HDMI/CEC, GPU, media, audio,
wireless, TEE, suspend and thermal support would each need bring-up and regression acceptance.

**Path C verdict: NO-GO for this architecture-ceiling phase.** It is a new BSP/kernel port,
not one bounded experiment; a 5.10 kernel merely reaching a shell would not preserve the
accepted hardware product.

### Ranked decision

| Rank | Path | Decision | Exact next condition |
|---:|---|---|---|
| 1 | A — QPR0/25Q2 plus retained 5.4 lineage | **SELECTED / CORE VIABILITY PHYSICALLY PROVEN / r4 OFFLINE CHECKED** | r4 formally integrates EGL and Remote OK but still needs physical fix validation; HDMI/audio and Wi-Fi-association remain open. |
| 2 | B — r4/25Q4 plus backports into 5.4 | **NO-GO** | Would require violating the version policy or executing a broad 5.10-class subsystem port. |
| 3 | C — public H616 5.10+ kernel | **NO-GO** | Requires a new exact-board Android BSP and hardware-stack port. |

Gate 2 is **NOT CLOSED / PENDING r4 PHYSICAL VALIDATION**. r3 physical proof depends on a runtime
EGL override; r4 removes that formal image dependency offline but does not yet prove either fix
physically. Unstable HDMI/audio and untested Wi-Fi association remain open. Prototype B and mixed
graphics work remain closed.

## 12. Target A/B/C/D comparison

All scores use 1 (poor) through 5 (strong); for effort/risk, a higher score means lower cost or
lower risk. They are decision aids grounded in the evidence above, not synthetic precision.

| Decision criterion | A: Android 12 ARM32 | B: Android 16 ARM32 | C: Android 16 mixed | D: full modern ARM64/kernel |
|---|---:|---:|---:|---:|
| Daily-use stability now | 5 | 2 | 1 | 1 |
| Accepted-function preservation | 5 | 4 | 3 | 1 |
| Modern app/API compatibility | 2 | 4 | 5 | 5 |
| 64-bit native-app support | 1 | 1 | 5 | 5 |
| Expected useful lifetime | 2 | 3 | 4 | 5 |
| Graphics viability | 5 | 5 | 3 | 1 |
| Media quality preservation | 5 | 4 | 4 | 2 |
| Netflix/commercial-streaming potential | 2 | 2 | 2 | 2 |
| HDMI/audio preservation | 5 | 4 | 4 | 2 |
| Exact hardware support | 5 | 4 | 3 | 1 |
| Donor/provider availability | 2 | 3 | 4 | 1 |
| Kernel risk | 5 | 2 | 2 | 1 |
| Engineering return / low effort | 5 | 3 | 2 | 1 |
| Regression and recovery control | 5 | 4 | 3 | 1 |
| Maintainability/security potential | 2 | 2 | 3 | 4 |
| **Unweighted total / 75** | **56** | **47** | **48** | **32** |

The raw totals expose the actual trade: A wins stability and cost but loses future usefulness;
B gains API 36 but now carries an EOL-kernel and QPR0-security burden; C has the best long-term
application value only after the same ARM32 base is established. The project objective still
makes C the preferred possible end state, but only after the source-audit-approved ARM32 QPR0
Prototype A is built and physically passes. The 5.4.302 wireless checkpoint is now closed;
D remains dominated on engineering economics.

| Family | Viability | Main advantage | Decisive blocker/limit | Engineering risk | Verdict |
|---|---|---|---|---|---|
| Target A — Mature Legacy | **PROVEN now** | Accepted stability and hardware completeness | API 31 age and no 64-bit native apps; security/platform life is short | Low | Keep as rollback/reference, not final investment ceiling |
| Target B — Modern Framework / Legacy Architecture | **OFFLINE CHECKED / RUNTIME OPEN** | Maximum vendor reuse and no new graphics provider | r4 requires 5.10, so only QPR0 applies; ARM32 excludes 64-bit-only native apps and still needs r3 physical runtime proof | High until r3 physically passes | Await separate UART-first validation decision |
| Target C — Modern Hybrid | **CLOSED / MEDIUM-LOW** | API 36 plus AArch64 apps while preserving working 32-bit HALs/kernel | ARM32 QPR0 r3 must first pass; paired ARM64 graphics SP-HAL/mapper must then close and run on exact H616 | High but potentially bounded after A | Possible final target, not current GO |
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
| Android generation | Android 16 for TV / API 36, based on exact `android-security-16.0.0_r7` QPR0; r4/25Q4 is retired for retained 5.4 |
| Userspace | Mixed AArch64 primary + ARM32 secondary |
| Zygote | `zygote64_32` |
| Kernel | Retain the physically accepted Allwinner H616 AArch64 5.4.302 BSP lineage with the r5 FMAC address contract and the six Path-A config additions; no GKI/ACK-support or continuing upstream-support claim |
| Vendor | Preserve accepted vendor/vendor_dlkm and all working ARM32 hardware services; add hash-pinned matched ARM64 graphics files, set `ro.zygote=zygote64_32`, correct the mapper bitness contract, and revalidate vendor/root AVB |
| Graphics | Paired ARM64 Mali-G31 EGL/GLES plus AArch64 mapper/gralloc; retain 32-bit counterparts and 32-bit SUNXI HWC/composer |
| Media | Retain 32-bit Allwinner OMX/Cedar service path; do not rewrite to Codec2 merely for elegance |
| Audio | Retain 32-bit Apollo HAL and accepted HDMI route |
| DRM/Netflix | Preserve current Widevine/TEE state; target only legitimate L3/basic playback; no HD/4K promise |
| Display/media | 1080p rendered UI; retain 4K60 HDMI output; target reliable 4K30 hardware video, with 4K60 decode/HDR as optional evidence-led stretch |
| App ecosystem | AArch64 apps preferred with ARM32 fallback; API 36 framework; no GMS/Play claim from the prototype |
| Intentionally legacy | Kernel, boot/vendor boundary and most hardware-facing services remain 32-bit/BSP-derived |
| Must change | Framework/system/product; same-lineage kernel LTS/config contract; vendor-owned zygote selection and affected AVB metadata; AArch64 graphics SP-HAL/mapper path; product/VINTF/linker/SELinux integration; release-specific TV components |

### Why this target?

1. Android 16/API 36 remains the explicit project objective and has official television
   framework/CDD support. Android 17 now exists, but changing platform generations during this
   retained-BSP failure study would expand scope and raises additional kernel/ION requirements.
   **PROVEN / SCOPE DECISION**.
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
7. The same-lineage 5.4.302 integration is reproducible, and r5 physically boots Android 12 with
   HDMI/UI, remote and functional AIC8800D Wi-Fi. One physical Wi-Fi OFF→ON cycle tears down and
   reinitializes successfully; both old START_APP-error filters are empty. Restoring the working
   `0x00120000` FMAC contract is strong single-variable corroboration. **PROVEN physical
   preservation checkpoint; bounded root-cause confidence**.
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

**Overall confidence: HIGH for ARM32 core architecture viability and r4 offline integration;
MEDIUM for physical candidate closure and the end-state hybrid.** The r1/r2 progression proves
early runtime, r5 closes the same-lineage 5.4.302 wireless checkpoint, and exact r7/r3/r4 outputs
close the bounded offline contracts. r3 with a runtime EGL override proves Android 16/zygote32/
system_server/Mali composition; r4 formally integrates EGL selection and Remote OK but is not yet
physically tested. HDMI/audio failures and untested Wi-Fi association keep Gate 2 open. Prototype B
remains unjustified until a no-runtime-intervention Prototype A candidate passes.

## 15. Go / No-Go decisions and remaining decisive gates

### Required decisions

| Question | Decision | Reason |
|---|---|---|
| Recommended modern Android target | **PATH A CORE VIABILITY PHYSICALLY PROVEN / r4 OFFLINE CHECKED** | r4 formally integrates EGL and Remote OK; physical fix validation plus unchanged HDMI/audio/Wi-Fi-association gates remain |
| Android 16 r4 / 25Q4 | **NO-GO with retained 5.4** | Physical and source evidence agree on the 5.10/5.10.210 requirement |
| Android 16 QPR0 / 25Q2 | **SELECTED / CORE RUNTIME PROVEN WITH EGL OVERRIDE / r4 OFFLINE CHECKED** | Exact r7 requires 5.4.277+; r3 proves the ARM32 base and r4 contains the no-override EGL/Remote corrections awaiting physical validation |
| Mixed ARM64/ARM32 userspace | **CLOSED PENDING NO-OVERRIDE PROTOTYPE A PASS** | Exact paired Mali provider exists, but r4 still needs physical fix and hardware preservation closure |
| Full ARM64 userspace | **NO-GO** | Would convert/replace working proprietary service stack for little user value |
| Kernel 5.4 as final architecture | **CLOSED / PASS AT 5.4.302 r5** | Boot/HDMI/remote/Wi-Fi/ADB and physical wireless reinitialization pass after restoring the working FMAC address contract |
| Kernel 5.10+ migration | **NO-GO IN THIS PHASE** | No complete exact-SoC/board Android provider; regression surface is a new BSP port |
| >1080p media target | **PLAUSIBLE** | Physical 4K60 output and 4K codec declarations exist; sustained physical 4K decode is not proven |
| Netflix above current basic/L3 class | **STRUCTURALLY BLOCKED** | L3, HDCP NONE, no secure decoder/protected path; service certification remains an additional gate |

### Remaining decisive gates (maximum four)

1. **Completed:** build and fully offline-audit exactly one r7/`bp2a` ARM32 Prototype A r3
   with no secondary ABI, `zygote32`, shipping API 31, VNDK31, r5 5.4.302 authority, the six
   Path-A config additions, two display HAL declarations and one-line `fuseblk` deferral.
2. Continue to carry the sole inherited full-VINTF NFS conformance exception; never report exit
   65 as PASS. The actual r3 linker/ELF/APEX/split-SELinux/AVB/LP reruns are complete.
3. **Completed to the current boundary:** local r3 validation proves QPR0 bpfloader progression,
   zygote32, system_server and Mali-G31 composition with a pre-existing runtime EGL override.
4. **Completed offline:** r4 persists EGL selection and maps Android OK with no third functional
   delta; physical validation still must prove both without intervention and separately record
   unchanged HDMI/audio/Wi-Fi/Ethernet boundaries. Prototype B remains closed.

## 16. Direct route to the target

1. **Completed — freeze the accepted baseline and provider contract:** keep `m8b-remote-r1` rollback,
   exact hashes, hardware evidence and donor/provider rights/hash manifest.
2. **Completed — exact ARM32 integration:** pair the completed Prototype A system image with the accepted
   partitions, close VINTF/linker/SELinux/AVB/LP checks and audit one rollback-safe candidate.
3. **Completed — corrected cgroup runtime proof:** the separately authorized r2 test proves the
   cgroup correction, mounted APEX init content and service managers, then reproducibly stops at
   the r4/25Q4 5.10 policy boundary.
4. **Completed — same-lineage kernel/wireless checkpoint:** r5 physically passes Linux
   5.4.302 boot, HDMI/UI/remote/Wi-Fi/ADB and one full Wi-Fi reinitialization after the bounded
   FMAC address-contract correction.
5. **Completed — exact QPR0 source audit:** pin official r7 identity, prove the 5.4.277 floor,
   re-derive minimum cgroup/netd/APEX/VNDK/linker/VINTF/SELinux/TV-product deltas, and issue the
   ARM32 r3 build GO.
6. **Completed — ARM32 QPR0 build/offline proof:** build the exact r7 system and Path-A kernel,
   package one exact-board r3, then close ELF/APEX/VNDK/linker/SELinux/AVB/LP/outer preservation
   while strictly carrying the sole inherited NFS exception.
7. **Completed — local r3 physical boundary:** prove core ARM32 A16 runtime with the pre-existing
   EGL override and record HDMI/audio/input/Wi-Fi-association failures or untested boundaries.
8. **Completed — strict two-delta closure candidate:** r4 persists `ro.hardware.egl=mali` and maps
   IR scanCode 352 while byte-preserving kernel/vendor/product and leaving HDMI/audio/Wi-Fi/
   Ethernet unchanged; full offline audit passes with only the inherited NFS exception.
9. **Current next action — separately authorized r4 physical validation:** fresh boot without
   UART/`setprop`, verify Mali/boot completion and real Remote OK, then classify unchanged
   HDMI/audio/Wi-Fi/Ethernet separately. Mixed `zygote64_32` remains closed.
10. **Final acceptance:** sustained daily-use regression, 4K30-or-1080p evidence-led media
   ceiling, recovery rehearsal and a hash-locked accepted architecture image.

## 17. Sources and provenance

Exact official r7 tag objects were audited locally on 2026-08-24. Web sources were last accessed
on 2026-08-22. Primary/official sources are used for platform, kernel and board claims.

- [Android 16 for TV](https://developer.android.com/tv/release/16)
- [Android 16/QPR1/QPR2 release notes, including television media-quality work](https://source.android.com/docs/whatsnew/android-16-release)
- [AOSP codenames, tags and build numbers](https://source.android.com/docs/setup/reference/build-numbers)
- [`android-security-16.0.0_r7` manifest tag](https://android.googlesource.com/platform/manifest/+/refs/tags/android-security-16.0.0_r7)
- [`android-security-16.0.0_r7` NetBpfLoad](https://android.googlesource.com/platform/packages/modules/Connectivity/+/refs/tags/android-security-16.0.0_r7/bpf/loader/NetBpfLoad.cpp)
- [`android-security-16.0.0_r7` netd kernel tests](https://android.googlesource.com/platform/system/netd/+/refs/tags/android-security-16.0.0_r7/tests/kernel_test.cpp)
- [`android-16.0.0_r4` manifest tag](https://android.googlesource.com/platform/manifest/+/refs/tags/android-16.0.0_r4)
- [`android-16.0.0_r4` NetBpfLoad](https://android.googlesource.com/platform/packages/modules/Connectivity/+/refs/tags/android-16.0.0_r4/bpf/loader/NetBpfLoad.cpp)
- [`android-16.0.0_r4` netd kernel tests](https://android.googlesource.com/platform/system/netd/+/refs/tags/android-16.0.0_r4/tests/kernel_test.cpp)
- [AOSP 25Q2 minimum-LTS decision for non-GKI 5.4](https://android.googlesource.com/platform/system/netd/+/7004c06cc45208ae8860057205fa41e7bb6eb47f)
- [Android common kernels](https://source.android.com/docs/core/architecture/kernel/android-common)
- [Android kernel architecture/GKI](https://source.android.com/docs/core/architecture/kernel)
- [Kernel.org active releases](https://www.kernel.org/releases.html)
- [Kernel.org 5.x release archive](https://www.kernel.org/pub/linux/kernel/v5.x/)
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
- [Orange Pi `orange-pi-5.10` kernel branch](https://github.com/orangepi-xunlong/linux-orangepi/tree/orange-pi-5.10)
- [Orange Pi `orange-pi-6.1-sun50iw9` kernel branch](https://github.com/orangepi-xunlong/linux-orangepi/tree/orange-pi-6.1-sun50iw9)
- [Linux mainline](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/)

Local primary evidence includes the accepted-image hashes and logical partitions, generated
ELF inventory, live read-only ADB capture in `work/architecture-ceiling/device-evidence/`,
the read-only Android 12 UBOX product, current repository candidate/device-test records, the
isolated Android 16 tree and donor metadata cache. The Linux 5.4.302 checkpoint additionally
pins the complete accepted/preservation/Path-A configs, conflict decisions, semantic patches,
integration/build/audit scripts and candidate manifest under `configs/kernel/`,
`configs/candidates/` and `scripts/`; its full inventory, logs, source/build trees and large
artifacts remain ignored or outside Git. No DRM secret material was collected.
