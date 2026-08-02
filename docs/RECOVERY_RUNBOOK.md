# UBOX10 刷写与恢复操作指南

## 1. 固件与工具镜像列表

| 角色 | 路径 | 文件大小 (字节) | SHA-256 |
|---|---|---:|---|
| r4 修复候选镜像 | `out/candidates/m8a-initial-atv-r4/x12-m8a-initial-atv-r4.img` | 996952064 | `5AFE57DE82B0A42BD3EFB4618375DB896FB0BD7C3C82FF9BD7E817C374C4AAB5` |
| Test8r2 回滚镜像 | `C:\Users\tiany\Documents\ubox10-rom改造\out\candidates\test8r2-restore-contacts-provider-r1\x12-test8r2-restore-contacts-provider.img` | 2005954560 | `6A52F3388E9ABF6AFA8A701CFD7198FE6C0090F16531F6E3BD3949E760892EC8` |
| 官方原厂恢复镜像 | `C:\Users\tiany\Documents\ubox10-rom改造\x12-1024.img` | 2018890752 | `371A653604618E8B78786F279EA6F64E5D1028B430C9B41F330B08456A264065` |
| PhoenixCard 工具 | `C:\Users\tiany\Documents\ubox10-rom改造\tools\PhoenixCard_v4.2.7\Tool\PhoenixCard.exe` | 不适用 | 不适用 |

## 2. 制作 PhoenixCard 烧写卡

1. 打开 `PhoenixCard.exe`。
2. 插入 TF 卡，选择对应的盘符。
3. 选择待烧写的镜像文件（如 `x12-m8a-initial-atv-r4.img`），校验文件大小与 SHA-256。
4. 写入模式选择 **Product**（生产模式）。
5. 点击烧卡，等待提示烧卡成功（100%）。
6. 安全拔出 TF 卡。

## 3. 板端烧写与冷启动观察

1. 将 UBOX10 完全断电。
2. 插入制作好的 Product 模式 TF 卡。
3. 按照 [UART_RUNBOOK.md](UART_RUNBOOK.md) 准备并启动 900 秒串口捕获。
4. 接通 UBOX10 原装电源，开始板端烧写。
5. 观察串口日志直至显示 `CARD OK` 与烧写完成。
6. 将 UBOX10 断电，待指示灯熄灭后**拔出 TF 卡**。
7. 再次接通电源进行冷启动，观察 BootROM/U-Boot/Kernel/Init/SystemUI/HDMI 启动全过程。

## 4. 回滚与恢复流程

若 r4 镜像启动异常需回滚：
1. 断电拔出 TF 卡。
2. 使用 `x12-test8r2-restore-contacts-provider.img` 按照第 2、3 步重新制作烧写卡并烧写。
3. 烧写完成后拔卡冷启动，验证系统恢复。
4. 若 Test8r2 恢复失败，使用官方原厂镜像 `x12-1024.img` 重复第 2、3 步进行原厂恢复。
