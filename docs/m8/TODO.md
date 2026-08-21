# M8 TODO

## Freeze decision

`m8b-remote-r1` 已冻结为 **FROZEN / DEVICE-ACCEPTED Android 12 working baseline**，作为 Android 16 架构工作的稳定回退与功能对照。当前不再实施 Android 12 M8B feature、P1/P2 修复或清理；以下未完成项全部 **DEFERRED pending Android 16 architecture outcome**。活跃架构开发位于 `codex/m8-architecture-ceiling`。

## Android 16 Gate 1 — Prototype A ARM32

- [x] 保持 Prototype A、ARM32 产品定义、relative `OUT_DIR`、VNDK 31 与 `systemimage` 目标不变。
- [x] 在 native GCP Ubuntu 24.04 / ext4 / 8 vCPU / 62.8 GiB RAM / no-swap 主机完成 `m -j8 systemimage`；未使用 cgroup、taskset、WSL wrapper 或 `SOONG_GOMEMLIMIT` patch。
- [x] 完成全部 123,197 个 target actions；`system.img` 为 946,765,824 bytes，SHA-256 `FD349F1D8073DFEB71E2CEA28915F1C755FA54E3EBA85616FCAA279063F3EDBE`。
- [x] 完成 Gate 1 离线 closure：ext4/e2fsck、AVB footer/hashtree、ARM32 ABI/property、36 个 APEX、VNDK 31、system-side VINTF、A16 linkerconfig、SELinux xattr/mapping 与 output-scope 均符合 Prototype A 预期。
- [x] 确认本 Gate 只生成 standalone `system.img`；未生成 boot/vendor/product/system_ext/super/userdata image，未组装 IMAGEWTY 或可刷固件，未修改设备。
- [ ] 把 exact accepted `m8b-remote-r1` 的 system/vendor/product/vendor_dlkm、boot/vendor_boot 与外层 rollback 资产复制到 GCP 并逐项校验既有 size/SHA-256；当前 VM 不具备这些 ignored 大文件。
- [ ] 用 exact accepted vendor/product 对 A16 system 运行完整 `checkvintf`、linker/ELF、SELinux、partition-fit、LP/AVB/outer preservation closure，并只在全部通过后形成一个可回滚 Prototype A ARM32 候选。
- [ ] 取得该候选的明确刷写授权后，做一次 UART-first exact-board boot；首要里程碑为 first-stage mount → `apexd` → `zygote32` → `system_server` → ARM32 SurfaceFlinger/accepted HWC。Gate 2 在这个隔离实验结果前不启动。

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
- [ ] **DEFERRED pending Android 16 architecture outcome / INFO：**`nano_input_open -3` 当前保留日志窗口与 62 秒样本均为 0；input capture 未测试，不声明 PASS/FAIL，且不阻塞 HDMI primary output。
- [ ] **DEFERRED pending Android 16 architecture outcome / P1：**permissive SELinux active-path AVC 已分组为 CEC extcon、system_suspend wakeup sysfs 与 audio HAL uevent socket；不修改 frozen Android 12 policy。

## 独立功能项

- [x] 选择并可逆实机证明 AOSP `LeanbackIME`：InputMethodManager discovery/enable/default、DPAD focus、DPAD_CENTER 输入 `ty`、BACK dismissal/reopen 与无 crash/retry 均通过；测试后恢复 accepted device 的空 IME 状态。
- [x] 构建 `m8b-ime-r1`：标准 product module 集成，product AVB/LP/outer preservation 通过；system/vendor/vendor_dlkm 与 accepted product properties 原字节保持。
- [x] `m8b-ime-r1` 物理设备验收：fresh-data 首启自动 enable/default，Wi-Fi 密码输入、物理 DPAD/OK/BACK、文字输入与 1920×1080 TV 观感通过；状态 **DEVICE ACCEPTED / IME PASS**。
- [x] 单独 reboot persistence 未另行执行；用户以 fresh-data 自动 enable/default 与实际物理使用接受为非阻塞，不声明该子项 PASS。
- [x] 构建独立 `m8b-remote-r1`：复用 accepted AOSP TvRemoteProvider，加入 hash-locked Google donor、system_ext RRO、exact privapp policy 与 CONNECT-only default grant；system_a/AVB/LP/outer 检查通过，product/LeanbackIME、vendor/vendor_dlkm 与 boot 保持。
- [x] `m8b-remote-r1` 物理设备验收：Projectivy/基础回归、Remote Service、CONNECT `GRANTED_BY_DEFAULT`、6466/6467、RRO lookup、official Google TV iPhone discovery/pair、DPAD/BACK/HOME/Volume/Mute 与真实 EditText phone text 均通过；状态 **DEVICE ACCEPTED / REMOTE PASS**。
- [x] paired mobile Remote 占用 text-input session 时提示 `Use the keyboard on your mobile device`；物理遥控导航保持，接受为 Android TV 行为而非 LeanbackIME regression。
- [x] Remote r1 reboot persistence 未单独执行且不声明 PASS；无具体失败迹象，本里程碑接受为非阻塞。当前实机无 Play Store/GMS/GSF，因此没有可执行的 Play runtime regression test。

## Deferred Android 12 backlog

- [ ] **DEFERRED — Settings/Menu semantics：**目标仍为 Menu→Projectivy menu、Settings→Android Settings；不回改 frozen kernel/rc-core/keylayout。
- [ ] **DEFERRED — suspend/resume recovery：**HDMI、Wi-Fi、Bluetooth、网络、ADB 与 mobile Remote 恢复未完成。
- [ ] **DEFERRED — graphics artifacts：**选中态渐变噪点、Wi-Fi 相关短暂撕裂/黑屏与 HWUI telemetry 尚未建立因果。
- [ ] **DEFERRED — HDMI CEC：**TV/盒子双向控制与已知 CEC AVC 的功能相关性未验收。
- [ ] **DEFERRED — CPU/thermal soak：**低负载 1.512 GHz、ThermalService `HAL Ready=false` 与实际 throttling 未完成现场关联。
- [ ] **DEFERRED — exFAT：**USB host/storage 已通过，Android 12 filesystem support 不再单独开发。
- [ ] **DEFERRED — commercial DRM playback：**Widevine L3 protected playback 与目标服务认证/播放未验证；不把 plugin operational 等同于认证。
- [ ] **DEFERRED — LeanbackIME cold-start latency：**cold/warm invocation timing 尚未受控测量，不确认 defect/root cause。
- [ ] **DEFERRED — SELinux enforcement-readiness：**不为清日志修改 frozen Android 12 policy。
- [ ] **DEFERRED — legacy multi_ir/uinput cleanup：**保留 inert reference；不在 frozen baseline 删除通用或历史恢复工件。

## 已知非里程碑项

- [x] 完成限定只读 system-quality audit：无 P0；stability、retry loop、audio residual、SELinux、CPU/thermal/idle、graphics 与 memory 证据见 `docs/m8/device-tests/20260816-m8b-system-quality-audit/`。
- [ ] **DEFERRED / P2 / 不修：**Wi-Fi HAL link-layer statistics 每约 3 秒返回 `ERROR_UNKNOWN`；网络 ADB 稳定且 Wi-Fi 进程未重启。
- [x] 保持 Mouse mode dropped；不重新引入 vendor mouse framework。
- [x] architecture-ceiling study 已找到强匹配 paired AArch64 Mali 与 multilib mapper/gralloc provider 证据；ARM32 OMX/Cedar media 可进程隔离复用。Android 16 mixed AArch64/ARM32 为 **CONDITIONAL GO**，其 build/runtime gates 转到 `codex/m8-architecture-ceiling`，不在本 Android 12 分支执行。
