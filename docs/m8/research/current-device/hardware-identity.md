# UBOX10 硬件身份

| 项目 | 结论 | 置信度 |
|---|---|---|
| Platform identity | Allwinner H616，4× Cortex-A53；由 DT、kernel 与主板丝印共同确认。H618 销售标签尚无芯片级证据 | 已确认 H616 / 未确认 H618 |
| 主板 | `H616_AXP313A_M1905 V2.1`，日期 `2022-04-18` | 已确认 |
| LED 板标识 | `H616_M1906_LED V2.0` | 已确认 |
| PMIC | AXP313A；系统中的 `axp1530-*` 是同芯片的 BSP 命名 | 已确认 |
| RAM | 8× Micron `D9PQL`，合计 4 GiB；对应 `MT41K1G4RH-125:E` DDR3L 的可能性高 | 高 |
| eMMC | MMY/Huacun `H1DH07DA-601` 系列，标称 64 GB、eMMC 5.1；系统可用 57.6 GiB | 高 |
| Wi‑Fi/BT | AW869A / AIC8800 系列，单天线 | 已确认 |
| `VIC H16S01 2306` | 位于 RJ45 附近，按布局判断是百兆网口隔离磁性器件，不是无线模组 | 较高 |

`F-M 94V-0 E351308 1723` 是 PCB 厂商/阻燃认证类丝印，不作为板型或固件匹配依据。
无需为当前 M8A 路线拆除散热器；如未来必须区分 H616/H618，再补充芯片级 SoC ID 或清晰芯片丝印证据。

参考：
[Micron FBGA 标记查询](https://www.micron.com/sales-support/design-tools/fbga-parts-decoder)、
[同为 H616/8×D9PQL 的 Tanix TX6s](https://linux-sunxi.org/Tanix_TX6s)、
[MMY 64 GB eMMC 条目](https://macrogroup.ru/catalog/moduli-i-mikroskhemy-pamyati/mikroskhemy-pamyati/flash/h1dh07da_601/)、
[AXP313A/AXP1530 上游说明](https://lkml.org/lkml/2023/1/27/1128)。
