# 产品化路线图

## 当前基线与边界

- 当前唯一稳定基线是 Test8r2：
  `out/candidates/test8r2-restore-contacts-provider-r1/x12-test8r2-restore-contacts-provider.img`
- 已确认 Wi‑Fi 连接成功后，互联网和 TCP ADB 可以稳定使用；但历史全频扫描存在连续零结果，同一目标的扫描 RSSI 在强、弱两档间相差约 30 dB。过去文档中的“Wi‑Fi 正常”只代表连接与传输测试通过，不代表扫描可靠性已经通过。
- Test9w1 是待实机验证的单变量实验候选，不是新基线：
  `out/candidates/test9w1-disable-aic-ant-div-r1/x12-test9w1-disable-aic-ant-div.img`
- Test9a/Test9b 只是 Google Play/TV feature 的诊断实验。两者均通过离线构建验证，但实机 Play Store 都进入 `AccessRestrictedActivity` 并提示当前版本不兼容，因此不得作为日常或后续开发基线。
- 当前 32 位系统继续保留现有 Google 服务作为登录、应用安装与更新基础设施；不再把手机式 Play Store 界面当作当前阶段的主要电视入口。

## Test9.1：Wi‑Fi 扫描可靠性

### 已完成的证据收敛

- 五轮连接态主动扫描都能完成，但开机历史中出现过连续全频 `0 results`；问题存在于 Settings 之外的扫描结果源。
- Settings 的特权和扫描节流不是首要问题，`wificond` 也没有崩溃；AIC vendor HAL 缺少 background scan/link-layer stats 能力，驱动不支持 scheduled scan。
- 板上丝印 `AW869A WiFi6`；官方规格把 AW869A 定义为 AIC8800D40、1T1R、单天线型。当前驱动却报告 `ant_div=Y`，与静止环境下约 30 dB 的扫描 RSSI 双峰共同构成首个可证伪假设。

### Test9w1 单变量候选

- system 与 Test8r2 保持一致。
- 只在来源 SHA-256 已锁定的 `/lib/modules/aic8800_fdrv.ko` 内，把 `ant_div` 默认值的一个字节由 `01` 改为 `00`；不替换 AIC 驱动或固件，不修改 HAL。
- 固件 SHA-256：`2D43D4A6B64702F1D0265EDC27B33EB424B4B56A721DC8068B5CCEBB4A310CC5`。
- ext4、完整 AVB 链、super、IMAGEWTY 和 20 项单元测试已通过；没有真机启动证据。
- 修改后的 vendor_dlkm 保留 dm-verity，但因本地没有可信 `fec` 工具而关闭 FEC；这进一步限定它只能先作为可恢复实验候选。

### 实机验证顺序

1. PhoenixCard 可能清除 userdata/metadata；刷机前备份需要保留的本地数据和账户信息，并保留 Test8r2 恢复卡/镜像。
2. 首次启动后先进入 Wi‑Fi 页面，不开关 Wi‑Fi；记录目标网络能否在 30 秒内出现，再正常连接。
3. ADB 读取 `/sys/module/aic8800_fdrv/parameters/ant_div`，必须为 `N`。
4. 在设备位置和路由器配置不变的情况下做五轮主动扫描；不把密码、完整 BSSID 或其他凭据提交仓库。
5. 只做一次 Settings 中的 Wi‑Fi 关闭/开启；重连 ADB 后再次确认 `ant_div=N`，证明 HAL 卸载/重载后仍采用补丁默认值。
6. 重启，检查无需开关 Wi‑Fi 即可发现/自动连接、互联网和 TCP ADB 正常，并第三次确认 `ant_div=N`。
7. 检查蓝牙保持 `ON`、可扫描且 `Bluetooth crashed 0 times`；Wi‑Fi/蓝牙共用模块，不能省略这一回归。

### 验收标准

- 冷启动后不切换 Wi‑Fi，目标 SSID 在 30 秒内出现。
- 目标 SSID 在 5 轮扫描中至少 4 轮能在 30 秒内出现。
- Settings 结果与 shell 扫描结果一致，没有连续全频零结果、scan failure 或驱动重置。
- 静止环境中目标扫描 RSSI 不再分成相差约 30 dB 的两个稳定档位。
- 启动、一次 Wi‑Fi HAL 重载和重启后的 `ant_div` 均为 `N`。
- 重启后无需开关 Wi‑Fi 即可自动重连。
- 连接成功后互联网和 TCP ADB 保持稳定。
- 蓝牙无回归。

若失败，直接刷回 Test8r2，并按证据判断：`ant_div=N` 但故障不变，则否定/显著削弱天线分集假设，下一个单变量应审计 2022 年 AIC 固件/全频扫描行为；不得同时更新未知来源的驱动与固件。

## Test9.2：iPhone 遥控与文字输入

此阶段依赖 Test9.1，因为官方手机遥控要求 iPhone 与电视处于同一 Wi‑Fi 网络。首选官方 Google TV iOS 应用提供的虚拟遥控和键盘输入，不把来源不明的远程键盘 APK 固化进 system。

### 验证顺序

1. 在 Test8r2 上只读盘点已安装包、服务、mDNS/局域网发现和监听端口，确认是否存在 Google TV Remote Service 或兼容接收端。
2. 用 iPhone 的官方 Google TV 应用尝试发现、配对并输入搜索、账号和密码字段。
3. 若接收端缺失：
   - 不直接移植或重新分发 Google 专有接收组件。
   - 优先评估可追溯、开源、仅局域网工作的遥控键盘接收方案，并先以 data app 试装。
   - 已验证可用的蓝牙键盘作为硬件回退方案。

### 验收标准

- 同一局域网内可发现设备，并以配对码或等价机制授权。
- 只有已配对设备可以输入；不开放未认证的 ADB 或通用网络端口。
- 文本框聚焦时可输入英文、常用 Unicode、账号及密码，重启后仍可正常配对使用。
- iPhone 断开不影响红外/蓝牙实体遥控器。
- 核心输入不依赖云端账户或公网服务。

## Test9.3：当前 32 位系统产品化收尾

- 提供 SmartTube、Kodi、Jellyfin 和 Moonlight 的可重复 data 分区安装脚本。
- 选择有明确来源、许可证和遥控器体验的 AirPlay 接收器及现代文件管理器。
- 将应用来源、版本、签名和校验写入配置；第三方 APK 不提交公共仓库。
- 完成 Projectivy 流畅度、启动、遥控、影音、蓝牙、Wi‑Fi、应用安装和重启回归。

## M8：未来平台升级

“真正适合电视的 Google Play 体验”与 64 位 Android 用户空间合并为一个未来平台阶段，不再尝试在当前 32 位系统上靠单个 feature XML 或随机替换 Play Store APK 解决。

进入实作的前提：

- 取得同板型、匹配 H616 硬件库的完整 arm64/multilib BSP 或可验证固件。
- 取得与目标设备身份、Google TV/Android TV feature 集和认证状态相匹配、且可合法使用的 Google TV 组件栈。
- 先在独立分支和候选镜像验证启动、硬解、Wi‑Fi、蓝牙、HDMI/CEC、遥控与 DRM，再考虑替换当前 Test8r2 主线。

目标包括：

- arm64/multilib 用户空间和完整匹配的 vendor 硬件栈。
- 遥控器友好的 TV Play Store 首页、搜索、安装和更新流程。
- 合理的设备名称与身份呈现，不再同时出现 Pixel 3、X12 和 A1 ADT-3 等互相矛盾的标签。
- 可核验的 Play Protect/设备认证状态；内部 GMS 日志不能替代 Play Store 设置页的认证结果。

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
