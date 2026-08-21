# Android 16 Prototype A r2 candidate

状态：**OFFLINE CHECKED CANDIDATE / NO PHYSICAL AUTHORIZATION**。Gate 2 继续 **CLOSED**；本候选尚未刷写或启动，不得据此启动 Prototype B。

## Purpose and runtime cause

r1 的 RAM-only `printk.devkmsg=on` 证据把第一可重复失败定位到 Android 16 process-group 初始化，而不是 APEX activation。`CgroupSetup()` 对 required v1 blkio 的 mount 因 retained kernel `CONFIG_BLK_CGROUP=n` 返回 `EINVAL`，并在创建 cgroup-v2 `/sys/fs/cgroup/system` 前退出。Init 虽然 fork 了 ueventd 和 apexd-bootstrap child，但 parent 的 `createProcessGroup()` 无法创建 `system/uid_0`，child 在 task profiles、credentials/caps 与 `ExpandArgsAndExecv()` 前 fatal exit。二者都未 exec，bootstrap APEX 没有被尝试。

Exact A16 `/system/etc/cgroups.json` 同时要求 blkio、cpu、cpuset；retained config 还缺少 `CONFIG_CPUSETS`，所以只启用 BLK_CGROUP 不足。Memory-v2 descriptor 是 optional，故本轮不引入 MEMCG。`libprocessgroup` 与 early `libprocessgroup_setup` 都消费同一 `cgroup_v2_sys_app_isolation=true` build flag，不存在 system/app hierarchy 路径不一致。

## Bounded change and provenance

Base 是已接受离线审计但实机失败的 `a16-prototype-a-r1` 外层镜像，1,261,038,592 bytes / SHA-256 `A034C8193236C93746E5962CB3E7F26A1D56CEC1435D5AD9D95F653B60BEBD83`。Kernel source 固定为 `https://github.com/orangepi-xunlong/linux-orangepi.git` commit `9ab7a758149d3c9b721878a0c18b3f9c5d6c93e6`；compiler 为 AOSP Android 12 `clang-r416183b1`（clang 12.0.7）。Retained rc-core patch 与 generated exact ff40 keymap 仍由 config/hash 锁定。

唯一有效 kernel config delta：

```text
CONFIG_BLK_CGROUP=y
CONFIG_CPUSETS=y
CONFIG_PROC_PID_CPUSET=y
```

最后一项由 Kconfig 自动启用。`CONFIG_MEMCG`、`CONFIG_BLK_DEV_THROTTLING`、`CONFIG_BLK_CGROUP_IOLATENCY` 与 `CONFIG_BLK_CGROUP_IOCOST` 保持关闭；generic blkio hierarchy/membership 不要求这些 policy。Builder 对任何其他 effective config 变化 fail closed。

Candidate boot 保持 r1 的 header、cmdline、ramdisk、AVB hash-footer algorithm/properties/salt 与 partition size，只替换 kernel。外层仅替换 `boot.fex` 并生成对应 `Vboot.fex`；system/APEX、super/LP、vendor_boot/ramdisk、vendor/product/vendor_dlkm、vbmeta/vbmeta_system、bootloader/TEE/DTBO/GPT/rollback 与其他 48/50 payload 原字节保持。没有物理设备命令。

## Artifacts

| 工件 | 大小 | SHA-256 |
|---|---:|---|
| `out/candidates/a16-prototype-a-r2/x12-a16-prototype-a-r2.img` | 1261038592 | `114DF8677CD6984EB1431377723EDF61C80ACF26C15D8770BAE47DCFE7D1B6D0` |
| `out/candidates/a16-prototype-a-r2/boot.fex` | 67108864 | `4F0DB0070E294DEA93319F4B21335E6725DBB7B70066E7C1E6BF55CFEB09C10C` |
| `kernel-build/Image` | 23232520 | `5D7D7F84A8E3CBCC4A4AF78A9EB4DECAC846E62BA4C681E85B438B69B196EBF3` |
| `kernel-build/candidate.config` | 141009 | `0F2284289AE5374296EA180F128BFEE12F648D75A1BBE575AE21F50A8582E02E` |

Artifacts 与 raw logs 留在 GCP ignored paths。构建/audit 证据位于 `/work/build-logs/ubox10-a16-gate2-cgroup/20260821T180108Z/`；detached compile/pack 和 resumed audit 总 wall 约 13 分 03 秒，其中包含约 3 分钟 host mount 权限停顿，已完成的 kernel/outer 没有重编。21 个采样中 available RAM 最低 31,036,456 KiB、无 swap，`/work` available 最低 182,048,014,336 bytes。

## Offline audit

- kernel config：required CGROUPS/BLK_CGROUP/CGROUP_SCHED/CPUSETS/CPUACCT/FREEZER/BPF 均为 `y`；PROC_PID_CPUSET 为 `y`；optional MEMCG 为 `n`。
- cgroup integration：A16 system cgroups/task profiles hashes、required v1 set、v2 root/controller optionality、API31 override absence、accepted vendor override absence与 shared Soong flag 全部重新核对。
- boot/AVB：candidate boot embedded footer 和 SHA-256 hash verify PASS；accepted boot properties/salt/ramdisk 保持；vbmeta 与 vbmeta_system 原字节保持。
- outer：IMAGEWTY verify PASS；50 entries 中 boot replacement 与 Vboot companion 之外 48 项原字节保持；base r1 hash 在构建前后不变。
- filesystem/LP/APEX：system、vendor、product、vendor_dlkm read-only e2fsck PASS；r1 system/APEX/super 与所有 logical extents 原字节保持，沿用已通过的 APEX/LP fit 审计。
- VINTF：对 exact r2 config 的 full check exit 65，唯一错误仍为继承的 `CONFIG_NFS_FS=y` 对 FCM 6 `n`；cgroup delta 未引入新 incompatibility，未把该结果误称 PASS。
- linker/ELF/SELinux：相关 r1 system/vendor/product 分区原字节保持后，继承 exact linker namespace/name-level ELF closure 与 split-policy compile PASS；runtime enforcing 未证明。
- integrity：candidate `SHA256SUMS` 全部 PASS；r2 focused 5 tests 与全量 75 tests PASS（25 个 expected fixture skip）；rollback `m8b-remote-r1`、Test8r2 与 stock assets 未改。

## Decision and next boundary

r1 的故障是 **bounded retained-kernel cgroup integration defect before exec**，不是 bootstrap APEX activation failure，也不是已证明的 ARM32 architecture-level blocker。r2 已把 source-proven minimum 闭合，并在离线范围内足够一致，可供一次未来单独授权的 UART-first ARM32 exact-board boot。

当前没有物理授权。若用户未来另行明确授权，唯一下一实验是只启动 r2 一次，并在 U-Boot RAM-only bootargs 临时加入 `printk.devkmsg=on`，确认 blkio/cpuset hierarchy、`/sys/fs/cgroup/system`、ueventd/apexd exec 以及第一条新的 runtime 边界。不得把离线结果写成 bootability、Gate 2 success 或 Prototype B authorization。
