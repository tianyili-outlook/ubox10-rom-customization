# M8 build guide

## Product boundary

M8A uses ARM32 Android 12 TV system/product content with the stock device-specific stack. It preserves boot, kernel, vendor, vendor_dlkm, DTBO, TEE, graphics, media, DRM, wireless, and the established recovery path.

Stock fstab and LP metadata have no `system_ext` logical partition. The build therefore merges the AOSP system_ext filesystem at `/system_ext` inside `system_a`, preserves `/system/system_ext -> /system_ext`, replaces `product_a`, and keeps the four-partition LP schema.

| Logical partition | Bytes |
|---|---:|
| system_a | 1651167232 |
| vendor_a | 119066624 |
| product_a | 272629760 |
| vendor_dlkm_a | 6680576 |
| A-group free | 1163292672 |

## Locked inputs

| Input | Locked value |
|---|---|
| AOSP branch | `android12-release` |
| `device/google/atv` HEAD | `3ce48358b7e06ab1f1a1b713fb0f285aaa0983ca` |
| Manifest HEAD | `8e7a52179c1704bc445f83efde08a6025acbf358` |
| Local AOSP output | `/home/tianyi/ubox10-aosp/out/target/product/ubox10` |
| Stock container | `x12-1024.img`, 2018890752 bytes, SHA-256 `371A653604618E8B78786F279EA6F64E5D1028B430C9B41F330B08456A264065` |
| Preferred rollback | Test8r2, 2005954560 bytes, SHA-256 `6A52F3388E9ABF6AFA8A701CFD7198FE6C0090F16531F6E3BD3949E760892EC8` |

The AOSP tree, stock image, extracted payloads, rollback image, and candidate outputs are local ignored inputs. A Git clone alone cannot rebuild the current candidate chain.

## Candidate chain

The original M8A r1-r13 chain established the bootable Android 12 TV product and remains preserved for provenance. The accepted working image is now the M8B native rc-core r5 derivative; its reproducible configs and builders are under `configs/candidates/m8b-rc-core-*` and `scripts/build-m8b-rc-core-*`.

Run from the repository root on the verified Windows + WSL environment:

```powershell
python scripts/prepare-candidate-inputs.py
python scripts/build-m8a-candidate.py
python scripts/build-m8a-r2-candidate.py
python scripts/build-m8a-r3-candidate.py
python scripts/build-m8a-r4-candidate.py
python scripts/build-m8a-r5-candidate.py
python scripts/build-m8a-r6-candidate.py
```

The early r1-r6 stages are intentionally retained because each stage hash-locks and consumes its predecessor:

| Stage | Change |
|---|---|
| r1 | Build ATV system/product, merge system_ext, rebuild LP/AVB/IMAGEWTY |
| r2 | Add ext4 metadata image and download-map entry |
| r3 | Repair dlinfo CRC |
| r4 | Add VFAT media_data image and descriptor |
| r5 | Replace top-level vbmeta with keyless verification-disabled metadata |
| r6 | Restore stock interleaved A/B LP table order |

Candidate configs under `configs/candidates/` are the machine-readable sizes, hashes, geometry, and predecessor contracts. Rebuilt ext4/super/container bytes are not guaranteed bit-for-bit reproducible; acceptance is based on locked inputs, structural checks, preservation audits, and the recorded final artifact hash.

M8B r1-r5 preserves the ARM32 userspace and hardware-facing vendor stack while replacing the legacy `multi_ir → uinput` remote path with native kernel rc-core. r5 is device accepted. The next permitted candidate, if audio root cause is proven, must be a single-variable audio-focused derivative of r5; it must not include IME, exFAT, graphics, thermal, DRM, CEC or legacy-input cleanup.

## Checks

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

Clean-clone tests exercise parsers, configs, and builders. Artifact-specific r2-r6 tests skip until their ignored local outputs exist, then validate the actual images.

Tool provenance is in [`tools/README.md`](../tools/README.md). Current hardware/runtime evidence is in [`docs/m8/research/current-device/`](m8/research/current-device/). Useful upstream references are [AOSP ATV](https://android.googlesource.com/device/google/atv/+/refs/heads/android12-release/), [TrebleDroid](https://github.com/TrebleDroid/device_phh_treble), [LineageOS ATV](https://github.com/LineageOS/android_device_google_atv), and [AOSP linkerconfig](https://android.googlesource.com/platform/system/linkerconfig/+/refs/heads/android12-release/); none is a drop-in UBOX10 image.
