# M8A initial ATV r5

状态：已刷写，失败；无 HDMI，首阶段 init 重启到 bootloader。

## 候选

- 路径：`out/candidates/m8a-initial-atv-r5/x12-m8a-initial-atv-r5.img`
- 大小：996951040 字节
- SHA-256：`B2EE421510BA6D6FE4C224960223DC08A8A8BFD71AD64D092B4FD9BB9E962AF0`
- 基线：r4，SHA-256 `5AFE57DE82B0A42BD3EFB4618375DB896FB0BD7C3C82FF9BD7E817C374C4AAB5`

## 故障证据

- UART：`logs/device/20260801-222006/uart-com3-115200.txt`。
- Product 模式成功写入并校验 `metadata`、`media_data`，随后显示 `CARD OK`。
- 冷启动到 `Kernel init done` 后，PID 1 在 1.105528 秒重启到 `bootloader`。
- 先前 ext4/vfat 错误已消失，UART 没有新的文件系统失败；剩余候选特有首阶段变量收敛为 flags 0 的重建 AVB 根链。

## 修复

- 仅替换顶层 `vbmeta.fex`：algorithm `NONE`、flags `2`、4096 字节，不使用私钥。
- 仅重算 `Vvbmeta.fex`；其余 48 个 IMAGEWTY 条目与 r4 逐字节一致。
- `super`、`boot`、`vendor_boot`、`vbmeta_system`、`vbmeta_vendor`、`metadata`、`media_data` 均未改变。

## 检查

- 聚焦测试：4/4 通过。
- AVB：Algorithm NONE、Flags 2，`verify_image` 通过。
- IMAGEWTY：12 个分区伴随校验和通过，0 错误。
- `SHA256SUMS`：通过；r4 输入哈希前后一致。

## 真机结果

- 证据：`logs/device/20260801-224818`。
- Product 模式成功并显示 `CARD OK`。
- 冷启动到 `Kernel init done` 后在 1.112778 秒重启到 `bootloader`，与 r4 基本一致。
- 顶层 AVB 绕过无效；fstab 逻辑分区项没有 AVB 标志。
- 下一候选：r6，恢复原厂 LP 分区表 A/B 交错顺序。
