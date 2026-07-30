# M8 理念与架构

## Project philosophy

这是个人兴趣项目。目标是得到好用、能长期看电视且容易恢复的系统，不追求
生产级流程完整性。

```text
usable TV experience
→ stable enough for daily use
→ easy rollback
→ understandable failures
→ formal completeness
```

执行规则：

- 优先真实设备实验、真实画面和日常观看体验。
- 允许先构建、刷机和测试，再根据第一条可复现故障返回定位。
- exhaustive audit、完整 ABI 证明、CTS/VTS 和形式化合规不能长期阻塞一个
  可回退的 candidate。
- candidate 只验证本轮可能影响的路径，不要求所有警告清零。
- 只有可能造成砖机、破坏恢复、损坏安全材料或让故障无法归因时提高谨慎级别。
- 每轮只改变一个主要高风险架构层。
- Test8r2 始终是稳定恢复基线，不在 M8 实验中改写。

## 最终路线

### M8A：ARM32 Android 12 ATV

使用当前已经工作的 UBOX10 硬件栈，构建真正的 ARM32 Android 12 ATV
product：

- 保留现有 boot、64 位 Kernel、vendor、vendor_dlkm、DTB/DTBO、TEE 和
  32 位 Vendor ABI；
- 替换并重建 Android product 层，而不是继续把厂商平板/手机 UI 修成电视；
- 以 Android 12 `aosp_tv_arm` 为 product 参考，不复制 emulator、
  goldfish 或 generic_x86 的硬件层；
- 首轮保留已工作的 `AwTvProvision`，后续再以单变量实验替换；不迁移
  `SettingsSetup`、`AwManager` 或 `PackageOverride`。

64 位 Kernel 加 ARM32 userspace 是当前已证明可工作的组合，不是 M8A
问题。

### M8B：AArch64/multilib

只有实际证明可用的 64 位图形供体后才开始。最低供体证据是适配本平台的
AArch64 Mali/EGL/GLES/Vulkan、Gralloc、Mapper、HWC 及其闭合依赖；仓库
声明、相似 SoC 名称或通用 GSI 能启动都不算证明。

M8B 不阻塞 M8A，也不下载 H618 BSP 只为“先看看”。

## 阶段

| 阶段 | 状态 | 目标 | 退出条件 |
|---|---|---|---|
| M8.0 | COMPLETE | 建立足够的当前设备证据 | 硬件、运行时、ELF/HAL/module、图形媒体、DRM 和恢复基线足以设计 M8A |
| M8A.1 | COMPLETE | 锁定 Android 12 ATV product 参考 | source-lock、package/overlay/VINTF 差异、分区预算和 UBOX10 product 计划可用 |
| M8A.2 | ACTIVE | 构建并启动最小 ARM32 ATV product | 依次通过离线构建、核心启动、显示和最小 TV UI |
| M8A.3 | PENDING | 达到日常电视可用 | 通过本文件的轻量 candidate 标准，用户体验优于 Test8r2 或前一 M8A 基线 |
| M8B.1 | PARKED | 证明 64 位图形供体 | 实际 AArch64 产物、依赖和 UBOX 适配路径为 GO |
| M8B.2+ | PARKED | 最小 AArch64/multilib 到日常可用 | 仅在 M8B.1 GO 后定义具体 candidate |

旧 `M8.1–M8.6` 只存在于
[归档架构](../archive/m8/pre-pragmatic/ARCHITECTURE.md) 中，不再用作当前
任务编号。

### M8A.2 子阶段

| 子阶段 | 工作 | 可在刷机后定位的问题 |
|---|---|---|
| M8A.2a | 建立 ARM32 system/product/system_ext，完成可打包的离线构建 | 无 |
| M8A.2b | 启动到 init、framework/ADB | linker namespace、VINTF/HAL、SELinux denial、缺库或服务顺序 |
| M8A.2c | 恢复 HDMI 画面与 SurfaceFlinger/HWC | overlay、显示属性、图形服务协商 |
| M8A.2d | 启动 Launcher、Settings 和最小 TV UI | provision、默认 HOME、权限、TV feature/package 组合 |

发现问题时保存第一条重复 fatal、相关服务日志和本轮差异，只修一个原因再
重建。不要求刷机前证明所有运行时 namespace、SELinux 或 framework 行为。

## 硬门禁

以下条件不满足时停止刷写：

1. 官方镜像和 Test8r2 回退仍可用，PhoenixCard 恢复路径已确认。
2. 本轮没有同时改变 Kernel、Vendor、System、DTB 和 TEE。
3. M8A 不替换已工作的硬件栈，且打包、super、AVB 和目标分区容量没有明显
   破坏。
4. candidate 的基线、唯一主要变量和预期故障范围可以说清楚。
5. 不修改、复制或导出 Widevine、TEE、HDCP、keybox、设备证书或其他安全
   材料。
6. 不把多个独立高风险实验合并进同一 candidate。

建议但不作为每轮硬门禁：

- 针对新增/替换 ELF 运行 `check_elf_file.py` 或等价检查；
- 对可疑 HAL 运行基本 `checkvintf`；
- 保存 `/linkerconfig/`、活动 APEX/classpath、uses-library 和 SELinux 摘要；
- 在方便时补官方 ROM DRM 对照；
- 做更长压力测试、完整 ABI 审计、CTS/VTS 或 SELinux enforcing 收敛。

这些检查在能快速排除砖机或提升归因时执行；不能为了清单完整而无限推迟
可恢复的实机实验。

## 轻量 candidate 标准

最低日常验收：

- 3 次冷启动；
- 5–10 次重启；
- 数小时正常使用；
- Launcher 和 Settings 导航；
- 实体遥控器；
- 网络；
- 音频；
- 至少一种代表性视频播放；
- 回退路径仍可用。

满足以下条件即可晋级：

- 启动基本可靠；
- 日常电视体验可用；
- 没有明显关键回归；
- 故障容易定位或回退；
- 用户实际体验优于前一基线。

每个 candidate 不要求完整 CTS/VTS、24 小时压力、exhaustive ABI audit、
完整 SELinux enforcing、全部警告清零或生产级测试报告。首次启动失败也不是
项目失败；能从 UART/ADB 得到可归因的故障就是有效实验结果。

## 横向工作

### M8.INPUT

Test9r2 已证明 Remote v2 的 provider、mDNS、TLS 配对、uinput 和官方
Google TV iPhone 客户端可工作，但该整机 candidate 因 Play Store 回归未
晋级。M8A 需要原生 product 合同；开源 Remote Protocol v2 客户端只用于
诊断或自动化，Web/ADB remote 只作 fallback。

### M8.GMS

无 GMS 的 AOSP ATV 启动不受阻。以后按 TV Google 组件、权限、overlay、
package visibility、签名和认证边界逐项处理。MindTheGapps 仅作为组件结构
参考，不是可直接刷入 UBOX10 的方案。

### M8.DRM

Test8r2 已确认 Widevine L3、HDCP `NONE`、无 secure decoder。M8 只保留
现有安全材料，先验证播放体验；Netflix HD 不能作为 M8A 启动门禁。

社区参考与明确的“不复制内容”见
[research/COMMUNITY_REFERENCES.md](research/COMMUNITY_REFERENCES.md)。
