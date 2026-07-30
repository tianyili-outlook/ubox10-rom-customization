# 当前运行手册

## 当前状态

Test8r2 是唯一稳定基线：

- 镜像：`out/candidates/test8r2-restore-contacts-provider-r1/x12-test8r2-restore-contacts-provider.img`
- 大小：2,005,954,560 bytes
- SHA-256：`6A52F3388E9ABF6AFA8A701CFD7198FE6C0090F16531F6E3BD3949E760892EC8`
- 已通过：Projectivy、英语、实体遥控、Settings、Wi‑Fi 连接、蓝牙和
  ContactsProvider/PBAP。

Test9r2 已完成一次性技术探针，不再是开发基线：

- 本地镜像与候选输出目录已在 M7 发布收束时删除；配置、生成脚本、固定哈希
  和真机报告保留，可按需复现。
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
`../../m7/tv-gms-remote/test9r2-runtime-report.md`，路线决定见
`../../m7/tv-gms-remote/route-decision.md`。

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

## M7 已完成：刷机后应用恢复

M7 已完成；重新刷入 Test8r2 后，不继承 Test9w1、Test9r1 或 Test9r2。
推荐使用交互式统一入口：

```powershell
python .\scripts\install-userdata-apps.py --guided-after-flash
```

引导模式先从锁定的官方 HTTPS 地址下载缺失的五项 APK，再验证其大小、
SHA-256、metadata 和签名以及 Test8r2 实机合同，然后直接打开
AirReceiverLite 的 Play Store 页面。用户在电视上登录 Play Store；出现
`Complete account setup` 时选择 `Skip`/`Not now`，无需绑定信用卡；安装
免费 AirReceiverLite 后回到终端按 Enter，脚本再统一安装 SmartTube、Kodi、
Jellyfin TV、Moonlight 和 AnExplorer，并把报告写入忽略的 `work/`。

首次使用 AirReceiverLite 时，在 Projectivy 中打开它并按界面提示授予
“显示在其他应用上层”。Lite 只能作为前台按需能力，部分功能每次会话限
5 分钟；M7 不要求购买完整版。

诊断或非交互复现仍可分步运行：

```powershell
python .\scripts\install-userdata-apps.py --verify-only
python .\scripts\install-userdata-apps.py --dry-run
python .\scripts\install-userdata-apps.py
```

完整结果、有限豁免与来源锁见
仓库根 `README.md`、
`archive/m7/M7_COMPLETION_REPORT.md` 和
`archive/m7/TEST9_3_USERDATA_APPS.md`。M7 不再接受 Play Store、GMS、
设备身份、framework remote gate 或 Google Remote Service 修改。

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
