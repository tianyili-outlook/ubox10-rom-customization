# M8A initial ATV r4

ID: `m8a-initial-atv-r4`  
Status: FLASHED / FAILED. Product 模式刷写成功，但首阶段 init 仍重启到 bootloader。

## Artifacts

- Firmware: `out/candidates/m8a-initial-atv-r4/x12-m8a-initial-atv-r4.img`
- Size: 996952064 bytes
- SHA-256: `5AFE57DE82B0A42BD3EFB4618375DB896FB0BD7C3C82FF9BD7E817C374C4AAB5`
- Retained media_data image: `out/candidates/m8a-initial-atv-r4/media_data.img`
- media_data size: 16777216 bytes
- media_data SHA-256: `334BE30C9F641F2B059B900B09C761E58CF2357C39EB94124F044FC82668331F`
- Retained metadata image: `out/candidates/m8a-initial-atv-r4/metadata.img`
- Metadata size: 16777216 bytes
- Metadata SHA-256: `21385B83F3DBEF67342BED553DE2DAC3BDD0D08BE8B9F7BBAB73E851A7139BB5`
- Base candidate: `out/candidates/m8a-initial-atv-r3/x12-m8a-initial-atv-r3.img`, 980171776 bytes, SHA-256 `B8130EE221AC3B020FC972CA04531064F26E9068EDCE20D3BBACACBF83F16234`

## Triage summary & failure evidence

- `M8A r3 - FLASHED / FAILED`
- Failure evidence log: `logs/device/20260801-212804`
- Root cause: r3 Product-mode flash succeeded (`CARD OK`), but cardless cold boot reached `Kernel init done` at UART line 4685 and then PID 1 requested `bootloader` at line 4686 because vendor_boot `fstab.sun50iw9p1` requires first-stage mount of `/dev/block/by-name/media_data` at `/oem` (vfat ro). Product mode erases GPT `media_data`, and r3 dlinfo lacked a `media_data` descriptor to pre-seed this partition.

## Repair implementation

- Generated a 16777216-byte (16 MiB) empty valid VFAT filesystem image using `mkfs.vfat` in WSL, retained as `media_data.img`, and checked read-only with `fsck.vfat -vn`.
- Extracted r3 `dlinfo.fex`, required count 12 and valid stored CRC (`0xd32ef288`), inserted one sorted descriptor:
  - name `media_data`
  - download sector 13280256 (`0xCAA400`)
  - size 32768 sectors
  - `MEDIA_DATA_FEX00`
  - `VMEDIA_DATA_FEX0`
- Updated count to 13 and recomputed CRC32 at offset 0 (`0x6b9b9b04`).
- Repacked r3 using `tools/pack_image_preserving.py` with one replacement (`dlinfo.fex`) and one addition (`media_data.fex` with companion `Vmedia_data.fex`).
- Preserved all 47 non-dlinfo payloads from r3 byte-for-byte, including `metadata.img`/`Vmetadata.fex`.

## Retained validation record

| Check | Method | Result |
|---|---|---|
| Candidate identity | SHA-256 & size | 996952064 bytes; `5AFE57DE82B0A42BD3EFB4618375DB896FB0BD7C3C82FF9BD7E817C374C4AAB5` |
| media_data VFAT | `fsck.vfat -vn` & boot sector signature | 16 MiB FAT16 structure valid; signature `0xAA55` PASS |
| dlinfo count & CRC | `test_m8a_r4_media_data.py` | Count 12 -> 13; stored CRC `0x6b9b9b04` matches `zlib.crc32(dlinfo[4:])` PASS |
| dlinfo geometry & names | `test_m8a_r4_media_data.py` | Download sector 13280256, 32768 sectors, `MEDIA_DATA_FEX00`/`VMEDIA_DATA_FEX0` sorted PASS |
| Payload preservation | Header & byte diff | 47 non-dlinfo payloads byte-identical to r3; metadata exact PASS |
| IMAGEWTY verification | `sunxi_image_tool.py verify` | 50 total files; 12 partition V companions OK |

## Device result

- Evidence: `logs/device/20260801-222006`.
- `metadata` 与 `media_data` 均成功写入和校验，刷写以 `CARD OK` 完成。
- 冷启动到 `Kernel init done` 后在 1.105528 秒重启到 `bootloader`；没有 ext4/vfat 运行时错误。
- 下一候选：`m8a-initial-atv-r5`，只关闭顶层 AVB verification。
