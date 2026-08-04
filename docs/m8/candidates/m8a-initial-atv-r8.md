# M8A initial ATV r8

状态：**可刷写**

r7 已成功写入，但仍在 `Kernel init done` 后约 312 ms 重启到 bootloader；`/metadata` 根目录变更未改变该故障。r8 仅将 boot header cmdline 设为 `console=ttyS0,115200n8 ignore_loglevel`，用于在下一次 UART 中显示 first-stage init 的首个致命原因。

| 项目 | 值 |
|---|---|
| 镜像 | `out/candidates/m8a-initial-atv-r8/x12-m8a-initial-atv-r8.img` |
| 大小 | 996586496 bytes |
| SHA-256 | `013AA02A59CB4A916CFEA14180824F7CFD781B514D96778C5933009B42B11B80` |
| 相对 r7 的改动 | 仅替换 `boot.fex` 并重建 `Vboot.fex` |
| 离线检查 | 12 个配对 payload 校验通过；r8 聚焦测试 3/3 通过；48 个外层 payload 保持原字节 |

## 刷写步骤

1. 核对镜像 SHA-256。
2. 在 PhoenixCard 选择 Product 模式并写入镜像。
3. 移除卡后冷启动设备。
4. 以 115200 8N1 采集完整 UART。
5. 记录 `Kernel init done` 后的首条 first-stage 致命信息。
