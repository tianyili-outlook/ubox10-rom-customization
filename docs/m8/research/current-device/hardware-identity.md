# UBOX10 硬件身份

| 项目 | 结论 | 置信度 |
|---|---|---|
| SoC | Allwinner H616，4× Cortex-A53 | 已确认 |
| 主板 | `H616_AXP313A_M1905 V2.1`，日期 `2022-04-18` | 已确认 |
| LED 板标识 | `H616_M1906_LED V2.0` | 已确认 |
| PMIC | AXP313A；系统中的 `axp1530-*` 是同芯片的 BSP 命名 | 已确认 |
| RAM | 8× Micron `D9PQL`，合计 4 GiB；对应 `MT41K1G4RH-125:E` DDR3L 的可能性高 | 高 |
| eMMC | MMY/Huacun `H1DH07DA-601` 系列，标称 64 GB、eMMC 5.1；系统可用 57.6 GiB | 高 |
| Wi‑Fi/BT | AW869A / AIC8800 系列，单天线 | 已确认 |
| `VIC H16S01 2306` | 位于 RJ45 附近，按布局判断是百兆网口隔离磁性器件，不是无线模组 | 较高 |

`F-M 94V-0 E351308 1723` 是 PCB 厂商/阻燃认证类丝印，不作为板型或固件匹配依据。
散热器下芯片无需拆除：设备树、内核和主板丝印已经共同确认 H616。

参考：
[Micron FBGA 标记查询](https://www.micron.com/sales-support/design-tools/fbga-parts-decoder)、
[同为 H616/8×D9PQL 的 Tanix TX6s](https://linux-sunxi.org/Tanix_TX6s)、
[MMY 64 GB eMMC 条目](https://macrogroup.ru/catalog/moduli-i-mikroskhemy-pamyati/mikroskhemy-pamyati/flash/h1dh07da_601/)、
[AXP313A/AXP1530 上游说明](https://lkml.org/lkml/2023/1/27/1128)。
