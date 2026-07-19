# UBOX10 ROM 改造运行手册 (Runbook)

本手册详细规范了 UBOX10 固件的反定制净化、编译、重签名与容器重打包的标准工作流。

---

## 🛠️ 核心执行管线 (Pipeline Workflows)

### 第一阶段：反定制净化与预集成
1. 将下载的预集成第三方 APK 放入 `work/preinstall_apks/` 目录：
   - 必须包含：`FLauncher.apk`、`SmartTube.apk`、`Gboard.apk`、`kodi-21.3-Omega-arm64-v8a.apk`、`org.videolan.vlc...apk`、`LocalSend...apk`。
2. 运行净化裁剪脚本，对提取的文件进行 P0/P1 精简，预装应用，并修改默认启动器属性：
   ```powershell
   python scripts/purify-rom.py
   ```
   *注意：该步骤将释放约 300MB 的系统空间，并将 `system/build.prop` 内的默认 Launcher 指向 FLauncher。*

### 第二阶段：ROM 分区编译与 AVB 签名
1. 运行重打包脚本编译 ext4 镜像，使用 test-keys 重新写入 AVB Hashtree 校验和，并组装 `super` 逻辑卷：
   ```powershell
   python scripts/repack-rom.py
   ```
   *注意：由于 AOSP 工具链在 Windows 下的兼容性问题，必须确保 Python 环境中已安装 `pycryptodome` 库。脚本将在 Python 内部进行原生 RSA 签名计算以绕过 openssl 命令行缺失的阻碍。*
2. 该脚本将在 `work/` 目录下生成以下产物：
   - `super.img` (动态分区镜像逻辑卷, ~1.36 GB)
   - `vbmeta.img`, `vbmeta_system.img`, `vbmeta_vendor.img` (重新签名的 AVB 校验链)

### 第三阶段：全志 Image 封装与校验和计算
1. 运行固件容器打包脚本，将更新后的镜像装回 Allwinner image 容器并重新计算 10 个挂载分区的小端 uint32 校验和伴生文件（`V*.fex`）：
   ```powershell
   python tools/pack_image.py
   ```
2. 对最终生成的 `x12-purified.img` 固件进行格式过检与比对：
   ```powershell
   python tools/sunxi_image_tool.py verify x12-purified.img
   ```
   *期待输出：`Verification complete: 10 partitions OK, 0 mismatches/errors.`*

---

## 💾 物理烧录与安装步骤 (Flashing Guide)

1. 打开 Windows 平台下的 **PhoenixCard** 工具 (推荐 v4.2.x 或 v4.9.x)。
2. 选择刚刚生成的 **`x12-purified.img`** 固件。
3. 插入 MicroSD 卡，并根据需要选择烧录模式：
   - **Startup (启动卡模式)**：固件直接在 TF 卡内运行，供临时测试和验证硬件使用。
   - **Product (量产卡模式)**：TF 卡插入盒子后上电，盒子会自动读取卡内固件并写入板载闪存 (eMMC)。刷写进度条走完（前置面板指示灯发生颜色变化或屏幕提示）后，**必须拔掉 TF 卡**，重新上电即可启动纯净系统。
4. 首次开机后验证指示灯、遥控器及默认 FLauncher 桌面逻辑。
