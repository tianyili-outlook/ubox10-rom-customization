# Test9r2 真机运行报告

采证日期：2026-07-29。

## 1. 结论

- Remote 技术链：`PASS`。
- Test9r2 整机候选：`PARTIAL`，不得晋级。
- 结果分类：`R2-REMOTE-PASS`。
- 近期路线：选择 `S3 / 收束 32 位 remote`；不制作 Test9r3 或 Test10p1，
  官方 Google TV 手机遥控的产品化集成转入 M8.INPUT。

Test9r2 已证明官方 Google TV iOS 应用可以在同一局域网发现电视、使用配对码
完成 TLS 配对、建立控制连接、操控电视并输入文字。接收端首次启动失败的
确定性根因不是 Wi-Fi、mDNS、iPhone 或 Play Store，而是预置产品没有为
Remote Service 默认授予 Android 12+ 的
`android.permission.BLUETOOTH_CONNECT` 运行时权限。

Play Store 仍进入 `AccessRestrictedActivity` 并显示版本不兼容，因此即使
remote 技术链通过，Test9r2 也不具备日常使用资格。重启后的自动启动和配对
持久性本轮未复验，留作 M8.INPUT 正式验收。

## 2. 测试对象

| 项目 | 值 |
|---|---|
| 基线 | Test8r2 |
| 候选 | Test9r2 |
| 固件 SHA-256 | `27B54FB83E96D3863FAE2EF2718E8EC9ADDD863E5ED123082D5E6C8CA6FFFD52` |
| Remote Service | `com.google.android.tv.remote.service` 5.2.473254133 |
| Remote Service target SDK | 33 |
| 手机客户端 | 官方 Google TV iOS 应用 |
| 网络 | 电视与 iPhone 位于同一 5 GHz WLAN |

本轮只改变了 userdata 中一个运行时权限状态；没有修改 system/vendor 分区、
没有构建或刷写新镜像，也没有授予 `INJECT_EVENTS`。

## 3. 分层证据

### RRO 与 framework：PASS

- `android.hardware.type.television`、`android.software.leanback` 和
  `android.software.leanback_only` 均存在。
- `com.android.media.tv.remoteprovider` shared library 存在。
- Remote Service 位于
  `/system/priv-app/AndroidTvRemoteService/AndroidTvRemoteService.apk`。
- RRO 位于
  `/system/system_ext/overlay/UBOX10TvRemoteConfigOverlay.apk`。
- framework lookup 精确返回
  `com.google.android.tv.remote.service`。
- `TV_VIRTUAL_REMOTE_CONTROLLER` 为 `granted=true`。
- SystemServer 已绑定 `AtvRemoteProviderService`。

这证明 Test9r2 对 Test9r1 RRO 扫描路径的单变量修正有效。

### 首次 receiver 启动：FAIL

未干预时：

- 只有 `:primes_lifeboat` 进程，Remote Service 主进程不存在；
- `AtvRemoteProviderService` 为延迟重启状态，`crashCount=2`；
- 6466/6467 均未监听；
- `BLUETOOTH_CONNECT`、`BLUETOOTH_SCAN` 和
  `BLUETOOTH_ADVERTISE` 均为 `granted=false`。

日志中的首个确定性失败为：

```text
RemoteService.onCreate
  -> BluetoothAdapter.getBondedDevices/getAddress
  -> SecurityException: Need android.permission.BLUETOOTH_CONNECT
  -> Remote Service 主进程退出
```

privapp allowlist 只处理 privileged 权限，不能代替 Android 12+ 危险权限的
默认/运行时授予。当前产品缺少相应 default-permissions 集成。

### 单权限探针：PASS

仅执行一次临时授权：

```powershell
adb shell pm grant com.google.android.tv.remote.service `
  android.permission.BLUETOOTH_CONNECT
```

随后以前台服务方式重新触发 Remote Service。探针完成时：

- `BLUETOOTH_CONNECT=granted`；
- `BLUETOOTH_SCAN=false`；
- `BLUETOOTH_ADVERTISE=false`。

因此本轮没有证据支持额外授予 SCAN 或 ADVERTISE；M8 应遵循最小权限，
先原生授予已证明必需的 CONNECT，只有实际代码路径和真机失败证据要求时才
扩大权限。

### receiver、发现与协议：PASS

CONNECT 授权后：

- Remote Service 主进程持续存活；
- 最终复核时已连续运行约 18 分钟，未出现新的 Remote Service fatal crash；
- `RemoteService` 与 `DiscoveryService` 均为 foreground service；
- TCP 6466 和 6467 同时监听；
- 服务生成本地服务器证书；
- mDNS 成功注册 `_androidtvremote2._tcp`；
- 广播设备名为 `Pixel 3`；
- framework provider 已正常绑定；
- 系统建立 `virtual-remote`、`virtual-remote-2` 和 `virtual-search`
  uinput 设备。

日志仍出现 “Security provider is not installed”，但随后证书生成成功；
因此它不是本次阻塞。Remote Service 也继续报告 Play Store “missing”以及
部分 Google API `SERVICE_INVALID`，但这些警告没有阻止本地 Remote v2
发现、配对、控制或文字输入。

### 官方 iPhone 客户端：PASS

真机日志和用户操作共同确认：

- iPhone 首先连接配对端口 6467；
- TLS 1.2 配对会话建立；
- 电视显示配对码界面；
- 配对完成后 iPhone 连接控制端口 6466；
- 接收端识别到 Apple/iPhone 与官方 Google TV iOS 客户端；
- 用户确认可以成功配对并操控电视；
- 用户确认手机文字输入正常。

未执行重启后的自动发现、配对持久性和文字输入复验，因此该项状态为
`NOT TESTED`，不伪记为通过。

## 4. Play/GMS 交叉结果

Play Store 29.2.15 仍进入
`com.google.android.finsky.accessrestricted.AccessRestrictedActivity`，
并显示当前版本与设备不兼容。这是 Test9r2 无法晋级的产品级回归。

Remote Service 的 “Play Store missing” 日志还有一项明确的产品配置缺口：

- framework `config_forceQueryablePackages` 当前只有
  `com.android.settings` 和 `com.android.providers.settings`；
- Remote Service 的 `queriesPackages=[]`；
- Play Store `forceQueryable=false`。

这与 Android 11+ 包可见性导致调用方看不到已安装 Play Store 的行为一致。
由于 remote 本地协议链仍然通过，本轮不再为 32 位候选增加 package visibility
overlay 或混装 Google 组件；该问题转入 M8.GMS。

## 5. 结果矩阵

| 层级 | 结果 | 备注 |
|---|---|---|
| RRO 扫描与 lookup | PASS | Test9r2 单变量修正有效 |
| framework/provider bind | PASS | `AtvRemoteProviderService` 已绑定 |
| 原始 receiver 启动 | FAIL | 缺 `BLUETOOTH_CONNECT` |
| 最小权限修正后 receiver | PASS | SCAN/ADVERTISE 仍未授予 |
| 6466/6467 | PASS | 两端口持续监听 |
| mDNS | PASS | `_androidtvremote2._tcp`，名称 `Pixel 3` |
| 官方 iPhone 发现 | PASS | 同一 5 GHz WLAN |
| TLS/配对码 | PASS | 6467 |
| 遥控输入 | PASS | 6466 与 framework uinput |
| 文字输入 | PASS | 用户真机确认 |
| 重启复验 | NOT TESTED | 转入 M8.INPUT |
| Play Store | FAIL | `AccessRestrictedActivity` / not compatible |
| 候选总体 | PARTIAL | remote PASS，但不可作为日常基线 |

## 6. M8 继承合同

M8 不复制 Test9r2 的二进制布局，而应在 AOSP ATV product/device tree 中
原生实现并逐层验收：

1. television/leanback product feature；
2. `com.android.media.tv.remoteprovider` shared library；
3. provider package resource 与实际可扫描的 overlay；
4. `BIND_TV_REMOTE_SERVICE`、`TV_VIRTUAL_REMOTE_CONTROLLER` 与最小
   privapp policy；
5. 为 Remote Service 默认授予已证实必需的
   `BLUETOOTH_CONNECT`，不预先扩大到 SCAN/ADVERTISE；
6. provider bind、证书、6466/6467、mDNS、配对码和 uinput；
7. 官方 Google TV iPhone 发现、配对、遥控、Unicode/账号/密码文字输入和
   重启复验；
8. 将 TV Play Store/GMS 一致性作为 M8.GMS 独立门禁。

详细路线选择见 [route-decision.md](route-decision.md)。
