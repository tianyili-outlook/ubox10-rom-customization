# 里程碑

- [x] **M0 基线**：保留官方镜像、分区清单和 SHA-256。
- [x] **M1 解包分析**：解析 IMAGEWTY、boot/vendor_boot/dtbo/vbmeta/super 和逻辑分区。
- [x] **M2 设备诊断**：Fastboot 只读通信与 UART 冷启动采集可用。
- [x] **M3 ext4 工具链**：WSL2、e2fsprogs 1.47.2、可复现 fixture 和独立解析器完成。
- [x] **M4 最小测试版构建**：测试版 1 仅删除 UBTunnel，离线验证通过。
- [x] **M5 实机启动验证**：Android、遥控、HDMI 音视频、Wi‑Fi、以太网、蓝牙扫描、高码率视频和目标网站通过；非必要项目按用户需求跳过。
- [x] **M6 分批净化**：测试版 2/3/4/5/6 已实机通过，纯删除阶段完成。
- [ ] **M7 Android TV 产品化**：Test8r2 已完成 Launcher 和蓝牙稳定基线；Test9w1 Wi‑Fi 假设已退役，当前 Test9r1 验证官方 Google TV iPhone 遥控/文字输入，之后完成目标应用、AirPlay、文件管理和整体验收。
- [ ] **M8.0 当前架构审计**：盘点 ELF/HAL/VINTF/图形/媒体/Wi‑Fi-BT/DRM，明确 64 位 blocker；与 Test9 只读并行。
- [ ] **M8.1–M8.2 供体与参考构建**：原样验证 BPI H618 BSP 的真实 arm64/图形能力，并建立 Android 12 AOSP ATV 产品差异基线。
- [ ] **M8.3 最小 64 位启动**：保持 UBOX10 底层启动链、Kernel、板级配置和安全材料，分层验证 linker→zygote64→SurfaceFlinger→HDMI/ADB。
- [ ] **M8.4–M8.5 硬件与 AOSP ATV 产品化**：逐项恢复硬件、M8.INPUT 官方 Google TV 手机遥控与 Netflix N1，建立 UBOX10 原生 ATV device/product tree。
- [ ] **M8.6 后续平台**：Android 12 arm64 稳定后，再单变量评估 Android 主版本、LineageOS 工程和 Kernel 更新。

当前关键节点：**Test8r2 仍是唯一稳定基线；Test9r1 已离线通过并等待真机 official Google TV iPhone remote/text input 验收，Test9w1 不再使用。与此同时只推进 M8.0 只读 inventory，不制作 64 位候选。64 位迁移第一硬门槛是 H616/Mali-G31 的 64 位图形 same-process HAL；M8.INPUT 不以 UBOX Input 替代，Netflix/DRM 原厂与 Test8r2 基线必须在相关修改前建立。**
