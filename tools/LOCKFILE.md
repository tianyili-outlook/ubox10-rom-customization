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
* **验证结果**：成功解析 `vbmeta.fex`、`vbmeta_system.fex` 和 `vbmeta_vendor.fex` 的离线描述符；密钥来源、bootloader 根信任和候选签名的运行时验签均未验证。

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
* **验证结果**：成功在 M2 阶段递归提取四个 Ext4 逻辑分区的 4000+ 文件；符号链接被保存为 `.symlink` 文本存根，适合分析但不保留可重建的链接/元数据语义。

### 7. make_ext4fs.exe & cygwin1.dll
* **名称**：Android ext4 image creation tool (Cygwin Port)
* **版本/提交**：Android 8.1.0 branch compatible
* **来源**：https://github.com/RickyDivjakovski/Android_IMG_Tools_Cygwin
* **许可证**：Apache-2.0 / GNU GPL
* **文件 SHA-256 (make_ext4fs.exe)**：`94CF4C2AFF6E88FD657D6DD182256D105F111E4F5E442141AEC43452BBCFFC60`
* **文件 SHA-256 (cygwin1.dll)**：`F22D44EF78AFE17D48718A8E1616A8A45E488D267F22ED000E61F728225C4661`
* **适用平台**：Windows (x86/x64)
* **调用命令**：`tools/make_ext4fs.exe [options] <output_img> <src_dir>`
* **验证结果**：可在 Windows 终端加载并显示帮助文档；尚未证明它能在当前提取流程下保留完整 ext4 语义或生成可启动分区。

### 8. lpmake.exe
* **名称**：Android Logical Partition Image Maker (super.img builder)
* **版本/提交**：android-15.0.0_r25
* **来源**：https://github.com/Rprop/aosp15_partition_tools
* **许可证**：Apache-2.0
* **文件 SHA-256**：`602D59D2670F6DCCFEF81D854444AAFE2CAC7995D07E22158271BEF65ACCAF3D`
* **适用平台**：Windows (x86/x64)
* **调用命令**：`tools/lpmake.exe [options]`
* **验证结果**：成功在 Windows 终端内启动并显示用法指南；产物的设备侧挂载/启动行为未验证。

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

### 11. pack_image.py
* **名称**：Allwinner IMAGEWTY v3 Firmware Re-packager
* **版本/提交**：Custom self-contained Python script
* **来源**：Workspace self-authored
* **许可证**：Apache-2.0
* **文件 SHA-256**：`C4406ABDD2BD56A8496DF15126CABE301D5F571FFAD45AA1376E147DC54BEAF5`
* **适用平台**：跨平台 (Python 3.13+)
* **调用命令**：`python tools/pack_image.py`
* **验证结果**：成功在本地运行并生成重组且容器校验通过的 IMAGEWTY 文件；这不证明动态分区、AVB 或 Android 启动通过。

### 12. img2simg.exe
* **名称**：Android Raw to Sparse Image Converter
* **版本/提交**：android-15.0.0_r25
* **来源**：https://github.com/Rprop/aosp15_partition_tools
* **许可证**：Apache-2.0
* **文件 SHA-256**：`FE9FF41802F61FF1E510F2E012C398D1B2BF7E2C90392967182FD594B9AF5B65`
* **适用平台**：Windows (x86/x64)
* **调用命令**：`tools/img2simg.exe <raw_img> <sparse_img>`
* **验证结果**：成功将 3.00 GB 的 raw `super_raw.img` 转换为兼容 AOSP 标准的 sparse `super.img`。

## 主机侧诊断工具（不属于发布工具链）

以下项目可用于 M6a 的只读主机取证；它们不因为存在于工作区就获得安装或刷写授权。

### 13. Android Platform Tools

* **版本**：r37.0.0
* **文件 SHA-256 (`fastboot.exe`)**：`DD55FEF77AB2753B6423F37F39D91CB00CE53AB4539A2431577F07C4ABCAA32A`
* **文件 SHA-256 (`adb.exe`)**：`957E46B8615F7AF5B7292A2DDABE98D2E61940C3FB2B0545756507F080613E71`
* **用途**：仅用于 `fastboot --version`、`fastboot devices` 和握手成功后的只读 `fastboot getvar version`。
* **当前结果**：U1 后 `fastboot devices` 返回 `992304568773    fastboot`，`getvar version` 返回 `0.5`；协议已验证。白名单变量仅得到 `product=sunxi`、`secure=yes`，槽位/userspace 变量不支持。不得执行任何写入或状态变化命令。

### 13a. 当前 Windows host binding（观察记录，非可分发工具）

* **观察日期**：2026-07-22
* **证据**：`logs/device/20260722-001337/usb-evidence.json`，SHA-256 `9823D913E07031822B41567C22DE3D88539E5D21F70431AFEAD29C2A3F766B33`。
* **当前设备/服务**：`USB\VID_1F3A&PID_1010\992304568773`，`WinUSB` / `\Driver\WINUSB`，`Status=OK`，`Problem=0`。
* **当前驱动包**：`C:\Windows\INF\oem79.inf`（Provider `libwdi`），只读审计 SHA-256 `5B13785711DC58CE2041D5DD9BAF15EFBFFF276A824BEFDBC3BC1F70F3CF1532`。
* **关键差异与结果**：初始 `DeviceInterfaceGUIDs` 没有 `{F72FE0D4-CBCB-407D-8814-9ED673D0DD6B}`。U1 已在完整备份后仅追加该 GUID，保留原值；物理拔插后 Fastboot 枚举/协议成功。详情和精确回滚见 `docs/U1_FASTBOOT_HOST_BINDING_TRIAL.md` 与 `logs/device/20260722-004314/`。
* **限制**：这是现场状态记录，不授权复制/分发/安装该驱动，也不作为发布 ROM 工具链的一部分。

### 13b. 本地 Android `mke2fs`（M6b.2 观察项，尚未放行）

* **文件**：`tools/platform-tools/mke2fs.exe`
* **运行时报告**：`mke2fs 1.47.2`；EXT2FS library `android-platform-15.0.0_r5-314-ga1f793f6b`
* **文件 SHA-256**：`BE42ABB5D1651C8766E230E7AF834BD8E0F2085857CCB483463F58BA5AD65E1A`
* **配置 SHA-256 (`mke2fs.conf`)**：`AD58A58DCDD24D85055814CA9CAC67DB89D4E67C434E96774BDCE0D0A007D067`
* **观察**：usage 支持 `-d root-directory|tarball`；本次仅运行 `-V` 和无输出路径 usage，未生成文件系统。
* **状态**：**尚未锁定/不得用于 M6b fixture 或 Android 分区生产**。D-0041 已确认目录输入依赖宿主 `lstat`/编译期 xattr，tarball 依赖 libarchive；usage 不能证明 Windows/NTFS 上的完整语义。当前又缺配套 `debugfs/e2fsck/dumpe2fs` 与第二解析实现。详见 D-0040、D-0041、ADR-0010、R-019/R-020。

### 13c. 计划中的 Linux e2fsprogs fixture oracle（尚未下载/构建）

* **角色**：只作为 M6b Gate 1 synthetic ext4 fixture 作者与作者侧结构检查器；不自动成为 Android system 生产构建器。
* **计划版本**：upstream e2fsprogs `1.47.2`。
* **官方来源**：https://www.kernel.org/pub/linux/kernel/people/tytso/e2fsprogs/v1.47.2/
* **计划源码归档**：`e2fsprogs-1.47.2.tar.xz`。
* **官方签名清单中的 SHA-256**：`08242E64CA0E8194D9C1CAAD49762B19209A06318199B63CE74AE4EF2D74E63C`。
* **所需产物**：`mke2fs`、`debugfs`、`e2fsck`、`dumpe2fs`；每个产物的版本、SHA-256、构建环境和 configure/make 命令均待实际构建后填写。
* **状态**：**设计锁定、物料未取得、不可调用**。D-0043/D-0045/D-0046/D-0052 已确认 CPU 能力、系统盘恢复边界、SVM H2b 和 H2c 双 feature Apply；当前 firmware virtualization=true，WSL/VMP 已 Enabled，系统等待重启。D-0053 已将正常重启、Linux/WSL runtime、联网下载和基础依赖纳入用户自管 B1 批次，完成后统一验收；上游源码、签名、工具哈希、toolchain manifest 和 fixture 仍继续分门。取得后必须先验证签名清单与源码 SHA-256，只生成 toolchain manifest 供评审；不得直接生成 fixture。
* **详细设计**：`docs/M6B_EXT4_FIXTURE_ORACLE_DESIGN.md` / ADR-0010。

### 14. 手工修改的 Google USB INF（禁止安装）

* **文件**：`tools/usb_driver/usb_driver/android_winusb.inf`
* **文件 SHA-256**：`C6B84F54F4FDE2AE15E4855B7D50A88B8C717B531D31F0F1DB26AE94617CD5EA`
* **状态**：仅作审计样本，**不得安装**。
* **原因**：在 Google 原始包中新增 `1F3A:1010` 匹配项后，原有 Catalog 不再能覆盖修改后的 INF/驱动包完整性。不得通过关闭 Windows 签名强制来规避该问题。

### 15. Zadig

* **版本**：2.9.788
* **文件 SHA-256**：`4ECAA95DF3DA3621486A043AEF8B3050B8BAFE7C901402871E816229EF82039B`
* **签名观察**：当前 Windows Authenticode 显示 Akeo Consulting 签名有效。
* **状态**：可作为只读枚举参考，**不得直接 Bind/Install**。普通 WinUSB 绑定未必注册 AOSP `fastboot.exe` 所需的 Android USB interface GUID，也会改变主机驱动状态。
