# 项目章程

## 目标

在现有硬件能力范围内，把 UBOX10 改造成可恢复、现代、开放、遥控器优先的电视影音设备。近期在厂商 Android 12/32 位栈上完成可靠性与体验收尾；M8 再以证据驱动的方式评估 AArch64/multilib 和源码级 AOSP Android TV 产品迁移。

产品体验重点：

- 简洁、现代、适合遥控器的电视 Launcher。
- 启动、桌面导航、应用启动和视频播放流畅。
- 服务电视影音和常用电视应用，不追求智能家居、办公、日程或机械最少进程。
- 当前系统保留 Google 服务、ADB、APK 安装、USB/文件管理等扩展方式；真正适合遥控器的 TV Play Store 体验属于未来平台升级，不用随机替换 APK 冒充完成。
- 提供便捷、安全的 iPhone 局域网遥控与文字输入，减少账号、密码和搜索词的遥控器逐字输入；蓝牙键盘保留为硬件回退。
- 目标应用包括 Projectivy、SmartTube、Kodi、Jellyfin、Moonlight 和 AirPlay 接收器；第三方 APK 必须记录来源、版本、签名和许可证。
- 在稳定性、驱动和应用兼容允许时充分利用 CPU、GPU、视频硬解、内存和存储；M8 首选 arm64 Framework + arm32 secondary ABI，并以 64 位 Mali/Gralloc/Mapper/HWC 为首个硬门槛。
- 使用用户本人合法 Netflix 账号实现稳定播放是正式目标；N1 基础播放必做，N2 HD 条件性推进，N3 4K/HDR 仅在硬件、安全链路和服务端资格全部满足时推进。

## 明确不做

- 不以 root、Magisk 或解锁为项目目标。
- 不把“仅安装第三方桌面”视为完成。
- 不以恢复官方原样固件为成果。
- 不在未建立可恢复路径前刷写候选镜像。
- 不通过复制其他设备 Widevine/TEE/HDCP 密钥、伪造认证或修改 Netflix ESN 获得受保护内容能力。
- 不把修改 ABI 属性、增加 `lib64`、更换 Kernel 或添加 Leanback XML 当作 64 位/AOSP ATV 迁移。

## 工作原则

1. 保留官方镜像及其 SHA-256，任何测试镜像使用新文件名。
2. 可恢复的解包、修改、重打包和刷机实验直接推进；失败后用官方 PhoenixCard 镜像恢复。
3. 只在可能永久损坏 eFuse/OTP/BootROM、唯一密钥、无备份分区表/bootloader 或宿主物理磁盘时暂停。
4. 文档只保留当前状态、重要事实、关键决定、阻塞、下一步和必须复用的路径/版本/参数；优先替换旧内容，不为普通错误建立风险编号或变更单。
5. 不复制、重签或重新分发受许可限制的 Google 组件。
6. 测试只覆盖本次修改最可能影响的功能；普通日志、文档、脚本和中间产物不默认生成哈希。
7. 不为了减少进程数量机械删除仍有电视价值、兼容价值或扩展价值的组件；每项保留/删除以实际使用场景决定。
8. 未验证架构判断使用 `CONFIRMED`、`LIKELY`、`UNKNOWN`、`BLOCKED`，不把供体仓库声明写成 UBOX10 真机能力。
9. 任何可能影响 DRM、TEE、secure codec、protected buffer 或 HDCP 的修改前，先建立原厂/Test8r2 只读基线。

## 当前状态

UART、Fastboot、WSL2、ext4/AVB/super/IMAGEWTY 构建链均已完成。Test8r2 是唯一稳定基线且设备已刷回；Test9w1 未证明改善并已退役，Test9r2 已在最小 `BLUETOOTH_CONNECT` 临时授权下证明官方 Google TV iPhone 发现、配对、遥控与文字输入可行，但因 Play Store 回归总体为 `PARTIAL`。项目已选择 S3。M7 于 2026-07-29 完成：Test9.3 五项应用完成统一安装、重启和遥控验收，SmartTube 1080p、AnExplorer USB/APK 与 AirReceiverLite iPhone 音视频通过；Kodi/Jellyfin/Moonlight 的有限资源豁免已记录。用户不把 AirReceiver 完整版购买纳入项目。官方手机遥控产品化转入 M8.INPUT；M8 不开发 UBOX Input，也不在图形栈与 DRM 基线明确前制作 64 位候选。
