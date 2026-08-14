# M8B rc-core-r2 candidate

状态：**OFFLINE CHECKED — READY FOR FOCUSED DEVICE TEST**

基线：**m8a-initial-atv-r13 — GOLDEN BASELINE / DEVICE ACCEPTED**

前代：`m8b-rc-core-r1` 的 native rc-core 架构已实机证明，但 repeat/release 生命周期失败。本轮未刷机、未执行设备命令。

## 根因与单变量修复

锁定 Orange Pi kernel commit `9ab7a758149d3c9b721878a0c18b3f9c5d6c93e6` 的 `drivers/media/rc/rc-main.c`。`ir_do_keydown()` 的 `new_event` 原本无条件包含 `!key_repeat`；但 `key_repeat` 只在 `CONFIG_SUNXI_MULTI_IR_SUPPORT` 分支赋值。r1 关闭该 config 后，每个 repeat frame 因 `!key_repeat == true` 被误判为新按键，造成先 keyup 再 keydown。

r2 的唯一修复是在 exact source 上把现有 `!key_repeat ||` 包入：

```c
#ifdef CONFIG_SUNXI_MULTI_IR_SUPPORT
                    !key_repeat ||
#endif
```

补丁：`configs/candidates/m8b-rc-core-r2/rc-main-repeat.patch`，SHA-256 `70A316DA67274FC2ED2584CCC090DC4282E6D740FFA04EE3C3B47DA2CD266549`。该零上下文补丁只在锁定 commit 的两个确定行号插入条件编译，构建时用 `git apply --unidiff-zero --check` 验证。`CONFIG_SUNXI_MULTI_IR_SUPPORT` 继续关闭；decoder、release timeout、DTS、wake、framework、Power、native rc-map、Android keylayout 和 disabled multi_ir 合同均不变。

## 构建输入

- `configs/candidates/m8b-rc-core-r2.json`
- `configs/candidates/m8b-rc-core-r2/rc-main-repeat.patch`
- `.gitattributes`（固定 patch 为 LF，避免 Windows checkout 改变锁定哈希）
- `scripts/build-m8b-rc-core-kernel.sh`
- `scripts/build-m8b-rc-core-r1-candidate.py`（现有 M8B 构建链参数化，r1 默认路径保留）
- `tests/test_m8b_rc_core_r2.py`

## 候选与哈希

| 项目 | 大小 | SHA-256 |
|---|---:|---|
| `out/candidates/m8b-rc-core-r2/x12-m8b-rc-core-r2.img` | 1007978496 | `AE53376C3F902C8B239321E196F7886BFEFEC74C43E66B6FAB50EC100A64F3C8` |
| kernel Image | 23029768 | `FE23BEEAE10389EA13575CA266AF45797F22BCF9BDBA7037AF6F7A8B3148C5E2` |
| `boot.fex` | 67108864 | `0A9473513B309BA3168242500658F35D96EC40B49CA91E33C1068861F8756678` |
| `system_a` | 1651167232 | `466D1E1CD40591D28FE71244C69F52CDA490530BFC99BFC32C280AEB90844D43` |
| `super.img` | 828179824 | `1C39829EF3696A6AEE94E1FFFFD800298AC07B18EAA2F7AC13EB34EB319D51C9` |
| `vbmeta_system.fex` | 1472 | `95A38ECF077DC7687547741B1ABAFCF74C68D11B9E2AA54764325A8C66116A82` |

派生校验：`Vboot.fex` `6B69B4881683275DA4E226A31A408FCB070044C2E1703FBF745D56A623077765`；`Vsuper.fex` `AB7194BB0C84B3443797CE3004F901EF881BDA403C390C3AC0ADA1357C70D519`；`Vvbmeta_system.fex` `BB36E80A6A99122055414A12EC939C47C6B6EA1B8B43BF1BE86AC234FA9339D0`。

## Payload 差异

相对 r13，变化为 `boot/kernel`、`boot.fex`、`Vboot.fex`、`system_a`、`super.fex`、`Vsuper.fex`、`vbmeta_system.fex`、`Vvbmeta_system.fex`。boot 变化来自 kernel；system 仍只有 r1 的 `multi_ir.rc` 与 `sunxi-ir.kl` 文件合同，候选 ID、固定 AVB salt 和 ext4 重组使 system/super/vbmeta 字节变化。`vendor_a`、`product_a`、`vendor_dlkm_a` 及其余 44 个外层 payload 原字节不变。

## 限定验证

- exact patch 已通过 `git apply --unidiff-zero --check`；锁定 kernel tracked source 未被原地修改。
- kernel source diff 仅为 `rc-main.c` 两行条件编译和 r1 已有的生成 `rc-sunxi-keymaps.c`；`git diff --check` 通过。
- r1/r2 rc-map SHA-256 同为 `E16FA743F02C6EC480E006B4DA6D6CF21EDB4BC17334D23128F048E83100FE42`；`sunxi-ir.kl` 同为 `14FFF2ADF2B5F258AD77483FC5821F699EFAE008FAB28B0493A733AB7EFBC3AD`。
- `multi_ir` 保持 disabled；legacy 工件保持 inert；r13 Projectivy、provisioning 和 Power 合同冻结。
- kernel、LP、AVB、ext4、SELinux、ELF/DT_NEEDED、IMAGEWTY 外层限定检查通过。
- M8B r1/r2 focused tests 6/6、r12/r13 回归测试 6/6 通过。

## 首次设备测试

刷入后把现场记录为 `r2-verify.log`。只测试：UP 单击、OK 单击、OK 连续按、UP 长按约 2 秒后释放。成功要求 event0 保持 native `EV_KEY`、每次单击仅一组 DOWN→UP、长按期间只有标准 repeat 且不出现周期性人工 UP→DOWN、释放后无 sticky/navigation continuation。legacy multi_ir/uinput 清理推迟到 r2 实机验收后。
