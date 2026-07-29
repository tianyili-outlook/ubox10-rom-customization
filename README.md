# UBOX10 ROM Customization

面向 UnblockTech UBOX10 / I12 Pro Max（Allwinner H616、Android 12）的可恢复固件改造项目。当前目标是先完成稳定、简洁、遥控器友好的 32 位电视体验，同时用只读审计为 AArch64 与真正 AOSP Android TV 迁移建立证据。

## 当前状态

- **稳定基线：Test8r2。** Projectivy、英语界面、遥控、Settings、Wi‑Fi 连接、蓝牙和 ContactsProvider/PBAP 回归已通过；蓝牙为 `state: ON`、`Bluetooth crashed 0 times`。
- **Test9r2 技术探针已完成。** 修正后的 system_ext RRO、provider、6466/6467、mDNS、官方 Google TV iPhone 配对、遥控和文字输入均已通过；首次启动失败的确定性根因是缺少 `BLUETOOTH_CONNECT` 默认运行时授权，仅临时授予该权限后完整链路工作。Play Store 仍进入 `AccessRestrictedActivity`，所以候选总体为 `PARTIAL`、不晋级。
- **Test9w1 已退役。** 真机确认 `ant_div=N`，但 5 GHz 本来稳定、目标 2.4 GHz 仍未出现，未证明一字节驱动改动带来实质改善；配置保留用于追溯，镜像不再长期保存或作为后续基线。
- **Play Store 当前只作为 Test8r2 的安装基础设施。** 可登录、搜索和安装 Jellyfin TV，但界面手机化、首页失败且没有可见的 Play Protect certification 项；加入 Leanback 的 Test9a/Test9b/Test9r1/Test9r2 均进入不兼容受限页。
- **M7 已完成并具备可复现发布入口。** Test8r2 是固件基线；SmartTube
  32.03、Kodi 21.3、Jellyfin TV 0.19.9、Moonlight 12.1 和 AnExplorer TV
  6.0.5 已完成来源锁、统一安装、重启与实体遥控验收。SmartTube 1080p、
  AnExplorer USB/APK 和 AirReceiverLite iPhone 音视频通过；Kodi、
  Jellyfin、Moonlight 的外部资源缺口以有限豁免记录。用户接受 Lite
  必须前台、部分功能每次限 5 分钟的范围，不购买完整版。
- **M8 已重排为先产品、后架构。** 当前是 64 位 Kernel 加纯 32 位 Android 用户空间。M8.0 先做共享只读盘点；M8A 保持现有 Kernel/vendor/32 位 ABI，建立真正 Android 12 AOSP ATV product；M8B 才迁移 AArch64/multilib，兼容 H616/Mali-G31 的 64 位 EGL/Gralloc/Mapper/HWC 是 M8B 第一 Go/No-Go。Test9r2 的 Remote v2 成功证据、最小 CONNECT 权限和 Play/GMS 缺口由 M8.INPUT/M8.GMS 继承；不开发 UBOX Input。
- **Netflix 纳入长期正式验收。** 先建立原厂/Test8r2 的 Widevine、TEE/OEMCrypto、secure codec、HDCP 和实际播放基线；不复制密钥、不伪造认证或 ESN。

## 本地镜像保留集

| 角色 | 文件 | SHA-256 |
|---|---|---|
| 官方恢复与唯一源原件 | `x12-1024.img` | `371A653604618E8B78786F279EA6F64E5D1028B430C9B41F330B08456A264065` |
| 稳定基线 | `out/candidates/test8r2-restore-contacts-provider-r1/x12-test8r2-restore-contacts-provider.img` | `6A52F3388E9ABF6AFA8A701CFD7198FE6C0090F16531F6E3BD3949E760892EC8` |
| 已完成技术探针（不晋级） | `out/candidates/test9r2-android-tv-remote-service-rro-path-r1/x12-test9r2-android-tv-remote-service-rro-path.img` | `27B54FB83E96D3863FAE2EF2718E8EC9ADDD863E5ED123082D5E6C8CA6FFFD52` |

其他候选固件和候选中间镜像不长期保留。四个 SHA-256 锁定的官方逻辑分区构建缓存长期保留，避免每轮重新提取；配置、脚本、哈希、生成方法和 Git 历史仍承担复现。详见 `docs/STORAGE_AND_REPRODUCTION.md`。

## M7 快速复现

完整的镜像校验、重建、PhoenixCard Product 刷机、首次启动和故障定位见
`docs/M7_RELEASE_GUIDE.md`。刷入 Test8r2、连接 Wi‑Fi 并记下电视 IP 后，
从仓库根目录运行：

```powershell
python .\scripts\install-userdata-apps.py `
  --guided-after-flash `
  --device "<电视IP>:7896"
```

脚本会下载并严格校验缺失的五项官方 APK，验证 Test8r2 合同，打开
AirReceiverLite 的 Play Store 页面；用户登录、跳过付款方式并安装 Lite
后回到终端按 Enter，脚本再统一安装其余应用。机器可读发布清单位于
`configs/releases/m7.json`。

## 后续工作顺序

1. M7 冻结；新功能、Play Store/GMS、官方手机遥控产品化和 64 位系统进入 M8。
2. 锁定 Android 12 `aosp_tv_arm` 参考并形成 M8A 产品差异。
3. 先以 M8A 建立 ARM32 真 ATV product，在 M8.INPUT/M8.GMS 中原生复现
   已证明可行的官方手机遥控链；再原样验证 BPI H618 供体并决定 M8B
   是否可进入 AArch64/multilib。

## 固件重建

清理后先从官方原件恢复并验证构建输入：

```powershell
python .\scripts\prepare-candidate-inputs.py
```

再按 M7 锁定的候选配置构建：

```powershell
python .\scripts\build-candidate-firmware.py `
  --config .\configs\candidates\test8r2-restore-contacts-provider.json
```

第一条仅在官方逻辑分区缓存缺失、损坏或需要审计时运行；四份锁定缓存长期
保留，不能为常规构建反复删除。构建器只在 ext4 语义、e2fsck、完整 AVB、
super、IMAGEWTY 和单元测试全部通过后发布候选。Projectivy 及用户态第三方
APK 不提交 Git 或公开镜像；其官方来源和完整性约束由配置锁定。

## 文档入口

- 总索引：`docs/README.md`
- M7 发布与复现：`docs/M7_RELEASE_GUIDE.md`
- 当前运行手册：`docs/RUNBOOK.md`
- M7 完成报告与历史实验：`docs/archive/m7/M7_COMPLETION_REPORT.md`
- 路线与里程碑：`docs/ROADMAP.md`、`docs/MILESTONES.md`
- M8 架构计划：`docs/architecture/M8_ARM64_AOSP_TV_MIGRATION.md`
- M8 研究区：`docs/research/m8/README.md`
- TV GMS/Remote 参考项目与路线门：`docs/research/tv-gms-remote/README.md`
- Test9r2 真机证据与收束决定：`docs/research/tv-gms-remote/test9r2-runtime-report.md`、`docs/research/tv-gms-remote/route-decision.md`
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
