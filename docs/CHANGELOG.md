# 变更日志

## 2026-07-29

- M7 正式完成：Projectivy 中五项新应用的实体遥控和焦点通过，SmartTube
  1080p、AnExplorer 内置存储/USB/APK、AirReceiverLite iPhone 镜像/音频/
  同步通过；Kodi/Jellyfin/Moonlight 的外部资源缺口以有限豁免记录。
- 发布入口补齐 `configs/releases/m7.json` 和 `M7_RELEASE_GUIDE.md`；
  `--guided-after-flash` 会下载并严格校验缺失 APK，打开 Play 页面等待用户
  登录、跳过付款方式并安装 Lite，再统一安装五项应用。
- 设备已从 Test9r2 刷回 Test8r2；自动复核 SDK 31/ARMv7、television、
  Projectivy HOME、ContactsProvider、Play Store 29.2.15、5 GHz Wi‑Fi 6/
  公网和蓝牙，确认 leanback/Remote Service 均已退出。
- 新增 `test9.3-userdata-apps.json` 与 `install-userdata-apps.py`：锁定
  SmartTube 32.03、Kodi 21.3、Jellyfin TV 0.19.9、Moonlight 12.1 和
  AnExplorer TV 6.0.5 的官方来源、许可证、版本、ABI、大小、SHA-256 与
  signer certificate；安装前 fail-closed 验证 Test8r2 合同。
- 五项 APK 本地校验和首次 userdata 安装全部通过；均可解析
  LEANBACK_LAUNCHER 并进入主 activity。真实系统重启后五项仍可启动，
  安装器再次运行全部返回 `already-current`，未见 AndroidRuntime crash，
  Projectivy/Wi‑Fi/蓝牙/Play Store 无自动化回归。
- AnExplorer TV 的官方页面版本标签落后于实际 APK，故锁定官方 data repo
  不可变 commit；实体遥控、内置存储、USB 与本地 APK 路径已通过并最终采用。
  AirReceiverLite 作为需前台、部分功能每次限 5 分钟的按需能力保留；
  用户不购买完整版，不导出或再分发商业 APK。
- AirReceiverLite 5.1.7 已从 Play 安装并通过 iPhone 发现、498×1080 镜像、
  HDMI 音频和同步实测；mDNS `_airplay._tcp.local` 与 7000/7100 可达。
  真实重启确认 Lite 不自动恢复服务，其弹窗明确要求前台且部分功能每次限
  5 分钟；结果记为 `AIRPLAY-TRIAL-PASS`。用户接受该有限范围，完整版后台/
  开机门不再属于 M7。
- 完成 Test9r2 真机分层采证：system_ext RRO lookup、framework provider 和
  shared library 均正常；初始 Remote Service 因缺少运行时
  `BLUETOOTH_CONNECT` 在 `getBondedDevices/getAddress` 处崩溃，主进程退出且
  6466/6467 不监听。
- 仅在 userdata 临时授予 `BLUETOOTH_CONNECT` 后，Remote Service 稳定运行、
  6466/6467 监听、`_androidtvremote2._tcp` 以 `Pixel 3` 名称发布；SCAN 和
  ADVERTISE 保持未授予。官方 Google TV iPhone 客户端完成 TLS 配对、遥控和
  文字输入，framework 建立 virtual-remote/uinput 设备。
- 将 Test9r2 分类为 `R2-REMOTE-PASS`、整机总体 `PARTIAL`：Play Store 仍进入
  `AccessRestrictedActivity`，Remote Service 的 Store “missing”/Google API
  警告虽不阻塞本地遥控，却证明产品组件不一致。选择 S3，结束当前 32 位
  remote 候选，不制作 Test9r3/Test10p1；Test8r2 保持唯一稳定基线，官方
  手机遥控和 TV GMS 分别转入 M8.INPUT/M8.GMS。
- 吸收 `UBOX10_TV_GMS_REMOTE_CODEX_HANDOFF.md` 中的后续调研并逐项核验参考项目；新增 TV GMS/Remote 研究索引，记录 AOSP ATV、MindTheGapps TV、Python/Swift Remote v2 客户端与 ADB/Web remote 的用途、许可证、限制和安全边界。
- Test9r2 后新增强制证据门：先分层记录 RRO、framework、receiver、mDNS/iPhone 与 Play/GMS，再在 S1/Test9r3、S2/Test10p1、S3/结束 32 位 remote 中只选一条；路线决策前不制作下一镜像。
- 明确 MindTheGapps TV 当前可见分支比 Android 12 更新，只用于组件、权限、overlay 和打包结构参考，不作为已验证 Android 12 ARM32 donor；独立 Remote v2 客户端只作诊断，不替代电视 receiver 或官方 Google TV iOS 验收。
- M8 重排为 M8.0 共享证据门、M8A ARM32 真 AOSP ATV product、M8B AArch64/multilib；M8.GMS、M8.INPUT 与 M8.DRM 改为横向独立门禁。旧 M8.1–M8.6 编号保留映射用于历史追溯。
- 将 ADB/Web remote 记为末级隔离参考；默认 LAN 可达 HTTP、raw shell、ADB key 与 ASCII 输入模型不满足当前配对认证、Unicode、最小权限和攻击面要求。
- Test9r1 真机确认 feature、`com.android.media.tv.remoteprovider` shared library、Remote Service 5.2.473254133 和 privileged permissions 已加载，但 `/system/overlay` 中的静态 RRO 未被 Package Manager 注册；framework lookup 为空，`TvRemoteProviderWatcher` 持续拒绝未配置/白名单化的 provider，6466/6467 未监听，iPhone 无法发现电视。
- Test9r1 上的 Play Store 29.2.15 同时确认失效：package/Launcher 入口存在，但启动进入 `com.google.android.finsky.accessrestricted.AccessRestrictedActivity`；Remote Service 多次报告 Play Store “missing”。因此不改变 leanback/Google stack 的 Test9r2 只作 remote 分层探针，即使 remote 成功也不能晋级。
- 启动日志显示该固件扫描 `/system/system_ext/overlay` 和 `/product/overlay`，且明确报告前者为空；据此从 Test8r2 创建 Test9r2，只把同一 RRO 移至 `/system/system_ext/overlay`，不改变 remoteprovider、权限、donor、feature 或 `vendor_dlkm`。
- Test9r2 的 25 项单元测试套件、ext4/e2fsck、完整 AVB、super、IMAGEWTY 10 分区校验全部 PASS；固件大小 2,005,946,368 bytes，SHA-256 `27B54FB83E96D3863FAE2EF2718E8EC9ADDD863E5ED123082D5E6C8CA6FFFD52`，等待真机验证 RRO 注册/lookup 后再测试 iPhone。
- 删除 Test9r1 失败镜像、Test9r2 中间镜像和一次超时探针留下的重复临时分区，共 7,404,837,598 bytes；保留配置、日志和清单。四个官方逻辑分区缓存合计 1,888,006,144 bytes，按用户指令改为长期保留，不再为节省空间重复删除。

## 2026-07-28

- 完成 Test9w1 真机收束：`ant_div=N`，5 GHz 网络稳定、目标 2.4 GHz SSID 仍未出现，蓝牙 `ON` 且崩溃 0 次；没有证据证明补丁实质改善，实验退役，后续恢复从 Test8r2 构筑。
- 审计当前 Android 12 TV remote 路径：framework 已含 `TvRemoteService`、provider watcher、Binder API 与 uinput bridge，但缺少 leanback、`com.android.media.tv.remoteprovider` shared library、provider package RRO、privapp policy 和接收端 APK。
- 锁定 Android TV Remote Service 5.2.473254133（APK SHA-256 `9D1B...B973`、Google 证书 SHA-256 `456E...9137`）；普通 data 安装实测因 required shared library 缺失而失败，未在设备留下 package。
- 新增 `prepare-tv-remote-experiment.py`：验证本地 donor 与两份 Android 12 AOSP source archive，从源码可复现构建只含 `TvRemoteProvider*` 的 runtime DEX，并构建/签名只覆盖 `config_tvRemoteServicePackage` 的静态 RRO；Google APK 和生成二进制均留在忽略的 `work/`。
- 候选构建器新增严格白名单的 `/system/priv-app`、remoteprovider framework jar 与单一 RRO 注入，支持安全创建缺失父目录并验证目录/file mode、UID/GID、SELinux 和 SHA-256；单元测试套件增至 24 项。
- 从 Test8r2 构建 Test9r1，未继承 Test9w1 vendor patch；system 只有 10 个预期新增路径，`vendor_dlkm` 与官方输入相同。ext4、完整 AVB、super、IMAGEWTY 和单元测试全部通过，固件 SHA-256 为 `38A0C232750ECD433B2783E0CFBFFC48C17071226EE2AEC978BE5AC6C12F6E33`。
- 将官方 Google TV iPhone 发现、配对、遥控和文字输入加入 M8.INPUT 正式验收；明确不开发 UBOX Input，Google 专有 APK 不进入 Git/公开镜像/项目再分发，许可或认证不可得时标记 `BLOCKED`。
- 镜像保留集切换为官方原件、Test8r2 和 Test9r1；删除 Test9w1、Test9r1 构建中间分区、本轮官方逻辑分区缓存和分析日志共 7,651,182,014 bytes（约 7.126 GiB），当前恰有三份 `.img`，三者 SHA-256 已复核。
- 吸收 UBOX10 AArch64/AOSP ATV/Netflix 调研，建立 M8.0–M8.6 与 M8.DRM 分阶段计划；首选 arm64+arm32 multilib，64 位 Mali/Gralloc/Mapper/HWC 是第一 Go/No-Go。
- 核实 BPI H618 Android 12 BSP 和 AOSP `device/google/atv` 研究入口；明确 H618 `-a arm64` 不能替代 userspace/ELF/图形产物验证，且其他板型底层与安全材料不得直接移植。
- 将 Netflix 提升为 N0–N3 正式验收：先建立原厂/Test8r2 的 Widevine、TEE/OEMCrypto、secure codec、protected buffer、HDCP 和实际播放基线，不复制密钥或伪造认证。
- 新增 M8 架构计划、研究索引、当前构建环境、存储/复现策略和核心文档索引；M8.0 可与 Test9w1 刷测只读并行，大型源码下载与 64 位候选尚未启动。
- 新增 `prepare-candidate-inputs.py`：从 SHA-256 锁定的官方 IMAGEWTY 原件恢复并验证容器提取物、四个逻辑分区和语义清单，为删除可再生成镜像提供复现门。
- 将完成使命的 M6 与主机配置文档移入 `docs/archive/`；根 README 改为当前状态、三镜像保留集和复现入口。
- 完成历史产物清理：`.img` 从 149 份降到官方原件、Test8r2 和 Test9w1 共 3 份；连同旧候选、中间分区和解包树释放约 81.604 GiB，当前工作区约 8.185 GiB。
- 在删除官方逻辑分区缓存后实际运行恢复脚本，四个分区均重建成功并命中锁定 SHA-256；随后再次删除缓存，只保留可复现方法和三份可刷写镜像。
- 完成 Test8r2 Wi‑Fi 扫描专项采证：连接链路强且稳定，五轮主动扫描都能完成；历史全频扫描记录却存在连续 `0 results`，目标扫描 RSSI 在约 `-46/-47 dBm` 与 `-75 dBm` 间双峰跳变。
- 排除 TV Settings 应用扫描节流与 `wificond` 崩溃作为首要原因；记录 AIC vendor HAL background scan/link-layer stats `ERROR_UNKNOWN`、无 scheduled scan，以及 2022 年 AIC8800D 驱动/固件栈。
- 用户确认无线模块丝印为 `AW869A WiFi6`；官方规格为 AIC8800D40、1T1R、单天线型，而设备运行时 `aic8800_fdrv` 默认 `ant_div=Y`，据此建立可证伪的天线分集假设。
- 候选构建器新增严格受限的 vendor_dlkm 模块二进制补丁：校验官方来源哈希、路径、偏移和原字节，恢复 mode/UID/GID/SELinux，并验证仅配置内模块内容变化。
- 生成 Test9w1：仅将 `aic8800_fdrv.ko` 偏移 `0x2949` 的默认值由 `01` 改为 `00`；20 项单元测试、ext4、完整 AVB 链、super 和 IMAGEWTY 全部通过，固件 SHA-256 为 `2D43D4A6B64702F1D0265EDC27B33EB424B4B56A721DC8068B5CCEBB4A310CC5`。
- Test9w1 重建的 vendor_dlkm 保留 dm-verity、明确关闭 FEC，因为本地没有可信 `fec` 生成器；候选保持实验状态，Test8r2 仍是稳定回退点，待真机完成扫描、模块重载、重启和蓝牙回归。

## 2026-07-27

- Test8r2 已通过 PhoenixCard 真机刷测：设备直接进入 Projectivy，默认英语，红外遥控、Settings 正常，Wi‑Fi 可连接。
- ADB 确认 ContactsProvider 来自 `/system/priv-app/ContactsProvider/ContactsProvider.apk`；蓝牙保持 `state: ON`、`Bluetooth crashed 0 times` 并可扫描。
- ADB 确认 X12、settingwizard 和 HappyCast 三个厂商包均不存在。Test8 因蓝牙回归淘汰，Test8r2 成为当前稳定基线。
- 构建器新增受限的 `/system/etc/permissions/*.xml` 文件注入、SHA-256/元数据/SELinux/语义差异验证；IMAGEWTY checksum 改为 16 MiB 分块计算，避免整镜像 unpack 导致内存不足，并增加回归测试。
- 构建并离线验证 Test9a/Test9b，分别加入 Leanback 和 Leanback-only feature；两者真机 Play Store 均提示版本不兼容，明确标记为失败诊断候选。
- Google 账户登录、GSF check-in 和 Jellyfin TV 安装已验证；当前 Play Store 仍为手机式、首页加载失败且没有可见的 Play Protect certification 项。TV Play Store 与 64 位系统合并为未来平台目标。
- 修正 Wi‑Fi 状态描述：连接后互联网/TCP ADB 可用，但目标 SSID 扫描随机，进入 Test9.1 专项采证。
- 新增产品化路线图：Wi‑Fi 扫描可靠性优先，随后验证 iPhone 官方 Google TV 遥控文字输入，再完成应用、AirPlay 和文件管理收尾。

## 2026-07-26

- 测试版 2 实机通过：Android、Settings、红外遥控、HDMI 音视频、Wi‑Fi 和 bilibili API 正常；ADB 确认五个目标包均已删除。
- Wi‑Fi ADB 地址确认为 `192.168.1.5:7896`；此前 Ethernet 地址失联源于网线被拔除，并非 adbd 不稳定。
- ADB 发现厂商浏览器和 H618 Upgrade 拥有安装软件包、写安全设置、重启及 Recovery 等高权限；Test3 确定删除浏览器、H618 Upgrade 和 Softwinner Update。
- Test3 构建完成；40 个预期路径删除、完整 AVB 启动链和 IMAGEWTY 载荷验证通过。镜像 SHA-256 为 `8E42CB38426E3E80359BA5F2A9A0A21368789B43BF6B8DD86DF2D67630E44B77`。
- Test3 实机通过：Android、Settings、遥控、HDMI 和 Wi‑Fi 正常；ADB 确认三个目标包消失且 Chrome 保留。
- Test4 确定批量删除八个不常驻的旧媒体、文件管理和输入应用；默认 LatinIME 和硬件媒体栈保留。
- Test4 构建完成；95 个预期路径删除、完整 AVB 启动链和 IMAGEWTY 载荷验证通过。镜像 SHA-256 为 `639403FDDB95439401FFC929764E549CA49A7AD4F5BF92DD232FF6955A50CE73`。
- Test4 实机包验证通过，默认 LatinIME 正常；`com.android.musicfx` 确认为独立音效服务，不是已删除 Music 应用的残留。
- Test5 确定批量删除 17 个电话、NFC、打印、CTS、企业管理、本地备份和 DSU 组件；ADB 已确认对应硬件/功能未启用。
- Test5 构建完成；累计 199 个预期路径删除、完整 AVB 启动链和 IMAGEWTY 载荷验证通过。镜像 SHA-256 为 `16332D8E6BC14FA8D5855383BD3C9248D7A374E81A4967DC471B3C6E610F472F`。
- Test5 实机包验证通过：17 个目标包均消失，Google Play、GMS、蓝牙、TV Settings 和 MusicFX 均保留。
- 确定后续四批路线；Test6 作为最后一批纯删除，新增清理 16 个旧个人设备 UI、壁纸/屏保、联系人/日历和非目标组件。
- Test6 构建完成；累计 295 个预期路径删除、完整 AVB 启动链和 IMAGEWTY 载荷验证通过。镜像 SHA-256 为 `D8AA71730952F4388D82E6B919E05B757C50CD3D74805351546566D62125A576`。
- Test6 实机通过：16 个目标包消失，六个关键电视包保留；纯删除阶段结束。
- 项目目标修正为现代遥控器电视体验、影音流畅和开放扩展，不再以机械减少包或进程为目标。
- 将候选构建流程改为 `scripts/build-candidate-firmware.py --config ...`，Test1/Test2 的删除项由 JSON 配置描述。
- 生成测试版 2：累计移除 UBTunnel 和五个工厂测试/日志工具；ext4 语义差异、完整 AVB 启动链及 IMAGEWTY 载荷验证全部通过。
- 测试版 2 镜像为 `out/candidates/test2-remove-factory-tools-r1/x12-test2-remove-factory-tools.img`，刷机校验 SHA-256 为 `4789EB9F76FD98E09D4155E95235CD06E38A9AE15E5A7BC7BF5B9F7D2224C964`。
- 测试版 1 已实机启动；主界面、设置、红外遥控、HDMI 音视频、Wi‑Fi 与目标网站通过。
- 归档量产 UART 粘贴记录；约 305 秒输出 `CARD OK`、`sprite success`。
- UART 采集器 schema 升级到 v2，支持按 `Ctrl+C` 或 `Q` 安全停止并保存终止原因、raw、文本和元数据。
- UART 普通采集不再默认生成 SHA-256；仅显式使用 `-GenerateChecksums` 时生成。
- 以太网、蓝牙扫描和高码率视频通过；CEC、BBLL 按当前需求跳过。
- Android USB debugging 开启后仍无 USB 枚举；离线确认固件预设 TCP ADB 端口为 `7896`。
- 局域网 ADB 通过 `192.168.1.8:7896` 建立；运行时确认 123 个包、UBTunnel 缺失、SELinux Permissive 和厂商 Launcher 强制属性。
- 两次 positive ext4 fixture 均通过且 SHA-256 相同：`6CA8B1E2B64690B480ECF45DF6B0F2C1270658E39FBFB2265E872A38B82AB1EA`。
- 完成独立 ext4 解析器并读取官方 `system_a` 的 3857 条语义清单。
- 测试版 1 仅删除 `/system/app/UBTunnel.6`；AVB、super、ext4 和 IMAGEWTY 离线验证全部通过。
- 生成 `out/candidates/test1-no-ubtunnel-r3/x12-test1-no-ubtunnel.img`，SHA-256：`3B8F8981E94B9BF209763FE3B67EC7102616B6D42631AA7F93264885C852C776`。
- 项目文档改为简洁状态模式；旧 M6 材料降为历史参考。
- Projectivy 4.71 用户态预检通过并接管 Home；记录轻微卡顿，进入 Test7 集成准备。
- 确认设备为 ARM64 内核加纯 32 位 Android 用户空间；决定当前主线不迁移 arm64。
- 验收 Kodi 21.3、Jellyfin TV 0.19.9、Moonlight 12.1 和 SmartTube 32.03 Beta 官方 APK，改为最终配置脚本安装。
- 扩展候选构建器以校验并注入 system APK、修改现有 system 属性，同时恢复 UID/GID/mode 和 SELinux 标签。
- 生成 Test7：Projectivy 4.71 注入 `/system/app`，默认 Launcher 属性改为 Projectivy，X12 保留；完整离线验证通过。
- Test7 实机通过；Projectivy system app、默认 HOME、遥控和应用启动正常。记录双 Launcher 首次选择框及默认繁体中文，转入 Test8。
- 将最终目标补充为在稳定性和驱动兼容允许时充分利用 CPU/GPU/硬解/内存/存储；arm64/multilib 作为独立扩展项目，不阻塞当前 32 位净化主线。
- Test8 删除 X12、settingwizard 和 HappyCast，将默认语言设为英语并关闭 HDMI 菜单语言覆盖。
- Test8 离线验证通过：仅 59 个预期路径新增删除、共同文件仅 `build.prop` 变化，ext4、完整 AVB 链、super 和 IMAGEWTY 均通过。
- 确认 system 使用 Google Pixel 3 `blueline` 身份属性并以 `model2/brand2` 保存真实 X12/Unblocktech 信息；为避免破坏 Google Play，暂不随 Test8 修改。
- Test8 实机大部分通过，但蓝牙开启约一秒后自动关闭；将 Test8 标记为有回归并开始诊断，其他功能不重复回归。
- ADB 定位蓝牙回归为 `BluetoothPbapService` 缺少 `com.android.contacts` provider；决定恢复 Test6 误删的 AOSP ContactsProvider。
- 临时安装官方 ContactsProvider APK 后蓝牙保持开启并扫描，因果验证通过；数据分区实验包随即卸载，修订固件将恢复 APK/ODEX/VDEX 完整目录。
- 构建器改为 WSL 前置检查、事务式输出和内置自动验证；新增已知 ContactsProvider/Bluetooth 依赖拒绝、失败清理及 Windows ACL 继承测试。
- Test8r2 恢复 ContactsProvider 完整目录并在一次构建中通过当时的 13 项单元测试、ext4、完整 AVB、super 和 IMAGEWTY 验证；ACL 修复测试加入后当前共 14 项单元测试通过。

## 2026-07-25

- UART COM3、115200 8N1 被动接收成功，日志位于 `logs/device/20260725-004019/`。
- 配置 WSL2 Ubuntu 24.04 和私有 e2fsprogs 1.47.2 工具链。
- 确认旧候选 `system_a` 根层级错误，旧 boot/vendor_boot 含调试修改，全部停止使用。

## 2026-07-22

- Windows WinUSB 接口 GUID 修正后，Fastboot 识别序列号 `992304568773`。
- `fastboot getvar version` 返回 `0.5`；常见 A/B 槽位变量不受支持。

## 2026-07-19 至 2026-07-20

- 建立官方 `x12-1024.img` 基线并完成 IMAGEWTY、dynamic super、boot 和 AVB 初步解析。
- 修正 `pack_image.py` 的 IMAGEWTY 对齐后，PhoenixCard 可完成 100% 写卡。
