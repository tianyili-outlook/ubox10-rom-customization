# Android 16 QPR0 r7 source-only audit

Date: 2026-08-24

Decision: **GO FOR PROTOTYPE A r3 BUILD — FUTURE TASK ONLY**

Scope: exact official AOSP source inspection only. This audit did not build a target image or
kernel, create a candidate/PhoenixCard image, access the UBOX, start Prototype B, or change the
product to `zygote64_32`.

## Executive decision

Exact `android-security-16.0.0_r7` source supports the selected Path A: Android 16 QPR0/25Q2 on
the retained AArch64 Allwinner Linux 5.4 lineage. Its fatal `NetBpfLoad` floor is 5.4, and its
non-GKI release/VTS floor is exactly 5.4.277. The accepted r5 kernel is 5.4.302, 25 stable patch
levels above that floor. The r4/25Q4 fatal requiring 5.10 is absent because this tag identifies
and self-checks as 2025 Q2 / API 36.0; no version check is bypassed.

The minimum retained-kernel delta remains bounded to the already tracked Path-A config: three
cgroup options needed by the observed r1/r2 init path and three traffic-control options required
by QPR0 netd rate limiting. QPR0 contains explicit 5.4 BPF program variants and does not require
a speculative backport of BTF, ring buffers, BPF link/batch, split CAP_BPF/CAP_PERFMON, tracing or
IncFS for ordinary boot/network operation.

No source-level blocker invalidates the ARM32 TV product. The API-31 cgroup overlays, VNDK 31
namespace, APEX bootstrap model, FCM-6 branch, bounded display matrix addition and bounded
`fuseblk` split-policy delta remain applicable. Full VINTF is still **INCOMPATIBLE** solely because
the inherited BSP has `CONFIG_NFS_FS=y` while FCM 6 requires it unset; this audit does not relabel
that conformance exception as PASS or claim enforcing SELinux compatibility.

Android 16 Gate 2 is therefore **UNBLOCKED / READY FOR ONE FUTURE PROTOTYPE A r3 BUILD**, not
automatically PASS. Prototype B and mixed AArch64/ARM32 work remain closed.

## Source identity and preservation method

The existing `/work/src/ubox10-a16-ceiling` Repo checkout was clean across 1,011 projects before
the audit. Before any manifest experiment, its exact r4 state was regenerated with
`repo manifest -r`:

- tag: `android-16.0.0_r4`;
- manifest commit: `15128c9e27cfa599c48d294babd39286ee8f1426`;
- pinned-manifest SHA-256: `4e8beb5d1b590dff3d631b1dbb957138dbda4e608a3183c625683da4bc84918f`;
- pinned manifest size: 233,871 bytes / 1,037 lines;
- retained r4 `system.img`: 946,765,824 bytes / SHA-256
  `fd349f1d8073dfeb71e2cea28915f1c755fa54e3eba85616fcaa279063f3edbe`.

`/work` had 54,527,959,040 bytes available. A second full AOSP checkout or a 58 GiB output-tree
duplicate would have been unnecessary and risky. The audit therefore left the clean r4 worktrees
and `out-ceiling` untouched and read immutable r7 tag objects from the existing shared Repo object
store. One shallow frozen VNDK project fetched only its official r7 tag; it peeled to the already
checked-out frozen v31 commit. No source sync, checkout or target build remained running.

The official r7 manifest identity is:

| Item | Exact value |
|---|---|
| tag | `android-security-16.0.0_r7` |
| manifest commit / tree | `ebea28d151539ecf0730b1a4ab92ac33edc17ac9` / `e4641ccf8e59e0028248d32e5a7fd212760b7a22` |
| `default.xml` SHA-256 | `455b978ffd07e7a1699364e6ccac3f8b9fe455905712b4923c0b97414f97769d` |
| manifest size | 100,836 bytes / 1,025 lines |
| build/make commit | `e780ae328060afca5ed007c34322bfa7ce9b4e60` |
| build/release commit | `ecaf883f0ecb92307aa38fd98bf79029b5855565` |
| `BUILD_ID` | `BP2A.250805.034` (`core/build_id.mk` SHA-256 `5c700904da9d04898ebe031a4fc8d6c252f17f4ef30a48b92ee8aa5052128f54`) |
| release config | `aosp_current -> bp2a`; `bp2a` inherits `bp1a` |
| platform | SDK `36`, full SDK `36.0`, codename `REL`, stable version `16` |
| SPL | `2025-08-05` |

Audited project revisions are recorded at the end of this document and machine-checked by
`scripts/audit-a16-qpr0-r7-source.sh`.

## A. Kernel release policy and BPF

`packages/modules/Connectivity` commit
`5276e77d46a4e1f3121f7d2f651fc2185fa59342` is decisive:

- `bpf/loader/NetBpfLoad.cpp:1716-1721` returns fatal only when a 25Q2 kernel is below 5.4.
- Lines 1730-1733 require a 64-bit kernel. The retained Image is AArch64; the physical
  `uname ... armv8l` suffix reflects the 32-bit Android userspace, not a 32-bit kernel.
- Lines 1747-1774 warn on older LTS patch floors but do not silently waive them. The release
  contract is asserted by `system/netd/tests/kernel_test.cpp:144-178`: 5.4+ and exact non-GKI
  5.4.277+. The tracked 25Q2 decision commit is
  `7004c06cc45208ae8860057205fa41e7bb6eb47f`.
- `netbpfload.rc:1` identifies `2025 2 36 0 0`; loader lines 1825-1836 parse that installed file
  and fail unless it is exactly 2025 Q2 / API 36.0.
- r4 `NetBpfLoad.cpp:1634-1639` contains the separate fatal
  `Android 25Q4 requires kernel 5.10.` QPR0 has no 25Q4 release state or that branch. Selecting
  the official QPR0 tag makes the check inapplicable; it does not patch around it.

QPR0 network programs are deliberately versioned. `bpf/progs/netd.c:616-660` contains 25Q2
ingress/egress implementations with `[5.4, 5.10)` bounds, and `offload.c` retains 5.4/older
fallbacks. The loader skips objects outside their declared kernel range.

### Minimum BPF/config contract

| Facility | QPR0 classification for this product | Evidence / action |
|---|---|---|
| `CONFIG_BPF`, `BPF_SYSCALL`, `BPF_JIT`, `BPF_JIT_ALWAYS_ON`, `CGROUP_BPF`, efficient unaligned access | Required network baseline; already present | netd tests lines 89-118 and retained config |
| `CONFIG_NET_CLS_MATCHALL` | Required for netd rate limiting/release test, not the generic init mount | Enable; exact netd test lines 89-101 |
| `CONFIG_NET_ACT_POLICE` | Required for netd rate limiting/release test | Enable |
| `CONFIG_NET_ACT_BPF` | Required for netd rate limiting/release test | Enable |
| `CONFIG_BPF_UNPRIV_DEFAULT_OFF` | Must remain unset for this QPR0 test | Already unset |
| vmlinux/object BTF | Not required on 5.4 | `NetBpfLoad.cpp:859-878` reads/loads BTF only on 5.10+ |
| BPF ring buffer | 5.10+ optional/debug path on this kernel | ringbuf macro declares `KVER_5_10`; loader skips the map on 5.4 |
| BPF link/batch APIs | Not in the minimum QPR0 5.4 network path | No backport justified by exact r7 sources |
| `CAP_BPF` | Not available in upstream 5.4 and not required by the root legacy loaders | Do not backport merely for parity |
| `CAP_PERFMON` | Used by disabled UprobeStats service; not boot/network critical | Record feature gap, do not backport for r3 |
| kprobe/uprobe/ftrace | UprobeStats/diagnostic functionality only in this product | Existing `n` values are acceptable for r3; do not claim UprobeStats works |
| IncFS | Incremental install/streaming feature, not ordinary boot | `readIncFsFeatures()` returns v1/none if feature dir is absent; retain `n` and do not claim feature support |

The UprobeStats APEX service remains `disabled`, `oneshot` and requests `PERFMON`. Its legacy
loader treats objects without a `critical` section as optional, logs failures, then execs the
platform bpfloader. Thus missing 5.10 ringbuf/tracing/CAP_PERFMON is a real unavailable optional
feature, not a reason to broaden the retained-kernel contract.

## B. Exact retained kernel configuration

The minimum future r3 config is the tracked
`configs/kernel/m8-kernel-5.4.302/path-a-5.4.302.config`. Its delta from the preservation config
is exactly:

- `CONFIG_BLK_CGROUP=y`;
- `CONFIG_CPUSETS=y`;
- `CONFIG_PROC_PID_CPUSET=y` (Kconfig consequence/required proc view);
- `CONFIG_NET_CLS_MATCHALL=y`;
- `CONFIG_NET_ACT_POLICE=y`;
- `CONFIG_NET_ACT_BPF=y`.

`BLK_CGROUP` and `CPUSETS` are required for this device's non-optional v1 blkio/cpuset mounts;
r1 failed before exec when blkio was absent and r2 physically proved this bounded correction.
`PROC_PID_CPUSET` supplies the proc cpuset membership interface expected by process-group code.
The three NET options are required for netd rate-limiting functionality and its release test; they
are not described as pre-init boot requirements.

`CONFIG_MEMCG` remains unset. The QPR0 `cgroups.json` marks the v2 memory controller optional, and
the 5.4-incompatible `memory_recursiveprot` mount option has a source fallback retry without it.
The newly visible blkio IOLATENCY/IOCOST/throttling policy choices remain unset. No speculative
5.10 subsystem is added.

## C. cgroups and task profiles

At r7, effective platform `cgroups.json` is byte-identical to r4. It declares non-optional v1
`blkio`, `cpu` and `cpuset`; a v2 root at `/sys/fs/cgroup`; required freezer; and optional memory
with activation depth 3. There are no source-shipped `cgroups_31.json` or
`task_profiles_31.json` files in this tag.

`libprocessgroup/util/util.cpp:190-212` loads descriptors in this order: platform, optional
`/etc/task_profiles/cgroups_${ro.product.first_api_level}.json`, then optional
`/vendor/etc/cgroups.json`, with later definitions replacing same-name controllers.
`task_profiles.cpp:825-849` uses the same order for platform profiles, API-specific profiles and
`/vendor/etc/task_profiles.json`. Unknown controllers/actions are warned and omitted; optional
attributes remain supported. The accepted vendor supplies neither override, as already proven in
the r2 exact-board audit.

The only r4→r7 task-profile change removes three compaction profiles; it adds no controller or
boot requirement. Therefore the r2 cgroup fix remains sufficient and no new QPR0 controller is
required beyond the separately classified netd traffic-control trio.

## D. APEX/bootstrap delta

This is a delta audit of the already-closed r1 APEX investigation:

- QPR0 `system/core/rootdir/init.rc:63-82` creates bootstrap linker configs, bind-mounts the
  bootstrap namespace, executes `apexd-bootstrap` synchronously, then runs
  `perform_apex_config --bootstrap` before later services.
- After `/data`, lines 715-733 restart full apexd; lines 999-1003 wait for `activated` before the
  normal APEX config pass. This preserves the ordering r2 already reached after its cgroup fix.
- `system/apex/apexd/apexd.cpp:170-211` selects i18n, runtime, tzdata, VNDK for the vendor's
  `ro.vndk.version`, and virt when `RELEASE_AVF_ENABLE_EARLY_VM` is true. `bp2a` sets that release
  flag true, matching the five-member r4 prototype bootstrap set.
- QPR0 `apexd_main.cpp:166` unconditionally uses `kDefaultConfig`, whose
  `mount_before_data=false`. The only release value for early data-APEX mounting is in
  `trunk_staging`, not `bp2a`; r7 does not carry r4's migration-mode selection in main.

The required runtime/VNDK31 bootstrap behavior is retained. There is no reason to restart APEX
debugging or alter the proven r2 cgroup boundary.

## E. VNDK, linkerconfig and legacy vendor compatibility

Official `prebuilts/vndk/v31` r7 peels to frozen commit
`1a059a5a203352d3e0c2fd3ccff5719cc37fc340`; its ARM v31 list still contains
`libaudioroute.so`. `system/linkerconfig` commit
`e6e748db0343684959fc49356f07e1793f96db85` retains the vendor default namespace and, when
`ro.vndk.version` exists, adds a `default -> vndk` link exposing the VNDK core/SP lists.
The vndk namespace searches `/apex/com.android.vndk.v${VENDOR_VNDK_VERSION}/${LIB}`.

The exact r4 offline closure already proved ARM32 VNDK31 `libaudioroute.so`, the generated vendor
namespace and all 1,769 ELF class/name dependencies against the accepted API-31 vendor. QPR0
retains these mechanisms and the v31 payload. No source rule forces retained vendor services to
become ELF64, and the QPR0 network loader explicitly continues ARM32 userspace on ARM64 TV.
Therefore the prior ARM32 offline assumptions remain valid for one build, subject to repeating
the same exact-board offline checks on the eventual r3 output.

## F. VINTF

QPR0 keeps `compatibility_matrix.6.xml` byte-identical to r4 (SHA-256
`3cb61405c9d65d5f2e428ff24556668d497a83b7330e711520c7a6661d2a3262`). Its build rule still
associates FCM level 6 with `kernel_config_s_5.4`; that config still says
`# CONFIG_NFS_FS is not set`.

The accepted vendor still needs the bounded device matrix entries for
`vendor.display.config@1.0::IDisplayConfig/default` and
`vendor.display.output.IDisplayOutputManager/default (@2)`. They remain device-specific accepted
HAL declarations, not a generic platform rewrite.

The r5/Path-A kernel inherits `CONFIG_NFS_FS=y`. Consequently the full exact VINTF result remains
exit 65 / **INCOMPATIBLE** solely for `NFS_FS`; the r2 counterfactual proved it passes with that
one bit unset. This is inherited from the device-accepted Android 12 BSP, is not known to cause
boot failure, and is not a new QPR0 architecture blocker. It is nevertheless a release-conformance
exception that must be removed or explicitly resolved before claiming a compliant release.

## G. SELinux

QPR0 `system/sepolicy/private/genfs_contexts:329` still owns
`genfscon fuseblk / u:object_r:fuseblk:s0`. The accepted API-31 vendor policy owns the identical
filesystem/path with its retained `vfat` label, so the split-policy duplicate found under r4 still
exists. The minimum bounded delta remains removal of that one platform line by
`0002-sepolicy-defer-fuseblk-label-to-api31-vendor.patch`; no wider policy copy or relabel is
justified.

A future r3 build must re-run exact split `secilc`. Historical boots were permissive, so neither
the old compile pass nor this source audit claims enforcement-ready platform/vendor behavior.

## H. TV/product composition

`device/google/atv/products/gsi_tv_base.mk` is byte-identical between r4 and r7 (SHA-256
`8ac914ec861407aafc11030a140358883f43ec93f31b1b6c1aad4378c9efc035`). It still supplies the
TV GSI system, system_ext/product composition, `TvProvision`, `LeanbackIME`,
`TvSampleLeanbackLauncher`, `PRODUCT_CHARACTERISTICS := tv`, and GSI release rules. QPR0 moves
the generic remote keylayout into `atv_system.mk` and removes obsolete TV service/client and
vendor batteryless defaults; these are bounded package/property composition changes inside the
same inherited base, not architecture blockers.

`device/generic/armv7-a-neon` changes only by adding a goldfish-opengl namespace for its emulator
product. The UBOX product does not inherit that mini-emulator file. Base system source still
ships `init.zygote32.rc` and defaults `ro.zygote?=zygote32` for a 32-bit primary product.

The Prototype A definition can therefore be ported with bounded changes:

1. place the existing `device/ubox/ceiling` product in an exact r7 tree;
2. change the release lunch suffix from `bp4a` to `bp2a` and use a new disposable r7 build number;
3. retain ARMv7-A NEON primary, no secondary ABI, `zygote32`, shipping API 31, extra VNDK 31,
   TV GSI base and pKVM off;
4. retain the exact two-entry display matrix and apply only the verified one-line r7 SELinux
   duplicate-ownership delta;
5. pair the future output only with the accepted vendor/hardware authority and Path-A 5.4.302
   config, then repeat AVB/LP/VINTF/linker/ELF/SELinux/APEX audits.

Do not use the retained WSL/r4 wrapper without first changing its `bp4a` assumptions. Do not
select the arm64 product or `zygote64_32` in r3.

## Exact proposed r3 contract and authorization boundary

**GO FOR PROTOTYPE A r3 BUILD** means a later, separately scoped source build may build exactly
one ARM32 Prototype A using:

- source tag `android-security-16.0.0_r7`, manifest commit
  `ebea28d151539ecf0730b1a4ab92ac33edc17ac9`, release `bp2a`, build
  `BP2A.250805.034`, API 36.0, SPL 2025-08-05;
- ARM32 primary/no secondary ABI/`zygote32`, shipping API 31 and VNDK 31;
- retained accepted vendor/product/vendor_dlkm authority and the physically accepted r5
  same-lineage 5.4.302 kernel/wireless contract;
- only the six tracked Path-A kernel config additions;
- exact two-HAL display matrix and one-line `fuseblk` platform deferral;
- no MEMCG, BTF, ringbuf, BPF link/batch, CAP split, tracing, IncFS, ARM64 graphics or mapper
  backport merely for feature parity.

The later build must remain offline until its output closes the same exact-board checks. This
audit authorizes no image build in the current task and no flash/physical test at all. Gate 2 can
be called PASS only after a later r3 runtime reaches and validates its intended boundaries.

## Audited project commits and decisive file hashes

| Project | r7 commit |
|---|---|
| `build/make` | `e780ae328060afca5ed007c34322bfa7ce9b4e60` |
| `build/release` | `ecaf883f0ecb92307aa38fd98bf79029b5855565` |
| `build/soong` | `4e8a4d55b99fce2bacf24b4942abf13d6cda2e12` |
| `packages/modules/Connectivity` | `5276e77d46a4e1f3121f7d2f651fc2185fa59342` |
| `packages/modules/UprobeStats` | `29fd11c92ed630721f946cf0ba57d80d11053b8d` |
| `system/netd` | `68859d33e9bfe9ddb1afdc282905c63339c1928d` |
| `system/bpf` | `4447acd742bf443f9088c300bd69f96ede8eaeb1` |
| `system/bpfprogs` | `cdb14b57cc698975b796224c507b4d15698b4788` |
| `system/core` | `68be0c2c0006a0740d0b1809abe4717308f90d15` |
| `system/apex` | `4c600506b4aceb0bb9f61bac84e9884d4b4d9b2b` |
| `system/sepolicy` | `d4a7f392598cee96d9479a8ac0f84259c19b043a` |
| `system/linkerconfig` | `e6e748db0343684959fc49356f07e1793f96db85` |
| `system/libvintf` | `2ef218d3586bbef90c2f0c14bbda901c7d60460a` |
| `system/incremental_delivery` | `c999e3e207ec7633a172d773dda162746b6eaf18` |
| `hardware/interfaces` | `b553275c84253b074a8532a6ff0f4406c43e606e` |
| `kernel/configs` | `e90ea709c3c2ec34bcfd7dca2ebec0bae287c91f` |
| `device/google/atv` | `28ec82d1e4f13072eb978f3e74335195aa7dfcc4` |
| `device/generic/armv7-a-neon` | `5be6c1b1d84a1f046329176d5da3368cb6547703` |
| `frameworks/base` | `0e92b8431dbcc5bc65dafc485fc0cef277df0644` |
| `prebuilts/vndk/v31` | `1a059a5a203352d3e0c2fd3ccff5719cc37fc340` |

Decisive r7 source SHA-256 values:

- Connectivity `NetBpfLoad.cpp`: `03d6adf9bf499cc23ef170dafa23a86c8a5ecb1e2c182dea940c0cdfba650254`;
- Connectivity `netbpfload.rc`: `b084ef36f4410b92ebf71ba6644baa989b84267b0d773661ecaebb7ea5a3c270`;
- netd `tests/kernel_test.cpp`: `6be1db941ba6d0bf83b4e6bb1d6e7376bc66d629110fdf2f93f18e6b97641697`;
- platform `cgroups.json`: `ab2ed667ff45958843fb0c6ee953a5512def0ae87470c4358aa9576a6a4b2e22`;
- platform `task_profiles.json`: `bee4c6181381d3e41c115475abcc3962e809a6fc2a97276e14c23db85e3e2ec9`;
- APEX `apexd.cpp`: `dd46d97231b5e1611f0d659573ea7303a74e34c14f2948fbb06da424c3615300`;
- init `rootdir/init.rc`: `133923deca1bb776b83856eba406441849fb1903f8aa2f96940183ae976e205d`;
- FCM-6 XML: `3cb61405c9d65d5f2e428ff24556668d497a83b7330e711520c7a6661d2a3262`;
- FCM-6 `s/android-5.4/android-base.config`:
  `26ea5c3c19e3547e8d1a74415c60e6ab2678230488d26baeb8aa9f07f905676f`;
- platform `private/genfs_contexts`: `8631ad087da5e4e2e81ce3a179b9d9ddf31532e9f4d3b6de32bd6d177512f3f1`;
- IncFS `incfs.cpp`: `c5fbf935b1f6b2cd5e2fdafe0327c132ab83666e6344b0b5137244e377c4e1e8`.
