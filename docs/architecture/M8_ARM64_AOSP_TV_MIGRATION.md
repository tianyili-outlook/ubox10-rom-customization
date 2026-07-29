# M8：ARM32 AOSP Android TV、AArch64 与 Netflix/DRM 迁移计划

研究快照：2026-07-29。本文吸收两轮用户调研，作为 M8 的当前架构计划；
它不授权下载大型源码、复制闭源安全材料或制作刷机候选。

## 1. 状态词

- `CONFIRMED`：已有本项目镜像、ADB、UART、源码或真机证据。
- `LIKELY`：多项证据支持，但仍需直接验证。
- `UNKNOWN`：尚无足够证据。
- `BLOCKED`：缺少不可由当前工作生成的必要输入或外部资格。

未验证判断不得写成已完成能力。

## 2. 当前边界

| 项目 | 结论 | 状态 |
|---|---|---|
| SoC | Allwinner H616，Cortex-A53，支持 AArch64 | CONFIRMED |
| Kernel | 64 位 ARM、当前 5.4.125 厂商内核 | CONFIRMED |
| Android 用户空间 | `zygote32`、`armeabi-v7a`，system/vendor 无 `lib64` | CONFIRMED |
| 当前产品形态 | 手机产品配置叠加厂商电视界面，不是源码级 AOSP ATV product | CONFIRMED |
| 稳定基线 | Test8r2 | CONFIRMED |
| Wi‑Fi 实验 | Test9w1 真机未证明改善，已退役；后续从 Test8r2 继续 | CONFIRMED |
| 手机遥控 framework | TvRemoteService/provider watcher/uinput bridge 已由 Test9r2 真机输入证明可用 | CONFIRMED |
| 手机遥控候选 | Test9r2 在临时授予 `BLUETOOTH_CONNECT` 后通过官方 iPhone 发现、配对、遥控和文字输入；因 Play 回归总体为 PARTIAL | CONFIRMED |
| Play Protect | Play Store 无可见认证项；实际认证结论未取得 | UNKNOWN |
| Widevine/TEE/HDCP/secure decoder | 尚无完整基线 | UNKNOWN |
| Netflix | 安装、登录、播放和最大分辨率尚未建立基线 | UNKNOWN |

## 3. 路线重排：先产品，后架构

原计划把 AOSP ATV product 与 AArch64 迁移交错推进，会在首个可刷写候选中
同时引入 product、framework、ABI、图形和 Vendor 风险。M8 现拆为：

| 工作流 | 目标 | 前置条件 |
|---|---|---|
| M8.0 共享证据门 | 当前 ELF/HAL/VINTF/图形/媒体/DRM 与已闭合的 Test9 remote 证据 | 只读，当前已具备开始条件 |
| M8A ARM32 真 ATV | 保留当前 Kernel/vendor/ABI，先建立 Android 12 AOSP ATV product | M8.0 与 AOSP Android 12 source-lock |
| M8.GMS / M8.INPUT | 分别验证 TV GMS 组件一致性与官方手机遥控 | 不阻塞纯 AOSP ATV 定义，但必须独立标状态 |
| M8B AArch64/multilib | 在稳定 TV product 上迁移 64 位 framework 与硬件栈 | M8A 产品合同稳定、64 位图形栈为 `GO` |
| M8.DRM | 保护并分级验证安全播放与 Netflix | 任何图形/媒体/TEE 相关修改前先完成 N0 |

Test9r2 runtime report 已完成，近期路线已选择 S3：结束 32 位 remote 候选，
不制作 Test9r3/Test10p1；当前 M7 回到 Test8r2 完成 Test9.3，remote 产品化
转入 M8.INPUT。

## 4. 目标与非目标

M8A 目标架构：

```text
保留 UBOX10 64-bit Kernel 5.4.125 与现有 32-bit vendor/userspace ABI
  ├─ 从锁定 Android 12 源码建立 AOSP ATV system/product/system_ext
  ├─ 原生 TV Settings / input / power / network / display / overlays
  ├─ 保持当前 boot0/U-Boot/DTB/DTBO/vendor/vendor_dlkm/TEE
  └─ 将 GMS TV、官方手机遥控与 DRM 作为独立门禁
```

M8B 目标架构：

```text
继承已经稳定的 M8A TV product 合同与 UBOX10 板级启动链
  ├─ 64-bit Framework / ART / zygote64 / system_server
  ├─ 64-bit SurfaceFlinger 与必须同进程加载的图形 SP-HAL
  ├─ arm32 secondary ABI 作为过渡兼容
  └─ 经 Binder/VINTF 验证后可暂留的独立 32-bit vendor service
```

产品目标是从源码继承 Android 12 AOSP ATV product，使 Settings、输入、电源、
网络、显示和遥控器行为真正面向电视。输入验收同时包含实体遥控和 iPhone
官方 Google TV 应用的发现、认证、遥控及文字输入。

以下不是迁移：

- 只改 ABI、`ro.zygote` 或 model/fingerprint；
- 只增加 `lib64` 目录；
- 只更换 64 位 Kernel；
- 只加入 Leanback XML 或更换 Launcher；
- 直接刷其他 H616/H618 板型完整镜像。
- 用自研 UBOX Input 协议/应用替代官方 Google TV 手机遥控目标。

当前也不同时升级 Android 主版本、Kernel、ABI、Vendor、HAL 和设备树。

## 5. M8B 第一硬门槛：64 位图形栈

64 位 SurfaceFlinger/应用不能加载 32 位 EGL、Mali、Gralloc、Mapper 或 HWC。
M8B 的第一项 Go/No-Go 是取得并证明与 UBOX10 H616/Mali-G31、Kernel Mali
ABI、allocator 和 VINTF 匹配的 64 位图形栈。这不阻止 M8A 先用当前 32 位
图形合同建立正确的 ATV product。

最低审计范围：

```text
vendor/lib64/egl/*
vendor/lib64/libMali*
vendor/lib64/hw/gralloc*
vendor/lib64/hw/mapper*
vendor/lib64/hw/hwcomposer*
vendor/bin/hw/android.hardware.graphics.*
allocator / ion / dma-buf / protected buffer
```

图形栈为 `BLOCKED` 时，不进入 64 位 UI 候选；Wi‑Fi、音频等可独立回移植的修复不受此阻塞。

## 6. 供体政策

### BPI H618 Android 12 BSP

公开仓库包含 Android、device、hardware、vendor、kernel、longan 等目录，并给出 H618/Linux 5.4/`-a arm64` 构建命令，因此是当前最高价值供体候选；但 `arm64` 参数本身不能证明 Android userspace 或 64 位 Mali 栈可用。状态：`LIKELY`。

进入下载前必须先完成：

1. 锁定上游 commit；
2. 记录 oversized files 的来源、大小和哈希要求；
3. 锁定 Docker/构建环境和磁盘预算；
4. 原样构建 m4berry 或 m4zero；
5. 以实际 ELF、`TARGET_ARCH/TARGET_2ND_ARCH`、`ro.zygote`、`lib64` 和图形栈判定。

H618 只作为 SoC/BSP/组件参考。不得复制其 boot0、U-Boot、DDR/PMIC、完整 DTB/DTBO、GPIO、Wi‑Fi 模组配置、TEE、密钥或分区表到 UBOX10。

### AOSP Android TV

先锁定 `device/google/atv` 的 `android12-release` commit，以 `aosp_tv_arm`
建立 M8A 参考，再以 `aosp_tv_arm64`/`gsi_tv_arm64` 服务 M8B。提取 product
inheritance、packages、permissions、overlays、VINTF、Settings、输入、网络
和电源差异。remote 专项必须追踪
`com.android.media.tv.remoteprovider`、framework provider package
resource、privapp policy、mDNS/配对与 uinput bridge。不得把当前 `main`
直接当作 Android 12 配置。

### TV GMS 组件结构

MindTheGapps `vendor_gapps_tv` 可用于研究 ARM/ARM64/common/overlay、
proprietary file list、privapp/default permission 与内联构建结构。当前可见
GitHub `baklava` 和 GitLab `vic` 分支均比 Android 12 更新，因此状态只是
`REFERENCE`，不是 Test10p1 donor。

任何 TV GMS 实验必须先锁定精确 Android 12、ABI、package 版本、签名、
shared library、permission、overlay、property、SELinux 和 Setup/Provision
依赖。不存在合法且依赖闭合的 ARM32 集合时标记 `BLOCKED`，不得混装较新
组件、伪造签名/身份或把认证状态写成已完成。

### LineageOS

本次调研未确认到可直接用于 UBOX10 的官方 H616 device tree。LineageOS 只作为 proprietary blob 管理、device tree 结构、提取脚本、SELinux 和可复现构建方法参考。

## 7. M8 分阶段计划

### M8.0：共享证据门

只读输入：

- 官方恢复镜像、Test8r2 配置/镜像、当前设备 ADB；
- Test9r1/Test9r2 的 donor、构建、RRO、runtime 与 Play/GMS 证据；
- boot/vendor_boot/system/product/system_ext/vendor/vendor_dlkm；
- init rc、VINTF、service/lshal、Kernel modules；
- 图形、媒体、Wi‑Fi/BT 与 DRM 相关文件；
- 锁定的 Android 12 AOSP ATV 与 remote framework 源码。

交付物：

- ELF inventory：partition、path、class、machine、interpreter、SONAME、
  NEEDED、SHA-256；
- HAL/service/init/VINTF 与 Kernel module inventory；
- graphics、media、Wi‑Fi/BT 依赖报告；
- current product 对 `aosp_tv_arm` 的 package/property/feature/overlay 差异；
- Test9r2 runtime report、TV GMS component gap 与 remote component map；
- arm64 blockers 和 M8.DRM-0 采集设计。

退出条件：关键组件均能追踪位数、依赖、启动方式和分区；明确
must-be-64、can-remain-32、preserve-security-state、missing-source；
图形栈得出 Go/Blocked/Unknown；Test9 近期路线有唯一决策。此阶段不生成
刷机镜像。

### M8A.1：Android 12 ARM32 ATV 参考与产品差异

锁定 `device/google/atv` 的 `android12-release` commit，构建或静态审计
`aosp_tv_arm`，与 Test8r2 比较：

- product inheritance、partition ownership 与 build properties；
- television/leanback/leanback_only feature；
- TV Settings、Launcher、input、power、network、display 与 media packages；
- framework/product/system_ext overlay；
- permission、shared library、SELinux、VINTF 与 init；
- remoteprovider、provider package resource、default-permissions、
  discovery/pairing 和 uinput；Test9r2 已证明最小必需运行时权限为
  `BLUETOOTH_CONNECT`。

输出 UBOX10 ARM32 ATV product/device tree 草案和分区容量预算，不下载或纳入
Google 专有二进制。

### M8A.2：最小 ARM32 AOSP ATV product

初次候选保持以下输入不变：

- boot0、U-Boot、DDR/PMIC、UBOX10 DTB/DTBO 与 Kernel 5.4.125；
- vendor、vendor_dlkm、Wi‑Fi/BT firmware、遥控/LED 和 TEE/安全材料；
- 32 位 ABI、分区表、AVB 恢复链。

分层出口：

1. `M8A.2a`：system/product/system_ext 离线依赖、权限、SELinux 与 VINTF 闭合；
2. `M8A.2b`：init、zygote32、system_server；
3. `M8A.2c`：SurfaceFlinger、HDMI 最小 UI 与 ADB；
4. `M8A.2d`：TV Settings、Home、实体遥控和重启。

每层只扩大一个变量，失败时回到 Test8r2。AOSP ATV 启动不等于 GMS TV、
官方手机遥控、DRM 或 Netflix 通过。

### M8A.3：ARM32 ATV 产品与硬件验收

顺序：GPU/显示 → 实体遥控 → 音频 → Wi‑Fi → 蓝牙 → 视频硬解 → CEC →
suspend/resume → 应用体验。每个子系统执行基线、依赖、最小移植、离线
检查、单变量候选、压力与交叉回归。

M8.INPUT、M8.GMS 与 M8.DRM 使用独立状态：

- AOSP ATV 可在 `M8.GMS=BLOCKED` 时作为开放产品继续；
- 官方 Google TV iPhone remote/text input 只有发现、配对、遥控、Unicode
  输入和重启复验都通过时才记为 `PASS`；
- Google 商业资格、Play Protect、TV Play Store 与 Netflix 分发不得由 AOSP
  产品启动推断。

### M8B.1：BPI H618 BSP 可复现构建与 64 位供体判定

固定源码和 oversized files 后原样构建，不加入 UBOX10 修改。对产物执行与
M8.0 相同的 inventory。

- `GO`：真实 arm64/multilib userspace、可识别且 Kernel ABI 兼容的 64 位
  图形栈、相对匹配的 Android 12 Vendor 接口。
- `PARTIAL GO`：缺完整 64 位产品，但有可编译 HAL/驱动补丁或有价值的 BSP
  结构。
- `NO-GO`：关键大文件不可得、图形 Kernel ABI 不兼容或构建不可复现。

### M8B.2：最小 AArch64/multilib 启动

继承 M8A 已验证的 ATV product 合同和 UBOX10 板级/安全输入，分层验证：

1. `M8B.2a`：离线 arm64/multilib system/vendor 依赖闭合；
2. `M8B.2b`：init/linker；
3. `M8B.2c`：zygote64/system_server；
4. `M8B.2d`：SurfaceFlinger/64 位 graphics；
5. `M8B.2e`：HDMI 最小 UI 与 ADB。

必须以 UART、ADB、ELF 与进程位数共同证明真实 64 位 userspace。

### M8B.3：64 位硬件与 DRM 回归

使用 M8A.3 的相同顺序和验收脚本，逐项恢复硬件，再执行
M8.INPUT、M8.GMS、M8.DRM 和 Netflix N1。禁止用“32 位版本曾通过”替代
64 位实测。

### M8B.4：Android/Kernel 后续升级

仅在 Android 12 arm64/multilib、硬件、SELinux/VINTF、Netflix N1 和恢复链
稳定后评估。Android Framework 与 Kernel major version 每次只改变一个维度；
Panfrost、Cedrus、GKI 和主线 Kernel 属于长期研究。

### 旧编号映射

| 2026-07-28 编号 | 当前编号 |
|---|---|
| M8.0 当前设备审计 | M8.0 共享证据门 |
| M8.1 H618 供体验证 | M8B.1 |
| M8.2 AOSP ATV 参考 | M8A.1 |
| M8.3 最小 64 位启动 | M8B.2 |
| M8.4 硬件恢复 | M8A.3 / M8B.3 |
| M8.5 原生 ATV 产品 | M8A.2 / M8A.3 |
| M8.6 后续平台 | M8B.4 |

旧编号只用于解释历史提交；新工作项使用 M8A/M8B。

## 8. M8.GMS 与 M8.INPUT

### M8.GMS：一致的 Android TV Google 组件层

M8.GMS 的目标不是“让某个 Play Store APK 能打开”，而是判断是否存在与
Android 12、ARM32/M8A 或 ARM64/M8B、签名和产品 feature 一致的合法组件层。
组件差距报告至少覆盖：

- GMSCore/GSF、Play Store、Google Services Framework 与账号组件；
- TV Setup/Provision、TV Search/Assistant、media shell 与 Remote Service；
- shared library、privapp/default permission、overlay、property 与 SELinux；
- package 签名、版本/SDK/ABI、更新关系和开机顺序；
- Play Store 首页、遥控器导航、搜索/安装、认证显示与 Remote Service 运行时
  依赖。

MindTheGapps TV 仅作为清单与打包结构参考。Google 专有文件由用户合法本地
提供并固定哈希，项目不下载或再分发。缺少兼容输入时允许
`AOSP ATV=PASS, M8.GMS=BLOCKED`，不得伪造设备身份、签名、Play Protect 或
商业资格。

### M8.INPUT：官方 Google TV 手机遥控与文字输入

Test9r1 已证明当前 Android 12 framework 包含 TV remote 服务端骨架，也证明
普通 data-app 安装会被缺失的 required shared library 拒绝；真机还证明
“RRO 文件存在”不等于 Package Manager 实际扫描、注册并应用。Test9r2 随后
证明修正后的 system_ext RRO、provider、Remote v2、官方 iPhone 配对、遥控
和文字输入都可工作；原始 receiver 崩溃只需最小
`BLUETOOTH_CONNECT` 运行时授权即可解除。M8 不继承 Test9r1/Test9r2
二进制，而是继承以下产品合同：

1. 从锁定 Android 12 AOSP 源码构建
   `com.android.media.tv.remoteprovider`；
2. product 原生声明 television/leanback、共享库、provider package resource、
   最小 privapp 权限和 default-permissions；
3. provider watcher 只绑定显式允许且要求
   `BIND_TV_REMOTE_SERVICE` 的 package；
4. 输入事件走 `TvRemoteProvider`/uinput bridge，不伪授予纯 signature 的
   `INJECT_EVENTS`；
5. 默认授予已证实必需的 `BLUETOOTH_CONNECT`；SCAN/ADVERTISE 只有出现
   对应代码路径和真机失败证据时才扩大；
6. 用户本地提供的官方原签名 Google Remote Service 能安装/预置、开机自动
   启动并在重启后保持可发现；
7. iPhone 官方 Google TV 应用能在同一 LAN 发现、配对、遥控和向账号/密码/
   Unicode 文本框输入；
8. Remote Service 对 Play Store/GMS 的 package visibility 与 API 依赖由
   M8.GMS 单独闭合，不能因本地 Remote v2 已工作而跳过；
9. Google 专有 APK 不进入 Git、公共下载或项目重新分发。

若第 5–6 项因 Google TV/GMS TV 商业许可、认证或服务端资格不可获得，状态
记为 `BLOCKED` 并保留证据。项目明确不开发 UBOX Input 作为替代验收。

以下开源客户端只用于分层诊断，不替代 receiver 或最终验收：

- `tronikos/androidtvremote2`：Python/Apache-2.0，适合自动化配对、协议、
  按键、URL 与语音消息测试；
- `odyshewroman/AndroidTVRemoteControl`：Swift/MIT，适合在 iPhone 上独立
  复现 Remote v2；
- `Legvan/tv-remote`：ADB/Web 路线仅作安全隔离的末级参考，默认 LAN 暴露、
  raw shell 和 ASCII 限制不符合当前产品门槛。

完整评估见 `docs/research/tv-gms-remote/README.md`。

## 9. M8.DRM：Netflix 与安全播放

Netflix 分级：

| 等级 | 含义 | 最低证据 |
|---|---|---|
| N0 | 能力审计 | 原厂/Test8r2 的 Play Protect、Widevine、DRM HAL、TEE/OEMCrypto、secure codec、HDCP 和 App 状态 |
| N1 | 基础播放 | 本人合法账号，安装/登录/遥控/稳定播放，实际最大分辨率可复查 |
| N2 | 条件性 HD | L1、secure decoder、protected buffer/path、HDCP 与服务端资格共同实测 |
| N3 | 机会型 4K/HDR | N2 稳定后再验证 secure 4K、HDCP 2.2+、HDR pipeline、电视/线材/套餐 |

Widevine L1、Play Protect、TV Play Store 分发和 Netflix HD/4K 资格互不等价。若只有 L3，稳定 SD 仍可满足 N1；缺 provisioning、密钥或服务端资格时标记外部阻塞。

绝不复制、生成或伪造其他设备的 Widevine/TEE/HDCP 密钥、证书、ESN、secure storage 或认证状态。任何可能影响安全播放的修改前，必须先完成原厂与 Test8r2 的 M8.DRM-0。

## 10. 当前下一步

Test9r2 分层报告和 S3 路线决策已完成；不制作 Test9r3/Test10p1：

1. 用户方便时刷回 Test8r2，当前 M7 进入 Test9.3 应用、AirPlay、现代文件
   管理器和整体回归；
2. 编写 ELF inventory 工具，生成当前图形、媒体、Wi‑Fi/BT、HAL/VINTF 与
   Kernel module 报告；
3. 锁定 `device/google/atv` Android 12 commit，形成 M8A.1 source-lock 与
   product/package/overlay/default-permission 差异合同；
4. 将 Test9r2 的 system_ext RRO、最小 `BLUETOOTH_CONNECT`、6466/6467、
   mDNS、TLS、uinput 和官方 iPhone 证据写入 M8.INPUT provider contract；
5. 以 AOSP ATV 与 MindTheGapps TV 结构形成 Android 12 ARM32
   `tv-gms-component-gap`，包括 Play package visibility，不下载或混装
   专有二进制；
6. 形成 BPI H618 M8B.1 source-lock 方案，不下载大型源码；
7. 设计原厂/Test8r2 DRM 只读采集；若原厂基线需要重新刷机，另行排期，
   不与 Test9.3 回归混做。

## 11. 主要资料

- BPI H618 Android 12 BSP：<https://github.com/BPI-SINOVOIP/BPI-H618-Android12>
- AOSP ATV device：<https://android.googlesource.com/device/google/atv/>
- AOSP ATV Android 12 products：<https://android.googlesource.com/device/google/atv/+/refs/heads/android12-release/products/>
- AOSP Android 12 TV remoteprovider：<https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-12.0.0_r1/media/lib/tvremote/>
- MindTheGapps TV：<https://github.com/MindTheGapps/vendor_gapps_tv>、
  <https://gitlab.com/MindTheGapps/vendor_gapps_tv>
- Remote v2 Python 客户端：<https://github.com/tronikos/androidtvremote2>
- Remote v2 Swift 客户端：<https://github.com/odyshewroman/AndroidTVRemoteControl>
- ADB/Web remote 安全参考：<https://github.com/Legvan/tv-remote>
- GSI/VNDK/VINTF：<https://source.android.com/docs/core/tests/vts/gsi>、<https://source.android.com/docs/core/architecture/vndk>、<https://source.android.com/docs/core/architecture/vintf>
- Android DRM：<https://source.android.com/docs/core/media/drm>
- Android Trusty：<https://source.android.com/docs/security/features/trusty>
- Android 12 CDD：<https://source.android.com/docs/compatibility/12/android-12-cdd>
- AIC8800 社区驱动参考：<https://github.com/radxa-pkg/aic8800>
- LineageOS blob 管理：<https://lineageos.github.io/lineage_wiki/proprietary_blobs.html>
- Netflix 官方帮助：<https://help.netflix.com/en/node/23939>、<https://help.netflix.com/en/node/100226>、<https://help.netflix.com/en/node/124156>、<https://help.netflix.com/en/node/13444>
