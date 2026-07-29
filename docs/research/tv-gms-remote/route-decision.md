# Test9r2 后路线决策

决策日期：2026-07-29。

## 决策

选择 `S3 / 收束 32 位 remote`。

- Test8r2 继续作为唯一稳定基线。
- 不制作 Test9r3。
- 不制作 Test10p1。
- 不在当前 32 位分支继续修改 framework startup gate、Play Store/GMS、
  package visibility 或设备身份。
- 官方 Google TV 手机遥控的产品化、默认权限与重启验收转入 M8.INPUT。
- TV Play Store 与 Google 组件一致性转入 M8.GMS。
- 当前 M7 剩余工作进入 Test9.3：目标应用、AirPlay、现代文件管理器和整体
  回归。

## 依据

Test9r2 已完成其技术探针使命：

- 修正后的 system_ext RRO 生效；
- provider/framework/uinput 路径工作；
- 仅临时授予 `BLUETOOTH_CONNECT` 后，Remote Service 稳定监听
  6466/6467 并发布 Remote v2 mDNS；
- 官方 Google TV iPhone 应用可以发现、TLS 配对、操控和输入文字。

因此 S1/Test9r3 在技术上并非不可行，但它需要从 Test8r2 移除 leanback，
再修改并重建 Android 12 framework 的 `TvRemoteService` startup gate，
同时补齐默认运行时权限。它仍不能解决当前手机型 Play/GMS 与 TV 产品定义
不一致的问题。

S2/Test10p1 需要合法、版本和签名一致的 Android 12 ARM32 TV Google 组件集。
当前没有经过验证的闭合 donor；继续混装 Play Store、GMSCore、Setup 和
Remote Service 会扩大变量并损害可归因性。

用户选择不在 M7 继续承担这两条平台集成风险。既然核心协议已经通过，额外
32 位候选带来的信息增量低于完成当前产品化收尾和建立真正 ATV product 的
价值。

## Test9r2 的最终地位

- Remote stack：`R2-REMOTE-PASS`。
- 整机候选：`PARTIAL`。
- 稳定基线资格：无。
- 后续构筑基线：Test8r2，不从 Test9w1、Test9r1 或 Test9r2 派生。
- 本轮设备侧唯一临时变化：userdata 中授予
  `android.permission.BLUETOOTH_CONNECT`；未改变只读分区。
- Play Store：仍为 not compatible，禁止把 Test9r2 留作日常固件。

## 当前执行顺序

1. 用户方便时刷回 Test8r2。
2. 在 Test8r2 上完成 Test9.3 用户态应用、AirPlay、现代文件管理器和整体
   回归；不重新开启 32 位 Google Remote 候选。
3. M8.0 接收 Test9r2 runtime report，继续只读 inventory 和 Android 12 ATV
   source-lock。
4. M8A 建立真正 ARM32 AOSP ATV product 后，以 M8.INPUT/M8.GMS 独立门禁
   恢复官方手机遥控和 TV Google 组件。

运行证据见 [test9r2-runtime-report.md](test9r2-runtime-report.md)。
