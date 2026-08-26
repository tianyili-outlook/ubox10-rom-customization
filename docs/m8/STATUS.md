# M8 status

Updated: 2026-08-26

## Golden baseline

`m8a-initial-atv-r13` 已完成实机验收，状态为 **GOLDEN BASELINE / DEVICE ACCEPTED**。

| 项目 | 结果 |
|---|---|
| 镜像 / SHA-256 | `out/candidates/m8a-initial-atv-r13/x12-m8a-initial-atv-r13.img` / `1D367F7091A7BD6A0791B2CFE45E7AAB551E0312D8C68136548A4927354A8E06` |
| boot / HOME | `sys.boot_completed=1`；Projectivy HOME PASS |
| provisioning | `device_provisioned=1`、`user_setup_complete=1`、`tv_user_setup_complete=1` PASS |
| 遥控 | DPAD、OK、BACK、Volume、HOME PASS |
| Power | 短按休眠、IR Power 唤醒、长按关机 PASS |
| 证据 | `logs/device/20260813-r13/` 的三个 UART 记录 |

## Accepted audio baseline

`m8b-audio-r2` 已完成实机验收，状态为 **DEVICE ACCEPTED / AUDIO PASS**。

| 项目 | 值 |
|---|---|
| 镜像 | `out/candidates/m8b-audio-r2/x12-m8b-audio-r2.img` |
| 大小 | 1025951744 bytes |
| SHA-256 | `B39300CB3E335D75C9D61594CD94565D9C24FC92F467F9050CD1E604D87E9C2C` |
| 音频合同 | `ro.treble.enabled=true`、`ro.vndk.version=31`、active `com.android.vndk.v31`，运行时 `default→vndk` 暴露 `libaudioroute.so` |
| 设备结果 | Apollo HAL 到达 `adev_open`；AudioFlinger 加载 primary interface 并建立 primary output；ALSA 识别 `ahubhdmi` 为 card 3 / `AUDIO_HDMI` |
| 媒体实测 | VLC 播放已知 HEVC+AAC 正常，时间线推进，HDMI TV 有声；kernel 报告 `HDMI Audio Enable Successfully` |
| VP9 runtime | **HARDWARE-RUNTIME PASS**；VLC 通过 `OMX.allwinner.video.decoder.vp9` / Cedar 播放已验证 VP9，远程时间位置推进并到达 EOF；未声称画质或逐帧正确性 |
| DRM / Widevine | framework/plugin **PRESENT AND OPERATIONAL**；Google Widevine CDM 16.1.0 可打开，`securityLevel=L3`，HDCP connected/max 均为 `NONE`，AVC/HEVC/VP9 均不要求 secure decoder；不构成 L1、secure playback 或商业服务认证 |
| 已继承通过 | Projectivy、native rc-core/repeat、exact `.kl`、DPAD/OK/BACK/HOME/Volume/Power/Menu 及 r5 既有功能 |

强制回滚仍为 `m8a-initial-atv-r13`：`out/candidates/m8a-initial-atv-r13/x12-m8a-initial-atv-r13.img`，SHA-256 `1D367F7091A7BD6A0791B2CFE45E7AAB551E0312D8C68136548A4927354A8E06`。

## Accepted IME milestone

`m8b-ime-r1` 已完成物理设备验收，状态为 **DEVICE ACCEPTED / IME PASS**，现由直接后继 `m8b-remote-r1` 继承。

| 项目 | 值 |
|---|---|
| 选择 | Android 12 AOSP `LeanbackIME`；`com.android.inputmethod.leanback/.service.LeanbackImeService`；source commit `40b72d02ed2af7d1696cd8903682dcfcd963323c` |
| live proof | 可逆安装后 IME discovery/enable/default PASS；真实 EditText 中 DPAD_CENTER 输入 `t`、DPAD_RIGHT 移焦、DPAD_CENTER 输入 `y`，UI hierarchy 精确读回 `ty`；BACK dismissal/reopen PASS；无 crash/retry |
| 镜像 | `out/candidates/m8b-ime-r1/x12-m8b-ime-r1.img`，1028208640 bytes，SHA-256 `B89612D5004BA3D8214F21E22E4BED7BFBA5B2F8FE441F9364315F851F1FE240` |
| 集成 | 标准 `PRODUCT_PACKAGES += LeanbackIME`；最终 product 差异为 `/app/LeanbackIME/**` 与 attributable NOTICE，accepted product properties 保持 |
| payload | 仅 `product_a`、`super.fex`、`Vsuper.fex`；system/vendor/vendor_dlkm、boot/kernel/vendor_boot、audio/graphics/DRM/rc-core/keylayout/SELinux 与其余外层 payload 不变 |
| device acceptance | fresh-data 首启正常进入 Projectivy；物理遥控和 Wi-Fi 正常；Wi-Fi 密码 EditText 无 ADB 介入即显示 LeanbackIME；package、inventory、enabled/default 均为预期 component；DPAD/OK、BACK、文字输入与 1920×1080 TV 观感 PASS |
| reboot persistence | 未单独执行；fresh-data 自动 enable/default 与实际物理使用已满足本里程碑，接受为非阻塞，不声明 reboot persistence PASS |
| 证据 | `docs/m8/device-tests/20260816-m8b-ime-r1/` |

## Frozen Android 12 working baseline

`m8b-remote-r1` 已正式冻结为 **FROZEN / DEVICE-ACCEPTED Android 12 working baseline**；它继承 **AUDIO PASS / IME PASS / REMOTE PASS**，作为 Android 16 架构工作的稳定日用回退与功能对照。除非 Android 16 架构结论明确要求回到 Android 12，本分支不再继续 M8B 功能开发、P1/P2 修复或清理工作。

| 项目 | 值 |
|---|---|
| 镜像 | `out/candidates/m8b-remote-r1/x12-m8b-remote-r1.img`，1031723008 bytes，SHA-256 `F3B09E5565AC4ED4E5EE326D392622E7B036A8519B8444B966E77CC4751B814A` |
| reused | accepted Android 12 AOSP `com.android.media.tv.remoteprovider` JAR/shared-library、TvRemoteProvider framework bridge 与 television/leanback features 原字节复用 |
| added | Google-original Remote Service 5.2.473254133（SHA-256 `9D1B5C...B973`、Google signer `456EDB...9137`）、exact privapp allowlist、CONNECT-only default-permissions、`com.ubox10.overlay.tvremote` static RRO |
| RRO | `/system/system_ext/overlay/UBOX10TvRemoteConfigOverlay.apk`；target `android`、priority 999、`config_tvRemoteServicePackage=com.google.android.tv.remote.service` |
| Bluetooth | 仅 default grant `BLUETOOTH_CONNECT`；未 default grant SCAN/ADVERTISE；未伪授予 signature-only `INJECT_EVENTS` |
| payload | logical 仅 `system_a`；外层 `super.fex`/`vbmeta_system.fex` 与两个 V companion 更新；`product_a`/LeanbackIME、vendor/vendor_dlkm、boot/kernel/vendor_boot 与其余外层 payload 保持 |
| proven provenance | Test9r2 已实机证明 6466/6467、`_androidtvremote2._tcp`、official Google TV iPhone discovery/TLS pair/navigation/phone text；本候选把当时唯一 deterministic blocker CONNECT 纳入首次启动默认授权 |
| runtime | `sys.boot_completed=1`；Remote Service 5.2.473254133 运行，CONNECT 为 `granted=true` + `GRANTED_BY_DEFAULT`，无需手工 grant；TCP `*:6466`/`*:6467` 监听；system_ext RRO 存在且 framework lookup 精确返回 Remote Service package |
| physical acceptance | Projectivy、物理遥控、Wi-Fi、Bluetooth、LeanbackIME 无基础回归；official Google TV iPhone discovery/pair、DPAD、BACK、HOME、Volume±、Mute 与真实 EditText phone keyboard text PASS |
| IME coexistence | 手机 Remote text-input mode 活跃时系统提示 `Use the keyboard on your mobile device` 并把输入交给手机；物理遥控导航仍工作。接受为 Android TV Remote session ownership，不视为 LeanbackIME 回归 |
| persistence | 未单独执行 reboot-persistence；无具体失败迹象，本里程碑接受为非阻塞，不声明独立 reboot PASS |
| Play guard | 当前实机 `com.android.vending`、`com.google.android.gms`、`com.google.android.gsf` 均不存在；候选未加入 Play/GMS、未改 feature identity 或 system/product properties，因此没有可执行的 Play runtime regression 测试，也未导入 Test9r2 `AccessRestrictedActivity` 变量 |
| observation | LeanbackIME boot 后首次调用明显慢于后续调用，偶尔需按 OK 两三次；仅列低优先级可用性调查，尚未确认 defect 或 root cause |
| offline checks | AOSP `systemimage`/`systemextimage`、donor v2/v3 signature、manifest/services/library、privapp/default grant、RRO target/resource、exact filesystem diff、四分区 e2fsck、AVB、LP、IMAGEWTY、14 项 focused tests 与全量 91 tests（3 fixture skip）PASS |
| 证据 | `docs/m8/device-tests/20260816-m8b-remote-r1/` |

详细实现、验收与回归边界见 `docs/m8/candidates/m8b-remote-r1.md`、`docs/m8/device-tests/20260816-m8b-remote-r1/` 与 `docs/DEVICE_TEST.md`。

## Active architecture transition

活跃架构开发位于 `codex/m8-architecture-ceiling` 的 Android 16 Path A。same-lineage Linux
5.4.302 r5 kernel/wireless preservation checkpoint 为 **CLOSED / PASS**，exact QPR0 r7 source
audit 为 PASS。r3 历史上以用户预先设置的 runtime EGL override 证明 Android 16/API36、
ARM32-only `zygote32`、Path-A 六项 config、system_server/SurfaceFlinger/Mali-G31 core
viability；其 HDMI 周期黑屏、Android OK unknown、Wi-Fi association 和真实音频输出边界保持为
当时的历史事实。

严格后继 `a16-prototype-a-r4` 已完成 exact-board build/offline audit 和 2026-08-26 physical
validation。其唯一实现变化仍是 source-generated `ro.hardware.egl=mali`（保留 vendor
`ro.board.platform=apollo`，无默认 `persist.graphics.egl`）与 device-specific `sunxi-ir`
scanCode 352→`DPAD_CENTER`；kernel/boot/22 modules/vendor/product 和 HDMI/audio/Wi-Fi/Ethernet
authority 未修改。Fresh r4 无 UART/`setprop` intervention 即 boot complete，Mali/UI、Remote OK、
稳定 HDMI、Wi-Fi association/DHCP/validated L3、direct HDMI audible audio 与真实 VLC video/audio
均物理 PASS。r3 黑屏循环未复现，但旧根因未证明。Boot 时 legacy audio HIDL
`getAudioPort` null-address SIGSEGV 仍复现并自动恢复；clean steady-state VLC playback 未出现新
crash。旧 Gate 2 的 **vendor audio HAL startup stability** 条件曾据此得到 HOLD；用户现已明确
授权把 Gate 2 改为 architecture/functional viability gate，并把该一次性 auto-recovered crash
列为 **KNOWN / UNFIXED / POST-GATE P1 STABILIZATION DEFECT**。因此当前正式状态为 **GATE 2
CLOSED / PASS**；这不是声称 audio bug 已修复。

`a16-prototype-a-r4` 现为 **PHYSICAL PASS / ACCEPTED ANDROID 16 ARM32 ARCHITECTURE BASELINE /
FROZEN CONTROL**。Android 12 `m8b-remote-r1` 继续作为 frozen daily-use fallback；r4 是所有未来
Prototype B 的 exact rollback/control。Enforcing SELinux 仍属 release hardening；full VINTF 的
inherited `CONFIG_NFS_FS=y` exit-65 exception 仍跟踪且不得称 PASS。

Prototype B0 preflight 已完成，其 historical decision 为 **B1 BUILD READINESS GO FOR ONE BOUNDED BUILD**。Exact
boot-critical set 为 paired ARM64 Mali、exact r7 AOSP passthrough mapper adapter 与 donor-source
ARM64 `gralloc.apollo.so`；mapper 通过 `hw_get_module()` 在 AArch64 consumer 内加载 gralloc。
Mali 297 个 strong imports 对 exact r7 ARM64 VNDK31/LLNDK unmatched 0。Adjacent H618 不是 exact
H616 proof，proprietary Mali redistribution rights 仍未证明；B1 只能使用 outside-Git、exact-hash、
fail-closed local intake。Mixed ABI/`zygote64_32`、vendor property、VINTF/linker、system+vendor
AVB/outer 和 rollback contract 已锁定，详见
`docs/m8/research/prototype-b-b0-readiness.md`。Vulkan 仍为 post-boot app capability；成熟 ARM32
HWC/media/audio/Wi-Fi/BT/DRM/TEE services 保持进程隔离。

同一 canonical `a16-prototype-b-r1` 已于 2026-08-26 继续执行。旧 HOLD 已关闭：Mali 本体的
18,145,112-byte / `03333D49...C7F8` identity 全部正确；旧失败是 checker 用 line-start regex
解析不了 `readelf -W -n` 单行 Build ID 的工具缺陷。最小 regex 修复后 size/SHA/ELF64/AArch64/
SONAME/Build ID/exact DT_NEEDED 仍全部 fail-closed，focused 正反测试与真实 intake 均 PASS。
`/work` build 前 free 为 252,889,870,336 bytes，host capacity 也 PASS。

Exact QPR0 `ubox10_ceiling_arm64-bp2a-userdebug` product preflight 为 ARM64 generic primary +
ARMv7-A NEON/cortex-a15 secondary、Apollo platform；exact r7 AOSP ARM64 mapper 与 public pinned
gralloc-1.x ARM64 provider 均编译 PASS。Compiler-derived `private_handle_t` 为两 ABI 相同的
232-byte/alignment-8、`numFds=2`、`numInts=53`、magic `0x03141592` 与全 transported offset；
**CROSS-BITNESS HANDLE LAYOUT OFFLINE PASS**。

随后 actual vendor staging 发现新的硬门槛：r4 `vendor_a` 固定 119,066,624 bytes，其中 ext4
可用区 117,104,640 bytes、仅余 368,640 bytes。只写最小 property delta 与 exact 三 provider 后，
`resize2fs -M` 仍需 135,270,400 bytes，即在重新生成 1,961,984-byte AVB/FEC/footer 前已至少超出
18,165,760 bytes。任务禁止静默改 LP geometry，故 system build 在 57,358/158,582 actions 后按政策
停止。正式状态为 **OFFLINE HOLD / NO CANDIDATE / PARTITION FIT BLOCKER**；未生成 system/vendor/
super/outer candidate，未执行 physical action，也不是 structural NO-GO。完整结果见
`docs/m8/candidates/a16-prototype-b-r1.md` 与其 machine-readable offline result。

2026-08-21 Android 16 Gate 1 状态为 **OFFLINE CHECKED / SUCCESS**。Source 为 exact `android-16.0.0_r4` / `BP4A.251205.006`，manifest commit `15128c9e27cfa599c48d294babd39286ee8f1426`，pinned manifest SHA-256 `4E8BEB5D1B590DFF3D631B1DBB957138DBDA4E608A3183C625683DA4BC84918F`；Prototype A 为 `ubox10_ceiling_arm-bp4a-userdebug`、ARMv7-A NEON、无 secondary arch、shipping API 31、extra VNDK 31、pKVM off。GCP native Ubuntu 24.04 / ext4 / 8 vCPU / 62.8 GiB RAM / no swap 上使用 relative `OUT_DIR=out-ceiling`、`BUILD_NUMBER=DISPOSABLE_CEILING_R4`、unset `SOONG_GOMEMLIMIT GOMEMLIMIT` 和 `m -j8 systemimage`，123,197/123,197 actions 成功，wall 30,314 秒（8:25:14）。最低 available RAM 12,295,132 KiB；swap I/O 为 0；平均 CPU user/system 约 88.05%/9.48%、I/O wait 0.05%；`/work` 最低 free 231,671,357,440 bytes。完整 raw log 仅保留在 GCP ignored 路径，未进入 Git。

唯一产物 `/work/src/ubox10-a16-ceiling/out-ceiling/target/product/generic/system.img` 为 946,765,824 bytes，SHA-256 `FD349F1D8073DFEB71E2CEA28915F1C755FA54E3EBA85616FCAA279063F3EDBE`。Raw ext4 `e2fsck -fn` clean；AVB SHA256_RSA2048 footer 与 system hashtree verify；staging 有 2,277 regular files、256 symlinks、997 个 ARM32 userspace ELF，另 7 个 ELF64 均为 Linux BPF object 而非 AArch64 userspace。36 个 installed APEX 全部可解析；`/system_ext/apex/com.android.vndk.v31.apex` 为 17,743,872 bytes / SHA-256 `FB94B4E2BA84BDEFDDFAF59729FDAE87B0195D2EEFD972FD69235DD7A12D705E`，含 ARM32 `libaudioroute.so` 与 v31 lists。A16 host linkerconfig 对实际 system/VNDK 生成 `[vendor]`、`/apex/com.android.vndk.v31/${LIB}` 和 `default→vndk` 的 `libaudioroute.so`；system-side `checkvintf --check-one` PASS，FCM 6 matrix 包含 5.4 kernel 分支；SELinux xattr、31.0 mapping 与 compiled policy 存在。只生成 `system.img`，未生成 boot/vendor/product/system_ext/super/userdata、IMAGEWTY 或可刷固件。

Gate 1 本身只证明 A16 ARM32 product 可以完整构建并在离线结构上满足预期；**不证明** UBOX10 boot、`apexd`/zygote/system_server/graphics/media/audio/wireless/DRM runtime 或 Gate 2。A16 VNDK 31 的 `libaudioroute.so` 也不是 accepted A12 文件的原字节（11,620 bytes / `9750F1...A2` vs 11,640 bytes / `BB5393...623`）；官方 v31 ABI/build 与 linker closure 通过，但 exact Apollo runtime 仍需实机验证。

### Android 16 Prototype A exact-board candidate

2026-08-21 已完成 accepted exact-board 离线集成，当时结论为 **OFFLINE CHECKED CANDIDATE / ELIGIBLE FOR ONE UART-FIRST AUTHORIZATION**。2026-08-22 用户另行明确授权并完成唯一一次 r1 物理刷写/启动；下述离线审计结果仍成立，但已被新的运行时失败边界补充。该历史 r1 时点的 Gate 2 继续 **CLOSED**；当前状态由文首 r5/r7 closure 取代。

输入在 GCP 逐项校验：`m8b-remote-r1` 外层镜像为 1,031,723,008 bytes / SHA-256 `F3B09E5565AC4ED4E5EE326D392622E7B036A8519B8444B966E77CC4751B814A`；Test8r2 rollback 为 2,005,954,560 bytes / `6A52F3388E9ABF6AFA8A701CFD7198FE6C0090F16531F6E3BD3949E760892EC8`。Accepted super、system/vendor/product/vendor_dlkm、boot、vendor_boot、vbmeta 与 Gate 1 system 均由 size/SHA-256 锁定；原始输入保持只读且构建前后 hash 一致。

初始 exact VINTF 审计发现三项真实差异：accepted vendor 暴露的 `vendor.display.config@1.0` 和 `vendor.display.output@2` 未在 A16 device matrix 中声明，以及实际 5.4.125 kernel 的 `CONFIG_NFS_FS=y` 与 FCM 6 要求的 `n` 不同。前两项用仅包含这两个 exact HAL 的 device matrix 闭合。NFS 项也存在于 device-accepted Android 12 FCM 6 对同一 kernel 的检查中，因此分类为继承 BSP conformance deviation；**完整 VINTF 仍返回 65 / INCOMPATIBLE，未声称 PASS**。把 kernel config 反事实改为 `n` 后 full check PASS，证明没有第二项剩余 VINTF 差异。

Exact split SELinux 的首错是 A16 platform 与 accepted API-31 vendor 对同一 `fuseblk /` 的冲突 `genfscon`；候选只移除 platform duplicate，保留 device-accepted vendor 的 `vfat` label，随后 exact `secilc` PASS。A16 linkerconfig 对 exact system/vendor/product/VNDK 31 生成 vendor namespace 和 `libaudioroute.so` link；1,769 个 ELF 的 class/name 级闭包无未解析项，且没有 AArch64 userspace ELF。四个 logical ext4 clean。官方 LP 工具确认 3 个相同 metadata slots、10.2/`virtual_ab_device`、原 3,221,225,472-byte super 与 1,651,167,232-byte system allocation；Gate 1 image 原始 headroom 为 704,401,408 bytes。候选 system 正好使用原 allocation，vendor/product/vendor_dlkm 与全部 B slot 原字节保持。

| 工件 | 大小 | SHA-256 |
|---|---:|---|
| `out/candidates/a16-prototype-a-r1/x12-a16-prototype-a-r1.img` | 1261038592 | `A034C8193236C93746E5962CB3E7F26A1D56CEC1435D5AD9D95F653B60BEBD83` |
| `system_a.img` | 1651167232 | `24CF6C9109CFDBBC8DB3A068E73EB5CD090440F58540AE6D62B8B667DB7DA2B5` |
| `super.fex` | 1081240172 | `DA043A276B28533E41FF17A7425604F1C79F68B2AA572260329EDC80E32F94D6` |
| `vbmeta_system.fex` | 1472 | `91C587E32CCA577F31770F6EE462FFE7F20594BCA6D4F84EB641C019440A21B1` |

候选 system 相对 accepted Gate 1 filesystem 的语义差异严格只有 `/system/etc/vintf/compatibility_matrix.device.xml` 与 `/system/etc/selinux/plat_sepolicy.cil`，文件 owner/mode/SELinux xattr 保持。System hashtree 与 `vbmeta_system` 使用既有项目 test key，rollback index `1644019200` / location 1 保持并通过 chain/standalone AVB verify；顶层 `vbmeta.fex` 原字节保留。外层 50 项中 46 项原字节保留，只替换 `super.fex`、`vbmeta_system.fex` 并重算两个 V companion；boot/kernel、vendor_boot、DTBO、TEE、metadata、media_data 与其他 rollback/recovery 依赖均未改。IMAGEWTY 12 个 payload checksum、SHA256SUMS、focused tests 与全量 70 tests（25 个缺少 ignored 历史 fixture 的 expected skip）PASS。

最终 detached candidate pass 用时 130 秒；`/work` free space 约从 184 GiB 到 181 GiB，可用内存约 60–61 GiB，无 swap。完整 intake/extraction/audit/build logs 保留在 GCP ignored 路径 `/work/build-logs/ubox10-a16-prototype-a/20260821T150330Z/`，未进入 Git。精确候选记录见 `docs/m8/candidates/a16-prototype-a-r1.md`。

### Android 16 Prototype A r1/r2 physical results and architecture hold

r1 状态为 **PHYSICAL FAIL — PRE-EXEC CGROUP INITIALIZATION / NOT ACCEPTED**。PhoenixCard 日志 `logs/20260822-a-r1/uart-putty.log`（44,206 bytes / `C4823F59F09FA2ED60E5F35251641B0B0E9ABFAFEF1318F065DAFBED901E4D0C`）确认写入成功；原 UART 日志 `logs/20260822-a-r1/boot.log`（78,275 bytes / `18BF7217AFA25CAB2B7443B17A801D8825932FA4EB15ADCFC87D6FE1C3F46C7F`）记录 7 次 kernel start、6 个完整重启周期。RAM-only `printk.devkmsg=on` 诊断日志 `logs/20260822-a-r1-devkmsg/boot-devkmsg-on.log` 为 35,625 bytes / SHA-256 `E3EF999E109B837C5DBB3390E110EC80AD3D9DEFE02F0B0CAF581C46C4C2A517`；该参数在 `run boot_normal` 前从 bootargs 回读确认，未写入 boot image 或持久 U-Boot 环境。

诊断把首个可重复边界精确提前到 Android 16 cgroup setup。5.204791 秒的 `cgroup1: Unknown subsys name 'blkio'` 令 required blkio mount 返回 `EINVAL`，`CgroupSetup()` 在创建 cgroup-v2 `apps`/`system` 子层级之前返回。Init 随后 fork PID 163/164，但 parent 的 `createProcessGroup(0, pid, false)` 无法创建 `/sys/fs/cgroup/system/uid_0`，通过 FIFO 返回 `kActivatingCgroupsFailed`；child 在 task profiles、credentials/caps 与 `ExpandArgsAndExecv()` 之前 fatal exit。因此 `ueventd` 与 `apexd-bootstrap` **均未 exec，bootstrap APEX activation 没有被尝试**。Kernel、first-stage init、LP/system handoff、split SELinux compile/load 与 second-stage init 已证明；servicemanager、zygote32、system_server、SurfaceFlinger、HWC 均未到达。SELinux 为 permissive，不声称 enforcing compatibility。

Exact `android-16.0.0_r4` source 证明这是一个连贯的 pre-exec failure path。Effective `/system/etc/cgroups.json` 要求非 optional 的 v1 blkio/cpu/cpuset，并使用 `/sys/fs/cgroup` v2 root；freezer required，memory v2 `NeedsActivation` 但 optional。first API 31 的 system override 与 accepted `/vendor/etc/cgroups.json`、`task_profiles.json` 都不存在。`libprocessgroup` 与 early `libprocessgroup_setup` 同时消费 `cgroup_v2_sys_app_isolation=true`，不存在 build-flag split。Retained 5.4.125 config 已有 CGROUPS、CGROUP_SCHED、CPUACCT、FREEZER、BPF，但 `BLK_CGROUP=n`、`CPUSETS=n`、`MEMCG=n`；只启用 BLK_CGROUP 会在下一个 required cpuset mount 再失败。

四类消息的最终分类为：blkio 是首个 causal blocker；missing `pid_163`/`pid_164/cgroup.procs` 是失败清理 cascade；`Could not update logical partition` 与 early secilc `/linkerconfig/ld.config.txt` warning 是已继续执行的 non-fatal early path；missing `/dev/block/by-name/misc` 只发生在 `reboot_on_failure` 已选择重启后。重启 reason 是 service policy 的结果，不是 apexd 内部错误。

唯一 Prototype A r2 先在 GCP 原生 Linux 上离线构建并审核，随后由用户单独授权并完成一次物理测试。Kernel source 固定为 Orange Pi commit `9ab7a758149d3c9b721878a0c18b3f9c5d6c93e6`，compiler 为 AOSP `clang-r416183b1`。唯一有效 config delta 是 `CONFIG_BLK_CGROUP=y`、`CONFIG_CPUSETS=y` 及 Kconfig 自动启用的 `CONFIG_PROC_PID_CPUSET=y`；MEMCG 与新显露的 blkio throttling/IOLATENCY/IOCOST policy 保持关闭。候选仅替换 kernel、`boot.fex` 和生成的 `Vboot.fex`；r1 system/APEX/super/LP、vendor_boot/ramdisk、vendor/product/vendor_dlkm、vbmeta/vbmeta_system 与其余 48/50 outer payload 原字节保持。

| r2 工件 | 大小 | SHA-256 |
|---|---:|---|
| `out/candidates/a16-prototype-a-r2/x12-a16-prototype-a-r2.img` | 1261038592 | `114DF8677CD6984EB1431377723EDF61C80ACF26C15D8770BAE47DCFE7D1B6D0` |
| `boot.fex` | 67108864 | `4F0DB0070E294DEA93319F4B21335E6725DBB7B70066E7C1E6BF55CFEB09C10C` |
| kernel `Image` | 23232520 | `5D7D7F84A8E3CBCC4A4AF78A9EB4DECAC846E62BA4C681E85B438B69B196EBF3` |
| `candidate.config` | 141009 | `0F2284289AE5374296EA180F128BFEE12F648D75A1BBE575AE21F50A8582E02E` |

Detached compile/pack 加无特权审计 wall 约 13 分 03 秒，其中包含一次约 3 分钟的 host mount 权限停顿；已完成的 kernel/outer 没有重编，审计续跑 4 秒成功。21 个资源样本中 available RAM 最低 31,036,456 KiB，无 swap；`/work` available 最低 182,048,014,336 bytes，远高于安全阈值。Boot AVB footer/hash 验证、IMAGEWTY、50-entry outer preservation、四 logical ext4、cgroup/config contract 与 SHA256SUMS PASS；r2 focused 5 tests 与全量 75 tests PASS（25 个缺少 ignored 历史 fixture 的 expected skip）。Full exact VINTF exit 65 的唯一错误仍是继承的 `CONFIG_NFS_FS=y` 对 FCM 6 `n`，r2 未引入新错误；linker/ELF、split SELinux、APEX 与 LP 结果由相关分区逐字节等同 r1 后继承。完整 raw logs 保留在 ignored `/work/build-logs/ubox10-a16-gate2-cgroup/20260821T180108Z/`。

r2 PhoenixCard 日志 `logs/20260822-a-r2/uart-flash-r2.log` 为 44,451 bytes / SHA-256 `832E3BEDC7BD50E3D9B562FFEE375189825EE3ECA1A3E67D8026157E4545DD2E`；13 个 download parts 全部成功并以 `CARD OK` / `sprite success` 结束。UART 日志 `logs/20260822-a-r2/boot-r2-devkmsg-on.log` 为 67,394 bytes / `BF3196E9DB99AF4F70B5F7CEA5CBA166A40A92299E9670ED517357F2EEE5C4AC`；U-Boot RAM-only `printk.devkmsg=on` 在启动前回读确认。日志包含 5 次 5.4.125 kernel start 和 4 个完整、相同的失败周期。

r2 运行时证明 required blkio/cpuset 与 `/sys/fs/cgroup/system` 已建立，r1 的 `/uid_0` pre-exec failure 消失；ueventd 实际执行，servicemanager、hwservicemanager、vndservicemanager 实际运行，且 init 读取 `/apex/com.android.uprobestats/etc/init.rc`。`bootstrap-apexd-failed` 不再出现。四个完整周期的首个 fatal 均为 `NetBpfLoad: Android 25Q4 requires kernel 5.10.`，随后 init 执行 bpfloader 的 `reboot_on_failure` 并以 `bpfloader-failed` 重启。Zygote32、system_server、SurfaceFlinger 与 HWC 仍未到达。

新兼容性信号已按控制流分类：5.4 不支持 `memory_recursiveprot`，但 A16 `CgroupSetup()` 明确无该选项重试且 r2 继续执行；`CAP_PERFMON` 缺失只使 disabled UprobeStats service 的 init stanza 失效，不是本轮 boot fatal，但代表真实的后续功能缺口；IncFS module 缺失会回退为 features v1/none，当前不阻塞普通启动；`/dev/stune/foreground/tasks` 与大部分 cgroup cleanup 消息发生在 bpfloader 已选择 shutdown 后。当前未发现新的 pre-bpfloader task-profile fatal。

Source-proven 路线结论如下：

| 排名 | 路线 | 结论 | 证据与边界 |
|---:|---|---|---|
| 1 | A：QPR0 A16 + retained 5.4 lineage | **SELECTED / SOURCE-AUDIT GO** | Exact `android-security-16.0.0_r7` 为 `BP2A.250805.034`、manifest `ebea28d151539ecf0730b1a4ab92ac33edc17ac9`、API 36.0 / 25Q2 / QPR0 / SPL 2025-08-05。NetBpfLoad fatal floor 是 5.4，netd non-GKI 5.4 floor 是 5.4.277；physical-pass 5.4.302 合格。Path-A 六项 cgroup/netd config 可在 retained lineage bounded closure。 |
| 2 | B：r4 / 25Q4 + 5.4 backports | **NO-GO（当前 bounded Gate 2）** | r4 loader 与 netd 都以版本要求 5.10（并要求 5.10.210 LTS floor）；现有 5.4 还真实缺 ringbuf、CAP_PERFMON/BPF capability split、uprobes/ftrace、vmlinux BTF、BPF link/batch API 等。只删除检查或伪造 uname 不合法；完整回移已不是 bounded fix。 |
| 3 | C：H616 5.10+ | **NO-GO（当前项目）** | Orange Pi `orange-pi-5.10` 是 5.10.75 / `e39ff11e...` 的 mainline-style H616 树，不含 retained 5.4 的 SUNXI display/Cedar/VIN/G2D/gralloc/DRM-heap/USB vendor stack。22 个 accepted vendor_dlkm modules 及 graphics/media/audio/TEE/wireless UAPI 都需同步移植或重建，实质是新 BSP/kernel port。 |

在 5.4.302 checkpoint 开始前，总决策因此为 **HOLD**：保留 Android 16/API 36 目标和 TV 适用性，但不再以 r4/25Q4 + exact 5.4.125 构建候选；当时要求先完成可审查的 same-lineage LTS update。下节记录该条件的离线结果；这不改写 r2 历史结论，也不开放 Gate 2。

### Linux 5.4.302 same-lineage BSP checkpoint

该 checkpoint 的最终结论为 **CLOSED / PASS**。历史 r1-r4 diagnostics 与失败边界保持不变；r5 physical validation 已关闭唯一 wireless 缺口，详见本节末尾和 `docs/m8/candidates/m8-kernel-5.4.302-r5.md`。期间没有构建 A16 r3、Prototype B 或 5.10 port。

Retained source 精确为 Orange Pi commit `9ab7a758149d3c9b721878a0c18b3f9c5d6c93e6` / tree `d37d590a1e61c8e099e72170bf36e54091aa4820` / `5.4.125+`。该七提交 BSP import 与 upstream v5.4.125 (`3909e237...`) 或 v5.4.302 (`9e3157c5...`) 都没有 Git merge-base，不能安全 blind rebase。最终策略用 Android common 5.4.125 merge commit `6cb0d5ef...` 作为 synthetic base，以 exact vendor tree 为 ours，合入包含 upstream v5.4.302 的 Android common `2443acb8...`。46 个冲突逐项分类为 31 upstream/common wins、12 vendor wins、3 semantic merge；可复现脚本在独立 worktree 17 秒精确重放最终 commit `027ef79e8facb73cb2419b4a08c0bd3f13a2206e` / tree `b328c32712d65f8da98e013bc74944d68c05552b`。

Pre-change inventory 记录 4,603 个 vendor-delta files（4,056 A / 494 M / 53 D）、384 个 LTS overlap 和 434 个 hardware-critical exported symbols。H616/sun50iw9 DTS、SUNXI display/HDMI、Mali-Bifrost、Cedar/VIN、G2D/DI/gralloc/DRM heap、AIC8800 与 SUNXI USB 关键 subtree 在 integration 前后 Git object 完全一致；audio、Ethernet、IR、thermal/DVFS、suspend/wake、DM/AVB 与 generic TEE/OP-TEE source/config 另行审核。Accepted rc-core repeat patch、ff40 keymap、XR819、AIC8800 `20221108-004` 与 vendor RTLwifi source 均由 commit/subtree/hash 锁定并重建。

Primary Android 12 preservation config 从 accepted Image 精确提取，140,888 bytes / `9D3DF7457F0921E1E5983ADB2DBD36A89042CE70BB28EBFEADA7FD5E633D677C`；5.4.302 effective config 为 141,140 bytes / `FA73240A16B52569D28EADF4AFD59834F05AEDD6B69F573863A611B3E359A75D`。32 个变化全部是新/移除 Kconfig 表达、Android KABI padding、stable ARM64 erratum/security/helper defaults 或保持为 `n` 的新增/淘汰选项，逐项解释与 exact diff 已 tracked。主 Image 不引入 A16-only config。Separate Path-A config 验证 `BLK_CGROUP`、`CPUSETS`、`PROC_PID_CPUSET`、`NET_CLS_MATCHALL`、`NET_ACT_POLICE`、`NET_ACT_BPF` 可作为六项 bounded `y` additions，三个新 blkio policy 保持 `n`。

Native GCP clean build 复用 AOSP `clang-r416183b1` / clang 12.0.7，main compile 639 秒、sequential external-module finalization 64 秒，总 wall 703 秒。Image 为 23,492,616 bytes / `9B781ABEA51DEF9AE1FEBB9011CFA630AC267C794FBA0E066674F0EAE2509DCC`，release `5.4.302+`。22 个 accepted vendor_dlkm module name/dependency/alias/firmware/version/license/export-name contract 全部保留，所有新 import CRC 都由 exact 5.4.302 symbol-version set 满足，vermagic 统一为 `5.4.302+ SMP preempt mod_unload modversions aarch64`；旧 5.4.125 modules 不被复用。11 个编译 warning 与一次 vendor Mali parallel make race 全部分类记录；相同 source 的 sequential build 零 error，最终 offline audit 为 `PASS_WITH_PHYSICAL_VALIDATION_REQUIRED`。最低 sampled available RAM 56,826,608 KiB、无 swap；`/work` available 最低 164,776,160 KiB，未发生 OOM/I/O failure。

唯一 Android 12 kernel-only candidate 为：

| 工件 | 大小 | SHA-256 |
|---|---:|---|
| `out/candidates/m8-kernel-5.4.302-r1/x12-m8-kernel-5.4.302-r1.img` | 1031739392 | `C93FC8A54391E091E0F95CFE63E4F6DA9AE90D55AA0163D91D42586B48BFEE2B` |
| `boot.fex` | 67108864 | `338CB4048796E213698585E035D8807D84381324163C19AA939BD8D6BFDDCD2C` |
| `super.fex` | 851940812 | `913CDED66A315EBD401F042037A2DEE4660209D90AE56C2C45E476BB40742957` |
| `vendor_dlkm_a.img` | 6680576 | `5B6FED8C5709F994450A2B3177A67E2F1BA94C17C170628F422A1EECE8BEC199` |

Candidate 保留 accepted boot header/cmdline/ramdisk/partition geometry，替换 exact kernel；在 fixed vendor_dlkm extent 中替换匹配的全部 22 modules，保留 mode/uid/gid/timestamps/SELinux labels、module metadata 与所有 non-module files，ext4 `e2fsck` PASS 且剩 1 个 4 KiB free block。Boot AVB、vendor_dlkm AVB hashtree/FEC、LP metadata/extents、sparse→raw exact roundtrip、IMAGEWTY 12/12 checksums 均 PASS。`system_a`、`vendor_a`、`product_a` 原字节保持；outer 仅 `boot.fex`、`super.fex` 与 V companions 改变，其余 46/50（含 bootloader、TEE、vendor_boot、DTBO、vbmeta/vbmeta_system、GPT/factory/security payload）原字节保持。Accepted `m8b-remote-r1` 与 Test8r2 rollback 构建前后 hash 不变。

Final validation 将 424,597-byte vendor inventory 与 39,373-byte offline audit 按原
SHA-256 byte-for-byte 重生；repository suite 80 tests 全通过，25 个 skip 仅对应本机
不存在的 ignored historical artifacts，5.4.302 checkpoint 的 5 tests 全部实际执行。
Selected integration、retained vendor input、两个 module donor、AOSP 与 toolchain checkout
均 clean；disposable 5.4.302 build worktree 已移除但 build outputs/logs 保留。历史 accepted
A16 r2 build worktree 保持原状，其唯一 status 是已在 r2 构建记录中锁定的 untracked
`drivers/net/wireless/xr819/` donor subtree，不属于本 checkpoint 的未记录修改。

原离线 evidence 本身不会运行 display、GPU、media、audio、wireless、Ethernet、USB、IR、thermal/DVFS、suspend/wake 或 secure-world path；vendor_dlkm 只有一块 free space 的风险仍需保留。后续 r1-r4 逐步证明 core/board contract 并收敛 Wi-Fi 边界，r5 现已物理证明 boot/HDMI/UI/remote/Wi-Fi 和一次完整无线 reinitialization。因此 Path A kernel/wireless 子 checkpoint 为 **CLOSED / PASS**；这项关闭解除 QPR0 audit 阻塞，但不单独使 Gate 2 PASS。

### Linux 5.4.302 r1 physical Wi-Fi boundary and r2 diagnostic

用户已另行授权并完成 r1 的一次 Android 12 实机回归。Linux 5.4.302 正常启动，`sys.boot_completed=1`；HDMI/UI、遥控、Ethernet 与 ADB PASS。唯一收敛失败是 AIC8800D Wi-Fi：SDIO card 枚举、`aic8800d`/U04 匹配、固件路径与三模块打包都成功，随后稳定出现 `Set SDIO Clock 66 MHz`、`cmd:1037 - reqcfm(1038)` timeout、`wifi start fail`、BSP remove 与 SDIO card remove。它排除 Android Wi-Fi HAL/framework 和简单 module/firmware missing 作为首因，把首个可重复边界定在 firmware START_APP confirmation 缺失。当前没有本地 raw r1 UART capture 可供 hash-lock；上述物理结果按用户提供的现场证据记录，不虚构日志 provenance。

Pinned AIC source 审计证明 66 MHz 不是日志猜测。Donor commit `abfe04920992577c71a4180a8480a4a774965c76` 的 `FEATURE_SDIO_CLOCK=70000000` 经 `aicbsp_get_feature()` 进入 `aicwf_sdio_func_init()`；代码直接设置 `host->ios.clock` 并调用 MMC host `ops->set_ios()`。Exact `allwinner,sunxi-mmc-v4p1x` SDR path 把 module clock 设为逻辑值两倍，`clk_round_rate()` 到约 133.333 MHz，再回写约 66.666 MHz，故 post-set 日志为 66 MHz。该调用位于 `aicbsp_8800d_fw_init()` 与 `rwnx_send_dbg_start_app_req()` 之前，START_APP 的两秒 confirmation wait 期间没有其他 AIC clock write；host claim/release 也不恢复 clock。

唯一 r2 source delta 是 tracked patch 把上述 AIC feature request 从 70,000,000 改为 50,000,000；没有改 DT/DTBO、firmware、userspace/HAL、generic MMC timeout/retry/core、kernel config 或其他 module。Clean clang-r416183b1 build 548 秒成功，22 modules 齐全；新 `aic8800_bsp.ko` 为 127,752 bytes / `D3BA64E43FCD708B4EB7628576D83A01581023181271E0CF76613DD9BC4528F3`，vermagic/dependencies/normalized symbols 与 r1 相同。由于 clean ThinLTO build 会产生绝对路径和私有 `.llvm` ID byte drift，严格候选复用已实机 r1 的 Image 与 21 module bytes，只替换这一 BSP module；machine result 为 `PASS_SINGLE_VARIABLE_OFFLINE`。

`m8-kernel-5.4.302-r2` 的构建/离线阶段结果为 **OFFLINE-CHECKED DIAGNOSTIC / NOT ACCEPTED**：1,031,739,392 bytes / SHA-256 `A2963FD46685829774DBF5EA2E899ED5844BF44329BC8F46788F1D14D09AA036`。Boot/Image/ramdisk/DT/AVB 原字节等同 r1；system/vendor/product、LP geometry 与 21 modules 保持；只有 vendor_dlkm 的 `aic8800_bsp.ko`、对应 AVB/FEC、super extent 和 `Vsuper` companion 改变，48/50 outer payload 保持。IMAGEWTY、boot/vendor_dlkm AVB、ext4/e2fsck、sparse round trip、LP 与 hash checks PASS。Kernel/module clean build 548 秒，deterministic candidate assembly 约 106 秒；最低 sampled available RAM 60,776,856 KiB，`/work` available 147,466,500 KiB，无 swap/OOM/I/O failure。Focused tests 与全量 84 tests PASS（25 expected fixture skips）。完整记录见 `docs/m8/candidates/m8-kernel-5.4.302-r2.md`；原始 build/audit logs 保留在 ignored `/work/build-logs/m8-kernel-5.4.302-r2/`。

r2 已另行授权并完成实机验证，状态为 **PHYSICALLY FAILED / 50 MHZ HYPOTHESIS REJECTED**。运行时明确出现 `Set SDIO Clock 50 MHz`，随后仍重复 `tkn[476] flags:0012 ... cmd:1037 - reqcfm(1038)`、`wifi start fail` 与 SDIO remove。Android 12 仍 boot complete，Ethernet/ADB 正常；BSP/btlpm 保持加载，fdrv 不保持，`wlan0` 不存在；HAL service 存在而 framework `CMD_STA_START_FAILURE` 属于下游结果。不得再猜测 SDIO 频率。

针对 exact retained vendor `9ab7a758...` 与 integration `027ef79e...` 的系统 diff 得出：generic `sdio_irq.c`、`sdio_io.c`、`sdio_ops.c`，MMC public host/card/function headers，以及全部 retained `sunxi-mmc*` host source 在两树之间相同；`mmc_request_done`、request wait、claim/release 也没有 changed hunk。LTS range 中冷启动可达的主要差异只剩 OCR range fix `076712ff...`，但它不改变已选 `ios.vdd`，且 card enumeration、firmware transfer 和先前 confirmation 都成功。Clock quirk `ea7e57d...` 已被 r2 排除；retune、NONSTD_SDIO、refcount/remove、host-cap validation、shutdown/SPI deltas 均由 exact call-path 证明 inactive 或发生在 timeout 之后。

Pinned AIC RX 链为 SUNXI IRQ → `ksdioirqd` → AIC IRQ handler → block-count CMD52 → CMD53 read → RX thread → config type `0x11` → message ID dispatch → token completion。Flags `0x0012` 表示 `REQ_CFM|WAIT_CFM`；token 476 又证明此前 476 个 blocking request/confirmation 已通过同一 transport/dispatch/completion machinery。现有输出却未记录 START_APP final TX return、IRQ entry、RX length/header/id，无法区分 final TX、firmware IRQ、CMD53 RX、protocol response 与 dispatcher 边界。没有一个 changed generic MMC commit 得到足够支持来安全行为回退，因此本轮没有构建多变量或猜测性候选。完整 ranking 与 exact upstream IDs 见 `docs/m8/candidates/m8-kernel-5.4.302-r2.md`。

`m8-kernel-5.4.302-r3` 已把上述缺口实现为严格 START_APP-gated observability。Patch 不硬编码 token 476；在真实 1037 command 获得 runtime token 后 arm generation，并以 final-CMD53 的 `not attempted` / `in call` / `returned` state 排除 TX attempt 前的旧 IRQ/RX，同时分开记录 post-attempt 与 post-return 活动。Summary 包含同步 bus TX 与最终 CMD53 requested length/return、AIC IRQ count 与 block-count CMD52、CMD53 RX requested length/return、frame type/message ID、1038 dispatch、token match 与 completion，随后在原 success/timeout 后只输出一条 `AIC_STARTAPP_TRACE:`。没有新增 sleep/retry/lock/claim/completion/timeout 或改变 MMC behavior；`FEATURE_SDIO_CLOCK` 保持 70,000,000。

Clean clang-r416183b1 build 565 秒成功，22 modules 完整；instrumented BSP 为 129,280 bytes / `1A64A5E98CBA60FC0D619014245F1FFCF9B4C983AB6092F084F5547978126AD8`，module metadata 与 normalized symbol contract 等同 r1。Candidate 严格复用 r1 boot/Image/DT/userspace 和 21 module bytes；只有 BSP、vendor_dlkm AVB/FEC、super extent 与 `Vsuper` companion 改变，48/50 outer payload 保持。最终镜像 `out/candidates/m8-kernel-5.4.302-r3/x12-m8-kernel-5.4.302-r3.img` 为 1,031,739,392 bytes / SHA-256 `9E52B601F11F9368599098B4C5082037D010930D9B424D7CA2828977047C1B28`。AVB/ext4/e2fsck/LP/sparse round trip/IMAGEWTY/source/single-module checks PASS；vendor_dlkm 仍剩一个 4 KiB block；仓库 88 tests PASS（25 expected skips）。完整记录见 `docs/m8/candidates/m8-kernel-5.4.302-r3.md`。

用户随后单独授权并执行 r3；一次手动 Wi-Fi ON 与一次 framework self-recovery 均得到完全相同的 token 476 trace：final 512-byte CMD53 与 bus TX 在 Linux host 返回 0，随后 attributable AIC IRQ、block-count CMD52、CMD53 RX、1038 dispatch、token match、completion 全部为零，再发生 1037→1038 timeout 和 teardown。因此 r3 状态为 **PHYSICAL DIAGNOSTIC PASS / WI-FI FAIL / POST-TX PRE-AIC-HANDLER BOUNDARY PROVEN**，不是 fix。它不证明 card/firmware 消费 START_APP，也不区分 card 未保留 pending 与 asserted/pending IRQ 在 AIC handler 之前丢失。

Exact source review 证明 current r3 不能可靠完成下一层只读判别：debugfs/devmem/MMC debug 未启用，SDIO sysfs 没有 CCCR pending，shared host IRQ count 不可归属；SUNXI 全寄存器 dump 会无 host claim 地读取 `0x000..0x14c`，不能证明无副作用且不含 card CCCR；card 又在 timeout 后约 188 ms 被移除。Exact hardware-IRQ path 是 card DAT1 → SUNXI `MISTA/RINTR[16]` → `mmc_signal_sdio_irq()` → `host->sdio_irq_pending`/`ksdioirqd/mmc2` → single-function fast path → AIC handler。CCCR `INTx` 是此边界最小的 card-level pending discriminator。

`m8-kernel-5.4.302-r4` 因此只在原 timeout 已成立后、teardown 前，保留 trace active 并依序只读 CCCR `INTx`/`IENx`，同时 snapshot function number、`MMC_CAP_SDIO_IRQ`、core pending、IRQ claim 与 handler 安装状态；随后关闭 trace 并输出同一条 summary。没有 write、sleep、retry、timeout/firmware/clock/DT/config/userspace 或 timeout 前控制流变化，70 MHz 行为不变。首次 ABI audit 拒绝了 MMC header 对两个 AIC export CRC 的非功能漂移；final patch 以 tree 已有 `__GENKSYMS__` KABI technique 隔离 implementation headers，最终 `aic8800.Module.symvers` 恢复为 r1 byte-identical。

Final clean clang-r416183b1 build 831 秒成功，22 modules 完整；r4 BSP 为 129,976 bytes / `C993867D21988F0F1C4E32A9857821ADDA7899374B440688131E2CD9897F8CA4`。Machine audit 为 `PASS_POST_TIMEOUT_CCCR_INSTRUMENTATION_ONLY`：config/DT/AIC export names+CRCs/module metadata 保持，唯一新增 import 为 kernel 已有 `sdio_f0_readb`，candidate root 仅 BSP 变化。Candidate assembly 151 秒成功；最终 `out/candidates/m8-kernel-5.4.302-r4/x12-m8-kernel-5.4.302-r4.img` 为 1,031,739,392 bytes / SHA-256 `18565E4F94FF1A843EA859254800E5E2BA732FBFE47410E86D6577038F85DFCA`。r1 boot/Image/DT/userspace/21 modules、LP geometry 与 48/50 outer payload 保持；AVB/FEC、ext4/e2fsck、sparse round trip、IMAGEWTY PASS。

用户随后单独授权并完成 r4 physical diagnostic。Android 12 在 Linux 5.4.302+ boot complete；exact r4 trace schema 与 audited candidate chain 证明 instrumented BSP 运行。一次手动 Wi-Fi ON 与一次正常 framework self-recovery 都得到 token 476、24-byte bus TX / final function-1 512-byte CMD53 host return 0，随后 IRQ/RX/1038/token/completion 全零。Timeout snapshot 均为 function 1、hardware SDIO IRQ、claim/handler 正常，`IENx=0x03`、`INTx=0x00`、core pending=0：没有 standards-compliant persistent function pending indication 保留到 timeout。该结果不证明 card FIFO dequeue、不排除 transient/malformed/self-cleared indication，也不证明 firmware failure。自然启动的一次 `aicwf_sdio_hal_irqhandler: Interrupt but no data` 由 exact source 证明 AIC handler 在更早状态真实进入，但不证明 START_APP response IRQ。

随后完成 exact U04 device-contract archaeology。Preserved `fmacfw.bin` 为 260,984 bytes / SHA-256 `FC3BC7865CBB01560E706E87FEA23F07CBF86B0E9F76649381D553FE8E781904`，Cortex-M vector 对应 load base `0x00120000`，version `v6.4.3.1` / 2022-10-08 / `gb01a3750`。Binary debug table 把 1037 映射到 `0x00144f61`：handler allocate 1038；type 3 实现 reboot；type >3 记录 invalid；然后把 indirect ROM/API selector 15 的 low byte 写入 `bootstatus`，输出 `DBG: FW started` 并 send。四个后续 public AIC8800 U03/U04 FMAC release 保持相同控制流，属于 strong same-chip lineage；same-vendor AIC8800 pre-transfer proxy 的 AUTO stop host interface 并 program/reset-launch vector，但不构造 CFM。由此最佳推断是 initial 1038 由 FMAC 在 execution transfer 后产生，但 exact U04 boot-ROM source/ROM map 未找到，故 authoritative ownership 仍为 unknown，不得把推断当证明。

Device-contract archaeology 没有找到 exact U04 read-only dequeue pointer、boot latch、CPU PC/status、FMAC-ready magic、exception state 或 CFM-constructed bit；`bootstatus` 只在缺失的 1038 内存在，different-chip FNCALL/DUMMY/COMREG 也不适合作为 U04 discriminator。随后对 accepted `m8b-remote-r1` BSP binary 与 pinned donor/r1 做 focused semantic audit：accepted 132,072-byte module / `C0660486...A835D` 与 r1 127,752-byte module / `2EF8EF0A...1C96B` 共享 compiler、2022-11-08 lineage、command manager、power/subsystem、firmware block-write、START_APP serialization、RX dispatch 与关键 SDIO machine code，属于 very strong same-lineage mapping，但不是 exact source provenance。

该 audit 找到一个真实而直接的差异。Accepted `aicbsp_8800d_fw_init` 在 firmware upload 和 `HOST_START_APP_AUTO` 两处都传 `0x00120000`；r1、r3、physically run r4 的 final ELF 均传 `0x00110000`。Donor source 用 `#ifdef CONFIG_AIC_INTF_SDIO` 选择前者，但 Makefile/最终 `.cmd` 只提供 `-DAICWF_SDIO_SUPPORT`，generated autoconf 也没有前一符号，故实际编译进入 `0x00110000` 分支。Exact accepted/current firmware 四文件仍 byte-identical；`fmacfw.bin` 的 MSP/reset vector 为 `0x00183800`/`0x00120189`，所以当前 build 把 image bytes 下移 64 KiB，却保留绝对 reset target。Revision/sub-ID 识别只选择 alias table/same files；SDIO setup、IRQ `0x04=0x07`、download helper、command/RX paths 相同；新增 reboot helper 仅 USB 可达；其余主要是 LTO/inlining/log/layout noise。Donor/build mismatch 因此 **RAISED / PLAUSIBLE ROOT-CAUSE CANDIDATE**，但未实机证明。

最早 source-proven divergence 已前移到 `aicwifi_init()` 的 FMAC upload destination。r5 one-line patch SHA-256 为 `10BE1AE58CB900DBD8B5250960B2FBA3846CC29DFFF676DAE5D87D17EBCADBD3`；final packaged BSP 为 129,976 bytes / `2BF0F46C69968408544D8F1B344C0999C6B2E69E03C7E24A5EB8D2A23133D03A`，upload/patch-read/START_APP 恢复 `0x00120000`/`0x00120180`/`0x00120000`。唯一镜像为 1,031,739,392 bytes / `A185B0A3C7516FBC9D34F61B3218171F07BDA00B84903A644D2D71FBB1DCC28F`，其 offline preservation checks 保持 PASS。

用户随后物理验证 r5：Linux `5.4.302+`、`sys.boot_completed=1`；system/HDMI/remote/Leanback/TV IME/Launcher/Wi-Fi/Wi-Fi ADB PASS。AIC BSP/BTLPM/FMAC/rfkill modules 正常加载，初始 probe/66 MHz/FMAC/supplicant startup 完整；过滤 `timeout|wifi start fail|reqcfm|1037|1038` 结果为空。物理 Wi-Fi OFF→ON 后旧 `wlan0`、SDIO、bus/thread 与 subsystem state 0 清理，再完成 state 1/probe/66 MHz/FMAC/supplicant fresh init；第二次同一过滤仍为空。单次 `aicsdio: write retry: 20` 后继续成功，按非致命 transient 记录，不重开 SDIO 调试。Android 完成 association、4-way/group handshake、DHCP、`192.168.1.8/24` / gateway `192.168.1.254`、validated L3；IP 与 DNS ping 均 4/4、0% loss，Wi-Fi ADB reconnect PASS。r1-r4 START_APP timeout 未复现。错误 `0x00110000` placement/build-guard contract 与 r5 `0x00120000` correction 因而接受为有强单变量实机佐证的 engineering root cause，不声称未证明的 firmware internals。Raw ADB captures 由用户外部收集且未在 VM 找到；tracked record 只保存 reviewed excerpts/result，不虚构 raw files 或 SHA。完整记录见 `docs/m8/device-tests/20260825-m8-kernel-5.4.302-r5/`。

### Android 16 QPR0 r7 source-only audit

Exact official `android-security-16.0.0_r7` identity 已由 tag objects 独立验证：manifest commit/tree `ebea28d151539ecf0730b1a4ab92ac33edc17ac9` / `e4641ccf8e59e0028248d32e5a7fd212760b7a22`，`default.xml` SHA-256 `455B978FFD07E7A1699364E6CCAC3F8B9FE455905712B4923C0B97414F97769D`，`BP2A.250805.034`、API 36.0、REL、SPL 2025-08-05。Clean r4 checkout 未 repoint；其 233,871-byte pinned manifest SHA-256 `4E8BEB5D1B590DFF3D631B1DBB957138DBDA4E608A3183C625683DA4BC84918F` 与 946,765,824-byte `system.img` / `FD349F...DBE` 已在审计前复核。为避免 `/work` 仅约 50.8 GiB free 下复制完整 AOSP/output，r7 使用现有 Repo object store 的 immutable official tag objects 进行 source-only audit；未 sync/change worktree、未 build target/kernel/candidate。

QPR0 `NetBpfLoad` fatal floor 是 5.4；netd exact non-GKI 5.4 floor 是 5.4.277，故 5.4.302 合法。r4 的 25Q4 5.10 fatal 在 r7 QPR0 不适用；r7 loader 还解析 installed rc 并强制 exact 2025 Q2/API 36.0，不是 bypass。Minimum config 精确为 tracked Path-A 六项：BLK_CGROUP/CPUSETS/PROC_PID_CPUSET 关闭已观测 init/cgroup contract，NET_CLS_MATCHALL/NET_ACT_POLICE/NET_ACT_BPF 满足 netd rate limiting。MEMCG optional；5.4 BPF variants 明确存在；BTF/ringbuf/link/batch/CAP split/kprobe/uprobe/ftrace/IncFS 均不应为 speculative 5.10 parity backport。

QPR0 cgroups/API31/vendor overlay 顺序无新增 controller；APEX 保持 bootstrap-before-data，`mount_before_data=false`，bootstrap set 仍为 i18n/runtime/tzdata/virt/VNDK31。Frozen VNDK31 仍含 ARM32 `libaudioroute.so`，linkerconfig 保持 vendor `default→vndk`。FCM6 matrix 与 r4 byte-identical，accepted display HAL 两项 delta 仍需要；full exact VINTF 仍 exit 65 solely for inherited `CONFIG_NFS_FS=y` 对 FCM6 `n`，不称 PASS。QPR0 platform `fuseblk /` genfscon 仍与 accepted vendor duplicate，minimum one-line deferral 保持；permissive historical boot 不证明 enforcing。TV GSI base 在 r4/r7 byte-identical；Prototype A 可 bounded port 到 `bp2a` 并保持 ARM32/no-secondary/`zygote32`/shipping API31/VNDK31。

2026-08-24 source-only decision 当时为 **GO FOR PROTOTYPE A r3 BUILD — FUTURE TASK ONLY**，并把 Gate 2 从 kernel/wireless blocked 转为 **UNBLOCKED / READY FOR QPR0 r3 BUILD**，不是 PASS。该历史 build-only 授权现已由下节唯一 r3 build/offline audit 履行，不把它扩张为 physical authorization。完整 exact commits/file hashes/contract 在 `docs/m8/research/android-16-qpr0-r7-source-audit.md`；Prototype B、`zygote64_32` 与 ARM64 Mali/mapper 工作继续 CLOSED。

### Android 16 QPR0 Prototype A r3 offline result

2026-08-25 将 source workspace 从 retained clean r4 reproducibly transition 到 exact
`android-security-16.0.0_r7`；manifest commit 为
`ebea28d151539ecf0730b1a4ab92ac33edc17ac9`，pinned manifest 为 246,298 bytes /
`F52BA4A04957CEC7EEE7C9DCDD1525533156A0B5A1F0ADFC31A8155F48FB087E`。产品只做
`bp4a→bp2a` release/lunch port、exact 两项 display matrix 与 one-line platform `fuseblk`
deferral；ARMv7-A NEON/no-secondary/`zygote32`/shipping API31/VNDK31/pKVM-off 合同保持。
Native `m -j8 systemimage` 完成 121,285/121,285 actions，exit 0；输出为
`BP2A.250805.034` / API36 / SPL 2025-08-05，source `system.img` 931,926,016 bytes /
`2963A982345C25F26F3128CC1A40E41B64FB6EBDEA412E89C1EAFE3C258750EC`。

Path-A kernel 从 retained integration commit `027ef79e...` clean build 为 `5.4.302+`；config
相对 preservation 只有 BLK_CGROUP/CPUSETS/PROC_PID_CPUSET 与
NET_CLS_MATCHALL/NET_ACT_POLICE/NET_ACT_BPF 六项 additions。Image 23,498,760 bytes /
`287A82F799982FB58D02ADE88150A9EAB22D4C0956BE3CE50765F6FD1DB24F40`，22-module
inventory/dependencies/vermagic/import CRC closure PASS。Final BSP 保持 r5 FMAC
`0x00120000`/`0x00120180`/`0x00120000`、70 MHz、firmware、generic MMC/SDIO 与 DT authority。

唯一 firmware `out/candidates/a16-prototype-a-r3/x12-a16-prototype-a-r3.img` 为
1,239,738,368 bytes / SHA-256
`FA47939654B4E2A7E14FE963C7819296157338D33355E75D89E8086356071F1B`。ext4/e2fsck、
system/boot/vendor_dlkm AVB、vbmeta_system rollback index/location、LP 10.2/three slots/sparse
roundtrip/A-B empty slots、outer IMAGEWTY、APEX、ARM32 ELF/name closure、VNDK31/linkerconfig、
split SELinux 和 kernel preservation audit close。Outer 50 entries 中只有 boot/super/
vbmeta_system 与三个 `V*` companions 改变，44 项保持；vendor/product、vendor_boot/ramdisk、
DT/DTBO、TEE、factory/security、top-level vbmeta、rollback/recovery 与其他 hardware payload
原字节保持。

System VINTF PASS；full exact VINTF 仍 exit 65 / **INCOMPATIBLE**，唯一原因是继承
`CONFIG_NFS_FS=y` 对 FCM-6 required `n`，没有新 incompatibility，绝不称 full PASS。35 个
actual r7 APEX 全部 parse/activate offline；ARM32 VNDK31 `libaudioroute.so` 与 generated
vendor `default→vndk` exposure PASS。1,816 ELF 中无 AArch64 platform userspace consumer；15
个 ELF64 为 BPF bytecode，22 个为 AArch64 kernel modules，AOSP ARM CTS shim 内一份 inactive
test-only arm64 JNI payload 不构成 secondary ABI。Exact result 与 changed/preserved inventory
见 `docs/m8/candidates/a16-prototype-a-r3.md` 和其 preservation JSON。
R3 focused 5/5、combined r3/kernel-preservation 22/22 与 full repository 101 tests PASS；25
个 skip 是预期缺少 ignored historical fixtures。Exact r7 source audit 与 `git diff --check`
也 PASS。

该离线阶段的历史决定为 **OFFLINE CHECKED / READY TO REQUEST PHYSICAL VALIDATION**。它本身
不授权 flash，也不证明 boot、zygote、system_server、SurfaceFlinger/HWC 或 enforcing runtime。
后续物理结果由下一节独立补充；Prototype B 继续 CLOSED。

### Android 16 QPR0 Prototype A r3 physical result

2026-08-25 的 local physical validation 未执行 flash、reboot、build 或 image mutation；通过
Ethernet ADB 对现场已运行的 r3 采证。完整脱敏证据位于
`docs/m8/device-tests/20260825-a16-prototype-a-r3-physical-validation/`。

`sys.boot_completed=1`，Android 16/API36/BP2A、ARM32-only ABI、`zygote32`、Linux 5.4.302+、
六项 Path-A config、APEX ready/mount、三个 service manager、system_server/SystemUI、TV/
Leanback launcher 与 LeanbackIME 均已运行时证明。旧 bootstrap/bpfloader fatal filter 为空。
原始 r3 的首个 physical blocker 是 EGL driver selection：没有 `persist.graphics.egl` 或
`ro.hardware.egl`，用户提供的 pre-validation 证据记录 SurfaceFlinger 无法从
`ro.board.platform=apollo` 选择驱动；在本次采证前用户已设置 runtime
`persist.graphics.egl=mali`，当前 SurfaceFlinger 报告 ARM Mali-G31 / GLES 3.2 并有 composition
layers。正式方向是保持 `ro.board.platform=apollo` 并加入 `ro.hardware.egl=mali`；该变化本次
**NOT IMPLEMENTED / NOT BUILT / NOT PHYSICALLY VALIDATED**。

Ethernet、gateway/IP/DNS 与 Ethernet ADB PASS。Wi-Fi BSP/framework、scan 与 OFF→ON clean
reinitialization PASS；因无 saved network 且无法输入凭据，association/DHCP/validated L3/DNS
为 **NOT TESTED**。物理 IR 全部按键均有 Linux DOWN/UP；OK 的 scanCode 352 在 Android 成为
`KEYCODE_UNKNOWN`，而 `Generic.kl` 只把 353 映射为 DPAD_CENTER，root cause PROVEN、fix
**NOT IMPLEMENTED**。音量/静音 framework effect PASS。

HDMI physical stability FAIL：monitor 周期性约 1 秒有画面、约 5 秒黑屏。45 秒 framework
monitor 中 SurfaceFlinger/system_server 保持，42 秒 extcon 始终 `HDMI=1`，20 秒 display
sampling 始终 unblank/error 0、3840x2160 YUV444 mode 34，interrupt 持续增长；kernel history
另有 HDMI disconnect/connect transitions。黑屏精确根因尚未证明，不得把 framework counters
稳定扩张为 physical PASS。

ALSA/Apollo/AudioFlinger 可枚举 `ahubhdmi`/`AUDIO_HDMI`，但 legacy HIDL audio HAL 在 observed
HDMI status transition 的 `getAudioPort` path 重复发生 null-pointer SIGSEGV；automatic service
recovery PASS，HAL stability FAIL。隔离窗口中的普通 AudioFlinger/AudioPolicy dumps 没有单独
增加 crash。当前连接的 monitor 没有音频输出，因此 basic/HDMI audible output 均为 **NOT
TESTED**；`tinyplay` 完成不等同实际听音。

物理结论为 **CORE PATH-A ARCHITECTURE VIABILITY PHYSICALLY PROVEN / FORMAL CANDIDATE
CLOSURE PENDING**。依赖 runtime EGL override 的证明不能关闭 Gate 2；enforcing SELinux、
Wi-Fi association、稳定 HDMI 与稳定 vendor audio HAL 均未闭合。Prototype B 继续 CLOSED。

### Android 16 QPR0 Prototype A r4 offline result

2026-08-26 以 r3 为直接 baseline 构建唯一严格 bounded `a16-prototype-a-r4`。Exact source
仍为 `android-security-16.0.0_r7` / manifest
`ebea28d151539ecf0730b1a4ab92ac33edc17ac9` / BP2A.250805.034；产品仍为 ARMv7-A NEON、
无 secondary ABI、`zygote32`、shipping API31、VNDK31、pKVM off。唯一功能 delta 为：

1. source product 加入 `ro.hardware.egl=mali`，accepted vendor 的
   `ro.board.platform=apollo` 与 Mali/apollo graphics blobs 保持，正式 image 不写入
   `persist.graphics.egl`；
2. 新增 device-specific `sunxi-ir.kl`，与 exact r7 `Generic.kl` 仅 scanCode 352 一行不同，
   映射为 `DPAD_CENTER` / Android keyCode 23，其他按键映射不变。

`OUT_DIR=out-ceiling BUILD_NUMBER=UBOX10_A16_QPR0_R4 m -j8 systemimage` exit 0、43/43
actions。最终 firmware
`out/candidates/a16-prototype-a-r4/x12-a16-prototype-a-r4.img` 为 1,239,746,560 bytes /
`E125DD8FFB9F5B4A7B2B9B86DD8377367409AB00D1B29BE1E719CE25768E2111`；candidate
`system_a.img` 为 1,651,167,232 bytes /
`F6437E0F7EDBAACF10B316A4DFCFEF916570766F9B0AAA4E72421C10C10D9001`。

ext4/e2fsck、system AVB/hashtree、vbmeta_system rollback、LP geometry/slots/sparse roundtrip、
IMAGEWTY、35 APEX、ARM32 ELF/name closure、VNDK31/linkerconfig、split SELinux 与 Path-A
kernel/module preservation 均 PASS。Full VINTF 仍严格为 exit 65 / INCOMPATIBLE，唯一例外是
继承的 `CONFIG_NFS_FS=y` 对 FCM-6 required `n`，没有新增 incompatibility。Outer 50 项只有
`super.fex`、`vbmeta_system.fex` 和两个 `V*` companion 改变，其余 46 项保持。Boot、
5.4.302+ Image、22 modules、vendor_dlkm、vendor/product、DT/DTBO、vendor_boot、TEE、DRM、
factory/security、top-level vbmeta、rollback/recovery 与 unrelated payload 为 r3 exact。

r3→r4 system tree 无删除，只新增 `sunxi-ir.kl`；三份 build.prop 只含 r4 generated identity
变化（system build.prop 另含 EGL property），NOTICE 只新增 keylayout 许可关联，没有第三项功能
delta。完整记录与机器可读 preservation inventory 见
`docs/m8/candidates/a16-prototype-a-r4.md` 和
`docs/m8/candidates/a16-prototype-a-r4-preservation.json`。

该 build/offline 阶段未 flash、reboot、UART/ADB 操作或其他实机动作；在该历史时点 EGL 与
Remote OK 只是 offline assertion，HDMI/audio/Wi-Fi association 仍 open。后续物理证据和
formal Gate 2 decision 由下一节追加，不改变这里记录的实现范围。

### Android 16 QPR0 Prototype A r4 physical result and Gate 2 closure

2026-08-26 用户已 flash 并测试 exact r4。原始 ADB/log captures 未出现在本 VM；tracked record
严格区分外部 **USER PHYSICAL CONFIRMATION** 与仓库内 build/offline evidence，不伪造 raw file
或 hash。完整结果矩阵见
`docs/m8/device-tests/20260826-a16-prototype-a-r4-physical-validation/`。

Fresh boot 无 UART、manual bootarg、runtime `setprop` 或 r3
`persist.graphics.egl` workaround：Android 16/API36、incremental
`UBOX10_A16_QPR0_R4`、Linux 5.4.302+、`zygote32`、core framework services 和
`sys.boot_completed=1` PASS。Runtime `persist.graphics.egl` 为空、
`ro.hardware.egl=mali`、`ro.board.platform=apollo`，Mali-G31/SurfaceFlinger/UI 物理 PASS；
r4 source-level EGL integration 正式证明。

InputManager 识别 `/dev/input/event0` `sunxi-ir` 并选择
`/system/usr/keylayout/sunxi-ir.kl`；installed `key 352 DPAD_CENTER` 与 runtime
scanCode 352→`DPAD_CENTER(23)` PASS，Linux KEY_OK DOWN/UP 保持。物理
UP/DOWN/LEFT/RIGHT/OK/BACK/HOME 及正常遥控操作 PASS，Remote OK fix **PHYSICALLY PROVEN**。

HDMI 为 **PASS / STABLE IN THIS VALIDATION**；r3 约 1 秒画面/约 5 秒黑屏循环
**NOT REPRODUCED**。r4 未修改 display implementation，因此旧 transient root cause 仍
**NOT PROVEN**，不得描述为“r4 修复 HDMI 根因”。Wi-Fi modules/`wlan0`/scan/association、
WPA `COMPLETED`、DHCP/IPv4/DNS、Android `INTERNET`/`VALIDATED`/`TRUSTED` 与实际稳定使用均
PASS。OFF→ON script 因测试 transport 本身为 Wi-Fi ADB 而断联，分类为 **NOT COMPLETED IN
THIS SESSION / NOT FAIL**；separate kernel-r5 evidence 已独立证明一次 same-lineage OFF→ON
reinitialization。Ethernet 本轮无 carrier，**NOT RETESTED**；r4 byte preservation 与 prior
physical PASS 保持 reference。

真实 48 kHz/16-bit/stereo WAV 经 ALSA card 3 `ahubhdmi`/`tinyplay` 在 HDMI TV 物理听到，
direct hardware path PASS。ARM32 VLC 播放有效 H.264/AAC-style MP4，picture normal、HDMI TV
audible audio、AudioFlinger session/writes/frames PASS；`audioserver` PID 1230 和 audio service
PID 1232 在 playback 前后相同。播放前清 logcat 后的 clean interval crash buffer 为空，无新
Fatal signal/SIGSEGV，steady-state Android application media playback PASS。

但 boot 期 `/vendor/bin/hw/android.hardware.audio.service` 已再次出现 fault address 0 的
SIGSEGV，stack 位于 `android.hardware.audio@7.0-impl.so`
`Device::getAudioPortImpl<audio_port_v7>` / `Device::getAudioPort` /
`PrimaryDevice::getAudioPort`；service 自动恢复，后续 playback impact 未观察到。Exact
source-level root cause 仍 **NOT PROVEN**；null callback/function pointer 为 **HIGH CONFIDENCE /
LIKELY**，不得把 steady-state PASS 改写为 boot defect 已修复。

既有 r3/r4 acceptance contract 明确要求 no-runtime EGL、stable physical HDMI、physical
Remote OK、Wi-Fi association、real audio sink playback 和 **vendor audio HAL startup stability**。
按该旧合同，boot-time SIGSEGV 合理地产生了 HOLD；该历史判断保留。用户随后明确改变项目治理
定义：Architecture Gate 2 评估 architecture/functional viability，而不是 zero-defect release
maturity。R4 已证明 direct audible HDMI 与真实 Android app audio/video，service auto-recovers、
没有 restart loop，playback PIDs 稳定且 clean interval 无新 crash；保留 ARM32 audio process 也不
阻塞 mixed-framework experiment。因此正式决定为：

**GATE 2 CLOSED / PASS — CORE PATH-A ARCHITECTURE VIABILITY PHYSICALLY PROVEN.**

Boot-time `getAudioPort` SIGSEGV 改列 **KNOWN / UNFIXED / AUTO-RECOVERED / POST-GATE P1
STABILIZATION DEFECT**，不得称 fixed。出现 user-visible failure、restart loop、B regression、
HDMI hotplug/suspend-resume failure 或 release target 时再提升。Enforcing SELinux 属 release
hardening；full VINTF 仍 exit 65 solely for inherited `CONFIG_NFS_FS=y` 对 FCM-6 `n`，不得称
PASS。Exact r4 现已 **FROZEN AS THE ACCEPTED ANDROID 16 ARM32 ARCHITECTURE BASELINE**；Android
12 `m8b-remote-r1` 继续 frozen fallback。

### Prototype B0 pre-build readiness decision

B0 在 exact r7 source、r4 logical images/vendor properties、official BPI donor commit、ELF、
linker/VINTF 与 AVB/outer metadata 上完成 read-only preflight；未 build、未改 source/image、未
创建 candidate。完整 source of truth 为
`docs/m8/research/prototype-b-b0-readiness.md`。

Exact B1 boot-critical AArch64 same-process set 为：

1. hash-pinned `/vendor/lib64/egl/libGLES_mali.so`，18,145,112 bytes /
   `03333D495E3566C7D85CA2E000DA569A16CE8F022EA25C0EA61950C891D5C7F8`；paired ARM32 file
   与 accepted UBOX byte-identical，297 strong imports 对 r7 ARM64 VNDK31/LLNDK unmatched 0；
2. exact r7 AOSP `/vendor/lib64/hw/android.hardware.graphics.mapper@2.0-impl-2.1.so`；
3. pinned Apache-2.0 donor gralloc-1.x source生成的 `/vendor/lib64/hw/gralloc.apollo.so`。

Accepted mapper 的 exact symbol/import contract 证明它是 AOSP passthrough adapter，并通过
`hw_get_module()` 同进程加载 `gralloc.apollo`；不能用 donor alternative 2.x mapper 偷换该架构。
Donor gralloc defaults to 1.x on modern SDK and `LOCAL_MULTILIB := both`；fixed-width/padded
native-handle design 无已知 cross-bitness contradiction，但 exact accepted handle compatibility 仍为
B1 offline/physical gate。Adjacent H618 只提供 HIGH lineage / MEDIUM exact-H616 confidence；Mali
redistribution rights **UNPROVEN**，B1 必须从 outside-Git local path 做 exact-hash fail-closed intake。

Exact r7 mixed product 为 ARM64 primary + ARM32 secondary / `zygote64_32`；primary
`app_process64` 启动 system_server，secondary `app_process32` 保持 32-bit apps。Accepted vendor
later-loads `ro.zygote=zygote32`、32-bit-only ABI 与 `ro.bionic.arch=arm`，所以 system-only 替换
不成立；B1 vendor delta 仅限 mixed ABI/zygote/bionic property fragment 与三个 lib64 provider。
Existing mapper manifest 已声明 passthrough `arch="32+64"`，无需 semantic change；r7 `sphal`
已搜索 `/vendor/${LIB}/{egl,hw}` 并链接 LLNDK/VNDK-SP。

Partition delta 已闭合：`system_a`、`vendor_a`、`super.fex`、`vbmeta_system.fex`、
`vbmeta_vendor.fex` 及 `Vsuper`/`Vvbmeta_system`/`Vvbmeta_vendor` 必须变化；`product_a`、
`vendor_dlkm_a`、boot/kernel/ramdisk、vendor_boot、top-level vbmeta、DT/DTBO、TEE、bootloader、
factory/security/recovery 与所有无关 payload 必须 exact。Top-level vbmeta 无 chain descriptor，
vendor 有自己的 hashtree + signed vbmeta，故该分类不是猜测。

B1 只允许 r4 + mixed ABI/`zygote64_32` + 三个 AArch64 graphics files + 最小 property/linker/
AVB consequences；必须保持 5.4.302 六项 Path-A config、22 modules、AIC FMAC/firmware、
Wi-Fi/Ethernet/audio、ARM32 HWC/allocator/OMX/Cedar/TEE/DRM、remote、HDMI/display 和 exact r4
rollback。Vulkan、GMS、5.10、25Q4、full vendor rewrite 与 product polish 禁止混入。

Historical B0 **PROTOTYPE B1 BUILD READINESS GO** 已正确触发这一次 bounded implementation；
它没有预证明实际 filesystem fit。B1 现已把该 unknown 转化为 exact
**VENDOR_A PARTITION FIT BLOCKER**。Mali、mapper/gralloc 与 handle ABI gates 通过，不存在新的
mandatory provider class；但在项目明确批准一种精确 storage contract 前，不得继续打包或请求
physical validation。

## Accepted audio milestone

`m8b-audio-r2` 状态为 **DEVICE ACCEPTED / AUDIO PASS**；r1 已实机证明确切 VNDK APEX 存在但 Treble linker namespace 未启用，r2 已在设备上闭合该合同。

| 项目 | 值 |
|---|---|
| 镜像 | `out/candidates/m8b-audio-r2/x12-m8b-audio-r2.img` |
| 大小 / SHA-256 | 1025951744 bytes / `B39300CB3E335D75C9D61594CD94565D9C24FC92F467F9050CD1E604D87E9C2C` |
| 直接基线 | `m8b-audio-r1` / `298DCA11DBDFDC81028869C01866411C634FC2C7B979EDA3FB0346BF7434DBDD` |
| 唯一变量 | Android 12 产品级 Treble/VNDK 合同；候选中仅 `/system/build.prop` 的 `ro.treble.enabled=false → true` |
| runtime 合同 | stock vendor `ro.vndk.version=31` + exact `com.android.vndk.v31`；生成 `[vendor]`、VNDK namespace 和 `default→vndk` 的 `libaudioroute.so` |
| payload 差异 | `system_a`、`super.fex`、`Vsuper.fex`、`vbmeta_system.fex`、`Vvbmeta_system.fex` |
| 保持项 | boot/kernel/ramdisk、vendor_boot、vendor/product/vendor_dlkm、遥控、Projectivy、Power 均不变 |

实机同时确认 `sys.boot_completed=1`。legacy missing mixer controls、`nano_input_open -3`/input path 与 permissive SELinux AVC 未阻塞 primary HDMI playback；证据保留，Android 12 清理/调查现已随 M8B freeze 延期。

## 2026-08-16 M8B system-quality audit

以在线 `m8b-audio-r2` 做限定、只读 ADB 审计，未清 log、重启、停止进程、修改设置/属性或改变设备。结论为 **无 P0；accepted baseline 不变**。两次快照间 core Android/media/graphics/Wi-Fi PID 保持，保留日志与 62 秒窗口均无 crash、ANR、watchdog、fatal signal、binder/service-manager failure 或 service/process restart；内存、zram、LMKD、primary audio 与 graphics HAL/service 均健康。

审计当时的分类：P1 为 permissive SELinux 的 CEC/suspend/audio active-path policy gaps、Projectivy/HWUI 无效 frame-completion 时间戳导致 99.74% jank telemetry，以及 medium-confidence 的 CPU 长驻 1.512 GHz / ThermalService `HAL Ready=false` policy-observability 问题；均未证明当前普通播放不稳定。P2 为每约 3 秒一次的 Wi-Fi link-layer statistics failure、Projectivy Billing unbind warning 与 boot-only legacy mixer noise。`nano_input_open -3` 在保留的 23153 行及 62 秒窗口均为 0 次，故仅保留 input function 未验证，不把它声明为当前 loop 或已证明 defect。这些 Android 12 P1/P2 项现均 deferred，不再是 active backlog；完整证据见 `docs/m8/device-tests/20260816-m8b-system-quality-audit/`。

## r5 device acceptance

| 功能 | 结果 |
|---|---|
| Projectivy / basic UI | **PASS**；可用 TV UI 与一般导航正常 |
| Native rc-core remote | **PASS**；DPAD、OK、BACK、HOME、Volume、Power、Settings→MENU 全部通过；`multi_ir` 保持 disabled |
| Wi-Fi / network ADB | **PASS**；SSID、关联、Internet、Android DNS/connectivity 与 `192.168.1.9:7896` ADB 正常 |
| Ethernet | **PASS**；eth0、Internet、ADB 正常 |
| Bluetooth / HID | **PASS**；service、扫描、配对、iPhone bonding、gamepad UI 控制正常 |
| USB host / storage | **PASS**；EHCI、枚举、Mass Storage/SCSI、block/partition、vold public volume 正常；exFAT 单独不支持 |
| H.264 / HEVC | **PASS**；VLC 使用 Allwinner OMX AVC/HEVC decoder，Cedar/VPU 硬解流畅 |
| Audio | **FAIL — HIGH**；AudioFlinger 无 primary output，带 AAC 的 HEVC 停在 0:00；无音频同视频正常 |

Android 12 未完成项包括 Settings/Menu 语义分离、exFAT、graphics artifacts、完整 post-resume recovery、HDMI CEC、CPU/thermal soak、LeanbackIME cold-start latency、SELinux enforcement-readiness、commercial DRM playback 与 legacy cleanup；全部 **DEFERRED pending Android 16 architecture outcome**，不再作为当前 M8B 执行优先级。VP9 runtime 已关闭；DRM 仍只证明可操作 Widevine L3、HDCP `NONE`、无 secure decoder 要求，不声称商业服务认证或播放。

## Audio failure boundary

- **CONFIRMED first fatal**：clean restart 日志显示 `vndksupport` 无法从 default namespace 加载 unchanged `/vendor/lib/hw/audio.primary.apollo.so`，直接原因是其 `DT_NEEDED libaudioroute.so` 不可解析。随后才出现 DevicesFactory `-19`、AudioFlinger 无 primary、AudioPolicy 无 primary output；HAL 尚未进入 `adev_open`。
- stock 与 r5 Apollo HAL 均为 `6679E7C653D184EC34070F259104CA0FC394CB4DC67DE4BA60134A13B0093791`，排除 HAL 被替换。r5 的 system/vendor/product/APEX 无 `libaudioroute.so`。
- Test8r2 `/system/apex/com.android.vndk.current/lib/libaudioroute.so` 为 ARM32，SHA-256 `BB5393CE70CD1A4AD9ED62814339CA3695788532242708B0D46DAED87D603623`；manifest runtime name 为 `com.android.vndk.v31`，`vndkcore.libraries.31.txt` 包含 `libaudioroute.so`，Test8 linkerconfig 将它由 default namespace 链接到 VNDK namespace。
- 遗漏发生在 AOSP 输出阶段：`/home/tianyi/ubox10-aosp/device/ubox/ubox10/BoardConfig.mk` 没有 `BOARD_VNDK_VERSION := current`，`ubox10.mk` 也未纳入 `com.android.vndk.current`，AOSP `out/.../system/apex` 已无 VNDK APEX；`scripts/build-m8a-candidate.py` 只复制 system 并合并 system_ext，没有裁剪该 APEX。
- r5 vendor 共 228 个唯一 `DT_NEEDED`；其中 55 个属于 Test8 VNDK 合同，r5 已有 54 个，唯一物理缺项为 `libaudioroute.so`。修复仍恢复完整 145-entry exact VNDK APEX，避免继续依赖 no-config fallback 或把单库任意放进 `/vendor/lib`。
- r1 离线确认 Apollo HAL 与 `libaudioroute.so` 的全部传递依赖可解析；exact VNDK 子树逐项一致、SELinux metadata 保持，LP/AVB/e2fsck/SELinux/ELF/外层校验通过。
- r1 实机确认 `com.android.vndk.v31` active 且 `/apex/com.android.vndk.v31/lib/libaudioroute.so` 存在，但 Apollo HAL 仍报该库不可见。运行时 `/linkerconfig/ld.config.txt` 没有 VNDK namespace 或 `default→vndk` link；`ro.treble.enabled=false`、`ro.vndk.version=31`。因此 r1 的 payload 恢复有效，缺失的是产品级 Treble/VNDK 合同。
- AOSP 根因已确认：原输出的 `DeviceVndkVersion`、`ProductVndkVersion` 为空，`Treble_linker_namespaces=false`、`Enforce_vintf_manifest=false`。源码产品缺少 `PRODUCT_SHIPPING_API_LEVEL := 31` 与 `BOARD_VNDK_VERSION := current`。
- r2 源码修复加入上述两个产品合同值，并确保 `com.android.vndk.current` 纳入产品。重建后 `DeviceVndkVersion=current`、`ProductVndkVersion=current`、`Treble_linker_namespaces=true`、`Enforce_vintf_manifest=true`、`Platform_vndk_version=31`、`ro.treble.enabled=true`；`systemimage/productimage/systemextimage/check-vintf-all` 和 SELinux 构建通过。
- r2 以 r1 为直接基线，仅把已验证生成属性 `ro.treble.enabled` 改为 `true`；r1 的 exact VNDK APEX、`system/etc/linker.config.pb`、vendor、boot/kernel 和全部已验收内容原字节不变。匹配 SP1A.210812.015 的 host linkerconfig 对 r2 system/vendor/product 输入离线生成 `[vendor]` 与 VNDK namespace，搜索 `/apex/com.android.vndk.v31/${LIB}`，且 `namespace.default.link.vndk.shared_libs` 包含 `libaudioroute.so`。未修补生成的 `ld.config.txt`，未向 `/vendor/lib` 复制库。
- `audio_mixer_paths.xml` controls、`audio_platform_info.xml` 的 `sndhdmi`/`audiocodec:4/5` 与 ALSA topology 仅保留为 HAL 成功加载后的第二层假设，本候选未修改。

## Verified progress

| Stage | Result | First useful finding | Next correction |
|---|---|---|---|
| Test8r2 | **ROLLBACK VERIFIED** | Stable ARM32 Android 12 baseline | Retained as preferred rollback |
| AOSP ATV product | **OFFLINE CHECKED** | ARM32 TV system/product/system_ext built from locked Android 12 sources | Assemble with stock hardware stack |
| r1 | **FAILED - `/metadata` mount** | First-stage init could not mount an ext4 metadata partition | Add preformatted metadata payload and download-map entry |
| r2 | **FAILED - flash map CRC** | PhoenixCard rejected the modified `dlinfo.fex` | Recompute dlinfo CRC |
| r3 | **FAILED - `/oem` mount** | Product flash passed; erased `media_data` left required VFAT `/oem` unavailable | Add preformatted media_data payload and descriptor |
| r4 | **FAILED - first-stage reboot** | Both filesystems mounted; PID 1 still rebooted to bootloader at about 1.106 s | Test whether the rebuilt AVB root caused the reboot |
| r5 | **FAILED - first-stage reboot, no HDMI** | Keyless top-level AVB bypass made no material difference; reboot occurred at about 1.113 s | Restore the first remaining concrete LP metadata difference |
| r6 | **FAILED - first-stage reboot** | Stock A/B interleaved LP partition-table order made no material timing change; reboot at 1.096406 s | Restore missing system-root `/metadata` switch-root target |
| r7 | **FAILED - first-stage reboot** | `/metadata` system-root target made no difference; reboot remained about 312 ms after `Kernel init done` | Expose first-stage fatal message on UART |
| r8 | **FAILED - confirmed non-canonical `/vendor`** | `realpath(/vendor) -> /system/vendor` causes required early mount failure, `LOG(FATAL)`, SIGABRT and `InitFatalReboot` | Reverse the vendor link topology to match Test8r2 |
| r9 | **FAILED - framework bootstrap stall** | 已越过 first-stage、SELinux、second-stage、zygote、SurfaceFlinger、bootanimation 并 fork system_server；Lights HAL 缺库令 system_server 主线程阻塞，framework Watchdog 杀死 PID 412 | 恢复 exact Test8r2 ARM32 vendor AIDL `ndk_platform` 兼容库 |
| r10 | **BOOT COMPLETE - NO REAL HOME** | Lights HAL 注册，system_server/zygote 稳定，`package_native`、`sys.boot_completed=1`、SystemUI 和 BOOT_COMPLETED 均完成；HOME 仅解析到 TvSettings FallbackHome | 加入一个真实 Android TV HOME Launcher |
| r11 | **BOOT COMPLETE - HOME OK, REMOTE RAW ONLY** | Projectivy 正常；RemoteIR_RX IRQ、NEC 和 `sunxi-ir/event0` 的 `MSC_SCAN` 正常，但无 `EV_KEY` | 恢复 Test8r2 已验证的 `multi_ir → uinput` 用户态链 |
| r12 | **REMOTE PATH DEVICE VERIFIED - SUPERSEDED BY r13** | exact Test8r2 `multi_ir → uinput` 恢复 ff40 遥控；后续 UI policy 由 r13 完成 | 保留为历史对照 |
| r13 | **GOLDEN BASELINE - DEVICE ACCEPTED** | boot、Projectivy、provisioning、遥控与 Power sleep/wake/shutdown 全部通过 | 作为 M8B 和回滚基线 |
| M8B rc-core-r1 | **FAILED - REPEAT/REPRESS LIFECYCLE** | 实机确认 native rc-core 架构成立，但单次 OK 可拆成两组 DOWN→UP，长按 UP 约每 108 ms 人工 UP→DOWN | 修正 config-off 路径的 new-event 判定 |
| M8B rc-core-r2 | **REPEAT LIFECYCLE PASS - KEYLAYOUT SELECTION FAIL** | native repeat/release、DPAD、HOME/BACK/Power 和物理 KEY_OK 已通过；Android 因设备标识不匹配而加载 `Generic.kl` | 安装 exact vendor/product/version keylayout |
| M8B rc-core-r3 | **FAILED - EXACT FILE FOUND, PARSE REJECTED** | exact keylayout 路径、权限、SELinux 与 SHA 均正确，但 Android 12 parser 在 line 13 拒绝 legacy `WAKE_DROPPED`，EventHub 回退 `Generic.kl` | 完整转换全部不受支持的 label/flag |
| M8B rc-core-r4 | **DEVICE ACCEPTED - SETTINGS SEMANTIC FAIL** | native rc-core/repeat、exact `.kl` 加载、OK/DPAD/HOME/BACK/Power 均通过；物理 Settings 产生 KEY_CONFIG 171→Android SETTINGS 176，但该 keyevent 在当前系统无效果 | 仅把 Linux 171 映射为已验证有效的 Android MENU 82 |
| M8B rc-core-r5 | **DEVICE ACCEPTED - AUDIO OPEN** | native rc-core/repeat、exact `.kl`、Settings→MENU 与全部基础遥控通过；Projectivy、网络、Bluetooth/HID、USB、AVC/HEVC 已验收 | 捕获 Apollo HAL `adev_open` 的首次返回分支，不做 XML card-name 猜测 |
| M8B audio-r1 | **FAILED - VNDK NAMESPACE DISABLED** | exact VNDK 31 APEX active、`libaudioroute.so` 存在，但 `ro.treble.enabled=false` 令 linkerconfig 使用 legacy 配置；无 VNDK namespace / `default→vndk` link | 启用正确 Android 12 产品级 Treble/VNDK 合同 |
| M8B audio-r2 | **DEVICE ACCEPTED - AUDIO PASS** | 运行时 Treble/VNDK 合同、Apollo/AudioFlinger/ALSA HDMI、VLC HEVC+AAC HDMI 音频通过；后续 ADB-only 验证 VP9 Allwinner/Cedar 硬解与 Widevine 16.1.0 L3 | 保持 accepted baseline；物理画面、商业 DRM 服务、CEC、resume 与 Settings/Menu 复验延期 |
| M8B ime-r1 | **DEVICE ACCEPTED - IME PASS** | fresh-data 自动 enable/default LeanbackIME；物理 DPAD/OK/BACK、文字输入与 1920×1080 TV 观感通过 | 作为 Remote v2 直接验收基线；单独 reboot persistence 未执行并接受为非阻塞 |
| M8B remote-r1 | **FROZEN / DEVICE-ACCEPTED ANDROID 12 BASELINE** | Projectivy/基础回归、CONNECT 默认授权、6466/6467、RRO lookup、official Google TV iPhone discovery/pair/navigation/volume 与真实 EditText phone text PASS；继承 AUDIO/IME PASS | 作为 Android 16 架构工作的日用回退和功能对照；不再继续 M8B feature/P1/P2 development |

## M8B native rc-core

r1 实机日志为 `logs/device/20260813-m8b-rc-core-r1/uart-coldboot.log` 和 `logs/device/20260813-m8b-rc-core-r1/input-debug.log`。设备已确认 `sys.boot_completed=1`、`multi_ir` 不运行、`sunxi-ir/event0` 直接输出 `EV_KEY`，且独立 UP/OK 均能产生 DOWN→UP，因此 native rc-core 架构已经设备证明。r1 失败点仅为 repeat/release 生命周期：单次 OK 可出现 DOWN→UP→DOWN→UP；长按 UP 约每 108 ms 出现人工 UP→DOWN。

锁定源码 commit `9ab7a758149d3c9b721878a0c18b3f9c5d6c93e6` 的 `drivers/media/rc/rc-main.c` 中，`ir_do_keydown()` 的 `new_event` 无条件包含 `!key_repeat`，而 `key_repeat` 只在 `CONFIG_SUNXI_MULTI_IR_SUPPORT` 分支赋值。r1 关闭该 config 后 `key_repeat` 恒为 false，故每个 NEC repeat frame 都被误判为新按键。r2 仅用条件编译把 `!key_repeat ||` 限定回该兼容分支，不改 decoder、release timeout、DTS、wake、framework、Power、rc-map 或 keylayout。

r2 候选为 `out/candidates/m8b-rc-core-r2/x12-m8b-rc-core-r2.img`，1007978496 bytes，SHA-256 `AE53376C3F902C8B239321E196F7886BFEFEC74C43E66B6FAB50EC100A64F3C8`；kernel SHA-256 `FE23BEEAE10389EA13575CA266AF45797F22BCF9BDBA7037AF6F7A8B3148C5E2`。`r2-verify.log` 已实机确认 DPAD 单击/长按、HOME/BACK/Power 和 clean KEY_OK DOWN→UP，r1 的人工 repeat/repress 周期消失，`multi_ir` 保持 disabled，因此 kernel/native rc-core 修复通过。`r2-kl.log` 显示现有 `/system/usr/keylayout/sunxi-ir.kl` 含 352→DPAD_CENTER、171→SETTINGS，但 input identifier 为 vendor/product/version `0001/0001/0100`，实际加载 `/system/usr/keylayout/Generic.kl`；剩余根因是 Android keylayout 文件名选择，不是 kernel 或 UI focus。

r3 以 r2 镜像为直接基线，只新增 `/system/usr/keylayout/Vendor_0001_Product_0001_Version_0100.kl`；内容与 `sunxi-ir.kl` 同为 1848 bytes、SHA-256 `14FFF2ADF2B5F258AD77483FC5821F699EFAE008FAB28B0493A733AB7EFBC3AD`，元数据为 regular `0644 root:root`、`u:object_r:system_file:s0`。`logs/device/20260815-m8b-rc-core-r3/r3-verify.log` 与 `r3-verify2.log` 已确认 Android 找到该 exact 文件，但 parser 在 line 13 报 `Expected key flag label, got 'WAKE_DROPPED'`，随后回退 `Generic.kl`；因此 r3 状态为 FAILED，路径选择假设已关闭。

r4 只转换 device-specific keylayout，保留 `sunxi-ir.kl` 原字节作参考。对 exact SP1A.210812.015 `InputEventLabels.cpp` 与 `KeyLayoutMap.cpp` 的完整表审计发现不支持 flag `WAKE_DROPPED` 和 labels `APPS`、`BROWSER`、`EXPAND`；分别转换为 `WAKE`、`ALL_APPS`、`EXPLORER`、`TV_ZOOM_MODE`。最终 46 条映射全部落在 parser 支持集合内，无省略；352→DPAD_CENTER、103/108/105/106→DPAD、172→HOME、158→BACK、115/114→Volume、116→POWER、171→SETTINGS 均保持。device keylayout 为 1795 bytes、SHA-256 `C8AB0907D9F7CFCDC9B14370548643DF9BCC03E488C5086D48BC424425A5E398`，元数据继续为 regular `0644 root:root`、`u:object_r:system_file:s0`。boot/kernel 原字节不变，Settings framework 与 legacy 清理继续延后。

r4 现已设备验收：native rc-core/repeat、exact device `.kl` 选择、物理 OK、DPAD、HOME、BACK 与 Power 全部通过。唯一剩余语义问题是物理 Settings 仍输出 Linux `KEY_CONFIG` 171，r4 将其映射为 Android `SETTINGS` 176，而现场 `input keyevent 176` 无效果；`input keyevent 82`（MENU）可打开 Projectivy settings menu，83 为 notifications 且不采用。r5 因此仅把 exact device `.kl` 的 171 从 `SETTINGS WAKE` 改为 `MENU WAKE`，不改 ff4044→KEY_CONFIG、rc-map、kernel、framework、Power 或 Projectivy。

primary evidence 仍使用 `logs/device/20260811-r11/uart-putty_3.log`、`uart-putty_8r2.log`、`uart-putty_8r2_2.log`、`uart-putty_8r2_3.log`，没有重复设备取证。r11 和 Test8r2 的物理 `sunxi-ir/event0` 均只发 `MSC_SCAN`；Test8r2 的 `multi_ir` 读取 event0、打开 `/dev/uinput` 并创建 `sunxi-ir-uinput/event1`，Android 才从 event1 获得 `EV_KEY`。

匹配 Linux 5.4.125 源码是 Orange Pi `orange-pi-5.4-sun50iw9` commit `9ab7a758149d3c9b721878a0c18b3f9c5d6c93e6`。`sunxi-ir-dev.c` 已注册 rc-core raw receiver 和 `RC_MAP_SUNXI`，`ir-nec-decoder.c` 已完成 NEC 解码；缺口不是 decoder，而是占位 rc-map 和 `CONFIG_SUNXI_MULTI_IR_SUPPORT=y`。该兼容分支把 press/release 分别编码成 `01ff40xx`/`00ff40xx` 的 `MSC_SCAN`，绕开普通 `rc_keydown`/`rc_repeat` 路径，直接解释 event0 没有 `EV_KEY`。

rc-core-r1 关闭该 config 分支，并从 exact `customer_ir_ff40.kl` 生成 48 项 native map 和 device-specific `sunxi-ir.kl`。49 项语义全部审计；ff4054 `MOUSE` 不进入 map/keylayout，Mouse mode 明确放弃。`multi_ir.rc` 加入 `disabled`，同时保留 `multi_ir`、rc、`libmultiirservice.so`、`customer_ir_ff40.kl`、`sunxi-ir-uinput.kl` 和 r12 `libinput.so` 作 inert rollback/reference。完整审计见 `docs/m8/candidates/m8b-rc-core-r1.md`。

候选镜像为 `out/candidates/m8b-rc-core-r1/x12-m8b-rc-core-r1.img`，1007978496 bytes，SHA-256 `E3F40ECFB2FE867EB6C04988E0C3207C49E1B1073AF42A2B41FFF3A7C3DBBCE0`。kernel 为 `D5AEED79EF04D3DF838385AD857AC81268C4CACDA986545016F5CEE7E45FE289`，`system_a` 为 `DC7B9EF4814E04F8EB4671E609D2ACD22CD7CB6218B5443B7D74E28793D0A9C5`，`super` 为 `3093AF2DC57BA45C15F0D01F6F7BB6C08A67FAEB75EFF81672D787F67BCCCA0D`，`vbmeta_system` 为 `F68247A300DB60E3512BCAF1B2240B43DF92004996D67CDB9FCC2E4AB73B1BFA`。

相对 r13，system 文件差异仅为 `/system/etc/init/multi_ir.rc` 和 `/system/usr/keylayout/sunxi-ir.kl`；boot 仅更换 kernel，ramdisk 未变。`vendor_a`、`product_a`、`vendor_dlkm_a`、vendor_boot、DT/DTBO、持久 bootargs、顶层 vbmeta、Projectivy、provisioning、Power RRO 和 r10 兼容库均保持。kernel build、LP、AVB、四分区 e2fsck、split SELinux compile、ELF/DT_NEEDED、外层校验、3 项 M8B focused tests 与 6 项 r12/r13 回归测试通过。设备侧仍需验证 native repeat/release 和 r13 Power wake 对等性。

## r13 TV provisioning 与 Power policy

主证据为 `logs/device/20260812-r12/20260812-r12-09-home-keypath-uart.log`、`20260812-r12-11-power-reboot-policy-uart.log`、`20260813-r12-12-home-postreboot-uart.log` 和 `20260813-r12-13-tv-setup-home-uart.log`。r12 的 IR/uinput/HOME 事件与 Projectivy resolver 均正常；WindowManager 拒绝 HOME 的直接原因是 `Not going home because user setup is in progress`。`device_provisioned=1` 和 `user_setup_complete=1` 重启后仍不足，补上 `secure tv_user_setup_complete=1` 后无需重启即可进入 Projectivy。因此 HOME/provisioning 根因确认为缺少 TV 专用 setup flag，不是遥控、Launcher 或 HOME resolver。

r13 从锁定的 Test8r2 镜像恢复 `/system_ext/priv-app/AwTvProvision/AwTvProvision.apk`（SHA-256 `D74DF03C4BBAB8ADCFC543D9F34D98C87178A63D15F66785B1EE3D286EDB68D8`）和 `/system_ext/etc/permissions/provision-permissions.xml`（SHA-256 `98C3C29A10F4956BBAB65F74E405E7B3F8DF20C262A22FF7FCC755C0F92F7E6A`）。该 direct-boot-aware、优先级 1 的 HOME/DEFAULT/SETUP_WIZARD 组件在首次 HOME 时写入 `device_provisioned=1`、`user_setup_complete=1`、`tv_user_setup_complete=1`，随后禁用自身，使 Projectivy 继续作为真实 HOME。当前 `ubox10.mk` 虽列出 `AwTvProvision`，但本地源码树没有对应 `vendor/aw` 模块，r12 构建输出也没有 APK；因此采用锁定 Test8r2 工件作为可复现输入，不恢复完整 SetupWizard，也不使用启动 shell hack。

Power 输入链已确认到达 `PhoneWindowManager`。r12 的 `framework-res.apk` 默认 `config_shortPressOnPowerBehavior=1`，但 `/vendor/overlay/framework-res__auto_generated_rro_vendor.apk` 是优先级 0 的静态 RRO，并把该值覆盖为 0；现有 product TV RRO 优先级为 -1，且只设置长按值 3。Android 12 当前实现初始化时读取资源，不读取已试验的 `power_button_short_press` Global setting，所以该 runtime setting 重启后仍不能改变行为。r13 新增平台签名的 `/system_ext/overlay/M8TvPowerPolicyOverlay.apk`（SHA-256 `B695200E1153F750B3BF1CD92228EE6E360BA7B12608CB56019D316017481C91`），优先级 1，仅定义短按值 1；解析结果为 `SHORT_PRESS_POWER_GO_TO_SLEEP`。它不定义长按资源，现有值 3 和 `LONG_PRESS_POWER_SHUT_OFF_NO_CONFIRM` 保持不变。

r13 解包差异仅为 `AwTvProvision` 目录/APK、allowlist、`system_ext/overlay` 目录和 Power RRO，无意外 system 文件差异。Projectivy、`multi_ir`、`multi_ir.rc`、三个 ff40/sunxi keylayout、`libmultiirservice.so`、r12 `libinput.so`、r10 两个兼容库、canonical `/vendor`、现有 SELinux/ueventd 合同均按 SHA-256/元数据保持不变。`vendor_a`、`product_a`、`vendor_dlkm_a` 与 r12 原字节一致；LP、AVB、四分区 e2fsck、split SELinux compile、ELF/DT_NEEDED、IMAGEWTY 外层校验和 focused tests 均通过。r13 已实机验收并冻结为 GOLDEN；M8B rc-core 已转为 active work，Mouse mode intentionally dropped。

r13 `system_a` 为 `28118A3316F1845A174667B527125C0FA750A719EFA0CF94FB88DC197FAE2055`，`super.img` 为 `FFAC0283599D9FE44383642843EA5A4645E09C140FD53CCB769196EA05A57200`，`vbmeta_system.fex` 为 `2A2AAA0F67BA2729834FC26B735AC8B5E0445EE88623C1758FCD99C62FB609BB`。

## r11 遥控根因与 r12 修复

主证据为 `logs/device/20260811-r11/uart-putty_3.log`、`uart-putty_8r2.log`、`uart-putty_8r2_2.log` 和 `uart-putty_8r2_3.log`。r11 与 Test8r2 的物理 `sunxi-ir/event0` 均只输出 `MSC_SCAN`；Test8r2 另由 root 进程 `/system/bin/multi_ir` 读取 event0 并打开 `/dev/uinput`，创建可输出 `EV_KEY`/`EV_REL` 的 `sunxi-ir-uinput/event1`，Android 对 event1 加载 `sunxi-ir-uinput.kl`。因此 r11 根因不是 kernel rc-map 失效，而是 system composition 没有恢复 Test8r2 的 Allwinner `multi_ir → uinput` 用户态链。

ff40 映射的 exact 来源是 Test8r2 `/system/usr/keylayout/customer_ir_ff40.kl`（SHA-256 `DB54F9843081DDC492F9BDD35E7EE341EBCB4562991513CB5B7A26BBBC74DE39`）。已知现场键对应为 11/14/16/17/13/66/26/21/28 → UP/DOWN/LEFT/RIGHT/CENTER/BACK/HOME/VOL+/VOL-；Power 为 77（raw `ff404d`），mouse-toggle 为 84（raw `ff4054`，标签 `MOUSE`）。完整 49 项 active scancode 映射已写入 r12 候选记录和 `remote-source.json`。

r12 恢复 7 个 Test8r2 exact system 工件：`multi_ir`、`multi_ir.rc`、`customer_ir_ff40.kl`、`sunxi-ir.kl`、`sunxi-ir-uinput.kl`、`libmultiirservice.so` 以及 Test8r2 `libinput.so`。前六项组成当前遥控的 runtime 与三层映射；`libinput.so` 是唯一替换项，用于恢复 r11 parser 缺少的 Allwinner `MOUSE`等 input label，避免整套旧 framework 回退。`libmultiir_jni.so` 无 DT_NEEDED 边且 Test8r2 运行进程未映射；`virtual-remote.kl` 不被当前物理或虚拟设备选中；`customer_ir_4040.kl` 不属于 ff40，故均未恢复。

mouse-toggle 状态、DPAD 到 pointer 的转换、重复定时与指针移动均由 exact `/system/bin/multi_ir` 实现；其创建的 uinput 设备输出 `EV_REL REL_X/REL_Y` 和 `EV_KEY`。r11 已保留与 Test8r2 同字节的 vendor policy、file_contexts 和 ueventd 合同：`multi_ir`/`multi_ir_exec`、`uhid_device`、`input_device`、Binder/service_manager 权限俱在，`/dev/uinput` 为 `0660 uhid:uhid`；无需改 SELinux 或 ueventd。

r12 `system_a` 为 `7ECF3B7891F012D296BC8C0A44684011E1FD83796F33AB01371A9700B89DBDDB`，`super` 为 `D08A974C5E9AD646E1B38512A4AA80041D37C37ED043F16509BE1E786639B540`，`vbmeta_system` 为 `28D42D0874B5749272C42EC4B42DA9EACE56BC518A314F9952EF06944DD7F924`。相对 r11，仅 `system_a`、`super.fex`、`Vsuper.fex`、`vbmeta_system.fex`、`Vvbmeta_system.fex` 变化；Projectivy、r10 两个兼容库、`vendor_a`、`product_a`、`vendor_dlkm_a` 与其他外层 payload 原字节不变。

## r10 boot complete 与 r11 HOME 修复

完整现场证据为 `logs/device/20260811-r10-first-boot/r10-first-boot-putty_2.log`。采集时 `sys.boot_completed=1`、`init.svc.bootanim=stopped`，system_server PID 415、zygote PID 244、SystemUI PID 781 均稳定；Lights HAL、`package_native`、SystemUI 和 BOOT_COMPLETED 已完成，r9 framework blocker 已解决。

当前 resumed HOME 是 `com.android.tv.settings/.system.FallbackHome`（PID 970，`mResumed=true`、`mActivityType=home`）。HOME query 只返回该 FallbackHome；Leanback query 只有 TvSettings 的 `.MainSettings`，显式启动 `MAIN+LEANBACK_LAUNCHER` 返回 unable to resolve。FallbackHome 每约 500 ms 输出 `User unlocked but no home; let's hope someone enables one soon?`，手动 HOME 仍回到 FallbackHome。因此白底“安博科技”画面属于 ImageWallpaper + FallbackHome，confirmed 根因是产品中没有真实 Launcher，不是 bootanimation 或 framework stall。

源码 composition 的遗漏点是 `/home/tianyi/ubox10-aosp/device/ubox/ubox10/ubox10.mk`：它只显式加入 `AwTvProvision`，所继承的 `atv_product.mk` 只加入 TV overlay；把 `TvSampleLeanbackLauncher` 加入 `PRODUCT_PACKAGES` 的 `aosp_tv_arm.mk` 未被继承。源码候选中，`TvSampleLeanbackLauncher` 和 Launcher3 都缺少 `LEANBACK_LAUNCHER`，Live TV 只有 Leanback 入口而不是 HOME，均不满足本项目 TV HOME 合同。

Test8r2 的构建记录把 Projectivy 4.71 安装到 `/system/app/ProjectivyLauncher/ProjectivyLauncher.apk`，并把默认 HOME 属性设为 `com.spocky.projengmenu/com.spocky.projengmenu.ui.home.MainActivity`；APK SHA-256 为 `6818FC2DB44411A605CA4D7067FB9D7227AAEF2414CFF42DE58FE13E9321B47A`。其同一 exported activity 同时声明 MAIN、HOME、DEFAULT 和 LEANBACK_LAUNCHER，要求 leanback、支持 ARM32，无 required shared library；它是项目已有的现代、遥控器友好桌面，因此 r11 复用 exact APK，不恢复旧厂商 `SimpleLauncher.ap`。

r11 仅新增 `/system/app/ProjectivyLauncher` 和其中 APK。`system_a` 为 `7E3BA3A79583CA29E50BAD7FC5DF1543E7B931FB53E4F88F6FFFB90AA2D9CB69`，`super` 为 `A81947E01D5300B417A6748393758494C3106E809B81478B3FD19793524952CC`，`vbmeta_system` 为 `E73DF3D2EA4A955934DFF5272B4D24FA568597E3E7A8DE240EE47C34A0CCB594`。相对 r10，仅 `system_a`、`super.fex`、`Vsuper.fex`、`vbmeta_system.fex`、`Vvbmeta_system.fex` 变化；r10 两个 compatibility library、canonical `/vendor` topology 和全部无关 logical/outer payload 保持原字节。

`device_provisioned=0`、`user_setup_complete=0` 且没有 Setup package 是已记录的后续产品决策，不是当前 HOME 缺失根因。r11 不修改这两个值；先确认真实 Launcher 能在现状下进入桌面，再单独选择 SetupWizard 或个人 TV Box 默认 provisioned 策略。

## r9 framework stall 与 r10

最新证据为 `logs/device/20260807-001357-r9-framework-stall/uart-putty.log`。安静启动仅使用 `console=ttyAS0,115200 loglevel=1`，未加入此前 fatal-panic 诊断参数，故障仍完整复现。r9 已越过 early mounts、SELinux、second-stage init、zygote、SurfaceFlinger、bootanimation，并启动 system_server。

`/vendor/bin/hw/android.hardware.lights-service` 反复因缺少 `android.hardware.light-V1-ndk_platform.so` 无法链接。system_server PID 412 随后停在 `ServiceManager.waitForDeclaredService` → `LightsService$VintfHalCache.get` → `LightsService.<init>` → `SystemServer.startBootstrapServices`；00:01:50.991 framework Watchdog 明确输出 `WATCHDOG KILLING SYSTEM PROCESS`，00:01:50.993 输出 `GOODBYE`。zygote PID 239 于 00:01:51.112 记录 system_server PID 412 因 signal 9 退出并自行退出，init 再启动 zygote；采集时新 system_server 为 PID 1028。直接 kill 来源已确认为 framework Watchdog，先前 llkd 假设已证伪；llkd PID 328 当时仍在运行且不在 kill 链中。

`aidl/package_native` 持续未注册发生在 system_server 尚未越过 LightsService/bootstrap 阶段时，是 PackageManager 尚未继续初始化的下游结果，不是本轮首因。rebootescrow HAL 同时缺少 `android.hardware.rebootescrow-V1-ndk_platform.so`，但它不是已证明的主阻塞点。

r9、Test8r2 与原厂 `vendor_a` 均为 `BB91A8B7ED4AC0145F434F89FD76865EB4311F234AA46D67C8373A7CD5B4929A`；Lights HAL 和 rebootescrow HAL 二进制逐字节一致。两个缺失库仅存在于 Test8r2/原厂 `system_a` 的 `/system/apex/com.android.vndk.current/lib/`，均为 ARM32、0:0、0644、`system_lib_file`。r9 AOSP 产品配置未设置 `BOARD_VNDK_VERSION`，产品包清单也没有两个接口库；仓库原组合链把该 system 与 stock vendor 合并时没有导入 Test8r2 的 vendor AIDL compatibility payload，因此 r9 中两个文件物理不存在。

匹配 Android 12 host linkerconfig 对 r9 实际 system/vendor/product 输入的离线生成结果不含 `dir.vendor`：r9 同时缺少 `com.android.vndk.v31` APEX，故 `/vendor/bin` 的 linker 配置匹配失败并进入 bionic no-config fallback，ARM32 搜索顺序为 `/system/lib`、`/odm/lib`、`/vendor/lib`。r10 因此不导入整套 VNDK APEX、不修改 linkerconfig 或 vendor，而以单一规则恢复 exact Test8r2 ARM32 vendor AIDL `ndk_platform` 双库到 `/system/lib`。两库来自同一 Test8r2 system 分区、同一版本和同一遗漏链，rebootescrow 因而与 lights 一并纳入；`libaudioroute.so` 等无关缺项未改。

r10 新增文件：

- `/system/lib/android.hardware.light-V1-ndk_platform.so`：`57ED3A999D158EE449D6621897275610B0479B0F06B7EFB1005AF397099BF663`
- `/system/lib/android.hardware.rebootescrow-V1-ndk_platform.so`：`F26AA210060D449AA2D0ED8B7341DB28BA072A6F1DD4AF31BB2005E427636AB0`

r10 `system_a` 为 `99130EDE6615F1C72743D74BDBE7F7FC08B92AA002D146EEB3469600F87E419F`，`super` 为 `E0AB7D19635A559DC505EEAF0FBFD7CACB441950CB6E94EAFBB3990351B3D90A`，`vbmeta_system` 为 `6D65C50C26BD7E6F0BB8CC92D37D146A49AF398386D3DDB1813A0765F5B7611D`。相对 r9，仅 `system_a`、`super.fex`、`Vsuper.fex`、`vbmeta_system.fex`、`Vvbmeta_system.fex` 变化；`vendor_a`、`product_a`、`vendor_dlkm_a`、boot、vendor_boot、顶层 vbmeta 和其余 46 个外层 payload 原字节不变。

## r4-r8 limited startup-chain review

### Log mapping

| Version | Evidence |
|---|---|
| r4 boot | `logs/device/20260801-222006` |
| r5 boot | `logs/device/20260801-224818` |
| r6 boot | `logs/device/20260801-232812` |
| r7 flash / boot | `logs/device/20260804-233745` / `logs/device/20260804-235259` |
| r8 boot | `logs/device/20260805-220923` |
| r8 volatile U-Boot diagnostic | `logs/device/20260805-233154-r8-uboot-diagnostic` |
| r8 volatile fatal-panic diagnostic | `logs/device/20260806-212631-r8-fatal-panic` |
| r8 volatile `/dev/kmsg` diagnostic | `logs/device/20260806-221823-r8-devkmsg-on` |
| Test8r2 normal boot | `logs/device/20260805-223511` |

r7 flash completed with `CARD OK` and `sprite success`; its boot evidence is the separate `20260804-235259` capture.

### Aligned events and first confirmed divergence

| Event | Test8r2 | r4-r8 |
|---|---|---|
| Runtime kernel command line | UART does not print a final command-line line | UART does not print a final command-line line; r8's exact added string is absent |
| Kernel and first-stage source | Stock kernel and stock boot-ramdisk init | Same stock kernel and boot-ramdisk init; stock vendor_boot ramdisk and `fstab.sun50iw9p1` retained |
| `Kernel init done` | 0.800555 s | r4 0.801224; r5 0.812560; r6 0.796053; r7 0.784518; r8 0.796057 s |
| First-stage mount / dynamic partition evidence | Reports invalid `/metadata` ext4 at 0.904080 s, invalid media_data VFAT at 0.942298 s, then `Could not update logical partition` at 1.142640 s and continues | No explicit success/failure marker for dm or `/metadata`, `/oem`, `/system`, `/vendor`, or `/product`; absence is not treated as success |
| switch-root / `selinux_setup` / second stage | No explicit transition marker in the window; later console and Android services prove the normal boot continued | No explicit transition marker before reboot; none of these stages is claimed as reached |
| Termination | No reboot; init continues | Orderly `reboot: Restarting system with command 'bootloader'` at r4 1.105528, r5 1.112778, r6 1.096406, r7 1.096870, r8 1.108413 s |

The first confirmed runtime divergence is therefore the failure action itself: r8 requests an orderly bootloader reboot while Test8r2 continues through later init work. The exact internal step before that request is not observable. Metadata and media_data return differences occur earlier in the normal log, but are intentional filesystem-input differences and do not identify the repeated r4-r8 failure.

The newer volatile U-Boot capture supersedes the original r8 capture for the current boundary. Its runtime kernel command line contains `console=ttyAS0,115200 loglevel=8 ignore_loglevel`; first-stage starts at 3.375881 s, switches to `/first_stage_ramdisk` at 3.400748 s, completes `/metadata` check and mount, mounts `dm-0` at 3.582748 s, requests bootloader restart at 3.605221 s, and reboots at 3.802562 s. LP metadata order plus slot `_a` and the stock fstab identify `dm-0` as `system_a` mounted at `/system`.

The latest fatal-panic capture is now authoritative for the termination path. Its runtime command line contains `console=ttyAS0,115200 loglevel=8 ignore_loglevel androidboot.init_fatal_panic=true`; first-stage starts at 3.400620 s, switches to `/first_stage_ramdisk` at 3.425459 s, completes the `/metadata` check and mount, mounts `system_a` as `dm-0` at 3.656223 s, triggers SysRq `c` at 3.679616 s, and panics at 3.684228 s. PID 1 is `init`; the system reboots after the configured five-second panic timeout. The panic stack is only the kernel SysRq write path, not the initiating userspace stack. The following boot lacks the volatile diagnostic arguments and is not a separate failure.

`20260806-221823-r8-devkmsg-on` 取代上述日志成为根因证据。运行时参数完整包含 `console=ttyAS0,115200 loglevel=8 ignore_loglevel printk.devkmsg=on androidboot.init_fatal_panic=true`。`vendor_a`、`product_a`、`vendor_dlkm_a` 分别创建为 `dm-1`、`dm-2`、`dm-3`；`system_a` 于 3.777677 s 挂载到 `/system`，3.788731 s 执行 `Switching root to '/system'`。随后 3.798753 s 报告 `realpath(/vendor) -> /system/vendor`，3.809241 s 的 `/vendor` 挂载失败，3.815898 s required early partitions 失败，3.824048 s 捕获 signal 6，3.843190 s 触发 crash。根因为 **confirmed**。

### Handoff findings

- The boot-header diagnostic path remains ineffective, but the verified volatile `setargs_mmc` route produces the intended runtime parameters and is now the authoritative r8 diagnostic evidence.
- The first-stage executable is the unchanged stock boot-ramdisk `/system/bin/init` (`SHA-256 2A7D6E125583C79E925B5D916C54C51E4AE8EE145F2D7422B2DD77D0B6C62751`); the stock vendor_boot fstab is also unchanged.
- Matching Android 12 control flow is: mount `/metadata`, create logical devices, mount `system_a` at `/system`, call `SwitchRoot("/system")`, then mount vendor/vendor_dlkm/product and finally exec the new `/system/bin/init selinux_setup`. 最新日志已确认第二次 switch-root 被调用；首个失败分支是随后对 `/vendor` 的 canonical 检查。
- At that switch, the top-level mount targets are `/system/dev`, `/system/proc`, `/system/sys`, `/system/mnt`, `/system/debug_ramdisk`, `/system/second_stage_resources`, and `/system/metadata`. Every target is an actual directory in both r8 and Test8r2 with matching mode, uid, gid, link count, and no symlink; only inode numbers differ. A missing or wrong-type switch-root target is not supported.
- Test8r2 and r8 first differ deterministically at the mounted system handoff: Test8r2 `/system/bin/init` is 1624080 bytes (`382507769EBB4ED0B6853DE73719301716082634F6BF04FF45AD3DB51ED7DF5D`), while r8 is 1622456 bytes (`272FB078122961ADEE30414CE24699A2F2E1A42EE201B1EDE202C6E91E47BC95`). r8 init is a valid executable ARM32 ELF using `/system/bin/bootstrap/linker`; the interpreter and checked key libraries are present. The UART does not prove that switch-root executed this binary.
- The exact r8 system/system_ext plus stock vendor 31.0 CIL inputs compile successfully with the locked Android 12 host `secilc`. A general ELF/interpreter failure and a deterministic split-policy compile incompatibility are not supported.
- The first-stage fatal path is **confirmed**: `/vendor` canonical 检查失败后 required early mounts 返回失败，触发 `LOG(FATAL)`、SIGABRT（signal 6）和 exact init 的 `InitFatalReboot`；watchdog、外部复位和 U-Boot 主动复位均已排除。
- The missing handler output is explained by the first-stage logging path. Android 12 `KernelLogger` keeps one opened `/dev/kmsg` FD; the exact kernel defaults each such FD to ten userspace messages per five seconds. The capture contains exactly ten `init:` records on that FD before silence, and the command line has no `printk.devkmsg` override. The original fatal text, `InitFatalReboot: signal`, unwind frames, and `Trigger crash` are subsequent writes and are rate-limited. Moving `/dev` does not invalidate the open FD; the direct `/proc/sysrq-trigger` write bypasses `/dev/kmsg`. Signal-handler logging and unwinding are also not async-signal-safe, but that is now a secondary fallback explanation rather than the first missing-output mechanism.
- The exact kernel accepts `printk.devkmsg=on`, which disables this userspace `/dev/kmsg` rate limit for one boot. `print-fatal-signals=1` is not equivalent because init installs handlers for the relevant fatal signals, so the kernel's default fatal-signal reporting path is not guaranteed to run.
- The exact stock init supports `androidboot.first_stage_console=1`: the debug product build enables `ALLOW_FIRST_STAGE_CONSOLE`, includes the matching first-stage console implementation, and creates `/dev/console` as major 5 minor 1. The exact boot has `console=ttyAS0,115200`, and the kernel confirms `console [ttyAS0] enabled`. The ramdisk has an executable ARM32 dynamic `/system/bin/sh`, its linker and `libc.so`, and root retains `CAP_SYS_PTRACE` before SELinux policy load; `CONFIG_SECURITY_YAMA` is off.
- The stock ramdisk has no `/first_stage.sh`, `strace`, `gdbserver`, `simpleperf`, `perf`, `debuggerd`, `crash_dump`, or ptrace-capable toybox applet. `toybox`, `toolbox`, `sh`, `setsid`, and `nohup` are present, but the relevant executables are dynamic ARM32 binaries and cannot provide the required signal metadata or syscall ring by themselves.
- LP ordering, top-level AVB flag, missing `/metadata` root directory, HDMI DDC, GPT fallback, invalid init architecture/interpreter, and deterministic CIL compile incompatibility are not current root-cause candidates.

r9 条件已满足。Test8r2 的实际结构为 `/vendor` 实体目录和 `/system/vendor -> /vendor`；r8 的方向相反。AOSP device `BoardConfig.mk` 未声明独立 vendor image，触发 `system/core/rootdir/Android.mk` 的 `/vendor -> /system/vendor` 分支，仓库原 system builder 又保留了该布局。r9 在仓库构建链中加入可复现的 topology 修复；r8d1 保持停放且未构建。

r9 的 `system_a` 为 `64FC2C65894C7EF36781DEDD87E1722A258F06E3361749A3AE274E24C955D851`，`super` 为 `F69E1201B432D9EFD6937B251B9CBE7AE215A0CF738A5D711605CABD6DA28FA4`，`vbmeta_system` 为 `5AA1E40EB8198BE0E6C350FAFED9E95A9F3B9AA93CA637314D0A303CE3C0FFCA`。r8 的 `vendor_a`、`product_a`、`vendor_dlkm_a` 哈希在 r9 中逐字节不变；stock fstab 和 exact first-stage init 所在的 `vendor_boot.fex`、`boot.fex` 也保持原字节。

Raw UART logs and candidate images are intentionally local under ignored `logs/` and `out/` paths. Git retains the concise findings, builders, configs, hashes, and focused validators; it does not pretend a clean clone contains the large artifacts.

## Boundaries

- No physical action was performed during the 2026-08-02 repository cleanup.
- r10 已在实机完成 framework boot；r9 Lights/Watchdog/llkd 方向保持关闭，不再修改。
- r13 是当前 GOLDEN BASELINE；Projectivy、provisioning、遥控和 Power sleep/wake/shutdown 均以实机 UART 为准。
- M8B native rc-core 遥控迁移已在 r5 设备验收并关闭；Mouse mode intentionally dropped，legacy multi_ir 工件保留为 inert reference，其 Android 12 清理已随 freeze 延期。
- 当前 board、DT 与 runtime 证据识别为 H616。历史 A16 ARM32 r2 稳定失败于 r4/25Q4 NetBpfLoad 的 5.10 门槛；历史 kernel r1-r4 AIC failure 已收敛到错误 `0x00110000` FMAC contract。r5 恢复 working BSP `0x00120000` 后物理 boot/HDMI/remote/Wi-Fi/ADB 与 Wi-Fi OFF→ON reinitialization PASS，preservation checkpoint **CLOSED / PASS**。Exact QPR0 r7 audit 与 r4 physical pass 已关闭 Architecture Gate 2；r4 frozen。Boot-time legacy audio HAL SIGSEGV 保持 post-Gate P1，不称 fixed。Prototype B0 complete；同一 B1 已通过 intake/provider/handle gates，现为 **OFFLINE HOLD / VENDOR_A PARTITION FIT BLOCKER**，无 candidate。
- `m8b-audio-r2` 只启用产品级 Treble/VNDK 合同；未修改 VNDK payload、mixer、audio platform XML、DTS、machine driver 或已验收功能，现已设备验收为 AUDIO PASS。
- 2026-08-16 ADB-only 补验未刷机、未重启且未修改 ROM/device properties：VP9 为 Allwinner OMX/Cedar hardware-runtime PASS；Widevine 为可操作 L3，HDCP `NONE`，无 secure decoder 要求。物理画面/逐帧质量与商业服务认证或播放仍未证明。
- 遥控器 Menu 与 Settings 当前均打开 Projectivy menu。两键语义分离为独立延期项，不回改已验收的 rc-core、keylayout 选择或其他按键行为。
- 当前用户在设备现场，后续可按具体里程碑进行物理交互、重启、suspend/resume、HDMI 观察与恢复；不再以 remote-only/remote-safe 作为一般规划前提。任何新候选刷写仍需该候选的明确授权。

## Next action

保持 frozen Android 12 `m8b-remote-r1`、frozen Android 16 ARM32 `a16-prototype-a-r4`、Test8r2/
stock rollback、A16 r1-r3 与 kernel r1-r5 artifacts 不变。Canonical B1 ID 保持
`a16-prototype-b-r1`，不得改名或创建 r2。下一步按顺序是：

1. 仅做一次项目治理/设计决定：是否明确允许调整 r4 LP extent，为 `vendor_a` 提供至少
   135,270,400-byte ext4 加 AVB/FEC headroom；或提出经 linker/SP-HAL/AVB 证明的等价 provider
   placement。不得把本轮临时 measurement resize 误写为已授权 geometry。
2. 若授权 LP 方案，先在不改变 3,212,836,864-byte `sb_a` group 上限的前提下精确计算
   system/vendor/product/vendor_dlkm extents、alignment、剩余 group bytes 与 top-level AVB 影响，
   并更新 B0 expected-exact partition contract；若无法形成 bounded plan，则同一 r1 继续 HOLD。
3. 只有 storage contract 闭合后才恢复同一个 r1 的 system build、vendor AVB/super/outer assembly
   和完整 ELF/linker/VINTF/preservation audit；不得复用未完成 system output 冒充 candidate。
4. Vulkan、GMS、5.10、25Q4、full vendor rewrite、Audio fix、SELinux/NFS/HDMI polish 与产品 feature
   均不得混入 B1；Mali 继续 outside-Git exact-hash intake。
