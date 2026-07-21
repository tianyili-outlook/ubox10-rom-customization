# 待办事项

## 当前：M6 启动故障诊断与 Recovery ADB 启用

### 高优先级
- [x] 验证 Recovery 是否有可用输入方式（结果：红外/键盘均无响应，未暴露 ADB）。
- [x] 强制开启 Recovery ADB 调试（实验 #5 & #6）：
  - [x] 编写 `scripts/enable-recovery-adb.py` 解包、修改 `prop.default`、重打包签名并输出 `boot.img`。
  - [x] 编译全局禁用 AVB 校验的 vbmeta 镜像（flags=2，结果：触发 U-Boot 引导死锁）。
  - [x] 回撤 flags=2 仅保留 ADB 内核（结果：依然极速 Bootloop，说明核心问题在重新打包的 `boot.img` 自身）。
- [x] 对照组封包测试（实验 #7）：
  - [x] 保持相同封包与签名链路，原封不动还原原厂 ramdisk 编译 `boot.img` 排除变量。
  - [x] 物理烧录验证（结果：依然极速 Bootloop，排除属性原因，确诊为 LZ4 压缩/封包不兼容）。
- [x] 对照组优化编译与验证（实验 #8）：
  - [x] 启用高压缩模式且移除 0 字节终止块，还原原厂 ramdisk 输出测试版 `boot.img`。
  - [x] 物理烧录验证（结果：成功开机！稳定在躺倒机器人界面，确诊原因为 0 字节块/体积冲突）。
- [x] Recovery ADB 跃变触发注入与验证（实验 #9）：
  - [x] 重新启用 `prop.default` 调试属性并在 `init.recovery.sun50iw9p1.rc` 注入 `none -> adb` 跃变。
  - [x] 物理烧录验证（结果：依然只看到 `sunxi` 裸口，ADB 无设备，原因为 user 固件限制及 SELinux Enforcing 导致 adbd Crash）。
- [x] 命令式 ConfigFS 强绑定与 SELinux 宽容注入（实验 #10）：
  - [x] 在 `prop.default` 中修改 `'ro.build.type': 'userdebug'` 解除 user 限制。
  - [x] 在 `init.recovery.sun50iw9p1.rc` 中写入完全手动的命令式 ConfigFS 强绑定序列。
  - [x] 物理烧录验证（结果：还是 `sunxi` 裸口，确诊为 `vendor_boot.img` 里的 rc 同名脚本发生了挂载覆写，将我们 boot 中的修改完全盖掉了）。
- [x] 厂商引导 vendor_boot 联动重构与异步绑定优化（实验 #11 & #11.1）：
  - [x] 联动修改脚本，对 `vendor_boot` 里的 `init.recovery.sun50iw9p1.rc` 写入相同的强绑和 OTG 切换代码，并使用原厂 Salt 进行 AVB 签名。
  - [x] 修复 ConfigFS 规范时序漏洞，将 UDC 绑定移至 `on property:sys.usb.ffs.ready=1` 异步触发器，并顺次兼容 `sunxi-udc` 等多个全志 UDC 名称。
  - [x] 升级主 `init.rc` 强行硬编码 import 并移除了 `adbd` 服务定义中的崩溃参数 `--root_seclabel`。
- [ ] **物理烧录 Experiment #11.1 联动调试固件并提取日志（当前待办）**：
  - [ ] 烧录并通电开机，确认稳定进入机器人界面。
  - [ ] 电脑端通过 USB OTG 连通，运行 `adb devices` 检测。
  - [ ] 提取崩溃日志（`last_log`）和内核日志（`dmesg`）定位系统未启动根因。

### 中优先级
- [ ] 硬件功能验证（Wi-Fi、蓝牙、以太网、HDMI、红外遥控）。
- [ ] 系统稳定性测试。

### 低优先级
- [ ] 仓库与工具链清理。
- [ ] 安装包打包脚本优化。

## 已完成

- [x] **M5 固件封装与伴生校验和重算** (2026-07-19)
- [x] **M4 ROM 重打包与 AVB 签名** (2026-07-19)
- [x] **M3/M3+ 反定制裁剪与预装** (2026-07-19)
- [x] **M2 分区与启动链审计** (2026-07-19)
- [x] **M1 只读容器清单** (2026-07-19)
- [x] **M0 原始镜像基线** (2026-07-19)

## 实验记录

- [x] **实验 #1** (2026-07-20)：首次刷写 → PhoenixCard 停滞在 5-10%，LED 高频闪烁。
- [x] **实验 #2** (2026-07-20)：引入 img2simg 稀疏化 → 现象不变，排除 Sparse 格式为根因。
- [x] **实验 #3** (2026-07-20)：修正 pack_image.py 1024 字节对齐 → PhoenixCard 100% 完成！
- [x] **实验 #4** (2026-07-20)：验证系统启动 → 设备进入 Recovery，Android System 未启动。
- [x] **实验 #5** (2026-07-20)：Recovery ADB 强启 & flags=2 绕过 → 设备极速无限黑屏重启（Bootloop）。
- [x] **实验 #6** (2026-07-20)：回撤 flags=2 保持 ADB boot.img → 依然无限重启，排除 flags=2 因素。
- [x] **实验 #7** (2026-07-20)：对照组（原样还原 ramdisk）→ 编译完成，等待刷机验证。
