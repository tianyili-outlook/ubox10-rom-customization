# M8 status

Updated: 2026-08-01

| Phase | State | Boundary |
|---|---|---|
| M8.0 inventory / M8A.1 design | COMPLETE | Existing device and source evidence |
| M8A.2a offline product build | COMPLETE - VERIFIED OFFLINE | Locked AOSP product build |
| M8A r1 first boot triage | FLASHED / FAILED | Booted through first-stage init; failed on `/metadata` ext4 mount |
| M8A r2 metadata repair candidate | FLASHED / FAILED | Flash failed during download-map fetch (`logs/device/20260801-210354`) due to stale dlinfo CRC |
| M8A r3 dlinfo CRC repair candidate | FLASHED / FAILED | Booted through kernel init (`logs/device/20260801-212804`); failed on first-stage `/oem` mount due to erased `media_data` |
| M8A.2b r4 media_data repair candidate | FLASHED / FAILED | Product flash passed; storage mount errors disappeared, but first-stage init still rebooted to bootloader at 1.105528 s |
| M8A.2b r5 AVB bypass candidate | FLASHED / FAILED - NO HDMI | AVB bypass did not change the failure: first-stage init rebooted to bootloader at 1.112778 s |
| M8A.2b r6 LP-order repair candidate | OFFLINE CHECKED - READY TO FLASH | Rebuilt super with stock interleaved A/B partition-table order; logical payload bytes unchanged |
| M8A.2c boot/init/framework/ADB/HDMI | PENDING | Requires explicit physical authorization |
| M8A.2d TV UI | PENDING | Follows M8A.2c |
| M8B AArch64/multilib | PARKED | No compatible graphics-provider proof |

## Active candidate

ID: `m8a-initial-atv-r6`.

- Path: `out/candidates/m8a-initial-atv-r6/x12-m8a-initial-atv-r6.img`
- Size: 996582400
- SHA-256: `8796B4FC9ABA2D213B044043F979992CE9C5996425D52273A088A04EA3BE5D93`

Triage summary & findings:
- `M8A r5 - FLASHED / FAILED - NO HDMI`；证据：`logs/device/20260801-224818`。
- Product 模式以 `CARD OK` 完成；冷启动到 `Kernel init done` 后在 1.112778 秒由 PID 1 重启到 `bootloader`，与 r4 同阶段、同时间尺度。
- fstab 的四个逻辑分区没有 AVB 标志，因此 r5 的顶层 AVB 绕过被真机证伪。
- 首个剩余的具体 boot-critical 差异是 LP 分区表顺序：原厂为 A/B 交错，r1-r5 super 为全部 A 后全部 B。
- r6 只重建 `super.fex` 为原厂交错顺序；四个逻辑分区回读哈希一致，其他 48 个 IMAGEWTY 条目不变。
- 聚焦测试 3/3、LP 回读、IMAGEWTY 12 个伴随校验和及 `SHA256SUMS` 均通过。

Implementation state: OFFLINE CHECKED - READY TO FLASH（未刷写）。
Next action: 通过 PhoenixCard Product 模式刷写 r6，并抓取冷启动 UART。
