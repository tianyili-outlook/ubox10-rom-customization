# 文档入口

## 当前阶段

- 稳定基线：Test8r2。
- 当前实验：Test9w1，正在进行 AW869A/AIC8800D `ant_div=N` 真机验证。
- 产品体验主线：Test9.1 Wi‑Fi → Test9.2 iPhone 遥控文字输入 → Test9.3 应用与整体验收。
- 架构研究主线：M8.0 只读盘点，与 Test9 实机测试并行；在图形栈和 DRM 基线明确前不制作 64 位候选。

## 核心文档

| 主题 | 文档 |
|---|---|
| 当前操作 | [RUNBOOK.md](RUNBOOK.md) |
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

[research/m8/README.md](research/m8/README.md) 定义 M8.0 的输入、交付物、状态标签和敏感数据边界。大型 BSP、AOSP 构建产物、闭源 blob、设备密钥和用户数据不进入 Git。

## 权威顺序

若文档互相冲突，按以下顺序处理：

1. 当前用户指令和 `RUNBOOK.md`；
2. `DECISIONS.md`、`VALIDATION_PLAN.md`；
3. `ROADMAP.md` 与 M8 架构计划；
4. `DISCOVERIES.md` 中的已确认事实；
5. `archive/` 历史材料。

归档文件用于追溯，不得据此恢复已经完成或淘汰的旧任务。
