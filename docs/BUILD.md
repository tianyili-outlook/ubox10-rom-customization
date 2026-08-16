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

The original M8A r1-r13 chain established the bootable Android 12 TV product and remains preserved for provenance. `m8b-audio-r2` is the current device-accepted baseline. The current offline candidate is `m8b-ime-r1`, which adds only the source-built AOSP TV LeanbackIME product module.

Run from the repository root on the verified Windows + WSL environment:

```powershell
python scripts/prepare-candidate-inputs.py
python scripts/build-m8a-candidate.py
python scripts/build-m8a-r2-candidate.py
python scripts/build-m8a-r3-candidate.py
python scripts/build-m8a-r4-candidate.py
python scripts/build-m8a-r5-candidate.py
python scripts/build-m8b-audio-r1-candidate.py
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

M8B r1-r5 preserves the ARM32 userspace and hardware-facing vendor stack while replacing the legacy `multi_ir → uinput` remote path with native kernel rc-core. r5 is device accepted.

The ubox10 AOSP source product omitted `BOARD_VNDK_VERSION := current` and did not include `com.android.vndk.current`; the original AOSP `system` output therefore lacked the VNDK APEX before M8 assembly. `m8b-audio-r1` uses `configs/candidates/m8b-audio-r1.json`, `scripts/build-m8b-audio-r1-candidate.py`, and `scripts/import-m8-test8r2-vndk-apex.sh` to copy the hash-locked Test8r2 `/system/apex/com.android.vndk.current` subtree into an r5 system staging copy with metadata intact. It does not modify vendor, boot, audio XML, DTS or the accepted input stack.

For the local input milestone, apply `configs/aosp/m8b-ime-r1-leanback-ime.patch` to the locked AOSP tree and run `m LeanbackIME -j4` plus `m productimage -j4`. `scripts/build-m8b-ime-r1-candidate.py` consumes the locked AOSP product/APK and accepted `m8b-audio-r2`, preserves the accepted product `build.prop`, verifies that the filesystem delta is only `/app/LeanbackIME/**`, `/app` link count and the attributable NOTICE update, signs product AVB, rebuilds the same LP geometry, and rejects any system/vendor/vendor_dlkm change. Build with:

```powershell
python scripts/build-m8b-ime-r1-candidate.py
```

LeanbackIME declares itself default in its standard input-method metadata, so Android 12 can enable/select it when no prior IME exists; fresh-data/reboot persistence remains a physical-device gate. The following `m8b-remote-r1` remains separate and will reuse the proven Test9r2 TvRemoteProvider/RRO/Google Remote Service chain. No Remote Service or proprietary APK is part of `m8b-ime-r1`.

## Checks

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

Clean-clone tests exercise parsers, configs, and builders. Artifact-specific r2-r6 tests skip until their ignored local outputs exist, then validate the actual images.

Tool provenance is in [`tools/README.md`](../tools/README.md). Current hardware/runtime evidence is in [`docs/m8/research/current-device/`](m8/research/current-device/). Useful upstream references are [AOSP ATV](https://android.googlesource.com/device/google/atv/+/refs/heads/android12-release/), [TrebleDroid](https://github.com/TrebleDroid/device_phh_treble), [LineageOS ATV](https://github.com/LineageOS/android_device_google_atv), and [AOSP linkerconfig](https://android.googlesource.com/platform/system/linkerconfig/+/refs/heads/android12-release/); none is a drop-in UBOX10 image.
