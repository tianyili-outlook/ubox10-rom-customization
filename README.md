# UBOX10 ROM Customization

面向 UnblockTech UBOX10（I12 Pro Max / Allwinner H616 / Android TV 12）的个人固件改造项目。目标是在保留 Wi‑Fi、蓝牙、以太网、HDMI/CEC、遥控器、音频和视频解码支持的前提下，逐步移除厂商软件与网络干预，最终制作干净的 Android TV 固件。

## 当前状态

- 官方 PhoenixCard 镜像 `x12-1024.img`、提取分区和 SHA-256 基线已保留，可随时刷回。
- Fastboot 只读通信可用：序列号 `992304568773`，协议版本 `0.5`。
- UART 只接收链路可用：COM3、115200 8N1；首份冷启动日志在 `logs/device/20260725-004019/`。
- WSL2 Ubuntu 24.04 与 e2fsprogs 1.47.2 已配置；两次 synthetic ext4 样本完全可复现。
- 独立 ext4 解析器可检查目录、文件、链接、UID/GID/mode、SELinux、capability 和 ACL。
- 官方 `system_a` 已提取并建立 3857 条语义清单。
- **测试版 1 已实机启动成功。** 主界面、设置、红外遥控、HDMI 音视频、Wi‑Fi、以太网、蓝牙扫描和高码率视频播放正常；Google、YouTube、`bilibili.com`、`api.bilibili.com` 均可访问。量产同时清除了 userdata/metadata，因此尚不能把网络改善完全归因于 UBTunnel。
- 测试版 1 的局域网 ADB 基线已取得：123 个包、UBTunnel 缺失、SELinux Permissive、厂商 Launcher 仍为 `com.moons.mylauncher10`。
- **测试版 2 已实机通过。** 它在测试版 1 基础上继续移除五个工厂测试/日志工具；Android、Settings、红外遥控、HDMI 音视频、Wi‑Fi 和 bilibili API 正常。
- 局域网 ADB 默认使用 Wi‑Fi 地址 `192.168.1.5:7896`；此前 `192.168.1.8:7896` 失联是拔除 Ethernet 网线造成，不是 adbd 故障。
- **测试版 3 已实机通过。** 它继续移除高权限厂商浏览器、H618 Upgrade 和 Softwinner Update；Android、Settings、遥控、HDMI 和 Wi‑Fi 正常，Chrome 保留。
- **测试版 4 已启动并通过包/输入法验证。** 八个目标包均已消失，默认输入法仍为 LatinIME；查询中的 `com.android.musicfx` 是独立的 AOSP 音效服务，不是 Music 播放器残留。
- **测试版 5 已实机通过。** 17 个目标包全部消失；Google Play、TV Settings、蓝牙、MusicFX 和 Google Play services 均保留。
- **测试版 6 已实机通过。** 16 个新增目标包全部消失，X12、SystemUI、TV Settings、LatinIME、蓝牙和 Google Play 均保留；纯删除阶段结束。
- **Projectivy 4.71 用户态预检通过。** 已设为默认 Launcher，方向键、OK、Back、应用列表、Settings、应用启动和 Home 接管正常；仅观察到轻微卡顿。
- 设备采用 64 位 ARM 内核，但 Android 用户空间为纯 32 位：`zygote32`、`armeabi-v7a`，且 system/vendor 没有 `lib64`。当前主线继续保留 32 位厂商栈。
- **Test7 已实机通过。** Projectivy 已作为 system app 和默认 HOME 正常工作；首次启动的 Launcher 选择框来自仍保留的 X12。
- **Test8 蓝牙回归已定位并修复。** 原因是 Test6 误删 AOSP ContactsProvider，导致 Bluetooth PBAP 崩溃；Test8r2 已恢复其完整目录并通过端到端自动验证和真机刷测。Projectivy、英语界面、遥控、Settings、Wi‑Fi 和蓝牙正常，蓝牙为 `state: ON` 且 `Bluetooth crashed 0 times`。Test8r2 是当前稳定基线。

## 测试版 1：实机通过

目的：只删除 `/system/app/UBTunnel.6`，验证 ext4 直接修改、AVB、dynamic super 和 PhoenixCard 封装整条链路。保留官方启动器以及 `boot`、`vendor_boot`、`dtbo`、`product`、`vendor`、`vendor_dlkm`。

- 镜像：`out/candidates/test1-no-ubtunnel-r3/x12-test1-no-ubtunnel.img`
- 大小：2,005,954,560 字节
- SHA-256：`3B8F8981E94B9BF209763FE3B67EC7102616B6D42631AA7F93264885C852C776`
- 离线验证：PASS
  - 只删除 UBTunnel 目录和 APK；共同文件语义无意外变化。
  - AVB 签名、system/vendor/product/vendor_dlkm hashtree 全部通过。
  - super 的 LP/ext4 结构通过。
  - IMAGEWTY 载荷来源与伴生校验通过。
- 实机验证：PASS
  - PhoenixCard 量产约 305 秒，最终输出 `CARD OK` 和 `sprite success`。
  - Android、主界面、设置、UBTunnel 删除、红外遥控、HDMI 音视频、Wi‑Fi、以太网、蓝牙扫描和高码率视频均通过。
  - Google、YouTube、bilibili 主站和 API 均通过。
  - CEC 按用户需求跳过；BBLL 以 API 恢复作为当前阶段通过，不单独安装验证。

## 测试版 2：实机通过

累计删除 `/system/app/UBTunnel.6`、`DragonAtt`、`DragonBox`、`DragonAgingTV`、`Factory_detection` 和 `AwlogSettings`。

- 镜像：`out/candidates/test2-remove-factory-tools-r1/x12-test2-remove-factory-tools.img`
- 大小：2,005,962,752 字节
- SHA-256：`4789EB9F76FD98E09D4155E95235CD06E38A9AE15E5A7BC7BF5B9F7D2224C964`
- 离线验证：PASS
  - ext4 语义差异只有 27 个预期删除路径；无新增内容或解析错误。
  - 完整 AVB 启动链和各分区哈希树通过。
  - PhoenixCard IMAGEWTY 中的关键分区载荷及伴生校验通过。
- 实机验证：PASS
  - Android 主界面、Settings、红外遥控、HDMI 图像和声音、Wi‑Fi 正常。
  - `api.bilibili.com` 可访问。
  - ADB 确认五个目标包均已消失。

## 测试版 3：实机通过

在 Test2 基础上继续删除 `/system/app/browser-v1.1`、`H618_UpgradeV3` 和 `Update`。Chrome、Launcher、遥控配对、LED、投屏、Google 服务和所有硬件分区保持不变。

- 镜像：`out/candidates/test3-remove-browser-updaters-r1/x12-test3-remove-browser-updaters.img`
- 大小：2,005,966,848 字节
- SHA-256：`8E42CB38426E3E80359BA5F2A9A0A21368789B43BF6B8DD86DF2D67630E44B77`
- 离线验证：PASS
  - 只少 40 个配置内的预期路径，没有新增内容、解析错误或意外共同条目变化。
  - 完整 AVB 启动链和各分区哈希树通过。
  - PhoenixCard IMAGEWTY 关键载荷及伴生校验通过。
- 实机验证：PASS
  - Android、Settings、红外遥控、HDMI 音视频和 Wi‑Fi 正常。
  - ADB 只匹配到 `com.android.chrome`，三个删除目标均已消失。

## 测试版 4：实机通过

在 Test3 基础上继续删除 CZFileManager、Zhuyin、GalleryTV、Music、VideoPlayer、TvdVideo、TvdFileManager 和 ImageParser。保留 Chrome、默认 LatinIME 和全部硬件媒体栈。

- 镜像：`out/candidates/test4-remove-legacy-user-apps-r1/x12-test4-remove-legacy-user-apps.img`
- 大小：2,005,966,848 字节
- SHA-256：`639403FDDB95439401FFC929764E549CA49A7AD4F5BF92DD232FF6955A50CE73`
- 离线验证：PASS
  - 只少 95 个配置内预期路径，没有新增内容、解析错误或意外共同条目变化。
  - 完整 AVB 启动链和各分区哈希树通过。
  - PhoenixCard IMAGEWTY 关键载荷及伴生校验通过。
- 实机验证：PASS
  - Android 和网络 ADB 正常，八个删除目标均不存在。
  - 默认输入法为 `com.android.inputmethod.latin/.LatinIME`。

## 测试版 5：实机通过

在 Test4 基础上新增删除 17 个非电视平台应用。Google Play、MusicFX、蓝牙、相机扩展、Launcher、配对组件和全部硬件分区保持不变。

- 镜像：`out/candidates/test5-remove-nontv-platform-apps-r1/x12-test5-remove-nontv-platform-apps.img`
- 大小：2,005,979,136 字节
- SHA-256：`16332D8E6BC14FA8D5855383BD3C9248D7A374E81A4967DC471B3C6E610F472F`
- 离线验证：PASS
  - 累计只少 199 个配置内预期路径，没有新增内容、解析错误或意外共同条目变化。
  - 完整 AVB 启动链和各分区哈希树通过。
  - PhoenixCard IMAGEWTY 关键载荷及伴生校验通过。
- 实机验证：PASS
  - 17 个目标包查询无输出。
  - `com.google.android.gms`、`com.android.vending`、`com.android.bluetooth`、`com.android.tv.settings`、`com.android.musicfx` 均存在。

## 测试版 6：实机通过

在 Test5 基础上新增删除 16 个旧个人设备 UI 和非目标功能组件。当前 Launcher、SystemUI 壁纸、PhotoTable 屏保、Google Play、蓝牙和硬件分区保持不变。

- 镜像：`out/candidates/test6-remove-legacy-personal-ui-r1/x12-test6-remove-legacy-personal-ui.img`
- 大小：2,005,979,136 字节
- SHA-256：`D8AA71730952F4388D82E6B919E05B757C50CD3D74805351546566D62125A576`
- 离线验证：PASS
  - 累计只少 295 个配置内预期路径，没有新增内容、解析错误或意外共同条目变化。
  - 完整 AVB 启动链和各分区哈希树通过。
  - PhoenixCard IMAGEWTY 关键载荷及伴生校验通过。
- 实机验证：PASS
  - 16 个目标包查询无输出。
  - X12、SystemUI、TV Settings、LatinIME、蓝牙和 Google Play 六个关键包均存在。

## 后续路线

- Test8r2：实机确认恢复 ContactsProvider 后蓝牙开启和扫描正常；其余已通过项目只做启动 sanity check。
- Test9：提供 SmartTube、Kodi、Jellyfin、Moonlight 的配置安装脚本，选择 AirPlay 接收器和现代文件管理器，并完成最终验证。
- arm64/multilib 作为独立扩展项目；只有取得同板型 64 位 BSP 或完整匹配的 64 位硬件库后才进入实作。

## 重要路径

- 官方固件：`x12-1024.img`
- 官方提取物：`firmware/extracted/`
- 官方 system：`out/official-system-a/20260726-r1/system_a.img`
- 官方 system 清单：`out/official-system-a/20260726-r1/official-system-a-manifest.json`
- 测试版 1：`out/candidates/test1-no-ubtunnel-r3/`
- 测试版 1 system 清单：`out/candidates/test1-no-ubtunnel-r3/candidate-system-manifest.json`
- 测试版 1 logical-system 报告：`logs/analysis/20260726-test1-logical-system/`
- 测试版 1 实机结果：`logs/device/20260726-test1-product-flash-console-paste/`
- 测试版 1 ADB 基线：`logs/device/20260726-135417-test1-adb/`
- 测试版 2：`out/candidates/test2-remove-factory-tools-r1/`
- 测试版 3：`out/candidates/test3-remove-browser-updaters-r1/`
- 测试版 4：`out/candidates/test4-remove-legacy-user-apps-r1/`
- 测试版 5：`out/candidates/test5-remove-nontv-platform-apps-r1/`
- 测试版 6：`out/candidates/test6-remove-legacy-personal-ui-r1/`
- 测试版 7：`out/candidates/test7-projectivy-default-home-r1/`
- 测试版 8：`out/candidates/test8-remove-vendor-home-wizard-cast-r1/`
- 测试版 8 修订版：`out/candidates/test8r2-restore-contacts-provider-r1/`
- 候选配置：`configs/candidates/`
- 测试版构建脚本：`scripts/build-candidate-firmware.py`
- ext4 解析器：`src/ubox10_rom/ext4_image.py`
- UART 手册：`docs/UART_RUNBOOK.md`
- 当前待办：`docs/TODO.md`
- 当前里程碑：`docs/MILESTONES.md`

## 工作方式

- 可恢复修改完成最低限度检查后直接构建、刷机和测试；失败就刷回官方固件。
- 只有 eFuse/OTP/BootROM、唯一密钥、无备份分区表或 bootloader、宿主物理磁盘等不可恢复操作才暂停。
- 文档只维护后续继续工作需要的当前事实；旧的 M6 详细文档作为历史分析资料，不代表当前门禁。
- 普通文档、日志、脚本和中间产物不默认生成 SHA-256；只在下载/传输、长期保存的原件或刷机镜像存在明确完整性风险时使用。
