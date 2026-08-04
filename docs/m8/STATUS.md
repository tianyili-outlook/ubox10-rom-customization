# M8 status

Updated: 2026-08-04

## Current candidate

`m8a-initial-atv-r8` is **READY TO FLASH** and has not been device-tested.

| Artifact | Value |
|---|---|
| Image | `out/candidates/m8a-initial-atv-r8/x12-m8a-initial-atv-r8.img` |
| Bytes | 996586496 |
| SHA-256 | `013AA02A59CB4A916CFEA14180824F7CFD781B514D96778C5933009B42B11B80` |
| Delta from r7 | Replace only `boot.fex` and regenerate `Vboot.fex`; set `console=ttyS0,115200n8 ignore_loglevel` |
| Offline result | 48 outer payloads unchanged; `boot.fex` command line is exact; all 12 paired payload checks and focused r8 tests passed |

## Verified progress

| Stage | Result | First useful finding | Next correction |
|---|---|---|---|
| Test8r2 | **ROLLBACK VERIFIED** | Stable ARM32 Android 12 baseline | Retained as preferred rollback |
| AOSP ATV product | **OFFLINE CHECKED** | ARM32 TV system/product/system_ext built from locked Android 12 sources | Assemble with stock hardware stack |
| r1 | **FAILED - `/metadata` mount** | First-stage init could not mount an ext4 metadata partition | Add preformatted metadata payload and download-map entry |
| r2 | **FAILED - flash map CRC** | PhoenixCard rejected the modified `dlinfo.fex` | Recompute dlinfo CRC |
| r3 | **FAILED - `/oem` mount** | Product flash passed; erased `media_data` left required VFAT `/oem` unavailable | Add preformatted media_data payload and descriptor |
| r4 | **FAILED - first-stage reboot** | Both filesystems mounted; PID 1 still rebooted to bootloader at about 1.106 s | Test whether the rebuilt AVB root caused the reboot |
| r5 | **FAILED - first-stage reboot, no HDMI** | Keyless top-level AVB bypass made no material difference; reboot occurred at about 1.113 s | Restore the first remaining concrete LP metadata difference |
| r6 | **FAILED - first-stage reboot** | Stock A/B interleaved LP partition-table order made no material timing change; reboot at 1.096406 s | Restore missing system-root `/metadata` switch-root target |
| r7 | **FAILED - first-stage reboot** | `/metadata` system-root target made no difference; reboot remained about 312 ms after `Kernel init done` | Expose first-stage fatal message on UART |
| r8 | **READY TO FLASH** | Set the boot console and `ignore_loglevel`; this is a single boot-payload diagnostic change | Flash once and capture the first explicit first-stage failure |

Raw UART logs and candidate images are intentionally local under ignored `logs/` and `out/` paths. Git retains the concise findings, builders, configs, hashes, and focused validators; it does not pretend a clean clone contains the large artifacts.

## Boundaries

- No physical action was performed during the 2026-08-02 repository cleanup.
- Runtime Android, framework, HDMI, ADB, launcher/HOME/IME, provisioning, remote, media, DRM, Wi-Fi, Bluetooth, audio, Ethernet, and CEC remain untested on r6.
- Current board, DT, and runtime evidence identifies the H616 platform. The device has a 64-bit kernel but no proven AArch64 Android graphics userspace, so M8B remains parked.

## Next action

After explicit authorization, follow [the device test guide](../DEVICE_TEST.md): verify the r8 hash, flash in PhoenixCard Product mode, remove the card, cold boot, and capture UART. Use the first first-stage fatal line to make the next minimal repair.
