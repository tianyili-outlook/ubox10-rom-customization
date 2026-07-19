# 待办事项

## 当前：M3 反定制规划与 APK 审计 (Decustomization Planning & APK Audit)

- [ ] 审计 `/system/app/X12`、`/system/app/UBTunnel.6` 和 `/system/app/happycast` 的依赖关系与服务行为。
- [ ] 审查 `init.rc` 及各组件 init 启动脚本，分析厂商自定义守护进程（Daemons）与开机自启任务。
- [ ] 提取并分析系统的 `build.prop` 等属性配置，规划反激活或精简的安全参数修改列表。
- [ ] 制定反定制清理方案，编写自动化精简脚本（保留全部硬件驱动与基本系统组件）。

## 已完成

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
