# M8B ime-r1 candidate

状态：**DEVICE ACCEPTED / IME PASS**。

直接基线为 `m8b-audio-r2`（**DEVICE ACCEPTED / AUDIO PASS**）；本候选现已刷入并完成物理设备验收。

## 选择与实机可用性

选择 Android 12 AOSP `LeanbackIME`：包 `com.android.inputmethod.leanback`，服务 `com.android.inputmethod.leanback.service.LeanbackImeService`。源码来自锁定树 `/home/tianyi/ubox10-aosp/packages/inputmethods/LeanbackIME`，commit `40b72d02ed2af7d1696cd8903682dcfcd963323c`，上游为 `platform/packages/inputmethods/LeanbackIME`，Apache-2.0。它是 AOSP Android TV 的默认键盘，控制器源码原生处理 DPAD 四向、DPAD_CENTER、BACK，基础输入不依赖触屏；纯 Java APK 无 native library，适合当前 ARM32 Android userspace。

可逆 userdata 试验已通过：APK 被 InputMethodManager 发现、正常 enable/set 为 default，AOSP `EditTextVariations` 的真实 EditText 获得焦点并显示该 IME。DPAD_CENTER 输入 `t`，DPAD_RIGHT 将键盘焦点移至 `y`，再次 DPAD_CENTER 后 UI hierarchy 精确读回 `ty`；BACK 隐藏，重新聚焦后可再次显示。IME 与 probe PID 在试验前后未变，无 exit-info 或 crash/retry loop。普通 `KEYCODE_ENTER` 在该 multiline EditText 执行 editor action，而不是选择当前软键；验收选择键路径为设备已接受的 DPAD_CENTER，不将 ENTER 行为夸大为通过。测试后两个 APK 均卸载，IME list/default 恢复为空，设备仍在线且 `sys.boot_completed=1`。

后续物理设备验收确认 fresh-data 首启正常进入 Projectivy，物理遥控与 Wi-Fi 正常；Wi-Fi 密码 EditText 无任何 ADB enable/set 即自动显示 LeanbackIME。`ime list -a`、`enabled_input_methods` 与 `default_input_method` 均为 `com.android.inputmethod.leanback/.service.LeanbackImeService`，物理 DPAD focus/OK 选键、文字输入、BACK dismissal 与 1920×1080 电视观感均通过。

拒绝项：stock/Test8r2 `LatinIME` 是约 18.5 MB 的普通手机 AOSP 键盘，没有 TV D-pad focus provenance；仅因可构建不足以证明可用。锁定 AOSP 已有合适 TV 模块，因此不引入外部第三方 APK或额外维护依赖。

## ROM 集成与边界

`configs/aosp/m8b-ime-r1-leanback-ime.patch` 通过标准 `PRODUCT_PACKAGES += LeanbackIME` 集成，AOSP `m productimage` 成功。最终 product 文件差异仅：

- `/app/LeanbackIME/**`（APK 与 ARM32 odex/vdex）；
- `/app` 的目录 link count；
- `/etc/NOTICE.xml.gz` 的 Apache-2.0 notice 更新。

AOSP 当前 Treble source contract 会额外生成与 accepted product 不同的 `build.prop`；packager 明确恢复 accepted `m8b-audio-r2` product property 文件原字节，避免把无关 runtime property 变化混入 IME 候选。`system_a`、`vendor_a`、`vendor_dlkm_a` 哈希不变，boot/kernel/vendor_boot、`vbmeta_system` 与其余外层 payload 均保持；payload delta 仅 `product_a`、`super.fex`、`Vsuper.fex`。product AVB、accepted system/vbmeta AVB、LP 重解包与 IMAGEWTY preservation/verify 均通过。

LeanbackIME 的 `input-method` metadata 为 `android:isDefault=true`；Android 12 在没有 enabled/default IME 时会选择 default-enabled IME。fresh-data 首启已证明无需 ADB enable/set。用户没有另行执行单独 reboot persistence，并以 fresh-data 自动选择和实际物理使用接受该子项为非阻塞；本文不声明 reboot persistence PASS。

## 工件

| 工件 | 大小 | SHA-256 |
|---|---:|---|
| `out/candidates/m8b-ime-r1/x12-m8b-ime-r1.img` | 1028208640 | `B89612D5004BA3D8214F21E22E4BED7BFBA5B2F8FE441F9364315F851F1FE240` |
| `product_a` | 272629760 | `6E2D0AF3E80DCCC488D73E1A7F483C96075E9F60588DDB7DCBBC42C64FCD8974` |
| `super.img` | 848409756 | `D32CCB2B85B0A869156D7389A51B1C56D33B3EBBBEA2FA7ED577E255CC460012` |
| source-built `LeanbackIME.apk` | 376800 | `4CF1AD0D5CA5514F59BAE9467981E7FDEB56692932208A15E9286166ECE73075` |

## Independent Remote candidate

`m8b-remote-r1` 已作为独立候选构建为 **READY TO FLASH**：保留 Test9r2 已证明的 AOSP `com.android.media.tv.remoteprovider`、system_ext 扫描路径中的 provider RRO、Google-original Android TV Remote Service donor、privapp allowlist/provider whitelist、6466/6467、mDNS、iPhone Google TV app discovery/pairing/navigation/phone keyboard，以及缺失 default `BLUETOOTH_CONNECT` grant 是首个 deterministic blocker、只授予 CONNECT 即完成链的事实。它未导入 Test9r2 全量或 Play/GMS 变化；当时 Play Store `AccessRestrictedActivity` regression 未证明由 Remote Service 引起。该服务仍不属于本 `m8b-ime-r1` 镜像。

证据：`docs/m8/device-tests/20260816-m8b-ime-r1/`。
