# M8 TODO

## Freeze decision

`m8b-remote-r1` 已冻结为 **FROZEN / DEVICE-ACCEPTED Android 12 working baseline**，作为稳定日用回退。`a16-prototype-a-r4` 现已冻结为 **PHYSICAL PASS / ACCEPTED Android 16 ARM32 ARCHITECTURE BASELINE / Prototype B ROLLBACK CONTROL**。用户明确把一次性、自动恢复的 boot-time `getAudioPort` SIGSEGV 从旧 Gate 2 startup-stability 条件改列为 **KNOWN / UNFIXED / POST-GATE P1 STABILIZATION DEBT**；故 Gate 2 为 **CLOSED / PASS**，不是静默弱化证据。当前不实施 Android 12 M8B feature、Prototype A r5 或 P1 polish；活跃架构路径是下述 Prototype B B1 bounded experiment。

## Android 16 Gate 1 / Gate 2 — Prototype A ARM32

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
- [x] 完成当时的 A/B/C source-proven 路线筛选：A（`android-security-16.0.0_r7` / API 36.0 / QPR0 + retained 5.4 lineage）排名第一但在 wireless checkpoint 前为 **HOLD**；B（r4 + 5.4 feature backports）和 C（5.10+ BSP port）为 **NO-GO**。该历史 HOLD 已由下述 r5 physical closure 与 exact r7 audit 解除；Prototype B 仍未启动。
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
- [x] 完成 original device-accepted BSP vs pinned donor/r1 focused semantic audit。Working BSP 与 donor 在 power/subsystem、SDIO setup/IRQ、firmware block-write、command manager、START_APP serializer 与 RX dispatch 上为 very strong same-lineage mapping；revision/U04 detection、USB-only reboot helper 与 LTO/thread organization 均不形成当前差异。唯一直接相关差异是 working upload+START_APP 均用 `0x00120000`，而 r1-r4 因 donor `CONFIG_AIC_INTF_SDIO` guard 未被实际 `AICWF_SDIO_SUPPORT` define 满足而编译为 `0x00110000`；exact FMAC vector 仍为 `0x00120189`。Donor/build mismatch **RAISED** 为 plausible root-cause candidate；最早边界前移到 wrong FMAC placement/bootaddr → AUTO handoff → FMAC execution。
- [x] 按 locked design 完成唯一 `m8-kernel-5.4.302-r5` offline build/audit/package：只把 `RAM_FMAC_FW_ADDR` guard 改为 `AICWF_SDIO_SUPPORT`；final packaged ELF 的 upload/patch-read/START_APP 为 `0x00120000`/`0x00120180`/`0x00120000`，与 working 5.4.125 BSP 一致。r4 trace/CCCR、firmware、Image/DT/userspace、ABI 与其他 21 modules 保持。镜像 1,031,739,392 bytes / SHA-256 `A185B0A3C7516FBC9D34F61B3218171F07BDA00B84903A644D2D71FBB1DCC28F`；AVB/ext4/LP/IMAGEWTY/focused checks PASS。该离线阶段未执行物理动作；后续 physical result 见下一项。
- [x] 用户已完成 `m8-kernel-5.4.302-r5` 物理验证：Linux 5.4.302+/Android boot、HDMI、遥控、Leanback/TV IME/Launcher、Wi-Fi 与 Wi-Fi ADB PASS。Initial 和 OFF→ON cycle 后 `timeout|wifi start fail|reqcfm|1037|1038` 两次过滤均为空；cycle 后完成 association/4-way/group handshake、DHCP、validated L3、IP/DNS ping 4/4 与 ADB reconnect。单次 `aicsdio: write retry: 20` 后初始化继续成功，按非致命 transient 记录。r1-r4 START_APP timeout 未复现。
- [x] same-lineage Linux 5.4.302 kernel/wireless preservation checkpoint **CLOSED / PASS**。接受 guard mismatch 导致 r1-r4 FMAC `0x00110000` 错位、r5 恢复 working BSP `0x00120000` contract 为有强单变量实机佐证的 engineering root cause；不扩张为未证明的 firmware/boot-ROM 内部结论。关闭 SDIO clock guessing、generic MMC revert、更多 START_APP instrumentation 与 r6 diagnostic。
- [x] 锁定并完成 exact `android-security-16.0.0_r7` source-only QPR0 audit：manifest `ebea28d151539ecf0730b1a4ab92ac33edc17ac9`，`BP2A.250805.034`，API 36.0，SPL 2025-08-05。5.4.302 满足 exact non-GKI 5.4.277 floor；cgroup/netd 六项 Path-A config bounded；APEX/VNDK31/linker/FCM6/SELinux/ARM32 TV product delta 可控。Full VINTF 仍只有继承 `CONFIG_NFS_FS=y` 对 FCM6 `n` 的 exit 65 exception，未声明 PASS。
- [x] 按 exact r7 contract transition source 并完成唯一 `ubox10_ceiling_arm-bp2a-userdebug` build：121,285/121,285 actions、exit 0；`BP2A.250805.034` / API36 / SPL 2025-08-05，ARMv7-A NEON/no-secondary/`zygote32`/shipping API31/VNDK31 合同 PASS。
- [x] 从 retained 5.4.302 integration clean build Path-A Image 与 exact 22-module set；相对 preservation config 只有 BLK_CGROUP/CPUSETS/PROC_PID_CPUSET 与 NET_CLS_MATCHALL/NET_ACT_POLICE/NET_ACT_BPF 六项 additions。模块 ABI/CRC、r5 FMAC `0x00120000`/`0x00120180`/`0x00120000`、generic MMC/SDIO、70 MHz、firmware、DT 与 hardware config preservation PASS；未创建 kernel r6。
- [x] 构建并完整离线审核唯一 `a16-prototype-a-r3`：firmware 1,239,738,368 bytes / `FA47939654B4E2A7E14FE963C7819296157338D33355E75D89E8086356071F1B`。ext4/e2fsck、AVB、LP/sparse roundtrip/A-B empty slots、IMAGEWTY、ARM32 ELF/name closure、35 APEX、VNDK31/linkerconfig、split SELinux、kernel 与 changed/preserved inventory close；vendor/product 和其余 hardware authority 保持。Focused 5/5、combined preservation 22/22、full repository 101 tests PASS（25 expected fixture skips）。
- [x] r3 full VINTF 严格记录 exit 65 / **INCOMPATIBLE**，唯一例外仍为 inherited `CONFIG_NFS_FS=y` 对 FCM-6 required `n`；两项 display HAL 已关闭且没有新 incompatibility。历史离线决定为 **OFFLINE CHECKED / READY TO REQUEST PHYSICAL VALIDATION**，不等于 runtime PASS。
- [x] 完成 r3 local physical validation/evidence capture：未 flash/reboot/build/image mutation。Android 16/API36、ARM32-only `zygote32`、Linux 5.4.302+、六项 Path-A config、APEX、service managers、system_server/SystemUI、TV/Leanback/IME 与 Ethernet 已运行时证明。原始 r3 first blocker 是缺少 EGL driver selector；在用户预先设置的 `persist.graphics.egl=mali` override 下 Mali-G31 GLES 3.2 composition PASS。结论 **CORE PATH-A ARCHITECTURE VIABILITY PHYSICALLY PROVEN / FORMAL CANDIDATE CLOSURE PENDING**。
- [x] 收敛本轮 hardware 边界：Wi-Fi modules/wlan0/scan/OFF→ON reinit PASS，association/DHCP/L3/DNS 因无法输入凭据为 NOT TESTED；IR Linux events PASS，但 scanCode 352 在 Android 为 UNKNOWN，`Generic.kl` 353→DPAD_CENTER root cause PROVEN；HDMI monitor 约 1 秒画面/约 5 秒黑屏为 physical FAIL；legacy HIDL audio HAL 在 observed HDMI transition 的 `getAudioPort` path null-pointer crash，HAL stability FAIL。Monitor 无音频输出，实际听音 NOT TESTED。
- [x] **1 — bounded r4 source delta：**source product 只加入 `ro.hardware.egl=mali` 并保留 accepted vendor `ro.board.platform=apollo`；新增 device-specific `sunxi-ir.kl`，与 r7 Generic 仅 scanCode 352→DPAD_CENTER 一行不同。未加入 default `persist.graphics.egl`，其他遥控映射不变。
- [x] **2 — r4 build/offline audit：**唯一 `a16-prototype-a-r4` 为 1,239,746,560 bytes / `E125DD8FFB9F5B4A7B2B9B86DD8377367409AB00D1B29BE1E719CE25768E2111`。ext4、AVB、LP、IMAGEWTY、ARM32 ELF、35 APEX、VNDK31/linker、split SELinux、Path-A kernel/22 modules 与 exact preservation close；full VINTF 仍只有 inherited NFS exit-65 exception。该历史离线时点状态为 **OFFLINE CHECKED / READY TO REQUEST PHYSICAL VALIDATION**；后续 physical result 见第 4–6 项。
- [x] **3 — strict preservation：**kernel/boot/vendor_dlkm/vendor/product、HDMI/audio/Wi-Fi/Ethernet hardware authority 未修改；outer 50 项仅 system/vbmeta consequences 四项改变，46 项 exact。r3→r4 system tree 无删除，功能语义 delta 只有 EGL property 与 Remote OK mapping。
- [x] **4 — r4 physical validation：**fresh exact r4 无 UART/`setprop` intervention 即到达 Mali-G31、stable SurfaceFlinger、Android UI 与 `sys.boot_completed=1`；`persist.graphics.egl` 空、`ro.hardware.egl=mali`、`ro.board.platform=apollo`。真实遥控 UP/DOWN/LEFT/RIGHT/OK/BACK/HOME PASS，InputManager 证明 `sunxi-ir.kl` scanCode 352→`DPAD_CENTER(23)`；EGL 和 Remote OK **PHYSICALLY PROVEN**。
- [x] **5 — unchanged subsystem regression：**HDMI **PASS / STABLE IN THIS VALIDATION**，r3 black-cycle 未复现但 root cause 未证明；Wi-Fi module/scan/association/WPA/DHCP/IPv4/DNS/Android VALIDATED/real use PASS，OFF→ON 因 Wi-Fi ADB self-disconnect 未完成且不记 FAIL；Ethernet current session 无 carrier、NOT RETESTED，r4 preservation + prior PASS 保持。Direct `tinyplay` HDMI TV audible 与 VLC video/audio/AudioFlinger steady-state playback PASS。
- [x] **6 — historical Gate 2 adjudication：**旧合同要求的 no-runtime EGL、Remote OK、stable HDMI、Wi-Fi association/L3 与 real audio sink playback 均 PASS；boot-time legacy HIDL `getAudioPort` null-address SIGSEGV 再现并 auto-recover，故按旧 **vendor audio HAL startup stability** criterion 得出 HOLD。该历史判断保留，不改写为当时已 PASS。
- [x] **7 — authorized Gate 2 policy closure：**用户明确决定 Architecture Gate 2 衡量 functional architecture viability，而非零缺陷 release maturity。r4 的 direct HDMI + real VLC audio/video、stable playback PIDs、auto-recovery 和 clean playback interval 足以关闭架构门；正式状态 **GATE 2 CLOSED / PASS**，r4 frozen。Boot crash 保持 **KNOWN / UNFIXED / POST-GATE P1**，不创建 Prototype A r5。
- [x] **8 — Prototype B B0 complete：**exact r7 source、r4 logical/vendor/AVB、official BPI commit `316cd80c...`、paired Mali、AOSP passthrough mapper→gralloc-1.x loader、cross-bitness handle design、vendor property ownership、mixed ABI/zygote init、VINTF/linker 和全 partition impact 已复核。三个 ARM64 same-process files boot-critical；Vulkan 为 post-boot capability。详见 `docs/m8/research/prototype-b-b0-readiness.md`。
- [x] **9 — Prototype B1 build readiness：GO。**允许下一任务构建 **一个** bounded B1：r4 + ARM64 primary/ARM32 secondary + `zygote64_32` + exact 三个 ARM64 graphics files + 最小 vendor property/system+vendor AVB consequences。Mali 只能从 `/work/local-proprietary/ubox10/prototype-b-b1/libGLES_mali.so` fail-closed intake（18,145,112 bytes / `03333D49...C7F8`），rights 不推定、blob 不进 Git；本轮没有 build/candidate。
- [x] **10 — same-r1 prebuild gate closure：**锁定 local Mali 本体 identity 正确；旧失败确认为
  `readelf -W -n` 单行 Build ID 与 anchored regex 不兼容。最小 parser 修复保留全部 fail-closed
  字段，normal/wide/no-ID tests 与真实 intake 均 PASS。`/work` build 前 free 252,889,870,336 bytes。
- [x] **11 — B1 provider/handle implementation gate：**exact QPR0 BP2A mixed product preflight PASS；
  exact r7 AOSP mapper 与 pinned public gralloc-1.x ARM64 输出 PASS；`private_handle_t` ARM32/ARM64
  232-byte/alignment-8、全部 transported offsets、`numFds=2`、`numInts=53` 相同，offline PASS。
- [ ] **12 — HOLD / same canonical `a16-prototype-b-r1` partition fit：**r4 `vendor_a` 固定
  119,066,624 bytes、ext4 数据区 117,104,640 bytes。只 staging 最小 mixed properties 与三个 exact
  providers 后，minimum ext4 为 135,270,400 bytes，AVB/FEC 前已 overflow **18,165,760 bytes**。
  任务禁止静默改 LP geometry，故 build 在 57,358/158,582 actions 后按政策停止；没有 candidate。
  下一步只能先批准并证明一个 exact extent/placement contract，然后恢复同一个 r1；不得创建 r2。

## Post-Gate stabilization / release hardening

- [ ] **P1 DEFERRED — legacy HIDL audio boot crash：**`getAudioPort` null-address SIGSEGV 仍真实、root cause 未证明、service auto-recovers、steady-state media PASS。只有出现 user-visible audio failure、restart loop、Prototype B worsening、HDMI hotplug failure、suspend/resume failure，或进入 release-stability target 时才重新提升优先级。
- [ ] **RELEASE HARDENING — SELinux enforcing：**运行时 enforcing compatibility 未证明；不是 Architecture Gate 2 条件。
- [ ] **INHERITED EXCEPTION — full VINTF：**`CONFIG_NFS_FS=y` 对 FCM-6 `n` 仍为唯一 exit-65 exception；不得称 PASS，也不为 B1 改 kernel。

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
- [x] architecture-ceiling study 与 B0 已锁定 paired AArch64 Mali、AOSP mapper adapter、multilib gralloc-1.x、lawful-local fail-closed intake、vendor property 与 AVB scope；ARM32 OMX/Cedar/media/HWC/audio/Wi-Fi/BT/DRM/TEE 继续进程隔离复用。B0 的 historical build-readiness GO 已执行；B1 当前以 actual staging 证明 **VENDOR_A PARTITION FIT HOLD**，不是 provider/architecture NO-GO。
