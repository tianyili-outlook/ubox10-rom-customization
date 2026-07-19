# 变更日志

遵循 Keep a Changelog 风格；所有日期使用 ISO 8601。

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
