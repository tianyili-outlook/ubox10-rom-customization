# Test8r2 ELF 依赖摘要

共识别 1667 个 ELF：partition/APEX 1560、APK/JAR 内嵌 85、Kernel module 22。

## ABI

| Partition | ARM32 userspace | AArch64 userspace | Other platform ELF | Packaged ELF | Kernel modules |
|---|---:|---:|---:|---:|---:|
| product | 7 | 0 | 0 | 3 | 0 |
| system | 1247 | 0 | 6 | 82 | 0 |
| vendor | 300 | 0 | 0 | 0 | 0 |
| vendor_dlkm | 0 | 0 | 0 | 0 | 22 |

## 关键栈

| Stack | ARM32 | AArch64 |
|---|---:|---:|
| graphics | 17 | 0 |
| media | 69 | 0 |
| Wi-Fi/BT | 43 | 0 |

## 名称级依赖检查

该检查只比较同 ELF class 的 SONAME/文件名，不代表 linker namespace 已通过。

- ELF32 未解析名称：0
- ELF64 未解析名称：0

## 决策

- 未发现 AArch64 用户空间 ELF；当前系统仍是纯 ARM32 用户空间。
- APK 内嵌的其他 ABI 不等于系统具备对应平台 ABI。
- 下一门禁是 64 位 Mali/Gralloc/Mapper/HWC/Vulkan 完整闭包。
