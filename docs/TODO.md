# 待办事项

## 当前：M1 只读容器清单

- [ ] 选择并固定可审计的 PhoenixCard/Allwinner 容器解析方案。
- [ ] 编写解析器或包装器，输出 JSON 条目清单（名称、偏移、长度、校验信息）。
- [ ] 交叉验证目录中的预期分区：bootloader A/B、boot A/B、vendor_boot A/B、super、sysrecovery、vbmeta、metadata、dtbo、misc、UDISK。
- [ ] 将工具版本、来源 URL、SHA-256 记录到 `tools/LOCKFILE.md`。

## 后续

- [ ] 准备可靠 UART 连接方案和只读启动日志采集流程。
- [ ] 制定网络故障的无改动证据采集实验。
