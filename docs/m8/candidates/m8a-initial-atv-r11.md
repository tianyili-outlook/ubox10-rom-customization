# m8a-initial-atv-r11

## 目的

r10 已完成 Android framework 启动，但产品构成中没有真实 HOME。r11 仅向可复现的 system composition 加入一个 Android TV Launcher，不修改 provisioning、Setup、SystemUI 或硬件栈。

## 输入与单变量

- 基线：`m8a-initial-atv-r10`
- Launcher：Projectivy Launcher 4.71，包名 `com.spocky.projengmenu`
- 来源：项目既有 `work/preinstall_apks/ProjectivyLauncher-4.71-c95-xda-release.apk`
- 来源 SHA-256：`6818FC2DB44411A605CA4D7067FB9D7227AAEF2414CFF42DE58FE13E9321B47A`
- 安装位置：`/system/app/ProjectivyLauncher/ProjectivyLauncher.apk`
- HOME activity：`com.spocky.projengmenu.ui.home.MainActivity`

当前 `device/ubox/ubox10/ubox10.mk` 只显式加入 `AwTvProvision`，继承的 `atv_product.mk` 只加入 overlay；包含示例 Launcher 的 `aosp_tv_arm.mk` 未被继承，因此 r10 composition 没有 Launcher。r11 构建器把已锁定 APK作为 system app 输入，避免对最终镜像做不可复现的临时修改。

## Manifest 与兼容性

- `MAIN`、`HOME`、`DEFAULT`、`LEANBACK_LAUNCHER` 均位于同一 exported HOME activity。
- `android.software.leanback` 为 required，触屏和 Wi-Fi feature 为 optional。
- `minSdk=23`，`targetSdk=37`；主 HOME 未声明 `directBootAware`，按 false 处理，适用于 r10 已解锁后的 HOME 交接。
- 普通 system app，非 privileged、无 `sharedUserId`，不需要 privapp allowlist。
- 没有 required platform shared library；三个声明库均为 optional。
- APK包含 `armeabi-v7a` 原生库，三项均为 ELF32/ARM，全部 `DT_NEEDED` 可在 r10 userspace 中解析。
- APK v1/v2 签名验证通过，zip/native 对齐检查通过。

## 产物

| 项目 | 值 |
|---|---|
| 镜像 | `out/candidates/m8a-initial-atv-r11/x12-m8a-initial-atv-r11.img` |
| 大小 | 1007847424 bytes |
| SHA-256 | `03C674F7A3D3D01B4466C0AF176C5CF218B4A68C0C1802684620D0295A0DB7C2` |
| system_a | `7E3BA3A79583CA29E50BAD7FC5DF1543E7B931FB53E4F88F6FFFB90AA2D9CB69` |
| super | `A81947E01D5300B417A6748393758494C3106E809B81478B3FD19793524952CC` |
| vbmeta_system | `E73DF3D2EA4A955934DFF5272B4D24FA568597E3E7A8DE240EE47C34A0CCB594` |
| Vsuper | `56591CF4B8AA8E0EB5DDC9395DF81A8202B19E310BACA963CC88836105707556` |
| Vvbmeta_system | `9F42085E9D7915B1EA11B642C24B4E5E5C7AA9C2037CA27557945B4536F17415` |

相对 r10，仅 `system_a`、`super.fex`、`Vsuper.fex`、`vbmeta_system.fex`、`Vvbmeta_system.fex` 变化。`vendor_a`、`product_a`、`vendor_dlkm_a`、boot、vendor_boot、顶层 vbmeta 和其余 46 个外层 payload 原字节不变。

## 离线检查

- 解包后的 system 仅新增 Launcher 目录和 APK；父目录 link count 变化属于新增子目录的确定性结果。
- APK SHA、uid/gid、mode 与 `system_file` SELinux label符合锁定值，PackageManager 扫描路径有效。
- r10 两个 AIDL compatibility library 原字节不变；canonical `/vendor` topology 不变。
- LP、AVB、四分区只读 e2fsck、ELF/native 依赖、SELinux policy 字节继承、外层 IMAGEWTY 校验和针对性测试通过。

## 首测

刷入后先确认：

```text
getprop sys.boot_completed
cmd package resolve-activity --brief --user 0 -a android.intent.action.MAIN -c android.intent.category.HOME
cmd package query-activities --brief --components --user 0 -a android.intent.action.MAIN -c android.intent.category.LEANBACK_LAUNCHER
dumpsys activity activities | grep -E 'mResumedActivity|topResumedActivity'
settings get global device_provisioned
settings get secure user_setup_complete
logcat -d -s FallbackHome ActivityTaskManager PackageManager
```

成功条件：`sys.boot_completed=1`；HOME 解析和最终 resumed activity 均为 `com.spocky.projengmenu/.ui.home.MainActivity`；Leanback 查询出现该 activity；`FallbackHome: User unlocked but no home` 停止。两个 provisioning 值本轮预期仍为 `0`。
