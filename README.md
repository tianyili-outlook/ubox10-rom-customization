# UBOX10 Android TV 固件定制工程 (ubox10-rom-customization)

本仓库用于以可复现、可审计、开源且安全的方式对 UnblockTech UBOX10 (I12 Pro Max / Allwinner H616) Android TV 12 固件进行解包、分析与反定制净化。

当前阶段：**M6a — 无修改启动链证据采集**。候选镜像可烧录，但 Android System 尚未启动；在取得启动链证据前，暂停新增刷写实验。

---

## 🚀 项目当前状态 (Current Status)

M0–M3 的离线分析已完成；M4 与 M5 仅完成离线构建/容器校验，尚未通过启动链验收。候选固件曾由 PhoenixCard 写入至设备（烧录进度 100%），设备可达 Android Recovery，但 **未能进入 Android System**。

* **开发分支状态**：`main` 与 GitHub 同步。
* **裁剪与预装**：候选构建已包含裁剪与预装计划；因 System 尚未启动，实际运行结果尚未验证。
* **启动器方案**：FLauncher/SimpleLauncher 是历史离线候选；用户目标为 Projectivy，最终启动器与预装清单将在 M6b 通过后以 manifest 单独评审，均尚未实机验证。
* **固件烧录**：✅ PhoenixCard 烧录进度 100%；这只证明容器可写入，不代表 Android 可启动。
* **设备启动**：⚠️ 设备显示官方 boot logo 后自动进入 Android Recovery，未进入 Android System。Recovery 目前无法操作（红外遥控无响应，USB 键盘无输入）。
* **USB 枚举**：✅ Windows 已观察到 `USB\VID_1F3A&PID_1010`，设备名为 `sunxi`；兼容 ID 含 `Class_FF&SubClass_42&Prot_03`，与 AOSP Fastboot 的接口描述符条件一致。
* **标准 Fastboot**：✅ 已完成只读协议验证：U1 后 `fastboot devices` 显示 `992304568    fastboot`，`fastboot getvar version` 返回 `version: 0.5`。尚未读写分区或改变设备状态。
* **Fastboot 白名单变量**：`product=sunxi`、`secure=yes`；`is-userspace`、槽位和 `has-slot:*` 均返回 `not supported`。该精简实现不能确认 A/B 状态，M6a 下一优先级为 UART 被动冷启动日志。

**当前阻塞项**：在不改写设备的前提下确认实际启动目标、A/B 槽位、BCB/Recovery 触发源，以及 AVB、dm-verity、ext4 或 init 的首个失败点。执行顺序见 `docs/M6_DIAGNOSTIC_PLAN.md`。

---

## 💡 核心审计发现 (Key Discoveries)

1. **AVB 结构可离线解析，但运行时信任未验证**
   原件和候选镜像均可由 `avbtool` 解析；候选镜像的根信任、密钥一致性和 bootloader 运行时验签仍待启动日志确认。

2. **调试启动链构建已隔离**
   `userdebug`、Permissive SELinux、root ADB 和 Recovery USB 注入只属于历史诊断候选，不属于发布 ROM，也不再作为当前获取日志的路线。

3. **Framework 启动器强锁定机制（离线发现）**
   安博固件在 Framework 中会读取 `ro.sw.defaultlauncher_package` 和 `ro.sw.defaultlauncher_class` 系统属性。历史候选曾将其改为 FLauncher；Projectivy 的最终集成仍须在 M6c 作为独立的单变量回归验证。

4. **LED 指示灯 PWM 依赖**
   前面板状态灯由 `com.mitac.android.i2ctool` 服务控制，`H616_led_blink-s` 目录绝对不能删除。

5. **PhoenixCard 容器可被写入，但根因归属仍需日志**
   调整 `pack_image.py` 对齐后曾达到 100% 写入；这证明容器路径可用，不足以证明早期失败一定由 U-Boot 的特定 panic 引起，也不证明 Android 可启动。

6. **设备可达 Recovery，但失败点尚未定位**
   可见 Recovery 仅证明设备进入了 Recovery 路径；尚不能证明是 System、A/B 槽位、BCB、AVB、挂载或 init 中的哪一环触发。必须以 UART 或已验证的只读 bootloader 查询确认。

7. **当前 ext4 全量重建不具备运行时放行资格**
   现有提取器将符号链接写成 `.symlink` 文本文件，且重建未恢复文件系统元数据。此路径只能视为离线构建原型，必须先通过零内容改动 round-trip 验证。

---

## 🗑️ 候选删除清单（离线执行，实机未验证）

下表描述候选构建的内容计划，不表示这些删除已经在可启动 ROM 上验证。M6b 后每项删除将改为单变量 manifest 变更并执行硬件回归。

### 🔴 P0 强烈推荐删除（候选构建）

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

### 🟠 P1 推荐删除（候选构建）

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

## 📦 历史候选预装应用（离线集成，实机未验证）

这不是最终产品清单。当前目标见 `PROJECT_CHARTER.md`：Projectivy、SmartTube、Kodi、Jellyfin、Moonlight、AirPlay 与合法 Google 服务/Play 可用性均须在 M6b 后独立审查来源、许可证、签名、分区归属和硬件兼容性。

### system/app/ (系统级，不可卸载)

| 应用 | 版本 | 来源 |
|------|------|------|
| **FLauncher**（历史启动器候选） | v2025.07.001 (osrosal fork) | [GitHub](https://github.com/osrosal/flauncher) |
| **SimpleLauncher**（历史回退候选） | v1.0 | 原始固件自带 |

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
| 14 | `platform-tools` r37.0.0 | 主机侧 ADB/Fastboot 探测；当前未与设备建立 Fastboot 握手 |

---

## 📂 目录结构

* **[docs/](docs/)**：工程决策文档、发现记录、变更日志，以及 [M6 诊断计划](docs/M6_DIAGNOSTIC_PLAN.md)、[启动失败假设矩阵](docs/M6_HYPOTHESIS_MATRIX.md)、[UART 手册](docs/UART_RUNBOOK.md)、[验证计划](docs/VALIDATION_PLAN.md)。
* **[tools/](tools/)**：已验证版本的工具链及锁定文件。
* **[scripts/](scripts/)**：自动化裁剪/打包脚本。
* **[work/](work/)**：中间提取产物与解包区（不入 Git 库）。

---

## ✅ 验证矩阵 (Validation Matrix)

| 组件 | 状态 | 备注 |
|------|------|------|
| 固件解包 | ✅ | 已验证 |
| super 提取 | ✅ | 已验证 |
| ext4 提取 | ⚠️ | 只读文件提取可用；重建语义不保真，不能放行 |
| APK 裁剪 | ⚠️ | 候选构建已生成，实机未验证 |
| 启动器替换 | ⚠️ | 离线集成完成，System 未启动 |
| Product 分区扩容 | ⚠️ | 离线结构校验通过，实机未验证 |
| AVB 签名 | ⚠️ | 离线产物已生成，运行时信任未验证 |
| super 重构 | ⚠️ | 元数据可解析，实机挂载未验证 |
| PhoenixCard 封包 | ⚠️ | 容器校验通过；端到端启动未通过 |
| 固件烧录 | ✅ | 进度 100%，运行时仍未通过 |
| Bootloader USB 枚举 | ✅ | `USB\VID_1F3A&PID_1010` / `sunxi` |
| Fastboot 接口描述符 | ✅（主机离线证据） | `FF/42/03`，与 AOSP Fastboot 匹配条件一致 |
| Fastboot 主机枚举 | ✅（主机实测） | U1 后 `992304568773    fastboot`；Windows GUID 变量的因果已验证 |
| 标准 Fastboot 命令握手 | ✅（协议已验证） | `getvar version` 返回 `version: 0.5`；仅执行读取命令 |
| Recovery | ✅ | 可达 (机器人躺倒界面，无菜单) |
| Recovery ADB | ❌ | 未启用 |
| UART 启动日志 | ⏳ | Fastboot 不支持槽位/用户空间变量；现为定位 Recovery 的第一优先级 |
| Android System | ❌ | 启动失败 |
| Wi-Fi / 蓝牙 / 以太网 / HDMI / 红外遥控 | ⏳ | 待验证 |

---

## 🧭 固件定制路线图 (Roadmap)

- [x] **M0**：原始固件基线校验与托管
- [x] **M1**：Allwinner 容器解析与伴生校验和推导
- [x] **M2**：分区解包与 Verified Boot 启动链审计
- [x] **M3**：反定制规划与 APK/Init 静态审计
- [x] **M3+**：增强裁剪执行 + 启动器替换 + 预装应用集成
- [/] **M4**：ROM 重打包与 AVB 签名 *(离线构建完成；ext4 语义保真和实机启动待验证)*
- [/] **M5**：固件封装与 PhoenixCard 校验和生成 *(容器可烧录；端到端启动待验证)*
- [/] **M6a**：无修改启动链取证 *(设备可达 Recovery；Fastboot 描述符已确认，等待经批准的主机 GUID 单变量试验或 UART 日志)*
- [ ] **M6b**：零内容改动重建对照 *(依赖 M6a)*
- [ ] **M7**：候选发布
