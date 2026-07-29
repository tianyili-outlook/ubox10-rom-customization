# 里程碑

- [x] **M0 基线**：保留官方镜像、分区清单和 SHA-256。
- [x] **M1 解包分析**：解析 IMAGEWTY、boot/vendor_boot/dtbo/vbmeta/super 和逻辑分区。
- [x] **M2 设备诊断**：Fastboot 只读通信与 UART 冷启动采集可用。
- [x] **M3 ext4 工具链**：WSL2、e2fsprogs 1.47.2、可复现 fixture 和独立解析器完成。
- [x] **M4 最小测试版构建**：测试版 1 仅删除 UBTunnel，离线验证通过。
- [x] **M5 实机启动验证**：Android、遥控、HDMI 音视频、Wi‑Fi、以太网、蓝牙扫描、高码率视频和目标网站通过；非必要项目按用户需求跳过。
- [x] **M6 分批净化**：测试版 2/3/4/5/6 已实机通过，纯删除阶段完成。
- [ ] **M7 Android TV 产品化**：Test8r2 已完成 Launcher 和蓝牙稳定基线；Test9w1 已退役，Test9r2 remote 技术链通过但因 Play Store 回归不晋级。Test9.3 五项 userdata 应用的源锁、安装、启动、幂等与真实重启自动化门已通过；AirReceiverLite 的 iPhone 发现/镜像/音频也已通过，且确认 Lite 的前台/五分钟限制。当前只剩五项遥控/播放/USB、AnExplorer 体验，以及用户购买完整版后可选的后台/开机复验。
- [ ] **M8.0 共享证据门**：Test9r2 runtime 与 S3 路线决策已闭合；继续盘点 ELF/HAL/VINTF/图形/媒体/Wi‑Fi-BT/DRM，完成 TV GMS gap 与 Android 12 ATV source-lock；不制作迁移镜像。
- [ ] **M8A.1 ARM32 ATV 参考**：以锁定的 `aosp_tv_arm` 建立 UBOX10 product/package/overlay/permission/VINTF 差异和容量预算。
- [ ] **M8A.2–M8A.3 真正 ARM32 AOSP ATV**：保持 UBOX10 boot/kernel/vendor/vendor_dlkm/TEE 与 32 位 ABI，分层启动原生 ATV product并恢复硬件；M8.GMS/M8.INPUT/M8.DRM 独立验收。
- [ ] **M8B.1 64 位供体门**：原样验证 BPI H618 BSP 的真实 arm64/multilib、图形和 Vendor 接口能力。
- [ ] **M8B.2–M8B.3 AArch64 迁移**：继承 M8A 产品合同，分层验证 linker→zygote64→SurfaceFlinger→HDMI/ADB，再逐项完成硬件、官方手机遥控和 Netflix N1 回归。
- [ ] **M8B.4 后续平台**：Android 12 arm64/multilib 稳定后，再单变量评估 Android 主版本、LineageOS 工程和 Kernel 更新。

当前关键节点：**Test8r2 仍是唯一稳定基线且设备已刷回；Test9r2 remote 技术链为 PASS、整机为 PARTIAL，已选择 S3 并关闭 Test9r3/Test10p1。Test9.3 自动化应用门通过、人工门待完成，官方手机遥控产品化转入 M8.INPUT。M8 先以 M8A 建立 ARM32 真 ATV product，再以 M8B 迁移 AArch64；64 位图形 same-process HAL 只阻塞 M8B。M8.INPUT 不以 UBOX Input 替代，M8.GMS 不以混装 APK 或伪造认证通过，Netflix/DRM 原厂与 Test8r2 基线必须在相关修改前建立。**
