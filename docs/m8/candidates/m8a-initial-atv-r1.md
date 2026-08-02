# M8A initial ATV r1

ID: `m8a-initial-atv-r1`  
Status: BUILT - VERIFIED OFFLINE. It is not boot-tested, promoted, or flash-authorized. No bootability claim is made.

## Artifact

- Firmware: `out/candidates/m8a-initial-atv-r1/x12-m8a-initial-atv-r1.img`
- Size: 963391488
- SHA-256: `68029C3F5EE3BEFC2AFD6187A3EE3EA9D4BD0A2A4C10B4C686429232B18491C5`
- Base: stock `x12-1024.img`, SHA-256 `371A653604618E8B78786F279EA6F64E5D1028B430C9B41F330B08456A264065`

The removed rejected prefix-defective build began `8D8C`. It must never be used.

## Single primary change and preservation

AOSP system and system_ext are merged into system_a at `/system_ext`; `/system/system_ext -> /system_ext` remains. AOSP product replaces product_a. No system_ext_a exists because stock LP/fstab has no system_ext logical partition/mount.

Only super.fex, vbmeta.fex, vbmeta_system.fex and their V companions changed. Forty other stored outer payloads are exact. Vendor, vendor_dlkm, stock vbmeta_vendor, and Vvbmeta_vendor are exact.

Logical sizes: system 1651167232, vendor 119066624, product 272629760, vendor_dlkm 6680576. A-group use/free: 2049544192/1163292672.

## Independently retained offline validation record

This is the retained independent validator/Sol acceptance record, not a restatement of `01-commands.log`. No raw validation scratch is retained.

| Check | Command or method | Result |
|---|---|---|
| Candidate identity | SHA-256 and size | 963391488 bytes; `68029C3F5EE3BEFC2AFD6187A3EE3EA9D4BD0A2A4C10B4C686429232B18491C5` |
| Script regression checks | `py_compile` plus unittest | 6/6 PASS |
| IMAGEWTY structure | Full parser comparison and `sunxi_image_tool.py verify` | Prefix differences exactly 25,26,27; bytes 96..1023 exact; 46 entries; 40 preserved stored payloads; 10 V checks PASS |
| LP image | `simg2img` plus `lpdumps` | Raw super 3221225472; system/vendor/product/vendor_dlkm schema and exact sizes; use/free 2049544192/1163292672 |
| LP extraction | `lpunpack` | Exit 0; vendor/vendor_dlkm match locked hashes; extracted system/product equal retained representations |
| ext4 | WSL `e2fsck -fn` on system/product | Exit 0 |
| ext4 content | `debugfs` and validator/Sol direct checks | Merged /system_ext and symlink confirmed; ATV packages/overlays/properties and system_file SELinux labels confirmed; Sol also checked /system_ext and SystemUI.apk |
| AVB | `avbtool verify_image` mixed chain | Exit 0; flags, rollback indexes, descriptors, and FEC policy verified |
| ELF | Spot checks | app_process32 and retained vendor composer are ELF32 ARM EABI5 and use /system/bin/linker |
| Integrity/provenance | SHA256SUMS and protected source rehash | 16/16 SHA sums PASS; protected source rehashes PASS |
| VINTF | checkvintf | Unavailable |

AVB/dm-verity uses flags 0. Rebuilt system/product omit FEC; retained vendor/vendor_dlkm retain stock FEC. The mixed test-root/stock-vendor chain validates offline, but bootloader acceptance of the test root is the largest device-only risk.

## Device boundary and rollback

No media was prepared and no device was operated. Runtime Binder, HAL, SELinux, VINTF, graphics, media, DRM, Wi-Fi, Bluetooth, remote, CEC, audio, Ethernet, first boot, launcher/HOME/IME/provisioning remain unproven.

AwTvProvision is configured but absent; Projectivy/launcher/default HOME/IME are absent or unproven.

Rollback reference: Test8r2, 2005954560 bytes, SHA-256 `6A52F3388E9ABF6AFA8A701CFD7198FE6C0090F16531F6E3BD3949E760892EC8`. Use the [recovery readiness runbook](../../RECOVERY_RUNBOOK.md) only after explicit authorization.
