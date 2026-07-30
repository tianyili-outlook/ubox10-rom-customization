# Test8r2 运行时基线

采集时间：2026-07-29；DRM API 补采于 2026-07-30。当前运行 Test8r2，另有 6 个用户安装包；这些
`/data/app` 包不计入固件组成结论。

| 范围 | 核心发现 |
|---|---|
| 系统 | Android 12 / SDK 31，Linux 5.4.125，64 位内核、纯 32 位 Android 用户空间，SELinux Permissive |
| 身份 | DT 为 `allwinner,h616`；产品属性伪装为 Pixel 3 / `blueline`，板级平台为 `apollo` / `sun50iw9p1` |
| 产品 | 有 `android.hardware.type.television`，无 Leanback/Leanback-only；Test8r2 无 Remote Service、provider RRO |
| 图形 | Mali-G31，驱动 `r20p0`；只有 `/system/lib`、`/vendor/lib`，无 `lib64`；HWC 工作并输出 3840×2160@60 Hz |
| 受保护图形 | EGL 声明 protected-content 扩展，但 SurfaceFlinger 的 protected context 支持为 0 |
| 媒体 | Allwinner OMX 硬解码公开 AVC/HEVC/MPEG2/MPEG4/VP8/VP9，另有软件 Codec2；未发现 secure codec 名称 |
| 音频 | Audio HAL 7.0；采集时 HDMI 为活动输出 |
| Wi‑Fi/BT | `aic8800_fdrv/bsp/btlpm` 已加载；Wi‑Fi 和蓝牙均工作，蓝牙崩溃计数为 0 |
| 输入 | 红外设备为 `sunxi-ir` 与 `sunxi-ir-uinput`，对应 keylayout 存在 |
| CEC | CEC HAL 和 feature 存在，但采集时 `mIsCecAvailable=false`，不能据此判定功能通过 |
| DRM | Widevine 16.1.0 可由 MediaDrm 打开，但仅为 L3；HDCP connected/max 均为 NONE，AVC/HEVC/VP9 不要求 secure decoder，未发现 secure codec |

结论：

- M8A 可继续做 ARM32 AOSP ATV 产品层迁移。
- M8B 暂停在 64 位图形栈门禁。
- Test8r2 没有 Netflix HD/4K 所需的 L1/HDCP/secure-decoder 证据；N1 实际
  播放可按需要验证，不为对照单独刷回官方 ROM。

只读采集入口为
[`capture-m8-runtime-readonly.ps1`](../../../../scripts/capture-m8-runtime-readonly.ps1)。
本次执行 67 项，9 项因目标路径或组件不存在而返回非零，0 超时。

linkerconfig、APEX、classpath、uses-library 和 VINTF 结果见
[兼容性运行时快照](compatibility-runtime-snapshot.md)。
