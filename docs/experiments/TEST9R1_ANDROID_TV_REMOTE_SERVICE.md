# Test9r1：Android TV Remote Service 移植实验

状态：**离线构建与完整性验证通过，等待真机刷测。**

目标是在不开发 UBOX Input、不开放通用网络输入端口的前提下，让 iPhone
官方 Google TV 应用能够发现、配对和控制 UBOX10，并在电视文本框中输入
账号、密码和普通文字。

## 1. 基线与变量

- 唯一基线：Test8r2。
- Test9w1 不参与构建；`vendor_dlkm` 与官方/Test8r2 保持完全一致。
- Test9r1 只增加 Android TV Remote 所需的 system 组件。
- 不修改 Kernel、`services.jar`、Wi‑Fi/蓝牙驱动、设备身份、GMS 或 Play
  Store。
- 不加入 `android.software.leanback_only`，避免重演 Test9b 的额外变量。
- 不开发或维护 UBOX Input；蓝牙键盘只保留为人工回退，不是项目方案。

## 2. 为什么普通安装不可行

真机 Test9w1/Android 12 已有 framework 端：

- `com.android.server.tv.TvRemoteService`
- `TvRemoteProviderWatcher`
- `TvUinputBridge`
- `android.media.tv.ITvRemoteProvider`
- `android.media.tv.ITvRemoteServiceInput`

但当前产品缺少：

1. `android.software.leanback` feature；
2. `com.android.media.tv.remoteprovider` 运行时共享库及声明；
3. 非空的 `android:string/config_tvRemoteServicePackage`；
4. Android TV Remote Service 接收端 APK；
5. `ro.control_privapp_permissions=enforce` 所要求的特权权限白名单。

对官方原签名 APK 执行普通 data-app 安装，Package Manager 已实测拒绝：

```text
INSTALL_FAILED_MISSING_SHARED_LIBRARY:
Package com.google.android.tv.remote.service requires unavailable shared
library com.android.media.tv.remoteprovider
```

因此这不是“再找一个兼容 APK”能解决的问题，而是缺少 Android TV product
层的 system 集成。

## 3. 锁定输入

Android TV Remote Service donor 只在本地 `work/` 使用，不进入 Git、不随
固件项目重新分发：

| 字段 | 锁定值 |
|---|---|
| package | `com.google.android.tv.remote.service` |
| version | `5.2.473254133` |
| versionCode | `95855272` |
| min/target SDK | 24 / 33 |
| APK SHA-256 | `9D1B5C5EF0E293F8ED17C26E8F62DE661ACC7F2DDC2AAA8EF23E4CABE430B973` |
| 签名证书 SHA-256 | `456EDBC33222D20FF158D42E9FAB0252DBE0514D6E1C39588D6B1982CC189137` |
| 签名 DN | `CN=atv_remote_service, OU=Android, O=Google Inc., L=Mountain View, ST=California, C=US` |

共享库从 Apache-2.0 的 AOSP `android-12.0.0_r1` 源码本地构建：

| 输入 | SHA-256 |
|---|---|
| `media/lib/tvremote` archive | `DE5B0404ADDC23C1B373810E448C381724D50D16BC2AE4816415998B701B51C6` |
| `media/java/android/media/tv` archive | `CE355B15F1C3DD11B92AAD35AE03FE229AD01C67C3A4C56E13F53FE534A1465C` |

脚本会验证 donor 的 APK 哈希、Google 证书、package/version，以及两个 AOSP
archive 的哈希。Google APK 不由脚本下载。

## 4. system 集成

| 目标路径 | 用途 |
|---|---|
| `/system/priv-app/AndroidTvRemoteService/AndroidTvRemoteService.apk` | 官方原签名接收端 |
| `/system/etc/permissions/android.software.leanback.xml` | 让 SystemServer 启动 TV remote framework service，并满足 APK required feature |
| `/system/framework/com.android.media.tv.remoteprovider.jar` | 从 Android 12 AOSP 构建的运行时 API 实现 |
| `/system/etc/permissions/com.android.media.tv.remoteprovider.xml` | 注册 required shared library |
| `/system/etc/permissions/privapp-permissions-com.google.android.tv.remote.service.xml` | 仅授予 Android 12 上具有 `privileged` protection bit 的请求权限 |
| `/system/overlay/UBOX10TvRemoteConfigOverlay.apk` | 将 `config_tvRemoteServicePackage` 指向接收端 package |

`android.permission.INJECT_EVENTS` 是纯 signature 权限，Google APK 与本机
platform key 不同，不能用 privapp allowlist 伪造授予。它被有意排除；输入
事件必须走 framework 的 `TvRemoteProvider`/uinput 桥。

RRO 只覆盖一个 framework string。它使用仓库已有测试私钥签名，证书公开
部分位于 `assets/tv_remote_overlay/`。该测试签名不用于 Google APK。

## 5. 复现命令

从官方 AOSP Gitiles 取得两个锁定 archive：

```powershell
$remoteWork = ".\work\remote-service-migration"
Invoke-WebRequest `
  "https://android.googlesource.com/platform/frameworks/base/+archive/refs/tags/android-12.0.0_r1/media/lib/tvremote.tar.gz" `
  -OutFile "$remoteWork\aosp-tvremote-android-12.0.0_r1.tar.gz"
Invoke-WebRequest `
  "https://android.googlesource.com/platform/frameworks/base/+archive/refs/tags/android-12.0.0_r1/media/java/android/media/tv.tar.gz" `
  -OutFile "$remoteWork\aosp-media-tv-android-12.0.0_r1.tar.gz"
```

当前工具包的固定下载入口：

- Temurin 17.0.19+10：
  <https://github.com/adoptium/temurin17-binaries/releases/tag/jdk-17.0.19%2B10>
- Android API 31：
  <https://dl.google.com/android/repository/platform-31_r01.zip>
- Android Build Tools 31：
  <https://dl.google.com/android/repository/build-tools_r31-windows.zip>

解压目录可使用脚本默认布局，也可用 `--jdk`、`--platform`、
`--build-tools` 显式指定。工具包哈希见 `docs/BUILD_ENVIRONMENT.md`。

将匹配上表哈希、由用户合法取得的 donor 放到脚本默认路径，准备本地依赖：

```powershell
python .\scripts\prepare-tv-remote-experiment.py
```

预期生成：

| 本地忽略文件 | SHA-256 |
|---|---|
| `work/preinstall_apks/AndroidTvRemoteService-5.2.473254133.apk` | `9D1B5C5EF0E293F8ED17C26E8F62DE661ACC7F2DDC2AAA8EF23E4CABE430B973` |
| `work/system_injections/com.android.media.tv.remoteprovider.jar` | `F5D12973FBD264097C14922D121FA5EA68330994A340CDC55410509F5EA1C523` |
| `work/system_injections/UBOX10TvRemoteConfigOverlay.apk` | `D6930D23D4C9BCFA4A6BC0B7892A871E55E9D3ADD2E512A2BCCEFE256C2EC0E9` |

恢复官方逻辑分区缓存并构建：

```powershell
python .\scripts\prepare-candidate-inputs.py
python .\scripts\build-candidate-firmware.py `
  --config .\configs\candidates\test9r1-android-tv-remote-service.json
```

## 6. 已完成的离线结果

| 项目 | 结果 |
|---|---|
| 候选 | `x12-test9r1-android-tv-remote-service.img` |
| 大小 | 2,005,946,368 bytes |
| SHA-256 | `38A0C232750ECD433B2783E0CFBFFC48C17071226EE2AEC978BE5AC6C12F6E33` |
| system 语义 | 348 个既定删除路径；10 个预期新增路径；共同普通文件仅 `build.prop` 改变 |
| vendor_dlkm | 路径/内容与官方输入相同；FEC 保持官方状态 |
| ext4/e2fsck | PASS |
| AVB 完整链 | PASS |
| dynamic super | PASS |
| IMAGEWTY | PASS |
| 单元测试 | PASS，24 项运行、3 项预期 fixture skip |

该结果只证明镜像结构与集成变量准确，不证明服务能在真机启动、被 iPhone
发现或完成文字输入。

## 7. 真机验收

PhoenixCard 可能清除 userdata/metadata。刷写前确认 Test8r2 恢复镜像存在并
核对 Test9r1 SHA-256。首次启动联网后执行：

```powershell
$adb = ".\tools\platform-tools\adb.exe"
& $adb connect 192.168.1.5:7896

& $adb shell pm list features |
  Select-String "android.hardware.type.television|android.software.leanback"

& $adb shell pm list libraries |
  Select-String "com.android.media.tv.remoteprovider"

& $adb shell pm path com.google.android.tv.remote.service
& $adb shell cmd overlay list |
  Select-String "com.ubox10.overlay.tvremote"
& $adb shell cmd overlay lookup `
  android android:string/config_tvRemoteServicePackage

& $adb shell dumpsys package com.google.android.tv.remote.service |
  Select-String "versionName=|versionCode=|TV_VIRTUAL_REMOTE_CONTROLLER|INJECT_EVENTS|granted="

& $adb shell ss -lntup |
  Select-String "6466|6467"

& $adb shell logcat -d -v threadtime |
  Select-String "TvRemoteService|TvRemoteProvider|AtvRemote|remote.service|privapp"
```

然后在同一 Wi‑Fi 的 iPhone 官方 Google TV 应用中：

1. 发现电视并显示正确的可识别名称；
2. 用电视上的配对码完成授权；
3. 验证方向、OK、Back、Home；
4. 在搜索、普通账号、密码和 Unicode 文本框验证键盘输入；
5. 重启电视后再次发现/配对或恢复既有配对；
6. 确认实体遥控、Wi‑Fi、蓝牙、Projectivy 和 Settings 无回归。

还必须检查 Play Store。加入 leanback 曾在 Test9a 触发版本不兼容；若
Test9r1 的手机遥控成功但 Play Store 失效，实验可以记录为 remote 技术
成功，但候选不能晋级为日常基线。

## 8. 分层判定与回退

- feature/library 缺失：Package Manager 启动期解析失败。
- overlay lookup 仍为空：RRO 未安装、未启用或不允许覆盖。
- package 不存在：required library、APK 签名/解析或 privapp enforcement
  失败。
- package 存在但无发现：检查 provider watcher、mDNS、监听端口、运行时网络
  与蓝牙权限。
- 能配对但不能控制：检查 `TV_VIRTUAL_REMOTE_CONTROLLER`、provider bind、
  uinput bridge；不得用伪授予 `INJECT_EVENTS` 绕过。
- 出现 boot、Play Store、网络、蓝牙或输入回归：停止扩大变量并刷回
  Test8r2。

## 9. M8 继承目标

Test9r1 是 32 位旧系统上的兼容性探针，不替代 M8 的源码级 ATV product。
M8 必须把以下项目作为输入子系统的正式验收项：

1. 从锁定 Android 12 AOSP 源码构建 remoteprovider API；
2. 由 product 配置原生声明 leanback、共享库、provider package 和权限；
3. framework provider watcher 与 uinput bridge 正常；
4. 用户本地提供的官方原签名 Remote Service 能被系统接受；
5. iPhone 官方 Google TV 应用完成发现、认证、遥控和文字输入；
6. Google 专有 APK 不进入 Git、公开镜像或项目再分发。

如果将来因 GMS TV 许可、签名或商业认证无法满足第 4–5 项，应明确标记
`BLOCKED`，而不是悄悄改成 UBOX Input。

## 10. 上游依据

- AOSP Android 12 TV remoteprovider：
  <https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-12.0.0_r1/media/lib/tvremote/>
- AOSP Android 12 TV remote framework：
  <https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-12.0.0_r1/services/core/java/com/android/server/tv/>
- Android privileged permission allowlist：
  <https://source.android.com/docs/core/permissions/perms-allowlist>
- Google Play 上的 Android TV Remote Service：
  <https://play.google.com/store/apps/details?id=com.google.android.tv.remote.service>
