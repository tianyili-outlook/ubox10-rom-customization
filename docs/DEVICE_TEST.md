# M8 device test and rollback

## 当前状态

- 最后一次刷入镜像：`out/candidates/a16-prototype-a-r2/x12-a16-prototype-a-r2.img`
- 当前设备状态：**BOOT LOOP / GATE 2 CLOSED**；r2 的 cgroup fix 生效，但 exact r4/25Q4 system 在 bpfloader 以 `Android 25Q4 requires kernel 5.10` 失败并 `bpfloader-failed` 重启，不能作为日用或 accepted baseline。
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

它只把 retained kernel config 的 `CONFIG_BLK_CGROUP`、`CONFIG_CPUSETS` 及 Kconfig 自动产生的 `CONFIG_PROC_PID_CPUSET` 改为 `y`，并只替换 outer `boot.fex`/`Vboot.fex`。r1 system/APEX/LP/vendor、vendor_boot/ramdisk、AVB 元数据和其余 48/50 outer payload 原字节保持。Boot AVB、IMAGEWTY、ext4、cgroup contract、SHA256SUMS PASS；full VINTF 没有新增错误，仍只保留继承的 NFS config 例外。Gate 2 继续 **CLOSED**。

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

r2 物理授权已经消耗。当前不得再次刷写，不构建 r3，不启动 Prototype B。后续只允许先完成早期 A16 QPR0 与 retained-kernel LTS 路线的离线架构 checkpoint；任何新候选仍需重新离线审核和单独物理授权。

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
