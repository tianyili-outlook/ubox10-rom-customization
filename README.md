# UBOX10 M8

UBOX10 H616/sun50iw9 的 Android TV 12 个人 ROM 项目。Android userspace 为纯 ARM32；M8B 使用 ARM64 Linux 5.4.125 重建 kernel 实现 native rc-core，同时保留 stock boot ramdisk、vendor_boot、vendor、vendor_dlkm、TEE、graphics、media、DRM、wireless 与分区合同。

## 当前状态

- 当前设备验收基线：`m8b-rc-core-r5`。Projectivy、native rc-core 遥控、Wi-Fi、Ethernet、Bluetooth/HID、USB host/storage 枚举、H.264 与 HEVC 硬解通过。
- 音频首错已确认：unchanged `/vendor/lib/hw/audio.primary.apollo.so` 在进入 `adev_open` 前因缺少 VNDK `libaudioroute.so` 而 `dlopen` 失败。Test8r2 的 exact `com.android.vndk.v31` APEX 包含该库；本机 ubox10 AOSP 产品未启用/纳入 VNDK APEX。
- `m8b-audio-r1` 已恢复完整 exact Test8r2 ARM32 VNDK APEX 合同并通过离线检查，等待单独授权刷写。mixer control 与 ALSA topology 仅保留为 HAL 成功加载后的第二层风险。
- 独立待办：IME、exFAT、graphics artifacts、完整 resume recovery、DRM/Widevine、HDMI CEC、VP9 runtime。
- 强制回滚：`m8a-initial-atv-r13`，SHA-256 `1D367F7091A7BD6A0791B2CFE45E7AAB551E0312D8C68136548A4927354A8E06`。

当前待测镜像：`out/candidates/m8b-audio-r1/x12-m8b-audio-r1.img`，1025951744 bytes，SHA-256 `298DCA11DBDFDC81028869C01866411C634FC2C7B979EDA3FB0346BF7434DBDD`。当前实机验收基线仍为 r5。

## 项目入口

| 内容 | 文档 |
|---|---|
| 当前事实、候选历史、下一步 | [M8 状态](docs/m8/STATUS.md) |
| 有序待办 | [M8 TODO](docs/m8/TODO.md) |
| 架构、输入与 M8A/M8B 构建链 | [构建说明](docs/BUILD.md) |
| 设备测试与回滚 | [设备测试](docs/DEVICE_TEST.md) |
| 当前候选差异与检查 | [M8B audio-r1](docs/m8/candidates/m8b-audio-r1.md) |
| Test8r2 硬件与运行时证据 | [运行时基线](docs/m8/research/current-device/runtime-baseline.md) |

`configs/candidates/` 与 `scripts/build-m8a*.py`、`scripts/build-m8b*.py` 是候选构建来源；`tests/` 提供 clean-clone 与本地工件限定检查。原始固件、候选镜像、原始日志、APK 与解包树保留在本地 ignored 路径。

M7 冻结于 Git tag [`m7`](https://github.com/tianyili-outlook/ubox10-rom-customization/tree/m7)，本分支不复制 M7 专用构建器和实验记录。
