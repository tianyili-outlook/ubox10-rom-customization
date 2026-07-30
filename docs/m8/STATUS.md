# M8 当前状态

更新时间：2026-07-30

阶段：`M8A.2 — ACTIVE`

## 当前设备

| 项目 | 已确认状态 |
|---|---|
| 设备 | UBOX10 / I12 Pro Max，Allwinner H616 + AXP313A |
| 内存 / 存储 | 4 GiB DDR3L / 64 GB eMMC |
| 运行系统 | Test8r2，另有用户安装的日常软件 |
| 访问 | ADB 可用 |
| Android | Android 12 / SDK 31 |
| 架构 | 64 位 Kernel + 纯 ARM32 userspace |
| 图形 | 当前 32 位 Mali-G31 / Gralloc / Mapper / HWC 可工作 |
| DRM | Widevine 16.1 L3；HDCP `NONE`；未发现 secure decoder |
| 稳定回退 | Test8r2；官方 `x12-1024.img` 为最终恢复源 |

证据入口：

- [硬件身份](research/current-device/hardware-identity.md)
- [运行时基线](research/current-device/runtime-baseline.md)
- [ELF 依赖摘要](research/current-device/elf-dependency-summary.md)
- [M8B 阻塞项](research/current-device/arm64-blockers.md)
- [DRM / Netflix 结论](research/drm-netflix/netflix-feasibility-verdict.md)

## 阶段进度

- `M8.0 COMPLETE`：现有证据已经足够开始 M8A；未做完的轻量运行时快照不再
  阻塞构建。
- `M8A.1 COMPLETE`：Android 12 `aosp_tv_arm` 来源、产品差异、overlay/
  permission/VINTF、分区预算和 UBOX10 product 计划已锁定。
- `M8A.2 ACTIVE`：尚未同步完整 AOSP，也没有生成 M8 candidate。
- `M8A.3 PENDING`：等待最小 TV UI candidate。
- `M8B PARKED`：0 个 AArch64 userspace ELF；没有可用 64 位图形供体。

## 信息是否足够

当前硬件识别和 Test8r2 软件基线足以继续 M8A，不需要拆散热器、继续猜芯片
丝印或进行泛化硬件搜索。

仍有价值但不是 M8A.2a 硬阻塞的 ADB 信息：

- `/linkerconfig/`；
- 活动 APEX、boot/system_server classpath；
- uses-library；
- 基本 `checkvintf` 输出；
- 首次 M8A 刷写前若方便，采集官方 ROM DRM 对照。

互联网调研已足够支持当前结构。后续只在出现具体构建/启动错误、选择 64 位
供体或锁定新的 Google/Remote 组件时做针对性查询，不继续泛搜 GSI/BSP。

## 当前阻塞

完整 Android 12 checkout 与构建需要至少 400 GB 可用的 Linux/ext4 构建卷。
当前 C/D 盘空间不足，因此没有下载源码或启动大型构建。

## 下一动作

准备构建卷后，按
[source-lock](research/m8a-atv-arm32/source-lock.md) 同步 Android 12，
建立 UBOX10 ARM32 ATV product，进入 `M8A.2a` 离线构建。

具体任务只看 [TODO.md](TODO.md)。
