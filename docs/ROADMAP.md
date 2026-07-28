# 产品化路线图

## 当前基线与边界

- 当前唯一稳定基线是 Test8r2：
  `out/candidates/test8r2-restore-contacts-provider-r1/x12-test8r2-restore-contacts-provider.img`
- Wi‑Fi 连接、互联网与 TCP ADB 可稳定使用；用户家庭 5 GHz 网络始终可见，主要缺失的是另一个 2.4 GHz SSID。Test9w1 将 `ant_div` 改为 `N` 后仍未使该 2.4 GHz SSID 出现，因此没有证据把驱动补丁提升为产品修复。
- Test9w1 已退役：配置和哈希用于历史复现，镜像删除；所有后续候选继续从 Test8r2 构筑。
- Test9r1 真机已确认因 RRO 放在该固件不扫描的 `/system/overlay` 而失败；
  feature、shared library、APK 和权限本身均加载成功。
- 当前候选是 Test9r2：
  `out/candidates/test9r2-android-tv-remote-service-rro-path-r1/x12-test9r2-android-tv-remote-service-rro-path.img`
  它仍从 Test8r2 构筑，只把同一 RRO 移到启动日志明确扫描的
  `/system/system_ext/overlay`；离线验证通过，等待 iPhone 真机复测。
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

### Test9r2 真机顺序

1. 用 PhoenixCard 刷入 Test9r2，先确认 Android、Projectivy、Settings、实体
   遥控、Wi‑Fi 和蓝牙。
2. ADB 先验证 overlay package 来自 `/system/system_ext/overlay`、已注册并
   启用，framework lookup 精确返回 provider package，watcher 不再拒绝。
3. 再验证 feature、shared library、provider package、privapp 权限、监听
   端口和相关日志。
4. iPhone 与电视连接同一 5 GHz 网络，验证发现、配对码、方向/OK/Back/Home。
5. 在搜索、账号、密码和 Unicode 文本框验证文字输入，随后重启复验。
6. 记录已知的 Play Store `AccessRestrictedActivity` 回归；即使遥控成功也
   不得将 Test9r2 晋级，采证后刷回 Test8r2。

### 验收标准

- 同一局域网内可发现设备，并以配对码或等价机制授权。
- 只有已配对设备可以输入；不开放未认证的 ADB 或通用网络端口。
- 文本框聚焦时可输入英文、常用 Unicode、账号及密码，重启后仍可正常配对使用。
- iPhone 断开不影响红外/蓝牙实体遥控器。
- 核心输入不依赖云端账户或公网服务。
- `INJECT_EVENTS` 不通过伪造签名或宽松权限授予；事件走 framework
  `TvRemoteProvider`/uinput 桥。
- Projectivy、Settings、Play Store、Wi‑Fi、蓝牙和重启无新增关键回归。

### Test9r2 后的 32 位分叉

Android 12 `SystemServer` 只在 `FEATURE_LEANBACK` 存在时启动
`TvRemoteService`，而本项目 Test9a/Test9b/Test9r1 已连续证明 leanback 会让
当前手机式 Play Store 进入受限页。因此：

- Test9r2 只用于确认 RRO/provider/官方 iPhone 输入链能否工作；
- 若 remote 通过，另立从 Test8r2 出发的候选，移除 leanback并定点改变
  framework 的 TvRemoteService 启动 gate；
- 不同时更换 Play Store/GMS、身份、donor 或网络参数；
- 若 framework 定点修改风险不可接受，32 位分支记录 `BLOCKED`，正式能力
  留给 M8 源码级 ATV product。

完整设计、哈希与判错树见
`experiments/TEST9R1_ANDROID_TV_REMOTE_SERVICE.md` 和
`experiments/TEST9R2_RRO_SCAN_PATH.md`。

## Test9.3：当前 32 位系统产品化收尾

- 提供 SmartTube、Kodi、Jellyfin 和 Moonlight 的可重复 data 分区安装脚本。
- 选择有明确来源、许可证和遥控器体验的 AirPlay 接收器及现代文件管理器。
- 将应用来源、版本、签名和校验写入配置；第三方 APK 不提交公共仓库。
- 完成 Projectivy 流畅度、启动、遥控、影音、蓝牙、Wi‑Fi、应用安装和重启回归。

## M8：AArch64 与真正 AOSP Android TV

M8 不再以“找到一套 Google TV APK”定义，而是两项相互关联但可分别验收的工程：

1. 建立真实 arm64/multilib Android userspace 和匹配 H616 的硬件栈；
2. 从源码继承 Android 12 AOSP ATV product，替代手机产品配置加 Launcher/feature 的伪装路线。

M8.0 可与 Test9r2 真机验收并行进行，只允许本地/ADB 只读盘点，不制作
64 位固件。

### 阶段与出口

- **M8.0 当前设备审计**：递归盘点 ELF、HAL/service、VINTF、Kernel modules、图形、媒体、Wi‑Fi/BT 和 DRM；标记 must-be-64、can-remain-32、missing-source 与 security-state。图形栈必须得到 Go/Blocked/Unknown。
- **M8.1 BPI H618 供体验证**：先锁定 commit、oversized files、Docker 环境和磁盘预算，再原样构建。`-a arm64` 只是一条线索，最终以 userspace ELF、`lib64` 和 Mali/Gralloc/Mapper/HWC 产物判定。
- **M8.2 Android 12 AOSP ATV 参考**：固定 Android 12 tag，比较 product inheritance、package、permission、overlay、VINTF、Settings、输入、网络、电源和显示，形成 UBOX10 product/device tree 草案；单列 remoteprovider shared library、provider package resource、privapp policy 与发现/配对路径。
- **M8.3 最小 64 位启动**：保持 UBOX10 boot0/U-Boot/DTB/DTBO/Kernel/DDR/PMIC/TEE/分区表不变，依次验证 linker、zygote64、system_server、SurfaceFlinger、HDMI、ADB 和最小 UI。
- **M8.4 硬件恢复**：GPU/显示、实体遥控与 official Google TV iPhone remote/text input、音频、Wi‑Fi、蓝牙、视频硬解、CEC、休眠、DRM 和 Netflix N1 分子系统恢复与压力回归。
- **M8.5 原生 AOSP ATV 产品**：完成 device tree、TV overlays/Settings/Launcher/input、SELinux、blob 提取和适用 CTS/VTS/GSI；官方原签名 Remote Service 可由用户本地提供，项目不重新分发。
- **M8.6 后续 Android/Kernel**：只有 Android 12 arm64 与 Netflix N1 稳定后才评估；Android 主版本和 Kernel major 每次只改变一个。

### Netflix/DRM 横向门禁

- N0：原厂/Test8r2 的 Play Protect、Widevine、DRM HAL、TEE/OEMCrypto、secure codec、protected buffer、HDCP 与 Netflix 实际播放基线。
- N1：本人合法账号可稳定安装、登录、遥控和播放，实际最大分辨率可复查。
- N2：只有 L1、secure decoder、protected path、HDCP 和服务端资格共同满足时验证 HD。
- N3：只有 N2 稳定且 secure 4K/HDR、HDCP 2.2+、电视/线材/套餐满足时推进。

不得复制或伪造 Widevine/TEE/HDCP 密钥、设备证书、ESN 或认证状态。Google TV/GMS TV 商业认证不是个人 AOSP ATV 工程可保证的结果。

完整架构、供体政策和退出条件见 `architecture/M8_ARM64_AOSP_TV_MIGRATION.md`。

## 参考依据

- AOSP 的 TV 核心 feature 文件同时声明 television、leanback 与 leanback_only：
  <https://android.googlesource.com/device/google/atv/+/578751f94fdc584be22d7b1ea3112723a861b3af/tv_core_hardware.xml>
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
