# UBOX10 Android TV 固件定制工程

本仓库用于以可复现、可审计、可回退的方式研究并定制 UnblockTech UBOX10（I12 Pro Max / Allwinner H616）Android TV 12 固件。

当前阶段：**M0 — 原始固件基线与非侵入式分析**。不修改原始镜像，不刷写设备，不绕过 AVB，不获取 root。

## 开始位置

1. 阅读 `docs/PROJECT_CHARTER.md`，确认范围和不可违反的原则。
2. 阅读 `docs/RUNBOOK.md`，按阶段执行脚本。
3. 每次发现先记录在 `docs/DISCOVERIES.md`，再开展下一步。

当前唯一原始镜像保留在仓库根目录 `x12-1024.img`，且被 Git 忽略；在获得已验证的第二副本前不得移动或重命名。后续归档位置为 `firmware/original/`。必须以 `docs/FIRMWARE_BASELINE.md` 中的哈希校验其身份。

## 目录

`docs/` 为工程决策、证据、风险和操作手册；`scripts/` 为可复现自动化；`tools/` 为工具清单及固定版本；`work/` 为可随时删除的中间产物；`out/` 为候选输出物；`tests/` 为离线验证。

详见 `docs/ARCHITECTURE.md`。
