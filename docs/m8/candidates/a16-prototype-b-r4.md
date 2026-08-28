# Android 16 QPR0 Prototype B r4

Date: 2026-08-28

Offline status: **OFFLINE CHECKED / READY FOR PHYSICAL VALIDATION**

Physical status: **NOT YET VALIDATED**. This is a single-cause ABI-property successor to immutable
physical-fail r3, not a graphics repair and not a mixed-runtime physical PASS.

## Why r4 was authorized

Exact r3 physical evidence reached second-stage ARM64 userspace. `app_process64` then aborted
deterministically because global `ro.product.cpu.abilist64` was empty, although system- and
vendor-scoped mixed ABI metadata was correct. The signed-image census and exact
`android-security-16.0.0_r7` property code uniquely explain all observations:

1. r3 product_a contains no `ro.product.product.cpu.abilist*` values;
2. retained ODM is ARM32-only, while system and vendor contain correct mixed scoped values;
3. `system/core/init/property_service.cpp` loads partition properties, then derives global ABI
   lists using fixed priority `product, odm, vendor, system`;
4. absent product metadata therefore lets ODM win, producing global ARM32-only `abilist`, empty
   `abilist64`, and the exact observed zygote abort;
5. `ro.product.cpu.abi=arm64-v8a` is emitted separately from the primary `DeviceAbi`, explaining
   why that single global property was correct.

The machine proof is `a16-prototype-b-r3-abi-root-cause.json`. This is a unique build/provenance
cause; it does not require runtime `setprop`, an init workaround, a vendor workaround or a change
to the mixed architecture.

## Exact bounded delta

The ARM64 product now generates the canonical product-scoped triplet from the locked mixed target
ABI lists:

```text
ro.product.product.cpu.abilist=arm64-v8a,armeabi-v7a,armeabi
ro.product.product.cpu.abilist32=armeabi-v7a,armeabi
ro.product.product.cpu.abilist64=arm64-v8a
```

Exact source is
`configs/aosp/architecture-ceiling-a16/device/ubox/ceiling/ubox10_ceiling_arm64.mk`, SHA-256
`1EE047D6824B31B8CCA4F239F949CC0F4E8E403194B84BBB818DF04A1F487341`. The exact QPR0 product build
generated those values into `system/product/etc/build.prop`; its SHA-256 is
`7508D4DDA27B68D52D7CBDC891F15D3DD91CB942E9DBB3E590D35697A4997729`.

Relative to r3, the signed product tree changes only `etc/build.prop` by adding those three lines.
Signed `system_a`, `vendor_a`, `vendor_dlkm_a`, boot, subordinate vbmeta, the B1 graphics providers,
mixed product/zygote architecture and every hardware-facing path are byte-preserved. Product AVB
is regenerated inside the existing exact product extent; LP metadata and geometry do not change.

## Exact artifact identity

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `out/candidates/a16-prototype-b-r4/x12-a16-prototype-b-r4.img` | 1,641,760,768 | `9A7E9FE31CBC16E17B458D8832739056B2A17F5B47BC221730B78EB0DDDCBBEC` |
| signed `system_a.img` | 1,651,167,232 | `F77559D602C780C5FBB1183FB7F26009EF7B66781BC2FC57DE9341997B8260EB` |
| signed `vendor_a.img` | 150,994,944 | `0166B5FB1718715E79F68D5A9FEAAE02439DC59DBE2379D4C1DA670541C7EC9B` |
| signed `product_a.img` | 272,629,760 | `C9050355ABB7C92D985275DBCF8D71E0796B371B0439D382464C8EA0E541A476` |
| raw `super` | 3,221,225,472 | `C09454E672090677554BC1B299DB50EA3978809B2D6F558D28270FF1797959E6` |
| sparse `super.fex` | 1,461,963,904 | `62A69A8C4A719E050D4C6BDFC46E4CFF04F14951D26F9ABC34FFE58610EC4249` |
| `vbmeta_system.fex` | 1,472 | `DC7067B9AD494967968BF496E9B6D211EA84479815B77DF1EF845E2E8BF9D29C` |
| `vbmeta_vendor.fex` | 1,600 | `DE14183FAFBBEA3EC0D2B0E8737FF9F71BA001186A0DE0D58E24891706ACE6C5` |

Source remains exact `android-security-16.0.0_r7`, manifest
`ebea28d151539ecf0730b1a4ab92ac33edc17ac9`, `BP2A.250805.034`, API 36, SPL 2025-08-05 and lunch
`ubox10_ceiling_arm64-bp2a-userdebug`. The product-property target used deterministic build number
`UBOX10_A16_QPR0_B4`; repository starting HEAD was
`fbb0015dda0e1545ffdeab4ea435c1c8d2d8321d`. The implementation delta and this record are delivered
by their enclosing Git commit. Android system and kernel were not rebuilt for candidate assembly.

## Offline acceptance

| Gate | Result |
|---|---|
| source/generated/signed property chain | **PASS** — exact product-scoped triplet; exact r7 derivation predicts canonical global triplet |
| signed product tree delta | **PASS** — only `etc/build.prop`, only three added lines |
| r2 `/metadata` and r3 `/vendor` contracts | **PASS / BYTE-PRESERVED IN SYSTEM_A** |
| ext4 / product AVB | **PASS** — SHA256_RSA2048 hashtree, no FEC, rollback 0/location 0 |
| system/vendor AVB and subordinate vbmeta | **PASS / BYTE-PRESERVED FROM r3** |
| LP geometry / sparse roundtrip / IMAGEWTY | **PASS** |
| outer payloads | **PASS** — only `super.fex` and `Vsuper.fex` changed; 48/50 preserved |
| mixed ABI / zygote | **PASS OFFLINE** — ARM64 primary, ARM32 secondary, `zygote64_32`, both app_process binaries |
| ELF census | **PASS** — 1,471 AArch64 system, 701 ARM system, zero AArch64 vendor service |
| Mali/linker/SP-HAL | **PASS OFFLINE** — 297 strong imports / zero unmatched; exact providers preserved |
| APEX / VNDK31 | **PASS** — 35 installed/activated; both VNDK31 ABIs |
| split SELinux | **PASS OFFLINE ONLY** — no enforcing runtime claim |
| system VINTF | **PASS** |
| full VINTF | **exit 65 / inherited `CONFIG_NFS_FS=y` vs FCM-6 `n` only; NOT PASS** |
| kernel/modules/AIC/hardware authority | **PASS / BYTE-PRESERVED** — 5.4.302+, six configs, 22 modules |
| r4 focused tests | **6/6 PASS** |
| full lightweight repository suite | **148 discovered / OK / 34 declared fixture skips** |
| JSON / Python / diff hygiene | **PASS** — 56 JSON parsed; scripts/tests compiled; `git diff --check` clean |

The proprietary Mali file remains outside Git. Machine-readable results are
`a16-prototype-b-r4-offline-result.json` and `a16-prototype-b-r4-preservation.json`; persistent
build/audit logs are under `/work/build-logs/a16-prototype-b-r4-20260828/`.

## Independent graphics boundary

R4 intentionally does not change Mali, mapper or gralloc. Read-only audit proves the ARM64 mapper
is ELF64/AArch64, has the expected SONAME and dependencies, exports global `HIDL_FETCH_IMapper`,
and follows exact r7 passthrough discovery into `gralloc.apollo.so`. It eliminates missing files,
wrong bitness/name/export, permanent linkerconfig absence and leading SELinux denial, but current
evidence cannot uniquely distinguish `dlopen`, fetch invocation, `hw_get_module`, or gralloc init
failure. Graphics root cause is therefore **PARTIALLY PROVEN / NOT UNIQUE** and no graphics fix is
mixed into this revision.

## Next physical gate

Validate the exact image above UART-first. First confirm default boot still crosses `/metadata`,
canonical `/vendor`, and second stage. Then record global `ro.product.cpu.abilist*`, both zygote
service states/processes, and AArch64 `system_server`. The ABI correction passes physically only if
`app_process64` no longer aborts for an empty ABI list and both primary/secondary zygotes stabilize.

SurfaceFlinger's independent `gralloc-mapper is missing` result is a separate gate. If it remains
while ABI/zygote/system_server cross their boundary, r4 is an ABI-fix physical PASS and a graphics
physical FAIL; it must not be misclassified as an ABI regression. No UI, Mali runtime, mixed-runtime
viability or physical candidate PASS is claimed before that test.
