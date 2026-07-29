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
- **Test9.3 安装器必须同时锁 APK 内容和签名身份**：配置记录 bytes、
  SHA-256、package/version/SDK/ABI/launch activity 与 signer certificate；
  脚本还验证 Test8r2 baseline contract 和设备端 `base.apk` SHA-256，任何
  一项不符即停止，不以文件名、版本号或“安装成功”代替来源验证。
- **Test9.3 五项保持 userdata 应用**：SmartTube、Kodi、Jellyfin TV、
  Moonlight 和 AnExplorer 不进入 system/product；刷机后用同一幂等脚本恢复，
  版本已相同时跳过，发现更高版本时拒绝静默降级。
- **SmartTube 在 Test9.3 冻结 32.03**：官方 beta 为推荐 channel，但本轮不
  追逐刚出现的 32.10；先用已核验 release asset/签名完成整体验收，再把 updater
  升级作为单变量测试。
- **AnExplorer TV 作为 M7 文件管理器采用**：官方 TV 专版的 D-pad、内置
  存储、USB 与 APK 路径通过，APK 来源锁到不可变官方 commit。免费版广告和
  Pro 网络功能不是 M7 承诺，不再转测 X-plore。
- **AirPlay 先走合法免费验证路径**：从 Play Store 安装 AirReceiverLite
  验证 iPhone 协议和性能，不导出、不修改或重打包专有 APK。2026-07-29
  已通过发现、镜像、HDMI 音频和同步；最终产品范围由下一项决定。
- **M7 接受 AirReceiverLite 的有限产品范围并完成**：用户不把购买完整版
  纳入项目；Lite 作为需前台启动、部分功能每次限 5 分钟的按需能力保留，
  后台/开机自启不再是 M7 门禁，也不转测 AirScreen。
- **Kodi/Jellyfin/Moonlight 使用资源型有限豁免关闭 M7**：三者的界面、
  D-pad 和连接/发现边界通过，但缺少本地媒体、Jellyfin 服务器和 Sunshine
  主机。该缺口不写成端到端 PASS；未来可非阻塞补测，不重新开启 M7。
- **Test7 将 Projectivy 注入 `/system/app`**：沿用已验证的 system ext4 修改链，并替换厂商已有的两项默认 Launcher 属性；X12 仅在 Test7 保留作回退。
- **Test9a/Test9b 只作为失败诊断实验保留**：加入 Leanback/Leanback-only feature 后，Play Store 仍拒绝当前设备组合；配置和通用文件注入能力用于复现证据，但镜像不作为部署基线。
- **当前阶段不再修补 Play Store APK**：保留现有 Google 服务用于登录、搜索、安装和更新；电视版 Play Store、Play Protect/认证、设备身份一致性与 64 位 BSP 合并到未来平台阶段。
- **Wi‑Fi 专项收束后进入官方手机遥控**：5 GHz 连接、互联网和 TCP ADB 已满足同 LAN 前提；2.4 GHz SSID 缺失不再阻塞产品主线，下一变量是 Test9r1。
- **手机输入目标固定为官方 Google TV iPhone 应用**：不考虑、自研或维护 UBOX Input。蓝牙键盘只是人工回退，不计为项目目标完成。
- **允许做本地、不可再分发的 Google Remote Service 兼容实验**：只接受版本、哈希和 Google 签名证书锁定的原始 APK；它保存在已忽略的 `work/`，不进入 Git、公共镜像或项目下载。仓库只提交 AOSP 源码构建脚本、配置、哈希和非专有 XML/RRO source。
- **Remote 输入走 framework provider bridge**：从 Android 12 AOSP 构建 `com.android.media.tv.remoteprovider`，由 RRO 指定 provider package；纯 signature 的 `INJECT_EVENTS` 不伪授予，事件必须经过 `TvRemoteProvider`/uinput。
- **Test9r1 必须从 Test8r2 单变量构筑**：不继承 Test9w1 的 driver patch 或无 FEC vendor_dlkm；只新增 remote stack 所需 system 路径。
- **Test9r1 因 RRO 预置路径错误退役**：真机已证明 APK、shared library 和权限加载，但 `/system/overlay` 不进入该固件的 Package Manager overlay 扫描，provider 未获 framework package allowlist。保留配置/日志，删除镜像。
- **Test9r2 只修正 RRO 扫描路径**：仍从 Test8r2 构筑，同一 RRO 移到启动日志明确扫描的 `/system/system_ext/overlay`；在 RRO package、lookup 和 watcher 通过前，不混入蓝牙运行时授权或 mDNS 改动。
- **Test9r2 只作一次性 remote 技术探针**：Test9r1 已确认 Play Store 进入 `AccessRestrictedActivity`，且 Remote Service 报告 Store “missing”；Test9r2 保留相同 leanback/Google stack，故无论 remote 结果如何都不晋级，完成采证后回到 Test8r2。
- **Test9r2 remote 技术链判定为 PASS**：初始 receiver 因缺少 `BLUETOOTH_CONNECT` 崩溃；只在 userdata 临时授予该权限后，6466/6467、mDNS、官方 iPhone TLS 配对、遥控、文字输入和 framework uinput 全部工作。SCAN/ADVERTISE 未授予，不扩大权限。
- **选择 S3 收束当前 32 位 remote**：Test9r2 因 Play Store `AccessRestrictedActivity` 总体仍为 `PARTIAL`；不制作需要 framework startup gate 的 Test9r3，也不制作混装 TV Google 组件的 Test10p1。后续从 Test8r2 完成 Test9.3，remote 产品化转入 M8.INPUT。
- **Remote v2 开源客户端只作诊断**：`androidtvremote2` 和 `AndroidTVRemoteControl` 用于区分 receiver、协议、mDNS 与官方 iOS 客户端问题；它们不提供电视端 receiver，也不替代官方 Google TV 应用最终验收。
- **ADB/Web remote 不进入当前产品路线**：`Legvan/tv-remote` 只作为末级技术参考；默认 LAN 可达服务、raw shell、ADB key 和 ASCII 输入模型不符合当前配对认证、Unicode、最小权限与攻击面门槛。
- **Wi‑Fi 先采证再改固件**：连接与传输已通过，但扫描不可靠；先比较 Settings、shell 扫描和 Wi‑Fi 栈日志，不在无根因时修改 vendor/HAL 或路由器。
- **Test9w1 只检验 AW869A 天线分集假设**：在 Test8r2 的 system 内容不变前提下，只把已锁定来源哈希的 `aic8800_fdrv.ko` 默认 `ant_div` 字节由 `01` 改为 `00`；不替换未知版本的 AIC 驱动/固件，不修改 Wi‑Fi HAL，也不把推断写成已证实根因。
- **不在当前 TCP ADB 会话中热卸载 Wi‑Fi 模块**：控制链本身依赖 Wi‑Fi，热卸载可能同时失去诊断与恢复通道；参数持久性改由可刷回的 Test9w1 在启动、一次 Wi‑Fi 开关和重启后三次验证。
- **Test9w1 已退役**：真机 `ant_div=N` 但目标 2.4 GHz SSID 仍未出现，5 GHz 本来稳定，未证明实质改善；配置/哈希保留作证据，镜像删除，Test8r2 继续作为唯一稳定基线。
- **Test9w1 的 vendor_dlkm 暂不生成 FEC**：本地工具链没有可信 `fec` 生成器；候选保留 AVB/dm-verity 并在结果中显式标记 `vendor_dlkm_fec=disabled`。该镜像仅用于可恢复实验；若进入长期发布，需引入可追溯、可复现的 FEC 工具链，或单独记录并接受无 FEC 策略。
- **M8 先审计、后供体、再启动**：M8.0、M8A.1 与 M8B.1 只做 inventory、source-lock、原样供体构建和 AOSP ATV 差异；不在缺少依赖图时生成 UBOX10 迁移镜像。
- **M8 改为先产品、后架构**：M8.0 是共享证据门；M8A 保持当前 Kernel/vendor/32 位 ABI，先建立真正 Android 12 AOSP ATV product；M8B 只在 M8A 产品合同稳定且 64 位图形栈为 `GO` 后迁移 AArch64/multilib。旧 M8.1–M8.6 编号只用于历史追溯。
- **首选 arm64 + arm32 multilib**：目标是 64 位 Framework/ART/SurfaceFlinger，过渡期保留 arm32 secondary ABI；只有 Binder/VINTF/进程边界明确的 32 位 Vendor service 才可能暂留。
- **64 位图形栈是 M8B 第一 Go/No-Go**：没有匹配当前 H616 Kernel Mali ABI 的 64 位 EGL/Mali/Gralloc/Mapper/HWC，不进入 M8B.2 64 位 UI 候选；该阻塞不妨碍 M8A 先建立 ARM32 ATV product。
- **BPI H618 只是供体候选**：先锁定 commit 和大文件并原样构建；H618 `-a arm64`、README 或其他板型能启动均不能证明 UBOX10 可用。boot0/U-Boot/DDR/PMIC/完整 DTB/TEE/密钥/分区表永不直接移植。
- **真正 TV 化从 Android 12 ATV product 开始**：AOSP ATV 可自主完成；Google TV/GMS TV、TV Play Store 商业资格和 Play Protect 认证不能靠复制组件保证。
- **MindTheGapps TV 只作组件与集成结构参考**：当前可见分支比 Android 12 更新；在精确 Android 12 ARM32 版本、签名和依赖未锁定前，不把其中专有二进制当作 donor，也不因 proprietary file list 推定使用或再分发权。
- **M8.INPUT 继承 Test9r2 已验证合同，不继承实验二进制布局**：remoteprovider 从锁定 AOSP 源码构建，product 原生声明共享库/provider/实际生效的 overlay、最小 privapp policy 和默认 `BLUETOOTH_CONNECT`；用户本地提供官方原签名 APK。M8 补做开机自动启动、重启持久性和完整输入复验；若 GMS TV 许可、签名或认证构成外部阻塞，记为 `BLOCKED`，不把 UBOX Input 当作替代通过。
- **Netflix 采用 N0–N3 分级且不规避安全机制**：N1 是正式目标，N2 条件性，N3 机会型；Widevine L1 不等于 Netflix HD。不得复制密钥、证书、ESN、secure storage 或伪造认证。
- **M7 发布后只长期保留两份可刷写镜像**：官方恢复/来源原件与
  Test8r2；Test9r1/Test9r2 等历史探针只保留配置、生成脚本、固定哈希、
  实验文档与 Git 历史。官方原件不受“只保留当前候选”清理规则影响。
- **长期保留四个官方逻辑分区缓存**：`system_a/product_a/vendor_a/vendor_dlkm_a`
  已由官方原件重建并命中固定哈希；不再在候选构建后删除，避免后续每次重复
  提取。它们不是可刷写候选，不改变两份 IMAGEWTY 保留集。

## 后续再决定

- M8.0/M8A 是否能建立稳定 ATV 产品合同，以及 M8B.1 的 64 位 Mali/Gralloc/Mapper/HWC 证据能否放行 M8B.2。
- 原厂/Test8r2 的 Widevine、secure decoder、HDCP 和 Netflix 实际能力是否允许 N2/N3。
- AirPlay 接收器和现代文件管理器的最终选择。
- AwTvProvision、SettingsSetup、AwManager、PackageOverride 是否有继续清理价值。
