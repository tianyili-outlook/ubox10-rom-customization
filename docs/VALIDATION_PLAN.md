# 验证计划与放行标准

## 核心原则

所有“成功”都必须标明证据等级：

1. **已观察**：屏幕、USB 枚举、原始命令输出。
2. **离线已验证**：主机侧可解析、校验和或差分通过。
3. **协议已验证**：设备完成无修改协议握手。
4. **实机已验证**：目标系统启动并完成相应硬件/功能回归。

不能将较低级证据升级为较高级结论。`lpdump`、`avbtool info_image`、容器 checksum 和 PhoenixCard 100% 进度均不是 Android 启动成功的证据。

## M6b：零内容改动 round-trip

M6b 的输入必须是官方原始副本；不删除 APK、不修改属性、不注入调试配置。每层失败时停止在该层修工具，不进入下一层。

| 层 | 要比较的对象 | 最低通过条件 | 当前状态 |
|---|---|---|---|
| PhoenixCard 容器 | 条目名、偏移、长度、填充、下载映射、伴生校验和 | 原件与重建容器目录语义一致；所有验证项通过 | 仅结构部分通过 |
| super / LP metadata | metadata slot、group、extent、分区大小、属性、分区内容哈希 | `lpdump` 差分可解释且每个逻辑分区内容保持一致 | 未通过 |
| ext4 | 路径树、文件内容、符号链接目标、UID/GID、mode、SELinux xattr、capability、硬链接、ACL、inode 特征、label/UUID/features | 语义差分为空，或每一差异均有批准的格式化理由 | 未通过 |
| AVB | public key、descriptor、算法、salt、hashtree、FEC、rollback index、分区大小 | 原件与零内容候选的所有差异为零或有可验证解释 | 未通过 |

二进制字节完全一致是最佳结果，但 ext4 可能因时间戳、UUID 或分配器而不同；这种情况下必须建立机器可读语义比较器，而不是靠人工抽查。

## M6c：最小内容变更回归

每次候选仅允许一个 manifest 变更，例如：一个 APK 删除、一个 APK 预装、一个 `build.prop` 属性，或一个 overlay。一次变更必须有：

- 输入/输出 SHA-256、工具版本、命令行和日志；
- 依赖解释（APK → service/init/SELinux/property）；
- AVB 与分区差分报告；
- 官方回退镜像及目标烧录介质确认；
- 清晰的“预期现象 / 失败判定 / 恢复步骤”。

只有 M6b 通过、风险登记册更新、并得到明确刷写授权后，才允许实机测试 M6c 候选。

## M7：实机功能矩阵

Android System 能启动后，按每个候选构建执行并记录：Wi-Fi、蓝牙、以太网、HDMI、CEC、遥控、音频输出、视频硬解、休眠/唤醒、Google Play、网络访问（包括 `bilibili.com` / `api.bilibili.com`）、Projectivy/目标启动器、SmartTube、Kodi、Jellyfin、Moonlight 和 AirPlay 接收。

任何硬件回归失败都必须回到最近一个可启动的、已标记构建；不得通过附加更多修改“顺带修复”。
