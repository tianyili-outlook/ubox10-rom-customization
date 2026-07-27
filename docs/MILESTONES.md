# 里程碑

- [x] **M0 基线**：保留官方镜像、分区清单和 SHA-256。
- [x] **M1 解包分析**：解析 IMAGEWTY、boot/vendor_boot/dtbo/vbmeta/super 和逻辑分区。
- [x] **M2 设备诊断**：Fastboot 只读通信与 UART 冷启动采集可用。
- [x] **M3 ext4 工具链**：WSL2、e2fsprogs 1.47.2、可复现 fixture 和独立解析器完成。
- [x] **M4 最小测试版构建**：测试版 1 仅删除 UBTunnel，离线验证通过。
- [x] **M5 实机启动验证**：Android、遥控、HDMI 音视频、Wi‑Fi、以太网、蓝牙扫描、高码率视频和目标网站通过；非必要项目按用户需求跳过。
- [x] **M6 分批净化**：测试版 2/3/4/5/6 已实机通过，纯删除阶段完成。
- [ ] **M7 Android TV 产品化**：替换 Launcher，加入目标应用并完成整体验证。

当前关键节点：**Test8r2 已恢复 ContactsProvider，并通过端到端自动验证和真机验收；蓝牙保持开启、可扫描且零崩溃。Test8r2 是当前稳定基线，下一步进入 Test9 体验与应用完善。**
