# UBOX10 M8

## 项目章程

UBOX10 M8 是面向客厅长期使用的 Android TV ROM 项目。项目以已核实的 Allwinner H616 / sun50iw9 硬件证据为准，不把未经芯片级验证的 H618 销售标签当作事实。Android 12、ARM64 Linux kernel 加传统 ARM32 Android userspace 是工程起点，不是永久终点。

M8 的 North Star 是把这台设备建设成一台连贯、可靠、可维护的 Android TV appliance：无需触摸屏或开发电脑即可完成日常操作，媒体、输入、网络、存储、音频、功耗和应用生命周期能够长期稳定协作。Projectivy 可以继续作为合适的 launcher，但平台架构不应无必要地绑定到某一个 launcher。

成功标准不是追逐单项规格，而是让这台实际硬件在可恢复、可重复验证的前提下达到最高可靠能力。若较低的名义规格能提供明显更好的稳定性、画质或可用性，就应优先选择它。

## 长期产品目标

### 1. 现代 Android TV 体验

形成 remote-first、Leanback/TV-native 的完整客厅体验。长期平台应具备可靠的物理 rc-core 遥控、本地 TV IME、官方 Google TV mobile remote 与手机文字输入，以及可预期的焦点、HOME、BACK、音量和特殊键行为。Wi-Fi、Ethernet、Bluetooth、USB、HDMI 音频、应用生命周期、suspend/resume、HDMI CEC 和电源行为应像同一台消费设备的组成部分，而不是互不关联的开发板功能。

### 2. ARM64-capable Android userspace

长期目标是从 ARM32 Android userspace 走向真正可用的 ARM64-capable 环境；在合适时可采用 `zygote64_32` 等 64/32 混合架构，为必须保留的 32-bit HAL、服务和应用提供兼容性。AArch64 同进程 graphics/mapper provider 必须与 H616/sun50iw9 栈匹配并经过 exact-board 验证；media、audio、wireless、DRM 等可进程隔离的成熟 ARM32 服务不要求为了架构纯粹性改写为 64-bit。

64-bit 的目标不是“framework 能启动”，而是现代 64-bit Android TV 应用可稳定运行，且 graphics、media、audio、DRM、networking、Bluetooth、input 与其他成熟功能没有不可接受的回归。在达到现有成熟基线前，64-bit 工作应作为隔离的架构里程碑或实验分支。

### 3. 最高实际媒体与显示质量

目标是获得这台 UBOX10 能长期可靠提供的最佳画面、声音与播放体验，而不是强制达到 4K 或 4K60。优先顺序是：最高稳定可用分辨率、可靠硬件解码、良好 frame pacing/画质、正确 HDMI 与音频行为、长时间播放稳定性。

应以实测逐步评估 1080p、1440p/2K、可行时的 4K、H.264/HEVC/VP9 硬解、高码率、丢帧与 A/V sync、HDMI hotplug、EDID、显示模式切换、HDR、10-bit、色彩空间以及音频/passthrough 能力。4K、HDR 和 10-bit 都是要调查和最大化的能力，不是无条件验收门槛；稳定的 1440p 或 1080p 优于不稳定的名义高分辨率。

### 4. Netflix、DRM 与商业流媒体

Netflix 是明确的长期目标，但目标表述为：获得这台设备在合法、技术上可行范围内的最佳稳定 Netflix 体验。验证应逐级进行：TV 应用可运行，登录/浏览/遥控交互正常，真实受保护内容可播放，再确定可合法维持的最高质量。SD、HD、更高分辨率或 4K 都不能预先假定。

需要如实调查 Widevine security level、TEE、OEMCrypto、provisioning、secure decoder/video pipeline、HDCP、codec/output limit、device identity 和服务认证。不得伪造认证、写入未授权 DRM key、绕过服务保护、在无证据时宣称 L1，或把 Widevine plugin 存在等同于 Netflix 认证。若硬件、provisioning 或认证形成结构性上限，应以证据确认边界，然后在边界内优化播放质量、遥控体验、音视频稳定性和可重复性。同一原则适用于其他商业服务。

### 5. 真实应用生态

平台应服务真实客厅负载，而不止通过合成 Android 测试。代表性目标包括 YouTube、Bilibili TV、Moonlight、Kodi、Plex、Jellyfin、本地/NAS 媒体播放、AirPlay 或等效 receiver，以及其他可信 Android TV 应用。兼容性必须以启动、遥控导航、登录、硬件加速、最高可靠画质、音频、控制器、网络和长会话稳定性验证；安装成功本身不构成应用兼容 PASS。

### 6. 应用安装与生命周期管理

提供安全、方便、可维护的 TV 应用发现、安装和更新路径。Android TV GMS/Play Store 的可行性应独立研究，包括正确 TV package set、Play Services、账号登录、feature identity、兼容过滤和 Play Protect/认证边界；GMS 实验不得连带破坏成熟平台功能。

同时保持不依赖 GMS 的可行路径：可信 APK provenance、签名和版本核对、更新检测、TV 兼容判断、可逆安装与回滚。核心设备功能不得暗中依赖 GMS。

### 7. 本地存储与网络媒体

面向日常媒体使用验证 USB host、常见存储设备、大文件、适当的 FAT 系列、exFAT、可行时的 NTFS、GPT、大容量磁盘、可靠 hotplug/unplug、SMB、NFS 或应用层 NAS、高码率网络播放与持续传输。文件系统“能挂载”不是终点，真实读写、播放、拔插和长时间稳定性才是验收依据。

### 8. 输入与客厅交互质量

设备应在没有触屏或开发电脑时完整可用。物理遥控必须可靠，Menu、Settings 等特殊键应具备清晰语义；本地 TV IME、mobile remote/mobile text、Bluetooth HID/controller 和各类 TV 应用中的焦点行为应可预测。不同输入路径应正常共存，而不是依赖某一只遥控器或手机。

### 9. Power、HDMI 与设备生命周期

系统应在真实电视使用模式中表现可预测：正常和重复启动、关机、IR power、suspend/resume、wake、CEC、TV/盒子上电顺序、HDMI 拔插与重新协商，以及恢复后的 Wi-Fi、Ethernet、Bluetooth、audio 和 mobile Remote。电源管理改动必须保持恢复能力，避免制造难以诊断的硬件状态。

### 10. 稳定性、温控与性能

最终系统应适合长期家庭运行：无有意义的 crash/restart loop，内存行为稳定，CPU/governor 与 thermal policy 合理，无持续 runaway clock/load，idle 行为可接受，并能在持续媒体负载下稳定工作。必要时执行物理 thermal soak 和 24h/48h 等长时间验证。性能以用户可见行为为准，不为 benchmark 或峰值牺牲稳定性。

### 11. 安全与成熟发布姿态

开发阶段可以保持 permissive 或 debug-friendly，但成熟发布应逐步采用与已理解硬件路径匹配的 SELinux enforcing policy、最小且有理由的 privileged permissions、明确的 ADB/debug policy、可行的 AVB/integrity、较少的 root/debug surface、安全 factory reset 和清晰的 user-data 处理。安全加固必须建立在功能理解之后，不为清除 AVC 或追求形式完整而破坏硬件功能。

### 12. 可维护性、可复现性与恢复

持续采用 reproducible build、deterministic candidate、精确 artifact hash、source/proprietary provenance（不重新分发受限二进制）、最小变更、单变量候选、回归测试和明确 DEVICE ACCEPTED gate。原始固件与不可替代证据不得被修改，开发全过程至少保留一条已知可用恢复路径。

长期可评估更简单的升级流程、重大实验前备份、可靠 rollback，以及确有价值时的 OTA 或等效更新机制。目标不只是产生一次成功镜像，而是让 ROM 能安全演进和维护。

### 13. 后续 Android 平台演进

Android 12 是当前工程基础，不必是永久终点。当硬件栈已充分理解、功能成熟、64-bit 可行性明确且 graphics/media/vendor 依赖受控后，再评估新的 Android/Android TV 世代。OS 版本迁移不得混入普通 M8 功能修复，应作为独立架构项目，拥有自己的验收标准和 rollback。

## 架构原则

- **功能优先于架构纯粹性。** 不为“更干净”破坏可用硬件路径。
- 保留已知良好的 vendor、TEE、graphics、media、DRM 和其他 hardware-facing 组件，直到替代方案被证明。
- **证据先于修复。** 不以猜测替代首个可复现失败或运行时证据。
- 风险较高的架构实验必须与 accepted baseline 隔离。
- 不宣称未经过物理或运行时验证的能力。
- 优先使用标准 Android/AOSP 机制，避免无必要的 bespoke hack。
- 始终维护可恢复、可回滚路径；保留原始固件和已知良好恢复资产。
- 除非里程碑明确要替换某项能力，否则必须保留已验收功能。
- 优化实际硬件的**最高可靠能力**，而不是任意规格目标。
- 4K、HDR、Widevine L1、Netflix HD/4K 和完整 64-bit 迁移都是要诚实调查并尽力提升的目标，不是硬件不支持时仍必须达到的门槛。
- 较低名义规格若显著提高稳定性和可用性，是可接受且通常更好的结果。
- 长期目标决定路线优先级；清空当前 TODO 本身不是项目目的。

## 文档职责与当前状态入口

| 文档 | 唯一职责 |
|---|---|
| `README.md` | 项目章程、North Star、长期目标和不可轻易变化的架构原则 |
| [`docs/m8/STATUS.md`](docs/m8/STATUS.md) | 当前 accepted baseline、运行时事实、候选状态、已证明结论、关键历史证据和技术边界 |
| [`docs/m8/TODO.md`](docs/m8/TODO.md) | 从长期目标与当前现实之间的差距推导出的短期/中期执行路线 |
| [`docs/BUILD.md`](docs/BUILD.md) | 可复现 build、integration 和 candidate 生成机制 |
| [`docs/DEVICE_TEST.md`](docs/DEVICE_TEST.md) | 物理设备、恢复与 acceptance procedure |
| [`docs/m8/candidates/`](docs/m8/candidates/) | 每个候选专属的实现、工件和证据记录 |

README 只在长期产品目标、永久架构约束或文档/规划模型改变时更新。候选名、镜像/hash、IP、当日 PASS/FAIL、候选阶段状态、近期缺陷、短期任务和详细候选历史必须留在 STATUS、TODO 或候选记录中，不能回流到 README。

## Agent Planning Contract

规划任何 M8 工作时：

1. 先完整阅读 `README.md`，理解长期目标与不可妥协的架构原则。
2. 阅读 `docs/m8/STATUS.md`，建立当前已验证现实，不沿用过时假设。
3. 阅读 `docs/m8/TODO.md`，理解既有短期和中期执行计划。
4. 明确 README 目的地与 STATUS 现实之间的差距。
5. 从该差距提出或更新可执行 TODO，而不是直接把愿望当成实现方案。
6. 优先选择能保留已验收功能、隔离变量、可验证且可恢复的里程碑。
7. 不得只为清理当前 TODO 而忽视 README 层面的项目目标。
8. 不得把易变候选、测试结果或近期状态复制回 README。

**README 是“项目最终去向”的 source of truth；STATUS 是“项目现在位置”的 source of truth；TODO 是“下一步工作”的 source of truth。**

## 历史边界

M7 冻结于 Git tag [`m7`](https://github.com/tianyili-outlook/ubox10-rom-customization/tree/m7)。M8 保留必要 provenance 和恢复资产，但不在项目章程中复制历史候选链或易变运行状态。
