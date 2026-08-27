# Android 16 QPR0 Prototype B r1

Date: 2026-08-27

Status: **PHYSICAL FAIL — SYSTEM SWITCH-ROOT `/METADATA` TARGET MISSING / NOT ACCEPTED**

Physical status: **FAILED BEFORE SECOND-STAGE INIT**. The prior build/offline audit performed no
UBOX action and remains valid as an offline record; the user subsequently flashed and UART-tested
the exact r1. That first physical result is now immutable evidence. This is still the same canonical
`a16-prototype-b-r1`; the later single-cause r2 does not rewrite this failure point.

## Initial diagnostic result — superseded causal classification

The user-supplied UART evidence establishes this strict boundary:

| Stage | Result |
|---|---|
| Linux 5.4.302+ kernel | **PASS / REACHED** |
| `/init` exec | **PASS / REACHED** |
| normal first-stage init | **PASS / REACHED** |
| `androidboot.force_normal_boot=1` | **PASS / APPLIED** |
| default fstab | **FAIL** — `ReadFstabFromFile(): failed to load '/fstab.sun50iw9p1'` |
| first-stage mount | **FAIL** — `Failed to create FirstStageMount`, then required early mounts fail |
| fatal handling | `InitFatalReboot` followed by kernel panic |
| second-stage init / `apexd` | **NOT REACHED** |
| zygote / system_server / SurfaceFlinger | **NOT REACHED** |
| ARM64 Mali / mapper / gralloc runtime | **NOT REACHED** |

No raw UART capture is present on this VM, so this repository record preserves the externally
supplied result and exact decisive excerpts; it does not fabricate a raw log or SHA-256. The proper
classification at that evidence point was **FIRST-STAGE MOUNT / DEFAULT FSTAB MISSING**. The later
RAM-only diagnostic proves this was induced by the diagnostic boot lacking `androidboot.slot_suffix`,
not by absent fstab bytes and not by the r1 candidate's current causal boundary.

## Latest RAM-only diagnostic and current root cause

With `androidboot.slot_suffix=_a`, the same r1 passes fstab parsing, metadata fsck/mount, creation of
`system_a`, `product_a`, `vendor_dlkm_a` and `vendor_a`, and mounting `system_a` at `/system`. The
first causal blocker advances to:

```text
Switching root to '/system'
Unable to move mount at '/metadata': No such file or directory
InitFatalReboot
```

Exact signed-root comparison proves r4 has `/metadata` as a directory, mode 0755, uid/gid 0:0,
SELinux `u:object_r:metadata_file:s0`; r1 has no root-level `/metadata`. All other observed top-level
move destinations (`/dev`, `/proc`, `/sys`, `/mnt`, `/debug_ramdisk`,
`/second_stage_resources`) exist in both and have matching type/mode/owner/label.

The exact signed-root contracts are:

| SwitchRoot source / required destination under `/system` | Frozen r4 root | B1 r1 root |
|---|---|---|
| `/dev` | dir `0755`, `0:0`, `device` | exact r4 |
| `/proc` | dir `0755`, `0:0`, `rootfs` | exact r4 |
| `/sys` | dir `0755`, `0:0`, `sysfs` | exact r4 |
| `/mnt` | dir `0755`, `0:1000`, `tmpfs` | exact r4 |
| `/debug_ramdisk` | dir `0755`, `0:0`, `tmpfs` | exact r4 |
| `/second_stage_resources` | dir `0755`, `0:0`, `tmpfs` | exact r4 |
| `/metadata` | dir `0755`, `0:0`, `metadata_file` | **ABSENT** |

Labels above abbreviate the exact `u:object_r:<type>:s0` xattr. Child mounts such as
`/sys/fs/selinux` are moved with their already-selected top-level parent by `MS_MOVE`; the
implementation deliberately excludes such children from the independent move list.

The build provenance explains the root difference exactly. R4's product sets
`PRODUCT_DEVICE := generic`, resolving `build/make/target/board/generic/BoardConfig.mk`; that file
inherits `BoardConfigGsiCommon.mk`, which sets `BOARD_USES_METADATA_PARTITION := true`. B1 instead
sets `PRODUCT_DEVICE := ubox10_ceiling_arm64`; its dedicated BoardConfig includes
`device/generic/arm64/BoardConfig.mk`, which does not set or inherit that GSI flag. Exact r7
`system/core/rootdir/create_root_structure.mk` creates `$(TARGET_ROOT_OUT)/metadata` only under
`ifdef BOARD_USES_METADATA_PARTITION`. Therefore the signed-root omission is the deterministic
product/BoardConfig generation consequence, not an ext4, AVB, packaging or first-stage fstab loss.

The executed r4/r1 first-stage init remains byte-identical at SHA-256 `2A7D6E12...62751`. Its
Android 12 `SwitchRoot` contract forms `new_mount_path = new_root + mount_path`; with
`new_root=/system`, moving the mounted source `/metadata` therefore requires target
`/system/metadata`. The signed system filesystem is read-only, so the attempted runtime `mkdir`
cannot supply the missing target; `mount(..., MS_MOVE)` returns the observed ENOENT. This is a
unique causal correspondence: **PROVEN B1 SYSTEM-ROOT `/metadata` MOVE TARGET ABSENT**.

## Exact r4 versus r1 fstab provenance audit

The physically accepted r4 default fstab does **not** come from its generated `system_a` root.
Both r4 and r1 generated system roots lack `/fstab.sun50iw9p1`,
`/first_stage_ramdisk/fstab.sun50iw9p1` and `/system/etc/fstab.sun50iw9p1`. The accepted source is
the header-v3 `vendor_boot.fex` vendor ramdisk:

```text
first_stage_ramdisk/fstab.sun50iw9p1
size 2330
mode 0644, uid/gid 0:0
SHA-256 6C771313A6F9DEDAEFA4061B14FE142F050F4AB13D360FF2F60FB9361277F701
```

The preserved boot ramdisk runs `/system/bin/init`, an ELF32 ARM executable with SHA-256
`2A7D6E125583C79E925B5D916C54C51E4AE8EE145F2D7422B2DD77D0B6C62751`. With
`androidboot.force_normal_boot=1`, first-stage init switches root to `/first_stage_ramdisk`; the
archive path above therefore becomes runtime `/fstab.sun50iw9p1`. The boot hardware suffix
`sun50iw9p1` is what directs default-fstab lookup to that filename. The DT supplies Android firmware,
boot-device and vbmeta data but has no Android fstab node, so the file is the required fallback.
`/vendor/etc/fstab.sun50iw9p1` is a later identical copy and cannot be the initial source because
vendor has not yet been mounted.

Detached extraction from both exact outer images proves that all pre-failure inputs are identical:

| Input | r4 and r1 exact identity |
|---|---|
| `boot.fex` | 67,108,864 bytes / `527CF878...B8063` |
| `Vboot.fex` | `CCA715D2...F8DA3` |
| `vendor_boot.fex` | 33,554,432 bytes / `AAF77E65...7E72` |
| `Vvendor_boot.fex` | `A9DD7B9B...4B90F` |
| vendor ramdisk | 1,437 bytes / `89CCD98E...C7E9` |
| vendor-boot DTB | 68,228 bytes / `24928802...2F72` |
| `sunxi.fex` | 72,704 bytes / `29E551D6...8EBAA` |
| `dtbo.fex` / `Vdtbo.fex` | `6CF9B085...911F` / `E966D753...AAC1` |
| first-stage fstab | 2,330 bytes / `6C771313...F701` |
| late vendor fstab | same `6C771313...F701` in both vendor images |

Both outer packages also pass IMAGEWTY checksum verification. The only six r1 outer changes remain
`super`/`Vsuper`, subordinate system/vendor vbmeta and their V companions; none supplies or executes
the default fstab before this failure.

This earlier audit correctly disproved a package-level fstab omission and prevented a speculative
fstab copy. The newer slot-correct diagnostic now resolves that evidence conflict and moves the
causal boundary to the signed system root. Machine-readable history and reclassification are in
`a16-prototype-b-r1-first-stage-audit.json`.

## Historical offline decision

All bounded B1 offline gates closed after the explicitly authorized storage correction. The exact
candidate is:

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `out/candidates/a16-prototype-b-r1/x12-a16-prototype-b-r1.img` | 1,641,752,576 | `796A2D46DB7FCDFF27D53397565ABDDC3D18F2E548A697055CE5E47278E69545` |
| signed `system_a.img` | 1,651,167,232 | `DBA433B58363F2C393B76428E339380604AFCA6F5CE2153D3A387C4A74CFFCA0` |
| signed `vendor_a.img` | 150,994,944 | `0166B5FB1718715E79F68D5A9FEAAE02439DC59DBE2379D4C1DA670541C7EC9B` |
| raw `super` | 3,221,225,472 | `E740AC913A9EE5643FD795CC1E6C8178F892ECAEFDEDF79CA0DDC4E42C223EA3` |
| sparse `super.fex` | 1,461,955,712 | `F961F2DD2674513E0788823A88D14FE67E493FC88D486E419F52BCEED7B48A3F` |
| `vbmeta_system.fex` | 1,472 | `7D3546FD3AA9F33075CB7BB858D1B9D7EF406CE6198C5D320A7E0B48DB20ADDB` |
| `vbmeta_vendor.fex` | 1,600 | `DE14183FAFBBEA3EC0D2B0E8737FF9F71BA001186A0DE0D58E24891706ACE6C5` |

That offline decision was not a runtime claim and is now superseded by the physical first-stage
failure above. Mixed zygote startup, AArch64 SurfaceFlinger/system_server, Mali rendering,
cross-bitness graphics-buffer transport and all preserved hardware behavior remain untested.

## Same-r1 history and bounded storage closure

The earlier same-r1 attempt first stopped at a local Mali intake check. The file identity was exact;
the failure was an anchored Build-ID parser that did not accept `readelf -W` single-line note
output. The minimally repaired checker remains fail-closed on size, SHA-256, ELF class/machine,
SONAME, Build ID and exact DT_NEEDED.

Actual vendor staging then proved frozen r4 `vendor_a` could not hold the locked three ARM64
providers and mixed product properties. That historical **PARTITION FIT HOLD** was valid under the
then-frozen LP contract. On 2026-08-27 the user authorized one correction only: grow `vendor_a` from
119,066,624 to 150,994,944 bytes using existing `sb_a` unallocated space. A fresh exact-r7
`lpdump` of frozen r4 reproduced JSON SHA-256
`65886ACB7D685691A9223392F351A384DEA84EFFD7496C4AC893B34CE191EF18` before implementation.

| Quantity | Frozen r4 | B r1 result |
|---|---:|---:|
| `vendor_a` | 119,066,624 | 150,994,944 |
| `sb_a` maximum | 3,212,836,864 | 3,212,836,864 |
| `sb_a` allocated | 2,049,544,192 | 2,081,472,512 |
| `sb_a` unallocated | 1,163,292,672 | 1,131,364,352 |

The 31,928,320-byte growth came only from old free space. `system_a`, `product_a`,
`vendor_dlkm_a`, every B-slot allocation, the group maximum and all other partition sizes/extents
remain exact; no partition was shrunk. The assembler checks these invariants from actual candidate
metadata and checks sparse→raw round-trip equality. In half-open 512-byte sectors, final
`vendor_a` is exactly `[[3227648,3461120],[4007936,4069376]]`; the first extent contains the old
`[3227648,3460200]` allocation, and the second is entirely within old unallocated `sb_a` space.

## Exact source and mixed product

| Contract | Exact result |
|---|---|
| Source | `android-security-16.0.0_r7`; manifest `ebea28d151539ecf0730b1a4ab92ac33edc17ac9` |
| Android identity | `BP2A.250805.034`; API 36; SPL 2025-08-05 |
| Lunch / number | `ubox10_ceiling_arm64-bp2a-userdebug` / `UBOX10_A16_QPR0_B1` |
| Primary | ARM64/AArch64 `armv8-a` generic |
| Secondary | ARM32/ARM `armv7-a-neon` cortex-a15 |
| ABI / zygote | `arm64-v8a,armeabi-v7a,armeabi` / `zygote64_32` |
| Product boundary | shipping API 31; VNDK 31; Apollo platform; r4 TV/EGL/remote composition retained |

The long mixed system build initially failed while creating `system.img`: generic arm64
BoardConfig had left `BOARD_SYSTEMIMAGE_PARTITION_SIZE` at 1 GiB while the completed mixed tree
needed 1,230,289,920 bytes. This was the first causal build failure. Frozen r4 already allocates
exactly 1,651,167,232 bytes to `system_a`, and that extent was required to remain fixed. The bounded
source-native correction therefore sets the build-time system image size to exactly
1,651,167,232; it changes no LP geometry or B1 semantics. The same output resumed and completed.

The unsigned source build is 1,651,167,232 bytes with SHA-256
`AA376DD3186044B82B1D0AD05415A2DDEFC174BACBCA153E9DF38769DF4E3FBC`. The signed candidate
filesystem minimized to 1,250,484,224 bytes before its AVB footer, leaving 400,683,008 bytes of
partition headroom.

## Locked B1 functional delta

The semantic delta from frozen r4 is exactly:

1. ARM64 primary plus ARM32 secondary Android userspace and `zygote64_32`;
2. the ten exact vendor-owned ABI/zygote/Dalvik property values required by that mixed product;
3. these three ARM64 same-process graphics providers:

| Candidate path | Bytes | SHA-256 |
|---|---:|---|
| `/vendor/lib64/egl/libGLES_mali.so` | 18,145,112 | `03333D495E3566C7D85CA2E000DA569A16CE8F022EA25C0EA61950C891D5C7F8` |
| `/vendor/lib64/hw/android.hardware.graphics.mapper@2.0-impl-2.1.so` | 36,080 | `83A236476CB24DE2514159534A267334A4C8D7BC957497CD25C70C93F757762D` |
| `/vendor/lib64/hw/gralloc.apollo.so` | 77,272 | `842BA5157989B6BCBF7DC800DC5323FAC9BEF37D914FA56A25A4656B97692E1F` |

The proprietary Mali input remained outside Git under its hash-locked local intake contract;
redistribution rights remain unproven. No ARM64 Vulkan provider or fourth proprietary provider was
added. ARM32 HWC/composer, graphics allocator service, media/Cedar, audio, Wi-Fi, Bluetooth, DRM,
TEE and other mature HAL processes remain process-isolated.

Compiler-derived ARM32 and ARM64 `private_handle_t` transport layouts are identical: size 232,
alignment 8, `plane_info_t` size 16/alignment 4, `numFds=2`, `numInts=53`, magic `0x03141592` and
all transported field offsets equal. This is offline structural evidence, not runtime import proof.

## Offline audit result

| Gate | Result |
|---|---|
| ext4 / `e2fsck -fn` | **PASS** — system, vendor, product, vendor_dlkm |
| AVB | **PASS** — system hashtree, vendor hashtree/FEC, signed subordinate vbmeta and rollback locations |
| LP / super | **PASS** — 10.2 metadata, three slots, exact bounded extents, empty B slots, sparse/raw round-trip |
| IMAGEWTY | **PASS** — 50 payloads |
| ELF / ABI | **PASS** — 2,517 ELF; 1,471 AArch64 system and 701 ARM system objects; zero unresolved mandatory names |
| Mali final-image closure | **PASS** — nine DT_NEEDED; 297 strong imports; zero unmatched |
| APEX | **PASS** — all 35 installed APEXes verify and activate |
| VNDK31 | **PASS** — ARM64 and ARM `libaudioroute.so` present |
| linkerconfig | **PASS** — mixed `${LIB}` expansion, vendor VNDK31 and ARM64 `sphal` visibility |
| split SELinux | **PASS OFFLINE ONLY** — exact platform/system_ext + API-31 vendor compile |
| system VINTF | **PASS**, exit 0 |
| full VINTF | **INCOMPATIBLE**, exit 65 — inherited NFS exception only; no new incompatibility |
| kernel / modules | **PASS PRESERVED** — 5.4.302+, six Path-A configs, exact 22 modules |
| AIC FMAC | **PASS PRESERVED** — upload/read/START_APP `0x00120000`/`0x00120180`/`0x00120000` |

The full VINTF result is deliberately not called PASS: the sole error remains inherited
`CONFIG_NFS_FS=y` versus FCM-6 required `n`. The kernel was not rebuilt or modified to make the
report green. Offline SELinux compilation likewise does not prove enforcing runtime compatibility.

The final ELF audit classifies 15 ELF64 BPF objects as BPF bytecode, not AArch64 userspace. APEX
activation found `com.android.runtime` and `com.android.vndk.v31`; both VNDK31 architectures are
present. A stable trailing-column symbol parser was required because AArch64 bionic exports several
Mali libc dependencies as GNU IFUNC (`<OS specific>: 10`); the final image resolves all of them.
The resumable APEX audit also recreates its generated activation directory on every run, preventing
stale local audit state from changing the result. Neither audit-tool correction changed candidate
bytes.

## Preservation result

Frozen r4 remains the exact hardware authority. The kernel is still 5.4.302+; extracted Image is
23,498,760 bytes / `287A82F799982FB58D02ADE88150A9EAB22D4C0956BE3CE50765F6FD1DB24F40`.
`boot.fex`, `product_a`, `vendor_dlkm_a`, all 22 modules, top-level vbmeta, vendor_boot, DT/DTBO,
TEE/DRM, bootloader, factory/security and rollback/recovery assets are byte-preserved. HDMI, audio,
Wi-Fi, Ethernet, remote and all other hardware behavior remain unchanged by design.

Exactly six of 50 outer payloads changed as required consequences:

- `super.fex` and `Vsuper.fex`;
- `vbmeta_system.fex` and `Vvbmeta_system.fex`;
- `vbmeta_vendor.fex` and `Vvbmeta_vendor.fex`.

The other 44 payloads compare exact to r4. Machine-readable evidence is in
`a16-prototype-b-r1-offline-result.json` and `a16-prototype-b-r1-preservation.json`.

## Repository quality gate

Exact-r7 source identity, the fail-closed Mali intake and the compiler-derived cross-bitness handle
check all pass. The combined B1 focused suite is 21/21 PASS. The established full repository command
`python3 -m unittest discover -s tests` reports 127 tests OK with 34 repository-declared skips.
Python syntax compilation, JSON parsing and `git diff --check` also pass.

## Current handoff

r1 remains the immutable failed physical evidence point and is not accepted. Its exact root cause
is now proven, so one strict single-cause `a16-prototype-b-r2` was authorized and built. r2 restores
only the accepted root `/metadata` directory contract and is **OFFLINE CHECKED / READY FOR PHYSICAL
VALIDATION**; see its separate candidate record. The known r4 auto-recovered boot-time legacy audio
failure remains unchanged and unfixed. Vulkan, enforcing SELinux, commercial DRM and
release-hardening work remain outside this failure boundary.
