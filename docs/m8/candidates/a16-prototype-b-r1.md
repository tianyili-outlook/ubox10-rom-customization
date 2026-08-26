# Android 16 QPR0 Prototype B r1 candidate attempt

Status: **OFFLINE HOLD / NO CANDIDATE / PARTITION FIT BLOCKER**.

Canonical candidate ID: `a16-prototype-b-r1`. Architecture milestone: Prototype B B1. This is the
continuation of the same r1 attempt recorded at repository HEAD `d2675ce6...`; no r2 exists.

## Decision

The former pre-build HOLD is closed. The outside-Git ARM64 Mali file is exact, the checker parsing
defect is repaired without weakening any identity field, `/work` has adequate host capacity, the
QPR0 mixed product configures correctly, both ARM64 graphics adapters compile, and the compiler-
derived ARM32/ARM64 transported handle layout is identical.

The actual, bounded vendor staging then established a new decisive gate:

**PARTITION FIT BLOCKER — the locked B1 vendor delta cannot fit frozen r4 `vendor_a`.**

The r4 vendor logical extent is 119,066,624 bytes. Its AVB footer reports a 117,104,640-byte ext4
data image; that filesystem has only 90 free 4 KiB blocks (368,640 bytes). Staging only the minimum
mixed-ABI property changes and the exact three ARM64 providers, then running `resize2fs -M`, requires
135,270,400 ext4 bytes. That is 18,165,760 bytes beyond the available filesystem region, before the
1,961,984 bytes reserved for vendor hashtree/FEC/footer are regenerated.

Formal result: **OFFLINE HOLD — EXACT BOUNDED BLOCKER: VENDOR_A PARTITION FIT**. This is not a Mali
identity failure, a provider ABI contradiction, a compile failure, or a Prototype B structural
NO-GO. The task explicitly prohibited changing LP geometry, so the system build was stopped at
57,358/158,582 actions (36%) once the fit result was conclusive. No system/vendor/super/IMAGEWTY
candidate was produced, and no physical action occurred.

## Control, source and host preflight

| Item | Exact result |
|---|---|
| Repository starting HEAD | `d2675ce6c291aede8686f156d1a3cc5881797101` |
| Frozen r4 image | 1,239,746,560 bytes / `E125DD8FFB9F5B4A7B2B9B86DD8377367409AB00D1B29BE1E719CE25768E2111` — PASS |
| QPR0 source | `android-security-16.0.0_r7`; manifest commit `ebea28d151539ecf0730b1a4ab92ac33edc17ac9` |
| Pinned manifest | 246,298 bytes / `F52BA4A04957CEC7EEE7C9DCDD1525533156A0B5A1F0ADFC31A8155F48FB087E` — PASS |
| Lunch / Android | `ubox10_ceiling_arm64-bp2a-userdebug`; Android 16 / `BP2A.250805.034` |
| Product arch | ARM64 `armv8-a`/generic primary + ARM `armv7-a-neon`/cortex-a15 secondary; Apollo platform — PASS |
| Host before build | 8 CPUs; 65,841,336 KiB RAM; no swap; 252,889,870,336 bytes free on `/work` |
| Physical actions | None; no image exists to flash |

The tracked mixed product changes the ARM64 lunch from retired `bp4a` to exact QPR0 `bp2a`, supplies
an Apollo BoardConfig, and carries forward r4's display matrix, `ro.hardware.egl=mali`, and
`sunxi-ir.kl`. It does not change the frozen kernel, hardware services or accepted r4 image.

The configured product contract is `TARGET_ARCH=arm64`, `armv8-a`/generic plus
`TARGET_2ND_ARCH=arm`, `armv7-a-neon`/cortex-a15. The staged vendor delta changes only
`ro.zygote=zygote64_32`; all/64/32 ABI lists to
`arm64-v8a,armeabi-v7a,armeabi` / `arm64-v8a` / `armeabi-v7a,armeabi`; primary/secondary bionic
arch/variants to arm64/generic and arm/cortex-a15; and the matching two Dalvik ISA variants.
`ro.board.platform=apollo` and `ro.vndk.version=31` remain exact. These are configuration/staging
PASS results, not final-image or runtime proof because the partition gate stopped packaging.

## Mali checker closure

The blob was always correct. `readelf -W -n` places `Build ID:` after the GNU note metadata on the
same line, while the old checker required it at line start. The parser now accepts `Build ID:` at a
word boundary; size, SHA-256, ELF class/machine, SONAME, Build ID and exact DT_NEEDED remain mandatory.
Focused tests cover multiline output, wide single-line output and fail-closed missing metadata.

`python3 scripts/check-a16-prototype-b-r1-mali.py` now returns
`PASS_EXACT_ARM64_MALI_LOCAL_INTAKE`:

| Field | Exact value |
|---|---|
| Outside-Git path | `/work/local-proprietary/ubox10/prototype-b-b1/libGLES_mali.so` |
| Size / SHA-256 | 18,145,112 / `03333D495E3566C7D85CA2E000DA569A16CE8F022EA25C0EA61950C891D5C7F8` |
| ELF / SONAME | ELF64 AArch64 / `libGLES_mali.so` |
| Build ID | `281008657ed1f606be382d076fe69918` |
| DT_NEEDED | exact B0 nine-library list — PASS |
| Provenance boundary | redistribution rights unproven; binary remains outside Git and evidence archives |

## Built provider and handle evidence

The public gralloc source remains pinned to BPI commit `316cd80ca43fa17b0385eacd7f6f3652bbd66b2a`,
tree `8a231b4f821fc0e30fd9010fb6b51ab01325d616`. Only two Android 16 build-compatibility adaptations
were required: move `libdl` from `LOCAL_CFLAGS` to `LOCAL_SHARED_LIBRARIES`, and replace removed
private `String8::isEmpty()/string()` calls with `empty()/c_str()`. Neither changes gralloc behavior
or serialized handle fields. Five imported files also receive whitespace-only EOF/indent cleanup so
the repository passes `git diff --check`. The unused donor mapper 2.x implementation was not selected.

| B1 provider output | Result |
|---|---|
| exact r7 AOSP ARM64 passthrough mapper 2.1 | 36,080 bytes / `83A236476CB24DE2514159534A267334A4C8D7BC957497CD25C70C93F757762D` / Build ID `e9198e0d05b08c9fb4a3d54c3f65f994` — ELF64 AArch64 PASS |
| public-source ARM64 `gralloc.apollo.so` | 77,272 bytes / `842BA5157989B6BCBF7DC800DC5323FAC9BEF37D914FA56A25A4656B97692E1F` / Build ID `59e5e1219b02315d7ac69734c760e0b8` — ELF64 AArch64 PASS |
| cross-bitness handle layout | `private_handle_t` 232 bytes/alignment 8; `plane_info_t` 16/alignment 4; `numFds=2`, `numInts=53`, magic `0x03141592`; every transported offset identical — **OFFLINE PASS** |

Pointer and `off_t` widths differ normally across architectures, but their transported unions keep
the same 8-byte slots. Exact-board import remains a physical gate only after a fit-approved image
exists.

## Partition-fit evidence

The measurement starts from a copy of exact r4 `vendor_a` (`BB91A8...929A`), erases its footer,
temporarily enlarges only the disposable measurement copy, writes the ten exact property values and
the three exact providers with the corresponding vendor/SP-HAL labels, checks ext4, and minimizes
it. It never modifies r4, the accepted super image, or LP metadata.

| Quantity | Bytes |
|---|---:|
| Fixed `vendor_a` logical extent | 119,066,624 |
| Available ext4 data region inside that extent | 117,104,640 |
| r4 free ext4 blocks | 368,640 |
| Exact three provider file bytes | 18,258,464 |
| Minimum staged ext4 | 135,270,400 |
| Minimum overflow before AVB/FEC | **18,165,760** |
| Existing AVB hashtree/FEC/footer reservation | 1,961,984 |

`scripts/audit-a16-prototype-b-r1-vendor-fit.py` reproduces the result. Detailed machine-readable
results are in `a16-prototype-b-r1-offline-result.json` and
`configs/candidates/a16-prototype-b-r1.json`; raw local logs are under
`/work/build-logs/ubox10-a16-prototype-b-r1/20260826T153506Z/`.

## Gates not reached

Because partition fit is a mandatory pre-packaging gate, the complete system image, final mixed ELF
census, final linker/`sphal`, final VINTF, system/vendor AVB, LP/super, IMAGEWTY, and detached r4
payload-preservation audits are **NOT RUN / NO CANDIDATE**. The inherited NFS full-VINTF exception
and r4 boot-time audio P1 remain unchanged; neither was exercised or repaired.

## Required next decision

Do not create r2 and do not silently resize. Before this same canonical r1 may resume, project
governance must authorize one exact storage contract and update B0's expected-exact partition rule:

1. an explicitly measured LP geometry change providing at least the staged vendor filesystem plus
   AVB/FEC headroom while keeping the 3,212,836,864-byte `sb_a` group and all logical contents
   controlled; or
2. an evidence-backed alternate placement that still exposes all three libraries at the required
   `/vendor/lib64/{egl,hw}` runtime paths without weakening linker/SP-HAL or AVB boundaries.

Until that single bounded decision is made, `a16-prototype-b-r1` remains HOLD, r4 stays the frozen
Android 16 ARM32 control, and no physical validation is requested.
