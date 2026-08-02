# M8A initial ATV r6

Status: **READY TO FLASH**; offline checked, not device-tested.

| Artifact | Value |
|---|---|
| Firmware | `out/candidates/m8a-initial-atv-r6/x12-m8a-initial-atv-r6.img` |
| Bytes | 996582400 |
| SHA-256 | `8796B4FC9ABA2D213B044043F979992CE9C5996425D52273A088A04EA3BE5D93` |
| Base | r5, SHA-256 `B2EE421510BA6D6FE4C224960223DC08A8A8BFD71AD64D092B4FD9BB9E962AF0` |

## Why r6 exists

r4 and r5 both reached `Kernel init done` and then PID 1 rebooted to bootloader at nearly the same time. The r5 top-level AVB bypass did not change the failure. The first remaining concrete candidate-specific difference was LP partition-table order: r1-r5 grouped all A entries before all B entries, while stock interleaves each A/B pair.

r6 rebuilds `super.fex` with the stock order:

`system_a`, `system_b`, `vendor_a`, `vendor_b`, `product_a`, `product_b`, `vendor_dlkm_a`, `vendor_dlkm_b`.

No logical partition payload was changed. In the outer container only `super.fex` is replaced and `Vsuper.fex` is regenerated; the other 48 entries match r5.

## Offline checks

- All three LP metadata slots parse and use the expected order.
- Extracted system, vendor, product, and vendor_dlkm payloads match the r1 inputs byte-for-byte.
- Focused r6 tests passed 3/3.
- IMAGEWTY companion checks passed 12/12.
- Candidate `SHA256SUMS` passed.

Next: use [the device test guide](../../DEVICE_TEST.md) after explicit flash authorization.
