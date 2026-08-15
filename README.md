# UBOX10 M8

UBOX10 H616/sun50iw9 的 Android TV 12 个人 ROM 项目。Android userspace 为纯 ARM32；M8B 使用 ARM64 Linux 5.4.125 重建 kernel 实现 native rc-core，同时保留 stock boot ramdisk、vendor_boot、vendor、vendor_dlkm、TEE、graphics、media、DRM、wireless 与分区合同。

## 当前状态

- 当前设备验收基线：`m8b-rc-core-r5`。Projectivy、native rc-core 遥控、Wi-Fi、Ethernet、Bluetooth/HID、USB host/storage 枚举、H.264 与 HEVC 硬解通过。
- 当前最高优先级：音频 primary output 失败。AudioFlinger 无 primary module，Apollo HAL 与 ALSA cards 均存在。
- 已证伪仅把 `sndhdmi` 改成 `ahubhdmi` 的方案；Apollo HAL 原生识别两者。当前最强差异是 legacy `audio_mixer_paths.xml` controls 与 exact H616 codec/machine driver 不匹配，下一步先捕获 `adev_open` 的首次失败分支，不制作猜测型候选。
- 独立待办：IME、exFAT、graphics artifacts、完整 resume recovery、DRM/Widevine、HDMI CEC、VP9 runtime。
- 强制回滚：`m8a-initial-atv-r13`，SHA-256 `1D367F7091A7BD6A0791B2CFE45E7AAB551E0312D8C68136548A4927354A8E06`。

当前镜像：`out/candidates/m8b-rc-core-r5/x12-m8b-rc-core-r5.img`，1007982592 bytes，SHA-256 `7B4D3E28D37CE242F92FF259BB43590EDF422630DA7B515D66E4DF1A000CFA98`。

## 项目入口

| 内容 | 文档 |
|---|---|
| 当前事实、候选历史、下一步 | [M8 状态](docs/m8/STATUS.md) |
| 有序待办 | [M8 TODO](docs/m8/TODO.md) |
| 架构、输入与 M8A/M8B 构建链 | [构建说明](docs/BUILD.md) |
| 设备测试与回滚 | [设备测试](docs/DEVICE_TEST.md) |
| 当前候选差异与检查 | [M8B rc-core-r5](docs/m8/candidates/m8b-rc-core-r5.md) |
| Test8r2 硬件与运行时证据 | [运行时基线](docs/m8/research/current-device/runtime-baseline.md) |

`configs/candidates/` 与 `scripts/build-m8a*.py`、`scripts/build-m8b*.py` 是候选构建来源；`tests/` 提供 clean-clone 与本地工件限定检查。原始固件、候选镜像、原始日志、APK 与解包树保留在本地 ignored 路径。

M7 冻结于 Git tag [`m7`](https://github.com/tianyili-outlook/ubox10-rom-customization/tree/m7)，本分支不复制 M7 专用构建器和实验记录。
