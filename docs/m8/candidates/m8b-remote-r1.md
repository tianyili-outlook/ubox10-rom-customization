# M8B remote-r1 candidate

状态：**DEVICE ACCEPTED / REMOTE PASS**。该镜像现为设备运行和后续 M8B 工作的 accepted baseline，继承 **AUDIO PASS** 与 **IME PASS**。

直接基线为 `m8b-ime-r1`（**DEVICE ACCEPTED / IME PASS**，继承 **AUDIO PASS**）。目标输入架构保持为物理 rc-core 遥控、local AOSP LeanbackIME、official Google TV iOS Remote/phone keyboard 三者共存。

## Proven contract and current compatibility

本候选复用 Test9r2 的 device-proven Remote v2 路径：commit `a8cd9629d4049161022099e6566024c28074a979` 提供实现 provenance，`4d68b496c6bf240fc5279921e27e0f8239a523e5` 修正 RRO 到实际扫描的 system_ext 路径，`1e4fa199413df6f74fe24f7c5edde9bc69c34c0a` 记录 official Google TV iPhone discovery、TLS pairing、navigation 与 phone text PASS。该实验证明 TCP 6466/6467、`_androidtvremote2._tcp` 和 TvRemoteProvider/uinput 链工作；首次确定性阻塞仅为缺少 Android 12+ runtime `BLUETOOTH_CONNECT`，只授予 CONNECT 即闭合，SCAN/ADVERTISE 保持未授予。

当前 M8B 已原生具备 Android 12 AOSP `com.android.media.tv.remoteprovider`：accepted JAR SHA-256 `CF2FC4A6878A1CC7576F6AF84D430C98D4485FFDA992D43A8AA03D9C696C2EBE`，shared-library XML SHA-256 `B3C1D21187054FB7049BFF10B9DA1D38D8685E0C2583AB000129340E74885994`；`tv_core_hardware.xml` 已声明 television/leanback/leanback_only。它们和 framework-res 均原字节复用，不注入历史 provider JAR或额外 feature XML。Bluetooth app、NetworkStack/NSD 与 permissive SELinux baseline 不改。

## Implementation

Google-original donor 为 `com.google.android.tv.remote.service` 5.2.473254133（versionCode 95855272、minSdk 24、targetSdk 33），3817484 bytes，SHA-256 `9D1B5C5EF0E293F8ED17C26E8F62DE661ACC7F2DDC2AAA8EF23E4CABE430B973`。APK v2/v3 signature 验证通过，signer certificate SHA-256 `456EDBC33222D20FF158D42E9FAB0252DBE0514D6E1C39588D6B1982CC189137`；无 native library，ARM32 兼容。binary 仅保存在 local ignored 路径，不进入 Git。

`configs/aosp/m8b-remote-r1/` 与 integration patch 通过 Android 12 正常模块集成：

- presigned privileged `AndroidTvRemoteService`，要求 existing `com.android.media.tv.remoteprovider` shared library；
- exact Test9r2 privileged-permission allowlist；signature-only `INJECT_EVENTS` 刻意不授予，输入使用 framework bridge；
- Android default-permissions 只授予 `BLUETOOTH_CONNECT`，`fixed=false`；不默认授予 SCAN/ADVERTISE；
- source-built static RRO `com.ubox10.overlay.tvremote`，target `android`、priority 999，在 `/system/system_ext/overlay/UBOX10TvRemoteConfigOverlay.apk`，把 `config_tvRemoteServicePackage` 设为 `com.google.android.tv.remote.service`。

最终 accepted system 文件差异仅：

- `/system/priv-app/AndroidTvRemoteService/AndroidTvRemoteService.apk`；
- `/system/etc/permissions/privapp-permissions-com.google.android.tv.remote.service.xml`；
- `/system/etc/default-permissions/default-permissions-com.google.android.tv.remote.service.xml`；
- `/system_ext/overlay/UBOX10TvRemoteConfigOverlay.apk`；
- 两个新目录及两个现有父目录的 link-count metadata。

没有修改 provider framework、SystemServer、feature identity、system/product properties、GMS/Play、launcher、LeanbackIME、keylayout/rc-core、audio、graphics、DRM、SELinux policy、CEC 或 vendor stack。

## Artifact and preservation

| 工件 | 大小 | SHA-256 |
|---|---:|---|
| `out/candidates/m8b-remote-r1/x12-m8b-remote-r1.img` | 1031723008 | `F3B09E5565AC4ED4E5EE326D392622E7B036A8519B8444B966E77CC4751B814A` |
| `system_a` | 1651167232 | `5992972F35EAFEB722C482A83D5B555F023DEAEA45EABFA282AB3379C8C3056B` |
| `super.img` | 851924428 | `6374231FECBA80294D0BEDB97F265068C88C193788E1048FD0894B5C854398B2` |
| `vbmeta_system.fex` | 1472 | `1B2C0F7A880319E12F70042935FEFE15D1B3EFFE048C652FE1AFF217062FF267` |

logical delta 仅 `system_a`。`product_a`（含 accepted LeanbackIME）保持 SHA-256 `6E2D0AF3E80DCCC488D73E1A7F483C96075E9F60588DDB7DCBBC42C64FCD8974`，`vendor_a` 与 `vendor_dlkm_a` 也原字节不变。外层仅替换 `super.fex`、`vbmeta_system.fex` 并生成各自 V companion；其余 46 项，包括 boot/kernel、vendor_boot、top-level vbmeta、DTBO、metadata 与 media_data，均由 preservation audit 确认为 preserved。

Test9r2 的 bulk system cleanup、Play/GMS/launcher/feature changes 和 `AccessRestrictedActivity` 变量均未导入。当前 accepted M8B system/product inventory 无 Play Store/GMS app；本候选不添加这些包，不改 `tv_core_hardware.xml`、framework-res 或 build properties，因此没有离线证据表明重现了历史 Play regression。当前实机再次确认 Play Store/GMS/GSF 均不存在，故没有可执行的 Play runtime regression test；“未引入变量”不等同于 Play runtime PASS。

## Offline checks and device acceptance

AOSP `systemimage`/`systemextimage`、donor signature/manifest/services/library、privapp coverage、CONNECT-only default grant、RRO target/resource、exact filesystem diff、SELinux file labels、四 logical partition e2fsck、system/vbmeta AVB、LP re-unpack、IMAGEWTY verify、SHA256SUMS、14 项 focused tests 与全量 91 tests（3 个 expected fixture skip）均通过。

用户随后刷入本候选并完成现场验收：正常进入 Projectivy；物理遥控、Wi-Fi、Bluetooth 与 LeanbackIME 无基础回归。只读 ADB 确认 `sys.boot_completed=1`，Remote Service 5.2.473254133 位于预期 system priv-app，`BLUETOOTH_CONNECT` 为 `granted=true` 且带 `GRANTED_BY_DEFAULT`，无需手工 `pm grant`；进程运行，TCP `*:6466`/`*:6467` 监听。RRO 位于 `/system_ext/overlay/UBOX10TvRemoteConfigOverlay.apk`，framework resource lookup 精确返回 `com.google.android.tv.remote.service`。

official Google TV iPhone app 的 discovery、pairing、DPAD、BACK、HOME、Volume+、Volume-、Mute 与 phone keyboard 向真实 TV EditText 写入均现场 PASS，闭合 Test9r2 Remote v2 功能。手机 Remote text-input mode 活跃时系统显示 `Use the keyboard on your mobile device` 并把文字输入交给手机；物理遥控导航保持正常。这是接受的 Android TV input-session ownership，不要求 LeanbackIME 同时显示，也不视为 IME regression。

单独 reboot persistence 未执行；现有 fresh install/default grant、自动服务运行和完整现场使用没有给出具体失败理由，故作为非阻塞接受，但不声明 reboot-persistence PASS。实机没有 `com.android.vending`、`com.google.android.gms` 或 `com.google.android.gsf`，因此不存在可执行的 Play runtime regression test；本候选仍只证明未导入历史 Test9r2 Play/GMS 变量。

另记录一个独立、非阻塞观察：boot 后 LeanbackIME 首次调用明显慢于后续调用，偶尔需要按 OK 两三次才出现。当前不确认 defect 或 root cause，也不修改 IME；后续只用受控真实 EditText 比较 cold/warm invocation timing。验收证据见 `docs/m8/device-tests/20260816-m8b-remote-r1/`。
