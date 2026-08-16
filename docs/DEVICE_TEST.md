# M8 device test and rollback

## 当前状态

- 当前运行并验收的设备基线：`out/candidates/m8b-audio-r2/x12-m8b-audio-r2.img`
- 状态：**DEVICE ACCEPTED / AUDIO PASS**
- 大小 / SHA-256：1025951744 bytes / `B39300CB3E335D75C9D61594CD94565D9C24FC92F467F9050CD1E604D87E9C2C`
- 2026-08-16 补验只通过 ADB 执行，未刷机、未重启、未改 ROM/system properties；任何物理刷写仍需单独明确授权。

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

accepted baseline 已确认 Treble/VNDK、primary HAL/output、HEVC+AAC HDMI 音频、VP9 Allwinner/Cedar hardware runtime 与 Widevine 16.1.0 L3。远程工作只做不会影响网络/ADB 的限定检查；不得 reboot/suspend、改网络/ADB、改 device properties 或测试 CEC。若出现新首错，保存最小决定性日志后停止。

## 强制回滚

| Role | Path | SHA-256 |
|---|---|---|
| r13 golden rollback | `out/candidates/m8a-initial-atv-r13/x12-m8a-initial-atv-r13.img` | `1D367F7091A7BD6A0791B2CFE45E7AAB551E0312D8C68136548A4927354A8E06` |
| Test8r2 rollback | `C:\Users\tiany\Documents\ubox10-rom改造\out\candidates\test8r2-restore-contacts-provider-r1\x12-test8r2-restore-contacts-provider.img` | `6A52F3388E9ABF6AFA8A701CFD7198FE6C0090F16531F6E3BD3949E760892EC8` |
| Stock recovery | `C:\Users\tiany\Documents\ubox10-rom改造\x12-1024.img` | `371A653604618E8B78786F279EA6F64E5D1028B430C9B41F330B08456A264065` |

Physical flashing requires a separate explicit user authorization. Never overwrite, rename or modify rollback sources.
