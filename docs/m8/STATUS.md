# M8 status

Updated: 2026-08-02

## Current candidate

`m8a-initial-atv-r6` is **READY TO FLASH** and has not been device-tested.

| Artifact | Value |
|---|---|
| Image | `out/candidates/m8a-initial-atv-r6/x12-m8a-initial-atv-r6.img` |
| Bytes | 996582400 |
| SHA-256 | `8796B4FC9ABA2D213B044043F979992CE9C5996425D52273A088A04EA3BE5D93` |
| Delta from r5 | Replace only `super.fex` and regenerate `Vsuper.fex`; restore stock interleaved A/B LP table order |
| Offline result | LP metadata valid; four logical payloads match r1; 48 other IMAGEWTY entries preserved; focused tests, companion checks, and `SHA256SUMS` passed |

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
| r6 | **READY TO FLASH** | Stock A/B interleaved LP partition-table order restored without changing logical payload bytes | Flash once and capture cold-boot UART |

Raw UART logs and candidate images are intentionally local under ignored `logs/` and `out/` paths. Git retains the concise findings, builders, configs, hashes, and focused validators; it does not pretend a clean clone contains the large artifacts.

## Boundaries

- No physical action was performed during the 2026-08-02 repository cleanup.
- Runtime Android, framework, HDMI, ADB, launcher/HOME/IME, provisioning, remote, media, DRM, Wi-Fi, Bluetooth, audio, Ethernet, and CEC remain untested on r6.
- Current board, DT, and runtime evidence identifies the H616 platform. The device has a 64-bit kernel but no proven AArch64 Android graphics userspace, so M8B remains parked.

## Next action

After explicit authorization, follow [the device test guide](../DEVICE_TEST.md): verify the r6 hash, flash in PhoenixCard Product mode, remove the card, cold boot, and capture UART. Do not design r7 until the earliest reproducible r6 failure is known.
