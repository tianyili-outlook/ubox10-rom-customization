# M8 TODO

## 当前工作：M8B native rc-core

- [x] 将 `m8a-initial-atv-r13` 标记为实机验收通过的 GOLDEN BASELINE。
- [x] 完成 Linux 5.4.125 `sunxi-rc-recv`、NEC、rc-core、rc-map 与 MSC-only 分支的 exact offline audit。
- [x] 从 exact ff40 语义生成 48 项 native rc-map 和 device-specific `sunxi-ir.kl`；49 项已逐项审计，ff4054 Mouse intentionally inert。
- [x] 禁用 `multi_ir` 自动运行，同时保留 legacy binary、rc、keylayout、libraries 作 inert rollback/reference。
- [x] 构建并实机验证 `m8b-rc-core-r1`：native `sunxi-ir/event0 → EV_KEY` 架构成立；因 repeat frame 被误判为新按键而失败。
- [x] 实机验证 `m8b-rc-core-r2`：repeat/release、DPAD、HOME/BACK/Power 和 native KEY_OK 通过；`multi_ir` 保持 disabled。
- [x] 确认 r2 Android 实际加载 `Generic.kl`，未选择已存在的 `sunxi-ir.kl`。
- [x] 构建并限定验证 `m8b-rc-core-r3`：仅新增 exact `Vendor_0001_Product_0001_Version_0100.kl`。
- [x] 实机确认 r3 找到 exact 文件，但 Android 12 parser 拒绝 legacy `WAKE_DROPPED` 并回退 `Generic.kl`。
- [x] 构建并限定验证 `m8b-rc-core-r4`：完整审计 46 条映射并转换全部不受支持的 label/flag。
- [ ] 刷入 r4，先确认 `dumpsys input` 选择 exact device-specific keylayout，再先测物理 OK，随后测 DPAD、HOME、BACK、Power。
- [ ] 回归 Projectivy HOME、短按 Power 休眠、IR Power 唤醒和长按 Power 关机。

## rc-core-r4 通过后

- [ ] 单独决定 `KEYCODE_SETTINGS` 全局行为；不在 r4 同时修改 framework。
- [ ] 在后续独立候选中删除已确认无运行依赖的 multi_ir/uinput legacy 工件；不在 r4 提前清理。
- [ ] 保持 Mouse mode dropped，不重新引入 vendor mouse framework。

## 后续设备检查

- [ ] 检查 IME、Wi-Fi、Ethernet、Bluetooth、音视频、CEC、重启、冷启动和 r13/Test8r2 回滚。
- [ ] 根据实测结果处理 Google TV Remote/Play、Netflix 和 Widevine。

## 暂停项

- [ ] 仅在确认匹配本机板的 64 位 Mali/Gralloc/Mapper/HWC/Vulkan provider 后恢复 64 位 Android userspace 工作；当前硬件事实仍为 H616。
