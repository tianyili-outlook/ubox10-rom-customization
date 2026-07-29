# 文档入口

## 当前阶段

- 稳定基线：Test8r2。
- Test9r2 技术探针已完成：system_ext RRO、provider、Remote v2 端口、mDNS、
  官方 Google TV iPhone 配对、遥控和文字输入均通过；唯一必要的临时修正是
  授予 `BLUETOOTH_CONNECT`。因 Play Store 仍不兼容，候选总体为
  `PARTIAL`、不晋级；本地镜像已删除，复现配置与证据保留。
- Test9r1 真机失败原因已确认：RRO 位于未扫描路径，framework 未白名单化
  provider；该镜像已删除，配置和证据保留。
- Test9w1 已退役；后续不继承其 driver patch。
- 产品体验主线：M7 已完成。Test8r2 为稳定基线；Test9.3 五项 userdata
  应用完成来源锁、统一安装、启动、重启和实体遥控验收，SmartTube 1080p、
  AnExplorer USB/APK 与 AirReceiverLite iPhone 音视频通过。Kodi/Jellyfin/
  Moonlight 的外部资源缺口以有限豁免记录，不阻塞 M7。
- 架构研究主线：M8.0 共享证据门 → M8A ARM32 真 ATV → M8B
  AArch64/multilib；M8.GMS、M8.INPUT 和 M8.DRM 独立验收。

## 核心文档

| 主题 | 文档 |
|---|---|
| M7 发布、刷机与一键恢复 | [仓库首页](../README.md) |
| 当前操作 | [RUNBOOK.md](RUNBOOK.md) |
| M7 完成报告与历史实验 | [archive/m7/M7_COMPLETION_REPORT.md](archive/m7/M7_COMPLETION_REPORT.md) |
| TV GMS/Remote 参考项目与路线门 | [research/tv-gms-remote/README.md](research/tv-gms-remote/README.md) |
| Test9r2 真机运行报告 | [research/tv-gms-remote/test9r2-runtime-report.md](research/tv-gms-remote/test9r2-runtime-report.md) |
| Test9r2 后路线决策 | [research/tv-gms-remote/route-decision.md](research/tv-gms-remote/route-decision.md) |
| 产品与 M8 路线 | [ROADMAP.md](ROADMAP.md) |
| M8 架构计划 | [architecture/M8_ARM64_AOSP_TV_MIGRATION.md](architecture/M8_ARM64_AOSP_TV_MIGRATION.md) |
| 当前待办与里程碑 | [TODO.md](TODO.md)、[MILESTONES.md](MILESTONES.md) |
| 验收门槛 | [VALIDATION_PLAN.md](VALIDATION_PLAN.md) |
| 项目目标 | [PROJECT_CHARTER.md](PROJECT_CHARTER.md) |
| 工程与主机环境 | [ARCHITECTURE.md](ARCHITECTURE.md)、[BUILD_ENVIRONMENT.md](BUILD_ENVIRONMENT.md) |
| 固件与空间管理 | [FIRMWARE_BASELINE.md](FIRMWARE_BASELINE.md)、[STORAGE_AND_REPRODUCTION.md](STORAGE_AND_REPRODUCTION.md) |
| 事实、决策和风险 | [DISCOVERIES.md](DISCOVERIES.md)、[DECISIONS.md](DECISIONS.md)、[RISK_REGISTER.md](RISK_REGISTER.md) |
| 历史 | [CHANGELOG.md](CHANGELOG.md)、[archive/README.md](archive/README.md) |

## M8 研究区

[research/m8/README.md](research/m8/README.md) 定义 M8.0/M8A/M8B 的输入、
交付物、状态标签和敏感数据边界；
[research/tv-gms-remote/README.md](research/tv-gms-remote/README.md) 记录
外部参考项目、Test9r2 结果分类和 TV GMS/remote 路线门。大型 BSP、AOSP
构建产物、闭源 blob、设备密钥和用户数据不进入 Git。

## 权威顺序

若文档互相冲突，按以下顺序处理：

1. 当前用户指令和 `RUNBOOK.md`；
2. `DECISIONS.md`、`VALIDATION_PLAN.md`；
3. `ROADMAP.md` 与 M8 架构计划；
4. `DISCOVERIES.md` 中的已确认事实；
5. `archive/` 历史材料。

归档文件用于追溯，不得据此恢复已经完成或淘汰的旧任务。
