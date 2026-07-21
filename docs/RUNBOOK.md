# UBOX10 ROM 改造运行手册

## 当前授权范围：M6a 无修改启动链取证

当前设备尚未进入 Android System。Fastboot 接口描述符已确认，但 Platform Tools 尚未完成命令握手。**构建、重打包、PhoenixCard 刷写和任何 boot/vendor_boot/vbmeta/Recovery 注入均暂停。** 当前可执行的步骤、风险和退出条件见 [M6 诊断计划](M6_DIAGNOSTIC_PLAN.md)。

允许的动作如下：

1. 记录 USB 枚举、设备管理器截图、PnP 驱动信息、Platform Tools 版本和原始命令输出。
2. 在用户明确确认后，进行 [Fastboot 主机 GUID 单变量试验](U1_FASTBOOT_HOST_BINDING_TRIAL.md)；此操作只影响 Windows 主机，只追加而不覆盖现有 `DeviceInterfaceGUIDs`，绝不重绑/安装驱动或关闭签名强制。
3. 使用 [UART 被动监听手册](UART_RUNBOOK.md) 采集冷启动日志：只接板端 GND 和 TX→适配器 RX，不接 VCC 或适配器 TX。

禁止的动作包括：`fastboot flash`、`erase`、`download`、`boot`、`continue`、`reboot`、`set_active`、`oem`、`unlock`，以及任何新的 PhoenixCard 刷写。

## M6a 操作顺序

1. 运行 `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\collect-usb-evidence.ps1` 归档 Windows PnP 信息；`Bypass` 仅对该进程生效，脚本默认不向设备发送协议命令。
2. 审查输出中的驱动提供商、INF、Class GUID、错误码和实例 ID，并附设备管理器截图。
3. 当前已有 WinUSB 服务。先审查 GUID 单变量试验及备份，获得用户确认后才可应用；不得安装仓库里手工修改过的 Google USB INF，也不得使用 Zadig Bind/Install。
4. 物理拔插后，只做 `fastboot devices`，成功出现序列号后才执行 `fastboot getvar version`。不要先运行 `getvar all`。
5. 当前标准握手已验证，但 Allwinner Fastboot 不支持槽位与 userspace 白名单变量；不要扩展为 `getvar all`。直接转为 UART 被动监听以获得启动链证据。

## M6b 以后才恢复的构建流程

在 M6a 通过后，先做 [验证计划](VALIDATION_PLAN.md) 中的零内容改动 round-trip：PhoenixCard 容器 → super → ext4。只有每层语义差分通过后，才允许生成一次仅含一个 manifest 变更的候选镜像。

## 烧录安全门禁（当前不执行）

PhoenixCard 写入属**严重风险**。将来需要同时满足：官方原件校验通过、回退介质可用、目标卡的物理磁盘号/容量/盘符已由用户复核、候选镜像和日志哈希已归档、单变量实验已批准。

`diskpart clean` 会清空目标磁盘；不得把它作为常规排障步骤。若未来确有必要，必须在执行前由用户确认精确磁盘编号、容量和无重要数据。
