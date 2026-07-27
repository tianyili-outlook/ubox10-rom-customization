# 关键技术决策

## 当前有效

- **官方镜像永不覆盖**：`x12-1024.img` 是统一恢复入口，所有候选使用新文件名。
- **采用可恢复的快速实机迭代**：离线完成路径、原件和恢复方式检查后直接刷测；启动失败就刷回官方镜像。
- **先直接编辑 ext4，不做全量重建**：测试版 1 用 `debugfs` 删除 UBTunnel，最大限度保留官方文件系统语义。
- **首个候选只删除 UBTunnel**：这是最小且与网络问题直接相关的变量；官方 Launcher 和全部硬件分区保持不变。
- **暂不删除 ProxyHandler/VpnDialogs**：它们是 AOSP 系统组件，不是仅凭名称即可判定的 UnblockTech 定制。
- **AVB 保持开启并重新签名**：不使用禁用校验 flags；测试密钥能否被本机启动链接受由 UART 实机结果决定。
- **应用和硬件分批回归**：每次只删除一组明确目标，启动后测试网络和硬件，避免一次改动过多导致无法定位。
- **文档保持简洁**：主入口只保留当前事实、决定、阻塞和下一步；旧 M6 文档仅作历史参考。
- **测试版 1 作为新的可启动净化基线**：后续候选从相同官方分区直接修改路线继续，不再回到旧 `work/` 全量重建流程。
- **测试与完整性检查按实际风险选择**：只测本次变更最可能影响的项目；普通日志和中间产物不生成哈希，刷机镜像与长期保存原件除外。
- **ADB 优先使用厂商预设 TCP 端口 7896**：Android USB 完全未枚举，而官方 boot 已明确配置网络端口；只有 TCP ADB 也失败时才采集短 UART 诊断。
- **测试版 2 只增加五个低风险删除项**：DragonAtt、DragonBox、DragonAgingTV、Factory_detection、AwlogSettings；保留 Launcher、投屏、蓝牙配对、LED 和 OTA 组件。
- **候选构建改为配置驱动**：统一使用 `scripts/build-candidate-firmware.py --config configs/candidates/<候选>.json`，避免为每批删除复制一套脚本。
- **候选构建从 Windows PowerShell 启动**：Windows Python 负责 `lpmake.exe` 和 IMAGEWTY，脚本内部再调用 WSL ext4 工具；不要从 WSL 直接启动构建器。
- **网络测试按变更范围执行**：普通应用删除不再重复测试 bilibili API；只有修改网络服务、代理、VPN、DNS、证书或相关 framework 配置时才复测。
- **测试版 3 删除厂商浏览器和两个更新应用**：删除 `browser-v1.1`、`H618_UpgradeV3`、`Update`；Chrome 可替代浏览器，固件恢复继续使用 PhoenixCard 官方镜像。
- **按证据处理厂商组件**：settingwizard 曾暂留到 Test7，确认不是硬件依赖后已随 Test8 删除；BLEAutoPair、NanoOtaBle 和 LED 仍可能参与遥控器配对或硬件状态，在取得依赖证据前继续保留。
- **Test4 扩大可替代用户应用批次**：在保持每个删除根目录可追踪的前提下，可以一次移除一组播放器、图库、音乐、文件管理器和未使用输入法，不再按单个 APK 刷机。
- **Test4 删除八个旧用户应用目录**：CZFileManager、Zhuyin、GalleryTV、Music、VideoPlayer、TvdVideo、TvdFileManager、ImageParser；保留 Chrome 和默认 LatinIME，后续由 Kodi/Jellyfin 等目标应用接替媒体功能。
- **包验证使用精确行匹配**：检查删除结果时在包名后使用 `$`，避免 `com.android.music` 错误匹配 `com.android.musicfx`。
- **Test5 批量删除 17 个非电视平台应用**：包括电话/NFC/打印、CTS shim、ManagedProvisioning、EasterEgg、本地备份确认和 DSU；保留 Google Play、MusicFX、蓝牙、相机扩展与电视核心组件。
- **Test6 作为最后一批纯删除**：新增删除 16 个旧个人设备 UI、壁纸/屏保工具、联系人/日历、相机扩展、蓝牙 MIDI、定时开关和厂商截图组件；之后不再继续无目标地精简 AOSP 核心。
- **Test8 集中清理厂商界面**：删除 X12、settingwizard 和 HappyCast，固定 `en-US` 默认语言；标准 Settings、BLEAutoPair/NanoOtaBle 和 Miracast 保留，AirPlay 后续以可更新应用补回。
- **Test8 不修改 Google `blueline` 身份属性**：这些属性可能维持现有 GMS/Play 认证；清除厂商品牌不应以失去 Google Play 或 TV 应用兼容为代价，留到 Test9 单独实验。
- **恢复 AOSP ContactsProvider**：Android 12 的 Bluetooth PBAP 对 `com.android.contacts` provider 有硬依赖；它没有必要的用户界面，但属于蓝牙兼容基础设施，不能按“电视不需要联系人”删除。
- **候选采用事务式构建并自动验收**：WSL 前置检查在复制大文件前完成；候选只在 ext4 语义、只读 e2fsck、完整 AVB、super、IMAGEWTY 和单元测试全部通过后发布，失败临时目录自动清理。
- **优化目标是电视体验而非最少进程**：保留对遥控、影音、Google Play、APK 安装、ADB、USB/文件访问或兼容性有价值的组件。
- **补回现代文件管理能力**：旧文件管理器已删除；最终固件应预装或明确提供一个遥控器友好的现代文件管理器，确保 USB 浏览和本地 APK 安装方便。
- **第三方 APK 二进制不提交公共仓库**：仓库记录官方来源、版本、包名和下载校验；APK 保存在已忽略的 `work/preinstall_apks/`，构建时本地注入。
- **Projectivy 先作为用户应用试跑**：4.71 用户态和 Test7 system app 均已实机通过；Test8 因此删除 X12。
- **保留当前 32 位 Android 用户空间**：H616 和内核支持 64 位，但 system/vendor 只有 32 位运行库和硬件栈；没有匹配的 64 位 BSP/厂商二进制时不迁移 arm64。
- **大型目标应用使用配置脚本安装**：Kodi、Jellyfin、Moonlight、SmartTube 不固化进只读分区，便于更新和替换；Projectivy 仍在 Test7 注入固件。
- **Test7 将 Projectivy 注入 `/system/app`**：沿用已验证的 system ext4 修改链，并替换厂商已有的两项默认 Launcher 属性；X12 仅在 Test7 保留作回退。
- **Test9a/Test9b 只作为失败诊断实验保留**：加入 Leanback/Leanback-only feature 后，Play Store 仍拒绝当前设备组合；配置和通用文件注入能力用于复现证据，但镜像不作为部署基线。
- **当前阶段不再修补 Play Store APK**：保留现有 Google 服务用于登录、搜索、安装和更新；电视版 Play Store、Play Protect/认证、设备身份一致性与 64 位 BSP 合并到未来平台阶段。
- **Test9 先网络后手机输入**：Wi‑Fi 扫描可靠性是当前最高优先级；iPhone 官方 Google TV 遥控依赖同一 Wi‑Fi，因此只有网络稳定后才进入配对和文字输入验收。
- **iPhone 输入采用官方方案优先、局域网最小权限**：先验证系统是否有兼容 TV Remote 接收端；缺失时不移植 Google 专有组件，优先评估可追溯、开源、无需云端的 data app，蓝牙键盘作为回退。
- **Wi‑Fi 先采证再改固件**：连接与传输已通过，但扫描不可靠；先比较 Settings、shell 扫描和 Wi‑Fi 栈日志，不在无根因时修改 vendor/HAL 或路由器。

## 后续再决定

- 若未来取得同板型完整 64 位 BSP/固件，再单独评估 arm64/multilib 分支；不与当前净化主线混做。
- 未来 64 位平台所使用的合法、成套 Google TV 服务和 TV Play Store 方案。
- AirPlay 接收器和现代文件管理器的最终选择。
- AwTvProvision、SettingsSetup、AwManager、PackageOverride 是否有继续清理价值。
