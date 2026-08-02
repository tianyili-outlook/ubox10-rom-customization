# M8A initial ATV r2

ID: `m8a-initial-atv-r2`  
Status: PASSED OFFLINE VALIDATION - READY FOR USER REVIEW. It is not boot-tested, promoted, or flash-authorized. No physical device action performed.

## Artifacts

- Firmware: `out/candidates/m8a-initial-atv-r2/x12-m8a-initial-atv-r2.img`
- Size: 980171776
- SHA-256: `84252B39C8632417FB1F1877C462F9D9945EEAEDF97D5E48554E87ED2DA9C8CC`
- Retained metadata image: `out/candidates/m8a-initial-atv-r2/metadata.img`
- Metadata size: 16777216
- Metadata SHA-256: `21385B83F3DBEF67342BED553DE2DAC3BDD0D08BE8B9F7BBAB73E851A7139BB5`
- Base candidate: `out/candidates/m8a-initial-atv-r1/x12-m8a-initial-atv-r1.img`, 963391488 bytes, SHA-256 `68029C3F5EE3BEFC2AFD6187A3EE3EA9D4BD0A2A4C10B4C686429232B18491C5`

## Triage summary & root cause

- `M8A.2a - BUILT / OFFLINE CHECKED`
- `M8A r1 - FLASHED`
- `M8A r1 - FAILED: r1 first boot reached kernel/first-stage init, failed on missing/unformatted /metadata ext4 filesystem, requested bootloader reboot, and second boot entered fastboot UI (fallen robot). No direct recovery/BCB boot occurred.`
- Both primary UART log paths: `logs/device/20260801-170033` and `logs/device/20260801-165049`
  - Cold boot init output: `EXT4-fs (mmcblk0p20): VFS: Can't find ext4 filesystem`
  - Kernel reboots with command `'bootloader'` into second boot fallen-robot UI (`fastbootlogo.bmp`).
- Identified root cause: First-stage init requires ext4 partition `metadata` (GPT p20, 16777216 bytes). Stock `init.formatdevice.rc` formats `Reserve0`, not `metadata`. r1 lacked a download descriptor and pre-seeded image payload for `metadata`.

## Repair implementation & sector facts

1. Generated empty ext4 filesystem labeled `metadata`, exactly 16777216 bytes (`mke2fs 1.47.0`, `e2fsck -fn` exit 0, `debugfs` verified). Retained in candidate directory and included in SHA256SUMS.
2. Sector geometry:
   - `dlinfo_download_sector`: 13206528 (sector offset in download map)
   - `card_boot_offset_sectors`: 40960 (SD card bootloader offset)
   - `gpt_first_lba_sector`: 13247488 (GPT partition p20 first LBA)
   - Formula verified: `13206528 + 40960 == 13247488`
3. Updated PhoenixCard download descriptors in `dlinfo.fex` (count 11 -> 12), inserting `metadata` entry at download sector `13206528` (size 32768 sectors, `METADATA_FEX0000` / `VMETADATA_FEX000`).
4. Action counts in r2 outer container:
   - 45 preserved payloads from r1 remain exact
   - 1 replacement (`dlinfo.fex`)
   - 1 addition (`metadata.fex`)
   - 1 companion (`Vmetadata.fex`)
   - Total entries: 48
5. Repository-only builder: Performs no external stock or rollback reads; rehashes repository-local r1 (`x12-m8a-initial-atv-r1.img`).
6. Updated default UART capture duration in `scripts/capture-uart-readonly.ps1` and active runbooks from 90 seconds to 900 seconds.

## Retained validation record

| Check | Method | Result |
|---|---|---|
| Candidate identity | SHA-256 & size | 980171776 bytes; `84252B39C8632417FB1F1877C462F9D9945EEAEDF97D5E48554E87ED2DA9C8CC` |
| Metadata image | WSL `mke2fs` / `e2fsck -fn` / `debugfs` | 16777216 bytes; ext4 label `metadata`; `e2fsck` exit 0; SHA-256 `21385B83F3DBEF67342BED553DE2DAC3BDD0D08BE8B9F7BBAB73E851A7139BB5` |
| dlinfo descriptor & magic | Entry parser | 12 entries; download sector 13206528; size 32768; preserved magic word `0x80B15BEB`; companion `Vmetadata.fex` checksum `0x21701403` PASS |
| IMAGEWTY verification | `sunxi_image_tool.py verify` | 48 total files; 11 partition V companions OK |
| Preservation audit | Header & payload diff | Outer prefix diffs restricted to `image_size` and `num_files`; 45 r1 outer payloads preserved exact |
| Test suite | `python -m unittest discover tests` | 63 run / 60 passed / 3 skipped / 0 failed |
| Independent validation | Conversation `c3a6b89b-3eaf-47a9-9d05-2b877f347f24` | All 9 validation groups PASS; r1 baseline and external stock/rollback rehashed and verified |

## Device boundary and next action

No physical-device action was performed in this task.
Status: PASSED OFFLINE VALIDATION - READY FOR USER REVIEW (not boot-tested, not flash-authorized).
Next action: request explicit user authorization for physical flash test.

Declared rollback record: Test8r2, 2005954560 bytes, SHA-256 `6A52F3388E9ABF6AFA8A701CFD7198FE6C0090F16531F6E3BD3949E760892EC8`.
