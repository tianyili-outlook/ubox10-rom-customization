# M8：AArch64、AOSP Android TV 与 Netflix/DRM 迁移计划

研究快照：2026-07-28。本文吸收用户提供的后续调研，作为 M8 的当前架构计划；它不授权下载大型源码、复制闭源安全材料或制作 64 位刷机候选。

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
| 手机遥控 framework | 已有 TvRemoteService/provider watcher/uinput bridge，缺 product 集成 | CONFIRMED |
| 手机遥控候选 | Test9r1 从 Test8r2 构建并通过离线验证，真机待测 | UNKNOWN |
| Play Protect | Play Store 无可见认证项；实际认证结论未取得 | UNKNOWN |
| Widevine/TEE/HDCP/secure decoder | 尚无完整基线 | UNKNOWN |
| Netflix | 安装、登录、播放和最大分辨率尚未建立基线 | UNKNOWN |

## 3. 两条并行主线

| 产品体验线 | 架构研究线 |
|---|---|
| Test9r1 验证官方 Google TV iPhone 遥控与文字输入 | M8.0 只读盘点当前 ELF/HAL/VINTF/DRM |
| Test9.3 完成应用、AirPlay、文件管理和整体验收 | M8.1 锁定并审计 H618 BSP 供体 |
| 当前 32 位产品完成最终交叉回归 | M8.2 建立 Android 12 AOSP ATV 差异基线 |

M8.0 可以在 Test9r1 刷测期间推进；M8.3 之后的可刷写迁移必须等待
M8.0–M8.2 的 Go/No-Go 结论。

## 4. 目标与非目标

首选目标架构：

```text
保留 UBOX10 64-bit Kernel 5.4.125 与板级启动链
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

## 5. 第一硬门槛：64 位图形栈

64 位 SurfaceFlinger/应用不能加载 32 位 EGL、Mali、Gralloc、Mapper 或 HWC。M8 的第一项 Go/No-Go 是取得并证明与 UBOX10 H616/Mali-G31、Kernel Mali ABI、allocator 和 VINTF 匹配的 64 位图形栈。

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

使用与 Android 12 匹配的 `device/google/atv` tag 建立 `aosp_tv_arm64`、
`gsi_tv_arm64` 和必要的 arm32 对照，提取 product inheritance、packages、
permissions、overlays、VINTF、Settings、输入、网络和电源差异。remote
专项必须追踪 `com.android.media.tv.remoteprovider`、framework provider
package resource、privapp policy、mDNS/配对与 uinput bridge。不得把当前
`main` 直接当作 Android 12 配置。

### LineageOS

本次调研未确认到可直接用于 UBOX10 的官方 H616 device tree。LineageOS 只作为 proprietary blob 管理、device tree 结构、提取脚本、SELinux 和可复现构建方法参考。

## 7. M8 分阶段计划

### M8.0：当前设备 32/64 位与依赖审计

只读输入：

- 官方恢复镜像、Test8r2 配置/镜像、当前设备 ADB；
- Test9r1 的 donor 审计、普通安装失败、system 集成和真机结果；
- boot/vendor_boot/system/product/vendor/vendor_dlkm；
- init rc、VINTF、service/lshal、Kernel modules；
- 图形、媒体、Wi‑Fi/BT 与 DRM 相关文件。

交付物：

- ELF inventory：partition、path、class、machine、interpreter、SONAME、NEEDED、SHA-256；
- HAL/service/init/VINTF inventory；
- Kernel module inventory；
- graphics、media、Wi‑Fi/BT 依赖报告；
- arm64 blockers 与 donor component map；
- M8.DRM-0 基线。

退出条件：关键组件均能追踪位数、依赖、启动方式和分区；明确 must-be-64、can-remain-32、preserve-security-state、missing-source；图形栈得出 Go/Blocked/Unknown。此阶段不生成刷机镜像。

### M8.1：BPI H618 BSP 可复现构建与供体判定

固定源码和 oversized files 后原样构建，不加入 UBOX10 修改。对产物执行与 M8.0 相同的 inventory。

- `GO`：真实 arm64/multilib userspace、可识别的兼容 64 位图形栈和相对匹配的 Android 12 Vendor 接口。
- `PARTIAL GO`：缺完整 64 位产品，但有可编译 HAL/驱动补丁或有价值的 BSP 结构。
- `NO-GO`：关键大文件不可得、图形 Kernel ABI 不兼容或构建不可复现。

### M8.2：Android 12 AOSP ATV 参考构建

锁定 Android 12 tag，构建 arm64 ATV/GSI 参考并与 Test8r2 比较。输出 UBOX10
自有 ATV product/device tree 草案；TV 化不再以 Play Store 页面为判据。
remoteprovider 必须由源码构建并通过 shared-library/API 边界检查，不从旧
Test9r1 镜像反向复制生成物。

### M8.3：最小 64 位启动

初次实验保持 boot0、U-Boot、UBOX10 DTB/DTBO、Kernel 5.4.125、DDR/PMIC、分区表、Wi‑Fi/BT firmware、遥控/LED、TEE 与安全材料不变。

分层候选：

1. M8.3a：离线 arm64 system/vendor 依赖闭合；
2. M8.3b：init/linker；
3. M8.3c：zygote64/system_server；
4. M8.3d：SurfaceFlinger/graphics；
5. M8.3e：HDMI 最小 UI 与 ADB。

必须以 UART、ADB、ELF 与进程位数共同证明真实 64 位 userspace。

### M8.4：逐项恢复硬件

顺序：GPU/显示 → 实体遥控 → Google TV iPhone remote/text input → 音频 →
Wi‑Fi → 蓝牙 → 视频硬解 → CEC → suspend/resume → DRM/secure playback →
Netflix N1。每个子系统执行基线、依赖、最小移植、离线检查、单变量候选、
压力与交叉回归。

### M8.5：UBOX10 原生 AOSP ATV 产品

建立 device tree、ATV product inheritance、TV
overlays/Settings/Launcher/input/power/network/display、SELinux、
`proprietary-files.txt` 和 Vendor 提取流程；执行适用 CTS/VTS/GSI。即使
没有 GMS TV 商业认证，也应能作为开放 AOSP ATV 使用；但官方 Google TV
手机遥控目标若受 GMS TV 许可/签名阻塞，必须单独标记 `BLOCKED`，不能用
“AOSP ATV 已启动”代替通过。

### M8.6：Android/Kernel 后续升级

仅在 Android 12 arm64/multilib、硬件、SELinux/VINTF、Netflix N1 和恢复链稳定后评估。Android Framework 与 Kernel major version 每次只改变一个维度；Panfrost、Cedrus、GKI 和主线 Kernel 属于长期研究。

## 8. M8.INPUT：官方 Google TV 手机遥控与文字输入

Test9r1 已证明当前 Android 12 framework 包含 TV remote 服务端骨架，也证明
普通 data-app 安装会被缺失的 required shared library 拒绝。M8 不继承
Test9r1 二进制，而是继承以下产品合同：

1. 从锁定 Android 12 AOSP 源码构建
   `com.android.media.tv.remoteprovider`；
2. product 原生声明 television/leanback、共享库、provider package resource
   和最小 privapp 权限；
3. provider watcher 只绑定显式允许且要求
   `BIND_TV_REMOTE_SERVICE` 的 package；
4. 输入事件走 `TvRemoteProvider`/uinput bridge，不伪授予纯 signature 的
   `INJECT_EVENTS`；
5. 用户本地提供的官方原签名 Google Remote Service 能安装/预置并正常启动；
6. iPhone 官方 Google TV 应用能在同一 LAN 发现、配对、遥控和向账号/密码/
   Unicode 文本框输入；
7. Google 专有 APK 不进入 Git、公共下载或项目重新分发。

若第 5–6 项因 Google TV/GMS TV 商业许可、认证或服务端资格不可获得，状态
记为 `BLOCKED` 并保留证据。项目明确不开发 UBOX Input 作为替代验收。

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

Test9r1 刷测期间只推进无写设备风险的 M8.0：

1. 建立 M8 研究索引和数据脱敏规则；
2. 编写 ELF inventory 工具；
3. 生成当前图形、媒体、Wi‑Fi/BT 组件清单；
4. 形成 BPI H618 source-lock 方案，不下载大型源码；
5. 将 Test9r1 的 remoteprovider/RRO/权限和真机日志结论写入 M8.INPUT
   component map；
6. 设计原厂/Test8r2 DRM 只读采集；若原厂基线需要重新刷机，必须另行排期，
   不与 Test9r1 回归混做。

## 11. 主要资料

- BPI H618 Android 12 BSP：<https://github.com/BPI-SINOVOIP/BPI-H618-Android12>
- AOSP ATV device：<https://android.googlesource.com/device/google/atv/>
- AOSP Android 12 TV remoteprovider：<https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-12.0.0_r1/media/lib/tvremote/>
- GSI/VNDK/VINTF：<https://source.android.com/docs/core/tests/vts/gsi>、<https://source.android.com/docs/core/architecture/vndk>、<https://source.android.com/docs/core/architecture/vintf>
- Android DRM：<https://source.android.com/docs/core/media/drm>
- Android Trusty：<https://source.android.com/docs/security/features/trusty>
- Android 12 CDD：<https://source.android.com/docs/compatibility/12/android-12-cdd>
- AIC8800 社区驱动参考：<https://github.com/radxa-pkg/aic8800>
- LineageOS blob 管理：<https://lineageos.github.io/lineage_wiki/proprietary_blobs.html>
- Netflix 官方帮助：<https://help.netflix.com/en/node/23939>、<https://help.netflix.com/en/node/100226>、<https://help.netflix.com/en/node/124156>、<https://help.netflix.com/en/node/13444>
