# 风险登记册

只记录可能长期影响项目或造成不可恢复后果的风险。

| 风险 | 当前处理 |
|---|---|
| eFuse、OTP、BootROM 被永久修改 | 禁止操作；如未来确有需要必须单独暂停确认。 |
| DRM、校准、设备身份或唯一密钥丢失 | 不擦除、不覆盖；不得把未知物理分区当作普通测试区。 |
| 无备份修改分区表或 bootloader | 官方 bootloader 和分区表已有 PhoenixCard 来源；测试阶段不单独改写它们。 |
| 宿主机物理磁盘被误写 | PhoenixCard 前必须确认目标是 TF 卡；不对不确定磁盘执行写入。 |
| 厂商应用与硬件服务存在隐藏依赖 | 可恢复组件允许批量删除；只测试本批最可能影响的功能，失败刷回上一测试版或官方镜像。 |
| AVB 测试密钥不被设备启动链接受 | 测试版可能不启动；UART 记录结果后刷回官方 `x12-1024.img`。 |
| Google 服务授权或认证被破坏 | 保留设备原有 GMS，不从项目重新分发或盲目替换。 |
| 历史 Test9w1 Wi‑Fi driver patch/无 FEC vendor_dlkm 被误传到后续 | Test9w1 已退役；Test9r1 和后续候选从 Test8r2 构筑，语义检查要求 `vendor_dlkm` 与官方输入一致。历史配置只用于复现证据。 |
| Google Remote Service 专有 APK 被误提交或重新分发 | donor 只放忽略的 `work/`；脚本验证固定 APK/证书哈希但不下载，Git 只保存 AOSP 构建脚本、XML、配置和哈希。提交前检查 ignored/untracked 文件。 |
| Remote Service 特权过大或绕过输入安全 | privapp allowlist 只列 Android 12 上具有 privileged bit 的请求；不伪授予纯 signature 的 `INJECT_EVENTS`，provider 必须走 BIND_TV_REMOTE_SERVICE、显式 package allowlist、配对认证和 framework uinput bridge。 |
| Test9r1 的 leanback 重新触发 Play Store 不兼容 | 真机把 Play Store 列为强制交叉回归；即使 iPhone remote 成功，Play Store 失效也禁止晋级，立即保留证据并刷回 Test8r2。 |
| 局域网 remote discovery/监听扩大攻击面 | 只接受官方配对码或等价认证；验证未配对客户端不能注入输入，不开放通用 ADB/键盘端口，失败即停止候选。 |
| 缺少兼容 H616/Mali-G31 的 64 位图形栈 | 作为 M8 第一 Go/No-Go；未证明 EGL/Mali/Gralloc/Mapper/HWC 与 Kernel ABI 匹配前不制作 64 位 UI 候选。 |
| H618/其他板型供体破坏 UBOX10 板级启动或硬件 | 只引用源码、配置或经依赖验证的单组件；不刷供体 bootloader、完整 DTB/DTBO、TEE、密钥或分区表。 |
| 64 位、图形或媒体迁移破坏合法 DRM 能力 | 相关修改前建立原厂/Test8r2 的 Widevine、TEE/OEMCrypto、secure codec、protected path 和 HDCP 基线；安全材料只保留 UBOX10 原件。 |
| 把 Widevine L1 或系统属性误当 Netflix HD/4K | 使用 N0–N3 分级和实际播放证据；缺服务端资格或 provisioning 时记录外部阻塞，不伪造通过。 |
| M8 大型源码/产物耗尽系统盘 | 下载前锁定 commit、文件清单和空间；源码/产物放 WSL/Linux 文件系统或独立构建盘，不放当前仓库。 |
| 空间清理误删唯一恢复或复现输入 | 官方 `x12-1024.img`、Test8r2 与当前 Test9r1 使用固定路径/哈希 allowlist；其他输入先证明可由准备脚本恢复再删除。 |

当前恢复路径：使用 PhoenixCard 将官方 `x12-1024.img` 重新写入设备。
