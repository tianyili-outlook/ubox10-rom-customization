# M8 device test and rollback

## 当前状态

- 最后报告的物理验收镜像：`out/candidates/a16-prototype-a-r4/x12-a16-prototype-a-r4.img`，1,239,746,560 bytes / SHA-256 `E125DD8FFB9F5B4A7B2B9B86DD8377367409AB00D1B29BE1E719CE25768E2111`
- 当前项目状态：**ANDROID 16 PATH-A PHYSICAL PASS / GATE 2 CLOSED**。QPR0 Prototype A r4 无 UART/runtime EGL intervention 即 boot complete；source-level EGL、Mali-G31/UI、Remote OK、stable HDMI、Wi-Fi association/DHCP/validated L3、direct HDMI audible audio 和 VLC video/audio 均 PASS。Boot-time legacy audio HAL `getAudioPort` null-address SIGSEGV 仍复现并 auto-recover；用户明确把该 defect 从旧 startup-stability gate 改列为 **KNOWN / UNFIXED / POST-GATE P1**。Prototype A r4 已冻结为 accepted Android 16 ARM32 architecture baseline。Prototype B r1-r4 已冻结为各自 immutable physical-fail evidence；最新 single-cause r5 已完成全离线验收，物理状态 **NOT YET VALIDATED**，下一步仅做 r5 UART-first ABI/zygote/system_server gate，graphics 独立判定。
- 保留的设备验收基线：`out/candidates/m8b-remote-r1/x12-m8b-remote-r1.img`，状态 **DEVICE ACCEPTED / REMOTE PASS**（继承 **AUDIO PASS / IME PASS**）。
- 大小 / SHA-256：1031723008 bytes / `F3B09E5565AC4ED4E5EE326D392622E7B036A8519B8444B966E77CC4751B814A`
- 用户当前在设备现场，可执行物理交互、重启、suspend/resume、HDMI 观察与恢复；任何新候选刷写仍需该候选的单独明确授权。

Wi-Fi ADB：

```powershell
C:\platform-tools\adb.exe -s 192.168.1.8:7896 shell <read-only-command>
```

回滚到 accepted baseline 后的 ADB 检查入口：

```powershell
C:\platform-tools\adb.exe -s 192.168.1.8:7896 shell getprop sys.boot_completed
C:\platform-tools\adb.exe -s 192.168.1.8:7896 shell dumpsys media.player
C:\platform-tools\adb.exe -s 192.168.1.8:7896 shell dumpsys media.audio_flinger
C:\platform-tools\adb.exe -s 192.168.1.8:7896 shell dumpsys media.audio_policy
C:\platform-tools\adb.exe -s 192.168.1.8:7896 logcat -d -b all
```

accepted baseline 已确认 Treble/VNDK、primary HAL/output、HEVC+AAC HDMI 音频、VP9 Allwinner/Cedar hardware runtime、Widevine 16.1.0 L3、LeanbackIME，以及 official Google TV iPhone Remote discovery/pair/navigation/phone text。刷入任何新候选仍须先获得该候选的单独明确授权。

## Gate 2 physical result: a16-prototype-a-r4

Evidence：`docs/m8/device-tests/20260826-a16-prototype-a-r4-physical-validation/`。Original raw
r4 captures 未存在于本 VM；tracked record 是 reviewed external user confirmation，不伪造 raw
file/hash。本任务未重做物理测试。

| 阶段/功能 | r4 结果 |
|---|---|
| Android/EGL | **PASS**：Android16/API36/`zygote32`/5.4.302+/boot complete；无 UART/`setprop`；`persist.graphics.egl` empty、`ro.hardware.egl=mali`、`ro.board.platform=apollo`；Mali/UI PASS |
| Remote | **PASS / PHYSICALLY PROVEN**：`sunxi-ir.kl`；scanCode 352→`DPAD_CENTER(23)`；UP/DOWN/LEFT/RIGHT/OK/BACK/HOME PASS |
| HDMI | **PASS / STABLE IN THIS VALIDATION**：r3 black-cycle **NOT REPRODUCED**；r4 无 display delta，旧 root cause **NOT PROVEN** |
| Wi-Fi | **PASS**：module/scan/association/WPA/DHCP/IPv4/DNS/Android VALIDATED/real use；本轮 OFF→ON 因 Wi-Fi ADB transport self-disconnect **NOT COMPLETED / NOT FAIL** |
| Ethernet | **NOT RETESTED / NO ACTIVE CARRIER**：r4 exact preservation + prior physical PASS 保持 control |
| Direct HDMI audio | **PASS / AUDIBLE**：48 kHz/16-bit/stereo WAV 经 `tinyplay`/`ahubhdmi` 在 HDMI TV 物理听到 |
| VLC video/audio | **PASS / AUDIBLE**：normal picture/TV audio；AudioFlinger writes/session；service PIDs playback 前后稳定；clean interval crash buffer empty |
| Boot audio HAL | **KNOWN OPEN / REPRODUCED / AUTO-RECOVERED**：`getAudioPortImpl`/`getAudioPort` null-address SIGSEGV；steady-state impact not observed；exact source root cause not proven |

旧合同按 **vendor audio HAL startup stability** 得出 HOLD；该历史结论保留。用户随后明确把
Architecture Gate 2 定义为 functional viability gate。基于 real audible playback、stable
steady-state PIDs、auto-recovery 和 clean playback interval，formal result 更新为 **GATE 2
CLOSED / PASS**。Crash 仍为 **KNOWN / UNFIXED / AUTO-RECOVERED / POST-GATE P1**，不称 fixed。
Enforcing SELinux 属 later release hardening；full VINTF 仍因 inherited `CONFIG_NFS_FS=y` 对
FCM-6 `n` exit 65，不称 PASS。Exact r4 为 frozen rollback control；B1 只能按
`docs/m8/research/prototype-b-b0-readiness.md` 构建一个 bounded candidate。

## Gate 2 physical result: a16-prototype-a-r3

本轮仅对现场已运行的 r3 进行 Ethernet-ADB 采证，未 flash、reboot、build 或修改 image。
Evidence：`docs/m8/device-tests/20260825-a16-prototype-a-r3-physical-validation/`。

| 阶段/功能 | r3 结果 |
|---|---|
| Android identity | **PASS**：Android 16、API36、BP2A.250805.034、SPL 2025-08-05 |
| ABI/zygote/kernel | **PASS**：ARM32-only、empty ABI64、`zygote32`、Linux 5.4.302+、六项 Path-A config `=y` |
| APEX/core framework | **PASS**：boot complete、APEX ready/mount、三个 service manager、system_server/SystemUI |
| Original EGL selection | **FAIL**：无 `persist.graphics.egl`/`ro.hardware.egl`；用户提供的原始日志显示 `ro.board.platform=apollo` 驱动选择失败 |
| Graphics with pre-existing runtime override | **PASS WITH OVERRIDE**：`persist.graphics.egl=mali`，Mali-G31 GLES 3.2、SurfaceFlinger composition |
| TV/launcher/IME | **PASS**：TV/Leanback feature、HOME launcher 与 LeanbackIME present/default；文字输入本身不声明 |
| Ethernet | **PASS**：carrier、gateway/IP/DNS 4/4、Ethernet ADB |
| Wi-Fi | **PARTIAL**：BSP/framework/scan/OFF→ON reinit PASS；association/DHCP/L3/DNS **NOT TESTED**（无 saved network/无法输入凭据） |
| IR remote | **PARTIAL FAIL**：全部 Linux DOWN/UP PASS；OK scanCode 352→Android UNKNOWN，Generic.kl 仅 353→DPAD_CENTER |
| HDMI | **FAIL**：monitor 约 1 秒画面后约 5 秒黑屏循环；framework/extcon/display counters 的 bounded sample 未解释物理黑屏 |
| Audio | **FAIL / NOT TESTED SPLIT**：Apollo/ALSA/AudioFlinger topology 与 volume/mute framework effect 存在；HIDL HAL 在 `getAudioPort` null-pointer crash，stability FAIL；monitor 无 audio output，实际听音 **NOT TESTED** |

Exact gate wording：**CORE PATH-A ARCHITECTURE VIABILITY PHYSICALLY PROVEN / FORMAL CANDIDATE
CLOSURE PENDING**。依赖 runtime EGL override，因此 Gate 2 **NOT CLOSED**。下一候选才可持久加入
`ro.hardware.egl=mali`（保持 `ro.board.platform=apollo`）和 scanCode 352→DPAD_CENTER；二者在
本轮均 **NOT IMPLEMENTED / NOT BUILT / NOT PHYSICALLY VALIDATED**。HDMI/audio 只按现有 evidence
继续 diagnosis，不在本轮修改。Prototype B 继续关闭。

## Gate 2 physical result: a16-prototype-a-r1

用户已对 r1 授权并仅执行一次 PhoenixCard 刷写。写入日志 `logs/20260822-a-r1/uart-putty.log` 为 44,206 bytes / SHA-256 `C4823F59F09FA2ED60E5F35251641B0B0E9ABFAFEF1318F065DAFBED901E4D0C`；13 个 download parts、26 个 MBR parts、payload checksum、`sprite success` 与 `CARD OK` 均通过。

运行日志 `logs/20260822-a-r1/boot.log` 为 78,275 bytes / SHA-256 `18BF7217AFA25CAB2B7443B17A801D8825932FA4EB15ADCFC87D6FE1C3F46C7F`。它记录 7 次 accepted 5.4.125 kernel start 和 6 个完整周期；每个完整周期均进入 Android init，并以 `reboot: Restarting system with command 'bootloader,bootstrap-apexd-failed'` 结束。第 7 次在相同 early-init/cgroup 位置后截断。

后续诊断日志 `logs/20260822-a-r1-devkmsg/boot-devkmsg-on.log` 为 35,625 bytes / SHA-256 `E3EF999E109B837C5DBB3390E110EC80AD3D9DEFE02F0B0CAF581C46C4C2A517`。`printk.devkmsg=on` 只在 U-Boot RAM 中追加并在启动前回读确认，未改 boot image 或持久环境。它推翻了原先把 blkio 视为独立噪声的分类。

运行时边界：

| 阶段 | 结果 |
|---|---|
| kernel / accepted first-stage init / LP mapping | **PROVEN** |
| system mount；vendor/system_ext SELinux inputs 可读 | **PROVEN** |
| split SELinux compile/load；A16 second-stage init | **PROVEN**；cmdline 为 permissive，不证明 enforcing |
| A16 `CgroupSetup` | **FIRST REPRODUCIBLE BLOCKER**；required v1 blkio mount 因 kernel 无 `CONFIG_BLK_CGROUP` 失败，并在创建 v2 `apps`/`system` 子层级前返回 |
| ueventd / apexd-bootstrap | **FORKED BUT NOT EXEC'D**；父进程无法建立 `/sys/fs/cgroup/system/uid_0`，子进程在 `ExpandArgsAndExecv()` 前收到 fatal 状态 |
| bootstrap APEX activation | **NOT ATTEMPTED / NOT PROVEN** |
| servicemanager / zygote32 / system_server | **NOT REACHED / NOT PROVEN** |
| SurfaceFlinger / HWC | **NOT REACHED / NOT PROVEN** |

Exact A16 source path 为：`CgroupSetup()` 在 required blkio `mount()` 返回 `EINVAL` 后 false-return；`cgroup_v2_sys_app_isolation=true` 所需 `/sys/fs/cgroup/system` 因此尚未创建；`Service::Start()` fork 后的 parent `createProcessGroup()` 失败并通过 FIFO 发 `kActivatingCgroupsFailed`；child 在 task profile、credentials/caps 和 `execv` 之前 fatal exit。Exact retained kernel 同时缺少 `CONFIG_CPUSETS`，所以只开启 `CONFIG_BLK_CGROUP` 仍会在下一个 required controller 失败；最小 delta 是 BLK_CGROUP + CPUSETS（自动带出 PROC_PID_CPUSET）。A16 v2 memory controller 为 optional，故本轮不增加 MEMCG。

`Could not update logical partition` 和 early secilc `/linkerconfig/ld.config.txt` 仍是继续执行的 non-fatal early-boot 行为；missing `pid_163`/`pid_164/cgroup.procs` 是进程组创建失败后的清理 cascade；missing `misc` 只发生在 `reboot_on_failure` 已选择重启之后。该 r1 结果本身没有授权后继候选；r2 后来取得了单独授权，其唯一物理结果记录如下。Prototype B 仍不得启动。

## Gate 2 physical result: a16-prototype-a-r2

r2 先完成离线审核，随后由用户单独授权并完成一次 PhoenixCard/UART-first 物理测试。镜像为 `out/candidates/a16-prototype-a-r2/x12-a16-prototype-a-r2.img`，1,261,038,592 bytes / SHA-256 `114DF8677CD6984EB1431377723EDF61C80ACF26C15D8770BAE47DCFE7D1B6D0`。

它只把 retained kernel config 的 `CONFIG_BLK_CGROUP`、`CONFIG_CPUSETS` 及 Kconfig 自动产生的 `CONFIG_PROC_PID_CPUSET` 改为 `y`，并只替换 outer `boot.fex`/`Vboot.fex`。r1 system/APEX/LP/vendor、vendor_boot/ramdisk、AVB 元数据和其余 48/50 outer payload 原字节保持。Boot AVB、IMAGEWTY、ext4、cgroup contract、SHA256SUMS PASS；full VINTF 没有新增错误，仍只保留继承的 NFS config 例外。该历史 r2 结果使当时 Gate 2 继续 **CLOSED**；当前状态见文首 r5/r7 closure。

Flash capture `logs/20260822-a-r2/uart-flash-r2.log` 为 44,451 bytes / SHA-256 `832E3BEDC7BD50E3D9B562FFEE375189825EE3ECA1A3E67D8026157E4545DD2E`。13 个 download parts 均成功，最终为 `CARD OK` / `sprite success`。旧 GPT fallback、erase alignment 文字与既有 successful PhoenixCard 流程一致，不改变写入成功结论。

Boot capture `logs/20260822-a-r2/boot-r2-devkmsg-on.log` 为 67,394 bytes / SHA-256 `BF3196E9DB99AF4F70B5F7CEA5CBA166A40A92299E9670ED517357F2EEE5C4AC`。`printk.devkmsg=on` 仅在 U-Boot RAM 中追加并在 `run boot_normal` 前回读，未写入 boot image 或持久环境。它记录 5 次 kernel start 与 4 个完整、相同的周期。

运行时边界：

| 阶段 | r2 结果 |
|---|---|
| retained 5.4.125 kernel / first-stage init / LP / system handoff | **PROVEN** |
| split SELinux load / second-stage init | **PROVEN TO CURRENT BOUNDARY**；仍为 permissive，不声明 enforcing compatibility |
| required blkio/cpuset、cgroup-v2 root 与 `/sys/fs/cgroup/system` | **PROVEN FIXED**；r1 `uid_0` pre-exec blocker 消失 |
| ueventd | **EXECUTED**；shutdown trace identifies live PID 164 |
| bootstrap/full APEX progress | **ADVANCED**；无 `bootstrap-apexd-failed`，init 实际读取 `/apex/com.android.uprobestats/etc/init.rc` |
| servicemanager / hwservicemanager / vndservicemanager | **EXECUTED**；live PID 267/268/269 与 interface-control traffic 可见 |
| bpfloader / NetBpfLoad | **FIRST REPRODUCIBLE FATAL**；四次均报告 `Android 25Q4 requires kernel 5.10`，然后执行 `reboot_on_failure` |
| zygote32 / system_server / SurfaceFlinger / HWC | **NOT REACHED / NOT PROVEN** |

`cgroup2: Unknown parameter 'memory_recursiveprot'` 由 A16 source 明确重试无该选项，随后 boot 继续；IncFS module 缺失回退为 features v1/none；UprobeStats init 的 `CAP_PERFMON` 不支持发生在 APEX content import 后，该 service 本身 disabled，当前不是 fatal，但保留为真实后续兼容缺口。`/dev/stune/foreground/tasks` 与大量 process-group cleanup 是 bpfloader 已触发 shutdown 后的 secondary/cascade output。没有证据支持再改 cgroup 作为本轮首错。

r2 的 A16 物理授权已经消耗。当前不得再次刷写，不构建 A16 r3，不启动 Prototype B。后续只允许早期 A16 QPR0 与 retained-kernel LTS 路线的离线架构 checkpoint；任何新候选仍需重新离线审核和单独物理授权。

## Physical result: m8-kernel-5.4.302-r1

用户已另行授权并执行一次 Android 12 kernel-only r1 实机测试。现场结果：Linux
5.4.302 正常启动，Android `sys.boot_completed=1`；HDMI/UI、遥控、Ethernet 与 ADB
PASS。Wi-Fi FAIL，且启动中稳定重复：

```text
mmc2: new SDIO card
aicbsp_sdio_probe: matched chip: aic8800d
Set SDIO Clock 66 MHz
aicbsp_8800d_fw_init ... chip rev U04
cmd timed-out
tkn[...] result:-4 cmd:1037 - reqcfm(1038)
wifi start fail
aicbsp_sdio_remove
mmc2: card ... removed
```

`aic8800_fdrv.ko`、`aic8800_bsp.ko`、`aic8800_btlpm.ko` 与 firmware 文件均存在；
首个可重复 boundary 是 AIC firmware START_APP confirmation 缺失，不是 Android Wi-Fi
HAL/framework 或 simple missing payload。当前仓库没有随该报告提供 raw UART capture，故不记录
虚构的文件路径或 hash。r1 结论为 **PARTIAL PHYSICAL PASS / WIRELESS FAIL**。

## Completed physical diagnostic: m8-kernel-5.4.302-r2

候选：`out/candidates/m8-kernel-5.4.302-r2/x12-m8-kernel-5.4.302-r2.img`，
1,031,739,392 bytes / SHA-256
`A2963FD46685829774DBF5EA2E899ED5844BF44329BC8F46788F1D14D09AA036`。
它只把 pinned AIC BSP runtime request 从 70 MHz 改为 50 MHz，复用 r1 Image/boot/DT、
userspace 与 21 个 module bytes。用户已另行授权并完成测试，结果为
**PHYSICALLY FAILED — 50 MHZ HYPOTHESIS REJECTED**：

```text
mmc2: new SDIO card
aicbsp_sdio_probe: matched chip: aic8800d
Set SDIO Clock 50 MHz
cmd timed-out
tkn[476] flags:0012 result:-4 cmd:1037 - reqcfm(1038)
wifi start fail
mmc2: card ... removed
```

该序列在多次 power/re-enumeration 中稳定重复。Android 12 boot complete，Ethernet 与
ADB 正常；`aic8800_bsp`/`aic8800_btlpm` 保持，`aic8800_fdrv` 不保持，`wlan0` 不存在。
HAL service 存在，framework `CMD_STA_START_FAILURE`/`DisabledState` 是 firmware init
失败的下游结果。不要再测试任意 SDIO frequency。

后续离线 source diff 证明 retained→5.4.302 的 generic CMD52/CMD53、SDIO IRQ、request
completion、host claim/release 与 SUNXI host live path 未改变，没有一个 LTS delta 足以
支持行为回退。后续 r3 只增加 START_APP-gated AIC BSP observability，不改变这些行为。

## Physical diagnostic result: m8-kernel-5.4.302-r3

候选：`out/candidates/m8-kernel-5.4.302-r3/x12-m8-kernel-5.4.302-r3.img`，
1,031,739,392 bytes / SHA-256
`9E52B601F11F9368599098B4C5082037D010930D9B424D7CA2828977047C1B28`。
状态为 **PHYSICAL DIAGNOSTIC PASS / WI-FI FAIL / POST-TX PRE-AIC-HANDLER BOUNDARY PROVEN**。

r3 回到 r1 的 `FEATURE_SDIO_CLOCK=70000000` 功能基线，并严格复用 r1 Image、boot、DT、
userspace 和其他 21 个 module bytes；只有 `aic8800_bsp.ko` 加入动态 runtime token /
transaction-window trace。它在原有 START_APP success/timeout 后只输出一条
`AIC_STARTAPP_TRACE:`，用于回答：

1. final 1037 CMD53 TX 是否尝试并成功返回；
2. TX 后是否有可归属于该 transaction window 的 AIC IRQ，以及 block-count CMD52 结果；
3. CMD53 RX 是否发生、requested length/return 与 frame type/message ID；
4. 1038 是否进入 dispatch；
5. 1038 是否匹配当前 runtime token 并完成 waiter。

用户手动打开一次 Wi-Fi 后，第一次启动与 framework 的一次自动 self-recovery 均保留
`Set SDIO Clock 66 MHz`，并产生相同 runtime token 476 trace：`tx_bus_ret=0`、
`tx_cmd53_state=2`、`tx_cmd53_len=512`、`tx_cmd53_ret=0`，随后
`irq_count=0`、`rx_cmd53_count=0`、`cfm_seen=0`、`token_match=0`、`completion=0`，再发生
1037→1038 timeout 与 SDIO teardown。`irq_block_count_ret=-115` 和 `rx_cmd53_ret=-115` 是
未触发路径保留的 `-EINPROGRESS` sentinel，不是实际 I/O error。

证据为 `/work/device-evidence/m8-kernel-5.4.302-r3/20260823-wifi-on/` 下的
`r3-wifi-on-kernel.txt`（39,758 bytes / SHA-256
`2EB7A8581C0B201A282995D7BA07AA24550D767A764B7A12DAE66113EDF6B0A2`）与
`r3-wifi-on-all.txt`（5,673,014 bytes / SHA-256
`A0FBC16964616C0E8BF24D00365B36C6B4C8CC7370250EB4A8AEE53579E36287`）；目录中没有 UART
文件。Host-side CMD53 return 0 不证明 card/firmware 已消费 START_APP；`irq_count=0` 也不
单独证明 card 未断言中断或 host 丢失中断。当前 r3 缺少 card CCCR pending 的安全接口，
因此不得从该结果选择行为修复。后续任何新诊断候选仍需单独明确物理授权并保持 Test8r2
rollback 边界。

## Physical diagnostic result: m8-kernel-5.4.302-r4

候选：`out/candidates/m8-kernel-5.4.302-r4/x12-m8-kernel-5.4.302-r4.img`，
1,031,739,392 bytes / SHA-256
`18565E4F94FF1A843EA859254800E5E2BA732FBFE47410E86D6577038F85DFCA`。
状态为 **PHYSICAL DIAGNOSTIC PASS / WI-FI FAIL / NO PERSISTENT FUNCTION PENDING AT TIMEOUT**；
该历史 r4 结果使当时 Gate 2 保持 CLOSED，后续 r5 已关闭此 wireless checkpoint。

r4 保留 r1/r3 的 70 MHz、Image、boot、DT、Android 12 userspace 和其他 21 modules，只在
原 START_APP timeout 已成立后、teardown 之前，由 `aic8800_bsp.ko` 读取 read-only CCCR
`INTx`，再读取 `IENx`，并记录 function、host/core pending、IRQ claim 与 handler 安装状态。
没有改 START_APP timeout、retry、firmware、clock、MMC behavior 或 timeout 前控制流。
离线检查确认 AIC exported-symbol CRC 与 r1 完全一致，避免 preserved `aic8800_fdrv.ko`
发生 symbol-version mismatch；AVB/ext4/LP/IMAGEWTY 和 single-module preservation PASS。

用户手动打开一次 Wi-Fi 后，该次尝试及一次正常 framework `WifiSelfRecovery` 均记录 token
476、`tx_bus_len=24 tx_bus_ret=0`、`tx_cmd53_state=2 tx_cmd53_len=512 tx_cmd53_ret=0`，随后
`irq_count=0 rx_cmd53_count=0 cfm_seen=0 token_match=0 completion=0`。两次 timeout snapshot 都是
`timeout_func=1 host_cap_sdio_irq=1 host_irq_pending=0 irq_claimed=1 handler_installed=1`、
`cccr_intx=0x00/ret=0`、`cccr_ienx=0x03/ret=0`。这只证明没有标准 function-1 pending 状态
保留到两秒 snapshot；不证明 card 未短暂 assert、自清或产生 malformed IRQ，也不证明 firmware
failure。自然启动的一次 `aicwf_sdio_hal_irqhandler: Interrupt but no data` 证明更早状态下 AIC
handler 曾实际进入，但不证明 START_APP response IRQ 正确。

后续 exact firmware/source archaeology 找到 U04 `fmacfw.bin` 内 post-start 1037 handler：它
allocate/send 1038，并在 send 前输出 `DBG: FW started`。没有找到 exact U04 boot-ROM consumer、
AUTO handoff 或 source-proven read-only dequeue/boot/FMAC-ready state；`bootstatus` 只存在于缺失的
1038 payload 且被 host 当作 `hwinfo_r`。该 archaeology 本身没有产生 r5，但随后的
accepted-driver semantic audit 证明 working BSP 的 upload/START_APP base 是 `0x00120000`，r1-r4
则因 donor preprocessor guard/Makefile define 不一致而编译成 `0x00110000`。这使仅修正该 guard、
保留 r4 trace 的 r5 单变量 design 成立。当时尚未 build/实测；后续 r5 结果已在下节关闭该
边界。不同芯片 FNCALL/DUMMY 或随机寄存器读取仍不成立。完整历史证据与 lineage 限制见
`docs/m8/candidates/m8-kernel-5.4.302-r4.md`。

## Physical result: m8-kernel-5.4.302-r5

候选：`out/candidates/m8-kernel-5.4.302-r5/x12-m8-kernel-5.4.302-r5.img`，
1,031,739,392 bytes / SHA-256
`A185B0A3C7516FBC9D34F61B3218171F07BDA00B84903A644D2D71FBB1DCC28F`。
状态为 **PHYSICAL PASS / WI-FI PASS / PRESERVATION CHECKPOINT CLOSED**。

r5 只把 `RAM_FMAC_FW_ADDR` guard 从未实际定义的 `CONFIG_AIC_INTF_SDIO` 改为 build 已提供的
`AICWF_SDIO_SUPPORT`。Final packaged `aic8800_bsp.ko` 为 129,976 bytes / SHA-256
`2BF0F46C69968408544D8F1B344C0999C6B2E69E03C7E24A5EB8D2A23133D03A`；final-ELF audit 证明
FMAC upload=`0x00120000`、patch read=`0x00120180`、START_APP=`0x00120000`，与 accepted working
5.4.125 BSP 一致。r4 三值分别为 `0x00110000`、`0x00110180`、`0x00110000`。

r4 START_APP trace/timeout CCCR、70 MHz、timeout/retry、MMC/SUNXI、firmware、Image/boot/ramdisk/DT、
Android userspace 与其他 21 modules 保持。Relative r4 outer delta 仅 `super.fex`/`Vsuper.fex`；
AVB/FEC、ext4/e2fsck、LP/sparse round trip、IMAGEWTY 与 focused tests PASS。完整记录见
`docs/m8/candidates/m8-kernel-5.4.302-r5.md`。

用户已完成 physical validation。`uname -a` 为
`Linux localhost 5.4.302+ #1 SMP PREEMPT Thu Aug 13 22:30:00 +08 2026 armv8l`，
`sys.boot_completed=1`。AIC FMAC/BTLPM/BSP/rfkill modules 加载，initial probe/66 MHz/FMAC/
supplicant startup 成功；旧 error filter 为空。Physical Wi-Fi OFF→ON 后 old wlan0/SDIO/bus/
thread/subsystem teardown 完整，再 fresh init 成功。一次 `aicsdio: write retry: 20` 后继续到
functional/validated connection，按 non-fatal transient 记录。Android 完成 association、4-way/
group handshake、DHCP `192.168.1.8/24`、gateway `192.168.1.254` 与 validated L3；IP/DNS ping
均 4/4、0% loss，Wi-Fi ADB reconnect PASS。Post-cycle old error filter 再次为空。

Original raw ADB captures 由用户在设备外部收集且未在 VM 找到；tracked evidence 只含 reviewed
facts/excerpts，不虚构 raw file/hash。详见
`docs/m8/device-tests/20260825-m8-kernel-5.4.302-r5/`。Rollback 仍为 frozen
`m8b-remote-r1`/Test8r2；本结果不授权后续 r3 flash/physical action。

## Accepted physical result: m8b-remote-r1

当前运行镜像：

- path：`out/candidates/m8b-remote-r1/x12-m8b-remote-r1.img`
- size：1031723008 bytes
- SHA-256：`F3B09E5565AC4ED4E5EE326D392622E7B036A8519B8444B966E77CC4751B814A`
- direct predecessor / rollback：accepted `m8b-ime-r1`

现场与运行时结果：

- Projectivy、物理遥控、Wi-Fi、Bluetooth 与 LeanbackIME 基础回归 PASS。
- Remote Service 5.2.473254133 运行；`BLUETOOTH_CONNECT` 为 `GRANTED_BY_DEFAULT`，没有手工 `pm grant`。
- TCP 6466/6467 监听；system_ext RRO 存在，framework resource lookup 精确返回 Remote Service package。
- official Google TV iPhone discovery、pair、DPAD、BACK、HOME、Volume±、Mute 与真实 EditText phone keyboard PASS。
- 手机 text-input session 活跃时 `Use the keyboard on your mobile device` 是接受的 Remote 行为；物理遥控仍可导航，不视为 LeanbackIME regression。
- reboot persistence 未单独执行且不声明 PASS；接受为本里程碑非阻塞项。
- `com.android.vending`、`com.google.android.gms`、`com.google.android.gsf` 均不存在，故没有可执行的 Play runtime regression test。

完整最小证据见 `docs/m8/device-tests/20260816-m8b-remote-r1/`。LeanbackIME 首次调用延迟另列低优先级 controlled cold/warm investigation，不在当前 accepted baseline 上盲改。

## 强制回滚

| Role | Path | SHA-256 |
|---|---|---|
| r13 golden rollback | `out/candidates/m8a-initial-atv-r13/x12-m8a-initial-atv-r13.img` | `1D367F7091A7BD6A0791B2CFE45E7AAB551E0312D8C68136548A4927354A8E06` |
| Test8r2 rollback | `C:\Users\tiany\Documents\ubox10-rom改造\out\candidates\test8r2-restore-contacts-provider-r1\x12-test8r2-restore-contacts-provider.img` | `6A52F3388E9ABF6AFA8A701CFD7198FE6C0090F16531F6E3BD3949E760892EC8` |
| Stock recovery | `C:\Users\tiany\Documents\ubox10-rom改造\x12-1024.img` | `371A653604618E8B78786F279EA6F64E5D1028B430C9B41F330B08456A264065` |

Physical flashing requires a separate explicit user authorization. Never overwrite, rename or modify rollback sources.
