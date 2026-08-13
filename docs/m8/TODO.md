# M8 TODO

## 当前工作：M8B native rc-core

- [x] 将 `m8a-initial-atv-r13` 标记为实机验收通过的 GOLDEN BASELINE。
- [x] 完成 Linux 5.4.125 `sunxi-rc-recv`、NEC、rc-core、rc-map 与 MSC-only 分支的 exact offline audit。
- [x] 从 exact ff40 语义生成 48 项 native rc-map 和 device-specific `sunxi-ir.kl`；49 项已逐项审计，ff4054 Mouse intentionally inert。
- [x] 禁用 `multi_ir` 自动运行，同时保留 legacy binary、rc、keylayout、libraries 作 inert rollback/reference。
- [x] 构建并限定验证 `m8b-rc-core-r1`。
- [ ] 刷入 `x12-m8b-rc-core-r1.img`，确认 `sunxi-ir` 直接输出 `EV_KEY`，且没有 `sunxi-ir-uinput`、`multi_ir` 不运行。
- [ ] 验收 UP/DOWN/LEFT/RIGHT、OK、BACK、HOME、VOL+/VOL-、POWER。
- [ ] 验收单击、长按 repeat、release，无 double press、sticky key 或 release 后继续导航。
- [ ] 回归 Projectivy HOME、短按 Power 休眠、IR Power 唤醒和长按 Power 关机。

## rc-core-r1 通过后

- [ ] 在独立 `rc-core-r2` 中删除已确认无运行依赖的 multi_ir/uinput legacy 工件；不在 r1 提前清理。
- [ ] 保持 Mouse mode dropped，不重新引入 vendor mouse framework。

## 后续设备检查

- [ ] 检查 IME、Wi-Fi、Ethernet、Bluetooth、音视频、CEC、重启、冷启动和 r13/Test8r2 回滚。
- [ ] 根据实测结果处理 Google TV Remote/Play、Netflix 和 Widevine。

## 暂停项

- [ ] 仅在确认匹配本机板的 64 位 Mali/Gralloc/Mapper/HWC/Vulkan provider 后恢复 64 位 Android userspace 工作；当前硬件事实仍为 H616。
