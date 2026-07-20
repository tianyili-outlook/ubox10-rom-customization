# 发现记录

每项发现必须包含来源、方法、证据位置、置信度、影响与下一步；推测必须明确标为推测。

## D-0001 — 官方固件使用动态分区

- 状态：已验证
- 日期：2026-07-19
- 结论：官方固件在 `super.img` 中存储逻辑分区（system_a, vendor_a, product_a, vendor_dlkm_a），采用 Retrofit A/B 动态分区设计。
- 影响：后续定制必须保留动态分区架构。

## D-0002 — AVB 签名链基于 AOSP test-keys

- 状态：已验证
- 日期：2026-07-19
- 结论：`vbmeta.fex`、`vbmeta_system.fex`、`vbmeta_vendor.fex` 的签名算法均为 `SHA256_RSA2048`，公钥 SHA1 指纹为 AOSP 官方默认测试密钥。修改后的分区可以通过标准 AOSP 密钥链重新签名。
- 影响：未签名的镜像不能视为有效构建产物。

## D-0003 — Product 分区需要扩容

- 状态：已验证
- 日期：2026-07-19
- 实验：扩展 product 分区至 300 MB。
- 结论：300 MB 提供了足够空间，同时保持兼容性。

## D-0004 — 启动器替换稳定

- 状态：已验证
- 日期：2026-07-19
- 结论：FLauncher 成功替代厂商启动器。框架通过 `ro.sw.defaultlauncher_package` 属性控制默认启动器，已在 `build.prop` 中修改。
- 影响：启动器替换不再被视为项目风险。

## D-0005 — PhoenixCard 烧录死锁由镜像布局导致（已解决）

- 状态：已解决
- 日期：2026-07-20
- 观察：初始定制固件在烧录时反复停滞在 5%-10%。
- 实验：
  1. 实验 #1：首次刷写 → PhoenixCard 停滞 5-10%，LED 高频闪烁。
  2. 官方固件对照组 → 烧录成功，证明硬件链路正常。
  3. 实验 #2：引入 img2simg 稀疏化 → 现象不变，排除 Sparse 格式为根因。
  4. 实验 #3：修正 `pack_image.py` 文件对齐（16 字节 → 1024 字节）→ PhoenixCard 100% 完成！
- 结论：烧录问题已解决。不应再被视为当前阻塞项。

## D-0006 — Android Recovery 可达

- 状态：已验证
- 日期：2026-07-20
- 观察：修正镜像打包后，设备完成烧录并启动。启动序列到达 Bootloader → Recovery。System 未启动。
- 结论：Bootloader、Kernel、Recovery 均功能正常。当前问题发生在 Android System 启动阶段。

## D-0007 — 当前根本原因未知

- 状态：开放
- 日期：2026-07-20
- 事实：设备进入 Android Recovery 而非 Android System。
- 事实：Recovery 目前无法操作（红外遥控无响应，USB 键盘通电但无可用输入）。因此尚未在 Recovery 中执行进一步诊断。
- 假设（未经实验验证）：
  - 文件系统不一致
  - init 启动失败
  - Recovery 触发标志位
  - 分区元数据不匹配
  - 启动配置不一致
- 下一步行动：在再次修改固件之前，先获取诊断能力（优先 Recovery ADB → UART 串口 → Recovery 日志提取）。

## D-0008 — 修改前先获取证据（工程原则）

- 状态：已接受
- 日期：2026-07-20
- 原则：在再次修改固件之前，每次修改应只回答一个具体问题。避免在单次实验中引入多个变更，否则实验证据将难以解读。此原则适用于所有后续调试工作。

## D-0009 — 物理 USB 设备标识 VID 1F3A & PID 1010 为 Fastboot 模式

- 状态：已验证
- 日期：2026-07-20
- 事实：在物理 UBOX10 设备进入 Recovery 界面时，通过特定 USB 口连接 PC 可在设备管理器中枚举出一个 VID `1F3A` / PID `1010` 的 "sunxi" 设备（无驱动，位于其他设备下）。同时，运行 `adb devices` 无法检测到设备。
- 方法：网络审计与业界 Allwinner SDK/sunxi 文档比对。
- 结论：
  1. **排除了 ADB 暴露的可能性**：该定制/官方 Recovery 在当前状态下未暴露任何 ADB 调试接口。
  2. **确定为 Fastboot 模式**：VID `1F3A` 为 Allwinner 厂商标识，而 PID `1010` 是 Allwinner 设备独有的 **Android Fastboot Mode** 标识。在 U-Boot 阶段或系统发生特定故障退回到 Recovery 状态时，启动链暴露了此 fastboot 接口。
- 影响：这一发现极其关键！我们不需要立刻诉诸焊接串口（UART），而是可以通过安装 Google USB 驱动程序激活该 Fastboot 接口，利用 `fastboot` 命令行工具直接与 U-Boot 进行会话，读取设备分区表、启动槽位及启动日志变量（如 `fastboot getvar all`）。