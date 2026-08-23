# M8 Linux 5.4.302 kernel checkpoint r1

状态：**OFFLINE CHECKED / GO FOR ONE SEPARATELY AUTHORIZED ANDROID 12 KERNEL-ONLY PHYSICAL VALIDATION**。这不是 Android 16 Prototype A r3；没有修改 Android 16 source baseline，没有启动 Prototype B，没有刷写或启动设备。Gate 2 继续 **CLOSED**。

## Decision

本 checkpoint 对“retained H616/Allwinner Android BSP 能否从 Linux 5.4.125 同 lineage 移到最终 5.4.302”给出限定 **GO**：source integration 可精确重放，硬件关键 vendor tree 被保留，accepted 22-module 合同可针对 5.4.302 完整重建，kernel 与唯一 Android 12 kernel-only candidate 均通过强离线审核。因此它足以支持一次另行明确授权、UART-first 的 Android 12 kernel-only 物理验证。

GO 不等于硬件兼容 PASS。Display/HDMI、Mali、Cedar/VPU、audio、Wi-Fi/Bluetooth、Ethernet、USB、IR、thermal/DVFS、suspend/wake 与 OP-TEE 只能由后续物理测试证明；旧 5.4.125 modules 也不能直接加载到 5.4.302，候选必须使用本次匹配重建的完整 22-module set。

## Exact lineage and integration strategy

| Source | Exact identity |
|---|---|
| Retained Orange Pi vendor | `https://github.com/orangepi-xunlong/linux-orangepi.git` commit `9ab7a758149d3c9b721878a0c18b3f9c5d6c93e6`, tree `d37d590a1e61c8e099e72170bf36e54091aa4820`, release `5.4.125+` |
| Upstream v5.4.125 | annotated tag object `e9351d7f0fb2ce8306234f07feb0a7598158bff4`, commit `3909e2374335335c9504467caabc906d3f7487e4` |
| Upstream v5.4.302 | annotated tag object `8ffcca9e0f269ee86a682eaae7e49c5efae79fe9`, commit `9e3157c56ec7917e6a80ea53a8bd752e0037f2cb` |
| Android common base | `android12-5.4` immediately after its v5.4.125 merge: `6cb0d5ef8b388d0249d96060e9ef31b466f88c7d` |
| Android common target | `2443acb8671f5eaeac985e70446726278ed014ae`, exact 5.4.302 and containing upstream v5.4.302 |
| Reproducible integration | synthetic vendor parent `31364553e3cb9171d767cbf0c5c1af4e0198d5d8`; merge commit `027ef79e8facb73cb2419b4a08c0bd3f13a2206e`; tree `b328c32712d65f8da98e013bc74944d68c05552b` |

The Orange Pi repository is a seven-commit BSP import rooted at `9da1b18174fe5dcd773207bf9b884e0e87f7e8d1`; it has no Git merge-base with either upstream v5.4.125 or v5.4.302. Its first BSP snapshot is `2ef19d18ce29fd6d8e77f89367480f65616da2df` (`Linux5.4 for H618`). A direct rebase therefore has no meaningful ancestry, while reconstructing 4,603 vendor-delta files on vanilla v5.4.302 would maximize opportunities to lose Android/common and Allwinner behavior.

The selected bounded hybrid makes the exact vendor tree the `ours` side of a synthetic three-way merge, uses Android common's v5.4.125 point as the base, and merges the Android common v5.4.302 target as `theirs`. This preserves the Android 12 5.4 kernel patch set as well as upstream stable changes and exposes only the 384 paths where the vendor delta and the 5.4.125→5.4.302 update overlap. `scripts/integrate-m8-kernel-54302.sh` independently replayed the operation in 17 seconds and reproduced the exact commit/tree above.

The upstream v5.4.125→v5.4.302 range contains 17,753 commits and 9,585 changed paths; the Android-common range contains 19,181 commits and 9,713 changed paths. No blind `git rebase` or vendor-source overwrite was performed.

## Vendor BSP inventory and conflicts

The pre-change machine inventory found 4,603 vendor-delta files: 4,056 added, 494 modified and 53 deleted relative to Android common 5.4.125. It classified 434 source-level exported symbols inside hardware-critical vendor delta. The full generated record remains in ignored build evidence; its stable SHA-256 is `B2381BE4D674CB64DEA4D1419C74805040F8E5FBFF60E91C5F1346DB5151AAF0`. The tracked summary is `configs/kernel/m8-kernel-5.4.302/checkpoint.json`, and `scripts/inventory-m8-kernel-54302.py` regenerates the per-file inventory.

| Hardware-critical class | Vendor-delta files | 5.4 update overlaps | Result |
|---|---:|---:|---|
| H616/sun50iw9 DTS and bindings | 36 | 0 | Exact vendor DTS subtree preserved |
| SUNXI display/HDMI/framebuffer/DRM | 716 | 0 | Exact vendor display subtree preserved |
| Mali-G31 / mali_kbase | 278 | 0 | Exact `mali-bifrost` subtree preserved and rebuilt |
| Cedar/VPU/VIN/media | 247 | 0 | Exact Cedar/VIN subtrees preserved |
| G2D/DMA heaps/ION/vendor memory | 53 | 8 | Critical G2D/DI/gralloc/DRM-heap trees preserved; generic stable overlap audited |
| Apollo/SUNXI audio | 60 | 0 | Vendor audio delta preserved |
| AIC8800 wireless/Bluetooth | 94 | 0 | Vendor tree preserved; exact accepted newer module source separately pinned |
| Ethernet | 6 | 0 | Vendor implementation preserved |
| USB host/device | 47 | 7 | SUNXI USB subtree preserved; generic gadget/common fixes carried |
| IR/rc-core | 9 | 1 | Stable rc-core plus accepted repeat/keymap delta rebuilt |
| Thermal/DVFS/clocks/regulators | 49 | 3 | Vendor cpufreq semantics preserved with one stable cleanup merge |
| Suspend/wake | 3 | 0 | Vendor delta preserved |
| TEE/OP-TEE vendor delta | 0 | 0 | No distinct vendor delta; generic TEE/OP-TEE source/config retained and TEE payload unchanged |
| Block/device-mapper/AVB/filesystem | 3 | 3 | Maintained Android-common dm-verity/generic implementations selected |

There were 46 textual conflicts: 31 use the maintained upstream/Android-common stable implementation, 12 preserve the vendor implementation, and 3 require semantic merges. The three semantic cases are:

- `drivers/char/Kconfig`: 5.4.302 RNG/Kconfig content plus all seven SUNXI vendor Kconfig includes;
- `drivers/cpufreq/sun50i-cpufreq-nvmem.c`: complete sun50iw9/sun50iw10 efuse/bin behavior plus the stable allocation cleanup in vendor error paths;
- `drivers/pinctrl/sunxi/pinctrl-sunxi.c`: complete vendor hardware-type, power-source, regulator and secure-pin model plus only the applicable stable `krealloc` failure fix.

The exact per-path classification is in `conflict-resolutions.json`. No conflict was resolved merely to compile. The two vendor-added generic pstore files changed by the target are superseded by the maintained common implementation; the hardware-specific subtrees remain byte-identical to the retained tree.

Accepted external project changes were reapplied after integration: `rc-main-repeat.patch` (357 bytes / `70A316DA67274FC2ED2584CCC090DC4282E6D740FFA04EE3C3B47DA2CD266549`) and generated ff40 keymap input (5,358 bytes / `474C2F842E71D45282740603E3B13150242A8E0DAC9718373222CD0251C62D7F`), with `CONFIG_SUNXI_MULTI_IR_SUPPORT=n`. Exact accepted XR819/wireless-switch source is pinned to `Mini-LinuxPC-Pro` commit `5bcbf22cdbc3f6ff7c5633447b0b0f8dbf6bfca1`; accepted AIC8800 `20221108-004` source is pinned to `GammaKinematics/sunxi_kernel` commit `abfe04920992577c71a4180a8480a4a774965c76`; accepted vendor RTLwifi source is the exact `8d1d70ea...` subtree from the retained commit.

## Effective configuration contract

The primary build starts from the Image-extracted accepted Android 12 config, 140,888 bytes / `9D3DF7457F0921E1E5983ADB2DBD36A89042CE70BB28EBFEADA7FD5E633D677C`. `olddefconfig` on 5.4.302 produces the preservation config, 141,140 bytes / `FA73240A16B52569D28EADF4AFD59834F05AEDD6B69F573863A611B3E359A75D`. The exact configs, unified diff and machine delta are tracked under `configs/kernel/m8-kernel-5.4.302/` and the builder compares its regenerated outputs byte-for-byte.

All 32 effective changes are accounted for:

- `ANDROID_KABI_RESERVE=y` and `ANDROID_VENDOR_OEM_DATA=y` are newly available Android-common default ABI/OEM padding. They do change internal structure padding, but no old binary module is reused: all 22 modules are rebuilt against the same layout. No UAPI is enabled.
- `ARM64_ERRATUM_1742098=y` and `ARM64_ERRATUM_3194386=y` are new default stable ARM64 erratum mitigations. CPU matching limits their runtime effect; retaining stable mitigations wins over suppressing them to mimic an older `.config`.
- `CC_HAS_ASM_GOTO_OUTPUT=y` and `CC_HAS_AUTO_VAR_INIT_ZERO_ENABLER=y` are clang capability probes, not enabled subsystems.
- `CRYPTO_LIB_BLAKE2S_GENERIC=y` is the refactored generic fallback for the existing BLAKE2s/WireGuard library path; old disabled parent `CRYPTO_LIB_BLAKE2S=n` disappears. `LIB_MEMNEQ=y` and `XOR_BLOCKS=y` are internal helpers selected by already-enabled consumers, not new user-visible hardware.
- `INET_TABLE_PERTURB_ORDER=16` is the new default RFC 6056 source-port table parameter. `MITIGATE_SPECTRE_BRANCH_HISTORY=y` is the stable default branch-history mitigation.
- The new `/proc/pid/mem` choice resolves to `PROC_MEM_ALWAYS_FORCE=y`, with `PROC_MEM_FORCE_PTRACE=n` and `PROC_MEM_NO_FORCE=n`, explicitly preserving traditional accepted behavior.
- `SURFACE_PLATFORMS=y` only exposes the Microsoft Surface submenu and adds no code because every child driver remains disabled.
- Newly visible `BATTERY_RT5033=n`, `BPF_UNPRIV_DEFAULT_OFF=n`, `LEDS_CLASS_MULTICOLOR=n` and `NVME_TCP=n` remain disabled; no new device class is enabled and the accepted unprivileged-BPF default is not silently changed.
- Disabled/obsolete symbols removed or made invisible are `DECNET`, `DRM_MXSFB`, `FORTIFY_SOURCE` (already `n`, and unavailable with this clang in the updated Kconfig), `MFD_TI_AM335X_TSCADC`, `NET_CLS_RSVP`, `NET_CLS_RSVP6`, `NET_CLS_TCINDEX`, `NET_SCH_CBQ`, `NET_SCH_DSMARK`, `NVM` and `PSTORE_BLK`; none was enabled before. `REFCOUNT_FULL=y` disappears because the later stable refcount implementation makes the checked behavior unconditional rather than optional.

The main Android 12 preservation Image does **not** enable Path-A-only additions. A separate `olddefconfig` check produced `path-a-5.4.302.config`, 141,228 bytes / `2A159B7EAF3ED96988F169A022A927B440A5D786F20C490D7AF004760F4B4F29`, and proves the bounded additions are available:

```text
CONFIG_BLK_CGROUP=y
CONFIG_CPUSETS=y
CONFIG_PROC_PID_CPUSET=y
CONFIG_NET_CLS_MATCHALL=y
CONFIG_NET_ACT_POLICE=y
CONFIG_NET_ACT_BPF=y
```

`PROC_PID_CPUSET` is selected by CPUSETS. The newly visible policy options `BLK_DEV_THROTTLING`, `BLK_CGROUP_IOLATENCY` and `BLK_CGROUP_IOCOST` remain `n`. This check proves configuration closure only; it does not switch Android 16 to r7 or build r3.

## Reproducible build result

The clean native-GCP build used AOSP `clang-r416183b1` / clang 12.0.7, `-j8`, the preservation config, and source commit/tree above. Main compilation took 639 seconds; the deterministic sequential external-module finalization took 64 seconds, total 703 seconds. The build host had no swap. Sampled available RAM stayed above 56,826,608 KiB and `/work` free space above 164,776,160 KiB (about 157.1 GiB); maximum sampled load was 9.16. There was no OOM or filesystem/I/O failure.

| Build output | Value |
|---|---|
| Kernel release | `5.4.302+` |
| ARM64 `Image` | 23,492,616 bytes / `9B781ABEA51DEF9AE1FEBB9011CFA630AC267C794FBA0E066674F0EAE2509DCC` |
| Modules | 22, all `5.4.302+ SMP preempt mod_unload modversions aarch64` |
| DTB build output | one `sun50i-h616-orangepi-zero3` DTB; it is build evidence only and is not inserted into the exact-board candidate |
| Accepted board DTBO | Preserved byte-for-byte in the outer image |
| Offline audit | `PASS_WITH_PHYSICAL_VALIDATION_REQUIRED` |

Eleven distinct warnings remain: vendor PWM possible-uninitialized, GMAC/IR unused variables, four XR819 source warnings, one maintained TCP pointer-type warning, a static-symbol diagnostic, vendor DTC duplicate-label output, and a submake jobserver warning. They are recorded, not hidden. The first build invocation omitted the vendor NAND `KERNEL_SRC` export and was corrected before compilation. The otherwise successful parallel main build then exposed the vendor Mali top-level make race (`llvm-nm` observed five objects during concurrent clean/build); running the identical already-compiled source through the vendor steps sequentially succeeded with zero final errors. These are classified host/invocation defects, not unresolved source or ABI failures.

## Offline BSP-preservation audit

| Contract | Offline evidence | Boundary |
|---|---|---|
| ARM64 / boot | ARM64 Image magic, embedded exact preservation config and release verified; accepted boot header v3, cmdline, ramdisk and 64 MiB partition retained; new AVB hash footer verifies | Does not prove CPU/interrupt/clock runtime |
| DTS/DTB/DTBO | Entire vendor `arch/arm64/boot/dts/sunxi` tree is byte-identical; accepted outer DTBO is byte-identical | No exact-board DT probe/run yet |
| Built-in hardware drivers | Required ARCH_SUN50IW9, display/HDMI, Cedar, G2D/heaps/ION, Apollo audio, Ethernet, thermal/DVFS, TEE/OP-TEE, DM/verity and suspend config/source contracts checked | Probe order, timing and hardware behavior require boot |
| Module ABI | Exact 22 filenames, module names, dependencies, aliases, firmware/version/license metadata and exported symbol names retained; every new import CRC resolves against the exact 5.4.302 `Module.symvers` set | Export CRC values legitimately change; old 5.4.125 modules are not reusable |
| Mali | Exact vendor `mali-bifrost` source preserved; `mali_kbase.ko` and DMA test exporter rebuilt; userspace-facing source is unchanged | GPU init, memory coherency, EGL/HWC require physical validation |
| Cedar/VPU/display/audio | Critical source trees/UAPI implementations preserved and compile in the same Image | Decode, HDMI mode/audio routing and suspend interactions remain physical gates |
| Wireless | Exact accepted AIC8800 version, XR819 and vendor RTLwifi implementations rebuilt; dependency/alias/firmware/export-name contracts match | SDIO power sequencing, firmware load and RF runtime unproven |
| USB / IR | SUNXI HCI modules and accepted rc-core repeat/keymap source rebuilt with exact metadata | Host enumeration and remote repeat behavior unproven |
| Thermal/DVFS/suspend/wake | Vendor implementation preserved; only reviewed stable semantic fixes applied | Requires soak and suspend/resume test |
| TEE/AVB | TEE/OP-TEE config/interfaces retained; bootloader, TEE, vbmeta, vendor_boot, DTBO and security/factory payloads unchanged; boot and vendor_dlkm AVB verify | SMC/secure-world interaction cannot be established offline |
| Path-A cgroup/BPF | Six required cgroup/netd options close cleanly in the separate config | No A16 QPR0 BPF program was built or loaded in this checkpoint |

The accepted Image reports `5.4.125+`, while its accepted vendor_dlkm modules encode `5.4.125`; that pre-existing vermagic mismatch is not carried forward. The new Image and all new modules consistently encode `5.4.302+`.

## Android 12 kernel-only candidate

`m8-kernel-5.4.302-r1` uses frozen device-accepted `m8b-remote-r1` as its userspace/vendor base. It changes no `system_a`, `vendor_a` or `product_a` bytes. It replaces the boot kernel and all 22 matching modules inside the fixed-size `vendor_dlkm_a`, regenerates only their boot/vendor_dlkm AVB data and the containing sparse super, then updates the IMAGEWTY checksum companions.

| Artifact | Size | SHA-256 |
|---|---:|---|
| `out/candidates/m8-kernel-5.4.302-r1/x12-m8-kernel-5.4.302-r1.img` | 1,031,739,392 | `C93FC8A54391E091E0F95CFE63E4F6DA9AE90D55AA0163D91D42586B48BFEE2B` |
| `boot.fex` | 67,108,864 | `338CB4048796E213698585E035D8807D84381324163C19AA939BD8D6BFDDCD2C` |
| `super.fex` | 851,940,812 | `913CDED66A315EBD401F042037A2DEE4660209D90AE56C2C45E476BB40742957` |
| `vendor_dlkm_a.img` | 6,680,576 | `5B6FED8C5709F994450A2B3177A67E2F1BA94C17C170628F422A1EECE8BEC199` |

IMAGEWTY verified 12/12 checksum-governed partitions. Boot AVB hash and vendor_dlkm AVB hashtree/FEC both verify. The sparse super converts back to a byte-exact raw candidate super; LP metadata 10.2, three slots, `virtual_ab_device` flag, group/partition sizes and all extents remain exact. The changed vendor_dlkm occupies the same single 6,680,576-byte extent; `system_a` (`5992972F...056B`), `vendor_a` (`BB91A8B7...929A`) and `product_a` (`6E2D0AF3...8974`) are byte-preserved. The rebuilt ext4 filesystem passes `e2fsck`, retains modes/uid/gid/timestamps/SELinux labels and all non-module files/module metadata, and has one 4 KiB block free. It is read-only at runtime, but the one-block margin is explicitly a physical-validation risk, not hidden headroom.

The boot ramdisk remains 12,752,798 bytes / `BE091606E285405F9FF018AE4E4BB286A380682280E72DD056B4FEB1F120A328`. Outer changes are exactly `boot.fex`, `super.fex`, `Vboot.fex` and `Vsuper.fex`; the other 46/50 payloads—including bootloader, TEE, vendor_boot, DTBO, vbmeta, vbmeta_system, GPT-related payloads and factory/security content—are byte-preserved. Accepted `m8b-remote-r1`, Test8r2 rollback and original source inputs remain untouched.

Candidate assembly took 101 seconds. Available RAM stayed above 64,186,932 KiB and `/work` free space above 147,783,332 KiB; maximum sampled load was 1.15. Failed packaging attempts are retained as local evidence and were limited to an AOSP `fec` PATH omission, AVB's descriptor-filename verification rule, and `lpdump` not directly accepting sparse input. The final builder pins the AOSP host-tool PATH, verifies `vendor_dlkm.img` under its descriptor name, and proves sparse-super integrity by exact `img2simg`→`simg2img` round trip.

Final repository validation independently regenerated the 424,597-byte vendor-delta inventory
and the 39,373-byte offline audit byte-for-byte at their recorded SHA-256 values. The full
repository suite completed 80 tests successfully; 25 expected skips cover absent ignored
historical artifacts, while all five 5.4.302 checkpoint tests—including hashes of this local
candidate—ran and passed.

## Physical result

The user separately authorized and completed the r1 Android 12 physical validation. Linux
5.4.302 boots, Android reaches `sys.boot_completed=1`, and HDMI/UI, remote, Ethernet and ADB
pass. Wi-Fi fails reproducibly after `mmc2` enumerates the SDIO card, the BSP matches
`aic8800d`, reports U04 and programs `Set SDIO Clock 66 MHz`:

```text
cmd timed-out
tkn[...] result:-4 cmd:1037 - reqcfm(1038)
wifi start fail
aicbsp_sdio_remove
```

The AIC BSP/fdrv/btlpm modules and firmware payloads are present. The first wireless boundary
is firmware START_APP confirmation, not Android Wi-Fi HAL/framework or a simple missing-file
failure. No local raw capture was supplied with this physical result, so this record identifies
the user-provided observations without inventing a log hash.

r1 is therefore **PARTIAL PHYSICAL PASS / WIRELESS FAIL**, not a complete hardware-preservation
PASS. Its source, artifact and prior offline conclusions remain historical inputs; it is not
rebuilt or overwritten for the follow-up.

## Remaining gate

The exact next action is **not** A16 r3. One offline-only `m8-kernel-5.4.302-r2` diagnostic
changes the pinned AIC runtime SDIO request from 70 MHz (rounded to about 66.7 MHz) to 50 MHz
while preserving this r1 Image, boot/DT/userspace and 21 other module bytes. It requires a new
explicit authorization before any physical test. If the same 1037→1038 timeout remains, the
clock hypothesis is rejected and the next work is a systematic Linux 5.4.125→5.4.302 generic
MMC/SDIO/AIC interaction diff. Gate 2 remains closed.
