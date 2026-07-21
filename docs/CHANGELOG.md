# 变更日志

遵循 Keep a Changelog 风格；所有日期使用 ISO 8601。

> 历史版本条目记录当时执行过的构建或实验；如与本节的证据等级、风险结论冲突，以最新的 `Unreleased`、`DISCOVERIES.md` 和 `M6_DEBUG_LOG.md` 为准。

## [Unreleased] - 2026-07-22

### Added

- **M6a 无修改启动链取证门禁**：新增 USB 主机侧身份采集、被动 UART 冷启动日志和启动链假设表三项前置条件。
- **只读 USB 证据采集器**：新增 `scripts/collect-usb-evidence.ps1`，默认仅归档 Windows PnP 信息和本地 Fastboot 版本；协议探测须显式传入参数。
- **分级验证路线**：新增容器、super、ext4 三层零内容改动 round-trip 的放行规则；诊断构建与发布候选隔离。
- **证据等级**：统一使用“已观察 / 离线已验证 / 协议已验证 / 实机已验证”，禁止以离线结构校验代替实机结论。
- **Fastboot 描述符与 PnP 证据归档**：记录 `logs/device/20260722-001337/` 的原始 JSON、Platform Tools 版本和 SHA-256；`FF/42/03` 已确认匹配 AOSP Fastboot 接口条件。
- **受控主机 GUID 试验**：新增 `docs/U1_FASTBOOT_HOST_BINDING_TRIAL.md` 与 `scripts/test-fastboot-interface-guid.ps1`。脚本默认只读；Apply/Rollback 需要管理员权限、显式确认、精确实例匹配和 JSON 备份，不调用 Fastboot、不安装/卸载/重绑驱动。

### Changed

- **修正 USB 结论**：Windows 已观察到 `USB\VID_1F3A&PID_1010`（`sunxi`）；`fastboot devices` 与 `fastboot getvar all` 均持续等待设备，标准 Fastboot 握手尚未建立。此前“Fastboot 已可用”的表述已撤销。
- **冻结实验 #11.1**：该镜像仅完成构建与离线校验，**未执行物理刷写**。在取得无修改启动链证据前，不再刷入新的 boot、vendor_boot、vbmeta 或 Recovery 调试镜像。
- **降级离线结论**：AVB 重签、super 重构、启动器替换和 APK 裁剪仅具离线证据；候选系统尚未启动，不能宣称运行时成功。
- **发现 ext4 重建语义缺口**：现有提取流程将符号链接保存在 `.symlink` 文本文件，重建流程也未证明恢复所有权、mode、SELinux xattr、capability 和硬链接；该路径暂不得用于运行时放行。
- **禁用未经审查的 USB 驱动方案**：仓库中手工注入硬件 ID 的 Google USB INF 不作为可安装驱动包；修改后原 Catalog 不再覆盖整个包。不得关闭 Windows 驱动签名强制，也不得直接使用 Zadig 绑定。
- **收敛 Fastboot 阻塞归因**：当前 libwdi `oem79.inf` 的 WinUSB 绑定未注册 Platform Tools 所需 Android interface GUID；“接口身份已确认”与“命令事务未验证”现被明确分开。该归因仍待单变量试验验证。
- **U1 授权执行状态**：用户已授权，但自动化环境不具 Windows 管理员令牌；脚本在写入前退出，未修改注册表、驱动或设备。后续只能在提升权限的本地 PowerShell 执行，禁止绕过 UAC。
- **U1 主机枚举验证通过**：提升权限执行已在唯一实例追加目标 GUID，备份/写后验证记录于 `logs/device/20260722-004314/`；物理拔插后 `fastboot devices` 显示 `992304568773    fastboot`。Fastboot 命令事务仍待 `getvar version` 验证。
- **U2 采集器兼容性修正**：保留 `logs/device/20260722-004615/` 的未启动子进程证据；将 `collect-usb-evidence.ps1` 从 `Start-Process` 重定向切换到 .NET 进程 API，规避 Windows 同时存在 `PATH` / `Path` 时的重复键异常。该失败未发送设备命令。
- **标准 Fastboot 协议验证通过**：`logs/device/20260722-004720/` 归档 `fastboot devices` 与 `getvar version → version: 0.5`；后续仅可逐项读取 M6a 白名单变量，写入类命令继续禁止。
- **白名单变量采集自动化**：新增 `scripts/probe-fastboot-readonly-vars.ps1`，仅接受 M6a 明确列出的变量，为每项独立记录 stdout/stderr、退出码与 SHA-256，拒绝其他变量。
- **Fastboot 证据上限已确定**：`logs/device/20260722-004937/` 显示 `product=sunxi`、`secure=yes`，但 userspace 和所有 A/B 槽位变量均不支持。项目停止扩展 Fastboot 探测，M6a 转入 UART 被动冷启动日志。

## [0.7.4] - 2026-07-21

### Added
- **M6 Recovery ADB 联动编译与异步 UDC 绑定 (实验 #11 & #11.1)**：
  - **同步重构 vendor_boot（候选假设）**：为验证同名 rc 优先级而生成过候选代码；实际 ramdisk 拼装/导入顺序未得到启动日志确认。
  - **异步 FFS 触发绑定（候选假设）**：将 UDC 写入逻辑移至 `on property:sys.usb.ffs.ready=1`，尚未实机验证。
  - **多 UDC 名称尝试（候选假设）**：`sunxi-udc`、`musb-hdrc.0` 等名称未获设备侧确认，不作为通用方案。
  - **主 init.rc / adbd 改造（隔离诊断代码）**：不属于发布候选，实验 #11.1 已暂停且未刷入。

## [0.7.3] - 2026-07-20

### Added
- **M6 Recovery ADB 跃变触发注入 (实验 #9)**：
  - 在 `init.recovery.sun50iw9p1.rc` 候选脚本中新增 `none -> adb` 跃变。该方法没有建立 ADB，关于属性触发器的因果解释现已降级为待验证假设。

### Changed
- **LZ4 封包格式修复验证 (实验 #8)**：
  - 高压缩和“去除尾部 0 字节终止符”的候选参数曾使设备不再快速重启；这只是部分兼容性证据，不证明完整 boot 镜像 100% 兼容。
  - 重新启用了 `prop.default` 中被暂时注释的调试与安全属性（`ro.debuggable=1`、`ro.secure=0`、`ro.adb.secure=0` 等）。

## [0.7.2] - 2026-07-20

### Added
- **M6 Recovery ADB 编译管线开发**：
  - 编写了 [enable-recovery-adb.py](../scripts/enable-recovery-adb.py)，实现了对 `boot.fex` 的解包、CPIO 归档解析、Legacy LZ4 块重压、`mkbootimg` 重构以及 `avbtool` hash footer 签名的全自动重包装管线。

### Changed
- **U-Boot 引导死锁排查与对照组集成**：
  - 排查并撤销了主 vbmeta 镜像生成指令中的 `--flags 2` 参数，以防 U-Boot 引导程序强制锁死启动。
  - 创建了对照组（实验 #7）测试机制，暂时屏蔽 ramdisk 内部 `prop.default` 属性修改，使用完全相同的打包格式输出原样还原版 `boot.img`，以控制变量法锁定导致 Bootloop 重启的临界位置。

## [0.7.1] - 2026-07-20

### Added
- **M6 Fastboot 调试通道发现**：
  - 观察到 USB 枚举 ID：VID `1F3A` / PID `1010`。后续测试未建立标准 Fastboot 握手，因此该记录不构成“可用 Fastboot”结论。
  - 曾在 Google USB INF 中加入 Allwinner ID；该手工修改后的包已被标为**禁止安装**，因为原 Catalog 不再覆盖修改后的 INF。
  - 排除并记录了 Recovery 状态下的输入设备（红外、USB键盘）和 ADB 接口的无响应现象。

## [0.7.0] - 2026-07-20

### Changed
- **项目文档系统重构**：
  - 项目理念重写，引入"证据驱动调试"和"最小预装"原则。
  - 项目章程重新定义，目标软件更新为实际预装清单。
  - 文档统一，移除过时的设计决策。
  - ADR 与实际实现同步（BLEAutoPair 和 UBTunnel 已标记为已删除）。
  - Product 分区最终确定为 300 MB。
  - 引入验证矩阵和工程原则。
  - 引入证据时间线和实验日志。

### Added
- **M6 容器写入观察**：
  - PhoenixCard 烧录进度达到 100%，烧录问题已解决。
  - 修正 `pack_image.py` 文件对齐（16 字节 → 1024 字节）修复了 U-Boot unaligned read panic。
- **M6 启动验证**：
  - 设备可见 Boot logo 和 Android Recovery 界面；启动链首个失败点未定位。
  - Android System 未能启动，当前调查方向转向启动故障分析。
- **调试文档**：
  - 新建 `docs/M6_DEBUG_LOG.md` 记录完整的实验日志和现象归档。
  - 引入 D-0008 工程原则："修改前先获取证据"。

## [0.6.0-M6.1] - 2026-07-20

### Added
- **M6 首次物理烧录与调试**：
  - TF 卡 242 锁死排除（Windows `diskpart clean`）。
  - 首次刷写停滞 5-10%，LED 高频闪烁。
  - 引入 img2simg 稀疏化，证明 Sparse 格式非根因。
  - 修正 pack_image.py 1024 字节对齐，烧录 100% 完成。

## [0.5.0] - 2026-07-20

### Added
- **M3+ 预装应用落地**：
  - 集成 Gboard TV输入法、Kodi 21.3 Omega、VLC 3.7.2 Beta 1、LocalSend 1.17.0。
- **M4 ROM 重打包与 AVB 离线产物生成**：
  - AVB 签名工具链原生修复（`pycryptodome` 替代 `openssl`）。
  - 分级重打包与签名（system, product, vendor, vendor_dlkm）。
  - vbmeta 签名链重建。
  - Super 逻辑卷拼接（lpmake + img2simg）。
- **M5 Allwinner 固件打包与校验和重算（离线）**：
  - `tools/pack_image.py` 自动化打包。
  - 伴生校验字重算（10 分区全部 Checksum OK）。

## [0.4.0] - 2026-07-19

### Added
- **M3+ 增强裁剪与预装应用集成**：
  - 全系统应用审计：90+ 个应用按 P0/P1/P2/保留/预装五级分类。
  - 启动器方案评审：确立 FLauncher(默认) + SimpleLauncher(fallback) 方案。
  - 增强裁剪执行：新增删除 14 个应用，累计释放 298.7 MB。
  - 预装应用集成：FLauncher、SmartTube。
  - build.prop 更新：默认启动器指向 FLauncher。
  - 裁剪脚本重写：`scripts/purify-rom.py` 一站式自动化管线。
- **M4 工具链配置**：
  - 获取并验证 `make_ext4fs.exe` + `cygwin1.dll`、`lpmake.exe`。
  - 下载 AOSP `testkey_rsa2048.pem`。
  - 全部工具 SHA-256 锁入 `tools/LOCKFILE.md`。

## [0.3.0] - 2026-07-19

### Added
- **M3 反定制规划与 APK 审计完成**。

## [0.2.0] - 2026-07-19

### Added
- **M2 分区与启动链审计完成**。

## [0.1.0] - 2026-07-19

### Added
- **M0 + M1 完成**：原始固件基线记录、Allwinner 容器解析、伴生校验和推导。
