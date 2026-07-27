# Milestone M6 物理烧录与实机验证调试记录

> 历史资料：本文件保留早期实验现象，不再定义当前门禁或下一步。当前状态以仓库 `README.md`、`TODO.md` 和 `RUNBOOK.md` 为准。

**日期**：2026-07-20  
**阶段**：M6 受控硬件验证  
**固件基线**：`x12-1024.img` (官方原件)  
**测试对象**：`x12-purified.img` (定制固件)  

> **历史解释校正（2026-07-21）**：本文件保留实验 #1–#11 的操作和观察，便于审计；其中关于 Fastboot、U-Boot、LZ4、init、vendor_boot、SELinux 与 UDC 的“原因/解决”文字均为当时假设，除非 `DISCOVERIES.md` 标为“离线已验证”或“实机已验证”，不得作为当前结论。实验 #11.1 仅完成构建与离线校验，**未进行物理刷写**。

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

**结论（已于 2026-07-21 校正）**：设备已枚举出 Allwinner USB 接口 `1F3A:1010`；这不等于标准 Fastboot 已可用。后续 Platform Tools 探测没有建立 Fastboot 握手，见实验 #12。

---

## 当前状态总结

| 阶段 | 状态 | 备注 |
|------|------|------|
| 固件烧录 | ✅ 已解决 | 进度达到 100% 并顺利完成写入 |
| Bootloader | ✅ 已执行 | 正常加载引导链 |
| Boot logo | ✅ 已显示 | 屏幕可显示安博官方 LOGO |
| Recovery | ✅ 可达 | 自动进入躺倒机器人界面（但无菜单且无法交互） |
| USB 调试 | ⚠️ 暴露 | 未暴露 ADB；`1F3A:1010` 已枚举。Fastboot-class 描述符后来得到确认，但标准 Fastboot 命令握手仍未建立。 |
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
2. **硬件脚本修改**：修改 [enable-recovery-adb.py](../scripts/enable-recovery-adb.py)，在 `init.recovery.sun50iw9p1.rc` 尾部追加自定义 `on boot` 触发器：
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
1. **SELinux 宽容模式注入**：在 [enable-recovery-adb.py](../scripts/enable-recovery-adb.py) 中，向 `mkbootimg.py` 指令添加 `--cmdline "androidboot.selinux=permissive"`，强行让 Recovery 内核以 SELinux Permissive 模式启动，彻底废除权限拦截。
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
1. **联动修改脚本**：重构 [enable-recovery-adb.py](../scripts/enable-recovery-adb.py)，在重构 `boot.img` 的同时，自动解包 `vendor_boot.fex` 并对其 ramdisk 根目录下的 `init.recovery.sun50iw9p1.rc` 写入相同的强制 ConfigFS 绑定和物理 USB OTG 切换指令：
   ```rc
   on boot
       copy /sys/devices/platform/soc/usbc0/usb_device /dev/null
       mount configfs none /config
       ... (手工强绑 UDC '5100000.udc-controller')
   ```
2. **AVB 重签名**：对重新打包生成的 `vendor_boot.img` 使用其原始 Salt（`2e606239ea40f534a157a4514d5ebbda81e01ab51bde9def5d877988e0851ab4`）进行 AVB Hash 重签名，保持安全引导链条完整。
3. **打包重组重构**：修改 `repack-rom.py` 将 `vbmeta` 生成过程中的描述符来源重定向至 `work/vendor_boot.img`，并更新 `pack_image.py` 将新生成的 `vendor_boot.img` 作为 `vendor_boot.fex` 写入最终输出的 `x12-purified.img`。

**结果**：失败。虽然解决了覆写问题，但 USB 依旧卡在 `1F3A:1010` 状态。

**原因分析**：
1. **ConfigFS 规范限制**：在 Linux USB Gadget 规范中，在用户态守护进程 `adbd` 开启 FunctionFS 端点之前，是不允许向 `/config/usb_gadget/g1/UDC` 写入控制器名称的（会直接报错 `Device or resource busy`）。我们在 `on boot` 中紧跟在 `start adbd` 后同步写入 UDC，由于 `adbd` 尚未初始化完成，该写入操作被静默拒绝，导致绑定未成功。
2. **设备树中的 UDC 名称**：我们反编译了 `vendor_boot` 的 DTB 文件，发现其 USB 节点兼容性字符串为 `sunxi-udc`。在 Recovery 模式下，注册的控制器名称可能是 `sunxi-udc`，而并非正常 Android 系统下的 `5100000.udc-controller`。

---

## 实验 #11.1：异步 ConfigFS 绑定监听与多 UDC 兼容机制

**目标**：等待 `adbd` 就绪后异步写入 UDC，并兼容全志平台所有可能的 UDC 控制器名称。

**变更**：
1. **异步写入 UDC 触发器**：在 [enable-recovery-adb.py](../scripts/enable-recovery-adb.py) 中，将对 UDC 的写入移出 `on boot` 同步阶段，单独挂载到 `on property:sys.usb.ffs.ready=1` 触发器中。当 `adbd` 正式打开 FunctionFS 端点并就绪后，系统会自动更新该属性，触发 UDC 写入。
2. **多 UDC 名称顺次尝试**：在触发器中顺次写入所有可能的全志/Inventra/标准 UDC 控制器名字，确保兼容性：
   ```rc
   on property:sys.usb.ffs.ready=1
       write /config/usb_gadget/g1/UDC "sunxi-udc"
       write /config/usb_gadget/g1/UDC "musb-hdrc.0"
       write /config/usb_gadget/g1/UDC "musb-hdrc"
       write /config/usb_gadget/g1/UDC "5100000.udc-controller"
   ```

**结果**：编译并重构校验通过；因其同时改变多个启动链变量，实验 #11.1 已暂停，未进行物理烧录验证。

---

## 实验 #12：标准 Fastboot 只读握手探测（2026-07-21）

**目标**：确认 `1F3A:1010` 是否实际提供标准 Android Fastboot 传输，不修改设备状态。

**环境**：Windows 设备管理器显示 `sunxi`，硬件 ID 为 `USB\VID_1F3A&PID_1010&REV_0200` / `USB\VID_1F3A&PID_1010`。

**执行命令**：

```powershell
tools\platform-tools\fastboot.exe devices
tools\platform-tools\fastboot.exe getvar all
```

**结果**：两个命令均停留在 `< waiting for any device >`，没有设备序列号、`OKAY`、`FAIL` 或变量输出。

**结论**：标准 Fastboot 会话未建立；当前不能读取 `getvar`，不能将此 USB 接口作为可用 Fastboot 通道。未发生设备写入。

---

## 当前状态总结（2026-07-21）

| 阶段 | 证据等级 | 状态 | 备注 |
|------|---|---|---|
| PhoenixCard 容器写入 | 已观察 | 100% 完成 | 仅证明容器可被刷卡工具写入，不证明 Android 可启动。 |
| Boot logo / Recovery 可视界面 | 已观察 | 可达 | Recovery 触发源及功能完整性未知。 |
| Android System | 已观察 | 未进入 | 首个失败点未定位。 |
| Allwinner USB 枚举 | 已观察 | `1F3A:1010` / `sunxi` | Windows PnP 已归档；协议命令事务未建立。 |
| Fastboot 接口描述符 | 主机离线已验证 | `FF/42/03` | 与 AOSP Fastboot 匹配条件一致；不等于命令握手。 |
| 标准 Fastboot | 未验证 | 未握手 | 当前 libwdi WinUSB 未注册 Platform Tools 所需 Android GUID；`fastboot` 持续等待设备。 |
| Recovery ADB | 未验证 | 未建立 | 不再以修改 Recovery 为当前路线。 |
| 实验 #11.1 | 离线构建 | 暂停且未刷入 | 诊断构建隔离在 M6 门禁之后。 |

**当前阻塞项**：缺少无修改的设备侧启动链证据。下一步是经明确授权的 Windows interface GUID 单变量试验，或被动 UART 监听；任何新刷写均暂停。

---

## 实验 #13：Windows PnP / WinUSB interface GUID 证据审计（2026-07-22）

**目标**：在不向设备发送命令、也不改变设备或驱动绑定的前提下，区分“设备没有 Fastboot 接口”与“Windows 无法让 Platform Tools 枚举已存在接口”。

**输入证据**：用户运行只读采集器生成 `logs/device/20260722-001337/usb-evidence.json`（SHA-256 `9823D913E07031822B41567C22DE3D88539E5D21F70431AFEAD29C2A3F766B33`）和 `fastboot.version.txt`（SHA-256 `69FDB6D057CBB0113153A8D9C069286B0572CFB395408926B5CA10608222F56E`）；另有设备管理器的驱动/事件截图。

**观察**：

1. 设备实例为 `USB\VID_1F3A&PID_1010\992304568773`，`Status=OK`、`Problem=0`，兼容 ID 含 `Class_FF&SubClass_42&Prot_03`。
2. 当前驱动为 `oem79.inf` / libwdi，服务 `WinUSB`；事件记录显示 2026-07-20 已配置该 INF 并启动 `WinUSB`。
3. 只读审计发现 `oem79.inf` 注册其自己的 `{9D8998B8-AD0B-4656-B575-AF23D189A1A8}`，而设备的 `DeviceInterfaceGUIDs` 不含 AOSP Android GUID `{F72FE0D4-CBCB-407D-8814-9ED673D0DD6B}`。

**结论**：Fastboot-class 描述符已确认；Platform Tools 未发现设备的高置信原因是主机 interface GUID 注册不匹配。此结论尚未证明设备会回应 Fastboot 命令，也没有执行任何设备协议命令。

**后续控制变量**：已新增 `scripts/test-fastboot-interface-guid.ps1`。默认 `Inspect` 只读；`Apply` 必须管理员权限、显式确认与 PowerShell 高影响确认，并只追加目标 GUID。实施前后按 `U1_FASTBOOT_HOST_BINDING_TRIAL.md` 留存备份、原始输出和回滚记录。

**执行状态（2026-07-22）**：用户已授权 U1 Apply。自动化执行环境未取得 Windows 管理员令牌，脚本在管理员权限预检处退出；未创建主机绑定备份、未写入注册表、未调用 Fastboot，也未发生设备侧操作。下一步须在用户的提升权限 PowerShell 中按 U1 手册执行同一脚本，而非绕过 UAC。

**用户提升权限执行结果（2026-07-22）**：`logs/device/20260722-004314/` 记录 Apply 成功，`ExpectedGuidPresent=true`，且原有三个 GUID 未丢失；`guid-backup.json` 可精确恢复原状态。物理拔插后，`fastboot devices` 输出 `992304568773    fastboot`。这确认 U1 的 Windows interface GUID 假设，尚未执行 Fastboot 命令事务。

## 实验 #14：U2 `getvar version` 自动采集器兼容性修正（2026-07-22）

**目标**：以 15 秒上限归档 `fastboot devices → fastboot getvar version` 的只读 U2 输出。

**首次结果**：`logs/device/20260722-004615/` 已保留。Windows PowerShell 的 `Start-Process` 在创建子进程前因继承环境同时存在 `PATH` / `Path` 键而报重复键异常；两个空的重定向文件表明 `fastboot` 没有启动，因此没有向设备发送任何命令。

**修正**：`collect-usb-evidence.ps1` 的子进程启动改为 .NET `System.Diagnostics.ProcessStartInfo`，显式异步读取 stdout/stderr 并保留同样的超时/终止行为。该修正只影响主机日志采集可靠性，不改变 U2 命令白名单。

**重试结果**：`logs/device/20260722-004720/` 已归档。`fastboot devices` 返回 `992304568773    fastboot`；随后的唯一 Fastboot 命令 `getvar version` 返回 `version: 0.5`（退出码 0，0.009 秒）。标准 Fastboot 协议因此已验证；未执行 `getvar all` 或任何写入/状态变更命令。

## 实验 #15：M6a Fastboot 白名单变量采集（2026-07-22）

**目标**：在已验证协议通道上读取最小变量集，确认是否能从 Fastboot 获得产品、锁定语义、userspace 和 A/B 槽位线索。

**方法**：新增 `scripts/probe-fastboot-readonly-vars.ps1`，先再次验证 `fastboot devices`，再为每一个白名单变量启动独立、15 秒上限的 `getvar` 子进程。脚本拒绝白名单外的变量。

**结果**：所有请求在 0.008–0.012 秒完成，退出码为 0。`product: sunxi`、`secure: yes`；`is-userspace`、`slot-count`、`current-slot`、`has-slot:boot`、`has-slot:vendor_boot`、`has-slot:vbmeta` 与 `has-slot:super` 全部为 `not supported`。原始逐项输出与 SHA-256 清单归档在 `logs/device/20260722-004937/`。

**结论**：该接口是可用但精简的 Allwinner Fastboot 实现。其 `secure` 返回值不能自行解释为 AVB 成功或解锁状态；缺失槽位变量不能反推设备非 A/B。Fastboot 无法进一步定位 Recovery，因此停止扩展探测，转 U3 UART 被动监听。

## 实验 #16：U3.1 被动 UART 冷启动捕获（2026-07-25）

**目标**：不发送数据、不改写设备的前提下，取得从 BootROM 至内核早期挂载的时间线。

**方法与边界**：运行 `scripts/capture-uart-readonly.ps1`，端口 `COM3`、115200、8N1、无流控、90 秒；元数据记录 `DTR/RTS=false`。物理接线仅为 `J21 GND → FT232RL GND` 与 `J21 TX → FT232RL RXD`；J21 RX、FT232RL TXD 与所有 VCC/5V/3V3 均断开。未发送 UART 命令，未调用 Fastboot，未执行设备写入。

**证据**：`logs/device/20260725-004019/`。接收 15,173 字节；`uart-capture.json`、raw 和 text 的 SHA-256 均已复算一致，值见 D-0026。

**结果**：

1. BootROM 识别 eMMC 2，报告 `59008 MB` 和 `***SD/MMC 2 init OK!!!***`。
2. U-Boot 2018.07 启动 `Android's image name: arm64`，随后 Linux 5.4.125 开始运行。
3. 内核输出 `Kernel init done` 后，在 2.484507 秒报 `EXT4-fs (mmcblk0p20): VFS: Can't find ext4 filesystem`。
4. 2.661412 秒后内核输出 `reboot: Restarting system with command 'bootloader'`。第二次 U-Boot 出现 `bootmode[2]:0x5f`，随后 `sunxi_fastboot_init`。

**结论**：本次启动的第一个可见存储失败信号是 p20 `metadata` 无法识别为 ext4；这发生在 Android userspace/Framework 证据之前，并在约 177 ms 后出现 bootloader 重启。该时序不证明 p20 单独发起了重启：AOSP Android 12 的 init 致命重启默认目标就是 bootloader。它也不能证明 p20 为什么无有效文件系统，或把 `secure enable bit: 0` 与 Fastboot `secure=yes` 混为一谈。后续离线盘点已发现 boot ramdisk 内含 `mke2fs`/`mkfs.ext4`、first-stage `e2fsck` 与 `libfs_mgr` 格式化原语，因此“工具根本不存在”已被排除，但尚无其实际调用的证据。下一步仅做离线格式化责任审计，不重新上电、不连接 FT232RL TXD/VCC，也不制作或刷写 metadata 镜像。

**新增静态候选（不构成归因）**：工作提取树的 system `init.rc` 在 `early-init` 以 `exec_start apexd-bootstrap` 执行 `/system/bin/apexd --bootstrap`；其服务有 `reboot_on_failure reboot,bootloader,bootstrap-apexd-failed`，而二进制引用 `/metadata/apex/sessions`。该工作树的镜像归属尚未确认。因此 U3.2 必须先做原件/候选差分和启动时序审计，确认或排除此路径；禁止以此猜测禁用 APEXd、改 reboot target 或预置 p20。

## 实验 #17：U3.2 原件/候选 `metadata` 启动路径离线审计（2026-07-25）

**目标**：在不重连设备、不生成 metadata 镜像的条件下，确认 p20 挂载/格式化相关文件是否被当前候选 boot 或 vendor_boot 改动，并将未归属的 APEXd 线索与已验证 ramdisk 内容分开。

**方法**：新增 `scripts/audit-metadata-init.py`。它只接受仓库内的新输出目录，重新解包 `firmware/extracted/boot.fex`、`vendor_boot.fex`、`work/boot.img` 和 `work/vendor_boot.img`，用内置只读 Legacy LZ4 + newc CPIO 解析器比较受限文件集；不导入可写脚本，不开串口，不调用 Fastboot/PhoenixCard。报告、输入哈希、解包输出和 `SHA256SUMS.txt` 位于 `logs/analysis/20260725-u3.2-metadata-init-audit-r2/`，报告 SHA-256 为 `A30CA83C3E768CE99906A44972C7EECCA3659F165AD994DF43EFED23905A5794`，清单已复核通过。

**结果**：

1. 官方和当前候选的 `system/bin/init`、`mke2fs`、`e2fsdroid`、`libfs_mgr.so` 以及 metadata first-stage fstab 都相同。故“候选移除了已审计格式化能力”不成立。
2. 当前候选 boot 命令行包含 `androidboot.selinux=permissive`；`prop.default` 把 `ro.build.type` 设为 `userdebug`、把 `ro.secure=0`，并追加 root ADB/USB 属性。boot 和 vendor_boot 的 recovery rc 都含 ConfigFS/FunctionFS/UDC/adbd 注入；它们是历史诊断变量，不是发布候选。
3. 重新解包的 boot/vendor_boot 都没有 `apexd`、`apexd.rc` 或 `init.formatdevice.rc`，且 rc 扫描没有 `reboot_on_failure`。此前工作 system 树中的 `apexd-bootstrap` 仍是未归属线索，不能用于解释 boot/vendor_boot 差异。

**结论与后续**：候选启动镜像必须隔离，不能刷写或作为恢复基线。下一步是只读核对 `x12-purified.img` 的 IMAGEWTY 内部 boot/vendor_boot payload 是否实际来自 `work/` 候选；即使相同，也不能替代设备分区读回。设备保持断电，UART 不增加 TXD/VCC 接线。

## 实验 #18：U3.2 IMAGEWTY boot/vendor_boot 容器来源审计（2026-07-25）

**目标**：确认 `x12-purified.img` 内部 boot/vendor_boot 是否实际来自已隔离的 `work/` 历史诊断候选，并验证 IMAGEWTY 伴生校验；不把本地文件关系误称为设备实装状态。

**方法**：新增 `scripts/audit-imagewty-payload-provenance.py`。脚本只读取 IMAGEWTY 头、条目范围和目标 payload，流式计算 SHA-256 与 IMAGEWTY 32 位小端和校验；不把 payload 导出到磁盘。报告位于 `logs/analysis/20260725-u3.2-imagewty-boot-provenance-r1/`，JSON SHA-256 为 `6CCB2B2F921E1047E688D6971114571E069FCFA0B2160ED2FE56E62F39F4EC27`，清单已复核。

**结果**：官方 `x12-1024.img` 的 boot/vendor_boot 都与 `firmware/extracted/` 对应文件一致；候选 `x12-purified.img` 的 boot/vendor_boot 分别与 `work/boot.img`/`work/vendor_boot.img` 字节级一致，且均不同于官方原件。官方和候选的 `Vboot.fex`、`Vvendor_boot.fex` 伴生校验全部匹配。

**结论与后续**：历史调试启动镜像确实被封入候选 PhoenixCard 容器，故该容器继续隔离、不得刷写；这不证明设备当下内容。下一项是只读追溯 super logical system 中 APEXd/init 文件的官方/候选来源，设备继续断电。

**工具边界更新**：在为下一阶段读取 candidate sparse super 元数据时，`lpunpack.py --info` 自动在 `work/` 创建了 3 GiB `super.unsparse.img`。该文件在命令前不存在，已验证是该工具的派生临时输出并删除；输入 `work/super.img`、官方镜像和设备未改动。后续不再直接对稀疏输入调用该工具，logical partition 审计必须采用显式证据输出或流式读取。

## 实验 #19：U3.2 流式 `system_a` init/APEXd 来源审计（2026-07-25）

**目标**：不生成完整 non-sparse 或 system 镜像的前提下，确认工作树 APEXd/init 线索属于官方还是候选 logical system，并检查候选是否具有相同的官方路径。

**方法**：新增 `scripts/audit-logical-system-init.py`，对已追溯来源的官方/候选 sparse super 直接解析 Android sparse 映射、LP metadata（含 SHA-256 校验）、`system_a` extent 和目标 ext4 inode。输出位于 `logs/analysis/20260725-u3.2-logical-system-init-audit-r1/`，只含小型 JSON/哈希清单；没有导出 partition。

**结果**：官方 system 的 `apexd`、`apexd.rc`、`init.formatdevice.rc`、`init.rc` 哈希全部与 `work/system_extracted/` 原有文件吻合，故这些工作树线索属于官方 system。候选 system 的 LP/ext4 元数据可解析，但在官方 `system/...` 路径下未找到相同受限文件集。

**结论与后续**：候选路径 absent 是高价值异常，但尚不能证明文件删除或设备根因。下一项只读工作是枚举候选 ext4 根目录与不带 `system/` 前缀的替代路径，验证是否仅为目录层级错位；候选容器仍不得刷写。

**扩展结果（U3.2-e.1）**：候选根目录确实没有 `system`，却直接包含官方 `/system` 的 `bin`、`etc`、`lib`、`framework`、`app` 等内容。候选根相对 `bin/init`、`bin/apexd`、`etc/init/apexd.rc` 等 8 个受限文件均与官方 `system/...` 路径逐字节相同。这确认的是候选 ext4 根输入错误/目录层级错位，而不是文件删除；候选 super 不具备实机验证资格。下一项只读审计重建脚本的源目录选择，任何修复留待 M6b 的零内容对照。

## 实验 #20：U3.2-f system ext4 重建源根 AST 审计（2026-07-25）

**目标**：在不执行任何历史构建脚本的前提下，确认候选 `system_a` 根级 `/system` 缺失是否由本地重建管线的源目录选择直接造成。

**方法与边界**：新增 `scripts/audit-rebuild-system-root.py`。工具仅用 Python AST 读取 `scripts/purify-rom.py` 与 `scripts/repack-rom.py` 的常量、路径表达式和 `make_ext4fs` 调用；不 import、不执行这两个脚本，不创建 ext4/super/容器，不调用外部构建器、串口、Fastboot 或 PhoenixCard。报告写入 `logs/analysis/20260725-u3.2-rebuild-system-root-audit-r1/`；`rebuild-system-root-audit.json` SHA-256 为 `6DA351EADDC54A9BDB36DD2C4F3F49652A31533A3511C8BC7C06303C1A75693E`，清单复核通过。

**结果**：

1. `purify-rom.py:45` 将 `SYSTEM_DIR` 定义为 `work/system_extracted`；其 build.prop 和裁剪目标均带 `system/...` 相对前缀。
2. `repack-rom.py:27` 将 system 分区的 `src_dir` 定义为 `work/system_extracted/system`；第 90 行直接把该值作为 `make_ext4fs` 的最后一个源目录参数。
3. 该关系的相对路径为 `system`。结合实验 #19 扩展结果中“官方 ext4 根有 `/system`、候选 ext4 根无 `/system`、候选根与官方 `/system` 内容哈希一致”的四项事实，报告计算 `confirmed_root_flattening_chain=true`。

**结论与后续**：错误的 `work/system_extracted/system` 源根足以直接解释候选 system 根层级扁平化。这是**候选本地构建根因**，不证明设备实际运行该候选，也不解释 p20 `metadata` 无 ext4 或 UART 的 reboot 调用者。不得直接把路径改成 `work/system_extracted` 后继续构建：当前仍缺符号链接、UID/GID、SELinux xattr、capability、硬链接和 AVB 保真验证。下一步仅为 M6b.0 的零内容 root-hierarchy control 设计与测试门禁；设备继续断电，FT232RL 不增加 TXD/VCC 接线，metadata 控制样本继续暂停。

## 实验 #21：M6b.0 ext4 工具链静态能力预检（2026-07-25）

**目标**：在创建任何 fixture 或 ext4 输出前，确认历史提取器和重建调用是否已具备完整语义保真的证据。

**方法与边界**：只读取 `tools/extract_ext4.py`、`scripts/repack-rom.py` 和锁定的 `make_ext4fs.exe`。对 `make_ext4fs.exe` 使用无输出路径的 usage 调用；该工具按 usage 返回非零但没有接收镜像文件名或目录，未生成分区、未改写输入、未访问设备。

**结果**：

1. `extract_ext4.py` 只创建目录、写普通文件内容，并把符号链接保存为 `<path>.symlink` 文本；没有 UID/GID、mode、xattr、ACL、capability、硬链接、特殊节点或 ext4 特征的导出逻辑。
2. 历史 `repack-rom.py` 的 `make_ext4fs` 参数只有 `-l`、`-a`、`-S`、输出和源目录；未提供 `-C` / `-X` fs_config 或 `-T` timestamp。工具 usage 表明这些是可选的 metadata 输入。

**结论与后续**：当前工具链无法证明完整 ext4 语义保真，且不应把这一事实简化为“只需改正 system 根路径”。D-0038、R-006 与 M6b.0 已更新。下一步先审阅 manifest schema 和允许差异白名单；在 Gate 0 通过前不创建 fixture、不调用重建器。

## 实验 #22：M6b.1 纯 JSON root-hierarchy guard（2026-07-25）

**目标**：在不读取任何 ext4 或官方固件的前提下，先验证 D-0037 所需的最小根身份规则能够被自动化、失败优先地执行。

**方法与边界**：新增 `src/ubox10_rom/ext4_manifest.py`、`scripts/validate-ext4-root-contract.py`、两个小型 JSON fixture 和 `unittest`。guard 只读取一个 JSON manifest，验证 schema、`/` 根、根级 `/system`、直接子项及禁止 `/system` subtree identity；它没有 image I/O、镜像工具调用或硬件接口。

**结果**：3 项单元测试全部通过。正确根 fixture 返回 `PASS` / 退出码 0；错误 fixture 返回退出码 2，并精确报告 `missing_required_directory:/system`、`missing_required_child:system`、`prohibited_subtree_identity:/system`。测试后复核未出现 `work/super.unsparse.img`。

**结论与后续**：根目录错位现在有一个可复用的自动化拒绝器，但其输入仍是人工最小 JSON，不是实际 ext4 manifest。D-0039 已记录边界。下一步只审阅最小真实 ext4 fixture 的生成/解析方案；在方案批准前不调用 `make_ext4fs`、不读取官方大镜像、设备继续断电。

## 实验 #23：M6b.2 主机 ext4 fixture 能力盘点（2026-07-25）

**目标**：在生成任何真实 ext4 fixture 前，确认主机是否具备相互独立的 fixture 作者和语义校验器。

**方法与边界**：只查询 Windows 命令可用性、Python 版本/模块导入、仓库工具列表与无输出路径的版本/usage。没有安装 WSL、Docker、Python 包或驱动，没有下载文件，没有向 `mke2fs` 提供输出路径，也未读取官方映像或设备。

**结果**：当前无 WSL 发行版、Docker/Podman、`debugfs`、`tune2fs`、`dumpe2fs` 或 `e2fsck`。Python 3.13.3 无法导入历史 `extract_ext4.py` 所需的 `ext4` 模块；直接运行该脚本在导入阶段失败。本地发现 Android `mke2fs 1.47.2`（SHA-256 `BE42ABB5D1651C8766E230E7AF834BD8E0F2085857CCB483463F58BA5AD65E1A`），usage 含 `-d root-directory|tarball`，但没有配套的独立语义注入/验证工具，也未单独锁定来源。

**结论与后续**：当前环境不足以让一个真实 ext4 fixture 同时具备可复现生成和独立语义验证。D-0040、R-019、TODO 与工具锁定文件已更新。下一步只读核对官方实现语义并形成 oracle 路线 ADR；在此之前不生成 fixture、不安装工具。

## 实验 #24：M6b.2 官方 ext4 工具语义与 oracle 路线评审（2026-07-25）

**目标**：确认通用 `mke2fs -d` 能否作为本项目完整 Android ext4 语义 oracle，并在不安装工具、不生成映像的前提下选择 fixture 作者与独立校验架构。

**方法与边界**：只读核验官方 upstream e2fsprogs 手册/发布说明及 AOSP `create_inode.c`、`mkuserimg_mke2fs.py`、`e2fsdroid.c`、`perms.c`。没有下载源码或二进制，没有启用 WSL/Docker，没有调用本地 `mke2fs`，没有创建 ext4、读取官方大镜像或访问设备。

**结果**：

1. `root-directory` 路径从宿主 `lstat` 取得硬链接身份、UID/GID/mode/time；xattr 复制受 `HAVE_LLISTXATTR` 编译能力约束。因此 Windows/NTFS 目录与 `-d` usage 不能证明 Android 语义保真。
2. tarball 输入依赖编译时和运行时 libarchive；其实现/回归不能替代 Android `fs_config/file_contexts`。
3. AOSP 正式流程先以 `mke2fs` 建空 ext4，再以 `e2fsdroid` 设置文件树、UID/GID/mode、capability 和 SELinux 标签。
4. 两条路线比较后，选择从官方签名源码构建的 Linux e2fsprogs 作为 synthetic fixture 作者，并以版本控制 fixture spec、作者侧 `e2fsck/dumpe2fs/debugfs` 证据及仓库独立解析器交叉验证；自研完整 ext4 生成器因实现和伪正确风险暂不采用。

**决策与恢复**：新增 D-0041、ADR-0010、R-020 和 `M6B_EXT4_FIXTURE_ORACLE_DESIGN.md`。Gate 1 fixture 工具不自动成为 Gate 3 Android 生产构建器。当前只完成设计；用户未授权配置 Linux/WSL、联网下载或生成 fixture。失败恢复仅涉及未来隔离的环境/输出，官方镜像和设备保持不变。

**下一步**：等待用户明确选择 Linux oracle 承载方式。获批后先建立 toolchain manifest（签名源码、OS/编译器/configure、二进制 SHA-256），仍不立即生成 fixture；manifest 评审通过后才进入 M6b.3。

## 实验 #25：M6b.2-d Windows/WSL 主机只读预检（2026-07-25）

**目标**：在请求安装 WSL 或改变 Windows 功能前，自动保存当前主机、WSL、可选功能和虚拟化查询的事实，并将“权限不足”与“功能未启用/硬件不支持”严格分开。

**方法与边界**：新增并运行 `scripts/inspect-wsl-oracle-host.ps1`。脚本只读取 Windows CurrentVersion 注册表、PowerShell/进程/OS 架构、管理员身份、两个可选功能、CPU/ComputerSystem CIM 字段，并以只读参数调用 `wsl --version`、`--status`、`--list --verbose`。输出写入新的 `logs/host/20260725-030723/`；没有查询 `--list --online`，没有调用 `wsl --install/--update`、DISM 功能变更、下载、重启、镜像工具、设备接口或固件路径。

**结果**：

1. 当次 schema v1 脚本 SHA-256 为 `D6599889985B6E89F37BD9821DA52E1B3BB36240313400ACD4C0BE292969B2D8`；主 JSON SHA-256 为 `16E50E3598B7A6E0E26E73777E2B9063B91AFF17BB56EEFCE18533A10ABFE8A1`，目录清单复核一致。
2. `wsl.exe` 存在，但三项只读调用分别退出 1/50/1，均报告 WSL 未安装。
3. 注册表原样给出 `Windows 10 Home`、`25H2`、build `26200.8875` 等字段，Windows PowerShell 为 Desktop `5.1.26100.8875`；项目不据此猜测市场版本。
4. 当前 run 不是管理员。两个可选功能查询要求 elevation，CIM 虚拟化查询 access denied；这些状态均保持 unknown。

**结论与恢复**：D-0042 与 R-021 已登记。下一项最小实验不是安装，而是在用户可见的管理员 PowerShell 重新运行同一只读脚本。其输出仍只在 Git 忽略的 `logs/host/<run-id>/`；失败时不需要主机回滚，只保留错误证据。安装 WSL、启用功能、联网取得发行版、下载工具链和重启仍需后续独立授权。

## 实验 #26：M6b.2-d2 管理员 H1 与 schema v2 恢复准备扩展（2026-07-25）

**目标**：补齐 WSL/VMP、CPU 虚拟化和 Hypervisor 的管理员事实；在任何 BIOS/Windows 功能变更前，再把系统盘加密恢复风险与主板身份纳入自动化门禁。

**方法与边界**：

1. 复核用户以管理员身份生成的 `logs/host/20260725-121016/`，逐项重算 SHA-256、检查 schema、`IsAdministrator=true` 与所有安全字段。
2. 只读核验 Microsoft WSL 前置条件及 ASUS AMD 主板 SVM 官方路径。
3. 将采集器升级为 schema v2，增加 BIOS 注册表和 `Get-BitLockerVolume` 的非秘密元数据；明确不读取 recovery key material。
4. 以非管理员身份运行 v2 到 `logs/host/20260725-121929/`，仅验证 schema、主板字段、拒绝访问时保持 unknown 与安全字段。没有安装、功能变更、BIOS 操作、下载、重启、设备或固件访问。

**结果**：

- H1 主 JSON SHA-256 `3D7B600AE681603016EB4F5D6BE91575A0AEDABAEFEF1166A61BC00C657885AF`，清单通过。
- WSL 与 VMP 均为 Disabled；Ryzen 5 5600X 报告 VM monitor extensions/SLAT 可用，但 firmware virtualization=false、hypervisor=false。
- v2 当前脚本 SHA-256 `3B5CE629FDA11E7AE2369BD56919970A25DF91E1A22E6FF8E9CFE9518551DC8C`；非管理员回归识别 `PRIME B550M-A WIFI II` / BIOS `3607`，加密状态因权限不足保持 unknown。
- H1 中两个 WSL 子进程超时，仅保留“未安装”stderr，不伪造退出码；管理员功能/CIM 结论独立成立。

**决策、风险与恢复**：新增 D-0043、D-0044、ADR-0011 与 R-022。下一项仍是 v2 管理员只读运行；不得直接改 BIOS。未来若放行 SVM，必须只改 `SVM Mode`，不更新 BIOS、不加载 defaults、不同时改变 Windows 功能；异常时回到 BIOS 恢复原值。UBOX10 与 FT232RL 保持断开。

## 实验 #27：M6b.2-d3b 管理员 schema v2 恢复准备（2026-07-25）

**目标**：在提出 BIOS SVM 变更前，确认系统盘 protection/encryption/protector 状态，并再次验证 H1 的主板、功能和虚拟化基线。

**方法与边界**：用户以管理员身份运行 schema v2 `inspect-wsl-oracle-host.ps1`，输出 `logs/host/20260725-123940/`。本轮只复核 JSON、原始 WSL stderr、SHA-256 与安全字段；没有进入 BIOS、改变 Windows 功能、安装/更新 WSL、联网、重启、访问设备或固件镜像。脚本只序列化 protector 类型，不访问或保存 recovery key material。

**结果**：

1. 主 JSON SHA-256 为 `9709EF08EC846A1EC765A7A7074D87E562BB387260BEE4D5FB8DB526D346F19D`；目录清单逐项通过。
2. `C:` 为 `FullyDecrypted`、Protection Off、EncryptionMethod None、0%、Unlocked，protector 类型为空。
3. PRIME B550M-A WIFI II / BIOS 3607、WSL/VMP Disabled、firmware virtualization=false、hypervisor=false、CPU VM monitor extensions/SLAT=true 均与 H1 一致。
4. 所有安全字段为无变更/无秘密读取；两个 WSL 只读子进程的既有超时行为未被误写为成功退出。

**决策、风险与恢复**：D-0045 已登记，H2a 标记通过。H2b 已具备**提案条件**但仍须用户明确授权；风险等级为中等主机固件变更、设备风险为无。恢复方案是只把 SVM 恢复为本轮原值 Disabled；禁止通过 BIOS update、Load Optimized Defaults 或 CMOS reset 代替精确回滚。

## 实验 #28：M6b.2-d3c H2b SVM 重启后验收（2026-07-25）

**目标**：验证用户在 BIOS 启用 SVM 后，固件虚拟化确实生效，且 Windows 功能、Hypervisor、系统盘保护与项目安全边界没有发生非预期变化。

**方法与边界**：

1. 先运行普通权限 schema v2 到 `logs/host/20260725-202850/`。该报告安全字段通过，但 CIM/DISM/BitLocker 查询因权限不足为 unknown，只用于证明失败关闭，不能验收 H2b。
2. 用户随后以管理员身份运行同一只读脚本，证据现位于 `logs/host/20260725-203346/`。逐项比较 H2a 报告、重算报告和七个 payload 的 SHA-256，并检查 schema、管理员身份与全部安全字段。
3. 不调用 `wsl --install/--update`，不启用 Windows 功能、不查询在线发行版、不再次进入 BIOS、不重启、不访问 UBOX10 或固件镜像。

**结果**：

1. 管理员主 JSON SHA-256 为 `97E2C071ECC9F48680517E610CAE192E84B87E58A50E9DA26439D5FD6096C2B4`；`VirtualizationFirmwareEnabled: false → true`，CPU VM monitor extensions/SLAT 仍为 true。
2. WSL/VMP 仍 Disabled、HypervisorPresent=false；系统盘仍 FullyDecrypted、Protection Off、EncryptionMethod None、0%、无 protector。
3. 全部只读安全断言通过。`wsl --status` 仍退出 50；另外两个探针写出未安装诊断后超时，不伪造退出码。
4. 证据采集时输出根为仓库根 `.\20260725-203346`，当前目录位于 `logs/host`。原绝对路径清单因此不可直接解析，但按 basename 在当前位置重算的七个 payload 全部匹配。原始证据未改写。

**决策、风险与恢复**：D-0046 将 H2b 标记通过。H2c 尚未授权；先盘点 VMware/VirtualBox/Docker/模拟器及相关 Hyper-V 功能兼容性，再提交 Windows 功能单变量方案。若 SVM 本身引发后续宿主异常，仍只把 BIOS SVM 恢复为 Disabled，不加载默认值或清 CMOS。D-0047/R-023 将未来证据清单改为相对文件名；`logs/host/20260725-203959/` 已完成无变更回归。

## 实验 #29：M6b.2-d3d-a H2c 兼容性预检器普通权限回归（2026-07-25）

**目标**：在任何 Windows feature change 前，以独立、可复核的报告盘点第三方虚拟化/容器/模拟器、相关服务、VBS/Device Guard、optional features、SVM、系统盘边界和待重启状态。

**方法与边界**：新增只读 `scripts/inspect-wsl-h2c-compatibility.ps1`。它只查询本地注册表、服务、CIM、DISM optional feature 和 BitLocker 非秘密状态，生成 JSON 与相对 SHA 清单；不联网、不调用 WSL install/update、不改变功能/服务/注册表、不安装/卸载、不重启、不访问设备或固件。

**结果**：

1. 首轮 `logs/host/20260725-204736/` 发现空 pipeline 在 PowerShell 5.1 被序列化为 `{}`；这会让通用数组计数产生 1 的假象，不代表检测到软件。报告保留但不进入门禁。
2. 修正后脚本 SHA-256 为 `47FAB0ECBD9630AD35104C573A24AFD6423BE363850DC0692FD866EA1FE1ADB0`。`logs/host/20260725-204907/` 的报告 SHA-256 为 `4E1CDE9A2642B8B3AD7BCF104B6A76635328C9F930F975D8BAEAE2510232F1FF`，相对清单与全部无变更安全断言通过。
3. 普通权限结果的安装项名称匹配为 0，相关服务仅 `HvHost`（Stopped/Manual），CBS/Windows Update/PendingFileRename 三类待重启信号均为 false。
4. CIM、optional features 和 BitLocker 在普通权限下为 unknown；因此不能用本轮结果确认 SVM、Hypervisor、Windows 功能或系统盘状态，也不能放行 Apply。

**决策、风险与恢复**：新增 D-0048。下一项只是管理员运行同一只读脚本；H2c Apply 仍未授权。若管理员报告出现待重启信号或第三方兼容性命中，先解释来源并停止，不通过叠加 feature change 解决。

## 实验 #30：M6b.2-d3d-a 管理员 H2c 预检与 optional-feature 三态修正（2026-07-25）

**目标**：以管理员权限补齐 H2c 兼容性字段，并验证采集器能将当前 SKU 不提供的 optional feature 与查询失败区分开。

**方法与边界**：用户运行只读 H2c 采集器得到 `logs/host/20260725-205525/`。本轮仅重算相对 SHA 清单、检查 schema/管理员/安全字段与 H2c 前置；不启用功能、不安装、不联网、不重启、不访问设备或固件。

**结果**：

1. 报告 SHA-256 `87A9218FCB3EAAD0EAF55CF1909A56A9B71AAD3CBEA8F46F6D14EE357F16507E`；SVM=true，WSL/VMP/HypervisorPlatform Disabled，HypervisorPresent=false，未检测到待重启或名称匹配的软件，系统盘边界不变。
2. `Microsoft-Hyper-V-All`、Containers、Containers-DisposableClientVM 与 Sandbox 成功调用后得到零条对象，但旧 helper 对 null 调用方法，误记为错误；这不是 feature 已启用的证据，也不能作为 feature 不存在的机器可读结论。
3. helper 已修正为 Present/NotPresent/Unknown 三态，脚本 SHA-256 `7FD7FBEC8BE5344444A91173C1C48E50729AFC42AD35D7CB01B4E0A7F6086ABA`。`logs/host/20260725-205727/` 的普通权限回归 SHA-256 `0338264FD775E4B61D3FFAA1DBB01658C9D99F88319361B738F789CC74C8E82B` 证明权限失败仍为 Unknown，未把错误降级为 NotPresent。

**决策、风险与恢复**：新增 D-0049。必须以管理员身份重跑修正版，不修改 `205525` 原始证据。H2c Apply 继续暂停；任何 feature 为 Unknown、pending reboot=true 或新增兼容性命中均停止在预检层。

## 实验 #31：M6b.2-d3d-a 修正版管理员 H2c 预检与 feature-gate Inspect 回归（2026-07-25）

**目标**：验收 Present/NotPresent/Unknown 三态的管理员兼容性报告，并验证 H2c Apply 自动化在 Inspect 模式下无法改变 Windows 功能。

**方法与边界**：用户以管理员身份运行修正版兼容性采集器到 `logs/host/20260725-205941/`。随后本机以非管理员权限运行新 feature-gate 的 `Inspect` 模式，并绑定该证据目录。两轮均不调用 `Enable-WindowsOptionalFeature`、WSL install/update、在线目录、下载、重启、设备或固件访问。

**结果**：

1. `205941` SHA-256 为 `3EC07DCBE20CB9AC3160FB73BB49F0A9DC279A14F18EF80869CD00506ECD26DB`；WSL/VMP/HypervisorPlatform 是 Present/Disabled，其余四项是 NotPresent，无 feature 查询错误。SVM=true、无 pending reboot、无软件名称匹配、系统盘边界稳定。
2. feature-gate 脚本 SHA-256 为 `149A296DACE55F22058DC3FEF08C64A54F16D81FB821EA1250139826D125F728`。其 AST 中唯一 feature mutator 是 `Enable-WindowsOptionalFeature`；静态检查未发现 WSL/DISM/重启/服务/注册表/安装类命令。
3. Inspect 回归 `logs/host/20260725-210253/` 验证了输入包 SHA-256，报告 `InspectOnly=true`、`WindowsFeaturesChangeRequested/Started/Completed=false`，SHA-256 `C8FDF12AADA60B95514EBF2ACB79C8C6D8C59C0CB262DD519CB0F2C7DBF0578B`。

**决策、风险与恢复**：D-0050/D-0051 已登记。现在只可**提出** H2c Apply；未获得明确授权前不运行 Apply。获授权后脚本仍以 `-NoRestart` 停在证据层；若 Apply 不完整或 LiveAfter 不符合预期，停止、保留日志，不自动禁用/重启，单独评审恢复。

## 实验 #32：M6b.2-d3d-b H2c 双 feature Apply（2026-07-25）

**目标**：在已验证的 H2c 管理员兼容性前置下，只启用 WSL 与 VMP，不重启、不安装发行版，并证明变更后状态与授权范围一致。

**方法与边界**：用户在提升权限 PowerShell 运行 `apply-wsl-h2c-features.ps1 -Mode Apply -ConfirmH2cWindowsFeatures -PreflightEvidenceDir ...205941`。脚本只接受 D-0050 的 SHA 绑定预检，实时复核 feature 与 pending reboot，然后用 `Enable-WindowsOptionalFeature -Online -NoRestart` 启用固定的两个 feature。没有调用 WSL、在线目录、下载、发行版安装、服务/注册表控制、重启、设备或固件路径。

**结果**：

1. `logs/host/20260725-211225/` 主 JSON SHA-256 为 `66BAABD9A5166AF5B2BB80FCDD180B404815A20BAEE629004D12A034FB95CB19`，相对清单通过。预检十项检查全部通过，管理员、确认开关、实时 Disabled 状态和无 pending reboot 均成立。
2. Apply Completed 且无错误/拒绝；LiveAfter 确认 WSL/VMP 都为 Enabled。所有非 feature-change 安全字段均为 false。
3. cmdlet 明确返回 RestartNeeded=true，CBS RebootPending=true；这是 `-NoRestart` Apply 的预期中间状态，不是脚本重启。

**决策、风险与恢复**：新增 D-0052。当时 H2c 尚未完成，唯一下一动作是正常 Windows 重启；不得运行第二次 Apply 或以额外 Windows/BIOS/UBOX10 操作绕过。该逐操作限制随后由 D-0053 的 B1 批次范围替代，并已由 D-0054 完成验收。

## 实验 #33：B1 post-reboot、WSL2 与 Ubuntu 环境统一验收（2026-07-25）

**目标**：验收已完成的 H2c `-NoRestart` 事务、受控 WSL runtime/Ubuntu 安装和通用 Linux 构建依赖，且不创建 ext4 fixture、不访问固件或设备。

**方法与边界**：用户按 D-0053 的 B1 文档正常重启 Windows、配置 WSL 2 与 `Ubuntu-24.04`、安装固定 APT 依赖并建立 Linux 家目录隔离工具链目录。之后以管理员身份运行两个只读 Windows 采集器，用户贴出 Ubuntu 的版本、磁盘、e2fsprogs、编译器与依赖输出。项目复算两份 Windows 证据的相对 SHA-256 清单；不运行 feature mutator、WSL 安装/更新、重启、fixture 生成、固件工具或设备命令。

**结果**：

1. `logs/host/20260725-215742/`（主报告 SHA-256 `7E445D31595B97C65194B06D376E15340D239E76A31F6B98409A9C43A48CB94D`）与 `logs/host/20260725-215747/`（主报告 SHA-256 `264601FBDD2AF8309DE2C0D6609DB2D061AB1408F1895B6B55F6165075ADF6B3`）的全部清单项复算通过。两份报告都是管理员只读采集，所有变更/设备/固件安全字段为 false。
2. WSL/VMP 均为 Enabled，三类 pending-reboot 信号均为 false，`C:` 仍完全未加密。WSL 版本 2.7.11.0，默认 `Ubuntu-24.04` 正以 Version 2 运行。
3. 用户输出显示 Ubuntu 24.04.4 LTS、Linux 6.18.33.2-microsoft-standard-WSL2、约 954 GiB 根文件系统可用、e2fsprogs 1.47.0、Python 3.12.3、GCC 13.3.0、GNU Make 4.3，以及 B1 所列开发依赖版本。
4. HypervisorPresent=true 和 VBS status=2 是 post-reboot 宿主虚拟化状态；名称匹配的软件为 0。HVCI/Memory Integrity 未从本证据推导，因为 `SecurityServicesRunning` 未含其标识值。

**决策、风险与恢复**：新增 D-0054。B1 通过，R-021 在本轮缓解、R-022 继续记录第三方虚拟化兼容性风险。下一步只可准备上游 e2fsprogs toolchain manifest；不得生成 fixture、读写官方完整 ext4、重建 Android 镜像或连接 UBOX10。若将来需撤销主机配置，须先单独制定仅涉及本轮 WSL/VMP/Ubuntu 的恢复方案，不触及 BIOS defaults、固件或设备。

## 实验 #34：R2 e2fsprogs 1.47.2 toolchain manifest 统一验收（2026-07-26）

**目标**：建立来源可验证、版本固定、只安装到 Linux 家目录的 Gate 1 ext4 工具，不生成文件系统或接触固件。

**方法与边界**：复算 `logs/host/20260726-000642-m6b-toolchain-1.47.2/` 的 20 项 SHA-256；核对 kernel.org 签名、完整公钥指纹、固定源码哈希、configure/build/install 日志、四个工具版本/哈希和动态依赖；额外审计失败与重试安装日志中的绝对安装目标。没有调用 WSL/设备/固件工具，也没有读取 WSL 私有构建目录以外的新输入。

**结果**：

1. 20 项清单复算通过。源码哈希为预先固定的 `08242E64...D74E63C`；GPG 完整指纹 `B8868C80...589DA6B1` 与签名一致并报告 Good signature。
2. 原 keys.openpgp.org 指纹端点返回 404；替换为 Ubuntu keyserver 后仍强制同一完整指纹，身份为 kernel.org checksum autosigner。该偏差有独立 amendment 记录。
3. 编译成功，并确认 xattr/ACL 头文件、`llistxattr` 和 libarchive 支持。缺少 makeinfo 只影响被上游忽略的 Info 文档。
4. 初次安装的上游 service 目录逃逸私有 prefix，在第一个 `/usr/lib/udev` 文件操作上因权限拒绝。没有 sudo，也没有观察到系统路径成功写入。三项 make-time 目录覆盖后的重试只安装到私有 prefix。
5. `mke2fs/debugfs/e2fsck/dumpe2fs` 均为 1.47.2，四项 SHA-256 已写入 D-0055。搜索未发现 `make check`、fixture、镜像输入、debugfs 写入或 e2fsck 修复调用。

**决策、风险与恢复**：D-0055 通过 R2；新增 R-024，并修正 R2 公钥来源和 service 安装路径合同。工具只获准作为下一阶段 synthetic fixture 作者/作者侧检查器；不得用其制作 Android system。保留首次失败日志作为防止未来 `sudo make install` 的回归证据。

## 实验 #35（待执行）：M6b.3a positive synthetic ext4 双次复现

**目标**：只使用项目自创数据和 D-0055 锁定的 e2fsprogs 1.47.2，连续生成两份 16 MiB 正样本，验证作者侧目录、软/硬链接、UID/GID/mode、SELinux/capability/ACL xattr、`e2fsck -fn` 与镜像哈希可重复性。

**方法与边界**：按 `M6B_POSITIVE_FIXTURE_RUNBOOK.md` 一次性执行两次 `scripts/build-m6b-positive-fixture.sh`。脚本拒绝 root/sudo、非固定仓库路径、工具哈希变化和已有输出目录；不挂载、不访问 `/dev`、官方镜像、`work/`、设备或固件接口。

**当前状态**：生成器已通过 WSL `bash -n` 静态语法检查；锁定的 `mke2fs 1.47.2 -n` 已接受全部固定 feature、UUID、hash seed 和大小参数，且 `-n` 未创建/修改文件系统。尚无实际 fixture 结果，不能提前记录 PASS。两次作者侧证据与镜像哈希是下一关键验收节点。
