# 待办事项

## 当前：M2 分区与启动链审计

- [ ] 运行 `tools/sunxi_image_tool.py` 将固件内所有分区镜像副本提取至 `firmware/extracted/`。
- [ ] 获取并验证 `unpack_bootimg` / `mkbootimg` 等 Android 工具，锁入 `tools/LOCKFILE.md`。
- [ ] 使用 `unpack_bootimg` 分解 `boot.fex` 与 `vendor_boot.fex`，提取并解压其中的 ramdisk 与 kernel。
- [ ] 静态分析 `dtbo.fex`，还原并比对 Device Tree (DTS)。
- [ ] 使用 `avbtool` 解析并审计 `vbmeta.fex`, `vbmeta_system.fex`, `vbmeta_vendor.fex` 的签名与 AVB 链。
- [ ] 解析 `super.fex`（Android 12 动态分区），提取并挂载逻辑分区（`system_a`/`system_b`, `vendor_a`/`vendor_b`, `product_a`/`product_b` 等）。

## 已完成

- [x] **M0：原始镜像基线** (2026-07-19)
- [x] **M1：只读容器清单** (2026-07-19)
  - [x] 选择自研可审计的 Allwinner 容器解析器（`sunxi_image_tool.py`）。
  - [x] 编写解析脚本，自动生成 `work/manifest.json` 条目清单。
  - [x] 交叉验证目录中所有预期的分区，并用数学方法推导验证了伴生文件的校验和。
  - [x] 将自研工具锁入 `tools/LOCKFILE.md`。
