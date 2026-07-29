# Test9.3 用户态应用收尾

状态：`PASS / M7-COMPLETE`

日期：2026-07-29

## 目标与边界

Test9.3 从唯一稳定基线 Test8r2 出发，以 data 分区应用完成当前 32 位系统的
产品体验收尾。它不继承 Test9r2 的 leanback/Remote Service stack，也不修改
system、product、GMS、设备身份或 Wi‑Fi 驱动。

APK 只保存在被 Git 忽略的 `work/preinstall_apks/`。公共仓库只记录官方来源、
许可证、包名、版本、ABI、SHA-256、签名证书以及安装方法，不下载或重新分发
第三方二进制。

## Test8r2 前置合同

`scripts/install-userdata-apps.py` 在接触 userdata 前强制确认：

- Android SDK 31，设备 ABI 包含 `armeabi-v7a`；
- 存在 `android.hardware.type.television`；
- 不存在 `android.software.leanback` 和
  `android.software.leanback_only`；
- Projectivy、ContactsProvider 和 Play Store 存在；
- `com.google.android.tv.remote.service` 不存在；
- 默认 HOME 为
  `com.spocky.projengmenu/.ui.home.MainActivity`；
- boot 已完成，ADB 状态为 `device`。

这使脚本在误刷 Test9r1/Test9r2、错误架构或不完整基线时 fail-closed。

## 已锁定应用

权威机器可读配置为
`configs/apps/test9.3-userdata-apps.json`。

| ID | 版本 / versionCode | package | ABI | 官方来源与许可证 |
|---|---|---|---|---|
| `smarttube-beta` | 32.03 / 2393 | `org.smarttube.beta` | armeabi-v7a | [GitHub release](https://github.com/yuliskov/SmartTube/releases/tag/32.03)，MIT |
| `kodi` | 21.3 / 2103000 | `org.xbmc.kodi` | armeabi-v7a | [Kodi 21.3](https://kodi.tv/article/kodi-21-3-omega-release/)，GPL-2.0-or-later |
| `jellyfin-tv` | 0.19.9 / 190999 | `org.jellyfin.androidtv` | arm64/armv7/x86/x86_64 | [GitHub release](https://github.com/jellyfin/jellyfin-androidtv/releases/tag/v0.19.9)，GPL-2.0 |
| `moonlight` | 12.1 / 314 | `com.limelight` | arm64/armv7/x86/x86_64 | [GitHub release](https://github.com/moonlight-stream/moonlight-android/releases/tag/v12.1)，GPL-3.0 |
| `anexplorer-tv` | 6.0.5 / 60504 | `dev.dworks.apps.anexplorer` | arm64/armv7/x86/x86_64 | [TV 下载页](https://anexplorer.io/download/android-tv)，Apache-2.0 |

SmartTube 官方推荐 beta channel。32.10 已在本轮核验时出现，但 Test9.3
有意冻结已经下载、签名核验且刚发布不久的 32.03，避免在同一验收中继续
滚动版本；完成基线后再通过其内置 updater 单变量评估升级。

AnExplorer 官网当时仍把 TV 下载标为 6.0.1，而官方直链实际 APK 自报 6.0.5。
配置因此不依赖可变 latest URL，而锁定官方 `1hakr/data` 仓库 commit
`2cc09a11f320cd67845154385b1893260e5a80e0`。免费版含广告，SMB/FTP 与
部分云功能需要 Pro；它目前是遥控器/USB/APK 安装候选，不在人工体验通过前
宣告最终选型。

## 二进制校验

| ID | bytes | APK SHA-256 | signer certificate SHA-256 |
|---|---:|---|---|
| `smarttube-beta` | 25,021,715 | `0B6222CD3246235D003AF5FBE032135239D13BD81B8AEB73F508ECA6C9C3044C` | `109735AA24FE85E2E1623EBB3B1ECC4BF4263F4C6374E4411D646BFA2EDA482A` |
| `kodi` | 67,832,726 | `12D75E895649F68F217E42C2D881A94FD3177D7B9A7937825852AED545520CC8` | `F517B44B5DB5E62A6C1EC55BA47526DB7DE0D61F6BA26A7987520E293499B8D5` |
| `jellyfin-tv` | 21,950,664 | `A3F692FB51D1C59E6B6DEB074FDD8E34B90AA544A2550F45E61A267057F7361F` | `D881796ED2A67FF6EF9F676828723C6B1FA18E09388962CBA4ABC4A594A69131` |
| `moonlight` | 6,765,523 | `87012EE6949CD51F211D029EE1194D0DAA03ADC6ED3FC9448AFA92B1DC43CD9F` | `D6CE3A4DF15060FE488FE52441A549DEE4BA199B36E2CB1ED9085CCA8BFA1ACA` |
| `anexplorer-tv` | 58,913,587 | `C596F8A52D40D7C970DE84A71F29AA762B917DC00A3799A4EFC36C9E7A26A985` | `67016069E9D0DFA00AE36F8BB5AE1487B6665F317F0D44CB30227FCBCE975680` |

Jellyfin 与 SmartTube 哈希还匹配官方 GitHub release API 的 asset digest；
Kodi 匹配官方 mirror service 公布的 SHA-256。Moonlight 的旧 GitHub asset
没有 digest 字段，故同时锁定官方 asset 大小、本地 SHA-256 与上游签名证书。

## 可重复安装

需要 Android SDK build-tools 中的 `aapt`/`apksigner`、Java 和 ADB。脚本会
优先发现标准 `ANDROID_SDK_ROOT`/`ANDROID_HOME`，也兼容当前本地工具链；
可用 `--aapt`、`--apksigner`、`--java-home` 和 `--adb` 显式指定。

```powershell
# 查看 bundle
python .\scripts\install-userdata-apps.py --list

# 下载缺失的锁定官方 APK 并核验，不连接电视
python .\scripts\install-userdata-apps.py `
  --download-missing `
  --verify-only

# 只核验本地 APK，不连接电视
python .\scripts\install-userdata-apps.py --verify-only

# 核验 APK 与 Test8r2 合同，但不安装
python .\scripts\install-userdata-apps.py --dry-run `
  --device 192.168.1.5:7896

# 安装默认五项并复核已安装版本
python .\scripts\install-userdata-apps.py `
  --device 192.168.1.5:7896 `
  --report .\work\test9.3-userdata-install.json

# 单独核验/安装/启动某项
python .\scripts\install-userdata-apps.py `
  --app anexplorer-tv `
  --launch anexplorer-tv
```

刷机后的推荐入口是：

```powershell
python .\scripts\install-userdata-apps.py `
  --guided-after-flash `
  --device "<电视IP>:7896"
```

该模式自动取得缺失的五项官方 APK、完成来源锁和 Test8r2 合同校验，打开
AirReceiverLite 的 Play 页面并等待用户登录、跳过付款方式、安装 Lite，
随后统一安装五项应用。现有 APK 永不被下载器覆盖。

默认重复运行是幂等的：版本完全相同时返回 `already-current`。若设备已有更高
versionCode，脚本拒绝静默降级；只有明确使用 `--allow-downgrade` 才传递
`adb install -d`。

## 2026-07-29 自动化结果

1. 五份 APK 的大小、SHA-256、package、versionCode/versionName、
   min/target SDK、native ABI、launch activity 与签名证书全部通过。
2. Test8r2 实机 dry-run 合同通过。
3. 五项首次 `adb install -r` 均返回 `Success`，设备端 `base.apk` SHA-256
   与本地来源锁逐项一致。
4. 五项均声明可解析的 `LEANBACK_LAUNCHER` activity，Projectivy 可枚举。
5. SmartTube 进入 BrowseActivity；Kodi、Jellyfin TV、Moonlight 与
   AnExplorer 均进入各自主 activity，未观察到 `AndroidRuntime` crash。
6. 实际执行系统重启；重启后五项仍在，安装器第二次运行五项全部返回
   `already-current`，五项再次启动通过。
7. 重启后 Projectivy 仍为唯一 HOME；5 GHz Wi‑Fi 6 已连接，公网 ping
   成功；蓝牙为 `ON`、`Bluetooth crashed 0 times`；Play Store 29.2.15
   仍存在；leanback 与 Google Remote Service 未被引入。

自动化门当时结论为 `PASS`，尚不能替代用户可见界面、遥控手感、真实媒体、
USB 与 AirPlay 人工验收；这些后续结果已记录在本页“人工验收清单”和
“最终验收与有限豁免”中，Test9.3 最终状态为 `PASS / M7-COMPLETE`。

## AirPlay 选型门

首选流程固定为：

1. 从 [Google Play 的 AirReceiverLite](https://play.google.com/store/apps/details?id=com.softmedia.receiver.lite)
   安装免费试用版；
2. 用当前 iPhone 验证发现、照片/视频、屏幕镜像、声音同步、后台运行与
   一次重启；
3. 只有通过且用户接受时，再由用户自己的 Play 账号购买
   [AirReceiver](https://play.google.com/store/apps/details?id=com.softmedia.receiver)。

选择原因：AirReceiver 官方说明面向 Android TV/Box、可后台运行和开机启动；
完整版是一次性付费且 Play 数据声明为不收集、不共享。AirScreen 协议覆盖更广，
但免费入口含广告和内购，和“简洁电视体验”冲突更大，故仅作为 AirReceiver
实测失败后的第二候选。

付费 APK 不从设备导出、不放入 `work/`、不写入安装 bundle，也不由项目再分发。

### 2026-07-29 AirReceiverLite 实测

- 用户从 Play Store 安装并首次启动
  `com.softmedia.receiver.lite` 5.1.7（versionCode `2020164765`，
  minSdk 21、targetSdk 35）；Play 下发 `base`、`armeabi_v7a`、`en` 与
  `xhdpi` 四个 split，应用同时声明 Launcher 与 Leanback Launcher。
- 本次已安装 payload 的 base SHA-256 为
  `C1EA11787692B16D5BB0E9BBBA05EB31052A0976B95F7B6FB3567979341B84FE`，
  signer certificate SHA-256 为
  `54EAA65CB223EE1EA69B049480A1C3F186E3B3700AE8B0019879EAE7E7DA05A4`。
  它是 Play 管理的专有 split 应用，不加入 Test9.3 离线安装 bundle。
- 授予“显示在其他应用上层”后，`AirReceiverService` 以前台服务运行；
  设备监听 mDNS 5353、AirPlay 7000/7100，并以
  `Pixel3-5[AirPlay]` 发布 `_airplay._tcp.local`。主机从
  `192.168.1.5:5353` 收到有效 PTR/TXT 响应，7000/7100 TCP 均可达。
- iPhone 实机可发现并连接；设备进入 `AirMirrorActivity`，收到
  `498x1080` 镜像。音频申请 media focus、启动 OpenSL ES player 并走
  HDMI 44.1 kHz 双声道输出；用户确认画面连续、声音和同步均无问题。
- 真实重启后 package 与 overlay 权限仍在，但 service、7000/7100 和
  AirPlay 广播没有自动恢复。随后 Lite 自身弹窗明确说明：试用版必须保持
  前台，且部分功能每次会话限 5 分钟。因此这不是 Test8r2 的启动回归，
  而是试用版产品限制。

结论为 `AIRPLAY-TRIAL-PASS`：协议、发现和实际音视频性能已证明可行，
无需转测 AirScreen。用户决定不把购买完整版纳入当前项目；M7 接受 Lite
作为需要前台启动、部分功能每次会话限 5 分钟的按需 AirPlay 能力，不承诺
后台或开机自启。项目不代购、不导出或再分发付费 APK。

## 人工验收清单

- [x] Projectivy 中五个新图标可见，滚动和打开没有明显焦点错误。
- [x] 五项均可用方向、OK、Back、Home 完成基础导航，不强制鼠标模式。
- [x] SmartTube 可浏览并播放一段 1080p 内容，声音与返回行为正常。
- [x] Kodi 可进入界面并完成遥控导航；本轮没有本地媒体资源，播放项按下述
  有限豁免记录。
- [x] Jellyfin TV 可进入服务器连接流程；本轮没有 Jellyfin 服务器，不要求
  伪造端到端播放结果。
- [x] Moonlight 可发现并可手动添加 Sunshine；本轮没有可用串流主机，串流与
  控制器项按有限豁免记录。
- [x] AnExplorer 可授予存储权限、浏览内置存储/USB，并从本地选择 APK；
  当前遥控与焦点体验可接受。
- [x] AirReceiverLite 可由 iPhone 发现，镜像、音频与同步测试通过。
- [x] 已执行 Lite 重启门并确认其前台/五分钟限制；该限制属于试用版设计。
- [x] 用户决定不把完整版购买与后台/开机门纳入 M7；付费 APK 不进入项目资产。
- [x] HDMI 音视频、红外/蓝牙实体遥控、Settings、Wi‑Fi 和蓝牙没有人工可见回归。

## 最终验收与有限豁免

2026-07-29，用户完成上述实体遥控、SmartTube 1080p、AnExplorer 内置存储/
USB/APK 和 AirReceiverLite iPhone 音视频测试。Kodi 缺本地媒体、
Jellyfin 缺服务器、Moonlight 缺可用串流主机，因此三者只验证到应用入口、
遥控导航和连接/发现边界，不虚构端到端播放。

这些豁免不阻塞 M7，理由是：

1. 三个未做端到端播放的项目均由缺少外部测试资源造成，不是已观察到的故障；
2. SmartTube 已覆盖真实 1080p 网络媒体与 HDMI 音频；
3. AirReceiverLite 已独立覆盖实时网络视频、音频和同步；
4. AnExplorer 已覆盖内置存储、USB 和本地 APK 路径；
5. 五项应用的安装、启动、重启持久性、D-pad/Back/Home 与系统回归门均已通过。

因此 Test9.3 记为 `PASS`，M7 记为 `COMPLETE`。未来若用户具备 Kodi 媒体、
Jellyfin 服务器或 Sunshine 主机，可作为非阻塞扩展复测，不重新开启 M7。

## 出口

- 最终结果：Test9.3 为 `PASS`，M7 已收束，进入 M8.0/M8A.1。
- AnExplorer 仅因广告/焦点体验失败：保持其配置为历史候选，改测官方 X-plore，
  不更改固件。
- AirReceiverLite 协议/性能已通过；用户不把完整版购买纳入项目，
  不把 Lite 的前台/五分钟限制误判为固件故障。
- 若完整版仍发生协议或性能失败：记录 iPhone/iOS、媒体类型和日志，再单变量
  评估 AirScreen；不从 APK 镜像站取所谓 premium/cracked 包。
- 任一应用导致系统回归：卸载对应 data package，Test8r2 固件本身无需重刷。
