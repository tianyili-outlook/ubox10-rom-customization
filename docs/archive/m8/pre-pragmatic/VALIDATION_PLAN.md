# 验证计划

## 每个候选的最低离线检查

- 输入、输出路径和刷机镜像完整性正确。
- 原版固件仍存在，可用 PhoenixCard 恢复。
- ext4 只出现计划内的文件差异。
- `e2fsck`、AVB、LP/super 和 IMAGEWTY 校验通过。

## Test8r2 实机检查结果

- PASS：启动后直接进入 Projectivy，英语界面、遥控和 Settings 正常。
- PARTIAL：Wi‑Fi 成功关联后互联网与 TCP ADB 正常；重复扫描目标 SSID 的可靠性尚未通过，按同目录 `ROADMAP.md` 的 Test9.1 单独验收。
- PASS：蓝牙保持开启并能扫描。
- PASS：ADB 确认 ContactsProvider 来自 `/system/priv-app`，蓝牙为 `state: ON`、`Bluetooth crashed 0 times`。
- PASS：X12、settingwizard 和 HappyCast 三个厂商包均不存在。
- 按变更范围未重复测试 bilibili、HDMI 音频、以太网、视频解码或 UART。

## Test9a/Test9b 结果

- FAIL：两者均通过离线结构和完整性验证，但 Play Store 实机进入 `AccessRestrictedActivity` 并提示版本不兼容。
- 只通过离线验证不足以提升为基线；Test9a/Test9b 仅保留作 Leanback feature 对照，不再继续配置或发布。

## Test9w1 最终结果

- 离线 PASS：只有锁定哈希的 `aic8800_fdrv.ko` 有效载荷一字节变化。
- 真机 PARTIAL：`ant_div=N`，当前 5 GHz 网络稳定，蓝牙无回归；目标
  2.4 GHz SSID 仍未出现。
- 产品结论 FAIL/退役：没有证据证明补丁带来实质改善，不再重复测试或传递
  到新候选；Test8r2 继续作为稳定基线。

## Test9r1/Test9r2 最终结果

- Test9r1 离线 PASS：从 Test8r2 只新增 10 个 remote stack 路径；`vendor_dlkm`
  与官方输入相同。
- Test9r1 真机 FAIL：RRO 位于该固件未扫描的 `/system/overlay`，未注册为
  package，framework lookup 为空，provider watcher 拒绝绑定，端口未监听。
- Test9r1 Play Store FAIL：29.2.15 入口仍存在，但启动进入
  `AccessRestrictedActivity`；Remote Service 同时报告 Play Store “missing”。
- Test9r2 相对 Test9r1 只能改变 RRO 目的路径为
  `/system/system_ext/overlay/UBOX10TvRemoteConfigOverlay.apk`；不得夹带
  driver、权限、APK 或其他 product 变化。
- Test9r2 离线 PASS：10 个预期新增路径、官方 `vendor_dlkm`、ext4/e2fsck、
  完整 AVB、super、IMAGEWTY 和 25 项单元测试套件全部通过。
- Test9r2 RRO/framework PASS：system_ext RRO 生效，lookup 返回
  `com.google.android.tv.remote.service`，provider 已绑定。
- Test9r2 原始 receiver FAIL：缺少运行时 `BLUETOOTH_CONNECT`，
  `RemoteService.onCreate` 崩溃，6466/6467 不监听。
- Test9r2 最小权限探针 PASS：只在 userdata 临时授予 CONNECT 后，主进程、
  6466/6467、mDNS、证书和 uinput 正常；SCAN/ADVERTISE 保持未授予。
- 官方 Google TV iPhone 客户端 PASS：同 LAN 发现、TLS/配对码、电视操控和
  文字输入均通过；重启后的自动启动和配对持久性本轮未复验。
- AOSP remoteprovider DEX 只能定义
  `com.android.media.tv.remoteprovider.TvRemoteProvider*`，不得重复打包
  framework AIDL/boot classes。
- Google donor 必须匹配固定 package、versionCode、APK SHA-256 和 Google
  签名证书；二进制不得提交 Git 或由项目重新分发。
- 真机已同时出现 leanback feature、shared library、provider APK 和生效的
  framework RRO；RRO package 来自 system_ext overlay，lookup 精确返回
  provider package。
- 不授予纯 signature 的 `INJECT_EVENTS`；输入必须通过
  `TvRemoteProvider`/uinput bridge。
- Play Store 继续进入 `AccessRestrictedActivity` 并显示 not compatible；
  因此 Test9r2 remote 分类为 `R2-REMOTE-PASS`，整机只能记录
  `PARTIAL`、不得晋级。
- 已选择 S3：不制作 Test9r3/Test10p1；设备已刷回 Test8r2，M7 已完成，
  remote 产品化转入 M8.INPUT。

## Test9.3 用户态应用门

- 本地门：APK 必须匹配配置中的 bytes、SHA-256、package、versionCode、
  versionName、min/target SDK、native ABI、launch activity 和 signer
  certificate SHA-256。
- 设备门：只允许 SDK 31/ARMv7 的 Test8r2；必须保留 television、
  Projectivy、ContactsProvider 和 Play Store，且不得出现 leanback 或
  Google Remote Service。
- 安装门：默认五项全部 `adb install -r` 成功，设备端 `base.apk` SHA-256
  必须等于来源锁；重复运行必须 `already-current`，发现更高 versionCode
  时禁止静默降级。
- 启动门：五项均可解析 LEANBACK_LAUNCHER、进入主 activity，且无
  `AndroidRuntime` crash。
- 重启门：真实 uptime 重置后五项仍在、可再次启动；Projectivy、Wi‑Fi/
  互联网、蓝牙、Play Store 和 feature guard 不回归。
- 人工门：实体遥控/Back/Home、可用资源下的真实媒体播放、USB/APK、
  广告体验与 iPhone AirPlay 必须逐项确认；缺少外部资源时必须明确记录有限
  豁免，不能写成未发生的端到端 PASS。自动化不能替代人工门。
  AirReceiverLite 已完成发现、镜像、HDMI 音频和同步验证。
- AirPlay 商业边界：Lite 明确要求前台且部分功能每次限 5 分钟；用户接受
  该有限范围并决定不购买完整版。后台、开机和长会话不属于 M7 承诺；
  项目不导出、提交或再分发付费 APK。

最终结果为 `PASS`：Projectivy/五项通用遥控、SmartTube 1080p、
AnExplorer 内置存储/USB/APK 和 AirReceiverLite iPhone 音视频通过。
Kodi 缺媒体、Jellyfin 缺服务器、Moonlight 缺串流主机，仅验到界面与
连接/发现边界；三项记录为资源型有限豁免。用户决定不购买完整版，
Lite 的后台/开机与长会话不属于 M7 承诺。详见
`archive/m7/M7_COMPLETION_REPORT.md`。

## M8 门槛

- M8.0、M8A.1 与 M8B.1 只产生 inventory、source-lock、差异和 Go/No-Go 报告，不产生刷机镜像。
- M8A.2 前必须闭合当前 32 位 vendor 与 AOSP ATV product 的 package/permission/overlay/VINTF/容量合同；M8B.2 前必须明确 64 位 Mali/EGL/Gralloc/Mapper/HWC 与当前 Kernel ABI 的兼容结论。
- `ro.zygote`、ABI 属性或目录名不能替代 ELF 和运行进程位数证据。
- 原厂/Test8r2 的 Widevine、DRM HAL、TEE/OEMCrypto、secure codec、protected buffer 和 HDCP 基线必须在相关修改前建立。
- 其他板型 bootloader、DTB/DTBO、TEE、密钥和分区表不得进入候选。
- M8 每个可刷写阶段仍须满足现有 ext4/AVB/super/IMAGEWTY、UART 和恢复门槛。
- M8.INPUT 必须从源码构建 remoteprovider，并实测官方 Google TV iPhone
  应用的发现、认证、遥控、文字输入和重启复验；product 必须通过
  default-permissions 原生授予已证实必需的 `BLUETOOTH_CONNECT`，不无证据
  扩大 SCAN/ADVERTISE。若受 GMS TV 许可/认证阻塞，明确记为 `BLOCKED`，
  不以 UBOX Input 替代通过。

## 结果处理

- 能启动且没有新回归：保留该候选作为下一批修改的基线。
- 不能启动：保存 UART 日志，刷回官方镜像，再根据第一个明确错误修改。
- 能启动但硬件异常：刷回官方镜像确认硬件正常，再缩小删除范围。
- Launcher 异常但 Android/ADB 正常：从 `Settings > Apps` 启动 Projectivy 并记录现象；必要时刷回 Test8r2。
