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
- [x] 完成 A/B/C source-proven 决策：A（`android-security-16.0.0_r7` / API 36.0 / QPR0 + retained 5.4 lineage）排名第一但 **HOLD**；B（r4 + 5.4 feature backports）和 C（5.10+ BSP port）在当前 bounded Gate 2 均 **NO-GO**。没有构建 A16 r3，没有启动 Prototype B。
- [x] 完成 retained kernel lineage/provenance：Orange Pi `9ab7a758...` 是无 upstream merge-base 的七提交 BSP import；锁定 upstream v5.4.125/v5.4.302、Android common 5.4.125/5.4.302、4,603-file vendor delta、434 个 critical exports、accepted rc-core/keymap 与三个 external module source identities。
- [x] 选择并精确重放 synthetic-base Android-common merge；46 conflicts 分类为 31 common/stable wins、12 vendor wins、3 semantic merges，最终 commit/tree `027ef79e...` / `b328c327...` 可由 tracked script/patch/record 在独立 worktree 17 秒重现。
- [x] 从 accepted Android 12 Image config 构建 preservation-only 5.4.302+ Image；32 个 effective Kconfig 变化全部解释并 hash-lock。另行确认 A16 cgroup + QPR0 netd 六项 config addition 在 5.4.302 clean closure，不把它们加入 Android 12 preservation Image。
- [x] 用 AOSP clang-r416183b1 完整构建 Image 与 exact 22-module set；critical vendor trees、module inventory/metadata/export names/import CRCs、ARM64/boot/DTBO/AVB source contracts 离线 PASS，结果 `PASS_WITH_PHYSICAL_VALIDATION_REQUIRED`。旧 5.4.125 modules 不复用。
- [x] 构建并审核唯一 Android 12 kernel-only `m8-kernel-5.4.302-r1`：1,031,739,392 bytes / SHA-256 `C93FC8A54391E091E0F95CFE63E4F6DA9AE90D55AA0163D91D42586B48BFEE2B`。System/vendor/product、ramdisk、LP geometry、46/50 outer payload、rollback bytes 保持；boot/vendor_dlkm AVB、sparse roundtrip、IMAGEWTY、e2fsck PASS。未修改物理设备。
- [x] 用户另行授权并完成 Android 12 kernel-only `m8-kernel-5.4.302-r1` physical validation：Linux 5.4.302、`sys.boot_completed=1`、HDMI/UI、遥控、Ethernet、ADB PASS；Wi-Fi FAIL，稳定收敛为 AIC8800D U04 firmware START_APP `cmd:1037 - reqcfm(1038)` timeout，随后 `wifi start fail`/SDIO remove。三模块和 firmware 均存在，不归因 HAL/framework 或 missing payload。
- [x] Source-proven 66 MHz path：pinned AIC `FEATURE_SDIO_CLOCK=70000000` 经 `aicbsp_get_feature` 进入 BSP probe 的 direct `host->ios.clock` + host `set_ios`；exact sunxi-mmc-v4p1x 将 SDR module clock 双倍取整到约 133.333 MHz并回写逻辑约 66.666 MHz。该值在 firmware START_APP wait 前设置且期间无其他 AIC clock write。
- [x] 构建并离线审核严格单变量 `m8-kernel-5.4.302-r2`：只把 AIC runtime request 70 MHz→50 MHz；候选复用实机 r1 Image 与 21 modules，只替换 `aic8800_bsp.ko`。外层 1,031,739,392 bytes / SHA-256 `A2963FD46685829774DBF5EA2E899ED5844BF44329BC8F46788F1D14D09AA036`；AVB/ext4/LP/IMAGEWTY/preservation PASS。状态为 diagnostic，不是 accepted fix。
- [x] 用户另行授权并完成 `m8-kernel-5.4.302-r2` physical diagnostic：运行时 `Set SDIO Clock 50 MHz` 证明唯一变量生效，但每次 power/re-enumeration 均重复 token 476 的 1037→1038 timeout、`wifi start fail` 与 card remove；50 MHz hypothesis **REJECTED**。Android 12 boot、Ethernet/ADB 正常；fdrv 不保持、无 `wlan0`，HAL/framework 为下游。不得再猜频率。
- [x] 完成 exact 5.4.125→5.4.302 generic MMC/SDIO/AIC source differential：CMD52/CMD53、SDIO IRQ claim/dispatch、request wait/completion、host claim/release 与 retained SUNXI host live path 未改变；changed OCR/clock/retune/NONSTD/refcount/host-validation/shutdown deltas逐项按 call path 排名和排除。Token 476 证明此前 476 个 blocking confirmations 已通过同一 RX/dispatch machinery；当前证据不足以选择一个 generic MMC behavior revert，因此没有构建猜测性候选。
- [x] 设计、source-review、构建并离线审核 `m8-kernel-5.4.302-r3`：回到 r1 的 70 MHz 功能基线，仅替换一个 START_APP-gated observability 版 `aic8800_bsp.ko`；动态捕获 1037 runtime token/generation，并在原有 success/timeout 后用一条 summary 记录 final CMD53 TX、final-TX-attempt/return 前后可归属 IRQ/block count、CMD53 RX、1038 dispatch/token match/completion。没有增加 timeout/retry/sleep/lock/host claim 或改变 MMC 行为。Candidate 为 1,031,739,392 bytes / SHA-256 `9E52B601F11F9368599098B4C5082037D010930D9B424D7CA2828977047C1B28`。
- [x] 用户另行授权并完成 r3 physical diagnostic：一次手动 Wi-Fi ON 与一次 framework self-recovery 都证明 final 512-byte CMD53 在 Linux host 返回 0，随后 AIC handler/RX/1038 dispatch/token completion 全部为零并 timeout；状态 **PHYSICAL DIAGNOSTIC PASS / WI-FI FAIL / POST-TX PRE-AIC-HANDLER BOUNDARY PROVEN**。该结果不证明 card consumption，也不区分 card-no-pending 与 IRQ 在 handler 前丢失。
- [x] Source-review 证明 current r3 无安全、可归属的 card CCCR pending readout；构建并离线审核 `m8-kernel-5.4.302-r4`。它只在原 timeout 后、teardown 前读取 CCCR `INTx`/`IENx` 并记录 host/core/claim/handler state，保持 r1/r3 70 MHz、timeout 前控制流与所有非 BSP bytes。AIC export CRC 已恢复为 r1 byte-identical；AVB/ext4/LP/IMAGEWTY/single-module checks PASS。Candidate 为 1,031,739,392 bytes / SHA-256 `18565E4F94FF1A843EA859254800E5E2BA732FBFE47410E86D6577038F85DFCA`。
- [x] 用户另行授权并完成 r4 physical diagnostic：Android 12 在 Linux 5.4.302+ boot complete；一次手动 Wi-Fi ON 与一次正常 framework self-recovery 均为 token 476、24-byte bus TX / final function-1 512-byte CMD53 host return 0，随后 IRQ/RX/1038/token/completion 全零。Timeout 时 function 1、hardware SDIO IRQ、claim/handler 均正确，`IENx=0x03`、`INTx=0x00`、core pending=0。状态 **PHYSICAL DIAGNOSTIC PASS / WI-FI FAIL / NO PERSISTENT FUNCTION PENDING AT TIMEOUT**；不证明 FIFO dequeue、无 transient IRQ 或 firmware failure。
- [x] 完成 AIC8800D U04 device-contract/source archaeology 与 exact firmware read-only disassembly。Exact `fmacfw.bin`（260,984 bytes / SHA-256 `FC3BC7865CBB01560E706E87FEA23F07CBF86B0E9F76649381D553FE8E781904`）在 `0x00120000` 的 debug table 将 1037 映射到 post-start handler：allocate 1038，填入 indirect ROM/API selector 15 的 low byte，输出 `DBG: FW started` 后发送 CFM。四个后续 public AIC8800 U03/U04 FMAC 版本保持同构；same-vendor pre-transfer proxy 的 AUTO 会 stop host interface 并 program/reset-launch vector，但不生成 CFM。Exact U04 boot-ROM consumer/AUTO handoff、initial CFM ownership 与 FIFO dequeue 仍没有 authoritative source；最佳推断为 post-transfer FMAC CFM，但不得提升为证明。
- [ ] **当前唯一下一动作：**保持 r1-r4 artifacts 与 Test8r2/stock rollback 不变，不构建 r5。等待 exact AIC8800D U04 boot-ROM source/image+verified map、vendor START_APP/boot-flow specification，或 exact working U04 device-side trace；在出现 source-proven read-only dequeue/boot/FMAC-ready discriminator 前，不执行软件或物理实验。Gate 2 保持 CLOSED。
- [ ] **随后但不提前执行：**只有 wireless/kernel preservation checkpoint 收敛后，才锁定 `android-security-16.0.0_r7` manifest/source 并做 source-only 产品/cgroup/APEX 差异审计；在此之前不构建 A16 r3、不启动 Prototype B。

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
