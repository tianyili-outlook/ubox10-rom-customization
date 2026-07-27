# M6b.0：零内容 `system` root-hierarchy control 设计

> 历史设计资料：根层级缺陷已规避；测试版 1 直接编辑官方 ext4，不使用旧的全量重建路径。

- 状态：**设计已建立，尚未执行构建**
- 日期：2026-07-25
- 风险等级：低（本文件与未来 manifest/fixture 设计仅离线）；任何实际 ext4 重建为中等风险的主机离线操作；任何设备写入仍为严重风险，且不属于本阶段。
- 前置发现：[D-0036](DISCOVERIES.md#d-0036--候选-system_a-确认将官方-system-子目录错误扁平化到-ext4-根目录)、[D-0037](DISCOVERIES.md#d-0037--重建脚本已确认选择错误的-system-ext4-根输入是候选目录层级扁平化的直接本地原因) 与 [D-0038](DISCOVERIES.md#d-0038--当前-ext4-提取重建工具链无法证明保留完整文件系统语义)。

## 1. 目标

本控制实验要证明的不是“可以生成一个镜像”，而是以下更小、可证伪的命题：

> 对本设备的官方 `system_a`，如果重建输入确实代表 ext4 根目录 `/`，则零内容变更的重建流程可以保留运行时所需的目录层级与文件系统语义；若不能证明，流程停止在离线工具层。

这里的关键层级是官方 ext4 根目录 `/` 下存在 `system/` 子目录。D-0037 已证实历史候选错误地把这个 `system/` 子目录本身传给 `make_ext4fs`，因此候选的 ext4 根没有 `/system`。

完整字段、规范化、比较结果和 allowlist 规则由 [ext4 语义 manifest 规范 v1](M6B_EXT4_SEMANTIC_MANIFEST_SPEC.md) 定义。宿主目录本身不是元数据权威：它必须由该 manifest 驱动并反向验证。

这项工作**不**试图：

- 解释或修复 p20 `metadata` 为什么没有有效 ext4；
- 推断当前设备实际装载了哪一个本地文件；
- 改写 `repack-rom.py`、`purify-rom.py`、`pack_image.py` 或任何镜像；
- 生成可刷写的 super、vbmeta、PhoenixCard 或 metadata 映像；
- 连接 UBOX10、运行 Fastboot、发送 UART 数据，或改变 FT232RL 接线。

## 2. 决策记录

| 项目 | 内容 |
|---|---|
| 决策 | 不直接将 `repack-rom.py` 的源路径改为 `work/system_extracted`；先实现并评审 M6b.0 的语义 manifest、根目录断言和失败 fixture。 |
| 理由 | 错误路径只解释目录层级扁平化。现有提取/重建仍未证明保留符号链接、UID/GID、SELinux xattr、capability、硬链接、ACL、ext4 特征和 AVB 语义。 |
| 收益 | 将“目录根正确”与“整个文件系统可用”分成独立、机器可判定的门禁，避免再次把多个变量合入一个候选。 |
| 风险 | 前期仅产生文档、manifest 和 fixture，不能快速得到可刷写产物；实现语义读取器需要额外工作。 |
| 恢复 | M6b.0 不写设备且不覆盖官方输入。任一门禁失败即停止在对应离线层，保留报告与哈希；官方 `x12-1024.img` 继续是唯一恢复锚点。 |

该决策也由 [ADR-0009](DECISIONS.md#adr-0009先设计-m6b0-root-hierarchy-control不直接修补历史重建脚本) 固化。

## 3. 输入冻结与隔离

| 角色 | 允许的输入 / 证据 | 约束 |
|---|---|---|
| 官方容器基线 | 根目录 `x12-1024.img`；SHA-256 `371A653604618E8B78786F279EA6F64E5D1028B430C9B41F330B08456A264065` | 只读；不得覆盖、改名或当作输出。 |
| 官方 super 基线 | `firmware/extracted/super.fex`；SHA-256 `BE6FAAA476D5DD17F9E6578ED8A48DA351C9D7C7EFD2C9AEBD65788F42A7F479` | 通过 D-0034 追溯到官方容器；不得对其直接运行会生成同级 `.unsparse.img` 的工具。 |
| 官方语义事实 | `logs/analysis/20260725-u3.2-logical-system-init-audit-r2/` 与其 SHA-256 `2685A6DD2E152B35671848F7AB425F38A35B5FFA4265E4FE251F8747768D37A4` | 已确认官方 ext4 根有 `system/`，且该目录含 22 项。 |
| 历史工作树 | `work/system_extracted/` | 仅可作为 D-0037 的历史路径证据；其可能经历过裁剪，**不得**作为零内容 control 的输入。 |
| 已隔离候选 | `work/super.img`、`work/boot.img`、`work/vendor_boot.img`、`x12-purified.img` | 只可用于缺陷对照；不得作为基线、恢复物、构建输入或刷写物。 |

未来实际执行时，必须从官方 `system_a` 重新生成一个全新、带 run-id 的 manifest 驱动 staging 根，例如 `out/m6b-root-control/<run-id>/official-system-root/`。此路径是新的工作副本，不覆盖 `work/`；其 `materialized-tree` manifest 必须与官方 `direct-image` manifest 语义相同，并证明它对应 ext4 `/`，而非官方 `/system` 子目录。宿主 Windows 文件属性不能替代 manifest 内的 POSIX/xattr/链接事实。

## 4. 语义 manifest 合同

M6b.0 首先实现可机器读取、稳定排序的 `ext4-semantic-manifest.json`。完整 schema 见 [规范 v1](M6B_EXT4_SEMANTIC_MANIFEST_SPEC.md)；它直接描述官方 logical `system_a`，不能用当前 `.symlink` 文本存根代替真实文件系统信息。

每个目录项至少记录：

| 分类 | 必填字段 | 比较规则 |
|---|---|---|
| 路径与类型 | 绝对逻辑路径、`regular` / `directory` / `symlink` / 设备节点 / FIFO / socket | **必须相同**；根 `/` 与根级 `system/` 必须被显式断言。 |
| 普通文件 | 逻辑大小、内容 SHA-256、稀疏洞布局（如存在） | **必须相同**。 |
| 符号链接 | 原始 link target（非宿主解析结果） | **必须相同**。 |
| 权限与身份 | mode（含特殊位）、UID、GID、inode flags、link count | **必须相同**，除非有单独批准的格式化理由。 |
| 安全语义 | SELinux xattr、Linux capability xattr、POSIX ACL | **必须相同**；缺失或无法解析即失败，不可默认为空。 |
| 硬链接 | path → canonical inode group 的关系 | 拓扑必须相同；绝对 inode 编号本身可不同。 |
| 文件系统级 | ext4 block size、feature flags、label、UUID、reserved blocks、journal/inode 参数 | 全部记录；任何变化必须逐项说明其运行时影响，不能靠人工抽样放行。 |
| 诊断字段 | atime/ctime/mtime、inode 编号、块映射、generation | 必须记录并比较；若工具链必然改变，差异须在 schema 中明确标为“允许但需解释”，不得静默忽略。 |

根 manifest 还必须包含输入 super、LP metadata、`system_a` extent、提取器版本/提交、命令行、输出 SHA-256 清单和“未访问设备”的声明。

## 5. 源根不变量与防呆规则

对本设备的 `system_a`，未来重建入口必须同时满足下列不变量：

1. 源目录由本轮新生成、与官方 `direct-image` 基线相同的 **根** manifest 标识，而不是由字符串名称猜测。
2. 源根的 manifest 必须含有目录项 `/system`；其子项应包含至少 `bin`、`etc`、`lib`、`framework`、`app` 等已知官方结构。
3. 传给 ext4 构建器的源目录必须是由该 manifest 驱动并反向验证的 staging 根；仅目录路径相同不足以证明 UID/GID、xattr、链接或根层级正确。
4. 若传入目录恰好代表官方 `/system` 子树，或其 manifest 缺少根级 `/system`，root-hierarchy guard 必须拒绝执行并返回非零状态。
5. `system` 分区的挂载点参数（例如 `-a /system`）与“文件系统根目录输入”是不同概念；测试必须覆盖二者，防止以挂载点掩盖错误源根。

历史 `work/system_extracted/system` 是本设备上第 4 条要拒绝的反例；它不是未来重建的快捷修复对象。

## 6. 分阶段放行

### Gate 0：设计审阅（当前阶段）

- [x] D-0036 与 D-0037 的证据、哈希和边界已写入发现记录。
- [x] 已明确候选 `work/` 树与候选 PhoenixCard 均不能做 zero-content 输入。
- [x] 已静态确认历史 `extract_ext4.py` 与 `make_ext4fs` 调用缺少完整语义保真证据（D-0038）。
- [x] 已建立本设计、ADR-0009、风险 R-018 与测试策略。
- [x] 已建立 [ext4 语义 manifest 规范 v1](M6B_EXT4_SEMANTIC_MANIFEST_SPEC.md)，默认零差异且没有自动 allowlist。
- [x] 已完成 [manifest 规范 v1 的 Gate 0 设计审阅](M6B_EXT4_SEMANTIC_MANIFEST_SPEC.md#12-gate-0-设计审阅记录)：默认没有 allowlist，未知字段 fail closed；这只放行小型 JSON guard fixture，不放行 ext4 构建。

### Gate 1：公开小型 fixture 的失败优先测试

先创建可公开分发的小型 ext4 fixture，而不是直接处理官方大镜像。必须至少覆盖：

1. **M6b.1 已完成（JSON 层）**：最小 manifest 正例声明 ext4 根含 `system/bin/init` 时 guard 接受；反例把 `system/` 子树标作根时 guard 以根级 `system` 缺失和 prohibited identity 拒绝（D-0039）。该步骤未创建 ext4。
2. 后续 ext4 fixture 必须复现同一正反例：ext4 根含 `system/bin/init` 时构建输入为 ext4 根；同一树的 `system/` 子目录作为构建输入时 guard 必须拒绝。
3. 真实符号链接、至少一个硬链接、非默认 UID/GID/mode、SELinux xattr、capability/ACL（工具可支持的最小集合）；manifest 能导出并比较。
4. manifest 或提取器遇到无法保存的语义时必须失败，不能降级成普通文本文件或默认权限。

只有 fixture 的正反例均通过，才允许读取官方 `system_a` 的完整语义。

### Gate 2：官方 `system_a` 语义基线

1. 从 D-0034 锁定的官方 sparse super 流式定位 logical `system_a`；不得在输入旁生成 `.unsparse.img`。
2. 生成完整官方语义 manifest 与 SHA-256 清单。
3. 通过 manifest 驱动的 staging adapter 生成全新 run-id 目录，并对其 `materialized-tree` manifest 与直接读取的官方 manifest 做零差异比对。
4. 若任何属性不能导出或不相同，停止。不得以修改 `repack-rom.py` 或补写文件来绕过。

### Gate 3：隔离的零内容 ext4 control（未来，需工程审阅）

只有 Gate 1/2 全部通过后，才允许在新的 `out/m6b-root-control/<run-id>/` 下调用重建器。该 control 必须满足：

- 不删除、不新增、不替换 APK；不修改 `build.prop`、overlay、init、boot、vendor_boot、dtbo、vbmeta、分区大小或 LP layout；
- 构建源经第 5 节 guard 认证为 manifest-verified 的官方 ext4 根 staging；
- 所有中间文件、工具版本、命令行、输入输出 SHA-256 写入独立日志；
- 输出命名为 `control-only`，并标记为**不可刷写**；不进入 `MODIFIED_FILES`，不调用 `lpmake`、`avbtool add_*footer` 或 `pack_image.py`。

输出 ext4 必须通过完整语义差分。任何未批准的差异，包括 `/system` 层级缺失，均为失败；不得进入 Gate 4。

### Gate 4：super、AVB 与容器边界（M6b 后续，不由本设计自动授权）

仅在 Gate 3 成功后，才分别设计：

1. super/LP 的零内容 containment 与 metadata/extent 差分；
2. AVB descriptor、public key、rollback index、salt、hashtree/FEC 与运行时信任的单独审计；
3. PhoenixCard 容器目录、映射、填充和伴生校验的零内容对照。

原始 AVB 私钥未知时，任何重新签名都只能证明离线结构，**不能**自动证明 bootloader 会信任它。M6b.0 不产生 AVB、super 或 PhoenixCard 产物，故不宣称可启动性。

### Gate 5：硬件阶段（M6c 之外，须单独授权）

即使 Gate 4 通过，也不自动授权设备写入。任何硬件试验必须先满足 M6a 退出条件、完成官方回退介质核验、明确单变量假设、更新风险登记册，并获得用户对精确镜像 SHA-256 与操作方式的单独授权。

## 7. 失败处理与回滚

| 失败位置 | 立即动作 | 禁止动作 | 恢复/下一步 |
|---|---|---|---|
| fixture / parser | 固化最小失败样本与测试结果 | 不触碰官方镜像或历史重建脚本 | 修复 parser/manifest，再跑 fixture。 |
| 官方提取语义差分 | 记录不支持的属性或提取差异 | 不把缺失属性默认化，不转入构建 | 改进提取/比较器；官方输入保持不变。 |
| root-hierarchy guard 拒绝 | 保存 guard 报告 | 不手工复制或移动 `system/` 内容后重试 | 回到源根 mapping 设计。 |
| 零内容 ext4 差分 | 冻结输出为不可刷写失败物 | 不打包 super、重签 AVB 或刷写 | 对照 manifest 定位单一语义，再创建 fixture。 |
| super / AVB 差分 | 停在对应层 | 不用 `--flags 2`、不禁用验证、不中途刷写 | 单独建立下一层的最小 control。 |

在 M6b.0 范围内没有设备写入，因此“回滚”是保留官方输入与报告、丢弃或隔离失败输出；不需要也不允许用 Fastboot/PhoenixCard 做恢复动作。

## 8. 与 `metadata` / UART 结论的关系

M6b.0 不能把 D-0037 倒推成 p20 问题的原因：根目录扁平化发生在历史候选 system 重建；UART 只观察到本次启动中 p20 无有效 ext4 后很快出现 bootloader reboot。二者可能相关，也可能独立。

因此本阶段的恢复计划是：先消除已证实的候选 system 结构缺陷作为混杂变量，再决定 `metadata` 格式化责任是否仍值得设计一个单变量、离线且非封装的控制样本。R-015 继续生效；不得预置或注入 metadata。

## 9. M6b.2 主机能力边界

2026-07-25 的只读盘点已记录为 D-0040：当前主机没有 WSL 发行版、Docker/Podman、`debugfs`/`e2fsck` 等独立 e2fsprogs 工具，历史 `extract_ext4.py` 也因 Python `ext4` 模块不可导入而无法运行。仓库内只有尚未单独锁定的 Android `mke2fs 1.47.2`，它可以声明 `-d root-directory|tarball`，但不能因此推断完整语义保真。

官方源码核验 D-0041 进一步确认：目录输入依赖宿主 `lstat` 与编译期 xattr API，tarball 输入依赖 libarchive，而 AOSP 正式 Android 映像流程是 `mke2fs` 建空文件系统后再由 `e2fsdroid` 根据 `fs_config/file_contexts` 配置权限、capability 与 SELinux 标签。因此本机 Windows `mke2fs -d` 不能成为完整 oracle。

[M6b.2 ext4 fixture oracle 设计](M6B_EXT4_FIXTURE_ORACLE_DESIGN.md) 与 ADR-0010 已选择“锁定 Linux e2fsprogs fixture 作者 + 仓库独立解析器”，并将 Gate 1 fixture 工具与 Gate 3 Android `mke2fs + e2fsdroid` 生产构建器分离。D-0043/D-0045/D-0046/D-0052 已完成管理员 H1、恢复准备 H2a、SVM H2b 与 WSL/VMP H2c Apply；D-0054 已完成 B1 重启、WSL runtime、Ubuntu LTS 与受控依赖的统一验收；D-0055 已完成上游 `e2fsprogs 1.47.2` 源码、签名、编译、私有安装与四工具哈希锁定。现在只剩真实 synthetic fixture 尚未建立。R-019/R-020/R-022 继续开放，R-021/R-023 已缓解，R-024 已通过私有路径覆盖缓解。

## 10. 当前下一步

1. H1、H2a、H2b 和 H2c Apply 已通过；保留 `logs/host/20260725-203346/` 的原始迁移路径限制，不改写证据。
2. B1 已由 D-0054 通过；保留其 Windows 证据和用户贴出的 Ubuntu 环境输出，不更改主机虚拟化设置。
3. 上游 `e2fsprogs 1.47.2` 工具链已由 D-0055 通过，保留签名源码、环境、构建参数、二进制 SHA-256 和首次安装路径失败证据。
4. 下一步实现公开 synthetic ext4 的 positive/negative fixture；fixture 通过后才实现只读官方 `system_a` 完整语义 manifest。

在完成以上四步前，UBOX10 保持断电；FT232RL 与电脑、UBOX10 均保持断开。
