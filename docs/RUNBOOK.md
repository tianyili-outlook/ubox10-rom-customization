# 当前运行手册

## 当前状态

Test8r2 是唯一稳定基线：

- 镜像：`out/candidates/test8r2-restore-contacts-provider-r1/x12-test8r2-restore-contacts-provider.img`
- 大小：2,005,954,560 bytes
- SHA-256：`6A52F3388E9ABF6AFA8A701CFD7198FE6C0090F16531F6E3BD3949E760892EC8`
- 已通过：Projectivy、英语、实体遥控、Settings、Wi‑Fi 连接、蓝牙和
  ContactsProvider/PBAP。

Test9r1 是当前实验候选：

- 镜像：`out/candidates/test9r1-android-tv-remote-service-r1/x12-test9r1-android-tv-remote-service.img`
- 大小：2,005,946,368 bytes
- SHA-256：`38A0C232750ECD433B2783E0CFBFFC48C17071226EE2AEC978BE5AC6C12F6E33`
- 基线：Test8r2，不含 Test9w1 driver patch。
- 变量：Android 12 AOSP remoteprovider shared library、leanback、framework
  provider RRO、privapp allowlist 和本地官方原签名 Android TV Remote
  Service。
- 离线结果：ext4、e2fsck、完整 AVB、super、IMAGEWTY 和单元测试全部 PASS。
- 状态：等待真机；不能作为稳定固件。

Test9w1 已退役。真机虽显示 `ant_div=N`，但稳定的 5 GHz 网络没有问题，
目标 2.4 GHz 网络仍未出现；它未证明实质改善，镜像不再保留，后续不得从其
构筑。

## 刷写前

PhoenixCard Product 模式可能清除 userdata/metadata：

1. 备份需要保留的账号和本地数据。
2. 确认 Test8r2 恢复镜像仍在。
3. 确认目标是 TF 卡。
4. 核对当前候选：

   ```powershell
   Get-FileHash `
     .\out\candidates\test9r1-android-tv-remote-service-r1\x12-test9r1-android-tv-remote-service.img `
     -Algorithm SHA256
   ```

5. 仅当结果为
   `38A0C232750ECD433B2783E0CFBFFC48C17071226EE2AEC978BE5AC6C12F6E33`
   时写卡。

## 首次启动最低回归

启动完成后先验证：

- 自动进入 Projectivy；
- Direction/OK/Back/Home 和 Settings；
- Wi‑Fi 连接、互联网和 TCP ADB；
- 蓝牙保持开启、可扫描；
- Play Store 能否打开、搜索和安装；
- 没有反复重启或系统错误。

任一启动、输入、网络或蓝牙关键项失败，停止 remote 测试并刷回 Test8r2。

## ADB 验证 remote stack

设备地址仍为 `192.168.1.5:7896` 时：

```powershell
$adb = ".\tools\platform-tools\adb.exe"
& $adb connect 192.168.1.5:7896

& $adb shell pm list features |
  Select-String "android.hardware.type.television|android.software.leanback"

& $adb shell pm list libraries |
  Select-String "com.android.media.tv.remoteprovider"

& $adb shell pm path com.google.android.tv.remote.service

& $adb shell cmd overlay list |
  Select-String "com.ubox10.overlay.tvremote"

& $adb shell cmd overlay lookup `
  android android:string/config_tvRemoteServicePackage

& $adb shell dumpsys package com.google.android.tv.remote.service |
  Select-String "versionName=|versionCode=|TV_VIRTUAL_REMOTE_CONTROLLER|INJECT_EVENTS|granted="

& $adb shell ss -lntup |
  Select-String "6466|6467"

& $adb shell logcat -d -v threadtime |
  Select-String "TvRemoteService|TvRemoteProvider|AtvRemote|remote.service|privapp"
```

预期：

- television 与 leanback 均存在，不要求 leanback_only；
- shared library 存在；
- APK 来自 `/system/priv-app/AndroidTvRemoteService/`；
- overlay 启用，lookup 返回
  `com.google.android.tv.remote.service`；
- `TV_VIRTUAL_REMOTE_CONTROLLER` 已授予；
- `INJECT_EVENTS` 可以未授予，这是设计结果；
- 没有 privapp allowlist enforcement 错误。

## iPhone 验收

iPhone 官方 Google TV 应用与电视连接同一 5 GHz Wi‑Fi：

1. 发现电视；
2. 电视显示配对码并完成认证；
3. 验证方向、OK、Back、Home；
4. 在搜索、普通账号、密码和 Unicode 文本框输入；
5. 断开 iPhone，确认实体遥控仍正常；
6. 重启电视，复验发现、配对状态和输入。

不要安装或开发 UBOX Input。不要开放未认证的 ADB/通用键盘端口，也不要
尝试伪授予纯 signature 的 `INJECT_EVENTS`。

## 结果判定

- remote 与全部交叉回归通过：记录 Test9r1 PASS，再决定是否晋级。
- remote 成功但 Play Store 不兼容：记录 PARTIAL；Test9r1 不晋级。
- package/library/RRO 失败：按 Package Manager/product 集成层定位。
- 能发现/配对但不能输入：按 provider bind、权限、uinput bridge 层定位。
- 任一关键回归：保存最小 ADB 日志并刷回 Test8r2。

完整判错树、输入哈希和复现方式见
`experiments/TEST9R1_ANDROID_TV_REMOTE_SERVICE.md`。M8 边界见
`architecture/M8_ARM64_AOSP_TV_MIGRATION.md`。
