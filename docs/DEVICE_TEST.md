# M8 device test and rollback

## 当前状态

- 当前设备验收基线：`out/candidates/m8b-rc-core-r5/x12-m8b-rc-core-r5.img`
- 待授权首测：`out/candidates/m8b-audio-r1/x12-m8b-audio-r1.img`
- 大小 / SHA-256：1025951744 bytes / `298DCA11DBDFDC81028869C01866411C634FC2C7B979EDA3FB0346BF7434DBDD`
- 当前未刷机；物理刷写仍需单独明确授权。

Wi-Fi ADB：

```powershell
C:\platform-tools\adb.exe -s 192.168.1.9:7896 shell <read-only-command>
```

刷写获批后，首轮只执行：

```powershell
C:\platform-tools\adb.exe -s 192.168.1.9:7896 shell getprop sys.boot_completed
C:\platform-tools\adb.exe -s 192.168.1.9:7896 shell cmd apexservice list --active
C:\platform-tools\adb.exe -s 192.168.1.9:7896 shell ls -l /apex/com.android.vndk.v31/lib/libaudioroute.so
C:\platform-tools\adb.exe -s 192.168.1.9:7896 shell dumpsys media.audio_flinger
C:\platform-tools\adb.exe -s 192.168.1.9:7896 shell dumpsys media.audio_policy
C:\platform-tools\adb.exe -s 192.168.1.9:7896 logcat -d -b all
```

验收顺序：`com.android.vndk.v31` active；`libaudioroute.so` 可见；日志不再出现 `dlopen ... libaudioroute.so not found`；primary HAL/output 创建；已知 HEVC+AAC 不再停在 0:00。若出现新首错，保存完整日志后停止，不修改 mixer、audio platform XML、DTS 或 machine driver。

## 强制回滚

| Role | Path | SHA-256 |
|---|---|---|
| r13 golden rollback | `out/candidates/m8a-initial-atv-r13/x12-m8a-initial-atv-r13.img` | `1D367F7091A7BD6A0791B2CFE45E7AAB551E0312D8C68136548A4927354A8E06` |
| Test8r2 rollback | `C:\Users\tiany\Documents\ubox10-rom改造\out\candidates\test8r2-restore-contacts-provider-r1\x12-test8r2-restore-contacts-provider.img` | `6A52F3388E9ABF6AFA8A701CFD7198FE6C0090F16531F6E3BD3949E760892EC8` |
| Stock recovery | `C:\Users\tiany\Documents\ubox10-rom改造\x12-1024.img` | `371A653604618E8B78786F279EA6F64E5D1028B430C9B41F330B08456A264065` |

Physical flashing requires a separate explicit user authorization. Never overwrite, rename or modify rollback sources.
