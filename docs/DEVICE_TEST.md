# M8 device test and rollback

## 当前状态

- 当前运行并验收的设备基线：`out/candidates/m8b-ime-r1/x12-m8b-ime-r1.img`
- 状态：**DEVICE ACCEPTED / IME PASS**（继承 **AUDIO PASS**）
- 大小 / SHA-256：1028208640 bytes / `B89612D5004BA3D8214F21E22E4BED7BFBA5B2F8FE441F9364315F851F1FE240`
- 现场验收已可用；但任何新候选的刷写仍需单独明确授权。

Wi-Fi ADB：

```powershell
C:\platform-tools\adb.exe -s 192.168.1.8:7896 shell <read-only-command>
```

当前 accepted baseline 的远程只读检查入口：

```powershell
C:\platform-tools\adb.exe -s 192.168.1.8:7896 shell getprop sys.boot_completed
C:\platform-tools\adb.exe -s 192.168.1.8:7896 shell dumpsys media.player
C:\platform-tools\adb.exe -s 192.168.1.8:7896 shell dumpsys media.audio_flinger
C:\platform-tools\adb.exe -s 192.168.1.8:7896 shell dumpsys media.audio_policy
C:\platform-tools\adb.exe -s 192.168.1.8:7896 logcat -d -b all
```

accepted baseline 已确认 Treble/VNDK、primary HAL/output、HEVC+AAC HDMI 音频、VP9 Allwinner/Cedar hardware runtime、Widevine 16.1.0 L3，以及 LeanbackIME fresh-data 自动 enable/default 和物理遥控文字输入。当前用户可在现场操作设备；刷入任何新候选仍须先获得该候选的单独明确授权。

## Pending physical test: m8b-remote-r1

候选状态 **READY TO FLASH**，尚未刷入：

- path：`out/candidates/m8b-remote-r1/x12-m8b-remote-r1.img`
- size：1031723008 bytes
- SHA-256：`F3B09E5565AC4ED4E5EE326D392622E7B036A8519B8444B966E77CC4751B814A`
- direct rollback：当前 accepted `m8b-ime-r1`

以下流程只有在用户对该候选另行明确授权后执行。首次启动不得先手工 `pm grant`，否则会掩盖 CONNECT default-permission gate。

1. 刷机/首启后观察 Projectivy，先用物理遥控验证 DPAD/OK/BACK/HOME/Volume/Power 基础回归。
2. 验证 Wi-Fi、Internet/network ADB 与 Bluetooth service/UI；不改现有网络配置，除非现场恢复需要。
3. 打开真实 EditText，验证 local LeanbackIME 仍自动 enable/default，物理 DPAD/OK 输入和 BACK dismissal 正常。
4. 检查 `pm path com.google.android.tv.remote.service`、`pm path com.ubox10.overlay.tvremote`、`cmd overlay list`，并要求 `cmd overlay lookup android android:string/config_tvRemoteServicePackage` 精确返回 `com.google.android.tv.remote.service`。
5. 用 `dumpsys package com.google.android.tv.remote.service` 确认 `BLUETOOTH_CONNECT granted=true`；SCAN/ADVERTISE 不应被本候选 default grant。检查主进程、`AtvRemoteProviderService`、`RemoteService`、`DiscoveryService` 与 crash/restart 状态。
6. 用 `ss -lntup` 确认 TCP 6466/6467 监听；保留 `logcat -d -b all` 的 Remote Service/TvRemoteProvider/NSD 决定性摘录，不清 log。
7. 确认 `_androidtvremote2._tcp` mDNS advertisement；若端口已监听但手机不可发现，先分离为 multicast/AP isolation 路径，不扩大 ROM scope。
8. 在同一 WLAN 使用 official Google TV iPhone app 验证设备 discovery 与配对码/TLS pairing。
9. 验证 phone DPAD/OK navigation，以及客户端支持的 BACK/HOME。
10. 在真实 EditText 验证 phone keyboard text entry，并从 Android UI/readback 确认文字实际写入。
11. phone text 完成后再次验证 local LeanbackIME，证明两个输入路径共存。
12. 现场执行一次 reboot，复验自动启动、6466/6467、mDNS、手机发现、既有 pairing persistence 与两种文字输入。
13. accepted baseline inventory 无 Play Store/GMS app；先确认 `pm path com.android.vending` 仍为空且没有 GMS package 被加入。若现场设备实际存在 Play，则物理启动并记录是否进入 `AccessRestrictedActivity`，但本里程碑不修 Play。
14. 保存最小证据并分类：全部通过才晋级 **DEVICE ACCEPTED / REMOTE PASS**；首个 deterministic failure 出现时停止扩展测试并决定 bounded r2 或回刷 `m8b-ime-r1`。

## 强制回滚

| Role | Path | SHA-256 |
|---|---|---|
| r13 golden rollback | `out/candidates/m8a-initial-atv-r13/x12-m8a-initial-atv-r13.img` | `1D367F7091A7BD6A0791B2CFE45E7AAB551E0312D8C68136548A4927354A8E06` |
| Test8r2 rollback | `C:\Users\tiany\Documents\ubox10-rom改造\out\candidates\test8r2-restore-contacts-provider-r1\x12-test8r2-restore-contacts-provider.img` | `6A52F3388E9ABF6AFA8A701CFD7198FE6C0090F16531F6E3BD3949E760892EC8` |
| Stock recovery | `C:\Users\tiany\Documents\ubox10-rom改造\x12-1024.img` | `371A653604618E8B78786F279EA6F64E5D1028B430C9B41F330B08456A264065` |

Physical flashing requires a separate explicit user authorization. Never overwrite, rename or modify rollback sources.
