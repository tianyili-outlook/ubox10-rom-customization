# 待办事项

## 当前：M6 物理烧录与实机调试 (Physical Flashing & Device Verification Debugging)

- [x] **实机首次烧录尝试** (2026-07-20)
  - [x] 首次写入 `x12-purified.img` 触发 5%-10% 进度卡死与 LED 蓝绿交替高频闪烁挂起错误。
  - [x] 成功执行官方镜像对照组实验，证明刷机链路正常，故障 100% 指向重打包固件逻辑。
- [x] **二次烧录尝试 (引入 img2simg)** (2026-07-20)
  - [x] 现象与首次完全一致，证明格式兼容非唯一主因，故障域锁定在体积绝对溢出或偏移量错位。
- [ ] **🚧 物理死锁问题破除 (Hard Blocker - 停止重打包尝试)**
  - [ ] **行动 1：静态体积精准测量**：直接比对原厂 `super.fex` 与生成的 `super.img` 字节数。若定制包体积膨胀，必须优化 `lpmake` 参数强制缩容至原厂物理边界之下。
  - [ ] **行动 2：UART 串口硬件级诊断**：焊接 UBOX10 主板 J21 UART 引脚并直连 PC（115200 波特率），抓取死锁瞬间的 U-Boot 底层 Fatal error panic 异常栈。

## 已完成

- [x] **M4 ROM 重打包与 AVB 签名** (2026-07-19)
  - [x] 选择并锁定适合 Windows 平台的 ext4 镜像生成工具（使用 `make_ext4fs.exe`）。
  - [x] 将已净化修改的逻辑卷目录（`system_extracted`、`product_extracted`）重新打包编译为 raw `ext4` 分区映像。
  - [x] 使用 `avbtool.py` 为重新生成的逻辑分区映像计算并追加 AVB Hashtree 校验页，并使用 standard test-keys 重新对 `vbmeta` 等签名。
  - [x] 使用 `lpmake` 重新构建 `super` 逻辑分区映像。
  - [x] 校验打包镜像的物理结构，确保其大小、对齐与原始分区完全一致。
- [x] **M5 固件封装与伴生校验和重算** (2026-07-19)
  - [x] 编写 `tools/pack_image.py` 将 `super.img` 和重新生成的 vbmeta/校验 和装回 Allwinner 格式的固件容器。
  - [x] 调用自研算法重新计算所有分区伴生校验文件（`V*.fex`），并在 `x12-purified.img` 中完成校验和写入。
- [x] **M0：原始镜像基线** (2026-07-19)
- [x] **M1：只读容器清单** (2026-07-19)
  - [x] 选择自研可审计的 Allwinner 容器解析器（`sunxi_image_tool.py`）。
  - [x] 编写解析脚本，自动生成 `work/manifest.json` 条目清单。
  - [x] 交叉验证目录中所有预期的分区，并用数学方法推导验证了伴生文件的校验和。
  - [x] 将自研工具锁入 `tools/LOCKFILE.md`。
- [x] **M2：分区与启动链审计** (2026-07-19)
  - [x] 获取并验证 Android Boot 镜像分解工具 `unpack_bootimg` / `mkbootimg` / `avbtool` / `lpunpack` 并在 `tools/LOCKFILE.md` 中锁定。
  - [x] 分包并反编译 `boot.fex` (Header v3) 和 `vendor_boot.fex` (Header v3)，成功提取内核与 ramdisks。
  - [x] 使用 `fdt` 成功反编译 `sunxi.fex`、`vendor_boot/dtb` 和 `dtbo.fex` (从 `dtbo.fex` 的 `DT_TABLE` 容器中剥离出来的 entry 0) 到可读的 DTS 源码。
  - [x] 使用 `avbtool` 审计 `vbmeta` 签名链，确认全部使用 AOSP 官方公开 `test-keys` (`SHA256_RSA2048`)。
  - [x] 使用 `lpunpack.py` 对 `super.fex` (Sparse 格式) 进行解包，并利用纯 Python 的 `ext4` 解析器完整提取了 `system_a`, `vendor_a`, `product_a`, `vendor_dlkm_a` 内的全部文件和符号链接。
- [x] **M3：反定制规划与 APK 审计** (2026-07-19)
  - [x] 使用 `pyaxmlparser` 静态解析了定制 APK/AP 属性，成功识别核心启动器 `X12`、代理服务 `UBTunnel` 和臃肿投屏 `happycast` 的依赖。
  - [x] 全面盘点并解析了固件中 222 个 `.rc` 文件中的 custom services，发现 `preinstall.sh` 脚本的 PWM 控制逻辑及 Google Location Wizard 弹窗自动跳过代码。
  - [x] 深度审计了 `system/build.prop`，发现框架绑定的 `ro.sw.defaultlauncher_package` 属性控制机制。
  - [x] 制定了反定制与 Launcher 替换策略并写入 `docs/DECISIONS.md` 的 `ADR-0004` 中。
  - [x] 编写并成功运行了自动化净化清理脚本 `scripts/purify-rom.py`，一键完成了系统裁剪、launcher 指向修改和系统无用日志禁用工作。
