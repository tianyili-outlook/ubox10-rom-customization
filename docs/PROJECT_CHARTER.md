# 项目章程

## 目标

在保留 UBOX10 硬件适配（Wi‑Fi、蓝牙、以太网、HDMI/CEC、遥控器、音视频解码）的前提下，基于已验证的官方 Android TV 12 固件制作干净、稳定且可维护的 Android TV 系统。预装应用仅包含 FLauncher、SmartTube、Kodi、VLC、LocalSend 及 Gboard；Jellyfin、Moonlight、AirPlay 及 Google 服务等由用户自行安装，不内置于 ROM 中。移除 UnblockTech 的非硬件定制和网络干预组件。

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

## 阶段门禁

仅在前一阶段的证据、验证结果和风险记录完整时进入下一阶段。详见 `MILESTONES.md`。
