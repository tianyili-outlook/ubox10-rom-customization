# Test8r2 → AOSP ATV package 差异

| 处理 | 组件 | 决策 |
|---|---|---|
| 已有，沿用 AOSP 源码 | `TvProvider`、`TvSettings`、`SystemUI`、`Bluetooth`、`InputDevices` 及核心网络组件 | 纳入 M8A |
| 新增 | `TvFrameworkPackageStubs` | 使用 TV 低优先级 intent stubs，替代通用 `FrameworkPackageStubs` |
| 新增 | `com.android.media.tv.remoteprovider` | 作为 AOSP shared library；receiver/RRO 留给 M8.INPUT |
| 保留产品选择 | Projectivy、LatinIME、ContactsProvider | 分别承担 HOME、输入法和蓝牙 PBAP 依赖 |
| 首版保留 | `AwTvProvision` | 当前无 `tmp_provision*` 或 Device Owner，但其 DEX 含可选 DPC provisioning；首版不与 AOSP `TvProvision` 共存 |
| 不采用 GSI 样例 | `TvSampleLeanbackLauncher`、`LeanbackIME` | 已有正式 HOME/IME |
| 继续精简 | `BasicDreams`、`CalendarProvider`、`PrintSpooler`、`SharedStorageBackup`、`ManagedProvisioning` | 不因上游默认列表自动恢复；依赖证明需要时再加 |
| 不迁移 | `SettingsSetup` | 只在 PRE_BOOT 写入 `icon_blacklist=rotate` 后自禁用，ATV overlay 已覆盖旋转/UI |
| 不迁移 | `AwManager` | 依赖 Allwinner 私有 `android.aw.BackgroundManager`，不是硬件服务 |
| 不迁移 | `PackageOverride` | 无代码、无组件，只有应用名称资源 |

Google/GMS、TV Play Store 和 Google Remote Service 不属于 M8A 基础产品。
