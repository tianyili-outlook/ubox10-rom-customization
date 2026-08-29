# Prototype B B0 pre-build integration preflight

Date: 2026-08-26

Status: **B0 COMPLETE / PROTOTYPE B1 BUILD READINESS GO FOR ONE BOUNDED BUILD**

Execution update, 2026-08-26: that GO was exercised by the same canonical
`a16-prototype-b-r1`. Exact Mali intake, ARM64 mapper/gralloc compilation and cross-bitness handle
layout passed. Actual staging proved the frozen 117,104,640-byte vendor filesystem region was at
least 18,165,760 bytes too small before AVB/FEC. B1 therefore correctly stopped at **OFFLINE HOLD /
PARTITION FIT BLOCKER / NO CANDIDATE** pending an explicit storage-contract decision. This does not
rewrite B0's historical pre-build decision; it records the downstream evidence that B0
intentionally required.

Storage-contract update, 2026-08-27: governance explicitly authorized the same canonical r1 to
enlarge only `vendor_a` from 119,066,624 to 150,994,944 bytes (144 MiB). A fresh exact-r7 `lpdump`
read of frozen r4 `super.raw.img` reproduces the committed metadata byte-for-byte: `sb_a` remains
3,212,836,864 bytes, old allocation is 2,049,544,192 bytes and old unallocated capacity is
1,163,292,672 bytes. The 31,928,320-byte growth leaves 1,131,364,352 bytes unallocated. The group
maximum, `system_a`, `product_a`, `vendor_dlkm_a`, every B-slot allocation and all other partition
sizes/extents remain fixed; no partition may shrink. This closed only the measured storage-fit
blocker and did not broaden B1 semantics or create r2.

Final execution update, 2026-08-27: the same r1 completed its mixed system build, exact 144 MiB
vendor image, system/vendor AVB, super/IMAGEWTY packaging and all required offline audits. The IMG
is 1,641,752,576 bytes / SHA-256
`796A2D46DB7FCDFF27D53397565ABDDC3D18F2E548A697055CE5E47278E69545`; status is **OFFLINE
CHECKED / READY FOR PHYSICAL VALIDATION**, not physical PASS. The actual candidate metadata proves
the authorized storage geometry and all preservation constraints. Full VINTF remains exit 65 for
the inherited NFS exception only. No physical action occurred.

Physical execution update, 2026-08-27: the first exact-r1 diagnostic without a slot suffix stopped
at default-fstab lookup; later slot-correct RAM-only UART evidence proved that result was an
artificial diagnostic-boot blocker. With `androidboot.slot_suffix=_a`, fstab parse, metadata
fsck/mount, logical partition creation and `system_a` mount all pass. The true first causal failure
is the attempt to move `/metadata` after `SwitchRoot("/system")`.

Exact signed r4/r1 root comparison uniquely proves r4 contains `/metadata` as a `0755`, `0:0`,
`u:object_r:metadata_file:s0` directory and r1 omits it; all other observed top-level move targets
match. The byte-identical first-stage init cannot create `/system/metadata` on the read-only system
mount, so `MS_MOVE` returns the observed `ENOENT`. R1 is therefore **PHYSICAL FAIL — SYSTEM
SWITCH-ROOT `/METADATA` TARGET MISSING**, not a default-fstab failure. Strict single-cause
`a16-prototype-b-r2` restores only the accepted r4 root mountpoint contract and is **OFFLINE CHECKED
/ READY FOR PHYSICAL VALIDATION** at that historical offline point. Its later RAM-only diagnostic
physically passes the `/metadata` correction, then fails at the next first-stage boundary because
root `/vendor` is a symlink to `/system/vendor` and cannot be the canonical target for the
independent vendor mount. Exact r4/r2 root, BoardConfig, root-generation, fstab and init evidence
uniquely proves that cause. `a16-prototype-b-r3` restores only the exact accepted r4 root `/vendor`
directory contract and completed its historical offline gate. Its later physical test closes
`/vendor`, reaches ARM64 second stage, then freezes independent zygote64 ABI-property and mapper
failures. Exact r7 priority (`product, odm, vendor, system`) proves retained ARM32 ODM wins because
r3 product has no scoped ABI metadata. Bounded `a16-prototype-b-r4` therefore adds only the canonical
product-scoped mixed triplet; its complete audit is **OFFLINE CHECKED / READY FOR PHYSICAL
VALIDATION**, not physical PASS. Graphics remains unchanged and separately unresolved. See the
r1-r4 candidate records, `a16-prototype-b-r1-first-stage-audit.json`,
`a16-prototype-b-r2-root-layout-audit.json`, and the r3 physical/root-cause machine records.

Runtime-source update, 2026-08-28: exact r4 physically retained the r2/r3 root closures and reached
second stage, but repeated the same zygote64 ABI abort. The decisive live layout was
`/product -> /system/product` with no product/product_a mount; logical product_a existed as dm-1 but
was inactive, so r4's correct triplet never entered the active 1657-byte embedded build.prop. Exact
signed root, retained `/product` skip-list, first-stage source and r7 property loading uniquely prove
that active source is `system_a:/system/product/etc/build.prop`. R4 is therefore an immutable
**PHYSICAL FAIL — PATCHED INACTIVE LOGICAL PRODUCT_A**. Strict single-cause
`a16-prototype-b-r5` source-generates the triplet in that active file and restores inactive product_a
to exact r3 bytes. Physical UART now proves this correction and canonical global mixed ABI PASS;
retained BoringSSL32 also exits 0. The newly activated vendor BoringSSL64 trigger then fails before
exec because its named executable is absent. Exact source/vendor audit authorized strict r6, which
adds only canonical r7 AArch64 `boringssl_self_test_vendor` output. Physical r6 crosses the old reboot
gate, starts both ART/Zygote runtimes and reaches primary preload. Its zygote restart is a downstream
result of repeated ARM64 SurfaceFlinger `gralloc-mapper is missing` crashes, not an independent
zygote failure.

Mapper execution update, 2026-08-28: exact r7 SurfaceFlinger/UI, Gralloc2, HIDL passthrough loader,
manifest, `sphal` namespace and working ARM32 control evidence uniquely proves that the r6 ARM64
mapper and its factory-loaded gralloc each import the same newer libc++ verbose-abort symbol absent
from the selected VNDK31 snapshot. Discovery name/path/export/transport are correct; eager relocation
fails before `HIDL_FETCH_IMapper`, and fixing mapper alone would make gralloc fail on the same symbol.
Strict r7 uses libc++'s documented ARM64 back-deploy hook for only this inseparable pair. Its exact
two-file vendor delta and full offline acceptance pass. Exact-r7 physical validation on 2026-08-29
then proves canonical mixed ABI, dual zygote, ARM64-parented system_server, stable ARM64
SurfaceFlinger, no recurrence of `gralloc-mapper is missing`, real gralloc allocation and Mali-G31
GLES/UI. R7 is now **PHYSICAL ARCHITECTURE PASS / FROZEN ARCHITECTURE BASELINE / PENDING GATE 3
FUNCTIONAL PRESERVATION**. Full VINTF remains inherited NFS exit 65, not PASS.

This record is the integration contract for the first Prototype B build task. B0 was read-only:
no Android or kernel build ran, no source or accepted image was modified, no candidate was created,
and no donor proprietary binary was committed or installed. Exact QPR0 source, the r4 candidate and
logical images, official donor objects, ELF contracts, property ownership, linker/VINTF source and
AVB/outer metadata were inspected only.

## 1. Gate policy and rollback control

The old Gate 2 contract included absolute vendor audio HAL startup stability. Exact r4 instead
proved functional audio viability through direct audible HDMI playback and real Android VLC
playback, with stable audio processes and no new crash during the clean playback interval. The
user has explicitly changed the project policy: the one-shot, auto-recovered boot-time
`getAudioPort` null-address SIGSEGV is **KNOWN / UNFIXED / POST-GATE P1 STABILIZATION DEBT**, not
an architecture blocker. This is a recorded governance decision, not an assertion that the defect
was fixed.

Consequently Gate 2 is **CLOSED / PASS**, and exact r4 is frozen as the Android 16 ARM32
architecture control:

| Identity | Exact value |
|---|---|
| Candidate | `a16-prototype-a-r4` |
| Image | `out/candidates/a16-prototype-a-r4/x12-a16-prototype-a-r4.img` |
| Size / SHA-256 | 1,239,746,560 bytes / `E125DD8FFB9F5B4A7B2B9B86DD8377367409AB00D1B29BE1E719CE25768E2111` |
| Candidate build commit | `db5712b7aed1ec72c071e67b4d93556a15826184` |
| Source | `android-security-16.0.0_r7`; manifest `ebea28d151539ecf0730b1a4ab92ac33edc17ac9`; pinned manifest SHA-256 `F52BA4A04957CEC7EEE7C9DCDD1525533156A0B5A1F0ADFC31A8155F48FB087E` |
| Android identity | `BP2A.250805.034`; API 36; SPL 2025-08-05 |
| Kernel | `5.4.302+`; Image SHA-256 `287A82F799982FB58D02ADE88150A9EAB22D4C0956BE3CE50765F6FD1DB24F40` |
| Kernel contract | six Path-A additions; exact 22 modules; AIC FMAC upload/patch-read/START_APP `0x00120000`/`0x00120180`/`0x00120000` |
| Physical status | **PASS / ACCEPTED ANDROID 16 ARM32 ARCHITECTURE BASELINE / FROZEN CONTROL** |

The rollback hierarchy is now `m8b-remote-r1` for the frozen Android 12 daily-use fallback and
`a16-prototype-a-r4` for the frozen Android 16 ARM32 architecture control. Every B candidate must
remain exactly rollback-compatible with r4.

## 2. ARM64 Mali provider intake

The old ignored donor directory `/home/tianyi/ubox10-ceiling-donors` was not present. B0 therefore
revalidated only the required objects against the official public BPI repository at commit
[`316cd80ca43fa17b0385eacd7f6f3652bbd66b2a`](https://github.com/BPI-SINOVOIP/BPI-H618-Android12/tree/316cd80ca43fa17b0385eacd7f6f3652bbd66b2a).
Temporary inspection copies were outside Git and removed after inspection; no donor executable was
run.

| Provider | Identity |
|---|---|
| Accepted ARM32 | `/vendor/lib/egl/libGLES_mali.so`; 14,487,716 bytes; SHA-256 `fbffe5601a58d1f8d624ee37129f73b76d0a73eb21fc8a2487368d9ab47f14b7`; ELF32/ARM; SONAME `libGLES_mali.so`; Build ID `7c42c3a6258ad3f35abd15c220b044d8` |
| Donor ARM32 | `hardware/aw/gpu/mali-bifrost/mali-g31/arm/lib/libGLES_mali.so`; byte-identical to the accepted file |
| Paired donor ARM64 | `hardware/aw/gpu/mali-bifrost/mali-g31/arm64/lib64/libGLES_mali.so`; 18,145,112 bytes; SHA-256 `03333d495e3566c7d85ca2e000da569a16ce8f022ea25c0ea61950c891d5c7f8`; ELF64/AArch64; SONAME `libGLES_mali.so`; Build ID `281008657ed1f606be382d076fe69918` |
| Intended B1 install path | `/vendor/lib64/egl/libGLES_mali.so` |

Both files declare the same DT_NEEDED set: `libcutils.so`,
`android.hardware.graphics.common@1.0.so`, `libnativewindow.so`, `liblog.so`, `libm.so`, `libc.so`,
`libdl.so`, `libz.so` and `libc++.so`. Exact r7 VNDK31 arm64 VNDK-SP/LLNDK files exist for all
nine. Their exported dynamic symbols cover all 297 unique strong undefined imports from the ARM64
Mali object; unmatched count is zero. This is **STATIC DEPENDENCY/SYMBOL CLOSURE PASS**. Runtime
namespace visibility is separately bounded by the `sphal` checks below.

Technical provenance is **HIGH** for the paired provider lineage: the public commit, exact path and
hash are pinned, its ARM32 mate is byte-identical to the accepted H616 file, and both identify the
same `apollo`/`sun50iw9p1`/Mali-G31 family. Exact H616 runtime compatibility remains **MEDIUM / NOT
PROVEN** because the public board is adjacent H618, not exact UBOX10 H616.

Redistribution permission for the proprietary Mali binaries is **UNPROVEN**. Public availability
does not establish a redistribution license. The B1 build must use this fail-closed local intake
contract:

1. a user or artifact custodian separately entitled to use the file places it at
   `/work/local-proprietary/ubox10/prototype-b-b1/libGLES_mali.so` outside Git;
2. the build task must require a regular 18,145,112-byte file with the exact SHA-256, ELF64/AArch64
   class/machine, SONAME and Build ID above and stop on any mismatch;
3. build tooling must not download the blob, infer rights, add it to Git, logs or an evidence
   archive, or replace the accepted ARM32 copy;
4. only the hash/path/provenance check and resulting local candidate inventory may be tracked.

This defines a deterministic local experiment mechanism; it does not grant or assert rights.

## 3. Mapper/gralloc architecture and buffer ABI

Accepted r4 contains no `/vendor/lib64`. Its relevant ARM32 controls are:

| File | SHA-256 | Build identity / role |
|---|---|---|
| `/vendor/lib/hw/android.hardware.graphics.mapper@2.0-impl-2.1.so` | `5d18bb597f91c90cc9a17bdad4cd3f525b33b903c7aa188a04d79b1273768be3` | ELF32/ARM; SONAME matches filename; Build ID `135f7c0cce47acd54988463641f4fbb4`; AOSP passthrough adapter |
| `/vendor/lib/hw/gralloc.apollo.so` | `7325bd8b0562f4a01cdf283daaa8db660aaff4e31f6fc7ad5d6dfabc4abf8aac` | ELF32/ARM; SONAME matches filename; Build ID `6bf946999407a78d3784f3c03c17aa42`; reports Arm gralloc 1.0 |

B0 corrects an ambiguity in the earlier readiness summary. The accepted mapper is not the donor's
standalone 2.x mapper backend. Its imports/symbols match exact r7
`hardware/interfaces/graphics/mapper/2.1/default`: `HIDL_FETCH_IMapper` uses
`GrallocLoader`, which calls `hw_get_module(GRALLOC_HARDWARE_MODULE_ID)` and loads
`gralloc.<ro.board.platform>.so` in the consumer process. Therefore an AArch64 SurfaceFlinger needs
both the AOSP r7 ARM64 mapper adapter and ARM64 `gralloc.apollo.so`.

The public donor gralloc source is pinned by tree
`8a231b4f821fc0e30fd9010fb6b51ab01325d616`. Its `Notice` is Apache-2.0 (blob
`5c76690dd02c00638352e9a451adeef7610c0580`, content SHA-256
`c690e3838821dd96f91ca7698431a9f443305b1e27fc7b302f93d25d52fd32ac`); top `Android.mk`,
`gralloc.version.mk` and `src/Android.mk` content SHA-256 values are respectively
`12759d38f0a753d42fc59fee4c2d8fb1d386b82eea05e87fdb4f0338e448cc29`,
`723507c7f2cedc3a49ab02aef7f93383c9fa325ed0ba64dd2af799029eed2a5e` and
`5135dfa585bb4dd5beea9720c4c286661a45c29a306884ba31528ff8bd43b832`. On SDK >24 its
default `GRALLOC_API_VERSION` is `1.x`; `src/Android.mk` names
`gralloc.$(TARGET_BOARD_PLATFORM)`, sets `LOCAL_MULTILIB := both`, and sends ARM/ARM64 outputs to
`vendor/lib/hw` and `vendor/lib64/hw`. B1 must use this gralloc-1.x path for
`gralloc.apollo.so`; it must use the exact r7 AOSP mapper adapter rather than switching to the
donor's alternative 2.x mapper implementation. The candidate assembler must install only the new
ARM64 products and retain both accepted ARM32 files byte-for-byte.

The donor `private_handle_t` transports two FDs followed by a fixed native-handle integer payload.
Its cross-bitness-sensitive values are fixed-width `uint64_t`, and pointer/`off_t` members sit in
unions padded to 64 bits; plane members are fixed-width. The accepted gralloc exports the matching
gralloc-1 function family and the accepted AOSP mapper wraps gralloc0/1. This provides **HIGH
CONFIDENCE / NO KNOWN ABI CONTRADICTION**, but a closed binary does not prove source identity or
exact layout. B1 must emit an ARM/ARM64 compiler layout report (`sizeof`, offsets, `numFds`,
`numInts`, magic), prove the two generated layouts transport the same handle payload, and then
physically validate cross-process allocation/import with the retained ARM32 allocator/HWC/media
services. That exact-board runtime uncertainty is the purpose of B1, not a B0 structural blocker.

The exact boot-critical AArch64 same-process provider set is therefore:

1. `/vendor/lib64/egl/libGLES_mali.so` — hash-pinned proprietary provider;
2. `/vendor/lib64/hw/android.hardware.graphics.mapper@2.0-impl-2.1.so` — exact r7 AOSP adapter;
3. `/vendor/lib64/hw/gralloc.apollo.so` — pinned Apache-2.0 donor gralloc-1.x source output.

No fourth mandatory proprietary provider class was found for first UI boot. The graphics allocator
and SUNXI composer/HWC are binderized process services and remain ARM32. Apollo audio, OMX/Cedar,
Wi-Fi, Bluetooth, DRM, TEE and other mature vendor HALs also remain ARM32 process-isolated.
`vulkan.apollo.so` is **POST-BOOT / NOT A B1 FIRST-UI GATE** while RenderEngine remains on the
physically proven GLES path.

The accepted gralloc DT_NEEDED set is `libhardware`, `liblog`, `libcutils`, `libion`, `libsync`,
`libutils`, `libGLESv1_CM`, `libnativewindow`, `libc++`, `libc`, `libm` and `libdl`; the accepted
mapper adds only exact AOSP graphics-mapper interfaces and ordinary base/hardware/HIDL libraries.
Exact r7 contains ARM64 providers/build modules for these dependencies. That is source-level
dependency closure; the generated ARM64 binaries and their exact DT_NEEDED closure remain mandatory
B1 offline outputs.

| Class | B1 treatment | Components |
|---|---|---|
| A — must have ARM64 same-process provider | **BOOT-CRITICAL** | Mali EGL/GLES, AOSP mapper 2.1 adapter, `gralloc.apollo` |
| B — remain ARM32 process-isolated | **PRESERVE** | SUNXI composer/HWC, graphics allocator service, OMX/Cedar, Apollo audio, Wi-Fi, Bluetooth, DRM, TEE, power/thermal/lights/USB and other binderized vendor HALs |
| C — not required for first boot | **POST-BOOT** | ARM64 Vulkan provider and Vulkan-app capability; GMS/Netflix/HDR/4K60 are also outside B1 |
| D — unknown mandatory provider | **NONE FOUND** | Recursive source/vendor loader review found no additional boot-critical proprietary class |

## 4. Mixed ABI and zygote contract

Exact r7 `ubox10_ceiling_arm64.mk` inherits `core_64_bit.mk` and targets
`device/generic/arm64/BoardConfig.mk`:

- `TARGET_ARCH=arm64`, `TARGET_ARCH_VARIANT=armv8-a`, ABI `arm64-v8a`;
- `TARGET_2ND_ARCH=arm`, `armv7-a-neon`, ABIs `armeabi-v7a,armeabi`;
- ABI lists must become `arm64-v8a,armeabi-v7a,armeabi`, `arm64-v8a`, and
  `armeabi-v7a,armeabi` for all/64/32 respectively;
- `init.zygote64_32.rc` imports `init.zygote64.rc`, starts primary `app_process64
  --start-system-server`, and starts `app_process32` as `zygote_secondary`;
- `system_server` is therefore AArch64; the primary-arch SurfaceFlinger is AArch64; 32-bit apps and
  intended ELF32 vendor services remain supported;
- frozen VNDK31 must be present in both arm64 and arm variants. Binder/HwBinder wire contracts are
  cross-bitness; retained 64-bit Binder plus compat already serves the proven ARM32 system.

At B0 time, `AndroidProducts.mk` still said `bp4a`; the same-r1 implementation has now made the
required single choice `ubox10_ceiling_arm64-bp2a-userdebug`. It also carries the r4 system composition
(`ro.hardware.egl=mali`, `sunxi-ir.kl`, exact display matrix and bounded SELinux composition) into
the ARM64 product. It must not select `zygote64` without the secondary zygote.

## 5. Vendor property ownership

Exact r7 init loads system properties before vendor, and later product-specific partitions have
higher precedence. Accepted `/vendor/build.prop` therefore overrides a system-only mixed product.
The minimum vendor-owned before/after contract is:

| Property | r4 | Required B1 |
|---|---|---|
| `ro.zygote` | `zygote32` | `zygote64_32` |
| `ro.vendor.product.cpu.abilist` | `armeabi-v7a,armeabi` | `arm64-v8a,armeabi-v7a,armeabi` |
| `ro.vendor.product.cpu.abilist64` | empty | `arm64-v8a` |
| `ro.vendor.product.cpu.abilist32` | `armeabi-v7a,armeabi` | unchanged |
| `ro.bionic.arch` | `arm` | `arm64` |
| `ro.bionic.cpu_variant` | `cortex-a7` | `generic` (exact generic-arm64 BoardConfig) |
| `ro.bionic.2nd_arch` | empty | `arm` |
| `ro.bionic.2nd_cpu_variant` | empty | `cortex-a15` (exact second-arch BoardConfig) |
| `dalvik.vm.isa.arm.variant` | `cortex-a7` | `cortex-a15` |
| `dalvik.vm.isa.arm64.variant` | absent | `generic` |

`ro.board.platform=apollo`, `ro.vndk.version=31`, all Wi-Fi/audio/display/hardware properties and
unrelated vendor identity remain unchanged. B1 must generate this fragment from the exact product
configuration and compare it to the table; it must not perform a broad build.prop replacement.

## 6. VINTF and linker contract

Accepted vendor already declares graphics mapper 2.1 as passthrough with
`arch="32+64"`; the allocator 2.0 and composer 2.2 remain hwbinder services. B1 therefore needs no
HAL interface or manifest semantic change: installing the actual lib64 mapper/gralloc providers
fulfills the existing claim. Preserve the manifest byte-exact unless the B1 offline VINTF tool
proves a generated representation change is mandatory.

Exact r7 `system/linkerconfig/contents/namespace/sphal.cc` makes `sphal` visible and searches
`/vendor/${LIB}`, `/vendor/${LIB}/egl` and `/vendor/${LIB}/hw`, with LLNDK and VNDK-SP links. Thus
the three lib64 paths are structurally visible to AArch64 consumers. B1 must generate linkerconfig
against the mixed root and prove the ARM64 Mali nine-library closure in the actual `sphal`
namespace; no static vendor linker file is currently justified.

No new VINTF HAL is introduced by bitness. Full VINTF must still be reported as exit 65 solely for
the inherited `CONFIG_NFS_FS=y` versus FCM-6 `n` exception unless new evidence changes it. B1 must
not alter the kernel or relabel that result PASS.

## 7. Exact partition and AVB impact

R4 outer inspection found 50 payloads. Current top-level `vbmeta.fex` is 4,096 bytes / SHA-256
`888229653ff0fd701c97ca7c0bbafc0042af7c63d7f671bf5f7162349d283f17`, algorithm NONE,
flags 2, and contains no chain descriptor. Current `vbmeta_vendor.fex` is 4,096 bytes / SHA-256
`0c69ef850d33e7deecffae128787f9d96812323a8dc9619d52c61c20b3110057`, signed
SHA256_RSA2048 and owns the `vendor` hashtree descriptor. System likewise has its own hashtree and
signed `vbmeta_system.fex`.

| Image/payload | B1 impact | Reason |
|---|---|---|
| `system_a` | **CHANGE REQUIRED** | ARM64 primary + ARM32 secondary userspace, both zygotes, and r4 product composition |
| `vendor_a` | **CHANGE REQUIRED** | exact property fragment plus the three lib64 graphics providers; regenerate vendor hashtree/FEC |
| `super.fex` | **CHANGE REQUIRED** | embeds changed `system_a` and 144 MiB `vendor_a`; `sb_a` maximum and every other partition extent remain fixed |
| `vbmeta_system.fex` | **CHANGE REQUIRED** | new system hashtree descriptor/signature |
| `vbmeta_vendor.fex` | **CHANGE REQUIRED** | new vendor hashtree descriptor/signature |
| `Vsuper.fex`, `Vvbmeta_system.fex`, `Vvbmeta_vendor.fex` | **CHANGE REQUIRED** | Allwinner checksum companions of changed payloads |
| `product_a` | **EXPECTED BYTE-IDENTICAL** | accepted image owns no zygote/ABI-list property and B1 adds no product feature |
| `vendor_dlkm_a` | **EXPECTED BYTE-IDENTICAL** | exact 22-module contract; no kernel/module change |
| `boot.fex` / kernel / ramdisk | **EXPECTED BYTE-IDENTICAL** | retained 5.4.302 Path-A boot contract |
| `vendor_boot.fex` | **EXPECTED BYTE-IDENTICAL** | no first-stage/vendor ramdisk delta |
| top-level `vbmeta.fex` / `Vvbmeta.fex` | **EXPECTED BYTE-IDENTICAL** | no chain descriptors bind changed subordinate vbmeta payloads |
| DT `sunxi.fex`, `dtbo.fex`, `Vdtbo.fex` | **EXPECTED BYTE-IDENTICAL** | no board/display/kernel delta |
| TEE/DRM, bootloader, factory/security, recovery, metadata/media-data and their companions | **EXPECTED BYTE-IDENTICAL** | outside the mixed-userspace semantic delta |
| B-slot logical images | **EXPECTED BYTE-IDENTICAL / EMPTY** | preserve exact r4 LP slot contract |

There is no unresolved `UNKNOWN` partition class. If a future build changes an expected-exact item,
the assembler must stop and require a new evidence-based decision rather than expanding B1.

## 8. B1 semantic and preservation manifest

Allowed candidate delta is exactly:

1. frozen r4 system composition rebuilt as ARM64 primary + ARM32 secondary under exact QPR0 r7;
2. `zygote64_32`, primary `app_process64`, secondary `app_process32`;
3. the three AArch64 same-process graphics files listed above while retaining their ARM32 peers;
4. only the vendor property, generated linkerconfig, existing-manifest fulfillment, system/vendor
   hashtree, vbmeta, super and checksum consequences enumerated above.

Forbidden delta includes Android 25Q4, a 5.10 port, kernel/config/module changes, Vulkan enablement,
GMS, feature/product work, a full vendor 64-bit conversion, donor HWC/media/audio/Wi-Fi/BT/TEE
binaries, SELinux cleanup, the NFS VINTF change, audio repair, HDMI/display changes or any r4
polish.

The B1 preservation hash gate covers Linux 5.4.302 and six Path-A configs; exact 22 modules;
AIC8800 BSP/modules/firmware/FMAC contract; Wi-Fi HAL/config; Ethernet; Apollo Audio HAL, policy
and ALSA topology; ARM32 SUNXI HWC/composer and allocator service; Allwinner OMX/Cedar; TEE;
Widevine/ClearKey; remote/`sunxi-ir`; HDMI/display; DT/DTBO; vendor_boot; bootloader;
factory/security/recovery; all unrelated product/vendor content; and exact r4 rollback artifacts.
No process-isolated mature vendor HAL is converted to ARM64.

## 9. Required B1 offline acceptance

Before a B1 image may be flashed, its build task must record PASS for:

- fail-closed Mali local-intake size/hash/ELF/SONAME/Build-ID check and no blob in Git;
- complete ARM64 and ARM32 ELF census, expected primary/secondary ABI lists, both app_process files,
  and zero unexpected loss of an ARM32 service/provider;
- exact three-file ARM64 provider inventory; Mali DT_NEEDED plus 297-import closure; r7 mapper
  adapter `hw_get_module` path; gralloc-1.x ARM/ARM64 handle-layout report;
- generated mixed linkerconfig with ARM64 `sphal` visibility and VNDK31 both-arch closure;
- VINTF/manifest result with the inherited NFS exception still isolated and no new mismatch;
- intended vendor services remain ELF32 and have no accidental AArch64 dependency;
- ext4 `e2fsck`, system/vendor AVB/hashtree verify, LP geometry/extents, empty B slots,
  sparse/raw super round trip and outer IMAGEWTY verification;
- exact r4 preservation hashes for every expected-byte-identical logical and outer payload;
- a detached final audit proving only the allowed semantic/partition delta.

## 10. First B1 physical architecture gate

The first physical gate is deliberately narrower than product acceptance:

- no UART intervention, no reboot loop, Android 16 and `sys.boot_completed=1`;
- primary zygote64 and secondary zygote32 both live; system_server and SurfaceFlinger verified
  ELF64/AArch64; representative platform/app processes ARM64; intended vendor services ELF32;
- SurfaceFlinger loads ARM64 Mali, ARM64 mapper and ARM64 `gralloc.apollo`; Mali-G31 renderer and
  stable physical HDMI UI;
- physical Remote, Wi-Fi association/L3, Ethernet basic operation, real HDMI audio, VLC video/audio,
  HDMI and intended HWC/media/vendor services retain r4 functionality.

The known r4 one-shot auto-recovered boot `getAudioPort` crash is baseline P1 debt. Identical
one-shot behavior followed by full playback does not alone fail B1 architecture. A restart loop,
repeated runtime crash, unavailable service, no audio or playback failure is a material regression
and fails B1. Vulkan, Netflix, HDR, 4K60 decode and GMS are not B1 requirements.

## 11. Readiness decision

**PROTOTYPE B1 BUILD READINESS: GO FOR ONE BOUNDED, SEPARATELY EXECUTED CANDIDATE BUILD.**

Gate 2 is closed, r4 is frozen, the proprietary provider identity and fail-closed local intake are
locked, static Mali dependency closure passes, the AOSP-mapper/donor-gralloc split is understood,
the cross-bitness handle path has no known contradiction, mixed ABI and vendor property ownership
are exact, the existing VINTF/linker contract admits the providers, every changed partition and AVB
consequence is enumerated, and no mandatory same-process ARM64 provider class remains unknown.
Exact-board runtime compatibility was not claimed by B0. Subsequent r1-r6 physical evidence and r7
offline closure are execution updates, not retroactive changes to this preflight decision. The next
bounded test is exact r7 physical mapper instantiation; B0 itself did not build or create B1.
