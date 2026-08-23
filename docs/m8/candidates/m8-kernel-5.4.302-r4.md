# M8 Linux 5.4.302 post-timeout SDIO interrupt snapshot r4

Date: 2026-08-23
Status: **OFFLINE CHECKED / INSTRUMENTATION ONLY / NOT A FIX / NOT PHYSICALLY VALIDATED**

## Decision boundary

The separately authorized r3 run is a physical diagnostic pass but a Wi-Fi failure.  Both the
manual Wi-Fi start and its one framework self-recovery attempt proved that the final 512-byte
START_APP CMD53 write returned zero on the Linux host, followed by no attributable AIC handler,
CMD53 RX, 1038 dispatch, token match or completion.  The proven boundary is therefore
**post-TX/pre-AIC-handler**.  A successful host-side return does not prove card consumption, and
zero AIC handler entries does not distinguish no card interrupt from an interrupt lost before the
handler.

The exact r3 build cannot make that distinction read-only from Android.  `CONFIG_DEBUG_FS`,
`CONFIG_DEVMEM` and `CONFIG_MMC_DEBUG` are disabled; SDIO sysfs exposes identity, not CCCR pending
state.  `/proc/interrupts` counts the shared host IRQ and cannot attribute a count to the card's
function interrupt.  SUNXI's `sunxi_dump_host_register` has no store method, but its show method
reads every MMIO offset from `0x000` through `0x14c` without claiming the host; it is not proven
non-destructive, does not expose card CCCR and cannot make a negative host snapshot conclusive.
The card is removed about 188 ms after the r3 timeout, so a later ADB read is also too late.

## Exact IRQ path

The pinned AIC8800D path is:

1. `aicwf_sdio_bus_start()` in
   `drivers/net/wireless/aic8800-accepted/aic8800_bsp/aicsdio.c` claims the host, calls
   `sdio_claim_irq(func1, aicwf_sdio_hal_irqhandler)`, writes AIC local interrupt config `0x07`,
   then releases the host.  The BSP does not log or propagate the `sdio_claim_irq()` return.
2. `drivers/mmc/core/sdio_irq.c` reads/writes CCCR `IENx`, sets the function and master-enable
   bits, installs `func->irq_handler`, starts `ksdioirqd/mmc2` and selects the single-function fast
   path.  The exact DT has `cap-sdio-irq`, so this is hardware-IRQ mode rather than polling.
3. Card DAT1 reaches retained `drivers/mmc/host/sunxi-mmc.c`; `sunxi_mmc_irq()` reads `MISTA`,
   recognizes `SDXC_SDIO_INTERRUPT` bit 16, acknowledges `RINTR` with its write-one-to-clear bit,
   then calls `mmc_signal_sdio_irq()`.
4. The MMC core masks the host SDIO IRQ, sets `host->sdio_irq_pending` and wakes `ksdioirqd/mmc2`.
   With one registered function, `process_sdio_pending_irqs()` calls the AIC handler directly
   without first reading CCCR `INTx`.
5. The AIC handler reads its local block-count register by CMD52, performs the CMD53 RX, queues the
   frame, dispatches message 1038 and completes the runtime-token waiter.

The [SDIO Simplified Specification](https://www.sdcard.org/cms/wp-content/themes/sdcard-org/dl.php?f=PartE1_SDIO_Simplified_Specification_Ver2.00.pdf)
defines CCCR Interrupt Pending as read-only; Linux's own multi-function path likewise reads `INTx`
with CMD52 and performs no acknowledgement write.  The function pending
bit is therefore the smallest card-level timeout discriminator, provided it is sampled before the
existing teardown.  A clear bit at two seconds does not prove that a transient, malformed or
self-cleared assertion never occurred.

## Single-variable instrumentation

The additive patch is
`configs/kernel/m8-kernel-5.4.302/aic8800d-startapp-timeout-cccr.patch`, SHA-256
`2E338EF6F8003F0CFD5F504039D0350263DB8AD0103758EE01D76400A195F251`.  It applies after the r3
START_APP trace patch and changes only `aic_bsp_driver.c` and the private `aicsdio.h` trace state.

Only after the unchanged blocking wait has already returned timeout, and before existing probe
failure/teardown, it:

- records runtime function number, `MMC_CAP_SDIO_IRQ`, the pre-claim `host->sdio_irq_pending`
  snapshot, `sdio_irq_claimed(host)` and whether `func->irq_handler` is installed;
- claims the existing host once, reads read-only CCCR `INTx` first and `IENx` second with
  `sdio_f0_readb()`, records requested register values/return codes, then releases the host;
- keeps the r3 trace window active across the snapshot so a handler racing at the timeout boundary
  is counted, then closes it and emits the existing one-line summary.

There is no write, sleep, retry, new completion, timeout change, firmware/clock/DT/config/userspace
change or pre-timeout control-flow change.  The original `FEATURE_SDIO_CLOCK=70000000` remains.
The two CMD52 reads can delay teardown only after Wi-Fi has already failed.  Reading `INTx` itself
does not acknowledge the card's function interrupt; reading `IENx` is also non-mutating.

The MMC headers needed by the implementation are hidden from `genksyms` with the tree's existing
Android KABI technique.  An initial offline audit caught that unguarded header visibility changed
two unrelated AIC exported-symbol CRCs; that build was rejected and never packaged.  The final
guarded build restores `aic8800.Module.symvers` byte-for-byte to r1, so the preserved r1
`aic8800_fdrv.ko` contract remains valid.

## Build and offline audit

The final clean detached build used integration commit
`027ef79e8facb73cb2419b4a08c0bd3f13a2206e`, AOSP clang-r416183b1 / clang 12.0.7, the exact r1
config, the r3 trace patch and the additive r4 patch.  Evidence is under ignored
`/work/build-logs/m8-kernel-5.4.302-r4/20260823T102830Z-final4/`.

It completed in 831 seconds with Image, normalized DTBs and all 22 modules.  The r4 source added no
compile warning or error.  Fourteen samples saw minimum available memory 14,175,996 KiB, minimum
`/work` available 75,163,268 KiB and maximum load1 13.49; no swap, OOM or I/O failure occurred.

The final `aic8800_bsp.ko` is 129,976 bytes / SHA-256
`C993867D21988F0F1C4E32A9857821ADDA7899374B440688131E2CD9897F8CA4`.  Focused machine audit
reports `PASS_POST_TIMEOUT_CCCR_INSTRUMENTATION_ONLY`:

- config, `Module.symvers`, AIC exported-symbol names/CRCs and normalized DTBs match r1;
- module inventory, names, dependencies and vermagic stay exact; the only r3→r4 added import is the
  existing GPL export `sdio_f0_readb`;
- donor→r4 source delta remains the four r3 trace files, while r3→r4 changes only
  `aic_bsp_driver.c` and `aicsdio.h`;
- the candidate module root differs from r1 only at `aic8800_bsp.ko`.

Candidate assembly ran in detached tmux for 151 seconds.

| Artifact | Size | SHA-256 |
|---|---:|---|
| `out/candidates/m8-kernel-5.4.302-r4/x12-m8-kernel-5.4.302-r4.img` | 1,031,739,392 | `18565E4F94FF1A843EA859254800E5E2BA732FBFE47410E86D6577038F85DFCA` |
| `boot.fex` | 67,108,864 | `338CB4048796E213698585E035D8807D84381324163C19AA939BD8D6BFDDCD2C` |
| `super.fex` | 851,940,812 | `68731B4E27029369A658A32344059561BFDDA406F2FFDF6BC048B6AE5A3E594B` |
| `vendor_dlkm_a.img` | 6,680,576 | `EB2CCAAB4DF8948DD626AA325CDF5604667B702059D71420531C5BB618CA43C5` |

r1 boot/Image/ramdisk/DT/boot AVB, Android 12 system/vendor/product, LP geometry and 21 unrelated
module bytes are exact.  Vendor_dlkm retains one free 4 KiB block; AVB hashtree/FEC,
ext4/e2fsck, sparse round trip and IMAGEWTY verification pass.  Only `super.fex` and checksum
companion `Vsuper.fex` change; the other 48/50 outer payloads, including bootloader, TEE,
vendor_boot, DTBO, vbmeta and security/factory data, remain exact.  Test8r2 rollback is unchanged.
All candidate `SHA256SUMS`, the outer IMAGEWTY verifier, JSON/shell/Python syntax checks and the
focused four-test r4 contract pass.  The full repository suite reports 92 tests passing with 25
expected fixture/candidate skips.

## Separately authorized physical discriminator

No physical action is authorized by this record.  After separate authorization for the exact
firmware hash above, use the r1/r3 PhoenixCard, UART-first and Test8r2 rollback boundary.  Boot
Android, confirm `sys.boot_completed=1`, start continuous UART/logcat capture, then manually turn
Wi-Fi on exactly once.  The framework's one normal self-recovery may be observed; do not add a
second manual attempt.

On the Windows host, collect the complete buffers without clearing them:

```powershell
adb wait-for-device
adb shell getprop sys.boot_completed
adb shell su 0 dmesg > .\r4-dmesg-before-wifi.txt
# Start a separate continuous capture before the single manual Wi-Fi ON:
adb logcat -b all -v threadtime > .\r4-wifi-on-all.txt
# After the timeout/self-recovery sequence, from a second terminal:
adb shell su 0 dmesg > .\r4-wifi-on-kernel.txt
Select-String -Path .\r4-wifi-on-kernel.txt -Pattern `
  'Set SDIO Clock|AIC_STARTAPP_TRACE|cmd timed-out|cmd:1037|wifi start fail|mmc2: card'
```

Interpret the added summary fields as follows:

- expected setup is `timeout_func=1 host_cap_sdio_irq=1 irq_claimed=1
  handler_installed=1`, `cccr_ienx_ret=0`, with IENx master bit 0 and function bit 1 set;
- `cccr_intx_ret=0` with function bit 1 set while r3 IRQ count remains zero proves the card reports
  a pending function interrupt at timeout but the AIC handler did not receive it; `host_irq_pending`
  then separates “core already signaled but not dispatched” from loss before core signaling;
- `cccr_intx_ret=0` with the function bit clear and correct IENx means no standards-compliant
  pending indication survived to timeout.  It narrows toward no persistent card indication but is
  not by itself proof of firmware failure or proof that no earlier pulse occurred;
- a nonzero CCCR return means card/bus state was unavailable and must be treated as its own result;
- any positive r3 IRQ/RX/1038 field supersedes the old pre-handler boundary and must be interpreted
  before choosing another experiment.

Do not change behavior in the same run.  This is not Wi-Fi PASS, not an accepted fix and not
Android 16 Prototype A r3.  Gate 2 remains **CLOSED**.

Rollback remains Test8r2, 2,005,954,560 bytes / SHA-256
`6A52F3388E9ABF6AFA8A701CFD7198FE6C0090F16531F6E3BD3949E760892EC8`.
