# M8 device test and rollback

## 当前状态

- 最后一次刷入镜像：`out/candidates/a16-prototype-a-r1/x12-a16-prototype-a-r1.img`
- 当前设备状态：**BOOT LOOP / GATE 2 CLOSED**；白色 UBOX logo → 黑屏 → reboot，不能作为日用或 accepted baseline。
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

运行时边界：

| 阶段 | 结果 |
|---|---|
| kernel / accepted first-stage init / LP mapping | **PROVEN** |
| system mount；vendor/system_ext SELinux inputs 可读 | **PROVEN** |
| split SELinux compile/load；A16 second-stage init | **PROVEN**；cmdline 为 permissive，不证明 enforcing |
| bootstrap apexd | **FAILED AT THIS BOUNDARY**；init 调用后失败退出，内部错误未被 UART 保存，未证明任何 bootstrap APEX activation |
| servicemanager / zygote32 / system_server | **NOT REACHED / NOT PROVEN** |
| SurfaceFlinger / HWC | **NOT REACHED / NOT PROVEN** |

`Could not update logical partition` 和 early secilc `/linkerconfig/ld.config.txt` 消息均为继续执行的非 fatal early-boot 行为；`blkio` 表示 exact kernel 缺少 `CONFIG_BLK_CGROUP`，是独立风险但尚无 apexd 因果证据；missing `misc` 仅发生在已经选择失败重启之后。不得把这些消息当作已证明根因。

当前不允许再次刷写，不允许启动 Prototype B。若以后单独授权下一次诊断，只捕获一个周期，首选保持 r1 全部 payload 不变并追加 `printk.devkmsg=on`，以解除 exact kernel 对 apexd/init `/dev/kmsg` 输出的限流；没有实际内部错误前不构建 r2。

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
