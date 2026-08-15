# M8B audio-r1 candidate

状态：**READY TO FLASH — OFFLINE CHECKED**。本轮未刷机。

直接基线：设备验收的 `m8b-rc-core-r5`，SHA-256 `7B4D3E28D37CE242F92FF259BB43590EDF422630DA7B515D66E4DF1A000CFA98`。

## 唯一修复变量

confirmed 首错为 unchanged `/vendor/lib/hw/audio.primary.apollo.so` 在进入 `adev_open` 前无法解析 `DT_NEEDED libaudioroute.so`。r5 完全缺少 VNDK APEX；Test8r2 exact `/system/apex/com.android.vndk.current` 的 runtime name 为 `com.android.vndk.v31`，并通过 VNDK namespace 暴露 ARM32 `libaudioroute.so`。

r1 把 Test8r2 的完整 145-entry flattened VNDK APEX 原样恢复到 r5 的同一路径。未修改 `audio_mixer_paths.xml`、`audio_platform_info.xml`、kernel/DTS、machine driver、vendor、boot 或已验收输入链。

## 候选与哈希

| 工件 | 大小 | SHA-256 |
|---|---:|---|
| `out/candidates/m8b-audio-r1/x12-m8b-audio-r1.img` | 1025951744 | `298DCA11DBDFDC81028869C01866411C634FC2C7B979EDA3FB0346BF7434DBDD` |
| kernel Image | 23029768 | `FE23BEEAE10389EA13575CA266AF45797F22BCF9BDBA7037AF6F7A8B3148C5E2` |
| `boot.fex` | 67108864 | `0A9473513B309BA3168242500658F35D96EC40B49CA91E33C1068861F8756678` |
| `system_a` | 1651167232 | `E621B672A30EF1D04645AE3EB225AFEACF414969158A0D96D05C60C105283AFE` |
| `super.img` | 846153208 | `373608B36A0E0117FABF0EFC6B5AF4357E3E5B3B1C73319AAD94F3AEA7B1856F` |
| `vbmeta_system.fex` | 1472 | `AD2D6ECC3A4D63FCB58EA665E6FEBF999E7533A8B3F178CC149A7E0ECB6D97CE` |
| `libaudioroute.so` | 11640 | `BB5393CE70CD1A4AD9ED62814339CA3695788532242708B0D46DAED87D603623` |

## 限定验证

- VNDK 子树 145 个条目、141 个 regular files、17512825 bytes 与 Test8r2 逐项一致；uid/gid/mode/SELinux xattr 保持。
- `apex_manifest.pb` 标识 `com.android.vndk.v31`；`vndkcore.libraries.31.txt` 包含 `libaudioroute.so`。
- Apollo HAL 与 `libaudioroute.so` 均为 ARM32；两者全部直接和传递 `DT_NEEDED` 离线可解析。
- r5 boot/kernel/ramdisk、vendor_boot、vendor/product/vendor_dlkm、Projectivy、Power、native rc-core/keylayout 与 `multi_ir` disabled 状态保持。
- payload 差异仅 `system_a`、`super.fex`、`Vsuper.fex`、`vbmeta_system.fex`、`Vvbmeta_system.fex`。
- LP、AVB、四分区 e2fsck、split SELinux、ELF、IMAGEWTY 外层校验通过；focused tests 与 `git diff --check` 通过。

## 首测

刷写需另行授权。启动后先确认 `com.android.vndk.v31` active、`/apex/com.android.vndk.v31/lib/libaudioroute.so` 存在且旧缺库日志消失；再确认 primary HAL/output，并播放已知 HEVC+AAC。若暴露 mixer/ALSA 新首错，只采集证据，不混入本候选。
