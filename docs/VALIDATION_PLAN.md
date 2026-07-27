# 验证计划

## 每个候选的最低离线检查

- 输入、输出路径和刷机镜像完整性正确。
- 原版固件仍存在，可用 PhoenixCard 恢复。
- ext4 只出现计划内的文件差异。
- `e2fsck`、AVB、LP/super 和 IMAGEWTY 校验通过。

## Test8r2 实机检查结果

- PASS：启动后直接进入 Projectivy，英语界面、遥控、Settings 和 Wi‑Fi 正常。
- PASS：蓝牙保持开启并能扫描。
- PASS：ADB 确认 ContactsProvider 来自 `/system/priv-app`，蓝牙为 `state: ON`、`Bluetooth crashed 0 times`。
- PASS：X12、settingwizard 和 HappyCast 三个厂商包均不存在。
- 按变更范围未重复测试 bilibili、HDMI 音频、以太网、视频解码或 UART。

## 结果处理

- 能启动且没有新回归：保留该候选作为下一批修改的基线。
- 不能启动：保存 UART 日志，刷回官方镜像，再根据第一个明确错误修改。
- 能启动但硬件异常：刷回官方镜像确认硬件正常，再缩小删除范围。
- Launcher 异常但 Android/ADB 正常：从 `Settings > Apps` 启动 Projectivy并记录现象；必要时刷回 Test7。
