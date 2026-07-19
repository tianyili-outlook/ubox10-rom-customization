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
* **验证结果**：成功在 M2 阶段对 sparse 格式的 `super.fex` 进行转换与逻辑卷（system_a/vendor_a/product_a/vendor_dlkm_a）提取。

### 6. extract_ext4.py
* **名称**：纯 Python 跨平台 Ext4 文件递归提取工具 (Ext4 Extractor)
* **版本/提交**：v1.0.0 (Initial M2 release)
* **来源**：自研代码 (In-house development)
* **许可证**：Apache-2.0
* **文件 SHA-256**：`7F9333A71192A33D3EDCFE505085D9DCBC0C13EB9D811998BC23443443311A59`
* **适用平台**：跨平台 (Python 3.13+)
* **调用命令**：`python tools/extract_ext4.py <ext4_image_path> <dest_dir>`
* **验证结果**：成功在 M2 阶段递归提取了四大 Ext4 逻辑分区的全部 4000+ 文件，并以 `.symlink` 文本文件记录保存了所有符号链接，完美规避了 Windows 无特权创建符号链接的报错。

### 7. make_ext4fs.exe & cygwin1.dll
* **名称**：Android ext4 image creation tool (Cygwin Port)
* **版本/提交**：Android 8.1.0 branch compatible
* **来源**：https://github.com/RickyDivjakovski/Android_IMG_Tools_Cygwin
* **许可证**：Apache-2.0 / GNU GPL
* **文件 SHA-256 (make_ext4fs.exe)**：`94CF4C2AFF6E88FD657D6DD182256D105F111E4F5E442141AEC43452BBCFFC60`
* **文件 SHA-256 (cygwin1.dll)**：`F22D44EF78AFE17D48718A8E1616A8A45E488D267F22ED000E61F728225C4661`
* **适用平台**：Windows (x86/x64)
* **调用命令**：`tools/make_ext4fs.exe [options] <output_img> <src_dir>`
* **验证结果**：成功在 Windows 终端内加载并显示帮助文档，确认可用。

### 8. lpmake.exe
* **名称**：Android Logical Partition Image Maker (super.img builder)
* **版本/提交**：android-15.0.0_r25
* **来源**：https://github.com/Rprop/aosp15_partition_tools
* **许可证**：Apache-2.0
* **文件 SHA-256**：`602D59D2670F6DCCFEF81D854444AAFE2CAC7995D07E22158271BEF65ACCAF3D`
* **适用平台**：Windows (x86/x64)
* **调用命令**：`tools/lpmake.exe [options]`
* **验证结果**：成功在 Windows 终端内启动并显示用法指南。

### 9. lpdumps.exe
* **名称**：Android Logical Partition Metadata Dumper
* **版本/提交**：android-15.0.0_r25
* **来源**：https://github.com/Rprop/aosp15_partition_tools
* **许可证**：Apache-2.0
* **文件 SHA-256**：`1DC8385534CD9A849750E42BE04CE0AF2AF1CE0C89074E8B88947CBD36035D23`
* **适用平台**：Windows (x86/x64)
* **调用命令**：`tools/lpdumps.exe <super_img_path>`
* **验证结果**：成功在 Windows 终端内运行并提取了 super 分区的完整分区表、对齐参数和组大小。

### 10. simg2img.exe
* **名称**：Android Sparse to Raw Image Converter
* **版本/提交**：android-15.0.0_r25
* **来源**：https://github.com/Rprop/aosp15_partition_tools
* **许可证**：Apache-2.0
* **文件 SHA-256**：`5D840C8352D3790712B68077AB5E224D190737DD6ADD80541E6A871B6B205546`
* **适用平台**：Windows (x86/x64)
* **调用命令**：`tools/simg2img.exe <sparse_img> <raw_img>`
* **验证结果**：成功将 1.78 GB 的 sparse `super.fex` 转换回 3.00 GB 的 raw 镜像。
