# UBOX10 M8

M8 replaces the Android product layer with ARM32 Android 12 TV while retaining the stock boot, kernel, vendor, vendor_dlkm, TEE, graphics, media, DRM, wireless, and partition dependencies.

## Current state

- The locked AOSP TV product and the r1-r6 candidate chain are complete offline.
- r1-r5 were flashed and produced useful, recoverable failures.
- `m8a-initial-atv-r6` is **READY TO FLASH**. It has not been tested on the device.
- The next action is a PhoenixCard Product-mode r6 flash plus cold-boot UART capture. Physical flashing still requires explicit user authorization.
- M8B/AArch64 remains parked: current device evidence proves a 64-bit kernel but only a 32-bit graphics/media userspace.

Current artifact: `out/candidates/m8a-initial-atv-r6/x12-m8a-initial-atv-r6.img`, 996582400 bytes, SHA-256 `8796B4FC9ABA2D213B044043F979992CE9C5996425D52273A088A04EA3BE5D93`.

## Start here

| Need | Source |
|---|---|
| Progress, candidate history, current artifact | [M8 status](docs/m8/STATUS.md) |
| Ordered remaining work | [M8 TODO](docs/m8/TODO.md) |
| Build inputs, architecture, and r1-r6 chain | [Build guide](docs/BUILD.md) |
| Flash, UART, and rollback procedure | [Device test guide](docs/DEVICE_TEST.md) |
| Current r6 delta and checks | [r6 record](docs/m8/candidates/m8a-initial-atv-r6.md) |
| Test8r2 hardware/runtime evidence | [Runtime baseline](docs/m8/research/current-device/runtime-baseline.md) |

`configs/candidates/` and `scripts/build-m8a*.py` are the executable source of the candidate chain. `tests/` contains clean-clone unit checks plus artifact checks that activate when local ignored candidate outputs exist. Original firmware, candidate images, raw device logs, APKs, and extracted trees remain local and ignored.

M7 is frozen at the Git tag [`m7`](https://github.com/tianyili-outlook/ubox10-rom-customization/tree/m7); M7-only builders, experiments, and reports are intentionally not duplicated on this branch.
