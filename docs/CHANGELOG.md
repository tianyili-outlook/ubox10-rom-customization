# 变更日志

遵循 Keep a Changelog 风格；所有日期使用 ISO 8601。

## [0.1.0] - 2026-07-19

### Added
- **M0 基线建立**：完成工程初始化、架构设计、目录分配以及原始固件 `x12-1024.img` 校验（SHA-256 为 `371a6536...`）。
- **Git 托管**：连接远程仓库 `tianyili-outlook/ubox10-rom-customization`，完成首个 Commits 的推送。
- **M1 解析与验证**：
  - 自研开源可审计的 Allwinner 固件工具 `tools/sunxi_image_tool.py`。
  - 数学证明并验证了 Allwinner 的累加和校验和算法。
  - 实现自动化脚本 `scripts/parse-image.ps1`，成功提取分区 manifest JSON，完成 10 个主分区的伴生校验和的一致性验证（全部成功）。
  - 更新工具锁、决策树和待办事项。
