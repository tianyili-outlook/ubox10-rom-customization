# 发现记录

每项发现必须包含来源、方法、证据位置、置信度、影响与下一步；推测必须明确标为推测。

## D-0001 — 原始输入文件身份

- 日期：2026-07-19
- 来源：用户提供的工作区文件。
- 方法：SHA-256 计算与前 128 bytes 只读检查。
- 证据：`docs/FIRMWARE_BASELINE.md`。
- 结论：`x12-1024.img` 为 2,018,890,752 bytes，SHA-256 为 `371A653604618E8B78786F279EA6F64E5D1028B430C9B41F330B08456A264065`；开头 ASCII 为 `IMAGEWTY`。
- 置信度：高（文件内容观察）；“PhoenixCard 容器”归类为中，尚待目录解析确认。
- 影响：可以进入只读容器目录分析；不得据此推断分区偏移或签名状态。

## D-0002 — 当前工具基线

- 日期：2026-07-19
- 方法：命令可用性检查。
- 结论：发现 Python 3.13 与 Git；未发现 `lpunpack`、`lpmake`、`lpdump`、`avbtool`、`magiskboot`、`simg2img`、`unpack_bootimg`、`mkbootimg` 等关键工具。
- 置信度：中（仅代表当前 PATH）。
- 影响：M1 先完成 PhoenixCard 容器解析工具选型与锁定；M2 前必须补齐并验证 Android 镜像工具。
