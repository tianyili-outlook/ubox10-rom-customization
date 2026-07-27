# 变更日志

## 2026-07-28

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
