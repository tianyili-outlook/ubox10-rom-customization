# 工程架构

## 推荐技术栈

- **Python 3.11+**：解析元数据、生成清单、哈希、报告与测试；跨平台且适合二进制编排。
- **PowerShell 7+**：Windows 上的薄包装脚本和环境检查；不承载复杂解析逻辑。
- **Bash（可选，WSL/容器）**：调用 AOSP/Android 镜像工具。
- **AOSP 官方工具**：`lpunpack/lpmake/lpdump`、`avbtool.py`、`unpack_bootimg.py/mkbootimg.py`、`simg2img/img2simg`、`mkdtboimg.py`。
- **Allwinner 专用工具**：待确认来源、版本、许可证与输出可复现性后才纳入锁定清单。PhoenixCard 打包不可在解析完成前假设工具或格式。

## 仓库布局

```
docs/                 章程、证据、决策、风险、运行手册
firmware/original/    原始输入（Git 忽略，只读基线）
firmware/manifests/   输入/输出物的机器可读清单
scripts/              可重复执行的入口脚本
src/                  Python 库：容器、分区、APK、策略、验证
tests/fixtures/       小型、可公开分发的测试样本
tools/                工具来源、版本与校验值（不提交私有二进制）
work/                 临时提取与挂载目录（Git 忽略）
out/                  候选镜像、校验和与签名报告（Git 忽略）
out/debug-quarantine/ 多变量诊断镜像隔离区（Git 忽略，不可发布）
logs/                 每次操作日志（Git 忽略）
logs/device/<run-id>/ USB PnP、UART 原始日志、照片索引与哈希
```

## 分层与数据流

`原始 PhoenixCard 容器 → 容器目录清单 → 分区原件 → 分区/AVB/SELinux/APK 分析报告 → 变更清单 → 可重建分区 → 独立验证 → 候选 PhoenixCard 容器`。

每一箭头均生成输入哈希、输出哈希、工具版本和执行日志。`work/` 可删除；`firmware/original/` 与 Git 中的清单共同构成可追溯基线。

## 证据层级与 M6 门禁

项目使用四级证据标签，禁止跨级推断：

1. **已观察**：屏幕现象、USB 枚举、命令原始输出等物理事实。
2. **离线已验证**：主机侧镜像、分区、校验和或工具输出一致。
3. **协议已验证**：真实设备完成不修改状态的协议握手。
4. **实机已验证**：目标系统启动并完成相应功能回归。

离线校验（容器 checksum、`avbtool info_image`、`lpdump`）只能证明输出可解析，不能证明 Android 可以运行。进入 M6 后必须按下列顺序放行：

`只读硬件取证 → 原始日志/描述符归档 → 启动链假设表 → 零内容改动 round-trip → 单变量受控实验 → 功能回归`。

其中零内容改动 round-trip 必须分别覆盖 PhoenixCard 容器、super 逻辑分区和 ext4 文件系统，并对符号链接、UID/GID、mode、SELinux xattr、capability、硬链接及 ext4 features 做语义比对。诊断镜像放入 `out/debug-quarantine/`，不得与发布候选混用。
