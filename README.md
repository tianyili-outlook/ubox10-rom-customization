# UBOX10 M8

UBOX10 H616/sun50iw9 的 Android TV 12 个人 ROM 项目。Android userspace 为纯 ARM32；M8B 使用 ARM64 Linux 5.4.125 重建 kernel 实现 native rc-core，同时保留 stock boot ramdisk、vendor_boot、vendor、vendor_dlkm、TEE、graphics、media、DRM、wireless 与分区合同。

## 当前状态

- 当前设备验收基线：`m8b-ime-r1`，状态为 **DEVICE ACCEPTED / IME PASS**。它继承 `m8b-audio-r2` 的全部验收项，并已在 fresh-data 首启中自动 enable/default AOSP LeanbackIME；Projectivy、物理遥控、Wi-Fi 与 1920×1080 电视文字输入均通过。
- r2 已启用正确的 Android 12 Treble/VNDK 产品合同；Apollo HAL 进入 `adev_open`，AudioFlinger 建立 primary output，ALSA 识别 `ahubhdmi` 为 card 3 / `AUDIO_HDMI`，VLC 的 HEVC+AAC 实测画面与 HDMI TV 声音正常。
- legacy missing mixer controls、`nano_input_open -3`/input path 与 permissive SELinux AVC 仅作为非阻塞后续项保留，本轮不修复。
- AOSP LeanbackIME 已通过可逆 userdata 证明和刷机后的物理设备验收；单独 reboot persistence 未另行执行并作为非阻塞项接受。独立 `m8b-remote-r1` 已构建为 **READY TO FLASH**，等待单独明确刷机授权后验收官方 Google TV iOS Remote + phone text input。
- 独立待办：exFAT、graphics artifacts、完整 resume recovery、HDMI CEC、Settings/Menu 物理复验，以及带物理画面/商业服务账号的 DRM 播放验证；不得把 Widevine L3 存在等同于流媒体认证。
- 强制回滚：`m8a-initial-atv-r13`，SHA-256 `1D367F7091A7BD6A0791B2CFE45E7AAB551E0312D8C68136548A4927354A8E06`。

当前设备验收镜像：`out/candidates/m8b-ime-r1/x12-m8b-ime-r1.img`，1028208640 bytes，SHA-256 `B89612D5004BA3D8214F21E22E4BED7BFBA5B2F8FE441F9364315F851F1FE240`。

## 项目入口

| 内容 | 文档 |
|---|---|
| 当前事实、候选历史、下一步 | [M8 状态](docs/m8/STATUS.md) |
| 有序待办 | [M8 TODO](docs/m8/TODO.md) |
| 架构、输入与 M8A/M8B 构建链 | [构建说明](docs/BUILD.md) |
| 设备测试与回滚 | [设备测试](docs/DEVICE_TEST.md) |
| 已验收音频基线 | [M8B audio-r2](docs/m8/candidates/m8b-audio-r2.md) |
| 当前设备验收基线 | [M8B ime-r1](docs/m8/candidates/m8b-ime-r1.md) |
| 当前待刷候选 | [M8B remote-r1](docs/m8/candidates/m8b-remote-r1.md) |
| Test8r2 硬件与运行时证据 | [运行时基线](docs/m8/research/current-device/runtime-baseline.md) |

`configs/candidates/` 与 `scripts/build-m8a*.py`、`scripts/build-m8b*.py` 是候选构建来源；`tests/` 提供 clean-clone 与本地工件限定检查。原始固件、候选镜像、原始日志、APK 与解包树保留在本地 ignored 路径。

M7 冻结于 Git tag [`m7`](https://github.com/tianyili-outlook/ubox10-rom-customization/tree/m7)，本分支不复制 M7 专用构建器和实验记录。
