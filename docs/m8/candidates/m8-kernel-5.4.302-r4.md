# M8 Linux 5.4.302 post-timeout SDIO interrupt snapshot r4

Date: 2026-08-23
Status: **PHYSICAL DIAGNOSTIC PASS / WI-FI FAIL / DRIVER SEMANTIC DIVERGENCE FOUND / r5 DESIGN JUSTIFIED, NOT BUILT**

## Decision boundary

The separately authorized r4 run is a physical diagnostic pass but a Wi-Fi failure.  Android 12
completed boot on Linux 5.4.302+, and the r4-only CCCR fields prove the instrumented BSP ran.  One
manual Wi-Fi start and its normal framework self-recovery both reported token 476, a successful
host-side 24-byte bus TX / final 512-byte function-1 CMD53, and no attributable AIC handler, CMD53
RX, 1038 dispatch, token match or completion.  Both timeout snapshots had function 1, hardware
SDIO IRQ capability, a claimed IRQ and installed handler, `IENx=0x03`, but core pending zero and
`INTx=0x00`.  Thus no standards-compliant function-1 pending indication survived to timeout.  This
does not prove card FIFO dequeue, firmware execution, or absence of an earlier transient signal.

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

## Physical result

The five preserved files under ignored
`/work/device-evidence/m8-kernel-5.4.302-r4/20260823-wifi-on/` show
`sys.boot_completed=1`, Linux 5.4.302+, U04 selection (`rev id 0x7`, `sub id 0x20`) and the exact
r4 trace schema.  Build/package evidence links that schema to the final 129,976-byte
`aic8800_bsp.ko`, SHA-256
`C993867D21988F0F1C4E32A9857821ADDA7899374B440688131E2CD9897F8CA4`; no on-device module hash was
captured, so the identity proof is the unique instrumentation plus the audited candidate chain,
not an independent runtime hash measurement.

At 320.093 and 324.637 seconds, the manual `AIC_WIFI ON` and framework `WifiSelfRecovery` attempts
both recorded:

```text
token=476 tx_bus_len=24 tx_bus_ret=0
tx_cmd53_state=2 tx_cmd53_len=512 tx_cmd53_ret=0
irq_count=0 rx_cmd53_count=0 cfm_seen=0 token_match=0 completion=0
timeout_func=1 host_cap_sdio_irq=1 host_irq_pending=0
irq_claimed=1 handler_installed=1
cccr_intx=0x00 cccr_intx_ret=0 cccr_ienx=0x03 cccr_ienx_ret=0
```

Several natural-boot AIC_BLUETOOTH/shared-BSP cycles reached the same timeout.  One earlier cycle
logged `aicwf_sdio_hal_irqhandler: Interrupt but no data`; that literal is emitted only after entry
to the AIC handler and a successful zero block-count read.  It proves the physical DAT1 → SUNXI →
MMC → AIC handler path can operate in an earlier state, but does not prove a START_APP response IRQ
was generated or handled.

The physical conclusion is therefore narrower than firmware failure: Linux completed the final
CMD53 without error; no persistent standard function pending indication remained at timeout; and
no START_APP-window handler/RX/1038/completion was observed.  Persistent-card-IRQ-lost-by-Linux is
low priority.  FIFO consumption, a boot-transition failure and a transient indication remain open.

## Exact U04 firmware contract audit

The exact preserved `vendor_a.img` firmware selected by the physical U04 path was extracted
read-only.  Its identities are:

| File | Size | SHA-256 |
|---|---:|---|
| `fmacfw.bin` | 260,984 | `FC3BC7865CBB01560E706E87FEA23F07CBF86B0E9F76649381D553FE8E781904` |
| `fw_adid_u03.bin` | 1,208 | `6C7CC9D899D2A4E5B91B0F009AA6679498131ADC27D220B96EC162536370A190` |
| `fw_patch_u03.bin` | 64,204 | `4B97D0F7C41F29EDB4B9082F0FB3B920770A8EF9C3F7E8D93C062AEDD9E778CD` |
| `fw_patch_table_u03.bin` | 1,336 | `9EC1A1CC6A6249E3EE8302DC952D71C9F494FEC2A1A16499FFB72893C0A475ED` |

`fmacfw.bin` is a raw Cortex-M image for the firmware-linked and accepted-driver load address
`0x00120000`: its vector table contains MSP `0x00183800` and Thumb reset vector `0x00120189`.
It identifies itself as
`v6.4.3.1`, built 2022-10-08 from `gb01a3750`.  Its debug-handler table at file offset `0x3f884`
maps message `0x040d` / 1037 to Thumb handler `0x00144f61`.  Read-only disassembly proves that
handler:

1. allocates a four-byte message 1038 addressed back to the request source;
2. treats types 0/1/2 as log-only in the already-running FMAC context;
3. treats type 3 as delayed or immediate reboot;
4. logs types above 3 as invalid, but still continues to confirmation;
5. calls an indirect ROM/API pointer stored at `0x000001a4` with selector 15, keeps its low byte as
   the four-byte `bootstatus`, prints `DBG: FW started`, then sends 1038.

The exact callee behind selector 15 is not symbolized.  The host stores only the low byte as
`aicbsp_info.hwinfo_r`; therefore `bootstatus` is a returned hardware-information-like value in
this lineage, not a source-proven boot-progress/error latch.  It exists only inside the missing
CFM and cannot discriminate an r4 timeout.

The exact FMAC therefore contains a real post-start producer of 1038.  It does not reveal the
initial U04 boot-ROM consumer, FIFO dequeue, AUTO handoff or whether the boot ROM could also emit a
1038.  Authoritative ownership of the initial confirmation remains unknown.  The best-supported
inference is post-transfer FMAC ownership: an AIC8800 same-vendor pre-transfer handler stops the
old host interface and programs/reset-launches the requested vector without allocating a CFM,
while the exact downloaded FMAC allocates and sends 1038 only after it is executing.

## External lineage and mode limits

[Radxa's AIC package history](https://github.com/radxa-pkg/aic8800) at commits
[`7c8ed35d5e634186e0d1a25bc1436531ab57088f`](https://github.com/radxa-pkg/aic8800/commit/7c8ed35d5e634186e0d1a25bc1436531ab57088f),
[`ea15d8515af1d773bda79c6a7ccaa4c271a73fa3`](https://github.com/radxa-pkg/aic8800/commit/ea15d8515af1d773bda79c6a7ccaa4c271a73fa3),
[`78d6075fd52e0fc5f774cdeb208b150ebb3a2c9e`](https://github.com/radxa-pkg/aic8800/commit/78d6075fd52e0fc5f774cdeb208b150ebb3a2c9e)
and [`d5e11d4b9166d4159ffb4d4baadfcdb07d482e20`](https://github.com/radxa-pkg/aic8800/commit/d5e11d4b9166d4159ffb4d4baadfcdb07d482e20)
provides AIC8800 SDIO U03/U04 firmware from vendor
SDK releases dated 2023-11-07 through 2026-01-23.  None of those `fmacfw.bin` files is byte-identical
to the project binary, but all four contain the same 1037 → allocate 1038 → type/reboot handling →
low-byte status → `DBG: FW started` → send control flow.  This is **strong same-chip/same-family
evidence**, not exact binary identity.  The project `fw_adid_u03.bin` is byte-identical to the
current public copy, while its FMAC and U03 patch/table are not.

The [public AIC embedded SDK mirror at commit
`0188df66ce158f540d65181109869fadf5cb9376`](https://github.com/RIRIKING/AIC8800Code/tree/0188df66ce158f540d65181109869fadf5cb9376)
supplies a symbolized but prebuilt AIC8800
`host_cmd.o`.  Its pre-transfer AUTO handler reads the vector at `bootaddr+4`, stops the host
interface and programs the execution/reset trigger; a target-device variant copies vector words
and calls `SystemCoreReset`.  CUSTOM only logs and returns.  Neither variant constructs a CFM.
This is a **plausible same-vendor ancestor/structural proxy**, not AIC8800D U04 proof.

Newer [AIC8800DC](https://github.com/radxa-pkg/aic8800/blob/df4c783b663eba1956579c681acd5e45f25c671d/src/SDIO/driver_fw/driver/aic8800/aic8800_bsp/aic8800dc_compat.c)
and [D80N](https://github.com/radxa-pkg/aic8800/blob/df4c783b663eba1956579c681acd5e45f25c671d/src/SDIO/driver_fw/driver/aic8800/aic8800_bsp/aic8800d80n_compat.c)
host code establishes only cross-chip usage semantics: FNCALL=4 runs uploaded
calibration/cinit code at a Thumb entry and returns before the host reads its results; DUMMY=5 is
used by the normal DC continuation path and returns quickly in a
[public AIC8800DC bring-up log](https://github.com/LuckfoxTECH/luckfox-pico/issues/131).  No public
device-handler source establishes their internal implementation.  The exact U04 FMAC labels both
4 and 5 invalid, so neither is a justified U04 diagnostic command.  AUTO's exact initial U04
setup, CUSTOM's initial semantics and the relative boot-ROM handoff ordering remain unknown.

No exact U04 read-only boot-status register, CPU PC/status, FIFO dequeue pointer, firmware-ready
magic, exception latch or CFM-constructed flag was found.  The `host_ready` string has no published
address/read contract; different-chip reset/COMREG registers are not safe proxies.  Device-contract
archaeology alone therefore found no source-proven read-only discriminator.  The later
accepted-driver audit below changes the r5 decision for a separate, earlier host-side contract
divergence; it does not make the unknown boot-ROM internals known.

## Accepted-driver versus donor semantic audit

The device-accepted reference was independently read from
`/work/ubox10-a16-prototype-a-inputs/verified/m8b-remote-r1/logical/vendor_dlkm_a.img` rather than
trusted only as a loose extraction.  Its 132,072-byte `aic8800_bsp.ko` is SHA-256
`C06604861F8264B764A848FA7F432160884A5A45AFB8C765844DBD809F5A835D`; the clean r1 module is
127,752 bytes / `2EF8EF0AE2302CD0B95452B9A6FA11710D07B19F518E53C985D4FFDEBE71C96B`.
Both contain version `1.0`, the same Android clang 12.0.7 and 11.0.2 producer strings, and related
2022-11-08 AIC BSP tags (`aic-bsp-sdio-20221108-001` versus
`aic-bsp-compatible(sdio)-20221108-001`).  Exact working vendor source is still absent, so the
pinned donor must not be called original UBOX source.  Nevertheless, equal sizes and raw machine
bytes for the command manager, `aicbsp_driver_fw_init`, `aicbsp_get_feature`,
`aicbsp_set_subsys`, `aicbsp_platform_power_off`, all debug memory request helpers,
`rwnx_plat_bin_fw_upload_android`, `rwnx_send_dbg_start_app_req`, RX dispatch and several SDIO
helpers establish **very strong same-lineage mapping** for the live path.

Focused disassembly classified the remaining visible differences as follows:

| Difference | Classification | START_APP relevance |
|---|---|---|
| Current code reads the revision sub-ID and labels the physical part U04; working code uses the older revision test | Semantic but irrelevant here | The SDIO donor aliases U03/U04 system tables and selects the same U03 firmware/config filenames for every non-U02 part |
| Current BSP contains `aicbsp_system_reboot()` / `aicbsp_8800d_system_reboot()` | Not reached | The only donor caller is compiled in `aicusb.c`; the SDIO module has no caller |
| Generic TX/RX thread names, larger inlined probe/thread bodies, private ThinLTO suffixes, log prefixes, layout, symbol count and module size | Build/refactor noise unless a selected branch differs | The U04-selected probe, function enable, 512-byte block size, register `0x0b=1`, byte-mode register `0x11=1`, IRQ claim and local interrupt register `0x04=0x07` instruction sequences match; the final message branch uses the same function, fixed address 7, padding and `sdio_writesb()` call |
| FMAC upload/patch-read/START_APP base | **Plausible root-cause candidate** | Working uses `0x00120000`; r1, r3 and physically run r4 use `0x00110000` |

The last row is exact binary and build evidence, not an inference from a source name:

- working `aicbsp_8800d_fw_init` passes `1179648` / `0x00120000` both to
  `rwnx_plat_bin_fw_upload_android()` at module `.text+0x2858` and to
  `rwnx_send_dbg_start_app_req(..., HOST_START_APP_AUTO, ...)` at `.text+0x290c`;
- clean r1 passes `1114112` / `0x00110000` at `.text+0x2860` and `.text+0x2914`;
- the final r3 and r4 modules also pass `0x00110000`, including r4 at `.text+0x2cf4` and
  `.text+0x2da8`; the r4 trace did not log `bootaddr`, so it cannot override its own ELF;
- pinned donor `abfe04920992577c71a4180a8480a4a774965c76` selects `0x00120000` under
  `#ifdef CONFIG_AIC_INTF_SDIO`, but its BSP Makefile translates that Kbuild variable only into
  `-DAICWF_SDIO_SUPPORT`.  Exact r1/r3/r4 `.aic_bsp_8800d.o.cmd` files contain
  `-DAICWF_SDIO_SUPPORT`, not `-DCONFIG_AIC_INTF_SDIO`, and generated `autoconf.h` has no such
  Kconfig symbol.  The C preprocessor therefore selects the `0x00110000` `#else` branch.

The upload helper, whose working and r1 machine bytes are identical, writes the raw file
sequentially from the supplied base in 1,024-byte debug-memory blocks.  The accepted and r4
`vendor_a.img` copies of all four U04 firmware inputs are byte-identical.  Exact `fmacfw.bin` has
size `0x3fb78`, so accepted placement is `[0x00120000, 0x0015fb78)` while current placement is
`[0x00110000, 0x0014fb78)`.  Its vector still names Thumb reset entry `0x00120189`: the intended
entry bytes are at image offset `0x188`, but current placement puts offset `0x188` at
`0x00110188`; bytes at `0x00120188` instead come from unrelated image offset `0x10188`.  This is a
real execution-image contract mismatch before the final CMD53, irrespective of whether the
unknown exact U04 AUTO implementation reads the vector or performs another vendor-specific
handoff.

This finding **RAISES donor/build-integration mismatch** from unproven lineage concern to the
highest-value plausible root-cause candidate.  It does not yet prove the physical cause.  The
earliest source-proven divergence is now the FMAC destination chosen in `aicwifi_init()`, before
START_APP serialization; the remaining physical boundary is wrong image placement/boot address →
boot-ROM AUTO handoff → FMAC reset-vector execution.  The former CMD53-complete → FIFO-dequeue
boundary remains observationally unresolved, but is no longer the earliest known divergence.

**r5 = YES, DESIGN ONLY / NOT BUILT.**  The bounded discriminator is one source-level contract
correction on top of r4: change only the `RAM_FMAC_FW_ADDR` guard in `aic_bsp_8800d.c` from
`CONFIG_AIC_INTF_SDIO` to the actually supplied `AICWF_SDIO_SUPPORT`, retaining all r4 trace code
unchanged.  A future authorized build must prove by final-module disassembly that the firmware
upload, `RAM_FMAC_FW_ADDR + 0x180` patch read and START_APP boot address all use `0x00120000`, while
firmware, kernel/MMC, timeout and every unrelated module remain exact.  A returned 1038 and working
Wi-Fi would strongly confirm sufficiency; the same r4 timeout after verified correct placement
would reject this mismatch as sufficient and restore the downstream device boundary.  Risk is
low and bounded because it reproduces the exact accepted module's address and leaves 0x1db0 bytes
before the fixed ADID region, but it is a behavioral experiment and requires separate build and
physical authorization.

No physical action is authorized by this record.  This is not Wi-Fi PASS, not an accepted fix and
not Android 16 Prototype A r3.  Gate 2 remains **CLOSED**.

Rollback remains Test8r2, 2,005,954,560 bytes / SHA-256
`6A52F3388E9ABF6AFA8A701CFD7198FE6C0090F16531F6E3BD3949E760892EC8`.
