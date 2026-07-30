# Test9r2：Android TV Remote Service RRO 扫描路径修正

> M7 完成后归档；Remote v2 的可迁移结论由 M8.INPUT 继承，本文件不是当前
> 固件构建入口。

## 1. 状态

- 基线：Test8r2。
- Test9w1 driver patch：不包含。
- Test9r1 结论：真机 FAIL。
- Test9r2 离线结论：PASS。
- Test9r2 remote 真机结论：`R2-REMOTE-PASS`。
- Test9r2 整机结论：`PARTIAL`；Play Store 不兼容。
- 路线结论：选择 S3，结束当前 32 位 remote 候选，转入 M8.INPUT。
- 产品晋级资格：无；Test9r1 已确认 Play Store 关键回归，而 Test9r2 不改变
  leanback/Google stack。

Test9r2 不改变 remoteprovider、Google donor、权限、feature、system property
或 `vendor_dlkm`。相对 Test9r1 的唯一变量是同一个静态 RRO 的预置路径：

```text
Test9r1  /system/overlay/UBOX10TvRemoteConfigOverlay.apk
Test9r2  /system/system_ext/overlay/UBOX10TvRemoteConfigOverlay.apk
```

## 2. Test9r1 真机证据

已正常加载：

- `android.hardware.type.television`；
- `android.software.leanback`；
- `library:com.android.media.tv.remoteprovider`；
- `/system/priv-app/AndroidTvRemoteService/AndroidTvRemoteService.apk`；
- Remote Service 5.2.473254133；
- `TV_VIRTUAL_REMOTE_CONTROLLER` 及设计内 privileged permissions。

失败链：

1. `/system/overlay/UBOX10TvRemoteConfigOverlay.apk` 文件存在；
2. `pm path com.ubox10.overlay.tvremote` 无结果；
3. `cmd overlay list` 不含该 package；
4. `cmd overlay lookup android android:string/config_tvRemoteServicePackage`
   无结果；
5. 启动日志明确扫描 `/system/system_ext/overlay` 和 `/product/overlay`，
   并显示前者为空，却没有扫描 Test9r1 使用的 `/system/overlay`；
6. `TvRemoteProviderWatcher` 持续记录：
   `Ignoring atv remote provider service because the package has not been set
   and/or whitelisted`；
7. 6466/6467 无监听端口，iPhone 无可发现目标。

因此首要故障发生在 Package Manager/RRO 产品集成层，早于 mDNS、局域网、
蓝牙运行时权限或手机端发现。

Test9r1 上还确认：

- Play Store 29.2.15 仍安装、enabled state 为 default、Launcher 入口可解析；
- 实际启动会跳转到
  `com.google.android.finsky.accessrestricted.AccessRestrictedActivity`；
- Remote Service 日志多次报告它需要 Play Store、但 Play Store “missing”。

因此修正 RRO 以后可能出现第二层 Google 组件兼容阻塞。Test9r2 不用于验证
Play Store 修复，也不能成为日常固件。

## 3. 修正与构建

配置：

```powershell
python .\scripts\build-candidate-firmware.py `
  --config .\configs\candidates\test9r2-android-tv-remote-service-rro-path.json
```

输出：

| 字段 | 值 |
|---|---|
| 文件 | `x12-test9r2-android-tv-remote-service-rro-path.img` |
| 大小 | 2,005,946,368 bytes |
| SHA-256 | `27B54FB83E96D3863FAE2EF2718E8EC9ADDD863E5ED123082D5E6C8CA6FFFD52` |
| system removals | 348 个预期路径 |
| system additions | 10 个预期路径 |
| common regular-file changes | 仅 `/system/build.prop` |
| `vendor_dlkm` | 与官方输入相同，保留官方 FEC |
| ext4/e2fsck | PASS |
| 完整 AVB 链 | PASS |
| super metadata | PASS |
| IMAGEWTY 10 分区校验 | PASS |
| 单元测试 | 25 项运行、3 项预期 fixture skip、PASS |

最终 system manifest 只包含修正后的
`/system/system_ext/overlay/UBOX10TvRemoteConfigOverlay.apk`，不包含旧
`/system/overlay` 路径。

## 4. 真机最终结果

Test9r2 已证明 RRO 路径修正有效：

- RRO package 位于 `/system/system_ext/overlay`；
- framework lookup 精确返回
  `com.google.android.tv.remote.service`；
- provider 成功绑定；
- 原始启动因缺少运行时 `BLUETOOTH_CONNECT` 崩溃，
  `crashCount=2`，6466/6467 不监听；
- 仅在 userdata 临时授予 CONNECT 并重新触发服务后，主进程稳定，
  6466/6467 监听，`_androidtvremote2._tcp` 以 `Pixel 3` 名称发布；
- SCAN/ADVERTISE 保持未授予；
- 官方 Google TV iPhone 应用完成 TLS 配对、电视操控和文字输入；
- framework 建立 virtual-remote/uinput 设备；
- Play Store 仍进入 `AccessRestrictedActivity` 并显示不兼容。

因此 remote stack 分类为 `R2-REMOTE-PASS`，候选总体仍为 `PARTIAL`。
重启持久性未复验。完整脱敏证据见
`tv-gms-remote/test9r2-runtime-report.md`。

## 5. 已执行的真机 RRO 判错步骤

先不要直接用手机反复搜索。启动后执行：

```powershell
$adb = ".\tools\platform-tools\adb.exe"
& $adb connect 192.168.1.5:7896

& $adb shell pm path com.ubox10.overlay.tvremote

& $adb shell cmd overlay list |
  Select-String "com.ubox10.overlay.tvremote"

& $adb shell cmd overlay lookup `
  android android:string/config_tvRemoteServicePackage

& $adb shell logcat -d -v threadtime |
  Select-String "TvRemoteProviderWatcher|UBOX10TvRemote|OverlayConfig|idmap"
```

必须同时满足：

- `pm path` 指向 `/system/system_ext/overlay/`；
- overlay list 中 package 已注册且启用；
- lookup 精确返回 `com.google.android.tv.remote.service`；
- 日志不再出现 “package has not been set and/or whitelisted”。

任一项失败都先停止手机发现测试。

## 6. 已执行的服务和发现步骤

RRO 通过后执行：

```powershell
& $adb shell ss -lntup |
  Select-String "6466|6467"

& $adb shell logcat -d -v threadtime |
  Select-String "AtvRemote|remote.service|TvRemoteProvider|Nsd|mDNS|privapp"
```

然后让 iPhone 官方 Google TV 应用与电视连接同一个 5 GHz WLAN，验证发现、
配对码、方向/OK/Back/Home、普通与 Unicode 文字输入以及重启复验。

分层判定：

- RRO 未注册：仍是预置分区/扫描路径问题；
- RRO 已注册但 lookup 失败：检查 idmap 和 overlay policy；
- lookup 正确但 provider 仍未绑定或端口未监听：检查 Remote Service 生命周期、
  provider bind 和运行时权限；
- 端口已监听但手机无法发现：检查 mDNS、AP/client isolation、组播与手机网络；
- 能配对但不能输入：检查 `TV_VIRTUAL_REMOTE_CONTROLLER`、provider Binder
  和 uinput bridge；不得伪授予 `INJECT_EVENTS`。

## 7. 最终结果与退出

Remote 技术链已经通过，但 Play Store 回归也再次确认，因此 Test9r2 总体
记录为 `PARTIAL`，不晋级。用户选择 S3 收束当前 32 位 remote：

- 不制作需要移除 leanback、修改 `SystemServer` startup gate 的 Test9r3；
- 不制作需要混装 TV Google 组件的 Test10p1；
- 后续固件继续从 Test8r2 构筑；
- 当前 M7 进入 Test9.3 应用、AirPlay、文件管理和整体回归；
- 官方 Google TV 手机遥控产品化转入 M8.INPUT。

Test9r2 完成采证后应刷回 Test8r2。路线依据见
`tv-gms-remote/route-decision.md`。

## 8. M8 继承

M8 应从 ATV product/device tree 原生声明 provider package、shared library、
permissions 和 overlay，而不是复制 Test9r1/Test9r2 二进制布局。必须把
“预置文件存在”与“Package Manager 实际扫描、注册并生效”分别验收。官方
Google TV iPhone 发现、认证、遥控与文字输入仍是 M8.INPUT 门槛；不开发
UBOX Input。

Test9r2 还为 M8 增加了最小权限合同：通过 default-permissions 原生授予
已证实必需的 `BLUETOOTH_CONNECT`；SCAN/ADVERTISE 只有在新的代码路径和
真机证据要求时才扩大。M8.INPUT 还需补做重启后的自动启动、发现、配对
持久性和文字输入复验。Play Store/package visibility/Google API 问题由
M8.GMS 独立处理。
