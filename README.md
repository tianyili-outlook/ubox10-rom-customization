# UBOX10 M8

UBOX10 H616/sun50iw9 的 Android TV 12 个人 ROM 项目。Android userspace 为纯 ARM32；M8B 使用 ARM64 Linux 5.4.125 重建 kernel 实现 native rc-core，同时保留 stock boot ramdisk、vendor_boot、vendor、vendor_dlkm、TEE、graphics、media、DRM、wireless 与分区合同。

## 当前状态

- 当前设备验收基线：`m8b-remote-r1`，状态为 **DEVICE ACCEPTED / REMOTE PASS**，继承 **AUDIO PASS** 与 **IME PASS**。Projectivy、物理遥控、Wi-Fi、Bluetooth、AOSP LeanbackIME、official Google TV iPhone discovery/pair/navigation/phone keyboard 均已现场通过。
- r2 已启用正确的 Android 12 Treble/VNDK 产品合同；Apollo HAL 进入 `adev_open`，AudioFlinger 建立 primary output，ALSA 识别 `ahubhdmi` 为 card 3 / `AUDIO_HDMI`，VLC 的 HEVC+AAC 实测画面与 HDMI TV 声音正常。
- legacy missing mixer controls、`nano_input_open -3`/input path 与 permissive SELinux AVC 仅作为非阻塞后续项保留，本轮不修复。
- Remote v2 运行时确认 CONNECT 首启默认授权、6466/6467、system_ext RRO 与 provider resource 均成立；官方 Google TV iPhone 的发现、配对、导航、音量与真实 EditText phone text PASS。配对手机占用 text-input session 时提示 `Use the keyboard on your mobile device` 属于接受的 Android TV 行为，不视为 LeanbackIME 回归。
- LeanbackIME 首次调用比后续调用慢、偶尔需按 OK 两三次，仅记录为低优先级可用性观察；尚未确认缺陷或根因。剩余路线优先进行 Settings/Menu 物理键语义分离，其后再处理 suspend/resume、graphics、CEC、thermal、exFAT、商业 DRM、SELinux 与 legacy 清理。
- 强制回滚：`m8a-initial-atv-r13`，SHA-256 `1D367F7091A7BD6A0791B2CFE45E7AAB551E0312D8C68136548A4927354A8E06`。

当前设备验收镜像：`out/candidates/m8b-remote-r1/x12-m8b-remote-r1.img`，1031723008 bytes，SHA-256 `F3B09E5565AC4ED4E5EE326D392622E7B036A8519B8444B966E77CC4751B814A`。

## 项目入口

| 内容 | 文档 |
|---|---|
| 当前事实、候选历史、下一步 | [M8 状态](docs/m8/STATUS.md) |
| 有序待办 | [M8 TODO](docs/m8/TODO.md) |
| 架构、输入与 M8A/M8B 构建链 | [构建说明](docs/BUILD.md) |
| 设备测试与回滚 | [设备测试](docs/DEVICE_TEST.md) |
| 已验收音频基线 | [M8B audio-r2](docs/m8/candidates/m8b-audio-r2.md) |
| 已验收 IME 里程碑 | [M8B ime-r1](docs/m8/candidates/m8b-ime-r1.md) |
| 当前设备验收基线 | [M8B remote-r1](docs/m8/candidates/m8b-remote-r1.md) |
| Test8r2 硬件与运行时证据 | [运行时基线](docs/m8/research/current-device/runtime-baseline.md) |

`configs/candidates/` 与 `scripts/build-m8a*.py`、`scripts/build-m8b*.py` 是候选构建来源；`tests/` 提供 clean-clone 与本地工件限定检查。原始固件、候选镜像、原始日志、APK 与解包树保留在本地 ignored 路径。

M7 冻结于 Git tag [`m7`](https://github.com/tianyili-outlook/ubox10-rom-customization/tree/m7)，本分支不复制 M7 专用构建器和实验记录。
