# UBOX10 Android TV 固件定制工程 (ubox10-rom-customization)

本仓库用于以可复现、可审计、开源且安全的方式对 UnblockTech UBOX10 (I12 Pro Max / Allwinner H616) Android TV 12 固件进行解包、分析与反定制净化。

当前阶段：**M2 — 分区与启动链审计完成 (等待 M3 反定制规划确认中)**。

---

## 🚀 项目当前状态 (Current Status)

目前项目已成功走完 **M0 基线建立**、**M1 容器解析** 和 **M2 分区审计**，完成了对原始固件的 100% 提取和文件分析。

* **开发分支状态**：`main` 保持干净且与 GitHub 同步。
* **已解包产物**：全部 46 个分区提取至 `firmware/extracted/`（Git 已忽略以防大体积文件入库）；所有动态逻辑分区（`system`、`vendor`、`product`、`vendor_dlkm`）已递归提取至 `work/` 下。

---

## 💡 核心审计发现 (Key Discoveries)

截至 M2 阶段结束，我们在工程静态审计中取得以下重大发现（详见 [DISCOVERIES.md](file:///c:/Users/tiany/Documents/ubox10-rom改造/docs/DISCOVERIES.md)）：

1. **AOSP test-keys 签名引导链 (D-0004)**
   固件中的 `vbmeta.fex`、`vbmeta_system.fex` 和 `vbmeta_vendor.fex` 均使用 **SHA256_RSA2048** 算法，并且公钥为 **AOSP 官方公开默认测试密钥 (test-keys)**。
   * *影响*：我们可以对修改后的分区直接使用公开的 test-keys 重新签名，固件即可通过 Verified Boot (AVB) 引导启动，**无需破解底层安全链**。
2. **调试与宽容模式内核 (D-0004)**
   `vendor_boot` 的内核启动参数中明确指定 `buildvariant=userdebug` (调试版) 且 `androidboot.selinux=permissive` (SELinux 宽容模式)。
   * *影响*：极大地降低了定制 ROM、系统修改和安装 Root 组件（如 Magisk/KernelSU）时的底层策略阻碍。
3. **已提取的挂载映射 (D-0005)**
   在 `vendor_boot` 提取出的 `first_stage_ramdisk/fstab.sun50iw9p1` 中锁定了设备的动态分区挂载逻辑，属于 A/B 槽位（Retrofit）动态分区布局。
4. **定位厂商定制与推广软件 (D-0005)**
   审计成功锁定如下净化/精简的关键目标：
   * `/system/app/happycast` (107.9MB 乐播投屏，包含大量推广广告) ➔ **计划直接剔除**。
   * `/system/app/UBTunnel.6` (12.1MB UnblockTech 专有网络隧道服务) ➔ **待评估是否保留**。
   * `/system/app/X12` (9.8MB 厂商自定应用市场/校验主控) ➔ **计划精简/替换**。
   * 厂商工厂老化及测试工具：`DragonAgingTV`、`DragonAtt`、`DragonBox`、`Factory_detection` ➔ **计划直接剔除**。

---

## 🛠️ 已锁定的固件工具链 (Locked Toolchain)

所有镜像解包、重打包和校验工具的版本、SHA-256 和来源均记录于 [LOCKFILE.md](file:///c:/Users/tiany/Documents/ubox10-rom改造/tools/LOCKFILE.md)，以保证工程的可复现性：
1. `sunxi_image_tool.py` (自研 PhoenixCard 容器解析器，SHA-256: `8E121C8B...`)
2. `unpack_bootimg.py` (AOSP 官方启动镜像解包器，SHA-256: `4497241A...`)
3. `mkbootimg.py` (AOSP 官方启动镜像重打包器，SHA-256: `4616FBEF...`)
4. `avbtool.py` (AOSP 官方 Verified Boot 校验工具，SHA-256: `1F1FDDD2...`)
5. `lpunpack.py` (Android Super 分区解包工具，SHA-256: `600D1CAB...`)
6. `extract_ext4.py` (自研纯 Python 跨平台 Ext4 提取器，SHA-256: `E9F5290A...` - 规避 Windows 下符号链接及 7z 解析局限)

---

## 📂 目录结构与规范

* **[docs/](file:///c:/Users/tiany/Documents/ubox10-rom改造/docs/)**：工程决策文档（ADR）、发现记录（Discoveries）、系统架构与设计说明。
* **[tools/](file:///c:/Users/tiany/Documents/ubox10-rom改造/tools/)**：已验证版本的 Python 固件工具链及锁定文件。
* **[scripts/](file:///c:/Users/tiany/Documents/ubox10-rom改造/scripts/)**：一键式构建/解析/校验的自动化脚本管线。
* **[work/](file:///c:/Users/tiany/Documents/ubox10-rom改造/work/)**：中间提取产物与解包区（此目录不入 Git 库）。

详见 `docs/ARCHITECTURE.md`。

---

## 🧭 固件定制路线图 (Roadmap)

- [x] **Milestone M0**：原始固件基线校验与托管
- [x] **Milestone M1**：Allwinner 只读容器解析与伴生校验和推导
- [x] **Milestone M2**：分区解包与 Verified Boot 启动链审计
- [ ] **Milestone M3**：反定制规划与 APK 静态审计 (等待开始中...)
- [ ] **Milestone M4**：反定制净化与 System/Product 裁剪
- [ ] **Milestone M5**：固件封装打包与 PhoenixCard 累加校验和生成
- [ ] **Milestone M6**：物理设备刷写测试与驱动完整性验证
