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
| 历史 Test9w1 Wi‑Fi driver patch/无 FEC vendor_dlkm 被误传到后续 | Test9w1 已退役；Test9r1/Test9r2 和后续候选从 Test8r2 构筑，语义检查要求 `vendor_dlkm` 与官方输入一致。历史配置只用于复现证据。 |
| Google Remote Service 专有 APK 被误提交或重新分发 | donor 只放忽略的 `work/`；脚本验证固定 APK/证书哈希但不下载，Git 只保存 AOSP 构建脚本、XML、配置和哈希。提交前检查 ignored/untracked 文件。 |
| Remote Service 特权过大或绕过输入安全 | privapp allowlist 只列 Android 12 上具有 privileged bit 的请求；不伪授予纯 signature 的 `INJECT_EVENTS`，provider 必须走 BIND_TV_REMOTE_SERVICE、显式 package allowlist、配对认证和 framework uinput bridge。 |
| Test9r2 的 leanback 重新触发 Play Store 不兼容 | 真机把 Play Store 列为强制交叉回归；即使 iPhone remote 成功，Play Store 失效也禁止晋级，立即保留证据并刷回 Test8r2。 |
| Remote Service 在 corrected RRO 后仍把 Play Store 判定为 missing | Test9r1 已出现该日志；Test9r2 分开记录 RRO/provider、端口和 Google API 初始化层。不得用替换/破解 Play Store 或伪造设备身份绕过。 |
| 预置 RRO 文件存在但不在设备实际扫描路径 | Test9r1 已暴露该风险；Test9r2 先验收 package path、overlay list、lookup 和 watcher，再测试网络发现。M8 必须在 product 构建中原生声明并验证实际注册。 |
| 局域网 remote discovery/监听扩大攻击面 | 只接受官方配对码或等价认证；验证未配对客户端不能注入输入，不开放通用 ADB/键盘端口，失败即停止候选。 |
| Test9r2 后同时修改 framework、GMS、身份和网络导致无法归因 | 先生成分层 runtime report；在 Test9r3、Test10p1 或结束 32 位 remote 中只选一条，路线决策前不制作候选。 |
| 把新版本 MindTheGapps TV 二进制误当 Android 12 ARM32 donor | 仓库只用于 package/permission/overlay/打包结构参考；必须另行锁定精确 Android 12、ABI、签名、依赖与合法来源，未闭合则标记 `BLOCKED`。 |
| 诊断客户端被误当作电视 receiver 修复 | Python/Swift Remote v2 项目只在接收端已监听时隔离客户端问题；它们不提供 system receiver，也不替代官方 Google TV iOS 验收。 |
| ADB/Web remote 向 LAN 暴露按键、文字或 shell 注入 | 当前不集成默认绑定 `0.0.0.0`、开放 HTTP、raw shell 或共享 ADB key 的方案；末级备选必须先完成强认证、绑定/CSRF、API 最小化、密钥与 SELinux 安全审计。 |
| M8A 的 AOSP ATV system/product 与现有 32 位 vendor 不兼容 | M8A.1 先做 package/permission/overlay/VINTF/容量差异；M8A.2 保持 boot/kernel/vendor/vendor_dlkm/TEE 不变并分层启动，每层可刷回 Test8r2。 |
| 缺少兼容 H616/Mali-G31 的 64 位图形栈 | 作为 M8B 第一 Go/No-Go；未证明 EGL/Mali/Gralloc/Mapper/HWC 与 Kernel ABI 匹配前不制作 64 位 UI 候选，但不阻塞 M8A 的 ARM32 ATV 产品研究。 |
| H618/其他板型供体破坏 UBOX10 板级启动或硬件 | 只引用源码、配置或经依赖验证的单组件；不刷供体 bootloader、完整 DTB/DTBO、TEE、密钥或分区表。 |
| 64 位、图形或媒体迁移破坏合法 DRM 能力 | 相关修改前建立原厂/Test8r2 的 Widevine、TEE/OEMCrypto、secure codec、protected path 和 HDCP 基线；安全材料只保留 UBOX10 原件。 |
| 把 Widevine L1 或系统属性误当 Netflix HD/4K | 使用 N0–N3 分级和实际播放证据；缺服务端资格或 provisioning 时记录外部阻塞，不伪造通过。 |
| M8 大型源码/产物耗尽系统盘 | 下载前锁定 commit、文件清单和空间；源码/产物放 WSL/Linux 文件系统或独立构建盘，不放当前仓库。 |
| 空间清理误删唯一恢复或高频构建输入 | 官方 `x12-1024.img`、Test8r2、当前 Test9r2 和四个 `out/official-*` 逻辑分区缓存使用固定路径/哈希保留清单；常规清理只删除淘汰候选和候选中间镜像。 |

当前恢复路径：使用 PhoenixCard 将官方 `x12-1024.img` 重新写入设备。
