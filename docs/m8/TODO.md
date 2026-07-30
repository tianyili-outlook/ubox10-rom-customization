# M8 当前 TODO

只记录尚未完成的工作。已完成内容和历史路线不在这里维护。

## P0：解除构建阻塞

- [x] 准备至少 400 GB 可用的 Linux/ext4 构建卷。
- [x] 记录构建路径、实际空闲空间和清理方式。

## P1：M8A.2a 离线 product

- [ ] 按锁定 revision 同步 Android 12 源码。
- [ ] 建立 UBOX10 device/product 目录；继承 AOSP ATV product 层。
- [ ] 保留现有 boot、Kernel、vendor、vendor_dlkm、DTB/DTBO、TEE 和 ARM32
  Vendor ABI。
- [ ] 保留 `AwTvProvision`；不引入 emulator/goldfish/generic_x86 硬件层。
- [ ] 构建 system/product/system_ext，核对分区容量与打包路径。
- [ ] 只对新增/替换 ELF 和可疑 VINTF 项做针对性检查。

## P2：首个 M8A candidate

- [ ] 在 [CANDIDATES.md](CANDIDATES.md) 建立单变量定义。
- [ ] 确认 PhoenixCard、官方镜像和 Test8r2 回退。
- [ ] 按核心启动 → HDMI 画面 → TV UI 的顺序刷测。
- [ ] 保存第一条重复 fatal 和本轮差异；一次只修一个原因。
- [ ] 达到日常 TV UI 后执行轻量 candidate 验收。

## 后续横向项

- [ ] M8.INPUT：把 Test9r2 已证明的 Remote v2 合同迁入原生 product。
- [ ] M8.GMS：建立 TV Google 组件/权限/overlay/package visibility 清单。
- [ ] M8.DRM：只验证保留后的播放能力，不修改安全材料。
- [ ] M8B：等待真实 AArch64 图形供体；当前不下载 H618 BSP。

已完成：M8 当前设备 inventory、Test8r2 DRM 与兼容性运行时快照、Android 12
source-lock、M8A product 差异、分区预算和产品计划。
