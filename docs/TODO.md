# 待办事项

## 当前：M6a 无修改启动链取证

### 已完成证据

- [x] 归档 Windows 设备管理器截图：`sunxi`，`USB\VID_1F3A&PID_1010&REV_0200` / `USB\VID_1F3A&PID_1010`。
- [x] 归档 `logs/device/20260722-001337/` 的 PnP 原始证据、Platform Tools 版本和 SHA-256；设备状态为 `OK`、`Problem=0`，当前服务为 `WinUSB`。
- [x] 确认 PnP 兼容 ID 含 `USB\\COMPAT_VID_1F3A&Class_FF&SubClass_42&Prot_03`，符合 AOSP Fastboot 接口描述符条件；这不是命令握手。
- [x] 确认当前 `oem79.inf`（libwdi）只注册 `{9D8998B8-AD0B-4656-B575-AF23D189A1A8}`，而 Android USB interface GUID `{F72FE0D4-CBCB-407D-8814-9ED673D0DD6B}` 缺失。
- [x] 执行标准 Fastboot 只读探测：`fastboot devices`、`fastboot getvar all` 均等待设备，未建立命令握手。
- [x] 冻结实验 #11.1：已构建，**未物理刷写**。

### 下一步（按顺序）

- [x] 审阅并获得 [Fastboot 主机 GUID 单变量试验](U1_FASTBOOT_HOST_BINDING_TRIAL.md) 的用户明确授权。自动化环境没有 Windows 管理员令牌，预检安全退出，未改变主机或设备。
- [x] 在管理员 PowerShell 中完成 `Apply`：`logs/device/20260722-004314/` 含 `guid-backup.json`、`ExpectedGuidPresent: True` 和 SHA-256 清单；原 GUID 均保留。
- [x] 物理拔插后，`fastboot devices` 输出 `992304568773    fastboot`。Windows 主机枚举已恢复。
- [x] 执行并归档 `fastboot getvar version`：`logs/device/20260722-004720/` 返回 `version: 0.5`；标准 Fastboot 现为协议已验证。
- [x] 自动化逐项读取 M6a Fastboot 白名单，输出在 `logs/device/20260722-004937/`：`product=sunxi`、`secure=yes`，其余槽位/userspace 变量均 `not supported`。
- [ ] Fastboot 已达到可用证据上限；准备 3.3V UART 适配器、杜邦线与（如 J21 未焊针）pogo pin，执行第一次**只接 GND 和 TX→RX**的冷启动监听。
- [ ] 采集当前设备状态的被动 UART 冷启动原始日志；记录接线照片、波特率、时间和 SHA-256。
- [ ] 根据 UART 或协议证据建立“Recovery 触发 / BCB / 槽位 / AVB / super / ext4 / init”假设表，选定下一项**单变量**实验。

### 明确暂停

- [ ] **实验 #11.1** — 暂停，未刷入。恢复条件：M6a 退出条件满足、风险登记册更新、官方回退路径可用、变更缩减为一个可验证假设并获明确批准。
- [ ] 新的 PhoenixCard 刷写、Recovery ADB 注入、SELinux Permissive、root ADB、AVB 禁用标志和多 UDC “散弹枪”方案均暂停。

## 后续里程碑

- [ ] **M6b**：PhoenixCard 容器、super、ext4 的零内容改动 round-trip 和语义差分。
- [ ] **M6c**：每次只引入一个 APK 删除、属性修改或预装 APK 的受控回归。
- [ ] **产品 manifest 决策**：在 M6b 后分别确认 Projectivy、SmartTube、Kodi、Jellyfin、Moonlight、AirPlay 和 Google 服务/Play 的来源、许可证、分区位置、签名与回归项目；不沿用历史候选列表作为默认决定。
- [ ] **M7**：Android System 启动、硬件功能矩阵与官方回退验证后，才准备候选发布。

## 历史工作（仅记录，不代表实机放行）

- [x] M0/M1：官方镜像基线、容器清单与校验。
- [x] M2/M3：分区、AVB、APK 和 init 静态审计。
- [x] M4/M5：候选重建与容器校验；运行时验证未完成。
- [x] 实验 #1–#10：历史物理和离线排查，原始现象见 [M6_DEBUG_LOG.md](M6_DEBUG_LOG.md)。其中因果解释均须以当前发现记录为准。
