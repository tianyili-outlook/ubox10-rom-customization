# 里程碑

- [x] **M0 基线**：保留官方镜像、分区清单和 SHA-256。
- [x] **M1 解包分析**：解析 IMAGEWTY、boot/vendor_boot/dtbo/vbmeta/super 和逻辑分区。
- [x] **M2 设备诊断**：Fastboot 只读通信与 UART 冷启动采集可用。
- [x] **M3 ext4 工具链**：WSL2、e2fsprogs 1.47.2、可复现 fixture 和独立解析器完成。
- [x] **M4 最小测试版构建**：测试版 1 仅删除 UBTunnel，离线验证通过。
- [x] **M5 实机启动验证**：Android、遥控、HDMI 音视频、Wi‑Fi、以太网、蓝牙扫描、高码率视频和目标网站通过；非必要项目按用户需求跳过。
- [x] **M6 分批净化**：测试版 2/3/4/5/6 已实机通过，纯删除阶段完成。
- [ ] **M7 Android TV 产品化**：Test8r2 已完成 Launcher 和蓝牙稳定基线；Test9.1 先解决 Wi‑Fi 扫描可靠性，Test9.2 验证 iPhone 遥控文字输入，Test9.3 完成目标应用、AirPlay、文件管理和整体验收。
- [ ] **M8 未来平台升级**：取得同板型完整 64 位 BSP 与合法匹配的 Google TV 组件栈后，统一处理 arm64/multilib、电视版 Play Store、设备认证和身份一致性。

当前关键节点：**Test8r2 是当前稳定基线。Test9a/Test9b 证明补充 Leanback feature 不能修复当前 Play Store 兼容问题；下一步在 Test8r2 上先采证 Wi‑Fi 扫描故障，网络可靠后再验证 iPhone 文字输入。**
