# Build and packaging pipeline

## Completed M8A.2b pipeline

`scripts/build-m8a-candidate.py` builds `m8a-initial-atv-r1` from locked inputs. It aborts on a pre-existing final output or protected-input hash mismatch, uses transactional staging, and only loop-mounts staging copies.

1. Hash-lock stock container, rollback reference, stock vendor/vendor_dlkm, stock AVB payloads, and AOSP inputs.
2. Unsparse staging copies of AOSP system, product, and system_ext.
3. Merge the system_ext filesystem root into system at `/system_ext`, preserving `/system/system_ext -> /system_ext`; run e2fsck/debugfs checks.
4. Add AVB hashtrees to rebuilt system and product with flags 0 and no FEC. Retained vendor/vendor_dlkm keep their stock bytes and stock FEC.
5. Rebuild the four-partition LP layout and create mixed-key vbmeta: test root/system chain plus locked stock vendor chain.
6. Package using `tools/pack_image_preserving.py`: replace only super.fex, vbmeta.fex, vbmeta_system.fex and their V companions.
7. Validate IMAGEWTY, LP extraction/layout, AVB, ext4 labels/ATV contents, ELF32 spot checks, source-after hashes, and SHA256SUMS.

The old Test8r2 builder and `tools/pack_image.py` are not M8A tooling.

## Preservation and reproducibility

Stock fstab/LP metadata has no system_ext logical partition or mount. The candidate therefore has no system_ext_a; it merges AOSP system_ext into system_a and replaces product_a. Vendor, vendor_dlkm, and stock vbmeta_vendor remain exact.

A rebuild can legitimately produce different ext4/signed/super/vbmeta bytes because e2fsck/resize and ext4 metadata are not bit-for-bit reproducible. Acceptance is defined by locked source hashes, provenance, preservation audit, and validation, not by a prior candidate hash.

The independently retained validation record, rather than the builder command log alone, is in [m8a-initial-atv-r1.md](m8/candidates/m8a-initial-atv-r1.md). It documents the final parser, LP, ext4, AVB, ELF, source-lock, and checksum results. No raw validation scratch is retained.
