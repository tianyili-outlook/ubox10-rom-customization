# 当前运行手册

## 当前阶段

Test8r2 已恢复 AOSP ContactsProvider 完整目录，并通过端到端自动验证和 PhoenixCard 真机刷测。原 Test8 有蓝牙回归，不再使用；Test8r2 是当前稳定基线。

- 镜像：`out/candidates/test8r2-restore-contacts-provider-r1/x12-test8r2-restore-contacts-provider.img`
- 大小：2,005,954,560 字节
- 仅在复制或移动镜像后核对 SHA-256：`6A52F3388E9ABF6AFA8A701CFD7198FE6C0090F16531F6E3BD3949E760892EC8`
- PhoenixCard：使用已验证的 Product 模式，并确认目标是 TF 卡。

Test9w1 已完成离线构建与验证，当前正在刷测但尚无实机结果，只能作为 Wi‑Fi 单变量实验：

- 镜像：`out/candidates/test9w1-disable-aic-ant-div-r1/x12-test9w1-disable-aic-ant-div.img`
- 大小：2,005,897,216 字节
- 刷写前核对 SHA-256：`2D43D4A6B64702F1D0265EDC27B33EB424B4B56A721DC8068B5CCEBB4A310CC5`
- 唯一功能变量：`aic8800_fdrv.ko` 的默认 `ant_div=Y` 改为 `N`；Test8r2 仍是恢复点。
- 已知限制：重建的 vendor_dlkm 有 dm-verity、无 FEC；本候选不能直接晋级为日常基线。

## Test8r2 真机验收结果

- PhoenixCard 刷写后正常进入 Android，并直接进入 Projectivy。
- 默认界面为英语；Direction/OK/Back/Home 和 `Settings` 正常。
- Wi‑Fi 连接成功后互联网与 TCP ADB 正常，但扫描目标 SSID 偶发长期不出现；不得再把“Wi‑Fi 可连接”等同于“扫描可靠性通过”。
- 蓝牙保持开启并可扫描，ADB 结果为 `enabled: true`、`state: ON`、`Bluetooth crashed 0 times`。
- ContactsProvider 来自 `/system/priv-app/ContactsProvider/ContactsProvider.apk`。
- X12、settingwizard 和 HappyCast 三个厂商包查询无输出。

本批未重复测试 bilibili、HDMI 音频、以太网、视频解码或 UART；这些项目不受本次 ContactsProvider 修复影响。

## 异常处理

- 若蓝牙仍关闭，把上述 `dumpsys` 输出发回；设备保持联网，不先采 UART。
- 若 Android 或 ADB 不可用，再采集 UART；可刷回 Test7 或官方 `x12-1024.img`。

## 禁止作为基线的诊断候选

- Test9a 只加入 `android.software.leanback`，Test9b 再加入 `android.software.leanback_only`。
- 两者均能启动、保留 Projectivy HOME 且通过离线验证，但 Play Store 29.2.15 都进入 `com.google.android.finsky.accessrestricted.AccessRestrictedActivity`，提示版本与设备不兼容。
- 不继续在这两个候选上配置设备；用户数据需要保留时先自行备份，开发主线刷回 Test8r2。

## Test9w1 刷测步骤

PhoenixCard 在本项目的既往量产中会清除 userdata/metadata。先备份需要保留的本地数据与账户信息，并确认 Test8r2 镜像仍可用；随后使用已验证的 Product 模式写卡。

1. 写卡前在 PowerShell 核对镜像：

   ```powershell
   Get-FileHash .\out\candidates\test9w1-disable-aic-ant-div-r1\x12-test9w1-disable-aic-ant-div.img -Algorithm SHA256
   ```

2. 刷入后等待首次启动完全结束。先进入 Wi‑Fi 页面，不开关 Wi‑Fi，记录目标网络是否在 30 秒内出现，然后正常连接。
3. 建立 ADB 并确认补丁已生效：

   ```powershell
   $adb = ".\tools\platform-tools\adb.exe"
   & $adb connect 192.168.1.5:7896
   & $adb shell cat /sys/module/aic8800_fdrv/parameters/ant_div
   ```

   预期只输出 `N`；若为 `Y`，停止扫描结论判定并刷回 Test8r2。

4. 保持设备和路由器不动，连续执行五轮扫描，每轮查看目标是否出现及 RSSI；不要把密码或完整 BSSID 提交仓库：

   ```powershell
   1..5 | ForEach-Object {
     & $adb shell cmd wifi start-scan
     Start-Sleep -Seconds 8
     & $adb shell cmd wifi list-scan-results
     Start-Sleep -Seconds 15
   }
   ```

5. 在 Settings 中只关闭、开启 Wi‑Fi 一次；重新连接 ADB，再读一次 `ant_div`，预期仍为 `N`。
6. 重启设备，不切换 Wi‑Fi；确认目标可见或自动连接、互联网/TCP ADB 正常，再读一次 `ant_div`。
7. 最后检查蓝牙：

   ```powershell
   & $adb shell dumpsys bluetooth_manager |
     Select-String "enabled:|state:|Bluetooth crashed"
   ```

   必须保持 `enabled: true`、`state: ON`、`Bluetooth crashed 0 times`，并在界面中能扫描设备。

通过门槛是：冷启动 30 秒内出现目标、五轮至少 4/5 成功、无连续全频零结果或约 30 dB RSSI 双峰、Wi‑Fi 重载和重启后 `ant_div=N`、自动重连与蓝牙均正常。任何启动、Wi‑Fi 或蓝牙关键项失败，都停止扩大改动并用 PhoenixCard 刷回 Test8r2。

Test9w1 通过后再进行 Test9.2 iPhone 官方 Google TV 遥控/文字输入验证；最后进入应用、AirPlay 和文件管理收尾。

刷测期间可并行进行 M8.0 的本地/ADB 只读 inventory 设计和报告，不下载大型 BSP、不修改设备、不制作 64 位候选，也不把 Test9w1 与 DRM/原厂 ROM 对照混成同一次刷机。M8 当前边界见 `architecture/M8_ARM64_AOSP_TV_MIGRATION.md`。

详细步骤和验收标准见 `docs/ROADMAP.md`。
