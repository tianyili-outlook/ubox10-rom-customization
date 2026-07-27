# M6b.0 ext4 语义 manifest 规范 v1

> 参考规范：当前解析器已经用于官方 `system_a`；下一步不需要重新执行本文门禁。

- 状态：**设计规范；M6b.1 JSON root guard 已实现，真实 ext4 解析器/fixture/重建器尚未实现**
- 日期：2026-07-25
- 适用范围：UBOX10 官方 logical `system_a` 的零内容 root-hierarchy control。
- 前置：D-0037 已确认历史源根错误；D-0038 已确认现有提取/重建路径不能证明完整 ext4 语义；真实 fixture 的作者/oracle 角色见 [M6b.2 设计](M6B_EXT4_FIXTURE_ORACLE_DESIGN.md) 与 ADR-0010。

## 1. 决策

| 项目 | 内容 |
|---|---|
| 决策 | 以直接从 ext4 映像读取的、版本化 JSON manifest 作为语义权威；宿主文件树只可作为内容搬运/staging，不是权限、xattr、链接或根目录身份的权威。 |
| 理由 | Windows/当前提取器不能天然表示 Android ext4 的全部 POSIX/SELinux 语义；从目录名或 `.symlink` 存根反推原始文件系统会丢失信息。 |
| 收益 | 根目录身份、文件类型、链接关系和安全标签可机器比较；重建适配器必须显式证明每一个可表达字段。 |
| 风险 | manifest 可能较大，解析器需处理 ext4 feature/xattr 边界；实现不足时必须失败而非猜测。 |
| 恢复 | 仅写入新的离线报告/fixture；官方 super 不变。任何解析不支持都使该层失败，不启动构建或设备动作。 |

## 2. 基本原则

1. **直接映像优先**：官方 `system_a` 的 raw ext4 字节是事实来源；从它导出的 manifest 才是对照基线。
2. **fail closed**：遇到未知 inode 类型、feature、xattr 格式、ACL、损坏目录项或读取错误，必须输出结构化错误并使比较失败；不得静默跳过或降级为普通文件。
3. **逻辑路径不依赖宿主路径**：manifest 一律使用规范 POSIX 逻辑路径，根为 `/`；Windows 路径、盘符和符号链接解析结果不得写入身份字段。
4. **内容和元数据分离**：普通文件内容用 SHA-256/大小描述；语义字段单独记录，避免“文件哈希相同”被误判为“文件系统相同”。
5. **源根可证明**：未来构建输入必须关联一个 `root_contract_digest`，证明它代表官方 ext4 `/`，并包含根级 `/system`；仅靠目录路径字符串不成立。
6. **没有默认例外**：所有差异默认阻断。即使某字段可能是构建器可变字段，也必须记录、解释并经 ADR/本轮 allowlist 审核，才能改变比较策略。

## 3. 规范化与哈希

- JSON 使用 UTF-8、LF、对象键的字典序、数组按规范路径/名称排序；字段缺失与空值不等价。
- 逻辑路径使用 `/`，不含 `.`、`..`、重复 `/` 或宿主路径分隔符；文件名原始字节若无法 UTF-8 编码，额外以 Base64 保存。
- SHA-256 全部使用大写十六进制。
- 原始二进制 xattr / ACL / symlink target 同时保存 `sha256`、`length` 和 Base64 值；禁止只保存显示文本。
- 内容哈希计算的是逻辑文件字节流；`allocated_extent_digest` 单独描述稀疏洞和物理 extent，不与内容哈希混淆。
- manifest 自身由 `SHA256SUMS.txt` 覆盖；输入镜像、工具源码、执行命令和环境版本必须记录。

## 4. 顶层 JSON 合同

实现可增加不影响语义的命名空间字段，但不得删除下列字段：

```json
{
  "schema": "ubox10.ext4-semantic-manifest/v1",
  "manifest_kind": "direct-image | materialized-tree | rebuilt-image",
  "created_utc": "YYYY-MM-DDTHH:MM:SSZ",
  "source": {
    "official_container_sha256": "...",
    "super_sha256": "...",
    "logical_partition": "system_a",
    "logical_extent_digest": "...",
    "ext4_image_sha256": "...",
    "read_method": "streaming-ext4-parser",
    "tool_sources": [{"path": "...", "sha256": "..."}]
  },
  "filesystem": { "...": "见第 5 节" },
  "root_contract": { "...": "见第 6 节" },
  "entries": [ { "...": "见第 7 节" } ],
  "hardlink_groups": [ { "...": "见第 8 节" } ],
  "comparison_policy": { "...": "见第 9 节" },
  "errors": [],
  "analysis_boundary": "离线文件事实，不证明设备实装或可启动性"
}
```

`direct-image` 是官方基线唯一可接受的 `manifest_kind`。`materialized-tree` 只能在其与基线的所有必需语义字段相同后作为构建 staging 输入。`rebuilt-image` 只能在 Gate 3 之后生成，且永远不自动获得刷写资格。

## 5. 文件系统级字段

`filesystem` 至少包含：

```json
{
  "magic": "EF53",
  "block_size": 4096,
  "inode_size": 256,
  "blocks_count": 0,
  "inodes_count": 0,
  "reserved_blocks_count": 0,
  "uuid": "canonical-lowercase-uuid",
  "volume_label_b64": "",
  "feature_compat": "0x00000000",
  "feature_incompat": "0x00000000",
  "feature_ro_compat": "0x00000000",
  "default_mount_options": "0x00000000",
  "error_behavior": "0x0000",
  "journal": { "present": true, "superblock_digest": "..." },
  "superblock_digest": "..."
}
```

未知 feature bit 必须单独列出并使 parser 返回 `unsupported_feature`，直到有 fixture 和解析支持；不得只把未知位复制到 JSON 后继续放行。

## 6. `root_contract`

该对象避免 D-0037 的“把子目录当根目录”错误：

```json
{
  "logical_root": "/",
  "root_entry_digest": "SHA256 of canonical root entry",
  "root_subtree_digest": "SHA256 of sorted direct children identity records",
  "required_directories": ["/system"],
  "required_child_names": ["system"],
  "observed_direct_child_names": ["..."],
  "source_root_identity": "sha256:...",
  "prohibited_subtree_root_identities": [
    {"logical_path": "/system", "subtree_identity": "sha256:..."}
  ]
}
```

对 UBOX10 当前官方基线，`/system` 是强制项。构建 guard 接收 staging manifest 而非仅接收目录字符串：

- `source_root_identity` 必须等于经批准的官方根身份；
- `/system` 必须存在且为目录；
- 任何与 `prohibited_subtree_root_identities` 相符的输入（特别是官方 `/system` 子树）必须拒绝；
- 宿主 staging 目录的路径可变，但它的 `materialized-tree` manifest 必须能追溯到同一官方 `direct-image` manifest。

## 7. 目录项记录

每个 `entries[]` 对象至少包含：

```json
{
  "path": "/system/bin/init",
  "path_bytes_b64": "L3N5c3RlbS9iaW4vaW5pdA==",
  "type": "regular | directory | symlink | char-device | block-device | fifo | socket",
  "mode_octal": "0755",
  "uid": 0,
  "gid": 0,
  "inode_flags": "0x00000000",
  "link_count": 1,
  "timestamps": {"atime_ns": 0, "ctime_ns": 0, "mtime_ns": 0, "crtime_ns": null},
  "xattrs": [
    {"name_b64": "c2VjdXJpdHkuc2VsaW51eA==", "length": 0, "sha256": "...", "value_b64": "..."}
  ],
  "acl": {
    "access_b64": null,
    "default_b64": null,
    "canonical_access": null,
    "canonical_default": null
  },
  "content": null,
  "symlink": null,
  "device": null,
  "hardlink_group": null,
  "allocated_extent_digest": null,
  "diagnostic_inode_number": 0
}
```

类型特有规则：

| `type` | 额外必需字段 |
|---|---|
| `regular` | `content.logical_size`、`content.sha256`、`allocated_extent_digest`。 |
| `directory` | 规范排序的直接子项名称 digest；目录内容不以普通文件方式哈希。 |
| `symlink` | `symlink.target_b64`、`target_sha256`、`target_length`；绝不解析到宿主目标。 |
| `char-device` / `block-device` | `device.major`、`device.minor`。 |
| `fifo` / `socket` | 类型本身和全部通用元数据；不得降级为普通空文件。 |

`security.selinux` 和 `security.capability` 必须作为普通 xattr 的原始值存在；缺失、格式错误或只保存可读字符串都算失败。

## 8. 硬链接拓扑

绝对 inode 编号和 block 位置可由重建器改变，因此它们不是硬链接身份的比较键。每组硬链接记录为：

```json
{
  "group_id": "sha256 of sorted logical paths and common immutable attributes",
  "paths": ["/path/a", "/path/b"],
  "expected_link_count": 2,
  "source_diagnostic_inode_number": 0
}
```

所有路径只能属于一个 group。若原映像中同一 inode 被多个目录项引用，materialized tree 和 rebuilt image 都必须保留相同的路径集合；复制为两个独立文件是失败。

## 9. 比较器与 allowlist

比较器返回 `PASS`、`FAIL` 或 `REVIEW_REQUIRED`；默认不允许任何差异。

| 差异类别 | 默认结果 | 举例 |
|---|---|---|
| 内容/结构/安全身份 | `FAIL` | 路径、类型、普通文件哈希、symlink target、UID/GID、mode、SELinux/capability/ACL、设备号、硬链接组、根级 `/system`、ext4 feature bit。 |
| 提取完整性 | `FAIL` | 未知 feature、无法读取 xattr、无法编码文件名、目录遍历错误、manifest 错误数组非空。 |
| 构建器诊断字段 | `REVIEW_REQUIRED` | UUID、卷标、timestamp、绝对 inode 编号、block/inode 分配、journal 初始化状态、reserved blocks。 |
| 证据完整性 | `FAIL` | 输入哈希不匹配、工具源码未锁定、缺少命令日志、候选/历史 `work/` 被误作官方输入。 |

只有一个内容为 JSON 的、随 run-id 保存的 `reviewed-allowlist.json` 才能把特定的 `REVIEW_REQUIRED` 项转为已审阅；每项必须包括：

```json
{
  "json_pointer": "/filesystem/uuid",
  "expected": "...",
  "actual": "...",
  "reason": "已由对应 fstab/启动链证据证明不参与此控制的运行时身份",
  "evidence": ["relative/path/to/report"],
  "decision_ref": "ADR-xxxx",
  "reviewed_by": "",
  "reviewed_utc": ""
}
```

空白、通配符、仅以“构建器会变”为理由的 allowlist 均无效。首次 Gate 1/2 不使用 allowlist；其目标是验证解析和 materialization，而非解释变化。

## 10. staging 与重建适配器的要求

1. staging 由基线 manifest 驱动，不能以当前 `work/system_extracted/` 为来源。
2. 对宿主文件系统无法原生表达的语义，适配器必须生成可审计的 sidecar 映射，并证明 Android 构建器的实际输入如何消耗它；例如 fs_config、file_contexts、显式 symlink/hardlink 指令等。
3. 若 `make_ext4fs` 或其他构建器不能表达某个基线字段，适配器必须失败。禁止用 `.symlink` 文本、默认 uid/gid/mode 或空 xattr 代替。
4. 适配器生成的 `materialized-tree` manifest 必须与官方 `direct-image` manifest 进行完整比较；两者未通过前，构建器不得启动。
5. 构建器输出的 `rebuilt-image` manifest 必须再与官方基线比较；它通过只证明该 ext4 control 的离线语义，不证明 AVB 或设备可启动。

## 11. 实现与测试顺序

1. 固化本规范，增加 JSON schema validation 的单元测试。
2. 用公开小型 fixture 实现 direct-image manifest；覆盖目录、普通文件、真实 symlink、硬链接、非默认 UID/GID/mode、SELinux xattr、capability/ACL，以及未知 feature 的失败路径。
3. 实现 root-hierarchy guard：正确根接受、错误 `/system` 子树拒绝。
4. 实现 materialized-tree manifest 和基线比较。
5. 仅在以上全部通过后，才可提议隔离的 zero-content ext4 build adapter。

每一步都必须先写失败测试，且不需要官方大镜像或设备接入。任何一步的 `FAIL` / `REVIEW_REQUIRED` 都终止后续步骤。

## 12. Gate 0 设计审阅记录

- 审阅日期：2026-07-25
- 审阅范围：字段完整性、根目录身份、宿主 staging 权威边界、默认差异策略、AVB/super 隔离、失败与恢复路径。
- 结论：**设计通过，执行未放行。** 本规范已明确 D-0037 的根目录错误不能通过路径字符串修补；也已明确 D-0038 的 `.symlink` 存根和缺失 metadata 映射不能作为构建输入。没有自动 allowlist，未知字段 fail closed。
- 未决项：选择能读取 ext4 xattr/ACL/extent/硬链接的实现；确定如何让构建器实际消耗 manifest 驱动的 UID/GID/mode/SELinux/链接映射；建立公开 fixture 的可复现生成方式。这些都是后续实现问题，不得以假设填补。
- 最安全的下一项实验：先只实现 root-hierarchy guard 对**手工最小 JSON manifest fixture**的正反例测试。它只读取/比较小型 JSON：正确的逻辑根含 `/system` 必须接受；把 `/system` 子树标作根必须拒绝。该实验不解析官方镜像、不调用 `make_ext4fs`、不创建 ext4、super 或 PhoenixCard，也不接触设备。通过后才评估真正 ext4 fixture 的生成/解析能力。

## 13. M6b.1 执行记录

- 日期：2026-07-25
- 结果：最安全的 JSON guard 实验已完成（D-0039）。`src/ubox10_rom/ext4_manifest.py` 只验证根合同；正例通过，`/system` 子树伪作根的反例被拒绝，3 项 `unittest` 全部通过。
- 边界：此实现不是 ext4 解析器、不是 staging adapter、不是重建器；它没有读取官方或候选映像、没有调用任何镜像工具，也不会访问设备。
- 后续：Gate 1 仍未完成。下一项须先评审真正 ext4 fixture 的生成/解析方案，再把同一逻辑规则接到 direct-image manifest；不得直接把 guard 接入历史 `repack-rom.py`。
