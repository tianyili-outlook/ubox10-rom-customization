# 工具锁定清单

在 M1 选型后逐项记录：名称、版本/提交、来源、许可证、下载文件 SHA-256、适用平台、调用命令和验证结果。不得使用未记录版本来生成可交付镜像。

## 锁定工具列表

### 1. sunxi_image_tool.py
* **名称**：Allwinner IMAGEWTY (PhoenixCard) 固件解析与验证工具
* **版本/提交**：v1.0.0 (Initial M1 release)
* **来源**：自研代码 (In-house development)
* **许可证**：Apache-2.0 (随项目整体授权)
* **文件 SHA-256**：`8E121C8B5978080A2929A703B79E7811843D4D6A0CB7E74C1CD377A79C615F8F`
* **适用平台**：跨平台 (Python 3.13+)
* **调用命令**：
  * 解析：`python tools/sunxi_image_tool.py list <image_path>`
  * 校验：`python tools/sunxi_image_tool.py verify <image_path>`
  * 提取：`python tools/sunxi_image_tool.py extract <image_path> [-o <out_dir>] [-f <file>]`
* **验证结果**：经测试成功解析 `x12-1024.img` 目录区并完美验证所有伴生 `V*.fex` 校验和。

### 2. unpack_bootimg.py
* **名称**：AOSP Boot Image Unpacker
* **版本/提交**：lineage-19.1 (Android 12 compatible)
* **来源**：https://github.com/LineageOS/android_system_tools_mkbootimg
* **许可证**：Apache-2.0
* **文件 SHA-256**：`4497241A77ED7E64BC619282A91689A17F655A76419C988F42DD4F8FB4E2A72F`
* **适用平台**：跨平台 (Python 3.13+)
* **调用命令**：`python tools/unpack_bootimg.py --boot_img <boot_img_path> --out <out_dir>`
* **验证结果**：成功解包 `boot.fex` (header v3, kernel 23MB, ramdisk 12MB) 和 `vendor_boot.fex` (header v3, dtb 68KB, ramdisk 1KB)。

### 3. mkbootimg.py
* **名称**：AOSP Boot Image Packer
* **版本/提交**：lineage-19.1 (Android 12 compatible)
* **来源**：https://github.com/LineageOS/android_system_tools_mkbootimg
* **许可证**：Apache-2.0
* **文件 SHA-256**：`4616FBEFA1C428C0D7441E3502704FF9F875C79B69451034EFEB6FA6783A76FD`
* **适用平台**：跨平台 (Python 3.13+)
* **调用命令**：`python tools/mkbootimg.py --header_version <v> ... -o <boot_img_path>`
* **验证结果**：备用，将在重打包阶段用于生成修改后的 boot/vendor_boot 镜像。

### 4. avbtool.py
* **名称**：AOSP AVB (Android Verified Boot) Tool
* **版本/提交**：v1.2 (AOSP master branch compatible)
* **来源**：https://github.com/cfig/Android_boot_image_editor
* **许可证**：Apache-2.0 / MIT
* **文件 SHA-256**：`1F1FDDD2764EBA76DC659415406062251EDCF2EB6B4E83B0F01D0224CD631281`
* **适用平台**：跨平台 (Python 3.13+)
* **调用命令**：`python tools/avbtool.py info_image --image <image_path>`
* **验证结果**：成功解析 `vbmeta.fex`、`vbmeta_system.fex` 和 `vbmeta_vendor.fex` 并确认其全部采用 standard AOSP test-keys 签名。

### 5. lpunpack.py
* **名称**：Android super.img Unpacker (Python version)
* **版本/提交**：v1.0.0 (Master branch)
* **来源**：https://github.com/unix3dgforce/lpunpack
* **许可证**：Apache-2.0
* **文件 SHA-256**：`600D1CAB2FC7DE5127FB287F4E2791718DB54EFB1102D0F365DB0D3EC1CCF62E`
* **适用平台**：跨平台 (Python 3.13+)
* **调用命令**：`python tools/lpunpack.py <super_img_path> <out_dir>`
* **验证结果**：待在 M2 阶段对 `super.fex` 进行解包测试。
