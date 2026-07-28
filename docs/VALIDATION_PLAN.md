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

## Test9w1 门槛

- 离线 PASS：只有锁定哈希的 `aic8800_fdrv.ko` 有效载荷一字节变化；ext4、AVB、super、IMAGEWTY 和单元测试通过。
- 实机必须确认：冷启动 30 秒内目标可见、五轮至少 4/5、无连续全频零结果或约 30 dB RSSI 双峰。
- 启动、一次 Wi‑Fi 关闭/开启和重启后的 `ant_div` 都必须为 `N`。
- 互联网/TCP ADB、自动重连和蓝牙 `ON`/扫描/崩溃 0 次必须同时通过。
- 任一关键项失败时 Test8r2 继续作为稳定基线。

## M8 门槛

- M8.0–M8.2 只产生 inventory、source-lock、差异和 Go/No-Go 报告，不产生刷机镜像。
- M8.3 前必须明确 64 位 Mali/EGL/Gralloc/Mapper/HWC 与当前 Kernel ABI 的兼容结论。
- `ro.zygote`、ABI 属性或目录名不能替代 ELF 和运行进程位数证据。
- 原厂/Test8r2 的 Widevine、DRM HAL、TEE/OEMCrypto、secure codec、protected buffer 和 HDCP 基线必须在相关修改前建立。
- 其他板型 bootloader、DTB/DTBO、TEE、密钥和分区表不得进入候选。
- M8 每个可刷写阶段仍须满足现有 ext4/AVB/super/IMAGEWTY、UART 和恢复门槛。

## 结果处理

- 能启动且没有新回归：保留该候选作为下一批修改的基线。
- 不能启动：保存 UART 日志，刷回官方镜像，再根据第一个明确错误修改。
- 能启动但硬件异常：刷回官方镜像确认硬件正常，再缩小删除范围。
- Launcher 异常但 Android/ADB 正常：从 `Settings > Apps` 启动 Projectivy 并记录现象；必要时刷回 Test8r2。
