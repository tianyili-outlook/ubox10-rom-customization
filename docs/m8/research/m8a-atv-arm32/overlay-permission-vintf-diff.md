# Overlay、permission 与 VINTF 差异

## 产品资源

| 项目 | M8A 决策 |
|---|---|
| `TvFrameworkOverlay` | 加入；锁定 TV UI、D-pad、无 Recents/Quick Settings、1920 UI 宽度和 TV 电源行为 |
| `TvSettingsProviderOverlay` | 加入；关闭旋转/锁屏，采用 TV 的常亮、休眠、屏保和 IME 默认值 |
| `TvWifiOverlay` | 加入；若 AIC8800 连接选择回归，单独撤回此 overlay |
| `atv-component-overrides.xml` | 加入；关闭 SystemUI KeyguardService |
| properties | 加入 `persist.sys.media.avsync=true` 和 SurfaceFlinger HDMI hotplug product-info 更新 |
| build identity | `PRODUCT_IS_ATV=true`、`ro.build.characteristics=tv`；不继承 Pixel/GMS feature |

权限文件使用 UBOX10 自有 TV feature 集：新增 `leanback` 与
`leanback_only`，保留 external camera、CEC、Ethernet、Wi-Fi、Bluetooth。
不整份复制 emulator 的 `tv_sdk_excluded_core_hardware.xml`；当前 SELinux
仍为 Permissive，也不声明 `android.hardware.security.model.compatible`。

首版若保留 `AwTvProvision`，同时保留其三项 privapp allowlist：
`WRITE_SECURE_SETTINGS`、`DISPATCH_PROVISIONING_MESSAGE`、`MASTER_CLEAR`。
AOSP `TvProvision` 替换时改用上游自带 policy，不允许两个 Setup HOME 共存。

## VINTF 与 SELinux

- `vendor` manifest/device matrix、target-level 6、VNDK 31 保持不变。
- 保留 product matrix 对 `vendor.display.config@1.0` 和
  `vendor.display.output` AIDL v2 的声明；丢失它会破坏显示栈 VINTF 合同。
- system/system_ext 使用 Android 12 framework matrix 与 ATV system_ext
  policy；不导入 ATV emulator vendor manifest 或 vendor policy。
- 离线候选必须通过 `checkvintf`；ATV 本身不需要新增设备 HAL。
