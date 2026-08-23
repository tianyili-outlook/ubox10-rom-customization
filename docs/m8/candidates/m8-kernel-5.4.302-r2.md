# M8 Linux 5.4.302 AIC8800D SDIO diagnostic r2

Date: 2026-08-23
Status: **OFFLINE-CHECKED DIAGNOSTIC / NOT AN ACCEPTED FIX / NOT AUTHORIZED TO FLASH**

## Why this candidate exists

The separately authorized Android 12 `m8-kernel-5.4.302-r1` physical test boots Linux
5.4.302, reaches `sys.boot_completed=1`, and passes HDMI/UI, remote, Ethernet and ADB.
Wi-Fi alone fails reproducibly after SDIO enumeration and AIC8800D U04 firmware setup:

```text
Set SDIO Clock 66 MHz
cmd timed-out
tkn[...] result:-4 cmd:1037 - reqcfm(1038)
wifi start fail
```

The three AIC modules and firmware files are present.  The boundary is the missing
`DBG_START_APP_CFM`, before Android Wi-Fi HAL/framework usability can be tested.  r2 tests
one narrower hypothesis: whether the host/card link is unreliable at the rounded 66.7 MHz
rate used during the firmware START_APP exchange.

## Source-proven clock and failure paths

The pinned donor is Orange Pi `external/aic8800` commit
`abfe04920992577c71a4180a8480a4a774965c76`, subtree
`70c98140316f7ed23af879bb0e3d881883f5e978` (AIC release 20221108-004).  Before modification:

1. `aic8800_bsp/aic_bsp_driver.h` defines `FEATURE_SDIO_CLOCK 70000000`;
2. `aicbsp_get_feature()` copies it to `feature.sdio_clock`;
3. `aicwf_sdio_func_init()` claims the host, assigns `host->ios.clock`, invokes
   `host->ops->set_ios(host, &host->ios)`, and logs the post-`set_ios` value;
4. the exact `allwinner,sunxi-mmc-v4p1x` SDR implementation requests a module clock at twice
   the logical SDIO rate, calls `clk_round_rate()`, and writes the rounded rate divided by two
   back to `ios->clock`.  A 70 MHz request therefore becomes about 66.7 MHz and logs `66 MHz`.

The set point precedes `aicbsp_driver_fw_init()` and no AIC path restores or changes it before
`aicwifi_start_from_bootrom()` waits for START_APP confirmation.  Host claim/release does not
restore `ios.clock`.  The same feature value is later consumed by fdrv runtime setup.

The failure call chain is
`rwnx_mod_init` → `aicbsp_set_subsys(AIC_WIFI, ON)` → BSP SDIO init/probe →
`aicbsp_8800d_fw_init` → `aicwifi_init` → `aicwifi_start_from_bootrom` →
`rwnx_send_dbg_start_app_req` → `rwnx_send_msg(reqcfm=1, DBG_START_APP_CFM)` → command queue
and bus TX → two-second completion wait.  The receive path must reach `rwnx_rx_handle_msg()`
and `cmd_mgr_msgind()` to match and complete the request.  TASK_DBG message numbering makes
the request/confirmation IDs 1037/1038.  The timeout then produces `wifi start fail`, fdrv
init unwinds, power is removed and the SDIO card disappears.  The printed `result:-4` is the
command's initial `-EINTR` sentinel before timeout conversion, not proof of a separate signal
interruption.

This proves where and when 66 MHz is selected and proves the missing confirmation boundary.
It does **not** yet prove that clock rate is the cause.

## Exact experiment

`configs/kernel/m8-kernel-5.4.302/aic8800d-sdio-50mhz.patch` contains one source change:

```diff
-#define FEATURE_SDIO_CLOCK 70000000
+#define FEATURE_SDIO_CLOCK 50000000
```

Patch SHA-256 is
`ED64ADF7943592281359667FA3CB8E27446FCE6F15AB4711CEC6A30847CC06A5`.
It changes no DT/DTBO, firmware, userspace, HAL, generic MMC timeout/retry, MMC/SDIO core,
kernel config, module inventory or other warning.

The clean r2 build uses the exact r1 integration commit
`027ef79e8facb73cb2419b4a08c0bd3f13a2206e`, preservation config and AOSP
clang-r416183b1/12.0.7.  It completes in 548 seconds with all 22 modules.  The r2 BSP module is
127,752 bytes / SHA-256
`D3BA64E43FCD708B4EB7628576D83A01581023181271E0CF76613DD9BC4528F3`.
Its module name, vermagic, dependencies, normalized exported-symbol set and unresolved-symbol
set equal r1; exact kernel and AIC `Module.symvers` are unchanged.

A clean whole-tree rebuild is not byte-identical to r1 because absolute build paths are
embedded and ThinLTO assigns private numeric `.llvm` IDs.  To enforce the physical experiment
instead of packaging irrelevant rebuild noise, the candidate deliberately reuses the
physically tested r1 Image and 21 r1 module bytes, replacing only `aic8800_bsp.ko` with the r2
build.  Machine audit result is `PASS_SINGLE_VARIABLE_OFFLINE`.

## Candidate and offline result

The final artifact values are hash-locked in
`configs/candidates/m8-kernel-5.4.302-r2.json`.  Candidate construction also pins the ext4
debugfs clock to the accepted filesystem creation time; this prevents wall-clock-only
superblock/AVB/super/outer hash drift without changing runtime content.

| Artifact | Size | SHA-256 |
|---|---:|---|
| `out/candidates/m8-kernel-5.4.302-r2/x12-m8-kernel-5.4.302-r2.img` | 1,031,739,392 | `A2963FD46685829774DBF5EA2E899ED5844BF44329BC8F46788F1D14D09AA036` |
| `boot.fex` | 67,108,864 | `338CB4048796E213698585E035D8807D84381324163C19AA939BD8D6BFDDCD2C` |
| `super.fex` | 851,940,812 | `FAAF908032F6E0461357D2457E4F979B070AAC37B262942287F4F15BFB63ED89` |
| `vendor_dlkm_a.img` | 6,680,576 | `3DFC93FDEA8024CF8960E55FA1D55EA2E1769FD5FA25C80706B1AB16351F6AB5` |

Offline checks establish:

- r1 `boot.fex`, Image, ramdisk, boot AVB and DT bytes are exact;
- 21 non-BSP modules and all module metadata/static vendor_dlkm files are exact;
- only `aic8800_bsp.ko` differs inside vendor_dlkm;
- `system_a`, `vendor_a`, `product_a`, LP geometry/extents/slots/groups and partition sizes are exact;
- vendor_dlkm AVB hashtree/FEC, ext4/e2fsck, sparse-super round trip and IMAGEWTY verify;
- outer changes are only `super.fex` and its `Vsuper.fex` checksum companion; 48/50 payloads,
  including bootloader, TEE, DTBO, vendor_boot, vbmeta and factory/security content, are exact;
- r1 input, accepted Android 12 inputs and Test8r2 rollback remain unchanged.

Focused r2 tests and the full repository suite pass: 84 tests run, with 25 expected skips for
absent ignored historical candidate fixtures.  Final deterministic candidate assembly takes
about 106 seconds; the clean kernel/module build takes 548 seconds.  Sampled build resources
remain safe: minimum available RAM 60,776,856 KiB, minimum `/work` available 147,466,500 KiB,
no swap, no OOM and no filesystem/I/O failure.

The result is **not Wi-Fi PASS**.  Offline work cannot prove the physical host realizes exactly
50 MHz, receives `DBG_START_APP_CFM`, keeps fdrv loaded, creates `wlan0`, or provides usable
Android Wi-Fi.

## Separately authorized physical decision rule

No physical action is authorized by this document.  If later authorized, the primary evidence
must show `Set SDIO Clock 50 MHz`, no 1037→1038 timeout, successful START_APP confirmation,
loaded `aic8800_fdrv`, `wlan0`, and usable Android Wi-Fi.  An otherwise identical
`cmd:1037 - reqcfm(1038)` plus `wifi start fail` rejects the 50 MHz hypothesis.  Do not then
guess another frequency; next diff Linux 5.4.125→5.4.302 generic MMC/SDIO request completion,
SDIO IRQ, CMD52/53, host claim/release, timeout/completion and card power/re-enumeration paths
against the pinned AIC BSP interaction.

Rollback remains the accepted Test8r2 image, 2,005,954,560 bytes / SHA-256
`6A52F3388E9ABF6AFA8A701CFD7198FE6C0090F16531F6E3BD3949E760892EC8`.
Gate 2 remains **CLOSED**.
