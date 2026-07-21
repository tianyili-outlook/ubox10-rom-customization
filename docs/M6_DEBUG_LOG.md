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

**结果**：设备开机后依然发生**无限快速重启（Bootloop）**，现象无任何变化。

**结论**：失败。由于 ramdisk 内部所有文件和安全配置与官方完全一致，这 **100% 证实了并非属性修改导致 init 崩溃**，而是我们的底层 CPIO 重打包/Legacy LZ4 压缩格式参数不被 U-Boot 或 Linux 内核的解压引擎识别，导致引导阶段发生 Kernel Panic 并重启。

---

## 实验 #8：LZ4 压缩参数优化与移除终止块（对照组）

**目标**：修复解压引擎崩溃，使重打包的 `boot.img` 底层结构与官方原厂达到 99.9% 吻合。

**分析与变更**：
1. **移除终止块**：之前的 LZ4 压缩逻辑在文件末尾追加了标准 LZ4 的 4 字节零块终止符 (`\x00\x00\x00\x00`)。但通过分析原厂 `boot.fex` 发现，原厂 ramdisk 并没有这个终止块，仅包含 3 个完整的 LZ4 块并直接截断。猜测全志的定制 LZ4 解压驱动可能未处理 0 大小块，导致溢出或 Panic。
2. **启用高压缩率（High Compression）**：默认 lz4 压缩模式体积比原版大出 1.7 MB，可能越过了引导程序硬编码的缓冲区边界。我们改用 `mode='high_compression', compression=9` 模式，使压缩体积从 14.4 MB 降至 **`12,774,703` 字节**，与官方原厂大小（`12,752,798` 字节）**仅相差 21 KB**，且块尺寸分配基本吻合。
3. **实验限制**：继续保持 `modify_properties` 逻辑被注释（无属性修改），以作为第 2 次对照组验证。

**结果：成功！设备能够顺利展示“白底安博科技”并最终稳定在“黑底躺倒机器人”界面，不再发生 Bootloop 重启。**

**结论**：非常关键的突破！证实了我们的高压缩（等级 9）以及“移除零块终止符”的 Legacy LZ4 重新压缩算法与全志引导链完美兼容！之前快速无限重启的根因确认为 **0 字节终止块引发的解压缩 Panic，或体积过大造成的缓冲区越界。**

---

## 实验 #9：Recovery ADB 激活与 init.rc 启动触发器注入

**目标**：强制激活 `adbd` 服务并令其绑定 ConfigFS 物理 UDC。

**分析与变更**：
1. **属性跃变逻辑注入**：即使在 `prop.default` 中注入了 `sys.usb.config=adb`，但由于该属性在开机时便处于 `adb` 状态且从未发生值改变，Android `init` 进程在解析 `init.rc` 时不会触发 `on property:sys.usb.config=adb` 动作块。这导致 ADB 守护进程和 USB 控制器绑定逻辑被静默跳过，物理 USB 接口保持在未绑定的 `sunxi (1F3A:1010)` 状态。
2. **硬件脚本修改**：修改 [enable-recovery-adb.py](file:///c:/Users/tiany/Documents/ubox10-rom改造/scripts/enable-recovery-adb.py)，在 `init.recovery.sun50iw9p1.rc` 尾部追加自定义 `on boot` 触发器：
   ```rc
   on boot
       setprop sys.usb.config none
       setprop sys.usb.config adb
   ```
   该配置通过 `none -> adb` 的物理属性跃变，强制触发 `init.rc` 中对 `adbd` 服务的启动及 ConfigFS UDC 的绑定动作。
3. **全局属性重启用**：取消注释 `modify_properties` 属性注入，保证 `ro.debuggable=1`、`ro.secure=0` 和 `ro.adb.secure=0` 的状态。

**结果**：失败。虽然成功开机稳定在机器人界面，但 USB 依旧卡在 unbound 的 `1F3A:1010` 状态，`adb devices` 找不到设备。

**结论**：即使通过 `none -> adb` 跃变，Android `init` 依然没有成功绑定 UDC。主要可能由于：
1. 原厂固件为 `user` 构建，其内置 `sepolicy` 完全去除了 `su` 调试域（`adbd` 尝试以 `--root_seclabel=u:r:su:s0` 运行时会直接 Crash 挂死）。
2. 在 `user` 构建中，SELinux 强制处于 Enforcing 状态，拦截了 `mount functionfs` 或 ConfigFS 读写。
3. 依赖 Dynamic Triggers (`sys.usb.ffs.ready=1`) 的链条仍旧由于 `adbd` 未能成功运行而被阻断。

---

## 实验 #10：命令式 ConfigFS 强绑定、Userdebug 改造与 Permissive SELinux 注入

**目标**：强制绕过所有的属性触发器和 SELinux 权限，直接以 root 身份调通 USB 控制器并启动 ADB。

**变更与原理**：
1. **SELinux 宽容模式注入**：在 [enable-recovery-adb.py](file:///c:/Users/tiany/Documents/ubox10-rom改造/scripts/enable-recovery-adb.py) 中，向 `mkbootimg.py` 指令添加 `--cmdline "androidboot.selinux=permissive"`，强行让 Recovery 内核以 SELinux Permissive 模式启动，彻底废除权限拦截。
2. **Userdebug 属性改造**：在 `prop.default` 修改逻辑中，追加 `'ro.build.type': 'userdebug'` 属性，解除 `user` 构建的系统调试限制。
3. **USB 物理角色强制切换**：通过分析 vendor `/vendor/etc/init/hw/init.sun50iw9p1.usb.rc`，定位了全志专属的 USB 设备模式转换节点。我们在 `on boot` 的第一行添加了 `copy /sys/devices/platform/soc/usbc0/usb_device /dev/null`，强制内核 OTG 芯片从 Host 状态切为 Device 状态。
4. **主 init.rc 强制硬编码 import**：因为 `${ro.hardware}` 属性在 init 早期可能为空，导致 `import /init.recovery.${ro.hardware}.rc` 丢失。我们修改了主 `system/etc/init/hw/init.rc`，直接在头部显式添加 `import /init.recovery.sun50iw9p1.rc` 语句，确保加载设备级配置。
5. **移除 adbd 崩溃参数 (Root seclabel)**：原厂 `sepolicy` 中不含 `su` 域，`adbd` 携带 `--root_seclabel=u:r:su:s0` 运行时会直接 Crash 挂死。我们在主 `init.rc` 中移除了此参数，防止进程崩溃。
6. **命令式 ConfigFS 初始化**：在 `init.recovery.sun50iw9p1.rc` 尾部的 `on boot` 事件中，用纯命令式脚本直接接管 USB 绑定的完整动作：
   ```rc
   on boot
       copy /sys/devices/platform/soc/usbc0/usb_device /dev/null
       mount configfs none /config
       mkdir /config/usb_gadget/g1 0770 shell shell
       write /config/usb_gadget/g1/idVendor 0x18D1
       write /config/usb_gadget/g1/idProduct 0xD001
       mkdir /config/usb_gadget/g1/strings/0x409 0770
       write /config/usb_gadget/g1/strings/0x409/serialnumber "ubox10_recovery"
       write /config/usb_gadget/g1/strings/0x409/manufacturer "Google"
       write /config/usb_gadget/g1/strings/0x409/product "Recovery ADB"
       mkdir /config/usb_gadget/g1/functions/ffs.adb
       mkdir /config/usb_gadget/g1/configs/b.1 0777 shell shell
       mkdir /config/usb_gadget/g1/configs/b.1/strings/0x409 0770 shell shell
       write /config/usb_gadget/g1/configs/b.1/strings/0x409/configuration "adb"
       symlink /config/usb_gadget/g1/functions/ffs.adb /config/usb_gadget/g1/configs/b.1/f1
       mkdir /dev/usb-ffs 0775 shell shell
       mkdir /dev/usb-ffs/adb 0770 shell shell
       mount functionfs adb /dev/usb-ffs/adb uid=2000,gid=2000
       start adbd
       write /config/usb_gadget/g1/UDC "5100000.udc-controller"
   ```

**结果**：失败。设备管理器依旧只显示 `sunxi (1F3A:1010)`，ADB 无法连通。

**结论与重大发现（Shadowing Trap）**：
我们通过解析 `vendor_ramdisk.cpio` (从 `vendor_boot.fex` 提取) 发现了决定性的原因：
1. **init.rc 覆盖机制**：设备专用的配置文件 `init.recovery.sun50iw9p1.rc` 同时存在于两个位置：`boot.img` (通用 ramdisk) 和 `vendor_boot.img` (vendor ramdisk)。
2. **挂载覆写规则**：在引导装载过程中，内核将 vendor ramdisk 挂载并覆盖于通用 ramdisk 之上。这会导致 `boot.img` 中所有被修改的 `init.recovery.sun50iw9p1.rc` 配置被 `vendor_boot.img` 中自带的原装未修改版本 **100% 覆盖和丢弃**！
3. **前功尽弃的原因**：因为上述覆盖机制的存在，先前我们对 `boot.img` 的所有 ConfigFS 手动绑定和 OTG 强制切换逻辑在开机时根本就没有生效，一直被原版的 `vendor_boot` 文件压制着。

---

## 实验 #11：双重编译联动 —— 同步修改 boot.img 与 vendor_boot.img

**目标**：同步解包、修改并重构 `boot.img` 与 `vendor_boot.img` 中的 ramdisk 配置文件，彻底消除覆写阴影。

**变更**：
1. **联动修改脚本**：重构 [enable-recovery-adb.py](file:///c:/Users/tiany/Documents/ubox10-rom改造/scripts/enable-recovery-adb.py)，在重构 `boot.img` 的同时，自动解包 `vendor_boot.fex` 并对其 ramdisk 根目录下的 `init.recovery.sun50iw9p1.rc` 写入相同的强制 ConfigFS 绑定和物理 USB OTG 切换指令：
   ```rc
   on boot
       copy /sys/devices/platform/soc/usbc0/usb_device /dev/null
       mount configfs none /config
       ... (手工强绑 UDC '5100000.udc-controller')
   ```
2. **AVB 重签名**：对重新打包生成的 `vendor_boot.img` 使用其原始 Salt（`2e606239ea40f534a157a4514d5ebbda81e01ab51bde9def5d877988e0851ab4`）进行 AVB Hash 重签名，保持安全引导链条完整。
3. **打包重组重构**：修改 `repack-rom.py` 将 `vbmeta` 生成过程中的描述符来源重定向至 `work/vendor_boot.img`，并更新 `pack_image.py` 将新生成的 `vendor_boot.img` 作为 `vendor_boot.fex` 写入最终输出的 `x12-purified.img`。

**结果**：固件编译、分区重组、AVB 签名验证及全镜像校验成功通过，等待物理烧录验证。

---

## 当前状态总结

| 阶段 | 状态 | 备注 |
|------|------|------|
| 固件烧录 | ✅ 已解决 | 进度达到 100% 并顺利完成写入 |
| Bootloader | ✅ 已执行 | 正常加载引导链 |
| Boot logo | ✅ 已显示 | 屏幕可显示安博官方 LOGO |
| Recovery | ✅ 已恢复 | 开机稳定在躺倒机器人界面 |
| USB 调试 | ⚠️ 暴露 | 物理连接仍卡在 `1F3A:1010`；等待刷入实验 #11 激活 ADB (`18D1:D001`) |
| Android System | ❌ 未启动 | 未加载开机动画，未能正常进入系统 |

**当前阻塞项**：⚠️ 正在刷入实验 #11 强绑调试包以获取 ADB。

---

## 后续行动计划

1. **执行实验 #11 物理烧录**：
   - 观察设备通电后是否稳定进入机器人界面，且电脑端识别到 Android ADB 设备（`18D1:D001`）。
2. **提取日志与根因诊断**：
   - 运行 `adb devices` 确认连接。
   - 运行 `adb pull /cache/recovery/last_log` 提取崩溃信息。
   - 运行 `adb shell dmesg > dmesg.txt` 提取内核启动日志。
   - 对系统挂载进行深度调试。