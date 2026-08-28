# Android 16 Prototype B r6

离线状态：**OFFLINE CHECKED**。物理状态：**PHYSICAL FAIL — BORINGSSL64 GATE CROSSED;
ARM64 SURFACEFLINGER GRAPHICS MAPPER RUNTIME DISCOVERY FAILURE**。

R5 已物理证明 active embedded product source 与 canonical global mixed ABI；retained vendor
BoringSSL32 随后 exit 0。新的首个 fatal 不是 crypto/linker/SELinux 失败，而是既有 vendor rc 在
`ro.product.cpu.abilist64=*` 成真后找不到 `/vendor/bin/boringssl_self_test64`。R6 只补入 exact
Android 16 r7 `boringssl_self_test_vendor` 的 AArch64 output。它没有修改 rc、32-bit test、
vendor libcrypto、system/ABI、graphics、kernel、TEE 或其他 service。

## Candidate identity

| 项目 | 值 |
|---|---|
| ID | `a16-prototype-b-r6` |
| IMG | `out/candidates/a16-prototype-b-r6/x12-a16-prototype-b-r6.img` |
| 大小 | 1,641,773,056 bytes |
| SHA-256 | `2AAF8E2CA89DDE486A9416FDE7ACFF7BCD6DB80CDCB161598ABF99A7CB2DBD53` |
| base | exact r5, 1,641,760,768 bytes / `418CDC6B...6FE2E` |
| Android | `android-security-16.0.0_r7`; manifest `ebea28d151539ecf0730b1a4ab92ac33edc17ac9` |
| source action | targeted `boringssl_self_test_vendor` build only; no system/kernel rebuild |
| physical result | exact image flashed; BoringSSL64 intended gate PASS, then ARM64 SurfaceFlinger repeatedly aborts `gralloc-mapper is missing` |

## Physical result (2026-08-28)

Externally collected UART/root-console evidence proves that r6 preserves the canonical mixed ABI
triplet and no longer enters the r5 `boringssl-self-check-failed` reboot loop. This is a
**PHYSICAL PASS at the exact r6 missing-executable boundary**, not a claim that the whole crypto
subsystem has been validated. Kernel, first stage, `/metadata`, canonical `/vendor`, SwitchRoot and
second stage remain crossed; the device stays alive with a root console.

Both `app_process64` and `app_process32` enter ART/Zygote startup. The primary reaches `Zygote:
begin preload` and `ZygoteHooks.beginPreload()`. Its restart is not an independent zygote failure:
ARM64 SurfaceFlinger receives SIGABRT four times before boot completion, the updatable-process
health path fires, and init explicitly sends signal 9 to primary `zygote`. System_server is therefore
**NOT REACHED / INDIRECTLY BLOCKED**, not independently failed.

The unique current primary blocker is the repeating ARM64 SurfaceFlinger abort:

```text
Abort message: gralloc-mapper is missing
```

The backtrace reaches `SurfaceFlinger::setupNewDisplayDeviceInternal`, `processDisplayAdded`,
`init`, and `main`. The UI remains black. Presence and offline closure of the three ARM64 graphics
providers do not establish runtime mapper instantiation, and this result proves nothing negative
about Mali yet. The original raw UART/crash captures were supplied externally and are not present
on this VM; `a16-prototype-b-r6-physical-result.json` records the reviewed facts without inventing
a raw-file hash.

## Proven root cause and exact delta

The retained 751-byte rc (`459FEA4E...FE1D`) always declares both vendor services. On the original
ARM32 product, empty ABI64 kept the 64-bit trigger dormant and packaging supplied only the ARM32
binary. R5 correctly activates mixed ABI, so that retained trigger becomes true. Physical init then
fails before exec because the signed vendor lacks the named file. Exact r7 source defines one
`vendor: true`, `compile_multilib: both` module with `32`/`64` suffixes; the canonical AArch64 output
is therefore uniquely identified without a donor or bypass.

R6 vendor tree delta from r5 is exactly:

```text
added   bin/boringssl_self_test64
changed none
removed none
```

The added file is 14,280 bytes, SHA-256
`E8F3B67A7BADC94FE034A74F5C59F085138D5D8E38A27CF3ADEB676AE60C058F`, ELF64/AArch64,
`/system/bin/linker64`, Build ID `7f73c5e1189408db688509323880032e`, mode 0755, owner 0:2000,
label `vendor_boringssl_self_test_exec`. Its five DT_NEEDED entries close against existing r5
VNDK31/Bionic providers with two strong imports and zero unmatched. No standalone vendor
`libcrypto.so` was added: exact VNDK31 libcrypto64 already exports the required symbol, and the
analogous retained 32-bit path physically exits 0.

## Newly activated ARM64 census

The exact signed rc census is prediction-only and authorizes no second r6 repair. Besides the
vendor first fatal, system and Conscrypt-APEX BoringSSL64 tests are present and close offline;
`app_process64`/`app_process32` are present and close offline but remain unmeasured after r5's early
reboot. SurfaceFlinger remains the already-observed independent `gralloc-mapper is missing` runtime
frontier. `dmesgd` is post-boot and not applicable with its 5.4 bootreceiver gate. Details and exact
hashes are in `a16-prototype-b-r6-arm64-service-readiness-census.json`.

## Read-only warnings

- TEE rc still tries three absent `.ko` paths, while `CONFIG_TEE`, `CONFIG_OPTEE` and
  `CONFIG_SUNXI_DRM_HEAP` are built-in. The warnings are real but non-fatal as of r5 and do not alter
  the frozen 22-module contract.
- `/dev/hw_random` returned ENODEV, so exact r7 `prng_seeder` deliberately parks instead of respawning.
  Hardware seeding loss is real; loss of kernel CSPRNG or a boot blocker is not proven.
- cgroup memory-controller warnings retain their successful fallback classification.

None is a BoringSSL64 prerequisite, and none was changed.

## Offline acceptance

- Vendor semantic diff is one added file; rc and BoringSSL32 stay byte-identical.
- System_a, active mixed ABI triplet, product_a, vendor_dlkm, boot, vbmeta_system, `/metadata`,
  canonical `/vendor` and `/product -> /system/product` stay exact r5.
- `e2fsck -fn`, system/vendor AVB, subordinate vbmeta, rollback locations, unchanged LP geometry,
  no shrink, sparse/raw roundtrip, IMAGEWTY and 50-payload audit PASS.
- Changed outer payloads are only `super.fex`, `Vsuper.fex`, `vbmeta_vendor.fex`,
  `Vvbmeta_vendor.fex`; 46 payloads are byte-preserved.
- Mixed ELF census PASS: 1,471 system AArch64 and 701 system ARM objects; `app_process64`,
  `app_process32`, `zygote64_32` present. Vendor AArch64 set is exactly BoringSSL64 plus the frozen
  three graphics providers.
- 35/35 APEX, both-arch VNDK31, linkerconfig, ARM64 SP-HAL, Mali 297/0 imports, split SELinux and
  system VINTF PASS offline.
- Full VINTF remains **exit 65 / inherited `CONFIG_NFS_FS=y` vs FCM-6 `n` only / NOT PASS**.
- Kernel 5.4.302+, six Path-A configs, exact 22 modules and AIC FMAC contract are preserved.
- Focused r1-r6 candidate tests 44/44 PASS; full lightweight suite 163/163 PASS with 34 declared
  missing-fixture skips. Python compilation, 73 tracked JSON parses and `git diff --check` PASS.

Machine records: `a16-prototype-b-r6-offline-result.json` and
`a16-prototype-b-r6-preservation.json`. Build/audit logs remain under
`/work/build-logs/a16-prototype-b-r6-20260828T141804Z/`.

## Closed and open physical gates

Canonical ABI and the r6 BoringSSL missing-executable/reboot boundary are physically closed. Both
ART runtimes and primary zygote preload are physically reached. The subsequent exact Android 16 r7
mapper audit proves filename/manifest/instance/export/SP-HAL discovery correct, but both r6 ARM64
mapper and its factory-loaded gralloc import one strong libc++ diagnostic symbol absent from the
selected VNDK31 snapshot. Bionic eager relocation fails before `HIDL_FETCH_IMapper`; this uniquely
explains the physical abort. Strict r7 closes only that inseparable two-file instantiation contract.
No zygote, Mali, kernel or broad graphics change is authorized by the r6 evidence.

Rollback remains frozen Android 16 ARM32 `a16-prototype-a-r4`; frozen Android 12
`m8b-remote-r1` remains final working fallback.
