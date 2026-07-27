# 当前运行手册

## 当前阶段

Test8r2 已恢复 AOSP ContactsProvider 完整目录，并通过端到端自动验证和 PhoenixCard 真机刷测。原 Test8 有蓝牙回归，不再使用；Test8r2 是当前稳定基线。

- 镜像：`out/candidates/test8r2-restore-contacts-provider-r1/x12-test8r2-restore-contacts-provider.img`
- 大小：2,005,954,560 字节
- 仅在复制或移动镜像后核对 SHA-256：`6A52F3388E9ABF6AFA8A701CFD7198FE6C0090F16531F6E3BD3949E760892EC8`
- PhoenixCard：使用已验证的 Product 模式，并确认目标是 TF 卡。

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

## Test8r2 恢复后的下一步

1. 等 PhoenixCard 刷写和首次启动完全结束；不在刷机过程中连接 ADB。
2. 先完成 Test9.1 Wi‑Fi 扫描采证，不先开关 Wi‑Fi、不改路由器，也不修改 vendor。
3. Wi‑Fi 扫描达到路线图验收标准后，再进行 Test9.2 iPhone 官方 Google TV 遥控和文字输入验证。
4. 最后用配置脚本安装 Kodi、Jellyfin、Moonlight 和 SmartTube，并选择 AirPlay 接收器与现代文件管理器。

详细步骤和验收标准见 `docs/ROADMAP.md`。
