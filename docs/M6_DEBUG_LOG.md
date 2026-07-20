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
- 屏幕表现：黑底，绿色 Android 机器人躺倒，后盖打开，无文字，无 "No command" 提示，无 Recovery 菜单。
- 红外遥控：无响应。
- USB 键盘：通电（指示灯亮）但无可用输入。
- **USB 连线测试**：通过特定 USB 口（OTG 口）连接 PC 时，Windows 成功检测到新设备插入。设备管理器显示 `VID = 1F3A`、`PID = 1010`，设备名为 `sunxi`（位于“其他设备”下，缺失驱动）。
- **ADB 尝试**：运行 `adb devices` 显示为空（未检测到任何 ADB 设备）。

**结论**：部分成功。启动链显著推进。当前 Recovery 模式未启用 ADB 接口，但通过 USB 暴露了 Allwinner 独有的 **Android Fastboot Mode** (`1F3A:1010`) 接口。

---

## 当前状态总结

| 阶段 | 状态 | 备注 |
|------|------|------|
| 固件烧录 | ✅ 已解决 | 进度达到 100% 并顺利完成写入 |
| Bootloader | ✅ 已执行 | 正常加载引导链 |
| Boot logo | ✅ 已显示 | 屏幕可显示安博官方 LOGO |
| Recovery | ✅ 可达 | 自动进入躺倒机器人界面（但无菜单且无法交互） |
| USB 调试 | ⚠️ 暴露 | 未暴露 ADB (❌)；但成功暴露 Fastboot Mode (✅, 1F3A:1010) |
| Android System | ❌ 未启动 | 未加载开机动画，未能正常进入系统 |

**之前的阻塞项**：❌ 烧录失败 → ✅ 已解决

**当前阻塞项**：⚠️ Android 启动失败（进入 Recovery 而非 System），调试交互受限

---

## 实验 #5：Recovery ADB 注入与全局 AVB 绕过 (flags=2)

**目标**：强制激活 Recovery 模式下的 ADB 通道，并尝试通过禁用 AVB 校验直接进入系统。

**变更**：
1. 编写 `scripts/enable-recovery-adb.py`，解包 `boot.fex` 并解压 ramdisk，修改 `prop.default` 强制写入 `ro.debuggable=1`、`ro.secure=0`、`persist.sys.usb.config=adb`、`sys.usb.config=adb`。重新采用 8 MB 块大小压缩为全志 Legacy LZ4 格式，利用 `mkbootimg.py` 重建 `boot.img` 并用 `avbtool.py` 签名。
2. 修改 `scripts/repack-rom.py`，在生成所有 `vbmeta.img` 时追加 `--flags 2` 参数，关闭全局分区校验。

**结果**：设备开机后，在“白底安博科技” LOGO 界面极速黑屏，随后再次亮屏显示 LOGO，陷入**无限快速重启（Bootloop）**。USB 连接在该状态下随供电复位而断续，无法建立通信。

**结论**：失败。U-Boot 或内核在极早期阶段发生了崩溃重启。

---

## 实验 #6：回撤 flags=2 参数

**目标**：排查是否因 U-Boot 拒绝 `flags=2` 的 `vbmeta` 声明而触发重启。

**变更**：在 `scripts/repack-rom.py` 中移除所有 `--flags 2` 参数（恢复默认的 `flags=0`），但保留修改了 `prop.default` 的 `boot.img`。

**结果**：设备依然保持**无限快速重启**状态，表现与实验 #5 完全一致。

**结论**：失败。快速重启与 `vbmeta` 的 `--flags 2` 无关，根因锁定在**重编译的 `boot.img` 自身**（包括重打包、压缩格式或属性改动）。

---

## 实验 #7：对照组——还原原厂 Ramdisk 内容

**目标**：定位是 `boot.img` 重新打包压缩格式的问题，还是 `prop.default` 安全属性修改导致 userspace `init` 崩溃。

**变更**：修改 `scripts/enable-recovery-adb.py`，**注释掉所有属性修改逻辑**，使用原厂 ramdisk 内容通过我们的 CPIO 序列化、LZ4 压缩和签名管线输出完全相同的控制组 `boot.img`。

**结果**：固件编译完成并校验通过，等待物理烧录验证。

---

## 当前状态总结

| 阶段 | 状态 | 备注 |
|------|------|------|
| 固件烧录 | ✅ 已解决 | 进度达到 100% 并顺利完成写入 |
| Bootloader | ✅ 已执行 | 正常加载引导链 |
| Boot logo | ✅ 已显示 | 屏幕可显示安博官方 LOGO |
| Recovery | ⚠️ 倒退 | 实验 #4 可达，但由于引入重建的 `boot.img` 导致发生 Bootloop |
| USB 调试 | ❌ 阻塞 | 设备处于 Bootloop 复位中，无法建立连接 |
| Android System | ❌ 未启动 | 未加载开机动画，未能正常进入系统 |

**当前阻塞项**：⚠️ 重建的 `boot.img` 导致系统在极早期引导阶段（U-Boot 解析或内核挂载 initramfs 阶段）发生 Crash 重启。

---

## 后续行动计划

1. **优先执行对照组（实验 #7）物理烧录**：
   - 验证如果 ramdisk 内容完全不改，重打包的固件能否恢复到不重启状态。
   - **若恢复（机器人正常显示）**：说明压缩格式兼容，无限重启是因为 `prop.default` 中的属性修改（如 `ro.secure=0`）触发了 Android 12 安全锁死，我们需要改用在 `init.rc` 中直接拉起 `adbd` 服务而不改动全局安全属性的策略。
   - **若依然重启**：说明是 `lz4` 重新压缩的参数格式（如块尾 0 填充、压缩比等）不被 Linux 内核引导头识别。我们将直接更换为最通用的 `gzip` 压缩格式重建 `boot.img`。
2. **记录结果与迭代**：根据实验 #7 的表现，立刻采取对应的软件调整，确保 Recovery ADB 的最终就绪。