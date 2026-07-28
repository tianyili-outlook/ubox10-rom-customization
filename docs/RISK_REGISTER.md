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
| 实验性 Wi‑Fi 驱动参数导致无线或蓝牙回归 | Test9w1 只改一个带来源/结果哈希和原字节前置条件的默认值；不热卸载模块，失败用 PhoenixCard 刷回 Test8r2 或官方镜像。 |
| 修改后的 vendor_dlkm 缺少官方 FEC 纠错冗余 | 保留 AVB/dm-verity 并只用于可恢复实机实验；长期发布前引入可信可复现的 FEC 工具链，或明确接受并记录无 FEC 策略。 |
| 缺少兼容 H616/Mali-G31 的 64 位图形栈 | 作为 M8 第一 Go/No-Go；未证明 EGL/Mali/Gralloc/Mapper/HWC 与 Kernel ABI 匹配前不制作 64 位 UI 候选。 |
| H618/其他板型供体破坏 UBOX10 板级启动或硬件 | 只引用源码、配置或经依赖验证的单组件；不刷供体 bootloader、完整 DTB/DTBO、TEE、密钥或分区表。 |
| 64 位、图形或媒体迁移破坏合法 DRM 能力 | 相关修改前建立原厂/Test8r2 的 Widevine、TEE/OEMCrypto、secure codec、protected path 和 HDCP 基线；安全材料只保留 UBOX10 原件。 |
| 把 Widevine L1 或系统属性误当 Netflix HD/4K | 使用 N0–N3 分级和实际播放证据；缺服务端资格或 provisioning 时记录外部阻塞，不伪造通过。 |
| M8 大型源码/产物耗尽系统盘 | 下载前锁定 commit、文件清单和空间；源码/产物放 WSL/Linux 文件系统或独立构建盘，不放当前仓库。 |
| 空间清理误删唯一恢复或复现输入 | 官方 `x12-1024.img` 与两份当前固件使用固定路径/哈希 allowlist；其他输入先证明可由 `prepare-candidate-inputs.py` 恢复再删除。 |

当前恢复路径：使用 PhoenixCard 将官方 `x12-1024.img` 重新写入设备。
