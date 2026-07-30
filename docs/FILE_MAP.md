# M8 文件地图

这是新 Codex 会话的唯一入口。

## 阅读顺序

1. [m8/STATUS.md](m8/STATUS.md)：当前设备、阶段、阻塞项和下一动作。
2. [m8/ARCHITECTURE.md](m8/ARCHITECTURE.md)：项目理念、M8A/M8B 路线、
   硬门禁和轻量 candidate 标准。
3. [m8/TODO.md](m8/TODO.md)：只保留当前尚未完成的工作。
4. [m8/CANDIDATES.md](m8/CANDIDATES.md)：稳定基线、历史 candidate 与新
   candidate 记录规则。
5. 按任务进入 [m8/research/README.md](m8/research/README.md) 的证据文件。

## 单一事实来源

| 问题 | 文件 |
|---|---|
| Project philosophy、架构和阶段退出 | [m8/ARCHITECTURE.md](m8/ARCHITECTURE.md) |
| 当前阶段、事实和阻塞项 | [m8/STATUS.md](m8/STATUS.md) |
| 立即要做什么 | [m8/TODO.md](m8/TODO.md) |
| candidate 定义、晋级和历史 | [m8/CANDIDATES.md](m8/CANDIDATES.md) |
| 文件位置与阅读顺序 | 本文件 |
| 已确认的长期决策 | [DECISIONS.md](DECISIONS.md) |
| 设备和构建发现日志 | [DISCOVERIES.md](DISCOVERIES.md) |

`CHANGELOG.md`、`DECISIONS.md` 和 `DISCOVERIES.md` 是追加日志，不维护当前
状态。`archive/` 中的阶段名、待办和门禁全部是历史信息。

## 任务路由

| 要做的事 | 先读 |
|---|---|
| 建立 M8A AOSP product | [m8/research/m8a-atv-arm32/ubox10-atv-product-plan.md](m8/research/m8a-atv-arm32/ubox10-atv-product-plan.md)、[BUILD_ENVIRONMENT.md](BUILD_ENVIRONMENT.md) |
| 判断 ARM32/ARM64 依赖 | [m8/research/current-device/elf-dependency-summary.md](m8/research/current-device/elf-dependency-summary.md)、[m8/research/current-device/arm64-blockers.md](m8/research/current-device/arm64-blockers.md) |
| 定位 linker namespace / ELF 错误 | [m8/research/COMMUNITY_REFERENCES.md](m8/research/COMMUNITY_REFERENCES.md)、[m8/research/current-device/elf-dependency-summary.md](m8/research/current-device/elf-dependency-summary.md) |
| 设计 overlay / TV package | [m8/research/m8a-atv-arm32/overlay-permission-vintf-diff.md](m8/research/m8a-atv-arm32/overlay-permission-vintf-diff.md)、[m8/research/COMMUNITY_REFERENCES.md](m8/research/COMMUNITY_REFERENCES.md) |
| 处理 GMS / 手机遥控 | [archive/m7/tv-gms-remote/README.md](archive/m7/tv-gms-remote/README.md)、[m8/research/COMMUNITY_REFERENCES.md](m8/research/COMMUNITY_REFERENCES.md) |
| 判断 DRM / Netflix 边界 | [m8/research/drm-netflix/netflix-feasibility-verdict.md](m8/research/drm-netflix/netflix-feasibility-verdict.md) |
| 构建旧式 IMAGEWTY candidate | [BUILD_PIPELINE.md](BUILD_PIPELINE.md)、[BUILD_ENVIRONMENT.md](BUILD_ENVIRONMENT.md) |
| 刷机、抓日志或回退 | [RECOVERY_RUNBOOK.md](RECOVERY_RUNBOOK.md)、[UART_RUNBOOK.md](UART_RUNBOOK.md) |
| 核对官方镜像 / Test8r2 | [FIRMWARE_BASELINE.md](FIRMWARE_BASELINE.md)、[STORAGE_AND_REPRODUCTION.md](STORAGE_AND_REPRODUCTION.md) |
| 查旧路线或失败原因 | [archive/README.md](archive/README.md) |

## 目录

```text
docs/
├─ FILE_MAP.md
├─ m8/
│  ├─ ARCHITECTURE.md
│  ├─ STATUS.md
│  ├─ TODO.md
│  ├─ CANDIDATES.md
│  └─ research/
├─ BUILD_PIPELINE.md
├─ BUILD_ENVIRONMENT.md
├─ RECOVERY_RUNBOOK.md
├─ UART_RUNBOOK.md
├─ FIRMWARE_BASELINE.md
├─ STORAGE_AND_REPRODUCTION.md
├─ DECISIONS.md
├─ DISCOVERIES.md
├─ CHANGELOG.md
└─ archive/

configs/candidates/   可复现的旧 candidate 配置
configs/apps/         M7 用户态应用来源锁
scripts/              构建、采集、验证和恢复入口
tests/                小型单元测试与 fixture
tools/                AVB、super、ext4、IMAGEWTY 等核心工具
```

`firmware/`、`out/`、`work/` 和 `logs/` 主要是本地输入、可再生成产物或设备
日志；除已跟踪的小型清单外，不把它们当作文档事实来源。
