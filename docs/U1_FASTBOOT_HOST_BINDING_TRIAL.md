# U1：Fastboot 主机 interface GUID 单变量试验

## 结论与目的

**当前建议的下一步不是刷写，也不是重新安装驱动。** 已连接设备已经使用 Microsoft `WinUSB` 服务；问题高度集中在该绑定没有注册 Android Platform Tools 用来发现设备的 interface GUID。

本试验只在 Windows 主机的一个现有注册表多字符串值中**追加**一个 GUID，用于验证这一因果假设。它不向 UBOX10 发送命令，不修改设备存储，不安装/卸载/重绑驱动，不解锁，也不改变任何固件分区。

执行需要用户对本文件和脚本内容作出明确确认；在此之前，只允许脚本的 `Inspect`（只读）模式。

## 已归档证据

证据目录为 `logs/device/20260722-001337/`，其校验和见同目录的 `SHA256SUMS.txt`：

| 项目 | 已确认事实 |
|---|---|
| 物理设备 | `USB\VID_1F3A&PID_1010\992304568773`，状态 `OK`，`Problem=0` |
| 接口描述符 | 兼容 ID 含 `USB\COMPAT_VID_1F3A&Class_FF&SubClass_42&Prot_03`；AOSP Fastboot 匹配 `0xff/0x42/0x03` |
| 当前服务 | `WinUSB` / `\Driver\WINUSB` |
| 当前驱动包 | `oem79.inf`，Provider `libwdi`，Class GUID `{88BAE032-5A81-49F0-BC3D-A4FF138216D6}` |
| 当前 INF 注册 GUID | `{9D8998B8-AD0B-4656-B575-AF23D189A1A8}` |
| 目标 GUID | `{F72FE0D4-CBCB-407D-8814-9ED673D0DD6B}`（AOSP Android USB interface GUID） |
| 关键差异 | 当前设备参数中没有目标 GUID；存在的 `{F72FE0D4-CBCB-407D-BC61-54A14A205A5A}` 不是同一个 GUID，不能替代它。 |

`usb-evidence.json` 的 SHA-256 为 `9823D913E07031822B41567C22DE3D88539E5D21F70431AFEAD29C2A3F766B33`；`fastboot.version.txt` 的 SHA-256 为 `69FDB6D057CBB0113153A8D9C069286B0572CFB395408926B5CA10608222F56E`。本机 `fastboot.exe` 为 Platform Tools r37.0.0。

参考实现：AOSP [Windows Fastboot USB 实现](https://android.googlesource.com/platform/system/core/+/refs/heads/main/fastboot/usb_windows.cpp) 的接口匹配条件，以及 [Android USB interface GUID 定义](https://android.googlesource.com/platform/development/+/refs/heads/main/host/windows/usb/api/adb_api.h)。

## 假设、判定与边界

| 项目 | 内容 |
|---|---|
| 假设 | Platform Tools 未枚举设备，是因为现有 libwdi WinUSB 绑定未公布目标 Android interface GUID，而不是设备没有 Fastboot 接口。 |
| 单变量 | 仅在唯一匹配的现有设备实例上，把目标 GUID 追加到 `DeviceInterfaceGUIDs`。 |
| 成功判据 | 物理拔插后，`fastboot devices` 显示序列号和 `fastboot`；随后 `fastboot getvar version` 收到 Fastboot 响应。 |
| 阴性判据 | `fastboot devices` 仍为空、设备不再正常枚举、或写后验证失败。阴性结果同样有价值：Windows GUID 不是唯一阻塞。 |
| 非目标 | 这不是安装包、不是长期驱动分发方案，也不证明 Android System、A/B 槽位或 Recovery 原因。 |

描述符匹配只让“接口身份”达到主机侧证据等级；只有成功的命令事务才达到“协议已验证”。

## 风险评估

**风险等级：中（仅 Windows 主机，可精确回滚）。**

- 好处：保留已工作的 `WinUSB` 驱动栈，不引入未知 INF、签名绕过或 Zadig 重绑变量。
- 风险：错误覆盖 `DeviceInterfaceGUIDs` 会影响这台主机对此 USB 设备的接口发现；操作通常需要管理员权限。
- 设备风险：低。脚本不执行 `fastboot`，也不对设备发包；随后规定的最小命令只读。
- 恢复：脚本在写前为完整原数组创建 JSON 备份并写入 SHA-256；若 Apply 的写后验证失败，会先尝试自动恢复原数组。其 `Rollback` 仅对备份中同一实例恢复原数组。然后物理拔插 USB。

不得使用仓库中修改过的 Google USB INF；不得关闭 Windows 驱动签名强制；不得使用 Zadig 的 Bind/Install。

## 操作程序

### 0. 预检（只读，当前允许）

设备保持在 `sunxi` 状态。以普通 PowerShell 先运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-fastboot-interface-guid.ps1 -Action Inspect
```

检查输出中恰好有一个 `USB\VID_1F3A&PID_1010` 现存实例，且 `ExpectedGuidPresent` 为 `false`。将生成的记录目录连同现有 PnP 证据保留。

若找不到或找到多个实例，**停止**。不要猜测实例 ID，也不要手工编辑注册表。

### 1. 应用（必须在用户明确授权之后）

以管理员 PowerShell 运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-fastboot-interface-guid.ps1 -Action Apply -IUnderstandThisChangesWindowsHostBinding
```

脚本会要求 PowerShell 的高影响确认。它将：

1. 再次验证仅有一个目标实例；
2. 将原有完整 `DeviceInterfaceGUIDs` 写入新的 `logs/device/<run-id>/guid-backup.json`；
3. 只追加目标 GUID，不删除、替换或重排原值；
4. 读取回写入值，并确认旧值仍全部存在；
5. 不调用 `fastboot`、`pnputil`、Zadig 或驱动安装程序。

完成后，物理拔出 UBOX10 的 USB 线，等待 5 秒再插回；不要使用设备管理器、不要重启设备、更不要刷写。

### 2. 最小协议阶梯（只读）

重新插入并确认设备仍为 `sunxi` 后，单独执行：

```powershell
.\tools\platform-tools\fastboot.exe devices
```

只有出现序列号后，才执行：

```powershell
.\tools\platform-tools\fastboot.exe getvar version
```

记录每条命令的原始输出和时间。不要执行 `getvar all`、`flash`、`erase`、`download`、`boot`、`continue`、`reboot`、`set_active`、`oem` 或 `unlock`。

### 3. 回滚

无论阴性结果还是出现主机侧异常，都可在管理员 PowerShell 中使用本次生成的备份：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-fastboot-interface-guid.ps1 -Action Rollback -BackupFile .\logs\device\<run-id>\guid-backup.json -IUnderstandThisChangesWindowsHostBinding
```

脚本会验证备份实例与当前唯一连接实例一致，再恢复原始多字符串数组。恢复后物理拔插 USB，并保存结果。不要删除驱动包或在没有记录的情况下改用其他驱动。

## 后续决策

| 结果 | 下一步 |
|---|---|
| `devices` 有序列号，`getvar version` 成功 | 将 Fastboot 标记为“协议已验证”；只读取 M6a 白名单变量，再按需要采集 UART。 |
| `devices` 仍为空 | 回滚，记录阴性结果；将 UART 被动监听提升为第一优先级。 |
| 设备不再正常枚举或脚本验证失败 | 立即回滚；如仍异常，使用 Windows 设备管理器恢复已归档的 `oem79.inf` 状态，停止试验并记录。 |
