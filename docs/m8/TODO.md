# M8 active TODO

## Offline validation completed

- [x] `m8a-initial-atv-r4` 已完成真机测试：刷写成功，`metadata`/`media_data` 错误消失，但首阶段 init 仍在 1.105528 秒重启到 bootloader。
- [x] `m8a-initial-atv-r5` 已完成真机测试：AVB 绕过未改变首阶段失败，1.112778 秒重启到 bootloader，无 HDMI。
- [x] `m8a-initial-atv-r6` 聚焦离线验证通过：super LP 表恢复原厂 A/B 交错顺序，逻辑分区内容不变。

## Pending only with explicit physical authorization

- [ ] 通过 PhoenixCard Product 模式刷写 `m8a-initial-atv-r6`，并抓取冷启动 UART；本任务未执行刷写。
- [ ] Perform M8A.2c boot/init/framework/ADB/HDMI observation using the recovery readiness runbook.
- [ ] Capture the first relevant UART/ADB evidence without changing device state.
- [ ] If needed, recover with Test8r2, then official stock.
- [ ] Perform M8A.2d launcher/HOME/IME/provisioning and minimal TV UI validation.
- [ ] Check remote, network, audio/video, Bluetooth, CEC, DRM/Widevine, reboot, cold boot, and rollback.

## Follow-up product risks

- [ ] Resolve or intentionally remove configured-but-undelivered AwTvProvision.
- [ ] Establish launcher/default HOME and IME behavior.
- [ ] Verify Projectivy delivery before claiming it.
- [ ] Treat runtime Binder/HAL/SELinux/VINTF/graphics/media/DRM/connectivity as device findings, not offline claims.

M8A r6 已完成离线验证，等待下一次真机刷写结果。
