# M8B rc-core-r3 candidate

状态：**OFFLINE CHECKED — READY FOR FOCUSED DEVICE TEST**

直接基线：`m8b-rc-core-r2`，SHA-256 `AE53376C3F902C8B239321E196F7886BFEFEC74C43E66B6FAB50EC100A64F3C8`。

## 根因与单变量修复

r2 已实机证明 kernel/native rc-core repeat 生命周期正确。剩余失败是 Android 对 `sunxi-ir` 的 identifier 为 vendor/product/version `0001/0001/0100`，因此加载 `Generic.kl`，不会按设备名选择 `sunxi-ir.kl`。

r3 只把 r2 已生成的 keylayout 以 exact Android 文件名安装到：

`/system/usr/keylayout/Vendor_0001_Product_0001_Version_0100.kl`

保留原 `sunxi-ir.kl` 和全部 legacy 工件；不修改 rc-main、NEC decoder、timeout、DTS/DTBO、Power、rc-map、repeat 或 Settings framework。

## 构建与候选

- 配置：`configs/candidates/m8b-rc-core-r3.json`
- 复用并参数化：`scripts/build-m8b-rc-core-r1-candidate.py`、`scripts/install-m8b-rc-core-input.sh`
- focused test：`tests/test_m8b_rc_core_r3.py`

| 项目 | 大小 | SHA-256 |
|---|---:|---|
| `out/candidates/m8b-rc-core-r3/x12-m8b-rc-core-r3.img` | 1007982592 | `3CF41276615D16A7B319467E5E3F031E52E468E5240AE23835F9C8675AC1D88B` |
| kernel | 23029768 | `FE23BEEAE10389EA13575CA266AF45797F22BCF9BDBA7037AF6F7A8B3148C5E2` |
| `boot.fex` | 67108864 | `0A9473513B309BA3168242500658F35D96EC40B49CA91E33C1068861F8756678` |
| `system_a` | 1651167232 | `4BE3196F39A08380A553F96FE8A364C413402980A96B70743D41FD6C4C16928F` |
| `super.img` | 828183920 | `9D37B5F01ED8F3C9D71EED1FF1C3751A0DCFEABFFF7D9E8D215D81FBEC0848F4` |
| `vbmeta_system.fex` | 1472 | `B2F9947D82B9D3143F2AC948FD097219EC9A1D1D1DBB97B9F9FEB735B85B5EA9` |

派生校验：`Vsuper.fex` `48A393D10BD223D6CD2651B5864E10B6C33D3DCE5F79A7EDA73EE64A4C01DE13`；`Vvbmeta_system.fex` `F8300A41CEF73D8CBB65C653FA9C98D1F5788EDCBC4142F7B3463D4D85C9EB2C`。

## 验证

- 新文件为 regular `0644 root:root`、1848 bytes、SELinux `u:object_r:system_file:s0`。
- 新文件与 `sunxi-ir.kl` 均为 SHA-256 `14FFF2ADF2B5F258AD77483FC5821F699EFAE008FAB28B0493A733AB7EFBC3AD`，`cmp` 同字节；352→DPAD_CENTER、171→SETTINGS 存在。
- r2 boot/kernel 原字节复用；kernel repeat patch 规格不变；`multi_ir` 保持 disabled。
- 相对 r2，system 语义差异只有新 keylayout；Projectivy、provisioning、Power、canonical vendor topology 和 legacy 工件保持。
- LP、AVB、四分区 e2fsck、split SELinux、ELF、IMAGEWTY 外层校验通过；M8B tests 9/9、r12/r13 regressions 6/6、`git diff --check` 通过。

## Payload 差异与首测

相对 r2 仅 `system_a`、`super.fex`、`Vsuper.fex`、`vbmeta_system.fex`、`Vvbmeta_system.fex` 变化；包括 `boot.fex`、`Vboot.fex` 在内的 46 个外层 payload 保持原字节。

首测先确认 `dumpsys input` 显示 `KeyLayoutFile: /system/usr/keylayout/Vendor_0001_Product_0001_Version_0100.kl`，再测试物理 OK、DPAD、HOME、BACK、Power。Settings 全局启动语义和 legacy 清理继续延后。
