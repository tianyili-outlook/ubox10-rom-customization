# M8A initial ATV r6

状态：已完成聚焦离线检查，尚未刷写。

## 候选

- 路径：`out/candidates/m8a-initial-atv-r6/x12-m8a-initial-atv-r6.img`
- 大小：996582400 字节
- SHA-256：`8796B4FC9ABA2D213B044043F979992CE9C5996425D52273A088A04EA3BE5D93`
- 基线：r5，SHA-256 `B2EE421510BA6D6FE4C224960223DC08A8A8BFD71AD64D092B4FD9BB9E962AF0`

## 首错与修复

- r5 在 `Kernel init done` 后 1.112778 秒由 PID 1 重启到 `bootloader`；Android 尚未进入可输出 HDMI 的阶段。
- r5 的 AVB 绕过未改变故障，且 first-stage fstab 的逻辑分区项没有 AVB 标志。
- r1-r5 的 super LP 表顺序为全部 A 后全部 B；原厂为 `system_a/system_b`、`vendor_a/vendor_b`、`product_a/product_b`、`vendor_dlkm_a/vendor_dlkm_b`。
- r6 只替换 `super.fex` 并重算 `Vsuper.fex`，恢复原厂交错顺序。

## 检查

- 四个逻辑分区从新 super 回读后与 r1 输入逐字节一致。
- LP 三个主副本槽位结构有效，主表顺序与原厂一致。
- 其他 48 个 IMAGEWTY 条目与 r5 一致。
- 聚焦测试 3/3、IMAGEWTY 12/12、`SHA256SUMS` 通过。

## 下一步

通过 PhoenixCard Product 模式刷写 r6，移除烧录卡后冷启动并抓取 UART。
