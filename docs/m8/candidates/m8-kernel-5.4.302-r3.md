# M8 Linux 5.4.302 AIC8800D START_APP trace r3

Date: 2026-08-23
Status: **OFFLINE CHECKED / INSTRUMENTATION ONLY / NOT A FIX / NOT PHYSICALLY VALIDATED**

## Purpose and baseline

Physical r2 rejected the 50 MHz hypothesis: its active `Set SDIO Clock 50 MHz` path still
repeated token 476 `DBG_START_APP_REQ` 1037 → missing `DBG_START_APP_CFM` 1038 → timeout.
The relevant retained 5.4.125→5.4.302 generic CMD52/CMD53, SDIO IRQ, request completion,
claim/release and SUNXI host paths do not justify a behavioral revert.  r3 therefore makes no
fix and answers only where the existing START_APP transaction stops.

r3 deliberately returns to the physically tested r1 functional baseline.  Pinned AIC donor
commit `abfe04920992577c71a4180a8480a4a774965c76` / subtree
`70c98140316f7ed23af879bb0e3d881883f5e978` retains
`FEATURE_SDIO_CLOCK=70000000`, so hardware remains on the original rounded ~66.7 MHz path.
The 50 MHz r2 patch is absent.  No token value is hardcoded; the runtime token assigned to the
actual 1037 command is captured.

## Source-reviewed trace design

Tracked patch:
`configs/kernel/m8-kernel-5.4.302/aic8800d-startapp-trace.patch`, SHA-256
`B65CC9940302D8F204012B7365EC1437B48A3AA6C7A7E772E4F0A57E266EFFE4`.
It changes four files inside `aic8800_bsp` and no generic MMC/SUNXI source:

1. `cmd_mgr_queue()` arms one trace generation after the real command manager assigns the
   runtime token and only when IDs are exactly 1037/1038.  Blocking command serialization means
   this window is attributable to that START_APP transaction, rather than to token 476 or an
   arbitrary global IRQ counter.
2. `rwnx_set_cmd_tx()` records the synchronous bus TX requested length/return.  For AIC8800D,
   `aicwf_sdio_tx_msg()` separately records whether its final `sdio_writesb()`-backed CMD53 was
   attempted, the padded requested length and the exact returned status.  The API exposes no
   actual transferred-byte count, so none is invented.
3. A three-state final-CMD53 marker (`not attempted` / `in call` / `returned`) prevents IRQ or RX
   activity before the actual final write attempt from entering the transaction counters.  The
   existing AIC IRQ handler records total activity after the attempt, activity specifically after
   the write returned, and the final block-count CMD52 value/result.  Thus an IRQ racing between
   host release and the caller's return marker remains visible without being mislabeled as
   post-return.  The existing handler control flow and retry loop are untouched.
4. The existing CMD53 RX wrapper likewise records total and post-TX-return attempt counts,
   requested length and return.  The RX
   worker records the parsed frame length/type/message ID; `rwnx_rx_handle_msg()` records whether
   1038 reaches dispatch; the command matcher records whether the real waiting token matches and
   whether it calls the existing completion path.
5. `atomic_xchg()` closes the window and exactly one `AIC_STARTAPP_TRACE:` summary is emitted on
   the existing success or timeout return.  IRQ/RX hot paths emit no new printk output.

The patch adds no sleep, retry, lock, host claim, completion, timeout, firmware, clock, DT,
kernel-config or userspace behavior.  Its in-memory atomics/`READ_ONCE`/`WRITE_ONCE` operations
are only active for START_APP; the summary is emitted after the existing success/timeout outcome.
The trace state is private to the BSP's internal `priv_dev`, so it changes no exported module ABI.

The compact summary fields are:

```text
AIC_STARTAPP_TRACE: result=... gen=... token=... req=1037 cfm=1038
  tx_queued=... tx_bus_len=... tx_bus_ret=...
  tx_cmd53_state=... tx_cmd53_len=... tx_cmd53_ret=...
  irq_count=... irq_after_tx_return=... irq_block_count=... irq_block_count_ret=...
  rx_cmd53_count=... rx_after_tx_return=... rx_cmd53_len=... rx_cmd53_ret=...
  rx_frame_len=... rx_type=... rx_msg_id=...
  cfm_seen=... token_match=... completion=...
```

It distinguishes final TX failure, no attributable card IRQ, IRQ without readable data, CMD53 RX
failure, non-1038 protocol data, 1038 dispatch loss, token mismatch and completion loss.  It does
not claim that every IRQ is itself a confirmation; the RX header/ID fields provide that second
level of attribution.

## Build and single-variable audit

The clean detached build used integration commit
`027ef79e8facb73cb2419b4a08c0bd3f13a2206e`, preservation config and AOSP
clang-r416183b1 / clang 12.0.7.  The build command was the tracked
`scripts/build-m8-kernel-54302.sh` invocation with the trace patch as argument 15 and
`70000000` as the explicit expected clock argument 16.  Persistent evidence is under ignored
`/work/build-logs/m8-kernel-5.4.302-r3/20260823T083600Z-final/`.

The clean build completed in 565 seconds with Image, DTBs and all 22 modules.  The inherited
kernel/DT/XR819 warnings remain; the traced AIC source introduced no compile warning or error.
Ten resource samples saw minimum available RAM 27,891,880 KiB and minimum `/work` available
95,373,076 KiB; no swap, OOM or I/O failure occurred.

The instrumented `aic8800_bsp.ko` is 129,280 bytes / SHA-256
`1A64A5E98CBA60FC0D619014245F1FFCF9B4C983AB6092F084F5547978126AD8`.
Its name, vermagic, dependency, normalized exported-symbol set and unresolved-symbol set match
r1.  Config, `Module.symvers` and normalized DTB inventory match r1.  Machine source audit proves
the donor delta is exactly the four trace files, the 70 MHz line is unchanged and the candidate
module root differs from r1 only at `aic8800_bsp.ko`.

## Candidate and offline result

Candidate assembly ran in detached tmux and completed in 170 seconds.

| Artifact | Size | SHA-256 |
|---|---:|---|
| `out/candidates/m8-kernel-5.4.302-r3/x12-m8-kernel-5.4.302-r3.img` | 1,031,739,392 | `9E52B601F11F9368599098B4C5082037D010930D9B424D7CA2828977047C1B28` |
| `boot.fex` | 67,108,864 | `338CB4048796E213698585E035D8807D84381324163C19AA939BD8D6BFDDCD2C` |
| `super.fex` | 851,940,812 | `FB1DC3C3568CAB428207B1BE3C823E8B0DC191041E00861B5B374DA34833638A` |
| `vendor_dlkm_a.img` | 6,680,576 | `471FDC7299BD36A9B2507A1450A398F130CDDAAEF9041A9D3803CB8C8F54AA44` |

Focused preservation checks establish:

- r1 `boot.fex`, Image, ramdisk, DT and boot AVB are byte-identical;
- system, vendor, product, Android 12 userspace and LP geometry/extents/slots/groups are exact;
- 21 unrelated modules and all module metadata/static vendor_dlkm files are exact; only
  `aic8800_bsp.ko` differs;
- the larger BSP still uses the same ext4 block count, leaving one 4 KiB block free;
- vendor_dlkm AVB hashtree/FEC, ext4/e2fsck, sparse round trip and IMAGEWTY verify pass;
- outer changes are only `super.fex` and checksum companion `Vsuper.fex`; the other 48/50
  payloads, including bootloader, TEE, DTBO, vendor_boot, vbmeta and security/factory content,
  are exact;
- physical r1, accepted Android 12 inputs and Test8r2 rollback remain unchanged.

Repository validation completed with 88 tests passing and 25 expected skips; the r3-specific
four-test contract, including the present local candidate, passed without skips.  `git diff
--check`, JSON parsing, all candidate `SHA256SUMS`, and the outer IMAGEWTY verifier also pass.

This is **not Wi-Fi PASS** and not an accepted fix.  Gate 2 remains **CLOSED**.  No physical
device action was performed and this record does not authorize one.

## Separately authorized physical discriminator

If the user later explicitly authorizes this exact hash, use the same PhoenixCard/UART-first and
Test8r2 rollback boundary as r1/r2.  Preserve a complete UART capture, then extract only the
decisive lines on the Windows host:

```powershell
Select-String -Path .\boot-r3-uart.log -Pattern `
  'Set SDIO Clock|AIC_STARTAPP_TRACE|cmd timed-out|cmd:1037|reqcfm\(1038\)|wifi start fail|wlan0'
```

The test answers, in order:

1. `tx_cmd53_state=2`, `tx_cmd53_ret=0` and `tx_bus_ret=0` prove final 1037 TX returned;
2. positive `irq_count` after the final write attempt proves transaction-scoped IRQ activity;
   `irq_after_tx_return` distinguishes activity after the caller observed TX return, while the
   block-count fields show whether readable blocks were advertised;
3. positive RX count with `rx_cmd53_ret=0` proves response data was read;
4. `rx_type=0x11`, `rx_msg_id=1038`, `cfm_seen=1` prove the expected CFM reached dispatch;
5. `token_match=1 completion=1 result=success` prove it matched the runtime waiter.

Do not interpret the trace as a fix, and do not proceed to a behavioral patch until these fields
identify the missing boundary.  Rollback remains Test8r2, 2,005,954,560 bytes / SHA-256
`6A52F3388E9ABF6AFA8A701CFD7198FE6C0090F16531F6E3BD3949E760892EC8`.
