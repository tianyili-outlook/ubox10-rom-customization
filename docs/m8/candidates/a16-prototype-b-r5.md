# Android 16 Prototype B r5

离线状态：**OFFLINE CHECKED**。物理状态：**PHYSICAL FAIL — ACTIVE PRODUCT/GLOBAL ABI
CORRECTION PASS / RETAINED VENDOR BORINGSSL64 EXECUTABLE MISSING FIRST FATAL**。

本版已物理关闭 r4 暴露的 inactive-property-source assembly 错误：exact r7 init 生成 canonical
global mixed ABI triplet，旧 empty `ro.product.cpu.abilist64` blocker 不再是首错。随后 retained
vendor BoringSSL32 self-test 以 status 0 通过；新首个 fatal 是 ARM64 ABI 激活的 vendor
`boringssl_self_test64_vendor` 找不到 `/vendor/bin/boringssl_self_test64`，继而请求
`reboot,boringssl-self-check-failed`。该 executable 尚未执行，所以这不是 algorithm/linker/SELinux
failure 的证据。Zygote、system_server 与 graphics 在本次 r5 启动中尚未到达；独立历史
`gralloc-mapper is missing` 也没有被本次结果重判。

## Candidate identity

| 项目 | 值 |
|---|---|
| ID | `a16-prototype-b-r5` |
| IMG | `out/candidates/a16-prototype-b-r5/x12-a16-prototype-b-r5.img` |
| 大小 | 1,641,760,768 bytes |
| SHA-256 | `418CDC6BBFC44E4BDD346D3AE2861BC44522F321288A570E9CA1729439F6FE2E` |
| Android source | `android-security-16.0.0_r7` |
| manifest | `ebea28d151539ecf0730b1a4ab92ac33edc17ac9` |
| build/API/SPL | `BP2A.250805.034` / 36 / 2025-08-05 |
| lunch | `ubox10_ceiling_arm64-bp2a-userdebug` |
| kernel | byte-preserved `5.4.302+`; no kernel/module build |
| physical evidence | user-supplied exact UART/root-console facts; raw capture not present on this VM |

## Physical result

R5 继续跨过 kernel、first stage、`/metadata`、canonical `/vendor`、SwitchRoot 和 second stage。
Exact init output physically proves:

```text
ro.product.cpu.abilist=arm64-v8a,armeabi-v7a,armeabi
ro.product.cpu.abilist32=armeabi-v7a,armeabi
ro.product.cpu.abilist64=arm64-v8a
```

Thus the r5 active `system_a:/system/product/etc/build.prop` correction and global derivation are
**PHYSICAL PASS**; the old app_process64 empty-ABI64 abort is closed as the current blocker.
Retained `/vendor/bin/boringssl_self_test32` starts from
`ro.product.cpu.abilist32=* && early-init` and exits 0: **PHYSICAL PASS**. Immediately afterward the
newly true 64-bit trigger executes `boringssl_self_test64_vendor`, but init reports:

```text
Could not start exec service:
Cannot find '/vendor/bin/boringssl_self_test64':
No such file or directory
```

The subsequent reboot reason is `reboot,boringssl-self-check-failed`. R5 is therefore frozen as an
immutable physical failure at the missing vendor executable boundary. Exact details are in
`a16-prototype-b-r5-physical-result.json`; no local raw-capture hash is claimed.

## Immutable r4 physical result

Exact r4 retains the r2 `/metadata` and r3 canonical `/vendor` physical closures and reaches ARM64
second stage, but repeats the r3 zygote64 abort. Live global ABI remains ARM32-only and
`ro.product.cpu.abilist64` empty. The decisive root probe is:

```text
/product -> /system/product
/proc/mounts: no /product or product_a mount
/product/etc/build.prop == /system/product/etc/build.prop (1657 bytes)
ro.product.product.cpu.abilist* absent in that active file
/dev/block/mapper/product_a -> /dev/block/dm-1, but not mounted at /product
```

Thus r4 is frozen as **PHYSICAL FAIL — PATCHED INACTIVE LOGICAL PRODUCT_A; RUNTIME PRODUCT SOURCE
REMAINS EMBEDDED `/SYSTEM/PRODUCT`; ZYGOTE64 ABI FAILURE UNCHANGED**. The raw UART capture is not on
this VM; the tracked physical JSON records the externally supplied authoritative facts without
inventing a raw log or hash.

## Exact root cause and generation provenance

The cause is uniquely proven, not inferred:

1. Signed Prototype A r4 and B r3/r4 roots all have `/product -> /system/product` with the same
   symlink metadata. B r4 embedded `system/product/etc/build.prop` is byte-identical to r3 and lacks
   the triplet.
2. Retained `vendor_boot:first_stage_ramdisk/fstab.sun50iw9p1` contains a logical `/product` entry,
   but the byte-identical signed GSI `skip_mount.cfg` contains `/product`. Exact retained Android 12
   `SkipMountingPartitions()` removes the entry before `MountPartition()`. Physical `/proc/mounts`
   independently confirms no product mount.
3. Exact r7 `PropertyLoadBootDefaults()` reads `/product/etc/build.prop`; the proven symlink makes
   `system_a:/system/product/etc/build.prop` the active file. It then derives global ABI in fixed
   priority `product → odm → vendor → system`.
4. Actual final dumpvars reports `TARGET_COPY_OUT_PRODUCT=system/product`, canonical
   `TARGET_CPU_ABI_LIST{,_32_BIT,_64_BIT}`, and both ABIs. Soong's `product-build.prop` module places
   `PRODUCT_PRODUCT_PROPERTIES` at the same embedded path.

R4's offline audit checked the correct values inside logical `product_a`, AVB and LP packaging, but
missed the invariant **patched file must equal runtime-resolved property source**. R5 adds that
fail-closed invariant and directly compares the active triplet with actual final build variables.

## Single-cause r5 delta

R5 changes exactly one runtime-active system tree file relative to byte-identical r3/r4 `system_a`:

```text
system/product/etc/build.prop
+ ro.product.product.cpu.abilist=arm64-v8a,armeabi-v7a,armeabi
+ ro.product.product.cpu.abilist32=armeabi-v7a,armeabi
+ ro.product.product.cpu.abilist64=arm64-v8a
```

There is no runtime `setprop`, init workaround, ODM/vendor mask, property-service change, zygote
change or standalone product mount. Logical `product_a` is restored to exact r3 bytes so the dead
r4 triplet cannot accidentally satisfy the new audit.

| Artifact | Size | SHA-256 / treatment |
|---|---:|---|
| signed `system_a` | 1,651,167,232 | `93D968693A2EEDA2BA53D4EE74BBA8EB73E341EA9BC63EFCD5878609C7DE80BE` |
| inactive `product_a` | 272,629,760 | exact r3 `6E2D0AF3E80DCCC488D73E1A7F483C96075E9F60588DDB7DCBBC42C64FCD8974` |
| `vendor_a` | 150,994,944 | byte-preserved `0166B5FB1718715E79F68D5A9FEAAE02439DC59DBE2379D4C1DA670541C7EC9B` |
| raw super | 3,221,225,472 | `8B3CB4A62C5E398CEB41A7D74F6D8536A25AED6B8DD5F213B18FA0694863C616` |
| sparse `super.fex` | 1,461,963,904 | `BAA52F8103A1322F0C93841E3B10E2EBFAD2019CC27C4B4ED65FA5D5065EF894` |
| `vbmeta_system.fex` | 1,472 | `40732C64F88194DB3CFC35E7F7CFA1DD13CF48B274D8B997152D71E2DA6FC9AA` |
| `vbmeta_vendor.fex` | 1,600 | byte-preserved `DE14183FAFBBEA3EC0D2B0E8737FF9F71BA001186A0DE0D58E24891706ACE6C5` |

## Offline acceptance

- Active-source guard PASS: `/product` symlink, skip list, embedded path, generated path, actual
  final build variables and exact-r7 global derivation all agree. Inactive `product_a` has no ABI
  triplet.
- Signed system tree delta is only `system/product/etc/build.prop`; r2 `/metadata`, r3 `/vendor` and
  `/product -> /system/product` contracts are preserved.
- `e2fsck -fn`, system/vendor AVB, subordinate vbmeta, rollback locations, LP metadata slots,
  unchanged geometry, sparse/raw super roundtrip and IMAGEWTY verification PASS.
- Outer delta relative r4 is exactly `super.fex`, `Vsuper.fex`, `vbmeta_system.fex`,
  `Vvbmeta_system.fex`; 46/50 payloads are byte-preserved. Top-level vbmeta, vendor vbmeta,
  boot/vendor_boot/fstab, DT/DTBO, TEE/DRM, bootloader, factory/security/recovery remain exact.
- Mixed ELF census PASS: 2,517 total ELF, 1,471 system AArch64, 701 system ARM;
  `app_process64` and `app_process32` present; `zygote64_32` offline contract present.
- 35/35 APEX activation, VNDK31 ARM64+ARM32 `libaudioroute`, linkerconfig mixed `${LIB}`, ARM64 SP-HAL
  visibility and Mali 297 strong imports / zero unmatched PASS.
- Exact ARM64 Mali/mapper/gralloc hashes are preserved. No graphics change was made.
- Split SELinux compilation and system VINTF PASS. Enforcing runtime is not claimed.
- Full VINTF is **exit 65 / inherited `CONFIG_NFS_FS=y` vs FCM-6 `n` only / NOT PASS**.
- Kernel `5.4.302+`, six Path-A configs, 22 modules and AIC FMAC `0x00120000` contract are preserved.
- Focused r5 contract tests are 6/6 PASS; the full lightweight repository suite is 154/154 OK with
  34 declared missing-fixture skips. Python compilation and 65 tracked JSON parses PASS.

Full generated audit lives under ignored candidate output; durable summaries are
`a16-prototype-b-r5-offline-result.json` and `a16-prototype-b-r5-preservation.json`. Build logs are
under `/work/build-logs/a16-prototype-b-r5-20260828T125538Z/`.

## Known independent residuals

- ARM64 graphics remains **PHYSICAL FAIL / PARTIALLY PROVEN / NOT UNIQUE** at
  `gralloc-mapper is missing`; r5 does not repair it.
- The frozen ARM32 control's one-shot auto-recovered `getAudioPort` crash remains unfixed post-Gate
  P1 debt.
- Full VINTF NFS exception and SELinux enforcing proof remain later hardening items.

## Exact physical gate

First confirm default boot still crosses `/metadata`, canonical `/vendor`, SwitchRoot and second
stage. Then capture:

```text
getprop ro.product.product.cpu.abilist
getprop ro.product.product.cpu.abilist64
getprop ro.product.product.cpu.abilist32
getprop ro.product.cpu.abilist
getprop ro.product.cpu.abilist64
getprop ro.product.cpu.abilist32
getprop init.svc.zygote
getprop init.svc.zygote_secondary
pidof system_server
```

The ABI gate passes only if both triplets are canonical, both zygotes run, the old app_process64 ABI
abort disappears and AArch64 system_server is reached. If SurfaceFlinger still aborts at
`gralloc-mapper is missing`, classify the r5 ABI/runtime-product fix separately as PASS and graphics
as its independent FAIL; do not require UI for this ABI gate.

Rollback remains frozen Android 16 ARM32 `a16-prototype-a-r4`; frozen Android 12
`m8b-remote-r1` remains the final working fallback.
