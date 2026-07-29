# 当前运行手册

## 当前状态

Test8r2 是唯一稳定基线：

- 镜像：`out/candidates/test8r2-restore-contacts-provider-r1/x12-test8r2-restore-contacts-provider.img`
- 大小：2,005,954,560 bytes
- SHA-256：`6A52F3388E9ABF6AFA8A701CFD7198FE6C0090F16531F6E3BD3949E760892EC8`
- 已通过：Projectivy、英语、实体遥控、Settings、Wi‑Fi 连接、蓝牙和
  ContactsProvider/PBAP。

Test9r2 已完成一次性技术探针，不再是开发基线：

- 镜像：`out/candidates/test9r2-android-tv-remote-service-rro-path-r1/x12-test9r2-android-tv-remote-service-rro-path.img`
- SHA-256：`27B54FB83E96D3863FAE2EF2718E8EC9ADDD863E5ED123082D5E6C8CA6FFFD52`
- Remote 技术链：`R2-REMOTE-PASS`。
- 整机结果：`PARTIAL`；Play Store 进入
  `AccessRestrictedActivity` 并显示 not compatible。
- 路线决定：S3，结束当前 32 位 remote 候选；不制作 Test9r3/Test10p1，
  官方手机遥控转入 M8.INPUT。

## Test9r2 最终证据

修正后的 system_ext RRO 生效，framework lookup 返回
`com.google.android.tv.remote.service`，provider 已绑定。

原始启动失败链：

```text
RemoteService.onCreate
  -> BluetoothAdapter.getBondedDevices/getAddress
  -> SecurityException: Need android.permission.BLUETOOTH_CONNECT
  -> 主进程退出，6466/6467 不监听
```

仅在 userdata 临时授予 `BLUETOOTH_CONNECT` 后：

- Remote Service 主进程和 foreground discovery service 稳定运行；
- 6466/6467 监听；
- `_androidtvremote2._tcp` 以 `Pixel 3` 名称发布；
- 官方 Google TV iPhone 应用完成 TLS 配对、遥控和文字输入；
- framework 建立 `virtual-remote`、`virtual-remote-2` 和 `virtual-search`
  uinput 设备；
- `BLUETOOTH_SCAN` 与 `BLUETOOTH_ADVERTISE` 仍未授予；
- `INJECT_EVENTS` 仍未授予，输入正确经过
  `TvRemoteProvider`/uinput bridge。

重启后的自动启动和配对持久性未复验。完整证据见
`research/tv-gms-remote/test9r2-runtime-report.md`，路线决定见
`research/tv-gms-remote/route-decision.md`。

## 已完成：当前设备退出 Test9r2

设备已于 2026-07-29 使用 PhoenixCard Product 模式刷回 Test8r2，并完成
自动基线复核。该过程清除了 userdata/metadata：

1. 备份需要保留的账号和本地数据。
2. 确认目标是 TF 卡。
3. 复核 Test8r2：

   ```powershell
   Get-FileHash `
     .\out\candidates\test8r2-restore-contacts-provider-r1\x12-test8r2-restore-contacts-provider.img `
     -Algorithm SHA256
   ```

4. 只有结果为
   `6A52F3388E9ABF6AFA8A701CFD7198FE6C0090F16531F6E3BD3949E760892EC8`
   时写卡。
5. 刷回后已验证 Projectivy、英语、方向/OK/Back/Home、Settings、HDMI、
   5 GHz Wi‑Fi、互联网、TCP ADB 和蓝牙。
6. Play Store 已回到 Test8r2 29.2.15；fresh userdata 当前进入未登录页面，
   不再进入 Test9r2 的 `AccessRestrictedActivity`。

本轮临时授予的 CONNECT 权限位于 userdata；刷写清除 userdata 时会自然消失，
无需修改只读分区或制作清理镜像。

## 当前 M7 工作：Test9.3

所有新工作继续从 Test8r2 出发，不继承 Test9w1、Test9r1 或 Test9r2：

已完成自动化部分：

1. `configs/apps/test9.3-userdata-apps.json` 固定五项来源、许可证、版本、
   包名、ABI、签名和 SHA-256。
2. `scripts/install-userdata-apps.py` 在 Test8r2 合同通过后，幂等安装
   SmartTube、Kodi、Jellyfin TV、Moonlight 和 AnExplorer TV。
3. 五项首次安装、launch activity、LEANBACK_LAUNCHER、真实重启持久性和
   重启后再次启动均通过；重复运行全部为 `already-current`。
4. 重启后 Projectivy HOME、5 GHz Wi‑Fi 6/互联网、蓝牙、Play Store 和
   feature guard 无回归。

当前人工步骤：

```powershell
python .\scripts\install-userdata-apps.py --verify-only
python .\scripts\install-userdata-apps.py --dry-run
python .\scripts\install-userdata-apps.py
```

- 用实体遥控逐项测试五个应用的焦点、Back/Home 和真实播放；
- 用 AnExplorer 测试存储权限、USB 和本地 APK 选择；
- AirReceiverLite 的 iPhone 发现、镜像、HDMI 音频和同步已经通过；Lite
  明确要求前台且部分功能每次限 5 分钟。由用户决定是否购买完整版，购买后
  再测后台接收、开机启动、长会话和电视广播名称。

完整源锁、命令、结果和人工清单见
`experiments/TEST9_3_USERDATA_APPS.md`。

Test9.3 不继续修改 Play Store、GMS、设备身份、framework remote gate 或
Google Remote Service。

## M8 并行边界

M8.0 当前只进行只读 inventory、source-lock 和报告，不制作迁移镜像：

- 当前 ELF/HAL/VINTF/Kernel module/图形/媒体/Wi‑Fi-BT inventory；
- Android 12 `aosp_tv_arm` product/package/overlay/permission 差异；
- 原厂/Test8r2 DRM-0 采集设计；
- BPI H618 source-lock 与空间预算。

M8.INPUT 必须原生继承 Test9r2 已证明的 product 合同：

- shared library、provider resource、实际生效的 overlay；
- 最小 privapp policy 和默认 `BLUETOOTH_CONNECT`；
- 不伪授予 `INJECT_EVENTS`；
- 6466/6467、mDNS、TLS 配对、uinput；
- 官方 iPhone 发现、配对、遥控、文字输入和重启复验。

M8.GMS 独立处理 TV Play Store、package visibility、Google API 与认证状态；
不得用 remote 成功替代 GMS 通过，也不得混装或重新分发未验证的 Google
专有组件。
