# Test8r2 DRM service inventory

| 层 | 发现 |
|---|---|
| 进程 | 32 位 `drmserver` 正在运行 |
| plugin | `/vendor/lib/mediadrm/libwvdrmengine.so`、`libdrmclearkeyplugin.so` |
| HAL | VINTF 文件声明 DRM 1.4 Widevine/ClearKey；`lshal` 仅见 legacy passthrough 1.0 wildcard，未见 1.4 实例 |
| TEE | 两个 OP-TEE TA 文件存在；未证明被 Widevine L1 使用 |
| boot | `ro.boot.drmkey=false` |
| API | Widevine 与 ClearKey 均可由 MediaDrm 打开 |

当前有效路径是 legacy 32 位 plugin/drmserver。VINTF 声明、TA 文件和 display
protected-buffer flag 都不能把实际 `L3` 结果提升为 L1。
