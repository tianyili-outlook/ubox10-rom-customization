# M8B rc-core-r5 candidate

状态：**DEVICE ACCEPTED — AUDIO OPEN**

直接基线：设备验收的 `m8b-rc-core-r4`，SHA-256 `44B8D1B4787EAF8CF601725D2630D8508CC139CCC2109BA27D07D9AF1FB0D571`。

## 唯一修复变量

r4 已通过 native rc-core/repeat、exact `.kl` 选择、OK、DPAD、HOME、BACK 与 Power。剩余问题仅为物理 Settings 的 Linux `KEY_CONFIG` 171 被映射到当前系统无效果的 Android `SETTINGS` 176；现场已验证 Android `MENU` 82 可打开 Projectivy settings menu。

r5 仅把 exact device keylayout 中：

```text
key 171 SETTINGS WAKE
```

改为：

```text
key 171 MENU WAKE
```

ff4044→Linux `KEY_CONFIG`、其余 rc-map/keylayout、r4 Android 12 parser 兼容转换、exact 文件名、`multi_ir` disabled 状态、kernel、boot、Power 与 Projectivy 均保持。

## 候选与哈希

| 工件 | 大小 | SHA-256 |
|---|---:|---|
| `out/candidates/m8b-rc-core-r5/x12-m8b-rc-core-r5.img` | 1007982592 | `7B4D3E28D37CE242F92FF259BB43590EDF422630DA7B515D66E4DF1A000CFA98` |
| kernel Image | 23029768 | `FE23BEEAE10389EA13575CA266AF45797F22BCF9BDBA7037AF6F7A8B3148C5E2` |
| `boot.fex` | 67108864 | `0A9473513B309BA3168242500658F35D96EC40B49CA91E33C1068861F8756678` |
| `system_a` | 1651167232 | `ADF53C96702032D28351AE0C1E11618A17C6EBBC2E46E6E07B45C0810549C2A1` |
| `super.img` | 828183920 | `18FCB90C15A86B1ED1B52C063C86F837BC6BDF166C6B53C44AC6B5B5FBFC57CC` |
| `vbmeta_system.fex` | 1472 | `B17452FE890175CA779D5AB9C64D703DE521A95CE32531806740886ABB49555F` |
| `Vsuper.fex` | 4 | `01FA1247CD7A88F9C0DEA8461BC80077EA0288AC068B295414FFDE62CD2DF964` |
| `Vvbmeta_system.fex` | 4 | `039EA9B4DDC2BD76D489FBC094EB48BDDCCBB69B86309274A01EF71AFA44A4E7` |

目标 keylayout 为 SHA-256 `BD23FE567533A270D5F0A0B0BBD0B642CAD64E5659D6E2A176378FDFD558860A`。

## 限定验证

- r4→r5 keylayout 语义差异仅 171：`SETTINGS WAKE`→`MENU WAKE`；其余 45 条映射同字节语义保持。
- 46/46 条映射通过 exact SP1A parser 表审计；原 r4 unsupported-label 转换全部保持，最终 flag 仅 `WAKE`，无省略。
- system 文件差异仅 `/system/usr/keylayout/Vendor_0001_Product_0001_Version_0100.kl`；`multi_ir` 保持 disabled。
- r4 boot/kernel 原字节复用；`vendor_a`、`product_a`、`vendor_dlkm_a` 原字节不变。
- LP、AVB、四分区 e2fsck、split SELinux、ELF/DT_NEEDED、IMAGEWTY 外层校验通过。
- M8B + r12/r13 focused regressions 21/21 通过；`git diff --check` 通过。

相对 r4 仅 `system_a`、`super.fex`、`Vsuper.fex`、`vbmeta_system.fex`、`Vvbmeta_system.fex` 变化；`boot.fex`、`Vboot.fex` 及其余 46 个外层 payload 保持。

## 首测

先确认 `dumpsys input` 仍显示：

`KeyLayoutFile: /system/usr/keylayout/Vendor_0001_Product_0001_Version_0100.kl`

随后按物理 Settings，必须打开 Projectivy settings menu；再快速回归 OK、DPAD、HOME、BACK、Power。

## 实机结果

r5 已确认 exact device `.kl` 继续加载；native rc-core/repeat、DPAD、OK、BACK、HOME、Volume、Power 以及物理 Settings→Projectivy menu 全部通过。Projectivy/basic UI、Wi-Fi/Internet/ADB、Ethernet、Bluetooth/HID gamepad、USB host/storage enumeration、H.264 与 HEVC Cedar hardware decode 也已验收。当前最高优先级故障转为 AudioFlinger 无 primary output；音频修复不回退或修改本候选已验收的遥控链。

后续 clean service restart 已确认更早的首错：unchanged Apollo HAL 在进入 `adev_open` 前因 VNDK `libaudioroute.so` 缺失而 `dlopen` 失败。Test8r2 exact `/system/apex/com.android.vndk.current` 含该 ARM32 库，r5 没有任何 VNDK APEX。mixer control 与 ALSA topology 因而降级为第二层风险；下一候选 `m8b-audio-r1` 只恢复完整 exact Test8r2 VNDK 31 APEX，不回改本候选已验收内容。
