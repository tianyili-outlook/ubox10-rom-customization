# M8 TODO

## 已验收基线

- [x] `m8b-rc-core-r5`：boot、Projectivy、native rc-core/repeat、exact `.kl`、DPAD/OK/BACK/HOME/Volume/Power/Settings→MENU。
- [x] Wi-Fi、Internet、Android connectivity/DNS、Wi-Fi ADB `192.168.1.9:7896`。
- [x] Ethernet、Internet、Ethernet ADB。
- [x] Bluetooth service、扫描/配对、iPhone bonding、Bluetooth gamepad HID/UI 控制。
- [x] USB host/EHCI/Mass Storage/SCSI/block/partition/vold public volume。
- [x] H.264 与 HEVC 1080p Allwinner OMX/Cedar hardware decode。
- [x] `m8b-audio-r2`：Treble/VNDK runtime 合同、Apollo HAL、AudioFlinger primary output、ALSA HDMI 与 VLC HEVC+AAC HDMI TV 音频。
- [x] VP9 hardware runtime：VLC 使用 `OMX.allwinner.video.decoder.vp9` / Cedar；已验证 VP9 资产、远程播放位置推进、EOF 与无 fatal codec/VPU failure。
- [x] DRM/Widevine 设备状态：MediaDrm 可打开 Google Widevine 16.1.0，L3，HDCP `NONE`；AVC/HEVC/VP9 不要求 secure decoder。该项不代表 L1、secure playback 或商业服务认证。
- [x] 保留 `m8a-initial-atv-r13` 与 stock/Test8r2 回滚；硬件事实保持 H616/sun50iw9。

## 音频 primary output — DEVICE ACCEPTED / AUDIO PASS

- [x] 对齐 r5、r13、Test8r2/stock 的 kernel config、DT sound nodes、machine driver 与 Apollo HAL 静态 card map；确认 DT 未随 M8B 改变，HAL 可识别 `ahubhdmi`。
- [x] 证伪“只把 `sndhdmi` 改为 `ahubhdmi` 即可恢复 primary output”；该结论不满足构建候选条件。
- [x] clean restart 已取得首错：Apollo HAL 在 `adev_open` 前因 `libaudioroute.so` 缺失而 `dlopen` 失败。
- [x] 确认 Test8r2 exact `com.android.vndk.v31` 提供 ARM32 `libaudioroute.so`，并定位到 ubox10 AOSP 产品未启用/纳入 VNDK APEX。
- [x] 构建 `m8b-audio-r1`：仅恢复完整 exact Test8r2 VNDK APEX；离线依赖闭包、LP/AVB/e2fsck/SELinux/ELF/外层检查通过。
- [x] r1 实机确认 exact VNDK APEX active、`libaudioroute.so` 存在，但 `ro.treble.enabled=false` 且运行时无 VNDK namespace / `default→vndk` link；根因收敛为不完整 AOSP Treble/VNDK 产品配置。
- [x] 加入 `PRODUCT_SHIPPING_API_LEVEL := 31`、`BOARD_VNDK_VERSION := current` 和 `com.android.vndk.current` 产品规则；重建确认 Device/Product VNDK、Treble linker namespace、VINTF enforcement 和 `ro.treble.enabled=true`。
- [x] 构建 `m8b-audio-r2`：以 r1 为基线，仅物化 `ro.treble.enabled=true`；精确 Android 12 linkerconfig 离线生成 vendor/VNDK namespace，`default→vndk` 包含 `libaudioroute.so`。
- [x] r2 实机确认 `sys.boot_completed=1`、Treble/VNDK namespace 与 `default→vndk` 合同成立、Apollo HAL 到达 `adev_open`、primary output 创建、`ahubhdmi` card 3 / `AUDIO_HDMI` 工作，VLC HEVC+AAC HDMI TV 音频通过。
- [x] system-quality audit 将 legacy missing mixer controls 定为 **P2 boot-only/inert noise**；当前保留日志窗口与 62 秒样本均为 0，不为清日志修改已验收 audio stack。
- [ ] **INFO / 等待明确 input 用例或现场：**`nano_input_open -3` 当前保留日志窗口与 62 秒样本均为 0；input capture 未测试，不声明 PASS/FAIL，且不阻塞 HDMI primary output。
- [ ] **P1 / 独立候选且现场验收后：**收敛 permissive SELinux active-path AVC；已分组为 CEC extcon、system_suspend wakeup sysfs 与 audio HAL uevent socket。不得直接修改当前 accepted device policy。

## 独立功能项

- [ ] **延期至现场：遥控器 Settings/Menu 物理复验与语义分离。** 既有 r5 证据为两键均打开 Projectivy menu；目标为 Menu→Projectivy menu、Settings→Android system Settings。不得远程修改当前 input stack。
- [ ] 增加可用 TV soft IME；当前 `ime list -a` 与 default IME 均为空。
- [ ] 增加 exFAT 支持；USB host/storage 已通过，当前仅 filesystem unsupported。
- [ ] 复现并定位选中态渐变噪点及启用 Wi-Fi 时短暂撕裂/黑屏。
- [ ] **延期至现场：**完整验证 suspend/resume 后 Wi-Fi、Bluetooth、网络与 ADB 恢复。
- [ ] **延期至现场：**HDMI CEC 实机交互。
- [ ] **延期至物理画面/服务账号：**Widevine 受保护内容和目标商业流媒体实际播放/认证；当前只证明 L3 plugin operational，不声称 Netflix、Disney+ 或其他服务认证。

## 后续系统质量里程碑

- [x] 完成限定只读 system-quality audit：无 P0；stability、retry loop、audio residual、SELinux、CPU/thermal/idle、graphics 与 memory 证据见 `docs/m8/device-tests/20260816-m8b-system-quality-audit/`。
- [ ] **P1 / medium confidence：**隔离调查低负载下 CPU 五次样本均为 1.512 GHz 且 ThermalService `HAL Ready=false`；active governor 因权限未读到。不得在线改 governor；候选需现场 thermal soak。
- [ ] **P1 / 先现场关联：**Projectivy/HWUI 99.74% jank telemetry 与 `FrameCompleted/GpuCompleted=INT64_MAX`；当前只证明 frame-metrics 异常，不声称已复现物理画面卡顿/噪点。
- [ ] **P2 / 默认不修：**Wi-Fi HAL link-layer statistics 每约 3 秒返回 `ERROR_UNKNOWN`；网络 ADB 稳定且 Wi-Fi 进程未重启。
- [ ] 在独立候选中清理已证明无依赖的 legacy `multi_ir/uinput` 工件；不得在无依赖证明时删除 `/system/lib/libinput.so` 等通用库。
- [ ] 保持 Mouse mode dropped；不重新引入 vendor mouse framework。
- [ ] 仅在获得匹配本板 64 位 graphics/media userspace provider 后重启 AArch64 Android userspace 工作。
