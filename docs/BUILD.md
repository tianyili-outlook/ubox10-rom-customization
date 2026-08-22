# M8 build guide

## Product boundary

M8A uses ARM32 Android 12 TV system/product content with the stock device-specific stack. It preserves boot, kernel, vendor, vendor_dlkm, DTBO, TEE, graphics, media, DRM, wireless, and the established recovery path.

Stock fstab and LP metadata have no `system_ext` logical partition. The build therefore merges the AOSP system_ext filesystem at `/system_ext` inside `system_a`, preserves `/system/system_ext -> /system_ext`, replaces `product_a`, and keeps the four-partition LP schema.

| Logical partition | Bytes |
|---|---:|
| system_a | 1651167232 |
| vendor_a | 119066624 |
| product_a | 272629760 |
| vendor_dlkm_a | 6680576 |
| A-group free | 1163292672 |

## Locked inputs

| Input | Locked value |
|---|---|
| AOSP branch | `android12-release` |
| `device/google/atv` HEAD | `3ce48358b7e06ab1f1a1b713fb0f285aaa0983ca` |
| Manifest HEAD | `8e7a52179c1704bc445f83efde08a6025acbf358` |
| Local AOSP output | `/home/tianyi/ubox10-aosp/out/target/product/ubox10` |
| Stock container | `x12-1024.img`, 2018890752 bytes, SHA-256 `371A653604618E8B78786F279EA6F64E5D1028B430C9B41F330B08456A264065` |
| Preferred rollback | Test8r2, 2005954560 bytes, SHA-256 `6A52F3388E9ABF6AFA8A701CFD7198FE6C0090F16531F6E3BD3949E760892EC8` |

The AOSP tree, stock image, extracted payloads, rollback image, and candidate outputs are local ignored inputs. A Git clone alone cannot rebuild the current candidate chain.

## Candidate chain

The original M8A r1-r13 chain established the bootable Android 12 TV product and remains preserved for provenance. `m8b-remote-r1` is the current device-accepted baseline (**REMOTE PASS**, inheriting **IME PASS / AUDIO PASS**); its direct predecessor is accepted `m8b-ime-r1`. This acceptance closure does not change the build architecture.

Run from the repository root on the verified Windows + WSL environment:

```powershell
python scripts/prepare-candidate-inputs.py
python scripts/build-m8a-candidate.py
python scripts/build-m8a-r2-candidate.py
python scripts/build-m8a-r3-candidate.py
python scripts/build-m8a-r4-candidate.py
python scripts/build-m8a-r5-candidate.py
python scripts/build-m8b-audio-r1-candidate.py
python scripts/build-m8a-r6-candidate.py
```

The early r1-r6 stages are intentionally retained because each stage hash-locks and consumes its predecessor:

| Stage | Change |
|---|---|
| r1 | Build ATV system/product, merge system_ext, rebuild LP/AVB/IMAGEWTY |
| r2 | Add ext4 metadata image and download-map entry |
| r3 | Repair dlinfo CRC |
| r4 | Add VFAT media_data image and descriptor |
| r5 | Replace top-level vbmeta with keyless verification-disabled metadata |
| r6 | Restore stock interleaved A/B LP table order |

Candidate configs under `configs/candidates/` are the machine-readable sizes, hashes, geometry, and predecessor contracts. Rebuilt ext4/super/container bytes are not guaranteed bit-for-bit reproducible; acceptance is based on locked inputs, structural checks, preservation audits, and the recorded final artifact hash.

M8B r1-r5 preserves the ARM32 userspace and hardware-facing vendor stack while replacing the legacy `multi_ir → uinput` remote path with native kernel rc-core. r5 is device accepted.

The ubox10 AOSP source product omitted `BOARD_VNDK_VERSION := current` and did not include `com.android.vndk.current`; the original AOSP `system` output therefore lacked the VNDK APEX before M8 assembly. `m8b-audio-r1` uses `configs/candidates/m8b-audio-r1.json`, `scripts/build-m8b-audio-r1-candidate.py`, and `scripts/import-m8-test8r2-vndk-apex.sh` to copy the hash-locked Test8r2 `/system/apex/com.android.vndk.current` subtree into an r5 system staging copy with metadata intact. It does not modify vendor, boot, audio XML, DTS or the accepted input stack.

For the local input milestone, apply `configs/aosp/m8b-ime-r1-leanback-ime.patch` to the locked AOSP tree and run `m LeanbackIME -j4` plus `m productimage -j4`. `scripts/build-m8b-ime-r1-candidate.py` consumes the locked AOSP product/APK and accepted `m8b-audio-r2`, preserves the accepted product `build.prop`, verifies that the filesystem delta is only `/app/LeanbackIME/**`, `/app` link count and the attributable NOTICE update, signs product AVB, rebuilds the same LP geometry, and rejects any system/vendor/vendor_dlkm change. Build with:

```powershell
python scripts/build-m8b-ime-r1-candidate.py
```

LeanbackIME declares itself default in its standard input-method metadata, so Android 12 can enable/select it when no prior IME exists. Fresh-data automatic selection and physical TV use passed; separate reboot persistence was not exercised and was accepted as non-blocking. No Remote Service or proprietary APK is part of `m8b-ime-r1`.

For `m8b-remote-r1`, copy the tracked text sources in `configs/aosp/m8b-remote-r1/` to `/home/tianyi/ubox10-aosp/device/ubox/ubox10/remote/`, place the ignored donor `work/preinstall_apks/AndroidTvRemoteService-5.2.473254133.apk` there as `AndroidTvRemoteService.apk`, and apply `configs/aosp/m8b-remote-r1-integration.patch` after the LeanbackIME patch. The donor must be exactly 3817484 bytes with SHA-256 `9D1B5C5EF0E293F8ED17C26E8F62DE661ACC7F2DDC2AAA8EF23E4CABE430B973`; it is never committed or redistributed. Then run from the locked AOSP tree:

```bash
source build/envsetup.sh
lunch ubox10-userdebug
m systemimage -j4
m systemextimage -j4
```

The inherited ATV product already supplies `com.android.media.tv.remoteprovider`, its shared-library XML, the TvRemoteProvider framework bridge and television/leanback features. The new normal modules add only the presigned privileged donor, its exact privapp allowlist, a CONNECT-only default-permissions file, and the source-built system_ext static RRO. `scripts/build-m8b-remote-r1-candidate.py` hash-locks those outputs, verifies donor signature/manifest/services/library and RRO resources, and installs the four generated files into a staging copy of accepted `m8b-ime-r1` system. It rejects every unrelated filesystem change and requires product/LeanbackIME, vendor and vendor_dlkm to remain exact. Build with:

```powershell
python scripts/build-m8b-remote-r1-candidate.py
```

The result is `out/candidates/m8b-remote-r1/x12-m8b-remote-r1.img`, 1031723008 bytes, SHA-256 `F3B09E5565AC4ED4E5EE326D392622E7B036A8519B8444B966E77CC4751B814A`. Only logical `system_a` changes; the outer replacements are `super.fex` and `vbmeta_system.fex` plus their generated V companions. The candidate is not device accepted until the explicit physical sequence in `docs/DEVICE_TEST.md` passes.

## Android 16 Architecture Ceiling Gate 1

Prototype A is a standalone ARM32 Android 16 TV system-image experiment, not an M8 candidate or firmware package. Its locked source is `android-16.0.0_r4` / `BP4A.251205.006`, manifest commit `15128c9e27cfa599c48d294babd39286ee8f1426`, pinned manifest SHA-256 `4E8BEB5D1B590DFF3D631B1DBB957138DBDA4E608A3183C625683DA4BC84918F`. Copy `configs/aosp/architecture-ceiling-a16/device/ubox/ceiling/` into the same path in the clean AOSP tree and verify it byte-for-byte before building.

The verified native-Linux procedure is:

```bash
cd /work/src/ubox10-a16-ceiling
export OUT_DIR=out-ceiling
export BUILD_NUMBER=DISPOSABLE_CEILING_R4
unset SOONG_GOMEMLIMIT GOMEMLIMIT
source build/envsetup.sh
lunch ubox10_ceiling_arm-bp4a-userdebug
m -j8 systemimage
```

`OUT_DIR` must remain the relative value `out-ceiling`. On the verified 62.8 GiB GCP host, do not use the WSL cgroup/taskset/swap wrapper or apply the legacy `SOONG_GOMEMLIMIT` patch. The successful run produced only `out-ceiling/target/product/generic/system.img`; it did not build boot, vendor, product, system_ext, super, userdata or an Allwinner outer image. The exact result and offline evidence are in `docs/m8/STATUS.md` and `docs/m8/research/architecture-ceiling-study.md`. Exact-device integration is the separate, completed candidate step below; it does not alter or rerun Gate 1.

## Android 16 Prototype A exact-board candidate

Do not rebuild accepted Gate 1. On the GCP host, the candidate builder consumes its exact hash-locked `system.img`, the verified accepted inputs under `/work/ubox10-a16-prototype-a-inputs/verified/m8b-remote-r1/`, and the read-only accepted outer image `/work/ubox10-a16-prototype-a-inputs/incoming/x12-m8b-remote-r1.img`. The input and output contracts are in `configs/candidates/a16-prototype-a-r1.json`.

From the repository root, with no existing final candidate directory, the retained construction command is:

```bash
python3 scripts/build-a16-prototype-a-r1-candidate.py --keep-failed
```

For long execution, wrap that command in a detached tmux session and redirect stdout/stderr plus an explicit exit-status file under `/work/build-logs/`; do not depend on the frontend connection. The builder performs no ADB, fastboot, PhoenixCard, FEL or other physical action. It refuses to overwrite an existing final candidate, verifies every accepted input before writing staging, and leaves the accepted outer image unchanged.

The builder materializes exactly two tracked compatibility inputs in a copy of Gate 1 system: the two-HAL device matrix and the one-rule SELinux patch. It preserves filesystem metadata, signs system/vbmeta_system with the established project test key and rollback index/location, inserts system into the exact accepted LP extent, validates all protected logical hashes, and repacks the accepted IMAGEWTY container with 46/50 payloads preserved. Full exact VINTF is accepted by the audit harness only when its terminal error is the single recorded inherited `CONFIG_NFS_FS=y` deviation; any additional config or HAL error fails closed.

The verified result is `out/candidates/a16-prototype-a-r1/x12-a16-prototype-a-r1.img`, 1,261,038,592 bytes, SHA-256 `A034C8193236C93746E5962CB3E7F26A1D56CEC1435D5AD9D95F653B60BEBD83`. It is an offline-checked candidate, not flash authorization. See `docs/m8/candidates/a16-prototype-a-r1.md` for the exact preservation and runtime boundary.

### Prototype A r2 cgroup kernel candidate

The r1 devkmsg result proves a pre-exec process-group failure. Do not rerun Gate 1 or rebuild r1 system/APEX/LP. `configs/candidates/a16-prototype-a-r2.json` pins the r1 outer input, Orange Pi kernel source commit `9ab7a758149d3c9b721878a0c18b3f9c5d6c93e6`, AOSP `clang-r416183b1`, the retained rc-core patch/keymap, exact base kernel config, and the only enabled config delta: `CONFIG_BLK_CGROUP=y`, `CONFIG_CPUSETS=y`, and Kconfig-generated `CONFIG_PROC_PID_CPUSET=y`. The builder fails if `olddefconfig` changes any other effective option; newly visible blkio throttling/I/O-cost policy symbols must remain disabled, and `CONFIG_MEMCG` remains disabled.

The verified GCP image lacks system-installed `libssl-dev` and `bc`, and only permits passwordless sudo for the final poweroff. Prepare these host-only tools without sudo under `/work/toolchains`: Ubuntu `libssl-dev_3.0.13-0ubuntu3.12_amd64.deb` SHA-256 `9A5CF7BC8E876EF4498DDF0180B6FAFE0E52C2A8DA2F06F8BC78C2A6FC92EC58`, matching `libssl3t64` `libcrypto.so.3` SHA-256 `1451ACEEC262C3338052FA77542EB971D4BA311C6BF12D9AA70D0B56ACA942F9`, and `bc_1.07.1-3ubuntu4_amd64.deb` SHA-256 `CB85D5929476088533B3C5E1DB2DE5AB4593A69FA54243710F762197DBAEA60D`. The expected extracted roots are `/work/toolchains/ubuntu-libssl-dev/root` and `/work/toolchains/ubuntu-bc/root`; package downloads remain outside Git.

With the pinned kernel checkout at `/work/tmp-orangepi-kernel-exact` and toolchain at `/work/toolchains/aosp-clang-android12/clang-r416183b1`, run the candidate builder from the repository root in detached tmux with persistent stdout, resource log and explicit status file:

```bash
python3 scripts/build-a16-prototype-a-r2-candidate.py --keep-failed
```

The builder uses `-j8`, repacks the accepted boot header/ramdisk/hash-footer contract, and replaces only `boot.fex` plus its generated `Vboot.fex` companion in the accepted r1 outer image. All other 48/50 payloads are byte-preserved. It performs IMAGEWTY and standalone boot AVB verification, exact cgroup/config checks, read-only ext4 checks and full exact VINTF with unprivileged `debugfs rdump`; linker, ELF, SELinux, APEX and LP results are inherited only after proving their r1-containing partitions byte-identical. The output is never flash authorization. If a host-only interruption occurs after kernel/outer artifacts are complete, `--resume-stage` may continue the same exact staging directory without recompiling; it refuses incomplete or external staging paths.

The verified result is `out/candidates/a16-prototype-a-r2/x12-a16-prototype-a-r2.img`, 1,261,038,592 bytes, SHA-256 `114DF8677CD6984EB1431377723EDF61C80ACF26C15D8770BAE47DCFE7D1B6D0`. Its boot image is 67,108,864 bytes / `4F0DB0070E294DEA93319F4B21335E6725DBB7B70066E7C1E6BF55CFEB09C10C`; kernel is 23,232,520 bytes / `5D7D7F84A8E3CBCC4A4AF78A9EB4DECAC846E62BA4C681E85B438B69B196EBF3`. See `docs/m8/candidates/a16-prototype-a-r2.md`; the output remains offline-only and does not authorize flashing.

## Linux 5.4.302 same-lineage BSP checkpoint

This is an isolated Android 12 kernel-preservation procedure, not an Android 16 build. It
never writes the accepted Orange Pi checkout or accepted firmware inputs. The tracked contract
under `configs/kernel/m8-kernel-5.4.302/` pins the retained vendor tree, Android-common
5.4.125/5.4.302 anchors, all 46 conflict decisions, semantic resolutions, exact effective
configs and expected integration commit/tree. Use a separate clean repository containing all
three pinned Git objects; the integration script refuses a dirty tree and reproduces commit
`027ef79e8facb73cb2419b4a08c0bd3f13a2206e`, tree
`b328c32712d65f8da98e013bc74944d68c05552b`:

```bash
git clone https://android.googlesource.com/kernel/common \
  /work/src/ubox10-kernel-5.4.302-common
git -C /work/src/ubox10-kernel-5.4.302-common remote add vendor \
  https://github.com/orangepi-xunlong/linux-orangepi.git
git -C /work/src/ubox10-kernel-5.4.302-common fetch origin \
  refs/heads/android12-5.4:refs/remotes/origin/android12-5.4
git -C /work/src/ubox10-kernel-5.4.302-common fetch vendor \
  refs/heads/orange-pi-5.4-sun50iw9:refs/remotes/vendor/orange-pi-5.4-sun50iw9
scripts/integrate-m8-kernel-54302.sh \
  /work/src/ubox10-kernel-5.4.302-common
```

Pin the external module donors exactly as recorded in `checkpoint.json`: XR819 from
`Mini-LinuxPC-Pro` commit `5bcbf22cdbc3f6ff7c5633447b0b0f8dbf6bfca1` and AIC8800
20221108-004 from `GammaKinematics/sunxi_kernel` commit
`abfe04920992577c71a4180a8480a4a774965c76`. Use the already validated
AOSP `clang-r416183b1` toolchain. From a clean build/evidence destination, the exact build
entry point is:

```bash
scripts/build-m8-kernel-54302.sh \
  /work/src/ubox10-kernel-5.4.302-common \
  027ef79e8facb73cb2419b4a08c0bd3f13a2206e \
  /work/build-logs/ubox10-kernel-5.4.302/20260822T170205Z/accepted/boot-unpacked/kernel \
  configs/candidates/m8b-rc-core-r1/ff40-map.json \
  configs/candidates/m8b-rc-core-r2/rc-main-repeat.patch \
  /work/toolchains/aosp-clang-android12/clang-r416183b1/bin \
  /work/toolchains/ubuntu-libssl-dev/root \
  /work/toolchains/ubuntu-bc/root \
  /work/kernel-builds/m8-kernel-5.4.302-r1 \
  /work/build-logs/ubox10-kernel-5.4.302/20260822T170205Z \
  /work/src/ubox10-xr819-5.4-donor \
  5bcbf22cdbc3f6ff7c5633447b0b0f8dbf6bfca1 \
  /work/src/gamma-sunxi-aic8800-donor \
  abfe04920992577c71a4180a8480a4a774965c76
```

The builder starts from the Image-extracted accepted Android 12 config and fails unless its
preservation and separate Path-A effective configs exactly match the tracked configs/diffs.
It builds the ARM64 Image plus the complete 22-module set, records full provenance/resources,
and leaves the source integration repository unchanged. Run it in a clearly named detached
tmux session with persistent console and status files for any future rebuild. The accepted run
used `-j8`, clang 12.0.7, and produced release `5.4.302+`; the Image is 23,492,616 bytes,
SHA-256 `9B781ABEA51DEF9AE1FEBB9011CFA630AC267C794FBA0E066674F0EAE2509DCC`.

After `scripts/audit-m8-kernel-54302.py` reports
`PASS_WITH_PHYSICAL_VALIDATION_REQUIRED`, the only candidate assembly entry point is:

```bash
python3 scripts/build-m8-kernel-54302-candidate.py --keep-failed
```

The candidate builder hash-locks the build audit, accepted Android 12 base, rollback image,
AOSP host tools and all expected results in
`configs/candidates/m8-kernel-5.4.302-r1.json`. It refuses to overwrite an existing final
output, performs no device operation, and must not be used to change system/vendor/product or
unrelated outer payloads. The accepted offline result is
`out/candidates/m8-kernel-5.4.302-r1/x12-m8-kernel-5.4.302-r1.img`, 1,031,739,392
bytes, SHA-256 `C93FC8A54391E091E0F95CFE63E4F6DA9AE90D55AA0163D91D42586B48BFEE2B`.
See `docs/m8/candidates/m8-kernel-5.4.302-r1.md` for conflict rationale, the complete config
delta, module audit, packaging invariants and the still-closed physical gate.

## Checks

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

Clean-clone tests exercise parsers, configs, and builders. Artifact-specific r2-r6 tests skip until their ignored local outputs exist, then validate the actual images.

Tool provenance is in [`tools/README.md`](../tools/README.md). Current hardware/runtime evidence is in [`docs/m8/research/current-device/`](m8/research/current-device/). Useful upstream references are [AOSP ATV](https://android.googlesource.com/device/google/atv/+/refs/heads/android12-release/), [TrebleDroid](https://github.com/TrebleDroid/device_phh_treble), [LineageOS ATV](https://github.com/LineageOS/android_device_google_atv), and [AOSP linkerconfig](https://android.googlesource.com/platform/system/linkerconfig/+/refs/heads/android12-release/); none is a drop-in UBOX10 image.
