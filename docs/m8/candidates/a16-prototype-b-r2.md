# Android 16 QPR0 Prototype B r2

Date: 2026-08-27

Status: **OFFLINE CHECKED / READY FOR PHYSICAL VALIDATION**

Physical status: **NOT YET VALIDATED**. This record does not authorize flashing and makes no mixed
runtime PASS claim.

## Decision

`a16-prototype-b-r2` is the one authorized single-cause continuation from the immutable failed r1.
It restores exactly one accepted system-root mountpoint contract:

```text
/metadata
type directory
mode 0755
uid/gid 0:0
SELinux u:object_r:metadata_file:s0
```

The final signed filesystem tree relative to r1 is exactly `added=[metadata]`, `removed=[]`,
`changed=[]`. No Android or kernel source was rebuilt. The existing system build identity remains
`UBOX10_A16_QPR0_B1`; r2 is the package/candidate revision.

## Proven r1 root cause

The latest user-supplied RAM-only diagnostic applies `androidboot.slot_suffix=_a` and proves fstab
parsing, metadata fsck/mount, all four A-slot logical device creations and `system_a` mount. It then
fails first at:

```text
Switching root to '/system'
Unable to move mount at '/metadata': No such file or directory
InitFatalReboot
```

Frozen r4 signed `system_a` contains the `/metadata` directory above; signed r1 does not. The other
six observed move destinations—`/dev`, `/proc`, `/sys`, `/mnt`, `/debug_ramdisk` and
`/second_stage_resources`—exist with matching r4/r1 type, mode, owner and SELinux label. The
byte-identical r4/r1 first-stage init is SHA-256 `2A7D6E12...62751`; its Android 12 `SwitchRoot`
forms the destination by concatenating `new_root` and the source mount path. Thus
`SwitchRoot("/system")` moving source `/metadata` uniquely requires `/system/metadata`. `system` is
mounted read-only by the exact fstab, so runtime `mkdir` cannot create the missing target before
`MS_MOVE`; the UART ENOENT maps uniquely to that absent path.

Generation provenance agrees: r4's `PRODUCT_DEVICE=generic` resolves the GSI BoardConfig that sets
`BOARD_USES_METADATA_PARTITION=true`; B1's dedicated `ubox10_ceiling_arm64` BoardConfig inherits
generic ARM64 without that flag. Exact r7 `create_root_structure.mk` conditionally creates root
`metadata` only when the flag is set.

The earlier fstab error is retained as diagnostic history but reclassified: that RAM diagnostic
boot omitted `androidboot.slot_suffix`, so it was an artificial blocker, not the r1 candidate root
cause. No fstab, boot or vendor_boot change is present in r2.

## Exact artifact identity

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `out/candidates/a16-prototype-b-r2/x12-a16-prototype-b-r2.img` | 1,641,756,672 | `6FA8D13220DC9367659B5B16798664E906A390820359E72FD16063B84EC48887` |
| signed `system_a.img` | 1,651,167,232 | `5FE7D77931146F6AA989E42F50EF935CA3E7800F479F3302D9C2BE43338F15FC` |
| signed `vendor_a.img` | 150,994,944 | `0166B5FB1718715E79F68D5A9FEAAE02439DC59DBE2379D4C1DA670541C7EC9B` |
| raw `super` | 3,221,225,472 | `E650755DDC29D1E02F6A41D5C141A100F5788645E1076FECD657D291E8D5911C` |
| sparse `super.fex` | 1,461,959,808 | `E14E34E60ED6460F81F40ED9295B7C1DD0C8D1DF93A089598EBCD91A06A6E15C` |
| `vbmeta_system.fex` | 1,472 | `DE6BE32D1C3E924E51283C1BE8E8ECC86E371387760BF07E8048F67D9275A2B2` |
| `vbmeta_vendor.fex` | 1,600 | `DE14183FAFBBEA3EC0D2B0E8737FF9F71BA001186A0DE0D58E24891706ACE6C5` |

Base r1 remains 1,641,752,576 bytes / `796A2D46...9545` and is not overwritten.

## Preservation and generated consequences

Only `system_a` changes semantically. Required generated consequences are its SHA256_RSA2048
hashtree, rollback-location-1 `vbmeta_system`, `super`, and the two Allwinner V companions. Relative
to r1, exactly four outer payloads change: `super.fex`, `Vsuper.fex`, `vbmeta_system.fex` and
`Vvbmeta_system.fex`; 46/50 are byte-identical.

`vendor_a`, `product_a`, `vendor_dlkm_a`, all B-slot bytes and LP geometry are exact r1 bytes.
`vbmeta_vendor`, top-level vbmeta, boot, vendor_boot/fstab, kernel 5.4.302+, all 22 modules, AIC,
Mali, mapper, gralloc, mixed ABI/zygote properties and all hardware-facing services are unchanged.

## Offline acceptance

| Gate | Result |
|---|---|
| root tree delta / seven move destinations | **PASS — SINGLE CAUSE** |
| ext4 / `e2fsck -fn` | **PASS** |
| system/vendor AVB and subordinate vbmeta | **PASS** |
| LP geometry / sparse roundtrip | **PASS / EXACT r1 GEOMETRY** |
| IMAGEWTY | **PASS** |
| mixed ELF | **PASS** — 1,471 AArch64 system, 701 ARM system, no ARM64 vendor service |
| ARM64 Mali closure | **PASS** — 297 strong imports / 0 unmatched |
| APEX / VNDK31 / linkerconfig | **PASS** — 35 APEX, both VNDK31 architectures |
| split SELinux | **PASS OFFLINE ONLY** |
| system VINTF | **PASS** |
| full VINTF | **exit 65 / inherited NFS exception only; NOT PASS** |
| kernel/modules/AIC/hardware preservation | **PASS** |
| r2 focused tests | **6/6 PASS** |
| combined r1/r2 focused tests | **17/17 PASS** |
| full lightweight repository suite | **136 PASS / 34 declared fixture skips** |

Machine records are `a16-prototype-b-r2-offline-result.json` and
`a16-prototype-b-r2-preservation.json`. The proprietary Mali remains outside Git.

## Physical boundary and next action

The exact r2 IMG may be proposed for one separately authorized UART-first physical validation.
The first question is whether it passes the former `/metadata` move and reaches second-stage init;
only then test `apexd`, `zygote64_32`, AArch64 system_server/SurfaceFlinger/Mali and frozen r4
hardware regressions. Do not create r3 or add another fix before this exact r2 result exists.
