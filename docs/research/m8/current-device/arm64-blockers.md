# ARM64 阻塞项

状态：`M8B BLOCKED`；`M8A GO`。

| 门禁 | 当前事实 | 解锁条件 |
|---|---|---|
| 用户空间 | 1554 个 ARM32 用户空间 ELF，AArch64 用户空间 ELF 为 0 | 取得匹配本板的 64 位用户空间供体 |
| 图形 | Mali EGL、Gralloc、Mapper、HWC、Vulkan 只有 32 位产物 | 找到并实测匹配 H616/`apollo` 的 64 位整套图形栈 |
| 媒体 | Allwinner OMX 能工作，但当前只证明 32 位运行时；无 secure codec | 明确 multilib 进程边界并通过硬解播放回归 |
| 无线 | 内核模块已明确，用户态 HAL/固件 ABI 尚未做 ELF 闭包 | 验证 64 位系统下 AIC8800 HAL 与蓝牙栈 |
| DRM | Test8r2 Widevine 可用但仅 L3，HDCP NONE，无 secure codec | 补官方 ROM 对照；M8B 后重新验证 N1 |
| 供体 | BPI H618 是相邻 SoC；`-a arm64` 不能证明 UBOX10 可用 | 锁定源码版本并检查真实 64 位产物，尤其图形栈 |

ELF 名称级依赖在当前 ARM32 class 内闭合；这不代表 linker namespace 已验证。
APK 内嵌的 AArch64/x86 库和 22 个 AArch64 Kernel module 不构成 64 位 Android
用户空间。

M8A.1 与完整 Android 12 platform source-lock 已完成。下一步准备构建卷并做
M8A.2a 静态构建；目前不需要搜索芯片丝印或下载完整 H618 BSP。
