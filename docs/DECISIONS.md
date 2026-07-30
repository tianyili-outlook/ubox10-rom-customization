# M8 现行决策

这里仅记录仍然影响 M8 的长期决策。当前状态和任务分别以
[m8/STATUS.md](m8/STATUS.md) 与 [m8/TODO.md](m8/TODO.md) 为准；M7 和重构前
决策已归档到 [archive/m8/pre-pragmatic/DECISIONS.md](archive/m8/pre-pragmatic/DECISIONS.md)。

- **体验优先**：排序固定为 usable TV experience、日常稳定、容易回退、
  故障可理解、形式完整。
- **快速实机迭代**：完成恢复、基线、分区和单变量检查后即可构建/刷测；
  exhaustive audit、CTS/VTS、完整 ABI 证明或零警告不阻塞可恢复实验。
- **Test8r2 不变**：它是当前稳定日常基线和 M8 默认回退点；官方
  `x12-1024.img` 是最终恢复源。
- **一次一个高风险层**：不在同一 candidate 同时改变 Kernel、Vendor、
  System、DTB、TEE，也不合并多个独立高风险实验。
- **M8A 先完成 ARM32 ATV product**：保留当前 boot、64 位 Kernel、vendor、
  vendor_dlkm、DTB/DTBO、TEE 和 32 位 Vendor ABI。
- **只借用 AOSP ATV 产品层**：以锁定的 Android 12
  `device/google/atv` 为参考，不复制 emulator、goldfish 或 generic_x86
  硬件层。
- **首轮保留 AwTvProvision**：日常 UI 可用后再单变量替换；不迁移
  SettingsSetup、AwManager 或 PackageOverride。
- **M8B 等待真实供体**：只有 AArch64 Mali/EGL/GLES/Vulkan、Gralloc、
  Mapper、HWC 及依赖产物通过后才进入 AArch64/multilib。相似 SoC、
  build flag 或 GSI 启动不算证明。
- **针对性检查**：`check_elf_file.py`、`checkvintf`、linkerconfig、APEX、
  classpath 和 SELinux 只在相关变更或故障中使用，不设全树形式门禁。
- **现有兼容性快照足够**：Test8r2 的 linkerconfig、APEX、classpath、
  uses-library 和 VINTF 结构已保存；设备缺少 `checkvintf` 不阻塞 M8A，
  构建树可用后只检查实际变更。
- **轻量 candidate 验收**：3 次冷启动、5–10 次重启、数小时使用，以及
  Launcher/Settings、遥控、网络、音频、视频和回退；用户体验优于前一基线
  即可晋级。
- **安全材料只保留不移植**：不修改、复制或导出 Widevine、TEE、HDCP、
  keybox、设备证书或其他设备安全材料。
- **GMS 不阻塞无 GMS ATV 启动**：MindTheGapps TV 只借鉴组件和 overlay
  组织，不复制专有包或认证结论。
- **Remote v2 原生整合**：Test9r2 证据可复用；开源客户端用于诊断，
  Legvan Web/ADB remote 仅作 fallback，不替代电视端 receiver 和官方 iPhone
  体验验收。
- **DRM 按实际播放能力描述**：当前只确认 Widevine L3、HDCP `NONE` 和无
  secure decoder；不把 Netflix HD 当作 M8A 启动门禁，也不为 DRM 对照单独
  刷回官方 ROM。
- **大型源码放独立 ext4 卷**：当前磁盘不满足 AOSP 构建空间，不向现有
  C/D 盘或仓库工作树同步完整源码。
- **文档单一事实来源**：架构、状态、TODO、文件地图和 candidate 索引各一份；
  archive 不维护现行状态。
