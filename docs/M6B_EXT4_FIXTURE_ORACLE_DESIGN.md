# M6b.2：ext4 fixture oracle 设计与工具角色隔离

> 历史设计资料：fixture 和独立解析器已经通过，当前状态见 `README.md`。

- 状态：**路线和工具链已通过；M6b.3a positive fixture 批量手册已准备，fixture 尚未执行**
- 日期：2026-07-25
- 风险等级：本设计与源码核验为低风险；配置 WSL/Linux 构建环境为中等主机变更；生成隔离 fixture 为低风险离线操作；设备写入仍为严重风险且不属于本阶段。
- 前置：[D-0038](DISCOVERIES.md#d-0038--当前-ext4-提取重建工具链无法证明保留完整文件系统语义)、[D-0040](DISCOVERIES.md#d-0040--当前-windows-环境没有可独立生成并校验完整-ext4-语义的已锁定工具链)、[ADR-0009](DECISIONS.md#adr-0009先设计-m6b0-root-hierarchy-control不直接修补历史重建脚本)。

## 1. 本阶段要解决的问题

M6b.1 已证明 root-hierarchy contract 可以在纯 JSON 层拒绝“把 `/system` 子树冒充 ext4 根”。Gate 1 的下一步不是读取官方 `system_a`，而是建立一个可公开、可重复生成的小型 ext4 fixture，用它验证未来解析器能够读取：

- ext4 根与根级 `/system`；
- 普通文件、目录与真实符号链接；
- 硬链接拓扑；
- 非默认 UID/GID/mode；
- `security.selinux`、`security.capability` 和 POSIX ACL xattr；
- 文件系统 label、UUID、block size 与 feature flags；
- 未知 feature、损坏元数据或不支持的语义会 fail closed。

fixture 的预期事实不能由待测解析器自己生成，否则会形成 R-019 的循环验证。

## 2. 官方实现语义核验

### 2.1 `mke2fs -d root-directory`

上游/AOSP `create_inode.c` 的目录输入路径以宿主机 `lstat` 结果为数据源：

- 以 `st_dev + st_ino` 识别并重建硬链接；
- 读取符号链接目标并调用 ext2fs symlink 原语；
- 将宿主的 UID、GID、mode 与时间写入目标 inode；
- 只有构建时存在 `HAVE_LLISTXATTR`，才通过 `llistxattr/lgetxattr` 复制宿主 xattr；否则该函数直接返回成功而不复制 xattr。

这意味着 `-d` 不是一个独立于宿主文件系统的语义描述格式。Windows/NTFS staging 不能被假定能表达 Android 所需的 UID/GID、POSIX mode、硬链接身份、SELinux xattr 或 ACL。本机 `mke2fs.exe` 的 usage 存在 `-d` 选项，不等于这些语义已经存在或可验证。

来源：[AOSP `misc/create_inode.c`](https://android.googlesource.com/platform/external/e2fsprogs/+/c7b68bcc3c51f4c3b95f7e140e0d24826088bfd2/misc/create_inode.c)。

### 2.2 `mke2fs -d tarball`

上游手册明确说明 tarball 输入仅在编译时启用 libarchive 且运行时能加载 libarchive 时可用；`-` 才表示从标准输入读取归档。该能力从 e2fsprogs 1.47.1 开始加入，不能从命令行 usage 推断实际依赖、归档方言或 xattr 覆盖范围。

归档导入实现会读取归档中的文件类型、stat、符号链接/硬链接和部分 xattr，但它不是 Android `fs_config + file_contexts` 的替代品。上游加入该功能时的回归用例明确覆盖 `security.capability`；没有证据允许把它扩张为“任意 SELinux/ACL 语义均完整保真”。因此 tarball 可以成为未来的单项兼容性测试输入，但不能成为本项目完整语义 fixture 的唯一作者。

来源：[上游 `mke2fs(8)`](https://kernel.googlesource.com/pub/scm/fs/ext2/e2fsprogs/+/22f5c951fa3b7dd44b9eb0bac45c58be5a3887f8/misc/mke2fs.8.in)、[e2fsprogs 1.47.2 发布说明](https://e2fsprogs.sourceforge.net/e2fsprogs-release.html)、[上游 tarball 支持补丁与测试](https://marc.info/?l=linux-ext4&m=169212219103951&w=2)。

### 2.3 Android 正式映像工具链

AOSP 的 `mkuserimg_mke2fs.py` 明确把制作分成两步：

1. `mke2fs` 建立空 ext4；
2. `e2fsdroid -f <src_dir> -a <mountpoint>` 填充文件系统，并按需传入 `-C fs_config`、`-S file_contexts` 和固定时间。

`e2fsdroid` 的 Android 配置阶段会：

- 由 `fs_config` 设置 UID、GID、mode 与 Linux capability；
- 由 SELinux `file_contexts` 设置 `security.selinux`；
- 对 inode 遍历后直接写入这些元数据。

因此未来 Gate 3 的 Android system 重建适配器应以锁定的 AOSP `mke2fs + e2fsdroid` 为候选，而不是继续把历史 `make_ext4fs.exe` 或通用 `mke2fs -d` 当作等价实现。Gate 1 的 synthetic fixture 作者与 Gate 3 的 Android 生产构建器是两个不同角色，必须分开评审。

来源：[AOSP `mkuserimg_mke2fs.py`](https://android.googlesource.com/platform/system/extras/+/master/ext4_utils/mkuserimg_mke2fs.py)、[AOSP `e2fsdroid.c`](https://android.googlesource.com/platform/external/e2fsprogs/+/886fdbbf29390e4a7298da65e46d976a27b4460c/contrib/android/e2fsdroid.c)、[AOSP `perms.c`](https://android.googlesource.com/platform/external/e2fsprogs/+/34f4f33/contrib/android/perms.c)。

## 3. 路线比较

| 路线 | fixture 作者 | 独立校验 | 收益 | 主要风险 | 结论 |
|---|---|---|---|---|---|
| A. 锁定 Linux e2fsprogs | 从官方签名源码构建的 `mke2fs/debugfs`；用离线命令直接设置 inode 与 xattr | `e2fsck -fn`、`dumpe2fs/debugfs` 证据，加仓库自研只读解析器 | 工具成熟；无需挂载或 root；能精确构造 synthetic 语义；源码/命令/哈希可锁定 | 需要经批准配置 Linux 环境；e2fsprogs 工具间仍属同一实现家族 | **选定** |
| B. 仓库自研 ext4 作者 + 第二解析实现 | 新写完整 ext4 生成器 | 另一套解析器或外部 e2fsprogs | 完全可控 | 需正确实现分配、目录、extent、xattr、校验和与 feature；测试成本和伪正确风险极高 | 当前拒绝；只在 A 无法建立时重新评审 |
| C. 当前 Windows `mke2fs.exe -d` | 未锁定的本机 Android 二进制与 NTFS staging | 当前没有独立校验器 | 无需改变主机 | 来源链不完整；宿主语义不足；无 `debugfs/e2fsck`；容易循环验证 | 拒绝 |
| D. 仅由远程 CI 生成 | CI 中临时 Linux 工具 | 下载后由本地解析器验证 | 不修改本机 Windows 功能 | runner/镜像漂移；外部服务和网络成为唯一依赖；本地无法独立复现 | 只可作为第二复现点，不作为唯一 oracle |

## 4. 已接受的架构决策

本项目选择路线 A，并由 [ADR-0010](DECISIONS.md#adr-0010m6b-fixture-使用锁定-linux-e2fsprogs且与-android-生产构建器分离) 固化：

1. Gate 1 fixture 作者使用**从官方签名源码构建并锁定哈希**的 Linux e2fsprogs。
2. 初始版本对齐为上游 e2fsprogs `1.47.2`。官方 `tar.xz` 的签名校验清单记录 SHA-256：
   `08242E64CA0E8194D9C1CAAD49762B19209A06318199B63CE74AE4EF2D74E63C`。
3. 下载前必须获得用户对网络访问和 Linux 环境配置的明确授权；下载后还必须验证签名清单与归档 SHA-256，记录编译器、configure 参数和每个产物哈希。
4. fixture 生成不挂载 loop device、不访问 `/dev`、不要求 root；只操作新的 `out/m6b-fixture/<run-id>/` 文件。
5. `mke2fs` 只负责建立指定参数的空 ext4；`debugfs` 负责按 fixture spec 注入目录项、inode 字段、链接与原始 xattr。
6. `e2fsck -fn` 只做非修改结构校验；`dumpe2fs`/`debugfs` 输出作为作者侧证据。仓库自研解析器是另一实现，必须从映像字节独立生成 observed manifest。
7. expected manifest 由版本控制下的 fixture spec 定义，不从 observed manifest 反向生成。
8. Gate 1 成功不放行 Gate 3。正式 Android system 映像仍需另行锁定 AOSP `mke2fs + e2fsdroid`、`fs_config`、`file_contexts` 和全部输入来源。

官方上游归档与签名清单入口：[kernel.org e2fsprogs v1.47.2](https://www.kernel.org/pub/linux/kernel/people/tytso/e2fsprogs/v1.47.2/)。

## 5. 最小 positive fixture 合同

初始 fixture 建议为 16 MiB raw ext4，全部内容为项目自创测试数据，不含官方固件、APK 或厂商代码。执行前还需把确切 feature 集和二进制 ACL 值冻结到 fixture spec。

| 路径 | 类型/语义 | 目的 |
|---|---|---|
| `/` | directory；固定 UUID、label、block size/features | 文件系统级字段 |
| `/system` | directory | 正确 ext4 根身份 |
| `/system/bin`、`/system/etc` | directory | 最小层级 |
| `/system/bin/init` | regular；固定短内容与 SHA-256 | root guard 正例 |
| `/system/bin/owned-tool` | regular；非默认 UID/GID/mode | inode 身份与权限 |
| `/system/bin/owned-tool-hardlink` | 与 `owned-tool` 同 inode | 硬链接拓扑/link count |
| `/system/bin/tool-link` | symlink，目标 `/system/bin/owned-tool` | 原始 link target |
| `/system/etc/selinux-test` | regular；原始 `security.selinux` xattr | SELinux 标签读取 |
| `/system/bin/cap-test` | regular；固定 20-byte `security.capability` | capability 二进制值 |
| `/system/etc/acl-test` | regular；固定有效 POSIX ACL xattr | ACL 解码与原始字节 |

禁止以宿主目录当前的 owner/mode/xattr 作为 fixture 真值；所有字段由 `fixture-spec.json` 和离线注入命令明确给出。

## 6. 必须存在的 negative fixtures

1. **结构有效但根错误**：第二个 ext4 以 `bin/init` 等内容直接位于根目录，故缺少根级 `/system`。文件系统结构本身可通过 `e2fsck -fn`，但 root contract 必须拒绝它。
2. **未知 incompat feature**：从独立小型基线复制后，只修改预先审核的 superblock feature 位；解析器必须在遍历目录前 fail closed。该样本的精确 bit、superblock checksum 处理和独立十六进制断言需在实现前冻结，不能临时手改。
3. **损坏目录项或 inode 引用**：只在 disposable 副本中用确定偏移的 mutator 产生；`e2fsck -fn` 与仓库解析器均应失败，但错误类别可以不同。
4. **语义缺失**：移除一个必需 xattr 或把 symlink 变成普通文本文件；比较器必须报告精确字段缺失，不能把空值当成等价。

所有 mutator 都只接受 fixture SHA-256 白名单，只能输出到新的 run-id 目录，并在执行前验证目标不是官方镜像、`work/` 候选或仓库根目录。

## 7. 生成与验证流水线

```text
官方签名源码 + 锁定 Linux 环境
             │
             ├─ build-toolchain → toolchain-manifest.json
             │
fixture-spec.json
             │
             ├─ mke2fs + debugfs → synthetic.ext4
             │                    ├─ e2fsck -fn
             │                    ├─ dumpe2fs/debugfs evidence
             │                    └─ SHA256SUMS.txt
             │
             └─ repo parser → observed-manifest.json
                               │
expected-manifest.json ────────┴─ semantic comparator → PASS/FAIL
```

放行必须同时满足：

- 工具源码签名/哈希、构建产物哈希和命令记录完整；
- `e2fsck -fn` 返回 clean，不执行修复；
- 作者侧证据与 `fixture-spec.json` 一致；
- 仓库解析器不调用 e2fsprogs 的解析输出，不读取 expected manifest 以决定如何解析；
- positive fixture 全字段相等；
- 每个 negative fixture 在预期门禁失败；
- 再运行一次得到相同 fixture 内容哈希，或把不可重复字段精确列出并消除后重试。

## 8. 主机环境授权门

D-0040 盘点时 Windows 没有可调用的 WSL 发行版、Docker/Podman 或所需 Linux e2fsprogs 工具；该环境缺口已由 D-0054/D-0055 解除。以下动作仍未被本设计自动授权：

- 启用 Windows 可选功能、虚拟化或 WSL；
- 安装 Linux 发行版、系统包或 Python 包；
- 下载 e2fsprogs、编译器或任何预编译二进制；
- 重启 Windows；
- 生成 ext4 fixture。

推荐的本地执行环境是经用户批准的 WSL2 Linux 发行版，因为它能保留本地可复现性并避免将远程 CI 作为唯一事实源。若用户已有独立 Linux 主机/虚拟机，也可以把它作为等价候选，但必须记录 OS、内核、编译器、源码签名、工具哈希与命令。

2026-07-25 已以 `scripts/inspect-wsl-oracle-host.ps1` 完成第一层非管理员只读预检（D-0042，`logs/host/20260725-030723/`）：

- `wsl.exe --version`、`--status`、`--list --verbose` 均报告 WSL 未安装；
- 查询 `Microsoft-Windows-Subsystem-Linux` 和 `VirtualMachinePlatform` 状态需要管理员权限，当前结果为 unknown；
- CPU 虚拟化/Hypervisor CIM 字段因 access denied 也是 unknown；
- 注册表产品名、DisplayVersion、build 原样记录，不以单字段推断 Windows 市场版本；
- 安全清单确认没有联网目录查询、安装/更新、功能变更、重启、设备或固件访问。

管理员 H1 已由 `logs/host/20260725-121016/` 完成（D-0043）：

- `Microsoft-Windows-Subsystem-Linux` 和 `VirtualMachinePlatform` 均为 Disabled；
- Ryzen 5 5600X 的 VM monitor extensions 与 SLAT 为 true；
- `VirtualizationFirmwareEnabled=false`、`HypervisorPresent=false`；
- H1 未安装、未联网、未改功能或固件、未重启。

这意味着 WSL2 路线技术上仍可行，但不能直接调用一键安装。ADR-0011 将 H2 进一步拆分：

1. **H2a — 恢复准备只读门**：以 schema v2 记录主板/BIOS、系统盘 protection/encryption/protector 类型；不读取恢复密钥内容。若保护开启，用户在项目外确认密钥可获得。
2. **H2b — SVM 单变量门**：只把 BIOS `SVM Mode` 从 Disabled 改为 Enabled；不更新 BIOS、不加载默认值、不改 Windows 功能。重启后重跑只读预检，必须观察 `VirtualizationFirmwareEnabled=true`。
3. **H2c — Windows 功能门**：只启用 WSL 与 Virtual Machine Platform 两个已确认 Disabled 的功能；不安装发行版。重启后验证 feature state 和 WSL runtime。
4. **H2d — 发行版/网络门**：才查询在线发行版、锁定精确名称/来源/版本/磁盘占用并授权安装。
5. **H2e — toolchain 门**：验证签名源码、编译依赖和二进制哈希，只产生 toolchain manifest；执行合同见 [R2 批量手册](M6B_TOOLCHAIN_MANIFEST_RUNBOOK.md)。

H2a 已由 `logs/host/20260725-123940/` 完成（D-0045）：系统盘 FullyDecrypted、Protection Off、EncryptionMethod None、0%、无 protector。H2b 已由 `logs/host/20260725-203346/` 完成（D-0046）：firmware virtualization 从 false 变为 true。D-0052 又确认 H2c 只将 WSL/VMP 从 Disabled 启用到 Enabled；D-0054 已确认 B1 重启后无 pending reboot、Ubuntu-24.04 在 WSL 2 运行且受控依赖可用。发行版运行环境已就绪；上游源码/fixture 门禁仍不属于 B1。

Microsoft 官方说明中，`wsl --install` 可能启用所需 Windows 功能、安装发行版并要求重启；`wsl --list --online` 会查询可用发行版。因此两者都不属于 H1。[WSL 安装说明](https://learn.microsoft.com/windows/wsl/install)、[WSL 基本命令](https://learn.microsoft.com/windows/wsl/basic-commands)。

本机主板只读识别为 ASUS PRIME B550M-A WIFI II、BIOS 3607。ASUS 对 AMD 主板给出的路径是 `Advanced → CPU Configuration → SVM Mode → Enabled`；H2b 已按该单变量路线完成并由管理员证据验收。[ASUS SVM 官方指引](https://www.asus.com/support/faq/1045141/)。

## 9. 风险与恢复

| 风险 | 防护 | 恢复 |
|---|---|---|
| 系统盘保护开启但恢复密钥不可得，BIOS 变更后出现恢复提示 | schema v2 只读 protection/protector 类型；用户在项目外确认恢复密钥可获得，绝不记录密钥内容 | 不执行 H2b；若已进入恢复界面，使用用户自有恢复流程，不向项目披露密钥 |
| SVM 单变量导致宿主异常 | 只改 SVM，记录原值；不更新 BIOS、不加载 defaults、不改 Windows 功能 | 回到同一路径恢复原 SVM 值 |
| WSL/虚拟化安装改变主机或要求重启 | H1 与 H2 分权；安装前单独说明精确命令、Windows 功能和重启可能性并再次授权 | 不运行 fixture；按 Windows 官方机制移除本轮新增发行版/功能，仓库和设备不变 |
| 同源工具循环验证 | expected spec、作者侧 e2fsprogs 和仓库解析器分权；失败 fixture 必须覆盖 | 删除本轮 disposable 输出，修复 parser/spec 后重跑 |
| 把 fixture 作者误作 Android 生产构建器 | Gate 1 与 Gate 3 使用不同工具角色和 ADR | 停止在 Gate 1；不生成官方 system 候选 |
| mutator 命中错误文件 | 输入 SHA 白名单、run-id 输出、禁止官方/`work` 路径 | 只删除刚生成的 negative 副本；官方输入未打开写权限 |
| fixture 语义不完整却被放行 | 完整 expected manifest、fail-closed、正反样本、两次复现 | 标记 fixture 失败，不读取官方 `system_a` |

## 10. 下一步

1. H2b 与 H2c Apply 已通过；不再进入 BIOS，也不改写既有证据。
2. D-0054 已通过 B1：管理员只读证据验证 WSL/VMP、Hypervisor、系统盘和兼容性状态，Ubuntu 环境清单已归档到发现记录。
3. R2 toolchain manifest 已由 D-0055 通过；保留首次绝对 service 路径失败和私有路径重试证据，不使用 sudo 重装。
4. M6b.3a 先按 [positive fixture 批量手册](M6B_POSITIVE_FIXTURE_RUNBOOK.md) 生成两次项目自创正样本并验证可重复性。
5. 正样本验收后实现独立 observed manifest、expected manifest 与 negative mutator。
6. Gate 1 全部通过后，才开始实现对官方 `system_a` 的只读完整语义解析。

在新的明确授权前，设备保持断电；FT232RL 不连接；`metadata`、boot、vendor_boot、super、vbmeta 与 PhoenixCard 均不写入。
