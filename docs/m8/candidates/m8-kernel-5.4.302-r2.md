# M8 Linux 5.4.302 AIC8800D SDIO diagnostic r2

Date: 2026-08-23
Status: **PHYSICALLY FAILED — 50 MHZ HYPOTHESIS REJECTED / NOT AN ACCEPTED FIX**

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

## Physical result: hypothesis rejected

The separately authorized r2 physical test is complete.  Android 12 still reaches
`sys.boot_completed=1`; Ethernet and ADB work.  The changed set point is active, but every
power/re-enumeration attempt repeats the r1 failure at the same protocol boundary:

```text
mmc2: new SDIO card
aicbsp_sdio_probe: matched chip: aic8800d
Set SDIO Clock 50 MHz
cmd timed-out
tkn[476] flags:0012 result:-4 cmd:1037 - reqcfm(1038)
wifi start fail
mmc2: card ... removed
```

`aic8800_bsp` and `aic8800_btlpm` remain loaded, but `aic8800_fdrv` does not remain loaded and
`wlan0` does not exist.  The Android Wi-Fi HAL service exists; framework
`CMD_STA_START_FAILURE` and return to `DisabledState` are downstream consequences.  r2 changed
exactly one functional variable from r1 and proves the 50 MHz request took effect, so the
rounded 66.7 MHz rate is not the root cause.  Do not test another arbitrary frequency.  No raw
r2 capture was added to this checkout; this record preserves the user-provided physical
observations without inventing a file identity.

## 5.4.125 to 5.4.302 MMC/SDIO differential

The comparison uses retained vendor commit `9ab7a758149d3c9b721878a0c18b3f9c5d6c93e6`
and the reproducible integration commit `027ef79e8facb73cb2419b4a08c0bd3f13a2206e`.
The Android-common update range is
`6cb0d5ef8b388d0249d96060e9ef31b466f88c7d..2443acb8671f5eaeac985e70446726278ed014ae`.

The exact live data/IRQ path did not change across the retained-vendor and integration trees:

- `drivers/mmc/core/sdio_irq.c`, `sdio_io.c` and `sdio_ops.c` are identical;
- `include/linux/mmc/host.h`, `card.h` and `sdio_func.h` are identical;
- all retained `drivers/mmc/host/sunxi-mmc*` sources, including request completion,
  `SDXC_SDIO_INTERRUPT` handling, `mmc_signal_sdio_irq()` and `enable_sdio_irq()`, are
  identical by tree comparison;
- `mmc_request_done()`, `mmc_wait_for_req[_done]()`, `mmc_wait_for_cmd()`,
  `__mmc_claim_host()` and `mmc_release_host()` have no changed hunk in `core.c`.

The retained host has a real `enable_sdio_irq` operation and the accepted DT carries
`cap-sdio-irq`, so the core runs `ksdioirqd`.  AIC is compiled with
`AICWF_SDIO_SUPPORT` and `CONFIG_PLATFORM_ALLWINNER`; its AIC8800D path claims function 1's
IRQ before firmware initialization.  CMD52 is implemented through `sdio_readb/writeb`, and
payload TX/RX through `sdio_writesb/readsb` (CMD53).  This rules out a silent wholesale
replacement of the Allwinner host or the generic CMD52/CMD53/IRQ implementation.

### Exact 1037/1038 path

The TX chain is:

`aicwifi_start_from_bootrom()` → `rwnx_send_dbg_start_app_req()` →
`rwnx_send_msg()` → `cmd_mgr_queue()` → `rwnx_set_cmd_tx()` →
`aicwf_sdio_bus_txmsg()` → TX kthread → `aicwf_sdio_tx_msg()` → flow-control CMD52 →
function-1 CMD53 write.

The required RX chain is:

SUNXI SDIO IRQ → `mmc_signal_sdio_irq()` → `ksdioirqd/mmc2` →
`process_sdio_pending_irqs()` → `aicwf_sdio_hal_irqhandler()` → block-count CMD52 →
function-1 CMD53 read → RX queue/completion → `aicwf_busrx_thread()` →
`aicwf_process_rxframes()` → config-response type `0x11` → `rwnx_rx_handle_msg()` →
`cmd_mgr_msgind()` matches ID 1038 → clears `WAIT_CFM` → completes the waiter.

Flags `0x0012` are `REQ_CFM|WAIT_CFM`: the confirmation never reached the matcher.  The AIC
device is zero-allocated and every firmware command is blocking; token 476 therefore means
476 earlier request/confirmation transactions completed before START_APP.  Firmware block
writes, patch reads/writes, the same SDIO IRQ/RX thread, command dispatch and completion
machinery all work before the firmware execution transition.  This sharply narrows the
problem but does not distinguish a failed final TX, no interrupt from the new firmware, an
IRQ with unreadable/empty data, a malformed response, or a message that reaches dispatch with
the wrong ID.

### Ranked semantic deltas

| Rank | Exact delta | Possible affected path | Evidence and smallest discriminator |
|---:|---|---|---|
| 1 | Android-common `076712ff50dc27ada280e1a07edae2534a017368`, upstream `39a72dbfe188291b156dd6523511e3d5761ce775`: `mmc_select_voltage()` keeps the correct two-bit OCR range using `3 << (bit - 1)` | Cold SDIO attach can send a different OCR mask to `mmc_sdio_init_card()` | It is the only changed cold-init item with a conceivable electrical consequence, but it does not change the already-selected `ios.vdd`; enumeration and hundreds of confirmed transfers succeed. First log old/new `ocr`, selected `rocr`, `ios.vdd` and signal voltage. Revert this one fix only if those values materially differ; current evidence does not justify restoring the old voltage bug. |
| 2 | Android-common `ea7e57d54b29662127d6890a46de67d26ec7a83f`, upstream `a2a44f8da29352f76c99c6904ee652911b8dc7dd`: apply `quirk_max_rate` to non-UHS SDIO | Initial SDIO clock choice before AIC probe | AIC has no recorded max-rate quirk and later directly overwrites `ios.clock`. r2 physically forced 50 MHz and reproduced the failure, so this rate hypothesis is rejected. No further clock experiment. |
| 3 | `2d95959fa4f43a4035c79bf9c3b3ca11ee1233a3` / upstream `77347eda64ed5c9383961d1de9165f9d0b7d8df6` and `894b678d865b374fe95cf95b29e15e3edee2d7df` / upstream `32a9cdb8869dc111a0c96cf8e1762be9684af15b`: retune flag cleanup and 1-bit-resume retune hold | A retune immediately before CMD52/53 could delay or fail traffic | The SUNXI host exposes no `execute_tuning` callback and this is a cold boot, not SDIO resume. Source evidence makes these paths inactive. A one-shot retune trace is the maximum justified discriminator; no behavior revert is warranted. |
| 4 | `761db46b29b496946046d8cb33c7ea6de6bef36e` / upstream `605d9fb9556f8f5fb4566f4df1480f280f308ded` and `7a09c64b7da0abdec3919812e3d93ecc44069ed0` / upstream `9972e6b404884adae9eec7463e30d9b3c9a70b18`: SDIO function refcount/error-removal fixes | Function/card lifetime during init error or removal | These execute on allocation error/removal, after the observed START_APP timeout in this run. They cannot selectively suppress 1038 before teardown. No candidate. |
| 5 | `95d65bca6eb9967aa5f6ed7a32e041b4f11ffbc2` / upstream `d6c9219ca1139b74541b2a98cee47a3426d754a9`: reject hosts that advertise SDIO IRQ without an operation | MMC host registration | The retained SUNXI host provides `enable_sdio_irq`; `mmc2` registers and AIC claims IRQ. If this fired there would be no card/probe/firmware path. No candidate. |
| 6 | `5cc8a367851b69920061a65fa7c98c0011e0cfa1` / upstream `8c3e5b74b9e2146f564905e50ca716591c76d4f1`: store OCR earlier for `MMC_QUIRK_NONSTD_SDIO` | Non-standard-card initialization/resume | AIC enumerates through standard CIS/function handling and only adds `MMC_QUIRK_LENIENT_FN0`; it does not set `NONSTD_SDIO`. Path inactive. No candidate. |
| 7 | shutdown/card-alive deltas `1c3d4122bec632ffbd6c40ef9321b17a55ff810d`, `4eb49404de26fab8be0cf2c2385652bbd2c95613`, and SPI-only `8613c9fb1c565d4282d764ee12b3710d6d93d279` (upstream `66c915d09b942fb3b2b0cb2f56562180901fba17`, `87a0d90fcd31c0f36da0332428c9e1a1e0f97432`, `fec40f44afdabcbc4a7748e4278f30737b54bb1a`) | Shutdown rescan or SPI card-alive test | Native SDIO START_APP occurs before teardown; removal follows the AIC timeout. These are secondary lifecycle changes, not a cause. No candidate. |

`CONFIG_ANDROID_KABI_RESERVE=y` is a real effective-config difference and adds reserved padding
to several MMC structures.  It does not mix ABIs here: the Image, SUNXI host and every external
module were rebuilt against the same effective config, and the existing fields retain their
meaning.  Disabling it would be a broad all-module ABI experiment with no specific 1038
mechanism, so it is not justified.

## Decision and next discriminating experiment

No changed generic MMC/SDIO commit is currently supported strongly enough to justify a
behavior-changing candidate.  Building a multi-revert or copying the 5.4.125 MMC subtree
would bundle unrelated variables and weaken the physical result, so no next image was built.

The highest-information next step is one diagnostic-only `aic8800_bsp.ko` with logs gated to
the START_APP transaction.  It must preserve timeouts and behavior while recording:

1. the actual return from `aicwf_sdio_bus_txmsg()`/final CMD53 write for message 1037;
2. entry to the AIC SDIO IRQ handler and its block-count CMD52 value;
3. CMD53 RX return/length and the config header/message ID before dispatch;
4. whether ID 1038 reaches `cmd_mgr_msgind()` and whether it matches token 476.

One authorized UART run would then discriminate TX failure, missing card IRQ, IRQ/RX failure,
firmware/protocol response absence, and AIC dispatch/completion loss without changing firmware,
DT, userspace/HAL, generic MMC timeouts or the retained host.  It is only an experiment plan;
no diagnostic candidate or physical authorization exists yet.

Rollback remains the accepted Test8r2 image, 2,005,954,560 bytes / SHA-256
`6A52F3388E9ABF6AFA8A701CFD7198FE6C0090F16531F6E3BD3949E760892EC8`.
Gate 2 remains **CLOSED**.
