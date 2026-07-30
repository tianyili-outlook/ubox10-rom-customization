# 产品化路线图

## 当前基线与边界

- 当前唯一稳定基线是 Test8r2：
  `out/candidates/test8r2-restore-contacts-provider-r1/x12-test8r2-restore-contacts-provider.img`
- Wi‑Fi 连接、互联网与 TCP ADB 可稳定使用；用户家庭 5 GHz 网络始终可见，主要缺失的是另一个 2.4 GHz SSID。Test9w1 将 `ant_div` 改为 `N` 后仍未使该 2.4 GHz SSID 出现，因此没有证据把驱动补丁提升为产品修复。
- Test9w1 已退役：配置和哈希用于历史复现，镜像删除；所有后续候选继续从 Test8r2 构筑。
- Test9r1 真机已确认因 RRO 放在该固件不扫描的 `/system/overlay` 而失败；
  feature、shared library、APK 和权限本身均加载成功。
- 已完成的技术探针是 Test9r2：
  `out/candidates/test9r2-android-tv-remote-service-rro-path-r1/x12-test9r2-android-tv-remote-service-rro-path.img`
  它仍从 Test8r2 构筑，只把同一 RRO 移到启动日志明确扫描的
  `/system/system_ext/overlay`；离线和真机 remote 技术链均通过，但因
  Play Store 回归总体为 `PARTIAL`、不晋级。
- Test9a/Test9b 只是 Google Play/TV feature 的诊断实验。两者均通过离线构建验证，但实机 Play Store 都进入 `AccessRestrictedActivity` 并提示当前版本不兼容，因此不得作为日常或后续开发基线。
- 当前 32 位系统继续保留现有 Google 服务作为登录、应用安装与更新基础设施；不再把手机式 Play Store 界面当作当前阶段的主要电视入口。

## Test9.1：Wi‑Fi 结论

- Test9w1 真机启动，`/sys/module/aic8800_fdrv/parameters/ant_div` 为 `N`。
- 五轮扫描中当前连接的 5 GHz 网络保持强且稳定，其他 5 GHz 网络也可出现；目标 2.4 GHz SSID 仍未出现。
- 蓝牙保持 `ON`、`Bluetooth crashed 0 times`。
- 用户确认可稳定使用 5 GHz，2.4 GHz 缺失不再构成当前产品阻塞；板上单天线结构也限制了进一步射频软件推断的价值。
- 结论：Test9w1 没有证明实质改善，不晋级、不继续投入、不传递其无 FEC 的 vendor_dlkm 到后续候选。若未来 5 GHz 连接/吞吐也出现可复现故障，再从 Test8r2 重新立项采证。

## Test9.2：iPhone 遥控与文字输入

当前网络已满足同一局域网前提。目标固定为官方 Google TV iOS 应用，不考虑
UBOX Input。

最终结果为 `R2-REMOTE-PASS`：修正后的 RRO、provider、6466/6467、mDNS、
官方 iPhone 配对、遥控和文字输入均通过。初始失败根因是预置产品没有默认
授予 `BLUETOOTH_CONNECT`；仅临时授予这一项后链路工作，SCAN/ADVERTISE
保持未授予。Play Store 仍为 not compatible，因此路线选择 S3，结束当前
32 位 remote 候选并把产品化集成转入 M8.INPUT。

### 已完成的技术收敛

- 当前 system 没有 `com.google.android.tv.remote.service`、leanback 或
  `com.android.media.tv.remoteprovider` shared library，framework resource
  `config_tvRemoteServicePackage` 为空。
- 设备 framework 已有 `TvRemoteService`、provider watcher、Binder 接口和
  `TvUinputBridge`，不需要修改 Kernel 或 `services.jar`。
- 官方原签名 Remote Service 5.2.473254133 普通安装实测因 required shared
  library 缺失而失败。
- Test9r1 从 Test8r2 加入 AOSP runtime library、共享库 XML、leanback、
  framework RRO、privapp allowlist 和本地 donor；完整离线验证通过。
- Test9r1 真机中 RRO 文件虽存在于 `/system/overlay`，Package Manager 却未
  注册它，framework lookup 为空，provider watcher 因 package 未配置/白名单
  而拒绝绑定，6466/6467 未监听。
- Test9r1 的 Play Store 29.2.15 同时进入 `AccessRestrictedActivity`；Remote
  Service 日志还把 Play Store 判定为 “missing”。这使 Test9r2 即使修好
  remote 也只能是技术 `PARTIAL`。
- Test9r2 只修正 RRO 预置路径，其他 system 内容和官方 `vendor_dlkm` 合同
  不变；完整离线验证通过。
- Google APK 不进入 Git 或项目再分发；AOSP library 由锁定源码复现。

### Test9r2 真机结果

1. RRO 位于 `/system/system_ext/overlay`，framework lookup 精确返回
   `com.google.android.tv.remote.service`，provider 已绑定。
2. 未干预时 Remote Service 因缺少 `BLUETOOTH_CONNECT` 崩溃，
   `crashCount=2`，6466/6467 均未监听。
3. 仅临时授予 CONNECT 并重新触发服务后，主进程稳定、两端口监听，
   `_androidtvremote2._tcp` 以 `Pixel 3` 名称注册。
4. 官方 Google TV iPhone 应用完成 TLS 配对、方向/OK/Back/Home 等操控和
   文字输入；virtual-remote/uinput 路径正常。
5. Play Store 继续进入 `AccessRestrictedActivity`。重启后的 remote
   持久性未复验，留作 M8.INPUT 正式验收。

### 验收标准

- 同一局域网内可发现设备，并以配对码或等价机制授权。
- 只有已配对设备可以输入；不开放未认证的 ADB 或通用网络端口。
- 文本框聚焦时可输入英文、常用 Unicode、账号及密码，重启后仍可正常配对使用。
- iPhone 断开不影响红外/蓝牙实体遥控器。
- 核心输入不依赖云端账户或公网服务。
- `INJECT_EVENTS` 不通过伪造签名或宽松权限授予；事件走 framework
  `TvRemoteProvider`/uinput 桥。
- Projectivy、Settings、Play Store、Wi‑Fi、蓝牙和重启无新增关键回归。

### Test9r2 后的证据与路线决策

Android 12 `SystemServer` 只在 `FEATURE_LEANBACK` 存在时启动
`TvRemoteService`，而本项目 Test9a/Test9b/Test9r1 已连续证明 leanback 会让
当前手机式 Play Store 进入受限页；Test9r1 的 Remote Service 还把已安装的
Play Store 判定为 “missing”。Test9r2 已把 RRO、framework、receiver、
发现/配对和 Play/GMS 依赖分层记录：

- `R2-REMOTE-PASS`：已确认；Play/GMS 警告没有阻止本地 Remote v2。
- receiver 最小产品缺口：`BLUETOOTH_CONNECT` 默认运行时授权。
- Google 产品缺口：Play Store 不兼容；Store “missing” 与 package visibility/
  Google API 配置不一致仍存在，但不在 M7 继续修补。

已在三条近期路线中选择 S3：

1. **S1 / Test9r3：不执行。** 不在 M7 修改 framework startup gate。
2. **S2 / Test10p1：不执行。** 不混装缺少闭合 donor 的 TV Google 组件。
3. **S3 / 收束 32 位 remote：已选择。** 保留 Test8r2，完成 Test9.3，
   把官方手机遥控和默认权限产品化转入 M8.INPUT。

不得在同一候选中同时改变 framework gate、整套 GMS、设备身份和网络。
不制作 Test9r3 或 Test10p1。

完整设计、哈希与判错树见
`archive/m7/TEST9R1_ANDROID_TV_REMOTE_SERVICE.md` 和
`archive/m7/TEST9R2_RRO_SCAN_PATH.md`；参考项目、结果分类和研究交付物见
`../../m7/tv-gms-remote/README.md`。最终真机证据和路线选择分别见
`../../m7/tv-gms-remote/test9r2-runtime-report.md` 与
`../../m7/tv-gms-remote/route-decision.md`。

## Test9.3：32 位系统产品化收尾（已完成）

M7 已从 Test8r2 完成，不继承 Test9r2 的 leanback/remote system stack。

- 提供 SmartTube、Kodi、Jellyfin 和 Moonlight 的可重复 data 分区安装脚本。
- 选择有明确来源、许可证和遥控器体验的 AirPlay 接收器及现代文件管理器。
- 将应用来源、版本、签名和校验写入配置；第三方 APK 不提交公共仓库。
- 完成 Projectivy 流畅度、启动、遥控、影音、蓝牙、Wi‑Fi、应用安装和重启回归。

2026-07-29 最终结果：

- 已从 Test9r2 刷回并自动确认 Test8r2 合同。
- 五项 source-lock、安装器、单元测试、首次安装、启动和真实重启自动化门
  通过。
- AirReceiverLite 5.1.7 已通过 iPhone 发现、镜像、HDMI 音频与同步实测；
  重启证明 Lite 因产品限制不会后台/开机运行，且部分功能每次限 5 分钟。
- Projectivy 图标/焦点、五项 D-pad/Back/Home、SmartTube 1080p 与
  AnExplorer 存储/USB/APK 人工门通过。
- Kodi/Jellyfin/Moonlight 因无媒体、服务器或串流主机，仅验到界面与
  连接/发现边界；以有限豁免记录，不虚构端到端播放。
- 用户不把 AirReceiver 完整版购买纳入项目；Lite 作为按需前台能力被接受，
  AirScreen 不再评估。Test9.3 为 `PASS`，M7 为 `COMPLETE`。

完成报告与实验历史见 `archive/m7/M7_COMPLETION_REPORT.md`。

## M8：先建立真正 AOSP Android TV，再迁移 AArch64

M8 不再以“找到一套 Google TV APK”定义，也不再把 TV product 与 64 位 ABI
放在同一个首发候选中。路线拆为：

1. **M8.0 共享证据门**：盘点当前 ELF/HAL/VINTF/图形/媒体/DRM，锁定参考
   源码与安全边界。
2. **M8A / ARM32 真 ATV**：保留当前 Kernel、vendor、vendor_dlkm 和 32 位 ABI，
   先从源码继承 Android 12 AOSP ATV product，验证真正 TV product、输入、
   Settings、电源、网络、显示和应用合同。
3. **M8B / AArch64**：M8A 产品合同稳定且 64 位图形栈为 `GO` 后，再建立真实
   arm64/multilib userspace 和匹配 H616 的硬件栈。

M8.GMS、M8.INPUT 和 M8.DRM 是横向门禁。AOSP ATV 可在没有 Google 商业认证
时独立完成；TV Play Store、官方 Google TV 手机遥控和 Netflix 资格必须分别
记录，不得用其中一项替代另一项。

### 阶段与出口

- **M8.0 共享审计**：递归盘点 ELF、HAL/service、VINTF、Kernel modules、
  图形、媒体、Wi‑Fi/BT 和 DRM；锁定 Android 12 ATV 参考与 Test9 remote
  证据。此阶段不生成刷机镜像。
- **M8A.1 ATV 参考与差异（完成）**：固定 `device/google/atv` 的
  `android12-release` commit，比较 `aosp_tv_arm` product inheritance、
  package、permission、overlay、VINTF、Settings、输入、网络、电源和显示。
- **M8A.2 最小 ARM32 ATV product**：保持 UBOX10 boot/kernel/vendor/
  vendor_dlkm/TEE/分区表不变，建立自有 system/product/system_ext，
  先闭合离线依赖，再分层验证启动、HDMI、ADB 和最小 TV UI。
- **M8A.3 产品与硬件验收**：恢复实体遥控、音频、Wi‑Fi、蓝牙、视频硬解、
  CEC、休眠和应用体验；M8.INPUT 与 M8.GMS 单列，不把 Play 页面当 ATV
  产品完成判据。
- **M8B.1 64 位供体验证**：锁定并原样构建 BPI H618 BSP，以实际 ELF、
  `lib64` 和 Mali/Gralloc/Mapper/HWC 判定，不以 `-a arm64` 文档代替证据。
- **M8B.2 最小 AArch64/multilib 启动**：在 M8A product 合同上依次验证
  linker、zygote64、system_server、SurfaceFlinger、HDMI、ADB 和最小 UI。
- **M8B.3 硬件/DRM 回归**：按 M8A 已建立的子系统基线逐项恢复并完成
  Netflix N1。
- **M8B.4 后续 Android/Kernel**：只有 Android 12 arm64/multilib 与 N1
  稳定后才评估；Android 主版本和 Kernel major 每次只改变一个。

旧编号 M8.1–M8.6 仅用于历史追溯；新旧映射和详细退出条件见架构文档。

### Netflix/DRM 横向门禁

- N0：原厂/Test8r2 的 Play Protect、Widevine、DRM HAL、TEE/OEMCrypto、secure codec、protected buffer、HDCP 与 Netflix 实际播放基线。
- N1：本人合法账号可稳定安装、登录、遥控和播放，实际最大分辨率可复查。
- N2：只有 L1、secure decoder、protected path、HDCP 和服务端资格共同满足时验证 HD。
- N3：只有 N2 稳定且 secure 4K/HDR、HDCP 2.2+、电视/线材/套餐满足时推进。

不得复制或伪造 Widevine/TEE/HDCP 密钥、设备证书、ESN 或认证状态。Google TV/GMS TV 商业认证不是个人 AOSP ATV 工程可保证的结果。

完整架构、供体政策和退出条件见同目录 `ARCHITECTURE.md`。

## 参考依据

- AOSP 的 TV 核心 feature 文件同时声明 television、leanback 与 leanback_only：
  <https://android.googlesource.com/device/google/atv/+/3ce48358b7e06ab1f1a1b713fb0f285aaa0983ca/permissions/tv_core_hardware.xml>
- Android TV 应用和 Leanback 要求：
  <https://developer.android.com/training/tv/get-started/create>
- Android 12 兼容性定义：
  <https://source.android.com/docs/compatibility/12/android-12-cdd>
- Google Play 认证说明：
  <https://support.google.com/googleplay/answer/7165974>
- Google TV iPhone/iPad 遥控与同一 Wi‑Fi 要求：
  <https://support.google.com/googletv/answer/15766805?co=GENIE.Platform%3DiOS&hl=en>
- AW869A 官方规格（AIC8800D40、1T1R、AW869A 1-ANT / AW869A2 2-ANT）：
  <https://fccid.io/m/b16603993f07640385676f2c4549dceaa073d19eb44d8bac682af82886b9b189.pdf>
- Android DLKM 模块与加载配置：
  <https://source.android.com/docs/core/architecture/kernel/kernel-module-support>
- BPI H618 Android 12 BSP：
  <https://github.com/BPI-SINOVOIP/BPI-H618-Android12>
- Android DRM 架构：
  <https://source.android.com/docs/core/media/drm>
