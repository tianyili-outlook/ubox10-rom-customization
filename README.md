# UBOX10 M8 开发分支

状态：`IN DEVELOPMENT`

分支：`codex/m8-development`

稳定底座：M7 / Test8r2

当前阶段：`M8.0 ACTIVE / M8A.1 COMPLETE`

本分支用于把 UBOX10 / I12 Pro Max 从当前 32 位厂商 Android 产品逐步迁移到
真正的 Android 12 AOSP ATV。M7 稳定版继续由 `main` 维护；M8 完整通过后才
合并。

## 路线

1. **M8.0 共享证据门**：盘点硬件、运行时、ELF、HAL、VINTF、Kernel module
   和 DRM。
2. **M8A ARM32 ATV**：保留 UBOX10 的 boot、64 位 Kernel、vendor、
   vendor_dlkm、TEE 和 32 位 ABI，先建立可启动的 AOSP ATV product。
3. **M8B AArch64/multilib**：只有在 64 位 Mali、Gralloc、Mapper、HWC 和
   Vendor HAL 供体通过后才开始。

M8.GMS、M8.INPUT 和 M8.DRM 是横向验收项，不阻塞无 GMS 的基础 AOSP ATV
启动。

## 已确认

- 主板为 Allwinner H616 + AXP313A，4 GiB DDR3L、64 GB eMMC。
- Test8r2 是 64 位 Kernel 加纯 ARM32 Android 用户空间。
- 四分区共识别 1667 个 ELF：1554 个 ARM32 用户空间、0 个 AArch64 用户空间、
  22 个 AArch64 Kernel module、85 个 APK/JAR 内嵌 ELF。
- Mali-G31 EGL、Gralloc、Mapper、HWC、Vulkan 和主要媒体/无线组件只有
  32 位产物；这阻塞 M8B，不阻塞 M8A。
- Android 12 `aosp_tv_arm` 产品参考、platform manifest 和 superproject
  已锁定，M8A.1 产品差异与分区预算已完成。
- Test8r2 的 Widevine 16.1.0 可用但仅为 L3，HDCP 为 `NONE`，未发现 secure
  decoder；目前不能宣称 Netflix HD。
- 完整 AOSP 尚未同步：当前磁盘空间不足，构建前需要至少 400 GB 可用的
  Linux/ext4 构建卷。

## 下一步

1. 准备 AOSP 构建卷。
2. 同步已锁定的 Android 12 源码。
3. 进入 M8A.2a，静态构建最小 ARM32 ATV product。
4. 首个 M8A 刷写前，用同一探针补齐官方 ROM 的 DRM 对照。
5. 按 boot/ADB/HDMI → HAL → ATV UI → INPUT/GMS/DRM 分层验证。

当前无需继续搜索硬件丝印，也不下载 H618 BSP。

## 常用命令

运行测试：

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

重建 Test8r2 ELF 清单：

```powershell
python .\scripts\inventory-elf.py '@configs/m8-test8r2-elf.args'
```

采集脱敏的只读运行时信息：

```powershell
.\scripts\capture-m8-runtime-readonly.ps1 -Device "<电视IP>:7896"
```

运行 DRM 探针；探针 APK 会在采集后自动卸载：

```powershell
.\scripts\run-m8-drm-probe.ps1 -Device "<电视IP>:7896"
```

## 文档

- [M8 架构与分阶段计划](docs/architecture/M8_ARM64_AOSP_TV_MIGRATION.md)
- [M8 研究索引](docs/research/m8/README.md)
- [当前设备证据](docs/research/m8/current-device/)
- [M8A ARM32 ATV 设计](docs/research/m8/m8a-atv-arm32/)
- [DRM / Netflix 基线](docs/research/m8/drm-netflix/)
- [路线图](docs/ROADMAP.md)
- [待办](docs/TODO.md)

仓库只保存脚本、配置、来源锁和脱敏结论；官方固件、闭源 Vendor blob、
Google 专有 APK、密钥和大型构建产物不进入 Git。
