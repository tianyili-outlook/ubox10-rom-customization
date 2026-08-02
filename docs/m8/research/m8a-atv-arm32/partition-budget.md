# M8A partition budget

The assembled candidate has a stock-compatible four-partition LP schema. Stock has no system_ext logical partition/fstab mount, so system_ext content is merged into system_a.

| Logical partition | Bytes |
|---|---:|
| system_a | 1651167232 |
| vendor_a | 119066624 |
| product_a | 272629760 |
| vendor_dlkm_a | 6680576 |
| A-group use | 2049544192 |
| A-group free | 1163292672 |

AOSP expanded source sizes are system 1625026560, product 268435456, and system_ext 268435456. system_ext is not added as a fifth partition. Vendor and vendor_dlkm remain stock bytes.

This is M8A.2b offline layout evidence, not a device mount/boot claim.
