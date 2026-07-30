# M8 研究证据

本目录只保存可复用证据，不维护当前阶段或 TODO。当前事实以
[../STATUS.md](../STATUS.md) 为准。

## 当前设备

| 文件 | 内容 |
|---|---|
| [current-device/hardware-identity.md](current-device/hardware-identity.md) | 主板、SoC、RAM/eMMC、网络模组和接口 |
| [current-device/runtime-baseline.md](current-device/runtime-baseline.md) | Android、Kernel、ABI、图形、媒体、无线、VINTF/HAL |
| [current-device/compatibility-runtime-snapshot.md](current-device/compatibility-runtime-snapshot.md) | linkerconfig、APEX、classpath、uses-library、VINTF 轻量快照 |
| [current-device/linkerconfig-test8r2.txt](current-device/linkerconfig-test8r2.txt) | Test8r2 完整生成态 linkerconfig |
| [current-device/elf-inventory.csv](current-device/elf-inventory.csv) | 四分区 ELF 清单 |
| [current-device/elf-dependency-summary.md](current-device/elf-dependency-summary.md) | ELF 统计与 name-level 依赖结论 |
| [current-device/hal-inventory.json](current-device/hal-inventory.json) | HAL/service 清单 |
| [current-device/kernel-module-inventory.csv](current-device/kernel-module-inventory.csv) | Kernel module 清单 |
| [current-device/arm64-blockers.md](current-device/arm64-blockers.md) | M8A/M8B Go/No-Go |

## M8A ARM32 ATV

| 文件 | 内容 |
|---|---|
| [m8a-atv-arm32/source-lock.md](m8a-atv-arm32/source-lock.md) | Android 12 manifest、superproject 和 ATV revision |
| [m8a-atv-arm32/product-package-diff.md](m8a-atv-arm32/product-package-diff.md) | 当前 product 与 AOSP ATV package 差异 |
| [m8a-atv-arm32/overlay-permission-vintf-diff.md](m8a-atv-arm32/overlay-permission-vintf-diff.md) | overlay、permission、VINTF 差异 |
| [m8a-atv-arm32/partition-budget.md](m8a-atv-arm32/partition-budget.md) | logical partition 容量 |
| [m8a-atv-arm32/ubox10-atv-product-plan.md](m8a-atv-arm32/ubox10-atv-product-plan.md) | UBOX10 product 继承和保留边界 |

## DRM / Netflix

| 文件 | 内容 |
|---|---|
| [drm-netflix/collection-plan.md](drm-netflix/collection-plan.md) | 只读采集方法 |
| [drm-netflix/widevine-report.md](drm-netflix/widevine-report.md) | Widevine 结果 |
| [drm-netflix/drm-service-inventory.md](drm-netflix/drm-service-inventory.md) | DRM 服务与文件 |
| [drm-netflix/secure-codec-inventory.csv](drm-netflix/secure-codec-inventory.csv) | secure codec 检查 |
| [drm-netflix/hdcp-status.md](drm-netflix/hdcp-status.md) | HDCP 状态 |
| [drm-netflix/netflix-feasibility-verdict.md](drm-netflix/netflix-feasibility-verdict.md) | 当前能力边界 |

## 外部参考

[COMMUNITY_REFERENCES.md](COMMUNITY_REFERENCES.md) 只收录对 M8 有直接借鉴价值
的上游项目，并明确哪些内容不能直接复制或刷入 UBOX10。

Test9/GMS/Remote 的历史真机证据已归档到
[../../archive/m7/tv-gms-remote/](../../archive/m7/tv-gms-remote/)。

## 重建

```powershell
python .\scripts\inventory-elf.py '@configs/m8-test8r2-elf.args'
.\scripts\capture-m8-runtime-readonly.ps1 -Device "<电视IP>:7896"
.\scripts\capture-m8-runtime-readonly.ps1 -Device "<电视IP>:7896" -CompatibilityOnly -UserDataAppsPresent
.\scripts\run-m8-drm-probe.ps1 -Device "<电视IP>:7896"
```

ADB 可执行文件不在项目默认位置或需要隔离 server 时，可另传
`-AdbExecutable` 与 `-AdbServerPort`。

报告只保留必要的脱敏事实。闭源 blob、Google APK、账号、设备密钥、TEE、
Widevine/HDCP/keybox 材料和大型构建产物不进入 Git。
