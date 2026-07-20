# Milestone M6 物理烧录与实机验证调试记录

**日期**：2026-07-20  
**阶段**：M6 受控硬件验证  
**固件基线**：`x12-1024.img` (官方原件)  
**测试对象**：`x12-purified.img` (定制固件)  

---

## 实验 #1：首次烧录尝试

**目标**：验证定制固件是否可烧录。

**结果**：PhoenixCard 停滞在 5-10%，LED 高频蓝绿交替闪烁。

**归因**：全志刷机引擎 (`sprite`) 遭遇 Fatal Error 触发系统挂起。

**对照组**：官方固件同卡同刷成功，LED 低频正常闪烁。证明硬件链路正常。

**结论**：失败。问题来自定制固件内部结构。

---

## 实验 #2：img2simg 稀疏化

**目标**：排查 Sparse 格式兼容性。

**变更**：引入 AOSP `img2simg` 工具，将 lpmake Raw 输出转换为标准 Sparse 格式。

**结果**：现象与实验 #1 完全一致。

**结论**：Sparse 格式兼容性非根因。

---

## 实验 #3：修正 pack_image.py 文件对齐

**目标**：排查固件容器内部文件偏移对齐问题。

**变更**：将 `pack_image.py` 的文件数据对齐因子从 16 字节修改为 1024 字节。

**结果**：✅ PhoenixCard 烧录进度 100% 完成！

**结论**：烧录问题已解决。根本原因为文件偏移未按 1024 字节对齐导致 U-Boot 底层 unaligned block read panic。

---

## 实验 #4：验证系统启动

**目标**：验证定制固件是否能正常启动进入 Android System。

**结果**：
- PhoenixCard 100% 完成（烧录时长超过 10 分钟，官方固件约 5-6 分钟）。
- 设备显示官方 boot logo。
- Boot animation 未出现。
- 设备自动进入 **Android Recovery**。

**Recovery 状态**：
- 红外遥控：无响应。
- USB 键盘：通电但无可用输入。
- 无法在 Recovery 中执行进一步诊断。

**结论**：部分成功。启动链显著推进，但 Android System 未能启动。

---

## 当前状态总结

| 阶段 | 状态 |
|------|------|
| 固件烧录 | ✅ 已解决 |
| Bootloader | ✅ 已执行 |
| Boot logo | ✅ 已显示 |
| Recovery | ✅ 可达 |
| Android System | ❌ 未启动 |

**之前的阻塞项**：❌ 烧录失败 → ✅ 已解决

**当前阻塞项**：⚠️ Android 启动失败（进入 Recovery 而非 System）

---

## 后续行动计划

在再次修改固件之前，需先恢复诊断能力：

1. **优先方法 1：Recovery ADB** — 检查 Recovery 是否暴露 USB 调试接口。
2. **优先方法 2：UART 串口** — 焊接 UBOX10 主板 J21 引脚（波特率 115200），直接抓取 U-Boot/init 异常栈。
3. **优先方法 3：Recovery 日志提取** — 尝试从 Recovery 模式提取 `/cache/recovery/last_log`。

**工程原则**：每次修改只回答一个具体问题，避免同时引入多个变量。