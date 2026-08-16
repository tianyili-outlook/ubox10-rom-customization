# M8 TODO

## 已验收基线

- [x] `m8b-rc-core-r5`：boot、Projectivy、native rc-core/repeat、exact `.kl`、DPAD/OK/BACK/HOME/Volume/Power/Settings→MENU。
- [x] Wi-Fi、Internet、Android connectivity/DNS、Wi-Fi ADB `192.168.1.9:7896`。
- [x] Ethernet、Internet、Ethernet ADB。
- [x] Bluetooth service、扫描/配对、iPhone bonding、Bluetooth gamepad HID/UI 控制。
- [x] USB host/EHCI/Mass Storage/SCSI/block/partition/vold public volume。
- [x] H.264 与 HEVC 1080p Allwinner OMX/Cedar hardware decode。
- [x] `m8b-audio-r2`：Treble/VNDK runtime 合同、Apollo HAL、AudioFlinger primary output、ALSA HDMI 与 VLC HEVC+AAC HDMI TV 音频。
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
- [ ] 后续独立清理 legacy missing mixer controls；不纳入已验收 r2 的修复范围。
- [ ] 后续独立调查 `nano_input_open -3`/input path；当前不阻塞 HDMI primary output。
- [ ] 后续独立收敛 permissive SELinux AVC；当前仅记录，不在音频验收收尾中修改策略。

## 独立功能项

- [ ] **延期：遥控器 Settings/Menu 语义分离。** 当前物理 Menu 与 Settings 两键均打开 Projectivy menu；目标为 Menu→Projectivy menu、Settings→Android system Settings。该项独立于已验收的 rc-core/audio，不修改当前 input stack；未来实现必须保持 DPAD/OK/BACK/HOME/Volume/Power/Menu 行为不回归。
- [ ] 增加可用 TV soft IME；当前 `ime list -a` 与 default IME 均为空。
- [ ] 增加 exFAT 支持；USB host/storage 已通过，当前仅 filesystem unsupported。
- [ ] 复现并定位选中态渐变噪点及启用 Wi-Fi 时短暂撕裂/黑屏。
- [ ] 完整验证 suspend/resume 后 Wi-Fi、Bluetooth 与网络恢复。
- [ ] 验收 DRM/Widevine、HDMI CEC 与 VP9 runtime decode。

## 后续系统质量里程碑

- [ ] 限定分析 boot critical path、UART errors/retries、CPU governor/frequency、thermal/idle、graphics renderer/allocator/mapper/SF 与残余 audio retry loop。
- [ ] 在独立候选中清理已证明无依赖的 legacy `multi_ir/uinput` 工件；不得在无依赖证明时删除 `/system/lib/libinput.so` 等通用库。
- [ ] 保持 Mouse mode dropped；不重新引入 vendor mouse framework。
- [ ] 仅在获得匹配本板 64 位 graphics/media userspace provider 后重启 AArch64 Android userspace 工作。
