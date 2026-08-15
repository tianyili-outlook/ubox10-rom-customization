# M8 device test and rollback

## 当前状态

- 当前设备验收基线：`out/candidates/m8b-rc-core-r5/x12-m8b-rc-core-r5.img`
- 大小：1007982592 bytes
- SHA-256：`7B4D3E28D37CE242F92FF259BB43590EDF422630DA7B515D66E4DF1A000CFA98`
- 本轮仅允许只读音频取证，不刷机、不写分区、不修改持久设置。

Wi-Fi ADB：

```powershell
C:\platform-tools\adb.exe -s 192.168.1.9:7896 shell <read-only-command>
```

只在某条命令能区分具体音频假设时采集 `/proc/asound`、`/sys`、`getprop`、`lshal`、`dumpsys`、logcat 或 dmesg；不重复已确认的基础功能测试。

下一项音频取证需另行授权非持久服务重启：先持续捕获完整 logcat，再仅重启 `vendor.audio-hal`/audioserver，记录 Apollo HAL `adev_open`、`audio_route_init`、首个 missing mixer control 与返回 errno。不得清数据、写分区或修改持久属性。

## 强制回滚

| Role | Path | SHA-256 |
|---|---|---|
| r13 golden rollback | `out/candidates/m8a-initial-atv-r13/x12-m8a-initial-atv-r13.img` | `1D367F7091A7BD6A0791B2CFE45E7AAB551E0312D8C68136548A4927354A8E06` |
| Test8r2 rollback | `C:\Users\tiany\Documents\ubox10-rom改造\out\candidates\test8r2-restore-contacts-provider-r1\x12-test8r2-restore-contacts-provider.img` | `6A52F3388E9ABF6AFA8A701CFD7198FE6C0090F16531F6E3BD3949E760892EC8` |
| Stock recovery | `C:\Users\tiany\Documents\ubox10-rom改造\x12-1024.img` | `371A653604618E8B78786F279EA6F64E5D1028B430C9B41F330B08456A264065` |

Physical flashing requires a separate explicit user authorization. Never overwrite, rename or modify rollback sources.
