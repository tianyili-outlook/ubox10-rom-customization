# M8A initial ATV r7

状态：**READY TO FLASH**。

| 项目 | 值 |
|---|---|
| 固件 | `out/candidates/m8a-initial-atv-r7/x12-m8a-initial-atv-r7.img` |
| 大小 | 996586496 |
| SHA-256 | `3098E1B238B60A39A8D93AAD3BF80EE6295338F99BD021F2A8C452168E6A370B` |

r6 已刷写，但仍在 `Kernel init done` 后约 300 ms 执行 `reboot bootloader`。r7 仅在 `system_a` 根目录新增空的 `/metadata`：原厂 system 根目录存在该切换根目录目标，候选缺失；vendor_boot fstab 将 metadata 作为 first-stage 挂载。

除 `super.fex` 与其 `Vsuper.fex` 外，外层 48 个 payload 保持不变；逻辑 `vendor`、`product`、`vendor_dlkm` 字节保持 r6 原样。

定向测试 2/2、IMAGEWTY 12/12 和 SHA256SUMS 均通过。
