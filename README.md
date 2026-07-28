# UBOX10 ROM Customization

面向 UnblockTech UBOX10 / I12 Pro Max（Allwinner H616、Android 12）的可恢复固件改造项目。当前目标是先完成稳定、简洁、遥控器友好的 32 位电视体验，同时用只读审计为 AArch64 与真正 AOSP Android TV 迁移建立证据。

## 当前状态

- **稳定基线：Test8r2。** Projectivy、英语界面、遥控、Settings、Wi‑Fi 连接、蓝牙和 ContactsProvider/PBAP 回归已通过；蓝牙为 `state: ON`、`Bluetooth crashed 0 times`。
- **当前实验：Test9r1。** 从 Test8r2 单变量加入 Android 12 AOSP remoteprovider 共享库、framework RRO、leanback、特权权限白名单和本地官方原签名 Android TV Remote Service；完整离线验证通过，等待真机发现、配对、遥控和文字输入验收。
- **Test9w1 已退役。** 真机确认 `ant_div=N`，但 5 GHz 本来稳定、目标 2.4 GHz 仍未出现，未证明一字节驱动改动带来实质改善；配置保留用于追溯，镜像不再长期保存或作为后续基线。
- **Play Store 当前只作为安装基础设施。** 可登录、搜索和安装 Jellyfin TV，但界面手机化、首页失败且没有可见的 Play Protect certification 项。Test9a/Test9b 证明单独加入 Leanback feature 不能完成 TV 化。
- **M8 已进入规划。** 当前是 64 位 Kernel 加纯 32 位 Android 用户空间。M8 首先做 ELF/HAL/VINTF/图形/媒体/DRM 只读盘点；首个 Go/No-Go 是兼容 H616/Mali-G31 的 64 位 EGL/Gralloc/Mapper/HWC。官方 Google TV iPhone 遥控/文字输入已加入 M8 输入子系统正式验收，不开发 UBOX Input。
- **Netflix 纳入长期正式验收。** 先建立原厂/Test8r2 的 Widevine、TEE/OEMCrypto、secure codec、HDCP 和实际播放基线；不复制密钥、不伪造认证或 ESN。

## 本地镜像保留集

| 角色 | 文件 | SHA-256 |
|---|---|---|
| 官方恢复与唯一源原件 | `x12-1024.img` | `371A653604618E8B78786F279EA6F64E5D1028B430C9B41F330B08456A264065` |
| 稳定基线 | `out/candidates/test8r2-restore-contacts-provider-r1/x12-test8r2-restore-contacts-provider.img` | `6A52F3388E9ABF6AFA8A701CFD7198FE6C0090F16531F6E3BD3949E760892EC8` |
| 当前实验 | `out/candidates/test9r1-android-tv-remote-service-r1/x12-test9r1-android-tv-remote-service.img` | `38A0C232750ECD433B2783E0CFBFFC48C17071226EE2AEC978BE5AC6C12F6E33` |

其他候选和逻辑分区镜像不长期保留；配置、脚本、哈希、生成方法和 Git 历史足以复现。详见 `docs/STORAGE_AND_REPRODUCTION.md`。

## 当前工作顺序

1. 刷入 Test9r1，验证 remoteprovider、官方 Google TV iPhone 应用发现/配对、遥控和文字输入；失败立即刷回 Test8r2。
2. 检查 Test9r1 对 Play Store、Projectivy、实体遥控、Wi‑Fi 和蓝牙的交叉回归；通过前 Test8r2 仍是唯一稳定基线。
3. 完成 SmartTube、Kodi、Jellyfin、Moonlight、AirPlay 和现代文件管理器的用户态配置。
4. 并行推进 M8.0 只读 inventory；不在图形和 DRM 基线明确前制作 64 位候选。
5. 锁定并原样验证 BPI H618 Android 12 BSP，再决定它是 `GO`、`PARTIAL GO` 或 `NO-GO` 供体。
6. 建立 Android 12 AOSP ATV 参考构建，之后才进入分层的最小 64 位启动实验。

## 构建复现

清理后先从官方原件恢复并验证构建输入：

```powershell
python .\scripts\prepare-candidate-inputs.py
python .\scripts\prepare-tv-remote-experiment.py
```

再按受版本控制的候选配置构建：

```powershell
python .\scripts\build-candidate-firmware.py `
  --config .\configs\candidates\test9r1-android-tv-remote-service.json
```

第一条恢复官方逻辑分区缓存；第二条验证用户本地提供的 Google 原签名 donor，并从锁定 AOSP 源码构建 remoteprovider/RRO。构建器只在 ext4 语义、e2fsck、完整 AVB、super、IMAGEWTY 和单元测试全部通过后发布候选。第三方/Google APK 不提交 Git、公开镜像或再分发，必须按配置中的版本、签名和 SHA-256 放入已忽略的 `work/`。

## 文档入口

- 总索引：`docs/README.md`
- 当前刷测：`docs/RUNBOOK.md`
- Test9r1 设计与验收：`docs/experiments/TEST9R1_ANDROID_TV_REMOTE_SERVICE.md`
- 路线与里程碑：`docs/ROADMAP.md`、`docs/MILESTONES.md`
- M8 架构计划：`docs/architecture/M8_ARM64_AOSP_TV_MIGRATION.md`
- M8 研究区：`docs/research/m8/README.md`
- 构建环境：`docs/BUILD_ENVIRONMENT.md`
- 存储与复现：`docs/STORAGE_AND_REPRODUCTION.md`
- 事实、决策、风险：`docs/DISCOVERIES.md`、`docs/DECISIONS.md`、`docs/RISK_REGISTER.md`
- 历史归档：`docs/archive/README.md`

## 安全边界

- 官方 `x12-1024.img` 永不覆盖或删除，候选使用新文件名。
- 不修改 eFuse、OTP、BootROM、唯一密钥或未知安全分区。
- 不直接刷其他 H616/H618 板型的完整镜像、bootloader、DTB/DTBO、TEE 或分区表。
- PhoenixCard 可能清除 userdata/metadata；刷写前备份用户数据并确认目标 TF 卡。
- 大型 BSP/AOSP 下载与构建必须先锁定来源、commit、空间和退出条件，并放在 WSL/Linux 文件系统或独立构建盘。
