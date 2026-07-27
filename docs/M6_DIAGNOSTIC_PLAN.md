# M6a 无修改启动链诊断计划

> 历史资料：M6a 已完成，本文件不再定义当前操作范围。当前任务见 `RUNBOOK.md`。

## 目标与边界

目标是在**不改写设备**的前提下，确认 USB 接口的可访问性，并取得能够定位 Recovery 路径的启动链证据。当前阶段不尝试修复 ADB、不重建 boot/vendor_boot、不改 AVB，也不刷 PhoenixCard。

| 已有事实 | 证据等级 | 含义 |
|---|---|---|
| Windows 显示 `sunxi`，硬件 ID 为 `USB\VID_1F3A&PID_1010` | 已观察 | 物理枚举正常；不能单独证明协议。 |
| PnP 兼容 ID 为 `Class_FF&SubClass_42&Prot_03` | 主机离线已验证 | 与 AOSP Fastboot 的接口描述符筛选条件一致；不等于命令事务已成功。 |
| 当前服务为 `WinUSB`；U1 已为唯一实例追加 Android interface GUID 并保留原值 | 协议已验证 | 物理拔插后 Platform Tools 已枚举设备；主机侧阻塞原因已通过可回滚单变量试验验证。 |
| 初始 `fastboot devices` / `getvar all` 曾只显示 `< waiting for any device >`；U1 后 `devices` 与 `getvar version` 成功 | 协议已验证 | 当前标准 Fastboot 会话已建立，但该 Allwinner 实现不支持槽位/userspace 白名单变量。 |
| 设备可见 Recovery 机器人界面，Android System 未进入 | 已观察 | Recovery 触发源和首个失败点未知。 |
| #11.1 已构建但未刷入 | 离线已验证 | 不可作为当前设备行为的证据。 |

实际 PnP 已记录 `FF/42/03` 描述符，这符合 AOSP Fastboot 的接口筛选条件；但实际设备仍须通过一次标准协议握手确认。Windows 上的 AOSP Fastboot 还依赖正确的 Android USB interface GUID 和驱动绑定；描述符本身不足以证明可访问性。

## 阶段 U0：只读主机证据采集

**风险等级：低。** 只读取 Windows 与本地工具信息，不向设备发送协议命令，不修改驱动。

1. 让设备处于当前能出现 `sunxi` 的状态，保持线材和 USB 端口不变。
2. 从仓库根目录运行：

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\collect-usb-evidence.ps1
   ```

3. 上述 `Bypass` 只作用于这个 PowerShell 进程，不改变系统执行策略、驱动签名设置或设备状态。脚本会在 `logs/device/<run-id>/` 写入 PnP 属性、设备实例、Platform Tools 版本和 SHA-256；运行前可以先审阅脚本内容。若仍无法运行，先提供设备管理器“驱动程序”和“详细信息”页截图，不要修改系统范围的安全策略。
4. 一并保存：设备管理器的“常规 / 驱动程序 / 详细信息（硬件 ID）/ 事件”截图、插入端口和线材信息、设备屏幕照片、采集时间。

**通过条件**：能记录当前驱动提供商、INF 路径、Class GUID、问题代码、实例 ID；若 Windows API 不可读取，也要明确记录该失败及截图。

## 阶段 U1：主机 interface GUID 单变量路径（需要用户单独确认）

**风险等级：中（只影响 Windows 主机，可逆；不改写设备存储）。**

U0 已完成，当前结果为：`oem79.inf` / libwdi 使用 `WinUSB`，但只注册 `{9D8998B8-AD0B-4656-B575-AF23D189A1A8}`，实际设备参数中没有 AOSP Android USB interface GUID `{F72FE0D4-CBCB-407D-8814-9ED673D0DD6B}`。因此先进行一个已文档化的、可逆的单变量验证，而不是安装另一套驱动。

**U1 实际结果（2026-07-22）**：已在唯一实例 `USB\VID_1F3A&PID_1010\992304568773` 上完成追加；备份与写后验证在 `logs/device/20260722-004314/`。物理拔插后 `fastboot devices` 显示 `992304568773    fastboot`。因此 U1 的主机枚举目标通过；进入 U2，但仍必须先完成 `getvar version`。

1. 先运行 [U1 Fastboot 主机 GUID 单变量试验](U1_FASTBOOT_HOST_BINDING_TRIAL.md) 的 `Inspect` 模式；必须只发现一个目标实例。
2. 只有用户明确确认后，才可使用 `Apply` 追加目标 GUID。脚本在写前备份全部原值，写后验证原 GUID 未丢失；不会执行 Fastboot、安装/卸载驱动、重绑设备或修改设备存储。
3. 物理拔插后进入 U2。若阴性或异常，按备份 `Rollback`，转 U3 UART；不要继续寻找或安装未知驱动包。

**明确禁止**：安装仓库内手工修改的 Google USB INF；关闭 Windows 驱动签名强制；直接用 Zadig 的 Bind/Install 功能。修改过 INF 后，原 Google Catalog 不能再证明整个驱动包的完整性；普通 WinUSB 绑定也不必然被 `fastboot.exe` 枚举。

**恢复计划**：Apply 前已保存 `DeviceInterfaceGUIDs` 全量备份。若试验异常，使用脚本的 `Rollback` 还原并物理拔插；不卸载当前驱动，不清理其他设备、USB 控制器或系统级驱动。

## 阶段 U2：标准 Fastboot 最小只读握手

**风险等级：低（设备读取）。** 仅在 U1 完成并经用户确认后执行。每个命令独立记录、设置 10–15 秒超时。

1. `fastboot devices`：只有出现序列号与 `fastboot` 状态才继续。试验前后的原始输出均归档。
2. `fastboot getvar version`：只有收到 `OKAY` / 变量值后，才记录为“协议已验证”。
3. 后续白名单仅读变量：`product`、`secure`、`is-userspace`、`slot-count`、`current-slot`、`has-slot:boot`、`has-slot:vendor_boot`、`has-slot:vbmeta`、`has-slot:super`。每个命令单独记录。

**U2 实际进度（2026-07-22）**：`logs/device/20260722-004720/` 已归档 `992304568773    fastboot` 与 `getvar version → version: 0.5`（退出码 0）。标准 Fastboot 达到“协议已验证”。接下来的白名单变量仍必须逐项记录；不因握手成功而放宽任何写入禁止项。

白名单采集由 `scripts/probe-fastboot-readonly-vars.ps1` 自动执行：每个变量使用独立的 `fastboot getvar <name>` 子进程、各自 stdout/stderr 文件与 15 秒上限；脚本拒绝任何不在白名单中的变量，并先再次验证 `fastboot devices`。

**U2 白名单结果（2026-07-22）**：`logs/device/20260722-004937/` 显示 `product=sunxi`、`secure=yes`；`is-userspace`、`slot-count`、`current-slot` 与全部四项 `has-slot:*` 均为 `not supported`。U2 已达到其可取得的证据上限，禁止继续猜测或运行 `getvar all`。直接进入 U3 UART。

当前 Recovery/BCB/slot/AVB/ext4/init 假设、证据和最小验证方式见 [M6 启动失败假设矩阵](M6_HYPOTHESIS_MATRIX.md)。

不要一开始执行 `getvar all`，更不要执行 `flash`、`erase`、`download`、`boot`、`continue`、`reboot`、`set_active`、`oem`、`unlock` 或 `upload`。

## 阶段 U3：UART 被动监听

**风险等级：低（按手册仅接收）/ 中（接线错误）。** 满足任一条件后，UART 是优先路径：

- 已确认合适的驱动/接口后，`fastboot devices` 仍为空或 `getvar version` 超时；
- Fastboot 可读变量不足以解释 Recovery 的原因；
- 需要 BootROM → U-Boot → AVB → Kernel → init 的完整时间线。

执行前必须阅读 [UART 被动监听手册](UART_RUNBOOK.md)。第一次只连接 GND 与板端 TX→适配器 RX，不连接 VCC 或主机 TX；这不会向目标板发送数据。

**U3 实际结果（2026-07-25）**：`logs/device/20260725-004019/` 已归档首次 90 秒冷启动捕获。`uart-capture.json` 记录 `COM3`、115200、8N1、无流控、`DTR/RTS=false`、15,173 字节以及仅 `J21 GND → FT232RL GND`、`J21 TX → FT232RL RXD` 的接线。JSON、raw 与 text 的 SHA-256 均已复算一致。日志显示 eMMC、U-Boot 和 Linux 内核均开始运行；`Kernel init done` 后第一个存储失败信号为 `mmcblk0p20`“找不到 ext4 文件系统”，177 ms 后出现 `bootloader` 重启。第二次 U-Boot 出现 `bootmode[2]:0x5f` 并初始化 Sunxi Fastboot。此结果足以把 p20 与本次早期失败窗口关联起来，但尚不足以证明 p20 错误由哪段 init/vendor 代码处理或单独导致重启；AOSP init 的默认致命重启目标本来就是 bootloader。它不解释 p20 为什么无有效 ext4，也不替代跳帽/VCCIO 的电气测量。

## 阶段 U3.2：`metadata` 格式化责任离线审计

**风险等级：低。** 只读取仓库中的官方提取物、候选工作副本和脚本；可以写入新的分析报告或隔离控制样本，但不连接 UBOX10，不调用 Fastboot，也不修改 PhoenixCard 容器。

1. 从 GPT/`sys_partition.fex` 复核 p20 的名称、边界与 16 MiB 大小，并记录输入文件哈希。
2. 从 first-stage fstab/ramdisk 审计 `/metadata` 的挂载选项、`formattable` 语义以及实际可用的格式化工具或厂商脚本。U3.2-b 已由 `logs/analysis/20260725-u3.2-metadata-init-audit-r2/` 完成：官方和当前候选的 `init`、`mke2fs`、`e2fsdroid`、`libfs_mgr.so` 及 metadata fstab 均相同。它排除“候选删掉已审计格式化能力”，**不证明**当前启动调用了任何格式化路径。
3. 审计官方容器条目和 `tools/pack_image.py`：已确认没有 `metadata` 有效载荷或映射；当前候选封装链不能传递该分区。不得由此反推官方镜像必然不可启动。
4. 审计第二阶段 `init.rc` 的实际触发顺序和所有 `reboot_on_failure`：重新解包的 boot/vendor_boot 都不含 `apexd`、`apexd.rc` 或 `init.formatdevice.rc`，也没有 `reboot_on_failure` 命中。后续 logical-system 审计已将工作树 APEXd/init 归属为官方 `system_a`，并确认候选把同一内容放错到 ext4 根相对路径；该线索不能归因给 boot/vendor_boot，也尚不是设备运行时证据。
5. U3.2-d 已由 `logs/analysis/20260725-u3.2-imagewty-boot-provenance-r1/` 完成：`x12-purified.img` 的 boot/vendor_boot payload 分别与 `work/boot.img`、`work/vendor_boot.img` 字节级相同，官方容器也与 `firmware/extracted/` 相同，伴生 IMAGEWTY 校验均通过。该结论仍不能证明物理设备实装内容。
6. U3.2-e：从官方/候选 super 的 logical `system` 分区建立 APEXd、`apexd.rc`、`init.formatdevice.rc` 与 `init.rc` 的输入哈希、文件存在性和差分 manifest；不得把工作树用作来源证据。D-0034 已确认输入来源为 `firmware/extracted/super.fex` 与 `work/super.img`。`tools/lpunpack.py` 对稀疏输入即使 `--info` 也会在输入同级写 `.unsparse.img`，故不得直接针对这些输入运行；必须使用流式读取方案或显式、全新的证据输出目录。
   - U3.2-e 已完成：工作树的 APEXd/init 哈希来自官方 `system_a`；候选将官方 `/system` 子树扁平化到 ext4 根目录，官方 `system/...` 路径缺失但根相对文件哈希一致（D-0036）。这确认候选 super 的离线结构缺陷，但不证明设备因果。
7. U3.2-f：**已完成**。`logs/analysis/20260725-u3.2-rebuild-system-root-audit-r1/` 以 AST 只读审计确认：`purify-rom.py` 在 `work/system_extracted` 的 `system/...` 子树中修改内容，而 `repack-rom.py:27` 将 `work/system_extracted/system` 直接传给 `make_ext4fs`。报告字段 `confirmed_root_flattening_chain=true` 将该选择与候选根级 `/system` 缺失建立了可复核的本地因果链（D-0037）。不得就地修补脚本或生成新 super；M6b.0/M6b.1/M6b.2 已把修复转化为语义合同、JSON guard 与独立 fixture oracle 门禁。H1、H2a、H2b、H2c 和 B1 已通过；真实 ext4 fixture 之前仍须先完成 [R2 toolchain manifest](M6B_TOOLCHAIN_MANIFEST_RUNBOOK.md)。
8. **M6a 内不生成 16 MiB `metadata` 控制样本。** p20 的格式化责任仍未知，而候选已经有独立、足以阻止运行时归因的 system 根层级缺陷。M6b.0 设计、M6b.1 JSON guard 与 M6b.2 oracle 路线已经完成，但真实 ext4 fixture/toolchain 门禁尚未通过。只有该门禁通过、仍有明确的单变量信息增益、且 R-015 被重新评审后，才可另行提议隔离的非封装控制样本。该样本不得命名为发布物、不得加入 `MODIFIED_FILES`、不得封装或刷写。

**通过条件**：将“p20 无有效 ext4”“谁应初始化 p20”“当前候选来自哪里”“候选 system 的已证实根层级缺陷”和“谁/为何请求 bootloader 重启”明确分开；给出支持/反证和下一项最小单变量实验。若责任仍无法确定，停在离线证据阶段，而不是尝试 `flash`、`erase`、VCC/TXD 或 UART 交互。

## M6a 退出条件

以下四项必须全部满足，才可提议 M6b；并不自动授权刷写：

1. 已归档 USB PnP 原始证据，且 USB 状态被准确标注为“协议已验证”或“未建立标准 Fastboot”。
2. 已获得至少一份完整冷启动 UART 原始日志；**已由 `logs/device/20260725-004019/` 满足**。若以后物理上无法取得，须记录 J21 实际形态、已尝试的无损方法和客观阻塞证据。
3. 已列出 Recovery、BCB、槽位、AVB、super、ext4 与 init 的假设、支持/反驳证据和下一项最小实验；U3.2 已确认历史候选的错误 ext4 根输入，但 `metadata` 初始化责任与设备侧重启因果仍开放。M6b.0/M6b.1/M6b.2 设计门禁、管理员 H1、schema v2 H2a、SVM H2b、WSL/VMP H2c Apply、D-0054 的 B1 post-reboot/Ubuntu 环境和 D-0055 的 Linux oracle 工具链验收均已完成；下一步通过真实 synthetic fixture 后重新评估。
4. 官方原件、候选构建哈希、恢复介质和风险登记册都可追溯；下一项实验只改一个明确变量。

## 参考

- [AOSP Fastboot protocol](https://android.googlesource.com/platform/system/core/+/refs/heads/main/fastboot/README.md)
- [AOSP Windows Fastboot USB implementation](https://android.googlesource.com/platform/system/core/+/refs/heads/main/fastboot/usb_windows.cpp)
- [Microsoft WinUSB installation guidance](https://learn.microsoft.com/en-us/windows-hardware/drivers/usbcon/winusb-installation)
