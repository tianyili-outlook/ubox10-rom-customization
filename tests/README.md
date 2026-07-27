# 测试策略

`tests/fixtures/` 只存放可公开分发的小型样本；官方固件、分区和 APK 不进入 Git。

当前纯 Python 单元测试可从仓库根运行：

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

该命令目前只执行 M6b.1 的小型 JSON root-hierarchy fixture；不会打开官方映像、调用镜像工具或访问设备。

## 测试层次

1. **单元测试**：IMAGEWTY 目录/校验和、LP metadata、AVB 描述符、CPIO、ext4 元数据导出与差分。
2. **属性测试**：对容器条目、稀疏镜像与符号链接生成随机小样本，验证提取 → 重建 → 比较不会静默丢失语义。
3. **Golden 测试**：对从官方镜像生成的受版本控制 manifest/哈希报告进行稳定比对。
4. **集成测试**：零内容改动 PhoenixCard → super → ext4 round-trip；任何一层差异必须可机器读取。
5. **硬件测试**：仅在明确授权的 M6c/M7 阶段执行；不作为本地 CI 的替代品。

## 主机诊断脚本静态门禁

- 所有 PowerShell 脚本必须先通过 `System.Management.Automation.Language.Parser.ParseFile` 与 `git diff --check`。
- `capture-uart-readonly.ps1` 必须保留显式 `-ReceiveOnlyWiringConfirmed` 门禁、`DtrEnable=false`、`RtsEnable=false`，且源码不得调用 `SerialPort.Write*`。
- `capture-uart-readonly.ps1` 的默认 `OutputRoot` 必须从 `$PSScriptRoot` 推导到仓库 `logs/device`，从 `System32` 等其他目录调用也不能改变证据根目录。
- UART 实机测试不进入 CI；必须以目标 TX→适配器 RXD 的物理单向接线、独立设备电源和日志 SHA-256 作为通过证据。
- `audit-metadata-init.py` 必须通过 `python -m py_compile`；输出目录必须是仓库内尚不存在的新目录，工具不得调用串口、Fastboot、PhoenixCard 或修改任一输入镜像。Golden 审计报告必须包含输入 SHA-256、GPT/fstab 事实、受限启动文件差分和输出清单复核结果。
- `audit-imagewty-payload-provenance.py` 必须通过 `python -m py_compile`；输出目录必须是仓库内尚不存在的新目录，工具不得提取或修改容器。Golden 审计报告必须包含 boot/vendor_boot/super 的 IMAGEWTY 条目范围、官方/候选容器与工作文件 SHA-256、`V*` 伴生校验和“本地来源不等同设备实装”的解释边界。
- 禁止直接对稀疏官方/工作 super 输入调用现有 `lpunpack.py`，包括 `--info`：其实现会在输入同级写 `<input>.unsparse.img`。任何替代方案必须把所有派生文件写到全新的、明确命名的分析目录，并在开始前检查空间和在结束后复核输入 SHA-256。
- `audit-logical-system-init.py` 必须通过 `python -m py_compile`，并以 sparse/LP/ext4 的流式读取验证官方和候选 `system_a`；不得产生 partition 或 `.unsparse.img`。Golden 报告必须包含 LP SHA-256 校验状态、ext4 根与 `/system` 目录观察、官方路径与根相对路径的文件 SHA-256、以及“候选结构缺陷不等同设备实装”的边界。
- `audit-rebuild-system-root.py` 必须通过 `python -m py_compile`，并且只能以 AST 读取 `purify-rom.py` / `repack-rom.py`；不得 import 或执行它们，不得创建镜像、启动外部构建器、访问串口、Fastboot 或 PhoenixCard。Golden 报告必须包含两个脚本的 SHA-256、源目录赋值和 `make_ext4fs` 调用的行上下文、逻辑 system 审计报告哈希，以及 `confirmed_root_flattening_chain`。
- `inspect-wsl-oracle-host.ps1` 必须通过 PowerShell AST 解析；schema v2 默认只允许 CurrentVersion/BIOS 注册表、可选功能/CIM、系统盘 BitLocker 非秘密状态和 `wsl --version/status/list --verbose` 只读查询。报告安全字段必须断言未查询在线目录、未改变 Windows 功能、未调用 WSL install/update、未重启、未访问设备/固件、未读取 recovery key material；查询错误必须保留为 unknown，不能转换为 disabled/unsupported。protector 类型不能替代用户对恢复密钥可用性的外部确认。
- `inspect-wsl-h2c-compatibility.ps1` 必须通过 PowerShell AST 解析；只允许本地注册表/CIM/DISM/BitLocker/服务盘点，禁止 feature change、服务状态变更、安装/卸载、联网、WSL install/update 和重启。空安装项必须序列化为 `[]` 而不是 `{}`；服务状态必须为字符串；optional feature 必须显式区分 `Present`、当前 SKU 未提供的 `NotPresent` 与查询失败的 `Unknown`；待重启信号和所有安全字段必须机器可读。
- 主机证据清单必须使用相对 basename；验证器以 `SHA256SUMS.txt` 所在目录解析文件。旧的绝对路径证据包不得为消除路径差异而改写。
- `apply-wsl-h2c-features.ps1` 默认必须处于 Inspect 模式；Apply 必须同时要求管理员、明确确认开关、通过 SHA 校验的 H2c 预检目录、实时 Present/Disabled 的 WSL/VMP 和无 pending reboot。静态命令范围除固定的 `Enable-WindowsOptionalFeature -Online -NoRestart` 外，不得包含 WSL/DISM、网络、重启、服务/注册表控制或软件安装/卸载。Inspect 回归必须证明所有 feature-change 标志为 false。
- M6b.0 的后续实现必须先在公开小型 ext4 fixture 上覆盖“根含 `system` 子目录”与“错误传入该子目录”两种测试；任何 root-hierarchy guard 需拒绝后者。只有语义 manifest 能同时比较路径、类型、内容/符号链接、UID/GID、mode、SELinux xattr、capability、硬链接与 ext4 feature 后，才可尝试隔离的零内容重建。
- M6b.0 manifest 实现必须符合 [规范 v1](../docs/M6B_EXT4_SEMANTIC_MANIFEST_SPEC.md)：未知 feature/xattr/inode 类型、读取错误或未审阅差异均须失败或 `REVIEW_REQUIRED`，不得静默忽略。首次 fixture 与官方 direct-image/materialized-tree 比较不允许任何 allowlist。
- 真实 fixture 必须符合 [M6b.2 oracle 设计](../docs/M6B_EXT4_FIXTURE_ORACLE_DESIGN.md)：expected manifest 来自版本控制的 fixture spec；锁定 Linux e2fsprogs 只负责 synthetic 作者/作者侧检查，仓库解析器不得消费 `debugfs/dumpe2fs` 输出作为解析结果。positive 和每个 negative fixture 必须分别断言通过/失败。
- Gate 1 fixture 通过不放行 Android 生产构建。Gate 3 必须另行验证 AOSP `mke2fs + e2fsdroid + fs_config + file_contexts`；不得用通用 `mke2fs -d` 或 fixture `debugfs` 命令替代。

新工具或重建路径必须先有失败测试，再修实现；不得用“能启动工具”或“能生成镜像”代替测试通过。
