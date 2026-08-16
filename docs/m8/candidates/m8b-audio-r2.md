# M8B audio-r2 candidate

状态：**DEVICE ACCEPTED / AUDIO PASS**。

直接基线：`m8b-audio-r1`，SHA-256 `298DCA11DBDFDC81028869C01866411C634FC2C7B979EDA3FB0346BF7434DBDD`。

## 根因与唯一修复变量

r1 实机已确认 `com.android.vndk.v31` active 且 `libaudioroute.so` 存在，但 `ro.treble.enabled=false` 使 Android 12 linkerconfig 走 legacy 配置：运行时没有 VNDK namespace，也没有 `default→vndk` link，unchanged Apollo HAL 因此仍无法解析该库。

源码产品加入 `PRODUCT_SHIPPING_API_LEVEL := 31`、`BOARD_VNDK_VERSION := current`，并显式纳入 `com.android.vndk.current`。AOSP 重建确认完整合同成立。r2 候选以 r1 为直接基线，只物化决定运行时路径的 `/system/build.prop` 单行变化：`ro.treble.enabled=false` 改为 `true`。未修补生成的 `ld.config.txt`，未向 `/vendor/lib` 复制库。

## 候选与哈希

| 工件 | 大小 | SHA-256 |
|---|---:|---|
| `out/candidates/m8b-audio-r2/x12-m8b-audio-r2.img` | 1025951744 | `B39300CB3E335D75C9D61594CD94565D9C24FC92F467F9050CD1E604D87E9C2C` |
| kernel Image | 23029768 | `FE23BEEAE10389EA13575CA266AF45797F22BCF9BDBA7037AF6F7A8B3148C5E2` |
| `boot.fex` | 67108864 | `0A9473513B309BA3168242500658F35D96EC40B49CA91E33C1068861F8756678` |
| `system_a` | 1651167232 | `0ADDD79774E03839DD00229B2DD90939D6BD235B5B5B69B803F423AFB23640B2` |
| `super.img` | 846153236 | `F25708E0DC7E57903F3FF93A18E4EDF2A7BC11CC2E5BAF29044E6F5F9AB00D69` |
| `vbmeta_system.fex` | 1472 | `76A649A886A4E7F66950C763207C369EF849F020337CA61D85F4F685BEFFECA8` |
| 离线生成 `ld.config.txt` | － | `A91778B05CDB7E56DFDD73F0491034FEF2A2792AEB06E7EF32F0349AA8F12982` |

## AOSP 与候选验证

- AOSP：`DeviceVndkVersion=current`、`ProductVndkVersion=current`、`Treble_linker_namespaces=true`、`Enforce_vintf_manifest=true`、`Platform_vndk_version=31`、`ro.treble.enabled=true`。
- `systemimage`、`productimage`、`systemextimage`、`check-vintf-all`、SELinux policy 构建通过；没有新增 VINTF/SELinux blocker。
- r2 system 文件差异仅 `/system/build.prop`；mode `0600`、uid/gid `0:0`、inode 类型和 SELinux label 保持。r1 exact VNDK APEX 与 `/system/etc/linker.config.pb` 原字节不变。
- 匹配 SP1A.210812.015 源码构建的 host linkerconfig 对 r2 system/vendor/product 输入生成 `[vendor]`、VNDK namespace、`/apex/com.android.vndk.v31/${LIB}` search path，且 `namespace.default.link.vndk.shared_libs` 包含 `libaudioroute.so`。
- boot/kernel/ramdisk、vendor_boot、vendor/product/vendor_dlkm、audio XML、DTS/machine driver、rc-core/keylayout、Projectivy 和 `multi_ir` disabled 状态保持。
- payload 差异仅 `system_a`、`super.fex`、`Vsuper.fex`、`vbmeta_system.fex`、`Vvbmeta_system.fex`。
- LP、AVB、四分区 e2fsck、split SELinux、ELF、IMAGEWTY 外层校验、focused tests 与 `git diff --check` 通过。

## 设备验收

- `sys.boot_completed=1`。
- `ro.treble.enabled=true`、`ro.vndk.version=31`，`com.android.vndk.v31` active。
- 运行时 VNDK namespace 与 `default→vndk` link 包含 `libaudioroute.so`。
- unchanged Apollo HAL 到达 `adev_open`；AudioFlinger 加载 primary audio interface 并建立 primary output。
- ALSA 识别 `ahubhdmi` 为 card 3 / `AUDIO_HDMI`；kernel 报告 `HDMI Audio Enable Successfully`。
- VLC 播放已知 HEVC+AAC 正常，时间线推进且 HDMI TV 音频确认工作。
- ADB-only VP9 补验为 **HARDWARE-RUNTIME PASS**：verified `V_VP9` 资产由 VLC 交给 `OMX.allwinner.video.decoder.vp9`，Cedar `CreateVideoDecoder`，远程位置推进后到达 EOF，无 fatal codec/VPU failure。
- MediaDrm 补验可打开 Google Widevine CDM 16.1.0，`securityLevel=L3`，connected/max HDCP 均为 `NONE`；AVC/HEVC/VP9 均不要求 secure decoder，未发现 secure codec 名称。

验收期间仍观察到 legacy missing mixer controls、`nano_input_open -3`/input path 与 permissive SELinux AVC。它们不阻塞当前 primary HDMI playback，仅作为后续清理或调查项，不改变 r2 的 **AUDIO PASS** 结论。远程 VP9 证据不声称物理画质或逐帧正确性；Widevine L3 不等同于 L1、secure playback 或 Netflix/Disney+/其他商业服务认证与实际播放。
