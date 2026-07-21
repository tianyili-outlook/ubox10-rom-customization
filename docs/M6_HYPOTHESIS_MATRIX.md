# M6 启动失败假设矩阵

## 目的与证据边界

本表将“设备进入 Recovery”拆分为可证伪假设。它不用于挑选下一次刷写内容；在取得被动 UART 冷启动日志前，所有候选镜像刷写仍暂停。

| ID | 假设 | 当前支持证据 | 当前反证/限制 | 最小下一证据 | 当前状态 |
|---|---|---|---|---|---|
| H-01 | BCB / `misc` 指示进入 Recovery | 设备稳定进入 Recovery；离线 `misc.fex` 以零开始 | 没有设备侧 BCB 读取；官方容器文件不能说明当前 eMMC 内容 | UART 中的 boot reason / BCB / recovery 选择日志 | 开放 |
| H-02 | 当前 A/B 槽位、slot-successful 或下载映射不匹配 | 离线 `sys_partition.fex` 倾向 a 槽，设备为 Android 12 A/B 动态分区 | Fastboot 的 `slot-count`、`current-slot` 与所有 `has-slot:*` 都不支持，不能判定当前槽位 | UART 的 U-Boot / Android Boot Control 日志 | 开放 |
| H-03 | AVB 根信任、描述符或 hashtree/FEC 差异使 System 不可启动 | 原件与候选 vbmeta 公钥、算法和 FEC 存在离线差异 | `secure: yes` 只是 Fastboot 变量，不能证明 AVB 结果或锁状态 | UART 中 AVB / dm-verity 错误，随后才设计零内容 AVB 对照 | 高优先级 |
| H-04 | ext4 重建丢失 symlink / ownership / SELinux xattr 等语义 | 提取器使用 `.symlink` 存根，当前重建未恢复元数据 | 尚未完成零内容 round-trip，不能把候选失败单归因于 ext4 | M6b 的机器可读 ext4 语义差分；UART 可确认早期挂载失败 | 高优先级 |
| H-05 | init、挂载或 Framework 启动失败后转 Recovery | Android System 未进入；历史诊断构建叠加过多变量 | 没有 init / kernel 日志，无法定位首次失败点 | UART 从 BootROM 至 init 的完整原始时间线 | 开放 |
| H-06 | Fastboot 本身能够提供完整启动状态 | Fastboot 协议已验证，`product=sunxi`、`secure=yes` | userspace、slot-count、current-slot 与所有 has-slot 变量均不支持 | 不再扩展 Fastboot；使用 UART | 已否定为充分路径 |

## 当前决策

U2 已完成且信息增益耗尽。下一项实验只能是 [UART 被动监听](UART_RUNBOOK.md)：第一次只连接板端 GND 与 TX→适配器 RX，不接 VCC 或适配器 TX。该操作风险为低（接线方向错误则为中），不向设备发送数据。

## 禁止的推断与操作

- 不把 `secure: yes` 当作 AVB、bootloader lock 或当前系统完整性的证明。
- 不把 Fastboot 不支持槽位变量当作“设备没有 A/B”的证明。
- 不执行 `getvar all`、`flash`、`erase`、`download`、`boot`、`continue`、`reboot`、`set_active`、`oem` 或 `unlock`。
- 不在 UART 日志前生成或刷写新的诊断 boot/vendor_boot/vbmeta/Recovery 镜像。
