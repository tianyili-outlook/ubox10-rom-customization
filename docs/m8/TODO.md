# M8 TODO

## 已验收基线

- [x] `m8b-rc-core-r5`：boot、Projectivy、native rc-core/repeat、exact `.kl`、DPAD/OK/BACK/HOME/Volume/Power/Settings→MENU。
- [x] Wi-Fi、Internet、Android connectivity/DNS、Wi-Fi ADB `192.168.1.9:7896`。
- [x] Ethernet、Internet、Ethernet ADB。
- [x] Bluetooth service、扫描/配对、iPhone bonding、Bluetooth gamepad HID/UI 控制。
- [x] USB host/EHCI/Mass Storage/SCSI/block/partition/vold public volume。
- [x] H.264 与 HEVC 1080p Allwinner OMX/Cedar hardware decode。
- [x] 保留 `m8a-initial-atv-r13` 与 stock/Test8r2 回滚；硬件事实保持 H616/sun50iw9。

## 当前：音频 primary output — HIGH

- [x] 对齐 r5、r13、Test8r2/stock 的 kernel config、DT sound nodes、machine driver 与 Apollo HAL 静态 card map；确认 DT 未随 M8B 改变，HAL 可识别 `ahubhdmi`。
- [x] 证伪“只把 `sndhdmi` 改为 `ahubhdmi` 即可恢复 primary output”；该结论不满足构建候选条件。
- [ ] 在同步 logcat 下做一次非持久 `vendor.audio-hal`/audioserver restart，捕获首次 `adev_open`、`audio_route_init`、missing mixer control 与最终 errno。
- [ ] 用该首错确认是 legacy `audio_mixer_paths.xml` control 合同、stock BSP 二进制差异或其他具体分支；不按 card name 猜测。
- [ ] 若存在单变量高置信修复，只构建一个 audio-focused 候选并做限定离线验证；不刷机。

## 独立功能项

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
