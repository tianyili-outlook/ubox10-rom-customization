# 项目章程

## 目标

在保留 UBOX10 硬件适配（Wi‑Fi、蓝牙、以太网、HDMI/CEC、遥控器、音视频解码）的前提下，基于官方 Android TV 12 固件制作干净、稳定且可维护的 Android TV 系统。产品目标是 Projectivy Launcher、SmartTube、Kodi、Jellyfin、Moonlight、AirPlay 接收能力以及现有合法 Google 服务/Google Play 的可用性；具体预装包、来源、许可证、签名和兼容性必须在 M6b 通过后以 manifest 决策。现有 FLauncher / VLC / LocalSend / Gboard 列表只是历史候选集，尚未构成实机产品承诺。移除 UnblockTech 的非硬件定制和网络干预组件。

## 明确不做

- 不以 root、Magisk 或解锁为项目目标。
- 不把“仅安装第三方桌面”视为完成。
- 不以恢复官方原样固件为成果。
- 不在未建立可恢复路径前刷写候选镜像。

## 工程不变量

1. 原始镜像只读保存，按 SHA-256 身份校验。
2. 任何改动先由清单（manifest）描述，再由脚本执行。
3. 修改前后均保留分区哈希、工具版本、命令日志和差异报告。
4. 未解析功能归属的文件、服务、SELinux 规则不得删除。
5. AVB 链、动态分区元数据、A/B 槽位语义必须验证，不可凭猜测重建。
6. 不得仅凭 VID/PID、设备名称或单次推断为设备接口命名协议；协议结论至少需要一次不修改状态的握手。
7. root ADB、Permissive SELinux、修改 init/boot/vendor_boot 的诊断构建与发布候选必须严格隔离。
8. 在完成无修改启动链取证前，不刷入新的诊断镜像。
9. 不复制、重签或重新分发受许可限制的 Google 组件；Google Play 可用性必须以设备原有授权状态和实机回归为准，不能仅由 APK 注入宣称实现。

## 阶段门禁

仅在前一阶段的证据、验证结果和风险记录完整时进入下一阶段。详见 `MILESTONES.md`。

## 当前 M6 强制门禁

Fastboot 协议已通过只读 `getvar version` 验证，但该实现不支持槽位/userspace 变量；实验 #11.1 已构建但暂停，未执行物理刷写。Fastboot 信息增益已耗尽，当前只允许保存既有主机绑定备份与进行 3.3V UART 被动监听。详见 `M6_DIAGNOSTIC_PLAN.md`、`M6_HYPOTHESIS_MATRIX.md` 与 `UART_RUNBOOK.md`。
