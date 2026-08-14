# M8B rc-core-r4 candidate

状态：**OFFLINE CHECKED — READY FOR FOCUSED DEVICE TEST**

直接基线：`m8b-rc-core-r3`，SHA-256 `3CF41276615D16A7B319467E5E3F031E52E468E5240AE23835F9C8675AC1D88B`。

## 根因与唯一修复变量

r3 已由设备确认 exact `Vendor_0001_Product_0001_Version_0100.kl` 被找到，但 Android 12 / SP1A.210812.015 parser 在 line 13 拒绝 `WAKE_DROPPED`，EventHub 回退 `Generic.kl`。路径、权限、SELinux 与 SHA 均不是根因。

r4 只把 device-specific keylayout 转换到 exact Android 12 parser 支持的 label/flag 集合。`sunxi-ir.kl` 继续保留 r3 原字节作参考；kernel、rc-main、NEC decoder、timeout、DTS/DTBO、rc-map、Power policy、Projectivy、Settings framework 与 disabled `multi_ir` 均不修改。

## 完整 parser 审计

审计源为 exact `/home/tianyi/ubox10-aosp/frameworks/native/libs/input/InputEventLabels.cpp`（SHA-256 `1FFFF95895274B79196C0F090AA7813E71A6737B8A67CE4F931681D0ECA0B1C8`）和 `KeyLayoutMap.cpp`（SHA-256 `F4949D9C04368CE98DF81E60301320A517EBCC898DBC68C874AD27DCA31BBDF7`）。本地没有可执行的预构建 `validatekeymaps`，因此直接解析 exact source 的完整 `KEYCODES_SEQUENCE`、`FLAGS_SEQUENCE` 和 keylayout grammar。

全部不受支持项及转换：

| 类型 | 原值 | Android 12 值 | 影响 |
|---|---|---|---|
| policy flag | `WAKE_DROPPED` | `WAKE` | 8 条映射；保留唤醒语义 |
| keycode label | `APPS` | `ALL_APPS` | Linux keycode 580 |
| keycode label | `BROWSER` | `EXPLORER` | Linux keycode 150 |
| keycode label | `EXPAND` | `TV_ZOOM_MODE` | Linux keycode 372 |

最终 46 条映射全部可由 exact parser 表解析，11 次转换，无省略项。352→DPAD_CENTER、103/108/105/106→DPAD、172→HOME、158→BACK、115/114→VOLUME_UP/DOWN、116→POWER、171→SETTINGS 均保持。

## 构建输入

- `configs/candidates/m8b-rc-core-r4.json`
- `scripts/convert-m8b-android12-keylayout.py`
- 参数化后的 `scripts/build-m8b-rc-core-r1-candidate.py`
- 参数化后的 `scripts/install-m8b-rc-core-input.sh`
- `tests/test_m8b_rc_core_r4.py`

## 候选与哈希

| 工件 | 大小 | SHA-256 |
|---|---:|---|
| `out/candidates/m8b-rc-core-r4/x12-m8b-rc-core-r4.img` | 1007982592 | `44B8D1B4787EAF8CF601725D2630D8508CC139CCC2109BA27D07D9AF1FB0D571` |
| kernel Image | 23029768 | `FE23BEEAE10389EA13575CA266AF45797F22BCF9BDBA7037AF6F7A8B3148C5E2` |
| `boot.fex` | 67108864 | `0A9473513B309BA3168242500658F35D96EC40B49CA91E33C1068861F8756678` |
| `system_a` | 1651167232 | `55DA1582A3684D0B9FA4ECA461B9B680E511469B08897CE3CD8F7D9BF8907D44` |
| `super.img` | 828183920 | `5171A589C38F911621065C23E5141302A0B2B23862A94A75EC4003A3A5ABA3DE` |
| `vbmeta_system.fex` | 1472 | `1ECEA896451C77D3D9A31A58494298D394DAC2362034BDB82C47162EA6145F44` |
| `Vsuper.fex` | 4 | `DB382578E8BC571634E7CCF7288E64282309B12A0EF87816F6AF84DE51B86E18` |
| `Vvbmeta_system.fex` | 4 | `3618BFCCE325F3B2A7FBD620194AE801D1AF20D6D19736A4DD220C5C290325A2` |

目标 keylayout 为 1795 bytes、SHA-256 `C8AB0907D9F7CFCDC9B14370548643DF9BCC03E488C5086D48BC424425A5E398`，安装为 regular `0644 root:root`、SELinux `u:object_r:system_file:s0`。参考 `sunxi-ir.kl` 保持 1848 bytes、SHA-256 `14FFF2ADF2B5F258AD77483FC5821F699EFAE008FAB28B0493A733AB7EFBC3AD`。

## 限定验证

- 完整 parser 表审计：46/46 条通过，最终 flag 仅 `WAKE`，无不支持 label/flag、重复 keycode 或省略项。
- system 文件差异仅 `/system/usr/keylayout/Vendor_0001_Product_0001_Version_0100.kl`；`sunxi-ir.kl`、`multi_ir` disabled 状态与 r13 contracts 保持。
- r2/r3 boot 和 kernel 原字节一致；kernel repeat patch SHA-256 仍为 `70A316DA67274FC2ED2584CCC090DC4282E6D740FFA04EE3C3B47DA2CD266549`。
- `vendor_a`、`product_a`、`vendor_dlkm_a` 原字节不变；LP、AVB、四分区 e2fsck、split SELinux、ELF/DT_NEEDED 与 IMAGEWTY 外层校验通过。
- M8B + r12/r13 focused regressions 18/18 通过；`git diff --check` 通过。

## Payload 差异与首测

相对 r3 仅 `system_a`、`super.fex`、`Vsuper.fex`、`vbmeta_system.fex`、`Vvbmeta_system.fex` 变化；`boot.fex`、`Vboot.fex` 和其余 46 个外层 payload 原字节保持。

首测先确认：

```sh
dumpsys input | grep -A 50 -B 5 'sunxi-ir'
```

必须显示 `KeyLayoutFile: /system/usr/keylayout/Vendor_0001_Product_0001_Version_0100.kl`，不得回退 `Generic.kl`。随后先测试物理 OK，再测试 DPAD、HOME、BACK、Power。Settings 全局启动语义和 legacy 清理继续延后。
