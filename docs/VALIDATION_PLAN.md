# 验证计划

## 每个候选的最低离线检查

- 输入、输出路径和刷机镜像完整性正确。
- 原版固件仍存在，可用 PhoenixCard 恢复。
- ext4 只出现计划内的文件差异。
- `e2fsck`、AVB、LP/super 和 IMAGEWTY 校验通过。

## Test8r2 实机检查结果

- PASS：启动后直接进入 Projectivy，英语界面、遥控和 Settings 正常。
- PARTIAL：Wi‑Fi 成功关联后互联网与 TCP ADB 正常；重复扫描目标 SSID 的可靠性尚未通过，按 `docs/ROADMAP.md` 的 Test9.1 单独验收。
- PASS：蓝牙保持开启并能扫描。
- PASS：ADB 确认 ContactsProvider 来自 `/system/priv-app`，蓝牙为 `state: ON`、`Bluetooth crashed 0 times`。
- PASS：X12、settingwizard 和 HappyCast 三个厂商包均不存在。
- 按变更范围未重复测试 bilibili、HDMI 音频、以太网、视频解码或 UART。

## Test9a/Test9b 结果

- FAIL：两者均通过离线结构和完整性验证，但 Play Store 实机进入 `AccessRestrictedActivity` 并提示版本不兼容。
- 只通过离线验证不足以提升为基线；Test9a/Test9b 仅保留作 Leanback feature 对照，不再继续配置或发布。

## 结果处理

- 能启动且没有新回归：保留该候选作为下一批修改的基线。
- 不能启动：保存 UART 日志，刷回官方镜像，再根据第一个明确错误修改。
- 能启动但硬件异常：刷回官方镜像确认硬件正常，再缩小删除范围。
- Launcher 异常但 Android/ADB 正常：从 `Settings > Apps` 启动 Projectivy并记录现象；必要时刷回 Test7。
