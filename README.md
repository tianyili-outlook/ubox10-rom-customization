# UBOX10 Android TV 固件定制工程 (ubox10-rom-customization)

本仓库用于以可复现、可审计、开源且安全的方式对 UnblockTech UBOX10 (I12 Pro Max / Allwinner H616) Android TV 12 固件进行解包、分析与反定制净化。

当前阶段：**M6 物理设备烧录验证完成 → 系统启动故障调查中**。

---

## 🚀 项目当前状态 (Current Status)

项目已完成 **M0–M5** 全部里程碑。固件已成功通过 PhoenixCard 刷写至设备（烧录进度 100%），设备可启动至 Bootloader 和 Android Recovery，但 **未能进入 Android System**。

* **开发分支状态**：`main` 与 GitHub 同步。
* **裁剪成果**：已删除 14 个厂商定制/无用应用（包括 BLEAutoPair、UBTunnel、开机音效 `111.mp3`），释放 **298.7 MB** 空间。
* **启动器方案**：默认启动器已被替换为开源的 **FLauncher**，SimpleLauncher 保留为紧急 fallback。
* **预装应用集成**：FLauncher (默认桌面)、SmartTube (YouTube TV)、Gboard (TV输入法)、Kodi Omega (媒体中心)、VLC (播放器)、LocalSend (局域网传输) 均已全部预装并封包完毕。
* **固件烧录**：✅ PhoenixCard 烧录进度 100%，刷写成功。
* **设备启动**：⚠️ 设备显示官方 boot logo 后自动进入 Android Recovery，未进入 Android System。Recovery 目前无法操作（红外遥控无响应，USB 键盘无输入）。

**当前阻塞项**：确定 Android 为何在成功烧录后进入 Recovery 而非 System。

---

## 💡 核心审计发现 (Key Discoveries)

1. **AOSP test-keys 签名引导链**
   固件 `vbmeta` 签名链完全基于 AOSP 官方公开测试密钥 (test-keys)，可直接对修改后的分区重签名通过 Verified Boot。

2. **调试与宽容模式内核**
   内核启动参数 `buildvariant=userdebug` + `androidboot.selinux=permissive`，降低了系统修改阻碍。

3. **Framework 启动器强锁定机制**
   安博固件在 Framework 中强制读取 `ro.sw.defaultlauncher_package` 和 `ro.sw.defaultlauncher_class` 系统属性来锁定启动器。已通过修改 `build.prop` 将默认指向 FLauncher。

4. **LED 指示灯 PWM 依赖**
   前面板状态灯由 `com.mitac.android.i2ctool` 服务控制，`H616_led_blink-s` 目录绝对不能删除。

5. **PhoenixCard 烧录死锁已修复**
   早期自定义固件因 `pack_image.py` 文件对齐错误（16 字节 → 需 1024 字节）导致 U-Boot 底层 unaligned block read panic。修正后烧录顺利完成。

6. **设备可达 Recovery**
   Bootloader、Kernel 和 Recovery 分区均功能正常。当前问题发生在 Android System 启动阶段。

---

## 🗑️ 已删除应用清单 (Removed Apps)

### 🔴 P0 强烈推荐删除 (已执行)

| 应用 | 大小 | 删除理由 |
|------|------|----------|
| happycast | 107.9 MB | 乐播投屏广告软件 (M3 已删) |
| X12 | 12.2 MB | 安博定制桌面启动器 |
| UBTunnel.6 | 12.1 MB | 安博 VPN 翻墙隧道 |
| settingwizard | 31.7 MB | 安博定制设置向导 |
| browser-v1.1 | 16.1 MB | 安博定制浏览器 |
| AwlogSettings | 2.2 MB | 全志日志调试配置 |
| zysrf | 41.3 MB | Google 注音输入法 |
| DragonAgingTV/Att/Box/Factory | — | 全志工厂测试工具 (M3 已删) |

### 🟠 P1 推荐删除 (已执行)

| 应用 | 大小 | 删除理由 |
|------|------|----------|
| H618_UpgradeV3 | 18.3 MB | 厂商 OTA 升级工具 |
| NanoOtaBle | 1.9 MB | 蓝牙遥控器 OTA |
| Update | 1.3 MB | 系统更新检查器 |
| CZFileManager | 10.1 MB | 第三方文件管理器 |
| Chrome | 118.4 MB | 浏览器 (用户确认删除) |
| TvdFileManager | 3.4 MB | 全志文件管理器 |
| BLEAutoPair | 19.2 MB | 蓝牙自动配对 (用户使用红外遥控器，已确认不需要) |

### Vendor 分区

| 文件 | 大小 | 说明 |
|------|------|------|
| 111.mp3 | 10.3 MB | 开机音效 |

**累计释放空间：~298.7 MB (不含 M3 阶段已删的 ~108 MB)**

---

## 📦 预装应用 (Preinstalled Apps)

### system/app/ (系统级，不可卸载)

| 应用 | 版本 | 来源 |
|------|------|------|
| **FLauncher** (默认启动器) | v2025.07.001 (osrosal fork) | [GitHub](https://github.com/osrosal/flauncher) |
| **SimpleLauncher** (fallback) | v1.0 | 原始固件自带 |

### product/app/ (用户级，可通过设置管理)

| 应用 | 版本 | 大小 | 来源 |
|------|------|------|------|
| **SmartTube** (YouTube TV) | v31.94 stable | 25.0 MB | [GitHub](https://github.com/yuliskov/SmartTube) |
| **Gboard** (Google TV 输入法) | v16.1.02 TV release | 24.6 MB | [APKMirror](https://www.apkmirror.com) |
| **Kodi** (媒体中心) | v21.3 Omega | 65.0 MB | [kodi.tv](https://kodi.tv) |
| **VLC** (视频播放器) | v3.7.2 Beta 1 | 45.9 MB | [APKMirror](https://www.apkmirror.com) |
| **LocalSend** (局域网传输) | v1.17.0 | 16.7 MB | [GitHub](https://github.com/localsend/localsend) |

---

## 🛠️ 已锁定的固件工具链 (Locked Toolchain)

所有工具的版本、SHA-256 和来源均记录于 [tools/LOCKFILE.md](tools/LOCKFILE.md)：

| # | 工具 | 用途 |
|---|------|------|
| 1 | `sunxi_image_tool.py` | 全志 IMAGEWTY v3 容器解析 |
| 2 | `unpack_bootimg.py` | AOSP 启动镜像解包 |
| 3 | `mkbootimg.py` | AOSP 启动镜像重打包 |
| 4 | `avbtool.py` | Verified Boot 签名/校验 |
| 5 | `lpunpack.py` | Super 分区逻辑卷解包 |
| 6 | `extract_ext4.py` | 自研 Ext4 文件提取 |
| 7 | `make_ext4fs.exe` + `cygwin1.dll` | Ext4 镜像编译 (Windows) |
| 8 | `lpmake.exe` | Super 分区逻辑卷拼装 |
| 9 | `testkey_rsa2048.pem` | AOSP AVB 测试签名密钥 |
| 10 | `lpdumps.exe` | Super 分区逻辑卷 Metadata 导出 |
| 11 | `simg2img.exe` | Sparse 格式镜像转换为 Raw 格式 |
| 12 | `pack_image.py` | 全志 IMAGEWTY v3 容器打包器 |
| 13 | `img2simg.exe` | Raw 格式镜像转换为 Sparse 格式 |

---

## 📂 目录结构

* **[docs/](docs/)**：工程决策文档 (ADR)、发现记录、变更日志。
* **[tools/](tools/)**：已验证版本的工具链及锁定文件。
* **[scripts/](scripts/)**：自动化裁剪/打包脚本。
* **[work/](work/)**：中间提取产物与解包区（不入 Git 库）。

---

## ✅ 验证矩阵 (Validation Matrix)

| 组件 | 状态 | 备注 |
|------|------|------|
| 固件解包 | ✅ | 已验证 |
| super 提取 | ✅ | 已验证 |
| ext4 提取 | ✅ | 已验证 |
| APK 裁剪 | ✅ | 已完成 |
| 启动器替换 | ✅ | 稳定 |
| Product 分区扩容 | ✅ | 300 MB |
| AVB 签名 | ✅ | 已验证 |
| super 重构 | ✅ | 已验证 |
| PhoenixCard 封包 | ✅ | 已生成 |
| 固件烧录 | ✅ | 进度 100% |
| Bootloader | ✅ | 已执行 |
| Recovery | ✅ | 可达 |
| Android System | ❌ | 启动失败 |
| Wi-Fi / 蓝牙 / 以太网 / HDMI / 红外遥控 | ⏳ | 待验证 |

---

## 🧭 固件定制路线图 (Roadmap)

- [x] **M0**：原始固件基线校验与托管
- [x] **M1**：Allwinner 容器解析与伴生校验和推导
- [x] **M2**：分区解包与 Verified Boot 启动链审计
- [x] **M3**：反定制规划与 APK/Init 静态审计
- [x] **M3+**：增强裁剪执行 + 启动器替换 + 预装应用集成
- [x] **M4**：ROM 重打包与 AVB 签名
- [x] **M5**：固件封装与 PhoenixCard 校验和生成
- [/] **M6**：物理设备烧录验证与系统启动故障调查 *(设备可达 Recovery，Android System 启动失败)*
- [ ] **M7**：候选发布
