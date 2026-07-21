# 发现记录

每项发现必须包含来源、方法、证据位置、置信度、影响与下一步；推测必须明确标为推测。

## D-0001 — 官方固件使用动态分区

- 状态：已验证
- 日期：2026-07-19
- 结论：官方固件在 `super.img` 中存储逻辑分区（system_a, vendor_a, product_a, vendor_dlkm_a），采用 Retrofit A/B 动态分区设计。
- 影响：后续定制必须保留动态分区架构。

## D-0002 — AVB 描述符可离线解析；运行时根信任未验证

- 状态：离线已验证
- 日期：2026-07-19
- 事实：`vbmeta.fex`、`vbmeta_system.fex`、`vbmeta_vendor.fex` 均可由 `avbtool info_image` 解析，且可提取签名算法和公钥指纹。
- 结论：离线解析证明描述符结构存在，不证明 bootloader 接受候选密钥、候选描述符或重建后的 hashtree。
- 影响：未签名镜像不能视为有效构建产物；已签名镜像也不得仅凭离线检查视为可启动。

## D-0003 — Product 分区扩容为候选离线布局

- 状态：离线已验证；实机未验证
- 日期：2026-07-19
- 实验：扩展 product 分区至 300 MB。
- 结论：300 MB 在当前 `lpmake` 输出中容纳候选内容；对设备上的动态分区、fstab 和 OTA 行为是否兼容仍未知。

## D-0004 — 启动器替换已离线集成

- 状态：离线已验证；实机未验证
- 日期：2026-07-19
- 结论：候选 `build.prop` 已指向 FLauncher，且静态审计显示 Framework 会读取对应属性。Android System 尚未启动，不能据此确认启动器可以拉起。
- 影响：启动器替换仍是 M6c 的回归项。

## D-0005 — PhoenixCard 烧录死锁由镜像布局导致（已解决）

- 状态：已解决
- 日期：2026-07-20
- 观察：初始定制固件在烧录时反复停滞在 5%-10%。
- 实验：
  1. 实验 #1：首次刷写 → PhoenixCard 停滞 5-10%，LED 高频闪烁。
  2. 官方固件对照组 → 烧录成功，证明硬件链路正常。
  3. 实验 #2：引入 img2simg 稀疏化 → 现象不变，排除 Sparse 格式为根因。
  4. 实验 #3：修正 `pack_image.py` 文件对齐（16 字节 → 1024 字节）→ PhoenixCard 100% 完成！
- 结论：烧录问题已解决。不应再被视为当前阻塞项。

## D-0006 — Android Recovery 可视界面可达

- 状态：已观察
- 日期：2026-07-20
- 观察：修正镜像打包后，设备完成烧录并启动。启动序列到达 Bootloader → Recovery。System 未启动。
- 结论：仅证明设备到达了 Recovery 路径。不能据此证明 System 分区是唯一故障点，也不能证明 Bootloader、Kernel 或 Recovery 的全部功能正常。

## D-0007 — 当前根本原因未知

- 状态：开放
- 日期：2026-07-20
- 事实：设备进入 Android Recovery 而非 Android System。
- 事实：Recovery 目前无法操作（红外遥控无响应，USB 键盘通电但无可用输入）。因此尚未在 Recovery 中执行进一步诊断。
- 假设（未经实验验证）：
  - 文件系统不一致
  - init 启动失败
  - Recovery 触发标志位
  - 分区元数据不匹配
  - 启动配置不一致
- 下一步行动：在再次修改固件之前，先完成 M6a：主机 USB 身份采集、被动 UART 冷启动日志和 slot/BCB 假设表。

## D-0008 — 修改前先获取证据（工程原则）

- 状态：已接受
- 日期：2026-07-20
- 原则：在再次修改固件之前，每次修改应只回答一个具体问题。避免在单次实验中引入多个变更，否则实验证据将难以解读。此原则适用于所有后续调试工作。

## D-0009 — 早期“Fastboot 已可用”结论已撤销

- 状态：已否定（2026-07-21）
- 原始日期：2026-07-20
- 原始依据：`VID 1F3A / PID 1010`、Windows 友好名称 `sunxi` 和 Allwinner 资料中的 ID 映射。
- 更正证据：Windows 设备管理器已观察到 `USB\VID_1F3A&PID_1010&REV_0200` 与 `USB\VID_1F3A&PID_1010`；但 `tools\platform-tools\fastboot.exe devices` 和 `fastboot.exe getvar all` 都只显示 `< waiting for any device >`。
- 结论：ID 映射可作为 Fastboot 候选身份线索，但当前未建立标准 Android Fastboot 协议握手，不能读取变量、不能把该接口当作可用 Fastboot，也不能据此推断槽位或启动链状态。
- 影响：当前优先级改为主机侧 PnP/驱动身份取证；若仍无法建立只读握手，转为 3.3V UART 被动监听。不得安装仓库中手工修改的 Google USB INF，亦不得直接用 Zadig 绑定。

## D-0010 — `--flags 2` 与快速重启相关，但因果未证实

- 状态：部分验证
- 日期：2026-07-20
- 事实：在 vbmeta 映像生成时加入 `--flags 2` 参数（声明 Verification Disabled），会导致主板通电后在“安博科技” LOGO 出现后极速黑屏重启，陷入无限快速 Bootloop 循环。
- 结论：该现象与同批 boot/ramdisk 等变化共存，尚无 UART 或 bootloader 日志证明是 U-Boot 对该 flag 的直接反应。
- 影响：`--flags 2` 不进入任何候选构建；只有启动链日志和单变量试验能确认其因果关系。

## D-0011 — Legacy LZ4 重建存在部分离线兼容性证据

- 状态：部分验证
- 日期：2026-07-20
- 事实：官方 `boot.fex` 的 ramdisk 采用 Legacy LZ4 帧结构（魔数 `\x02\x21\x4c\x18`），且按每块 `8,388,608` 字节（8 MB）大小独立打包压缩。
- 方法：使用 Python `lz4.block.compress(..., store_size=False)` 模块进行 8 MB 块重压缩测试，其输出数据能够完美被原厂 LZ4 解压程序识别并解压为 100% 吻合的 CPIO 字节流。
- 影响：该结果不足以证明完整 boot 镜像的 CPIO 元数据、页对齐、签名和所有设备启动路径均兼容；仍须纳入 M6b 零内容重建验证。

## D-0012 — init 属性触发器是待验证的 USB 调试假设

- 状态：待验证假设
- 日期：2026-07-20
- 事实：在实验 #8 中，即使我们在 `prop.default` 中写入了 `sys.usb.config=adb` 并且设备成功无重启启动，Windows 依然只识别到 `VID_1F3A&PID_1010` (sunxi 裸口)，未识别到 ADB。
- 解释：`sys.usb.config` 的初始值、`init` 属性动作的加载时序、adbd 是否运行和 ConfigFS 是否绑定均未得到设备日志。仅凭 Windows 未出现 ADB，不能证明“同值静默”是原因。
- 影响：`none -> adb` 只能作为未来单变量实验假设，不能作为已证实的修复方案。

## D-0013 — boot/vendor_boot 中同名 rc 文件的优先级待验证

- 状态：待验证假设
- 日期：2026-07-21
- 事实：修改了 `boot.img` 中的 `init.recovery.sun50iw9p1.rc` 配置文件后，开机后设备的 USB 状态依然毫无变化，完全卡在 unbound。
- 解释：离线确实发现同名 rc 文件位于相关 ramdisk，但实际拼装顺序、导入顺序和文件优先级未由启动日志证明。
- 影响：未来若必须测试该假设，应先获得 UART 证据；不得把同时改写 boot 与 vendor_boot 当作已证实的修复方案。

## D-0014 — ConfigFS/UDC 时序与名称为待验证假设

- 状态：待验证假设
- 日期：2026-07-21
- 事实：离线 DTB 与 rc 脚本提供了一组候选 UDC 名称，但尚无设备侧 ConfigFS、FunctionFS 或内核错误日志。
- 影响：将 UDC 写入转移到 `sys.usb.ffs.ready`、或顺次尝试多个名称，只能作为隔离后的假设；不是已经验证的通用解决方案。

## D-0015 — Allwinner USB 接口已枚举；标准 Fastboot 传输未建立

- 状态：已观察
- 日期：2026-07-21
- 来源：Windows 设备管理器截图与用户在项目目录执行的 Platform Tools 命令。
- 证据：设备显示为 `sunxi`，硬件 ID 为 `USB\VID_1F3A&PID_1010&REV_0200` / `USB\VID_1F3A&PID_1010`；`fastboot devices` 与 `fastboot getvar all` 持续输出 `< waiting for any device >`。
- 结论：物理 USB 枚举成功；标准 Fastboot 会话没有建立。Allwinner 文档对 PID 的映射不能取代本机协议握手。
- 未发生的操作：未执行 `flash`、`erase`、`download`、`boot`、`continue`、`reboot`、`set_active`、`oem` 或 `unlock`。
- 更新（2026-07-22）：PnP 原始记录已归档；详见 D-0019 与 D-0020。下一步是经明确授权的主机 GUID 单变量试验，而非另装驱动。

## D-0016 — 当前 ext4 重建流程存在语义损失风险

- 状态：离线已验证
- 日期：2026-07-21
- 证据：`tools/extract_ext4.py` 将符号链接保存为普通 `.symlink` 文本文件；现有 `work/system_extracted` 中有 376 个此类存根。当前重建输入仅指向嵌套的 `system` 目录，且没有经审计的 fs_config、UID/GID、mode、SELinux xattr、capability 或硬链接恢复流程。
- 结论：现有 ext4 工具链适合只读分析，不足以产生可进入实机验证的系统分区。
- 下一步：在任何内容变更前实现元数据导出、符号链接重建与语义差分，并通过 M6b 零内容 round-trip。

## D-0017 — 候选 AVB 产物与官方原件存在离线差异

- 状态：离线已验证
- 日期：2026-07-21
- 证据：原始 vbmeta 公钥 SHA-1 为 `4728165bce7c07e3e2df5f4d787a0bfedc5ac133`；当前候选 `work/vbmeta.img` 为 `cdbb77177f731920bbe0a0f94f84d9038ae0617d`。原件描述符使用 SHA-256 hashtree 且含 FEC；候选脚本路径默认 SHA-1 并使用 `--do_not_generate_fec`。
- 结论：候选 AVB 只能称为“结构可解析的离线产物”；bootloader 的根信任、描述符兼容性和运行时验签均未知。
- 下一步：M6a 获取启动链日志；M6b 的零内容重建必须保留或解释每一项描述符差异。

## D-0018 — A/B 下载映射存在 a 槽倾向，真实设备槽位未知

- 状态：离线已验证；设备状态未验证
- 日期：2026-07-21
- 证据：`firmware/extracted/sys_partition.fex` 将 `boot.fex`、`vendor_boot.fex` 等下载项映射到 a 槽；b 槽没有等价的 `downloadfile` 条目。`sysrecovery.fex` 只有 11 bytes，`misc.fex` 在官方镜像中以零开始。
- 结论：容器映射不足以确定设备当前槽位、slot-successful 状态、BCB 内容或 Recovery 触发原因。
- 下一步：仅在标准 Fastboot 被协议验证后读取白名单变量，或以 UART 启动日志确认实际槽位与 BCB 路径。

## D-0019 — Fastboot 接口描述符已在 Windows PnP 中确认

- 状态：主机离线已验证；命令事务未验证
- 日期：2026-07-22
- 来源：`logs/device/20260722-001337/usb-evidence.json`，SHA-256 `9823D913E07031822B41567C22DE3D88539E5D21F70431AFEAD29C2A3F766B33`。
- 事实：同一现存实例为 `USB\VID_1F3A&PID_1010\992304568773`，兼容 ID 包含 `USB\COMPAT_VID_1F3A&Class_FF&SubClass_42&Prot_03`、`USB\Class_FF&SubClass_42&Prot_03`。
- 理由：AOSP Windows Fastboot 以 interface class/subclass/protocol `0xff/0x42/0x03` 筛选接口；这使“设备暴露 Fastboot-class USB 接口”的判断有描述符级证据，而不仅是 VID/PID 映射。
- 限制：Fastboot 描述符不证明 Windows 是否以正确 GUID 打开接口，也不证明设备会回应命令。`fastboot devices` 尚无序列号，故协议等级仍为未验证。
- 下一步：验证主机 GUID 变量；若仍无会话，采集 UART。

## D-0020 — 当前 libwdi WinUSB 绑定未注册 Platform Tools 所需的 Android interface GUID

- 状态：主机实测已验证；命令事务待验证
- 日期：2026-07-22
- 来源：`logs/device/20260722-001337/usb-evidence.json`、设备管理器驱动/事件截图，以及本机 `C:\Windows\INF\oem79.inf`（SHA-256 `5B13785711DC58CE2041D5DD9BAF15EFBFFF276A824BEFDBC3BC1F70F3CF1532`）的只读审计。
- 事实：当前设备 `Status=OK`、`Problem=0`，服务为 `WinUSB` / `\Driver\WINUSB`；`oem79.inf` Provider 为 `libwdi`，注册 `{9D8998B8-AD0B-4656-B575-AF23D189A1A8}`。设备参数尚有 `{DEE7A190-67CD-11D4-8A1D-005004C3A7C4}` 与 `{F72FE0D4-CBCB-407D-BC61-54A14A205A5A}`，但不含 AOSP Android interface GUID `{F72FE0D4-CBCB-407D-8814-9ED673D0DD6B}`。
- 执行结果：用户已授权 U1。`logs/device/20260722-004314/fastboot-interface-guid.json`（SHA-256 `91611924C6129AB43975555322DCBD3B69CAD4C963AD0369A201825D6060B7C8`）确认目标 GUID 已追加且原有三个 GUID 均保留；其备份 `guid-backup.json` 的 SHA-256 为 `0F3EBD47FA16AC0161EFD77B47DED3A8D66E095369891FA88A4B7163CB495E6E`。物理拔插后，用户记录 `fastboot devices` 输出 `992304568773    fastboot`。
- 结论：当前 WinUSB 内核服务本身可用，而目标 GUID 缺失确实阻止了 Platform Tools 枚举该接口。该单变量因果已经在主机上验证；它仍不证明设备会回应 Fastboot 命令，也不解释 Recovery。
- 下一步：只执行 `fastboot getvar version`；成功后才将 Fastboot 标记为“协议已验证”，再读取 M6a 白名单变量。

## D-0021 — 标准 Android Fastboot 协议已完成只读验证

- 状态：协议已验证
- 日期：2026-07-22
- 来源：`logs/device/20260722-004720/fastboot-devices.stdout.txt`（SHA-256 `A313C5BAAAD81FABBFDF615F11BABA5AEA4E225FA50D799B8C261E804F9CD573`）与 `fastboot-getvar-version.stderr.txt`（SHA-256 `FDF5D0ACD12B2746ED8BAEBD35F26AC8A177C07C48E5031C1AE5ACDA3DC64948`）。同目录 `SHA256SUMS.txt` 记录了本次完整采集清单。
- 事实：`fastboot devices` 返回 `992304568773    fastboot`；随后唯一发送的 Fastboot 命令为 `getvar version`，返回 `version: 0.5`，进程退出码为 0，总耗时 0.009 秒。
- 结论：设备当前 USB 接口不仅可被 Platform Tools 枚举，而且会按 Fastboot 协议回应只读请求；标准 Fastboot 现为“协议已验证”。
- 边界：这不授权任何状态改变命令，也不确定 Product、锁定状态、A/B 槽位、BCB、AVB 或 Recovery 根因。
- 下一步：仅按 M6a 白名单逐条读取 `product`、`secure`、`is-userspace`、`slot-count`、`current-slot` 与各 `has-slot:*`；每项独立记录、超时即停止。

## D-0022 — Allwinner Fastboot 实现不暴露 A/B 或 userspace 状态变量

- 状态：协议已验证；变量能力已验证
- 日期：2026-07-22
- 来源：`logs/device/20260722-004937/fastboot-readonly-vars.json`（SHA-256 `A3098D6760908FCFDF4774BFF63C848A778DF3216F943F870DDE5BA2F9E008A3`）及同目录逐项 stderr/stdout 与 `SHA256SUMS.txt`。
- 事实：每项请求均在 15 秒内以退出码 0 完成。`product` 返回 `sunxi`，`secure` 返回 `yes`；`is-userspace`、`slot-count`、`current-slot`、`has-slot:boot`、`has-slot:vendor_boot`、`has-slot:vbmeta`、`has-slot:super` 均返回 `not supported`。
- 结论：当前 Fastboot 实现足以提供受控只读协议通道，但变量表是精简/厂商实现，不能读取 A/B 槽位、动态分区槽位映射或 userspace 状态。这不否定离线已确认的 Android 12 A/B 动态分区容器结构，也不能把 `secure: yes` 解释成 bootloader 锁定状态或 AVB 已通过。
- 影响：停止进一步扩展 Fastboot 变量探测；不执行 `getvar all`。Recovery/BCB/真实槽位/AVB 首个失败点的下一项证据必须来自被动 UART 冷启动日志。
