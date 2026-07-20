# 变更日志

遵循 Keep a Changelog 风格；所有日期使用 ISO 8601。

## [0.7.1] - 2026-07-20

### Added
- **M6 Fastboot 调试通道发现**：
  - 成功捕获 USB 握手标识：VID `1F3A` / PID `1010`，确认其为 **Android Fastboot Mode**。
  - 下载官方 Google USB 驱动，并在 `tools/usb_driver/` 目录下完成 Allwinner Fastboot 硬件 ID 的注入，为免焊接获取系统环境变量与诊断日志打下基础。
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
- **M6 烧录验证成功**：
  - PhoenixCard 烧录进度达到 100%，烧录问题已解决。
  - 修正 `pack_image.py` 文件对齐（16 字节 → 1024 字节）修复了 U-Boot unaligned read panic。
- **M6 启动验证**：
  - 设备成功启动至 Bootloader 和 Android Recovery。
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
- **M4 ROM 重打包与 AVB 签名成功**：
  - AVB 签名工具链原生修复（`pycryptodome` 替代 `openssl`）。
  - 分级重打包与签名（system, product, vendor, vendor_dlkm）。
  - vbmeta 签名链重建。
  - Super 逻辑卷拼接（lpmake + img2simg）。
- **M5 Allwinner 固件打包与校验和重算成功**：
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
