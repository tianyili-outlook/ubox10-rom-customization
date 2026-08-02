# M8A initial ATV r3

ID: `m8a-initial-atv-r3`  
Status: PASSED OFFLINE VALIDATION - READY FOR USER REVIEW. It is not boot-tested, promoted, or flash-authorized. No physical device action performed.

## Artifacts

- Firmware: `out/candidates/m8a-initial-atv-r3/x12-m8a-initial-atv-r3.img`
- Size: 980171776 bytes
- SHA-256: `B8130EE221AC3B020FC972CA04531064F26E9068EDCE20D3BBACACBF83F16234`
- Retained metadata image: `out/candidates/m8a-initial-atv-r3/metadata.img`
- Metadata size: 16777216 bytes
- Metadata SHA-256: `21385B83F3DBEF67342BED553DE2DAC3BDD0D08BE8B9F7BBAB73E851A7139BB5`
- Base candidate: `out/candidates/m8a-initial-atv-r2/x12-m8a-initial-atv-r2.img`, 980171776 bytes, SHA-256 `84252B39C8632417FB1F1877C462F9D9945EEAEDF97D5E48554E87ED2DA9C8CC`

## Triage summary & failure evidence

- `M8A r2 - FLASHED`
- `M8A r2 - FAILED: r2 flash failed before partition writes during PhoenixCard download map fetch.`
- Failure evidence log: `logs/device/20260801-210354/uart-com3-115200.txt` lines 294-297 (`fetch download map`, `downlaod map is bad`, `sunxi sprite error : fetch download map error`).
- Root cause: r2 `dlinfo.fex` added `metadata` partition entry (11 -> 12 entries), but left offset 0 CRC32 header byte stale at `0x80b15beb`. Computed `zlib.crc32(dlinfo[4:])` is `0xd32ef288`.

## Repair implementation

- Extracted r2 `dlinfo.fex`, changed only its first 4 bytes to little-endian `0xd32ef288`.
- Repacked as the sole replacement over r2 using `tools/pack_image_preserving.py`.
- Preserved all 47 other stored payloads in r2 byte-for-byte.
- Final r3 firmware size remains exactly 980171776 bytes and differs from r2 at only the four CRC byte positions of `dlinfo.fex`.

## Retained validation record

| Check | Method | Result |
|---|---|---|
| Candidate identity | SHA-256 & size | 980171776 bytes; `B8130EE221AC3B020FC972CA04531064F26E9068EDCE20D3BBACACBF83F16234` |
| dlinfo CRC fix | `test_m8a_r3_dlinfo_crc.py` | r2 stored CRC stale (`0x80B15BEB`), r3 stored CRC equals `zlib.crc32(r3_dlinfo[4:])` (`0xD32EF288`) PASS |
| dlinfo content after CRC | Payload slice diff | Bytes after offset 4 identical to r2 PASS |
| Entry & payload count | Header parser | 48 entries, 47 non-dlinfo payloads byte-identical PASS |
| Single-patch invariant | Image-wide byte diff | Entire r3 image differs from r2 only at dlinfo's 4 CRC bytes PASS |
| IMAGEWTY verification | `sunxi_image_tool.py verify` | 48 total files; 11 partition V companions OK |

## Next action

Status: PASSED OFFLINE VALIDATION - READY FOR USER REVIEW.  
Next action: flash r3 candidate via PhoenixCard Product mode and observe UART logs.
