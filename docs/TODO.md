# 待办事项

## 当前：M6 系统启动故障调查 (Boot Failure Investigation)

### 高优先级
- [ ] 确定 Android 为何进入 Recovery 而非 System。
- [ ] 获取诊断日志（尝试 Recovery ADB / UART / Recovery 日志提取）。
- [ ] 验证 Recovery 是否有可用输入方式。
- [ ] 定位根本原因。

### 中优先级
- [ ] 硬件功能验证（Wi-Fi、蓝牙、以太网、HDMI、红外遥控）。
- [ ] 系统稳定性测试。

### 低优先级
- [ ] 文档整理与仓库清理。
- [ ] 安装包优化。

## 已完成

- [x] **M5 固件封装与伴生校验和重算** (2026-07-19)
  - [x] 编写 `tools/pack_image.py` 将 super.img 和重签的 vbmeta 装回 Allwinner 格式固件容器。
  - [x] 调用自研算法重新计算所有分区伴生校验文件（`V*.fex`）。
  - [x] 修复 1024 字节对齐问题，解决 U-Boot unaligned read panic。
- [x] **M4 ROM 重打包与 AVB 签名** (2026-07-19)
  - [x] 选择并锁定适合 Windows 平台的 ext4 镜像生成工具（使用 `make_ext4fs.exe`）。
  - [x] 将已净化修改的逻辑卷目录重新打包编译为 raw ext4 分区映像。
  - [x] 使用 `avbtool.py` 为重新生成的逻辑分区映像计算并追加 AVB Hashtree 校验页。
  - [x] 使用 `lpmake` + `img2simg` 重新构建 super 逻辑分区映像。
- [x] **M3/M3+ 反定制裁剪与预装** (2026-07-19)
  - [x] APK 审计与分级裁剪（P0/P1），删除 14 个应用释放 298.7 MB。
  - [x] 启动器替换为 FLauncher，build.prop 属性修改。
  - [x] 预装应用集成：SmartTube、Gboard、Kodi、VLC、LocalSend。
- [x] **M2 分区与启动链审计** (2026-07-19)
- [x] **M1 只读容器清单** (2026-07-19)
- [x] **M0 原始镜像基线** (2026-07-19)

## 实验记录

- [x] **实验 #1** (2026-07-20)：首次刷写 → PhoenixCard 停滞在 5-10%，LED 高频闪烁。
- [x] **实验 #2** (2026-07-20)：引入 img2simg 稀疏化 → 现象不变，排除 Sparse 格式为根因。
- [x] **实验 #3** (2026-07-20)：修正 pack_image.py 1024 字节对齐 → PhoenixCard 100% 完成！
- [x] **实验 #4** (2026-07-20)：验证系统启动 → 设备进入 Recovery，Android System 未启动。
