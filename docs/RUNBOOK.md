# 当前运行手册

## 当前阶段

Test8r2 已恢复 AOSP ContactsProvider 完整目录，并通过端到端自动验证和 PhoenixCard 真机刷测。原 Test8 有蓝牙回归，不再使用；Test8r2 是当前稳定基线。

- 镜像：`out/candidates/test8r2-restore-contacts-provider-r1/x12-test8r2-restore-contacts-provider.img`
- 大小：2,005,954,560 字节
- 仅在复制或移动镜像后核对 SHA-256：`6A52F3388E9ABF6AFA8A701CFD7198FE6C0090F16531F6E3BD3949E760892EC8`
- PhoenixCard：使用已验证的 Product 模式，并确认目标是 TF 卡。

## Test8r2 真机验收结果

- PhoenixCard 刷写后正常进入 Android，并直接进入 Projectivy。
- 默认界面为英语；Direction/OK/Back/Home、`Settings` 和 Wi‑Fi 正常。
- 蓝牙保持开启并可扫描，ADB 结果为 `enabled: true`、`state: ON`、`Bluetooth crashed 0 times`。
- ContactsProvider 来自 `/system/priv-app/ContactsProvider/ContactsProvider.apk`。
- X12、settingwizard 和 HappyCast 三个厂商包查询无输出。

本批未重复测试 bilibili、HDMI 音频、以太网、视频解码或 UART；这些项目不受本次 ContactsProvider 修复影响。

## 异常处理

- 若蓝牙仍关闭，把上述 `dumpsys` 输出发回；设备保持联网，不先采 UART。
- 若 Android 或 ADB 不可用，再采集 UART；可刷回 Test7 或官方 `x12-1024.img`。

## 后续应用

下一阶段进入 Test9：先检查 Google Play 认证、TV 应用目录、设备显示名称和 Projectivy 轻微卡顿，再用配置脚本将 Kodi、Jellyfin、Moonlight 和 SmartTube 安装到 data 分区，并选择 AirPlay 接收器和现代文件管理器。
