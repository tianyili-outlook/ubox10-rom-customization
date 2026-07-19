# 变更日志

遵循 Keep a Changelog 风格；所有日期使用 ISO 8601。

## [0.6.0-M6.1] - 2026-07-20

### Added
- **M6 受控硬件验证与刷机调试**：
  - **TF 卡 242 锁死排除**：记录 PhoenixCard 格式化报错 242 故障原因，制定 Windows `diskpart clean` 命令行磁盘清理规避规程。
  - **刷机死锁与 LED 高频报警记录**：记录在物理 UBOX10 上烧录 `x12-purified.img` 触发 5%-10% 进度卡住，前置面板蓝绿 LED 灯高频闪烁挂起硬件级 Fatal Error。
  - **对照组实验完成**：使用原厂包 `x12-1024.img` 同卡同刷，低频交替闪烁并顺利刷完闭环，验证了物理硬件链路完整性，将故障点定位回定制包 `super` 绝对体积溢出或 sparse 对齐缺陷。
  - **引入调试文档**：新建 [M6_DEBUG_LOG.md](file:///c:/Users/tiany/Documents/ubox10-rom改造/docs/M6_DEBUG_LOG.md) 详细归档现象与推演。
  - **制定两项 Debug 行动**：1) 测量 `super` 物理容量约束边界以限制其重打包最大体积；2) 准备主板 UART 串口（波特率 115200）直连抓取 Fatal error panic 异常栈。
  - **二次实机刷写死锁确认**：引入 `img2simg` 稀疏化处理后，实机依然在 5%-10% 触发 LED 高频死锁挂起。确诊黑盒尝试达到边界，全面中止基于猜测的重打包行为，强制转入静态数据体积测量与 UART 硬件日志捕获阶段。

## [0.5.0] - 2026-07-20

### Added
- **M3+ 预装应用落地**：
  - 集成用户提供的真正需要的 APK 清单到 product 分区中：Gboard TV输入法、Kodi 21.3 Omega 媒体中心、VLC 3.7.2 Beta 1 播放器、LocalSend 1.17.0 局域网传输（替代 Google Files / Send Files to TV）。
- **M4 ROM 重打包与 AVB 签名成功**：
  - **AVB 签名工具链原生修复**：在 `avbtool.py` 中引入 `pycryptodome` (Crypto) 依赖，利用纯 Python 实现 RSA-2048 私钥的载入和 `pow(m, d, n)` 签名，成功规避了 Windows 下调用 `openssl` 进程报错的问题。
  - **分级重打包与签名**：将裁剪修改后的 system 分区（原大小）和 product 分区（扩容至 300MB）重新编译为 ext4 镜像，并对 system, product, vendor, vendor_dlkm 所有 4 个分区应用 AOSP test-key 重签名与 hashtree 追加。
  - **vbmeta 签名链重建**：新生成 `vbmeta_system.img`、`vbmeta_vendor.img` 与主 `vbmeta.img` 闭环验证签名链。
  - **Super 逻辑卷拼接**：使用 `lpmake.exe` 按照 3GB 物理尺寸和 1MB sector 对齐将 4 个分区组合编译为 sparse `super.img`。
- **M5 Allwinner 固件打包与校验和重算成功**：
  - **自动化打包工具编写**：编写并执行 `tools/pack_image.py`，加载原始 Image Manifest，自动重排 46 个文件的地址块偏移和长度，并写回 `x12-purified.img` 容器中。
  - **伴生校验字重算**：自动计算 10 个挂载分区的小端 uint32 累加字校验和（checksum）并写入 `V*.fex` 伴生校验分区。
  - **固件完整性过检**：运行 `tools/sunxi_image_tool.py verify` 对生成的 `x12-purified.img`（1.50 GB）进行 100% 格式比对校验，全部通过（10 partitions OK）。

## [0.4.0] - 2026-07-19

### Added
- **M3+ 增强裁剪与预装应用集成**：
  - **全系统应用审计**：盘点 system/product/vendor 三大分区共 90+ 个应用，按 P0(强烈推荐删除)/P1(推荐删除)/P2(可选)/保留/预装 五级分类。
  - **启动器方案评审**：对 FLauncher、Projectivy Launcher、SimpleLauncher 三款 Android TV 启动器进行全面对比，确立 FLauncher(默认) + SimpleLauncher(fallback) 方案。
  - **增强裁剪执行**：新增删除 14 个厂商定制/无用应用 (X12、UBTunnel、settingwizard、browser、AwlogSettings、zysrf、H618_UpgradeV3、NanoOtaBle、Update、CZFileManager、Chrome、TvdFileManager、BLEAutoPair、vendor/111.mp3)，累计释放 298.7 MB。
  - **预装应用集成**：下载并预装 FLauncher v2025.07.001 (osrosal 社区 fork, arm64) 和 SmartTube v31.94 stable (arm64)。
  - **build.prop 更新**：默认启动器从 SimpleLauncher 更新为 FLauncher (`me.efesser.flauncher`)。
  - **裁剪脚本重写**：`scripts/purify-rom.py` 完全重写为支持 P0/P1/Vendor 分级裁剪、FLauncher/SmartTube 预装、可选 APK 检测的一站式自动化管线。
- **M4 工具链配置**：
  - 获取并验证 `make_ext4fs.exe` + `cygwin1.dll` (ext4 镜像编译) 和 `lpmake.exe` (Super 分区拼装)。
  - 下载 AOSP `testkey_rsa2048.pem` 用于 AVB 重签名。
  - 全部工具 SHA-256 锁入 `tools/LOCKFILE.md`。

## [0.3.0] - 2026-07-19

### Added
- **M3 反定制规划与 APK 审计完成**：
  - **APK 静态审计**：引入 `pyaxmlparser` 依赖，自动扫描并分析了 `X12.apk` (核心启动器 `com.moons.mylauncher10`，使用 system UID 权限)、`UBTunnel.6.apk` (专有网络代理 `com.yanggis.chinatunnelCOM`)、`happycast.apk` (第三方广告投屏) 以及备份的 `SimpleLauncher.ap` 和 `zysrf.ap`。
  - **Init RC 服务盘点**：扫描了固件中 222 个 `.rc` 脚本并提取出所有自定义启动项。分析发现了 Allwinner LED 状态灯 PWM 控制机制、工厂 run-in 自动化测试脚本，以及在 `preinstall.sh` 中硬编码自动跳过 Google 初始向导地理位置同意框的 UI 注入代码。
  - **build.prop 系统属性审计**：深入分析发现 Android TV 框架绑定了 `ro.sw.defaultlauncher_package` 和 `ro.sw.defaultlauncher_class` 属性来强制引导至厂商 `X12` 定制启动器，并找到了后台大量冗余日志的全局 persistent 开关。
  - **反定制清理策略确立**：在 `docs/DECISIONS.md` 记录 `ADR-0004`，设计了安全精简而不破坏系统框架的 “Launcher 属性指向替换” 与 “广告及诊断程序清退” 方案。
  - **自动化精简工具开发**：编写并成功运行了自动化裁剪精简脚本 `scripts/purify-rom.py`。一键清理了 107MB 的投屏广告及全部厂测工具，将预载 launcher (`SimpleLauncher`) 重打包为默认启动器，并关闭了后台所有的日志收集服务。

## [0.2.0] - 2026-07-19

### Added
- **M2 分区与启动链审计完成**：
  - **工具获取与锁定**：获取了 Android 12 兼容的 `unpack_bootimg.py`、`mkbootimg.py`、`avbtool.py` 和 `lpunpack.py` 并计算哈希锁定在 `tools/LOCKFILE.md`。
  - **Boot 分区解压**：解压了 `boot.fex` 和 `vendor_boot.fex`，分离出了 kernel 和 ramdisk 并且利用纯 Python 的 LZ4 & CPIO 工具链完整解压出两者的 ramdisk 目录。
  - **DTS 反编译**：在 Python 环境安装了 `fdt` 依赖，解包了 `dtbo.fex` 容器并成功反编译 `sunxi.fex`、`vendor_boot/dtb` 和 `dtbo.fex` (entry 0) 的 DTS 源码。
  - **AVB 安全链审计**：利用 `avbtool` 确认 vbmeta 均采用 RSA-2048 算法以及 AOSP 公开默认测试密钥 (test-keys) 进行签名，内核命令行中 SELinux 默认配置为宽容模式 (permissive) 且 build variant 为 `userdebug`。
  - **逻辑分区解包**：使用 `lpunpack.py` 对 sparse 格式的 `super.fex` 进行转换和提取，成功解出 system_a/vendor_a/product_a/vendor_dlkm_a。
  - **Ext4 递归提取**：自研了纯 Python 的 `extract_ext4.py` 文件提取工具，在 Windows 平台上绕过 7-Zip 对部分 Ext4 功能支持不佳的局限，无缝且完整提取了四大逻辑分区的全部 4000+ 文件与符号链接（以 `.symlink` 形式记录保存）。
  - **厂测与定制 App 盘点**：审计发现了 UnblockTech 的核心推广/私有服务组件 (`UBTunnel.6` 和 `X12`)、大型第三方推广 adware (`happycast`，占 107MB) 以及全志的 factory 测试工具 (`DragonAgingTV`, `DragonBox` 等)。

## [0.1.0] - 2026-07-19

### Added
- **M0 基线建立**：完成工程初始化、架构设计、目录分配以及原始固件 `x12-1024.img` 校验（SHA-256 为 `371a6536...`）。
- **Git 托管**：连接远程仓库 `tianyili-outlook/ubox10-rom-customization`，完成首个 Commits 的推送。
- **M1 解析与验证**：
  - 自研开源可审计的 Allwinner 固件工具 `tools/sunxi_image_tool.py`。
  - 数学证明并验证了 Allwinner 的累加和校验和算法。
  - 实现自动化脚本 `scripts/parse-image.ps1`，成功提取分区 manifest JSON，完成 10 个主分区的伴生校验和的一致性验证（全部成功）。
  - 更新工具锁、决策树和待办事项。
