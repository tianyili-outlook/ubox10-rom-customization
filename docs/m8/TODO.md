# M8 TODO

## Freeze decision

`m8b-remote-r1` 已冻结为 **FROZEN / DEVICE-ACCEPTED Android 12 working baseline**，作为 Android 16 架构工作的稳定回退与功能对照。当前不再实施 Android 12 M8B feature、P1/P2 修复或清理；以下未完成项全部 **DEFERRED pending Android 16 architecture outcome**。活跃架构开发位于 `codex/m8-architecture-ceiling`。

## Android 16 Gate 1 — Prototype A ARM32

- [x] 保持 Prototype A、ARM32 产品定义、relative `OUT_DIR`、VNDK 31 与 `systemimage` 目标不变。
- [x] 在 native GCP Ubuntu 24.04 / ext4 / 8 vCPU / 62.8 GiB RAM / no-swap 主机完成 `m -j8 systemimage`；未使用 cgroup、taskset、WSL wrapper 或 `SOONG_GOMEMLIMIT` patch。
- [x] 完成全部 123,197 个 target actions；`system.img` 为 946,765,824 bytes，SHA-256 `FD349F1D8073DFEB71E2CEA28915F1C755FA54E3EBA85616FCAA279063F3EDBE`。
- [x] 完成 Gate 1 离线 closure：ext4/e2fsck、AVB footer/hashtree、ARM32 ABI/property、36 个 APEX、VNDK 31、system-side VINTF、A16 linkerconfig、SELinux xattr/mapping 与 output-scope 均符合 Prototype A 预期。
- [x] 确认本 Gate 只生成 standalone `system.img`；未生成 boot/vendor/product/system_ext/super/userdata image，未组装 IMAGEWTY 或可刷固件，未修改设备。
- [x] 已把 exact accepted `m8b-remote-r1` 外层镜像和 Test8r2 rollback 复制到 GCP 并 hash-verify；accepted logical、boot/vendor_boot、super/LP 与 AVB payload 已提取并逐项锁定，原始输入保持只读。
- [x] 已完成 exact VINTF、linker/ELF、SELinux、partition-fit、LP/AVB 与 outer preservation closure：两个 accepted display HAL 已加入 device matrix；split SELinux 的单一 duplicate `fuseblk` rule 已做 bounded fix；linker/ELF/SELinux/LP/AVB/outer PASS。Full VINTF 仍准确记录唯一继承偏差 `CONFIG_NFS_FS=y`（FCM 6 要求 `n`），未声明 PASS。
- [x] 已形成且审核唯一 `a16-prototype-a-r1`：外层 1,261,038,592 bytes / SHA-256 `A034C8193236C93746E5962CB3E7F26A1D56CEC1435D5AD9D95F653B60BEBD83`；system 语义差异仅 device matrix 与 platform duplicate genfscon；46/50 外层 payload、boot/kernel/vendor/product/vendor_dlkm/top-level vbmeta 保持。
- [x] 用户另行明确授权并完成一次 r1 PhoenixCard 刷写/启动；刷写 checksum 与 `CARD OK` PASS。7 次 kernel start / 6 个完整周期稳定到达 A16 second-stage init，随后以 `bootstrap-apexd-failed` 重启。
- [x] RAM-only `printk.devkmsg=on` 诊断取得首错：required blkio mount 因 `CONFIG_BLK_CGROUP=n` 返回 `EINVAL`，`CgroupSetup()` 在创建 `/sys/fs/cgroup/system` 前退出；ueventd 与 apexd-bootstrap 被 fork，但 child 在 `ExpandArgsAndExecv()` 前 fatal exit。APEX activation 未尝试；servicemanager、zygote32、system_server、SurfaceFlinger、HWC 未到达。
- [x] 完成 exact A16 init/libprocessgroup 控制流、system/API31/vendor cgroup/task-profile、Soong flag 与 retained 5.4 config 审计。除 BLK_CGROUP 外，`CONFIG_CPUSETS=n` 也是下一个 required blocker；最小 delta 为 BLK_CGROUP + CPUSETS + Kconfig 自动 PROC_PID_CPUSET，optional memory-v2 不要求本轮启用 MEMCG。
- [x] 更新消息分类：blkio 为首个 causal blocker；missing pid cgroup.procs 为 cascade；logical-partition 与 early secilc linkerconfig 为 non-fatal early path；missing misc 为 reboot-path secondary noise。r1 是 bounded retained-kernel integration defect，不是 apexd 内部失败或 architecture-level blocker。
- [x] 构建并离线审核唯一 `a16-prototype-a-r2`：外层 1,261,038,592 bytes / SHA-256 `114DF8677CD6984EB1431377723EDF61C80ACF26C15D8770BAE47DCFE7D1B6D0`；只改变 kernel/boot/Vboot，r1 system/APEX/LP/vendor/vendor_boot/AVB 与其余 48/50 payload 保持。AVB/IMAGEWTY/ext4/cgroup/SHA PASS；full VINTF 仍只有继承的 NFS 例外，没有新增 incompatibility。
- [x] 用户单独授权并完成一次 r2 PhoenixCard/UART-first 物理测试；flash `CARD OK`。5 次 kernel start / 4 个完整周期证明 r1 cgroup fix 生效、ueventd 与三个 service manager 运行、APEX init content 被 import；`bootstrap-apexd-failed` 消失。
- [x] 确认 r2 新的首个可重复 fatal：exact r4/25Q4 `NetBpfLoad` 在加载 BPF objects 前因 5.4.125 小于 5.10 返回，init 的 bpfloader `reboot_on_failure` 随后以 `bpfloader-failed` 重启。Zygote32、system_server、SurfaceFlinger、HWC 未到达。
- [x] 审核 `memory_recursiveprot`、CAP_PERFMON、剩余 cgroup/task-profile、IncFS、BPF/BTF 与最低 LTS：memory_recursiveprot 和 IncFS 当前有明确 fallback；CAP_PERFMON/UprobeStats 是非致命但真实后续缺口；当前没有第二个 pre-bpfloader cgroup fatal。25Q2 的 non-GKI 5.4 最低为 5.4.277，exact 5.4.125 不满足。
- [x] 完成 A/B/C source-proven 决策：A（`android-security-16.0.0_r7` / API 36.0 / QPR0 + retained 5.4 lineage）排名第一但 **HOLD**；B（r4 + 5.4 feature backports）和 C（5.10+ BSP port）在当前 bounded Gate 2 均 **NO-GO**。没有构建 r3，没有启动 Prototype B。
- [ ] **当前唯一下一动作：**在独立 clean checkout 锁定 `android-security-16.0.0_r7` manifest/source，先完成 source-only 产品/cgroup/APEX 差异审计；同时为 retained H616 BSP 形成可审查的 5.4.125→至少 5.4.277、优先最终 5.4.302 LTS rebase 与 netd config delta 方案。该 checkpoint 未通过前不构建 r3、不刷写；Gate 2 保持 **CLOSED**。

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
