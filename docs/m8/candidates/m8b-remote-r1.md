# M8B remote-r1 candidate

状态：**READY TO FLASH**。本轮未刷机；任何设备测试仍需单独明确授权。

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

Test9r2 的 bulk system cleanup、Play/GMS/launcher/feature changes 和 `AccessRestrictedActivity` 变量均未导入。当前 accepted M8B system/product inventory 无 Play Store/GMS app；本候选不添加这些包，不改 `tv_core_hardware.xml`、framework-res 或 build properties，因此没有离线证据表明重现了历史 Play regression。刷机后仍按回归计划复核实际 Play 状态，不把“未引入变量”等同于 runtime PASS。

## Offline checks and next gate

AOSP `systemimage`/`systemextimage`、donor signature/manifest/services/library、privapp coverage、CONNECT-only default grant、RRO target/resource、exact filesystem diff、SELinux file labels、四 logical partition e2fsck、system/vbmeta AVB、LP re-unpack、IMAGEWTY verify、SHA256SUMS、14 项 focused tests 与全量 91 tests（3 个 expected fixture skip）均通过。

下一步是在单独明确刷机授权后执行 `docs/DEVICE_TEST.md` 的 physical sequence：boot/Projectivy/物理遥控、Wi-Fi/Bluetooth、LeanbackIME regression、service/provider/RRO、6466/6467、mDNS、iPhone discovery/pair/navigation/BACK/HOME、真实 EditText phone text、local IME coexistence、reboot persistence 与 Play 状态。通过前不得标记 DEVICE ACCEPTED。
