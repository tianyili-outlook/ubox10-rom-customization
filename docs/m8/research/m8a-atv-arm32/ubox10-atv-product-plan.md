# UBOX10 ARM32 ATV product 计划

用途：M8A product 设计证据。当前阶段以
[../../STATUS.md](../../STATUS.md) 为准。

## 分层

- 不变：boot0、U-Boot、DTB/DTBO、Kernel 5.4.125、vendor、vendor_dlkm、
  Wi-Fi/BT firmware、遥控/LED、TEE、安全材料和分区表。
- 重建：Android 12 ARM32 `system`、`system_ext`、`product`。
- 继承：ATV system/system_ext/product；不继承 emulator/goldfish vendor。
- 产品选择：Projectivy、LatinIME、ContactsProvider；首版保留
  `AwTvProvision`，其余非硬件 Allwinner UI 不迁移。
- 隔离：GMS、Google Remote Service、DRM 改动和 AArch64 不进入首版。

## 实施顺序

1. Android 12 platform manifest、superproject 和 Test8r2 DRM 已锁定；
   在有足够空间的 WSL/Linux 文件系统准备构建树。
2. 建立 `device/ubox/ubox10`，生成 ARM32 system/system_ext/product；先跑
   分区容量和 AVB 离线门；只对新增/替换 ELF、privapp 和 VINTF 做针对性
   检查。
3. 与 Test8r2 的 boot/vendor/vendor_dlkm 组合最小候选，只验
   zygote32、system_server、SurfaceFlinger、HDMI UI 和 ADB。
4. 再验 TV Settings、Projectivy、实体遥控、音频、Wi-Fi/BT 和硬解。
3. 与 Test8r2 的 boot/vendor/vendor_dlkm 组合最小候选，只验
   zygote32、system_server、SurfaceFlinger、HDMI UI 和 ADB。
4. 再验 TV Settings、Projectivy、实体遥控、音频、Wi-Fi/BT 和硬解。
5. 基础产品稳定后，单独替换 AOSP `TvProvision`；M8.INPUT、M8.GMS、
   M8.DRM 各自作为后续单变量。

首个失败点若位于 VINTF、32 位图形/媒体依赖或最小 UI，先修产品层，不改
vendor 或转向 AArch64。Test8r2 始终是刷回基线。

宿主 C 盘已成功清理出 435.12 GiB 空闲空间，WSL2 Linux/ext4 构建卷（位于 `/home/tianyi/ubox10-aosp/`）可用空间 954 GB，已满足 400 GB 构建卷要求。P0 解除，可以按锁定 revision 启动源码同步与产品构建。
