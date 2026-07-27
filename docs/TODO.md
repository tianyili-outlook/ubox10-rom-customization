# 待办事项

## 当前：Test8r2 上完成 Test9 可靠性与体验收尾

- [x] 提取官方 `system_a/product_a/vendor_a/vendor_dlkm_a`。
- [x] 建立官方 `system_a` 的 3857 条 ext4 语义清单。
- [x] 只删除 `/system/app/UBTunnel.6` 并生成测试版。
- [x] 验证 AVB、dynamic super、ext4 和 IMAGEWTY 容器。
- [x] 用 PhoenixCard 刷入 `x12-test1-no-ubtunnel.img`；`CARD OK`、`sprite success`。
- [x] Android、主界面、设置正常，UBTunnel 已消失。
- [x] 红外遥控、HDMI 音视频、Wi‑Fi、以太网、蓝牙扫描和高码率视频正常。
- [x] `google.com`、YouTube、`bilibili.com`、`api.bilibili.com` 可访问。
- [x] CEC 按用户需求跳过；BBLL 以 API 恢复作为本阶段通过。
- [x] 通过 `192.168.1.8:7896` 建立局域网 ADB并取得最小运行时基线。
- [x] 构建测试版 2：累计删除 UBTunnel、DragonAtt、DragonBox、DragonAgingTV、Factory_detection、AwlogSettings。
- [x] 验证测试版 2 的 ext4 语义差异、完整 AVB 启动链和 IMAGEWTY 载荷。
- [x] 用 PhoenixCard Product 模式刷入测试版 2。
- [x] 最小回归：Android/Settings、红外遥控、HDMI 音视频、Wi‑Fi 和 bilibili API。
- [x] ADB 确认五个工厂测试/日志应用不再存在。
- [x] 通过只读 ADB 确定测试版 3 目标：厂商浏览器、H618 Upgrade 和 Softwinner Update。
- [x] 构建并离线验证测试版 3。
- [x] 刷入测试版 3，验证启动、遥控、HDMI，并确认三个目标包消失。
- [x] 确定 Test4：批量删除八个旧媒体、文件管理和输入应用目录。
- [x] 构建并离线验证 Test4。
- [x] 刷入 Test4，Android 启动且默认 LatinIME 正常。
- [x] ADB 确认八个目标包消失。
- [x] 确定 Test5：删除 17 个无对应硬件或当前未使用的平台应用。
- [x] 构建并离线验证 Test5。
- [x] 刷入 Test5，Android、网络 ADB 和 Google 核心包正常。
- [x] ADB 确认 17 个新增目标包消失且五个关键保留包存在。
- [x] 确定 Test6：新增删除 16 个旧个人设备 UI 和非目标功能组件。
- [x] 构建并离线验证 Test6。
- [x] 刷入 Test6 并完成最小实机验收。
- [x] 从官方 GitHub 下载并核对 Projectivy 4.71。
- [x] 通过 ADB 将 Projectivy 4.71 安装为用户应用。
- [x] 在电视端启动 Projectivy并设为默认 Launcher；遥控、应用列表、Settings、应用启动和 Home 行为通过，仅有轻微卡顿。

## 后续批次

- [x] 构建并离线验证 Test7：注入 Projectivy、设为默认 Launcher，保留 X12 回退。
- [x] 刷入 Test7：Projectivy system app、默认 HOME、遥控/Home/Settings 和应用启动通过；首次启动因保留两个 HOME 出现选择框。
- [x] 构建并离线验证 Test8：移除 X12、settingwizard、HappyCast，默认语言改为英语。
- [x] 刷入 Test8：单一 Projectivy HOME、英语、遥控/HDMI、Wi‑Fi 和目标包删除结果通过。
- [x] 定位蓝牙回归：Bluetooth PBAP 因 Test6 删除 ContactsProvider 而崩溃，与 settingwizard/HAL 无关。
- [x] 临时恢复 ContactsProvider 后蓝牙保持开启并进入扫描；实验包已卸载。
- [x] 构建器增加 WSL 前置检查、事务式发布、失败自动清理和统一自动验证。
- [x] 构建并离线验证 Test8r2；恢复 ContactsProvider APK/ODEX/VDEX 完整目录。
- [x] 刷入 Test8r2，确认蓝牙保持开启、能扫描且 `Bluetooth crashed 0 times`；原 Test8 不作为基线。
- [x] Test9a：只加入 `android.software.leanback`；离线验证通过，但实机 Play Store 提示版本不兼容，候选淘汰。
- [x] Test9b：继续加入 `android.software.leanback_only`；离线验证通过，但实机仍进入 Play Store `AccessRestrictedActivity`，候选淘汰。
- [x] 确认当前 Play Store 可登录、搜索和安装 Jellyfin TV，但首页失败、界面不适合遥控且没有可见的 Play Protect certification 项。
- [x] Test9.1：在 Test8r2 上完成 5 轮主动扫描、历史 `WifiScanner`、framework/HAL/驱动和模块加载路径采证；确认存在历史连续零结果扫描、约 30 dB RSSI 双峰与 AIC vendor 能力缺口。
- [x] Test9.1：确认板上丝印 AW869A，结合官方 1T1R/单天线规格与运行时 `ant_div=Y`，建立可证伪的天线分集假设；未把相关性当作根因结论。
- [x] Test9.1：构建并离线验证 Test9w1；只对锁定 SHA-256 的 `aic8800_fdrv.ko` 在偏移 `0x2949` 执行 `01→00`，完整 AVB、ext4、super、IMAGEWTY 和 20 项单元测试通过。
- [ ] Test9.1：刷入 Test9w1，确认启动后、开关 Wi‑Fi 后、重启后 `ant_div` 均为 `N`；目标 SSID 至少 4/5 轮在 30 秒内出现，没有连续零结果或约 30 dB RSSI 双峰。
- [ ] Test9.1：确认重启自动重连、互联网/TCP ADB稳定，且蓝牙保持 `ON`、可扫描、`Bluetooth crashed 0 times`；任一关键项失败即刷回 Test8r2。
- [ ] Test9.2：只读审计 TV remote 接收服务、mDNS/局域网发现与监听端口，验证 iPhone 官方 Google TV 应用的发现、配对和文字输入。
- [ ] Test9.2：若官方接收端缺失，评估可追溯的开源局域网输入方案；先作为 data app 测试，蓝牙键盘作为已验证硬件回退。
- [ ] Test9.3：提供 SmartTube、Kodi、Jellyfin、Moonlight 的用户态配置安装脚本，选择 AirPlay 接收器和现代文件管理器，完成最终验证。
- [ ] M8：取得匹配的 64 位 BSP 和合法、成套的 Google TV 组件后，再处理 arm64/multilib、TV Play Store、认证与设备身份；当前不修改 fingerprint。
- [ ] 分析 AwTvProvision、SettingsSetup、AwManager、PackageOverride；只保留确有硬件/平台职责者。
- [ ] 保留 AOSP `ProxyHandler`、`VpnDialogs`，除非实机证据证明它们参与厂商网络干预。

## 后续准备

- 需要确定现代文件管理器和 AirPlay 接收器的可追溯 APK 来源、版本与许可证。
- SmartTube 曾发生构建环境/签名密钥事件，纳入固件前必须单独核对当前官方稳定版和签名；不得使用随机 APK 镜像站。
- 待下载的原始 APK 统一放入 `work/preinstall_apks/incoming/`，保留原文件名和来源 URL。
- Kodi 21.3、Jellyfin TV 0.19.9、Moonlight 12.1 和 SmartTube 32.03 Beta 均已匹配官方发布；最终通过配置脚本安装，不固化进 system/product。
- USB ADB 无枚举，但 TCP ADB 已验证可用；默认连接 `192.168.1.5:7896`。
