# M8 status

Updated: 2026-08-15

## Golden baseline

`m8a-initial-atv-r13` 已完成实机验收，状态为 **GOLDEN BASELINE / DEVICE ACCEPTED**。

| 项目 | 结果 |
|---|---|
| 镜像 / SHA-256 | `out/candidates/m8a-initial-atv-r13/x12-m8a-initial-atv-r13.img` / `1D367F7091A7BD6A0791B2CFE45E7AAB551E0312D8C68136548A4927354A8E06` |
| boot / HOME | `sys.boot_completed=1`；Projectivy HOME PASS |
| provisioning | `device_provisioned=1`、`user_setup_complete=1`、`tv_user_setup_complete=1` PASS |
| 遥控 | DPAD、OK、BACK、Volume、HOME PASS |
| Power | 短按休眠、IR Power 唤醒、长按关机 PASS |
| 证据 | `logs/device/20260813-r13/` 的三个 UART 记录 |

## Accepted working baseline

`m8b-rc-core-r5` 已完成实机验收，状态为 **DEVICE ACCEPTED — AUDIO OPEN**。

| 项目 | 值 |
|---|---|
| 镜像 | `out/candidates/m8b-rc-core-r5/x12-m8b-rc-core-r5.img` |
| 大小 | 1007982592 bytes |
| SHA-256 | `7B4D3E28D37CE242F92FF259BB43590EDF422630DA7B515D66E4DF1A000CFA98` |
| 唯一功能变量 | exact device keylayout 中 Linux 171 的 Android 语义由 `SETTINGS` 改为 `MENU` |
| Mouse | intentionally dropped；ff4054 保持 inert |
| payload 差异 | 相对 r4 仅 `system_a`、super/vbmeta_system 及其校验 companions；boot/kernel 原字节不变 |
| 设备结果 | native rc-core/repeat、exact `.kl`、OK/DPAD/HOME/BACK/Volume/Power、Settings→Projectivy menu PASS |

强制回滚仍为 `m8a-initial-atv-r13`：`out/candidates/m8a-initial-atv-r13/x12-m8a-initial-atv-r13.img`，SHA-256 `1D367F7091A7BD6A0791B2CFE45E7AAB551E0312D8C68136548A4927354A8E06`。

## Current audio candidate

`m8b-audio-r1` 状态为 **READY TO FLASH — OFFLINE CHECKED**；尚未刷机，r5 仍是实机验收基线。

| 项目 | 值 |
|---|---|
| 镜像 | `out/candidates/m8b-audio-r1/x12-m8b-audio-r1.img` |
| 大小 / SHA-256 | 1025951744 bytes / `298DCA11DBDFDC81028869C01866411C634FC2C7B979EDA3FB0346BF7434DBDD` |
| 唯一变量 | 把 Test8r2 exact flattened `/system/apex/com.android.vndk.current` 完整恢复到 r5 system |
| runtime APEX 名 | `com.android.vndk.v31` |
| payload 差异 | `system_a`、`super.fex`、`Vsuper.fex`、`vbmeta_system.fex`、`Vvbmeta_system.fex` |
| 保持项 | boot/kernel/ramdisk、vendor_boot、vendor/product/vendor_dlkm、遥控、Projectivy、Power 均不变 |

## r5 device acceptance

| 功能 | 结果 |
|---|---|
| Projectivy / basic UI | **PASS**；可用 TV UI 与一般导航正常 |
| Native rc-core remote | **PASS**；DPAD、OK、BACK、HOME、Volume、Power、Settings→MENU 全部通过；`multi_ir` 保持 disabled |
| Wi-Fi / network ADB | **PASS**；SSID、关联、Internet、Android DNS/connectivity 与 `192.168.1.9:7896` ADB 正常 |
| Ethernet | **PASS**；eth0、Internet、ADB 正常 |
| Bluetooth / HID | **PASS**；service、扫描、配对、iPhone bonding、gamepad UI 控制正常 |
| USB host / storage | **PASS**；EHCI、枚举、Mass Storage/SCSI、block/partition、vold public volume 正常；exFAT 单独不支持 |
| H.264 / HEVC | **PASS**；VLC 使用 Allwinner OMX AVC/HEVC decoder，Cedar/VPU 硬解流畅 |
| Audio | **FAIL — HIGH**；AudioFlinger 无 primary output，带 AAC 的 HEVC 停在 0:00；无音频同视频正常 |

开放功能项：无 IME；exFAT unsupported；选中态渐变白/灰噪点；启用 Wi-Fi 时偶发短暂撕裂/黑屏后恢复；完整 post-resume Wi-Fi/Bluetooth/network 恢复待测；DRM/Widevine、HDMI CEC、VP9 runtime 待验收。启动耗时/错误、thermal/CPU、graphics/rendering、残余 retry loop 和 legacy `multi_ir/uinput` 清理归入后续系统质量里程碑；不得在音频候选中混入。

## Audio failure boundary

- **CONFIRMED first fatal**：clean restart 日志显示 `vndksupport` 无法从 default namespace 加载 unchanged `/vendor/lib/hw/audio.primary.apollo.so`，直接原因是其 `DT_NEEDED libaudioroute.so` 不可解析。随后才出现 DevicesFactory `-19`、AudioFlinger 无 primary、AudioPolicy 无 primary output；HAL 尚未进入 `adev_open`。
- stock 与 r5 Apollo HAL 均为 `6679E7C653D184EC34070F259104CA0FC394CB4DC67DE4BA60134A13B0093791`，排除 HAL 被替换。r5 的 system/vendor/product/APEX 无 `libaudioroute.so`。
- Test8r2 `/system/apex/com.android.vndk.current/lib/libaudioroute.so` 为 ARM32，SHA-256 `BB5393CE70CD1A4AD9ED62814339CA3695788532242708B0D46DAED87D603623`；manifest runtime name 为 `com.android.vndk.v31`，`vndkcore.libraries.31.txt` 包含 `libaudioroute.so`，Test8 linkerconfig 将它由 default namespace 链接到 VNDK namespace。
- 遗漏发生在 AOSP 输出阶段：`/home/tianyi/ubox10-aosp/device/ubox/ubox10/BoardConfig.mk` 没有 `BOARD_VNDK_VERSION := current`，`ubox10.mk` 也未纳入 `com.android.vndk.current`，AOSP `out/.../system/apex` 已无 VNDK APEX；`scripts/build-m8a-candidate.py` 只复制 system 并合并 system_ext，没有裁剪该 APEX。
- r5 vendor 共 228 个唯一 `DT_NEEDED`；其中 55 个属于 Test8 VNDK 合同，r5 已有 54 个，唯一物理缺项为 `libaudioroute.so`。修复仍恢复完整 145-entry exact VNDK APEX，避免继续依赖 no-config fallback 或把单库任意放进 `/vendor/lib`。
- r1 离线确认 Apollo HAL 与 `libaudioroute.so` 的全部传递依赖可解析；exact VNDK 子树逐项一致、SELinux metadata 保持，LP/AVB/e2fsck/SELinux/ELF/外层校验通过。
- `audio_mixer_paths.xml` controls、`audio_platform_info.xml` 的 `sndhdmi`/`audiocodec:4/5` 与 ALSA topology 仅保留为 HAL 成功加载后的第二层假设，本候选未修改。

## Verified progress

| Stage | Result | First useful finding | Next correction |
|---|---|---|---|
| Test8r2 | **ROLLBACK VERIFIED** | Stable ARM32 Android 12 baseline | Retained as preferred rollback |
| AOSP ATV product | **OFFLINE CHECKED** | ARM32 TV system/product/system_ext built from locked Android 12 sources | Assemble with stock hardware stack |
| r1 | **FAILED - `/metadata` mount** | First-stage init could not mount an ext4 metadata partition | Add preformatted metadata payload and download-map entry |
| r2 | **FAILED - flash map CRC** | PhoenixCard rejected the modified `dlinfo.fex` | Recompute dlinfo CRC |
| r3 | **FAILED - `/oem` mount** | Product flash passed; erased `media_data` left required VFAT `/oem` unavailable | Add preformatted media_data payload and descriptor |
| r4 | **FAILED - first-stage reboot** | Both filesystems mounted; PID 1 still rebooted to bootloader at about 1.106 s | Test whether the rebuilt AVB root caused the reboot |
| r5 | **FAILED - first-stage reboot, no HDMI** | Keyless top-level AVB bypass made no material difference; reboot occurred at about 1.113 s | Restore the first remaining concrete LP metadata difference |
| r6 | **FAILED - first-stage reboot** | Stock A/B interleaved LP partition-table order made no material timing change; reboot at 1.096406 s | Restore missing system-root `/metadata` switch-root target |
| r7 | **FAILED - first-stage reboot** | `/metadata` system-root target made no difference; reboot remained about 312 ms after `Kernel init done` | Expose first-stage fatal message on UART |
| r8 | **FAILED - confirmed non-canonical `/vendor`** | `realpath(/vendor) -> /system/vendor` causes required early mount failure, `LOG(FATAL)`, SIGABRT and `InitFatalReboot` | Reverse the vendor link topology to match Test8r2 |
| r9 | **FAILED - framework bootstrap stall** | 已越过 first-stage、SELinux、second-stage、zygote、SurfaceFlinger、bootanimation 并 fork system_server；Lights HAL 缺库令 system_server 主线程阻塞，framework Watchdog 杀死 PID 412 | 恢复 exact Test8r2 ARM32 vendor AIDL `ndk_platform` 兼容库 |
| r10 | **BOOT COMPLETE - NO REAL HOME** | Lights HAL 注册，system_server/zygote 稳定，`package_native`、`sys.boot_completed=1`、SystemUI 和 BOOT_COMPLETED 均完成；HOME 仅解析到 TvSettings FallbackHome | 加入一个真实 Android TV HOME Launcher |
| r11 | **BOOT COMPLETE - HOME OK, REMOTE RAW ONLY** | Projectivy 正常；RemoteIR_RX IRQ、NEC 和 `sunxi-ir/event0` 的 `MSC_SCAN` 正常，但无 `EV_KEY` | 恢复 Test8r2 已验证的 `multi_ir → uinput` 用户态链 |
| r12 | **REMOTE PATH DEVICE VERIFIED - SUPERSEDED BY r13** | exact Test8r2 `multi_ir → uinput` 恢复 ff40 遥控；后续 UI policy 由 r13 完成 | 保留为历史对照 |
| r13 | **GOLDEN BASELINE - DEVICE ACCEPTED** | boot、Projectivy、provisioning、遥控与 Power sleep/wake/shutdown 全部通过 | 作为 M8B 和回滚基线 |
| M8B rc-core-r1 | **FAILED - REPEAT/REPRESS LIFECYCLE** | 实机确认 native rc-core 架构成立，但单次 OK 可拆成两组 DOWN→UP，长按 UP 约每 108 ms 人工 UP→DOWN | 修正 config-off 路径的 new-event 判定 |
| M8B rc-core-r2 | **REPEAT LIFECYCLE PASS - KEYLAYOUT SELECTION FAIL** | native repeat/release、DPAD、HOME/BACK/Power 和物理 KEY_OK 已通过；Android 因设备标识不匹配而加载 `Generic.kl` | 安装 exact vendor/product/version keylayout |
| M8B rc-core-r3 | **FAILED - EXACT FILE FOUND, PARSE REJECTED** | exact keylayout 路径、权限、SELinux 与 SHA 均正确，但 Android 12 parser 在 line 13 拒绝 legacy `WAKE_DROPPED`，EventHub 回退 `Generic.kl` | 完整转换全部不受支持的 label/flag |
| M8B rc-core-r4 | **DEVICE ACCEPTED - SETTINGS SEMANTIC FAIL** | native rc-core/repeat、exact `.kl` 加载、OK/DPAD/HOME/BACK/Power 均通过；物理 Settings 产生 KEY_CONFIG 171→Android SETTINGS 176，但该 keyevent 在当前系统无效果 | 仅把 Linux 171 映射为已验证有效的 Android MENU 82 |
| M8B rc-core-r5 | **DEVICE ACCEPTED - AUDIO OPEN** | native rc-core/repeat、exact `.kl`、Settings→MENU 与全部基础遥控通过；Projectivy、网络、Bluetooth/HID、USB、AVC/HEVC 已验收 | 捕获 Apollo HAL `adev_open` 的首次返回分支，不做 XML card-name 猜测 |

## M8B native rc-core

r1 实机日志为 `logs/device/20260813-m8b-rc-core-r1/uart-coldboot.log` 和 `logs/device/20260813-m8b-rc-core-r1/input-debug.log`。设备已确认 `sys.boot_completed=1`、`multi_ir` 不运行、`sunxi-ir/event0` 直接输出 `EV_KEY`，且独立 UP/OK 均能产生 DOWN→UP，因此 native rc-core 架构已经设备证明。r1 失败点仅为 repeat/release 生命周期：单次 OK 可出现 DOWN→UP→DOWN→UP；长按 UP 约每 108 ms 出现人工 UP→DOWN。

锁定源码 commit `9ab7a758149d3c9b721878a0c18b3f9c5d6c93e6` 的 `drivers/media/rc/rc-main.c` 中，`ir_do_keydown()` 的 `new_event` 无条件包含 `!key_repeat`，而 `key_repeat` 只在 `CONFIG_SUNXI_MULTI_IR_SUPPORT` 分支赋值。r1 关闭该 config 后 `key_repeat` 恒为 false，故每个 NEC repeat frame 都被误判为新按键。r2 仅用条件编译把 `!key_repeat ||` 限定回该兼容分支，不改 decoder、release timeout、DTS、wake、framework、Power、rc-map 或 keylayout。

r2 候选为 `out/candidates/m8b-rc-core-r2/x12-m8b-rc-core-r2.img`，1007978496 bytes，SHA-256 `AE53376C3F902C8B239321E196F7886BFEFEC74C43E66B6FAB50EC100A64F3C8`；kernel SHA-256 `FE23BEEAE10389EA13575CA266AF45797F22BCF9BDBA7037AF6F7A8B3148C5E2`。`r2-verify.log` 已实机确认 DPAD 单击/长按、HOME/BACK/Power 和 clean KEY_OK DOWN→UP，r1 的人工 repeat/repress 周期消失，`multi_ir` 保持 disabled，因此 kernel/native rc-core 修复通过。`r2-kl.log` 显示现有 `/system/usr/keylayout/sunxi-ir.kl` 含 352→DPAD_CENTER、171→SETTINGS，但 input identifier 为 vendor/product/version `0001/0001/0100`，实际加载 `/system/usr/keylayout/Generic.kl`；剩余根因是 Android keylayout 文件名选择，不是 kernel 或 UI focus。

r3 以 r2 镜像为直接基线，只新增 `/system/usr/keylayout/Vendor_0001_Product_0001_Version_0100.kl`；内容与 `sunxi-ir.kl` 同为 1848 bytes、SHA-256 `14FFF2ADF2B5F258AD77483FC5821F699EFAE008FAB28B0493A733AB7EFBC3AD`，元数据为 regular `0644 root:root`、`u:object_r:system_file:s0`。`logs/device/20260815-m8b-rc-core-r3/r3-verify.log` 与 `r3-verify2.log` 已确认 Android 找到该 exact 文件，但 parser 在 line 13 报 `Expected key flag label, got 'WAKE_DROPPED'`，随后回退 `Generic.kl`；因此 r3 状态为 FAILED，路径选择假设已关闭。

r4 只转换 device-specific keylayout，保留 `sunxi-ir.kl` 原字节作参考。对 exact SP1A.210812.015 `InputEventLabels.cpp` 与 `KeyLayoutMap.cpp` 的完整表审计发现不支持 flag `WAKE_DROPPED` 和 labels `APPS`、`BROWSER`、`EXPAND`；分别转换为 `WAKE`、`ALL_APPS`、`EXPLORER`、`TV_ZOOM_MODE`。最终 46 条映射全部落在 parser 支持集合内，无省略；352→DPAD_CENTER、103/108/105/106→DPAD、172→HOME、158→BACK、115/114→Volume、116→POWER、171→SETTINGS 均保持。device keylayout 为 1795 bytes、SHA-256 `C8AB0907D9F7CFCDC9B14370548643DF9BCC03E488C5086D48BC424425A5E398`，元数据继续为 regular `0644 root:root`、`u:object_r:system_file:s0`。boot/kernel 原字节不变，Settings framework 与 legacy 清理继续延后。

r4 现已设备验收：native rc-core/repeat、exact device `.kl` 选择、物理 OK、DPAD、HOME、BACK 与 Power 全部通过。唯一剩余语义问题是物理 Settings 仍输出 Linux `KEY_CONFIG` 171，r4 将其映射为 Android `SETTINGS` 176，而现场 `input keyevent 176` 无效果；`input keyevent 82`（MENU）可打开 Projectivy settings menu，83 为 notifications 且不采用。r5 因此仅把 exact device `.kl` 的 171 从 `SETTINGS WAKE` 改为 `MENU WAKE`，不改 ff4044→KEY_CONFIG、rc-map、kernel、framework、Power 或 Projectivy。

primary evidence 仍使用 `logs/device/20260811-r11/uart-putty_3.log`、`uart-putty_8r2.log`、`uart-putty_8r2_2.log`、`uart-putty_8r2_3.log`，没有重复设备取证。r11 和 Test8r2 的物理 `sunxi-ir/event0` 均只发 `MSC_SCAN`；Test8r2 的 `multi_ir` 读取 event0、打开 `/dev/uinput` 并创建 `sunxi-ir-uinput/event1`，Android 才从 event1 获得 `EV_KEY`。

匹配 Linux 5.4.125 源码是 Orange Pi `orange-pi-5.4-sun50iw9` commit `9ab7a758149d3c9b721878a0c18b3f9c5d6c93e6`。`sunxi-ir-dev.c` 已注册 rc-core raw receiver 和 `RC_MAP_SUNXI`，`ir-nec-decoder.c` 已完成 NEC 解码；缺口不是 decoder，而是占位 rc-map 和 `CONFIG_SUNXI_MULTI_IR_SUPPORT=y`。该兼容分支把 press/release 分别编码成 `01ff40xx`/`00ff40xx` 的 `MSC_SCAN`，绕开普通 `rc_keydown`/`rc_repeat` 路径，直接解释 event0 没有 `EV_KEY`。

rc-core-r1 关闭该 config 分支，并从 exact `customer_ir_ff40.kl` 生成 48 项 native map 和 device-specific `sunxi-ir.kl`。49 项语义全部审计；ff4054 `MOUSE` 不进入 map/keylayout，Mouse mode 明确放弃。`multi_ir.rc` 加入 `disabled`，同时保留 `multi_ir`、rc、`libmultiirservice.so`、`customer_ir_ff40.kl`、`sunxi-ir-uinput.kl` 和 r12 `libinput.so` 作 inert rollback/reference。完整审计见 `docs/m8/candidates/m8b-rc-core-r1.md`。

候选镜像为 `out/candidates/m8b-rc-core-r1/x12-m8b-rc-core-r1.img`，1007978496 bytes，SHA-256 `E3F40ECFB2FE867EB6C04988E0C3207C49E1B1073AF42A2B41FFF3A7C3DBBCE0`。kernel 为 `D5AEED79EF04D3DF838385AD857AC81268C4CACDA986545016F5CEE7E45FE289`，`system_a` 为 `DC7B9EF4814E04F8EB4671E609D2ACD22CD7CB6218B5443B7D74E28793D0A9C5`，`super` 为 `3093AF2DC57BA45C15F0D01F6F7BB6C08A67FAEB75EFF81672D787F67BCCCA0D`，`vbmeta_system` 为 `F68247A300DB60E3512BCAF1B2240B43DF92004996D67CDB9FCC2E4AB73B1BFA`。

相对 r13，system 文件差异仅为 `/system/etc/init/multi_ir.rc` 和 `/system/usr/keylayout/sunxi-ir.kl`；boot 仅更换 kernel，ramdisk 未变。`vendor_a`、`product_a`、`vendor_dlkm_a`、vendor_boot、DT/DTBO、持久 bootargs、顶层 vbmeta、Projectivy、provisioning、Power RRO 和 r10 兼容库均保持。kernel build、LP、AVB、四分区 e2fsck、split SELinux compile、ELF/DT_NEEDED、外层校验、3 项 M8B focused tests 与 6 项 r12/r13 回归测试通过。设备侧仍需验证 native repeat/release 和 r13 Power wake 对等性。

## r13 TV provisioning 与 Power policy

主证据为 `logs/device/20260812-r12/20260812-r12-09-home-keypath-uart.log`、`20260812-r12-11-power-reboot-policy-uart.log`、`20260813-r12-12-home-postreboot-uart.log` 和 `20260813-r12-13-tv-setup-home-uart.log`。r12 的 IR/uinput/HOME 事件与 Projectivy resolver 均正常；WindowManager 拒绝 HOME 的直接原因是 `Not going home because user setup is in progress`。`device_provisioned=1` 和 `user_setup_complete=1` 重启后仍不足，补上 `secure tv_user_setup_complete=1` 后无需重启即可进入 Projectivy。因此 HOME/provisioning 根因确认为缺少 TV 专用 setup flag，不是遥控、Launcher 或 HOME resolver。

r13 从锁定的 Test8r2 镜像恢复 `/system_ext/priv-app/AwTvProvision/AwTvProvision.apk`（SHA-256 `D74DF03C4BBAB8ADCFC543D9F34D98C87178A63D15F66785B1EE3D286EDB68D8`）和 `/system_ext/etc/permissions/provision-permissions.xml`（SHA-256 `98C3C29A10F4956BBAB65F74E405E7B3F8DF20C262A22FF7FCC755C0F92F7E6A`）。该 direct-boot-aware、优先级 1 的 HOME/DEFAULT/SETUP_WIZARD 组件在首次 HOME 时写入 `device_provisioned=1`、`user_setup_complete=1`、`tv_user_setup_complete=1`，随后禁用自身，使 Projectivy 继续作为真实 HOME。当前 `ubox10.mk` 虽列出 `AwTvProvision`，但本地源码树没有对应 `vendor/aw` 模块，r12 构建输出也没有 APK；因此采用锁定 Test8r2 工件作为可复现输入，不恢复完整 SetupWizard，也不使用启动 shell hack。

Power 输入链已确认到达 `PhoneWindowManager`。r12 的 `framework-res.apk` 默认 `config_shortPressOnPowerBehavior=1`，但 `/vendor/overlay/framework-res__auto_generated_rro_vendor.apk` 是优先级 0 的静态 RRO，并把该值覆盖为 0；现有 product TV RRO 优先级为 -1，且只设置长按值 3。Android 12 当前实现初始化时读取资源，不读取已试验的 `power_button_short_press` Global setting，所以该 runtime setting 重启后仍不能改变行为。r13 新增平台签名的 `/system_ext/overlay/M8TvPowerPolicyOverlay.apk`（SHA-256 `B695200E1153F750B3BF1CD92228EE6E360BA7B12608CB56019D316017481C91`），优先级 1，仅定义短按值 1；解析结果为 `SHORT_PRESS_POWER_GO_TO_SLEEP`。它不定义长按资源，现有值 3 和 `LONG_PRESS_POWER_SHUT_OFF_NO_CONFIRM` 保持不变。

r13 解包差异仅为 `AwTvProvision` 目录/APK、allowlist、`system_ext/overlay` 目录和 Power RRO，无意外 system 文件差异。Projectivy、`multi_ir`、`multi_ir.rc`、三个 ff40/sunxi keylayout、`libmultiirservice.so`、r12 `libinput.so`、r10 两个兼容库、canonical `/vendor`、现有 SELinux/ueventd 合同均按 SHA-256/元数据保持不变。`vendor_a`、`product_a`、`vendor_dlkm_a` 与 r12 原字节一致；LP、AVB、四分区 e2fsck、split SELinux compile、ELF/DT_NEEDED、IMAGEWTY 外层校验和 focused tests 均通过。r13 已实机验收并冻结为 GOLDEN；M8B rc-core 已转为 active work，Mouse mode intentionally dropped。

r13 `system_a` 为 `28118A3316F1845A174667B527125C0FA750A719EFA0CF94FB88DC197FAE2055`，`super.img` 为 `FFAC0283599D9FE44383642843EA5A4645E09C140FD53CCB769196EA05A57200`，`vbmeta_system.fex` 为 `2A2AAA0F67BA2729834FC26B735AC8B5E0445EE88623C1758FCD99C62FB609BB`。

## r11 遥控根因与 r12 修复

主证据为 `logs/device/20260811-r11/uart-putty_3.log`、`uart-putty_8r2.log`、`uart-putty_8r2_2.log` 和 `uart-putty_8r2_3.log`。r11 与 Test8r2 的物理 `sunxi-ir/event0` 均只输出 `MSC_SCAN`；Test8r2 另由 root 进程 `/system/bin/multi_ir` 读取 event0 并打开 `/dev/uinput`，创建可输出 `EV_KEY`/`EV_REL` 的 `sunxi-ir-uinput/event1`，Android 对 event1 加载 `sunxi-ir-uinput.kl`。因此 r11 根因不是 kernel rc-map 失效，而是 system composition 没有恢复 Test8r2 的 Allwinner `multi_ir → uinput` 用户态链。

ff40 映射的 exact 来源是 Test8r2 `/system/usr/keylayout/customer_ir_ff40.kl`（SHA-256 `DB54F9843081DDC492F9BDD35E7EE341EBCB4562991513CB5B7A26BBBC74DE39`）。已知现场键对应为 11/14/16/17/13/66/26/21/28 → UP/DOWN/LEFT/RIGHT/CENTER/BACK/HOME/VOL+/VOL-；Power 为 77（raw `ff404d`），mouse-toggle 为 84（raw `ff4054`，标签 `MOUSE`）。完整 49 项 active scancode 映射已写入 r12 候选记录和 `remote-source.json`。

r12 恢复 7 个 Test8r2 exact system 工件：`multi_ir`、`multi_ir.rc`、`customer_ir_ff40.kl`、`sunxi-ir.kl`、`sunxi-ir-uinput.kl`、`libmultiirservice.so` 以及 Test8r2 `libinput.so`。前六项组成当前遥控的 runtime 与三层映射；`libinput.so` 是唯一替换项，用于恢复 r11 parser 缺少的 Allwinner `MOUSE`等 input label，避免整套旧 framework 回退。`libmultiir_jni.so` 无 DT_NEEDED 边且 Test8r2 运行进程未映射；`virtual-remote.kl` 不被当前物理或虚拟设备选中；`customer_ir_4040.kl` 不属于 ff40，故均未恢复。

mouse-toggle 状态、DPAD 到 pointer 的转换、重复定时与指针移动均由 exact `/system/bin/multi_ir` 实现；其创建的 uinput 设备输出 `EV_REL REL_X/REL_Y` 和 `EV_KEY`。r11 已保留与 Test8r2 同字节的 vendor policy、file_contexts 和 ueventd 合同：`multi_ir`/`multi_ir_exec`、`uhid_device`、`input_device`、Binder/service_manager 权限俱在，`/dev/uinput` 为 `0660 uhid:uhid`；无需改 SELinux 或 ueventd。

r12 `system_a` 为 `7ECF3B7891F012D296BC8C0A44684011E1FD83796F33AB01371A9700B89DBDDB`，`super` 为 `D08A974C5E9AD646E1B38512A4AA80041D37C37ED043F16509BE1E786639B540`，`vbmeta_system` 为 `28D42D0874B5749272C42EC4B42DA9EACE56BC518A314F9952EF06944DD7F924`。相对 r11，仅 `system_a`、`super.fex`、`Vsuper.fex`、`vbmeta_system.fex`、`Vvbmeta_system.fex` 变化；Projectivy、r10 两个兼容库、`vendor_a`、`product_a`、`vendor_dlkm_a` 与其他外层 payload 原字节不变。

## r10 boot complete 与 r11 HOME 修复

完整现场证据为 `logs/device/20260811-r10-first-boot/r10-first-boot-putty_2.log`。采集时 `sys.boot_completed=1`、`init.svc.bootanim=stopped`，system_server PID 415、zygote PID 244、SystemUI PID 781 均稳定；Lights HAL、`package_native`、SystemUI 和 BOOT_COMPLETED 已完成，r9 framework blocker 已解决。

当前 resumed HOME 是 `com.android.tv.settings/.system.FallbackHome`（PID 970，`mResumed=true`、`mActivityType=home`）。HOME query 只返回该 FallbackHome；Leanback query 只有 TvSettings 的 `.MainSettings`，显式启动 `MAIN+LEANBACK_LAUNCHER` 返回 unable to resolve。FallbackHome 每约 500 ms 输出 `User unlocked but no home; let's hope someone enables one soon?`，手动 HOME 仍回到 FallbackHome。因此白底“安博科技”画面属于 ImageWallpaper + FallbackHome，confirmed 根因是产品中没有真实 Launcher，不是 bootanimation 或 framework stall。

源码 composition 的遗漏点是 `/home/tianyi/ubox10-aosp/device/ubox/ubox10/ubox10.mk`：它只显式加入 `AwTvProvision`，所继承的 `atv_product.mk` 只加入 TV overlay；把 `TvSampleLeanbackLauncher` 加入 `PRODUCT_PACKAGES` 的 `aosp_tv_arm.mk` 未被继承。源码候选中，`TvSampleLeanbackLauncher` 和 Launcher3 都缺少 `LEANBACK_LAUNCHER`，Live TV 只有 Leanback 入口而不是 HOME，均不满足本项目 TV HOME 合同。

Test8r2 的构建记录把 Projectivy 4.71 安装到 `/system/app/ProjectivyLauncher/ProjectivyLauncher.apk`，并把默认 HOME 属性设为 `com.spocky.projengmenu/com.spocky.projengmenu.ui.home.MainActivity`；APK SHA-256 为 `6818FC2DB44411A605CA4D7067FB9D7227AAEF2414CFF42DE58FE13E9321B47A`。其同一 exported activity 同时声明 MAIN、HOME、DEFAULT 和 LEANBACK_LAUNCHER，要求 leanback、支持 ARM32，无 required shared library；它是项目已有的现代、遥控器友好桌面，因此 r11 复用 exact APK，不恢复旧厂商 `SimpleLauncher.ap`。

r11 仅新增 `/system/app/ProjectivyLauncher` 和其中 APK。`system_a` 为 `7E3BA3A79583CA29E50BAD7FC5DF1543E7B931FB53E4F88F6FFFB90AA2D9CB69`，`super` 为 `A81947E01D5300B417A6748393758494C3106E809B81478B3FD19793524952CC`，`vbmeta_system` 为 `E73DF3D2EA4A955934DFF5272B4D24FA568597E3E7A8DE240EE47C34A0CCB594`。相对 r10，仅 `system_a`、`super.fex`、`Vsuper.fex`、`vbmeta_system.fex`、`Vvbmeta_system.fex` 变化；r10 两个 compatibility library、canonical `/vendor` topology 和全部无关 logical/outer payload 保持原字节。

`device_provisioned=0`、`user_setup_complete=0` 且没有 Setup package 是已记录的后续产品决策，不是当前 HOME 缺失根因。r11 不修改这两个值；先确认真实 Launcher 能在现状下进入桌面，再单独选择 SetupWizard 或个人 TV Box 默认 provisioned 策略。

## r9 framework stall 与 r10

最新证据为 `logs/device/20260807-001357-r9-framework-stall/uart-putty.log`。安静启动仅使用 `console=ttyAS0,115200 loglevel=1`，未加入此前 fatal-panic 诊断参数，故障仍完整复现。r9 已越过 early mounts、SELinux、second-stage init、zygote、SurfaceFlinger、bootanimation，并启动 system_server。

`/vendor/bin/hw/android.hardware.lights-service` 反复因缺少 `android.hardware.light-V1-ndk_platform.so` 无法链接。system_server PID 412 随后停在 `ServiceManager.waitForDeclaredService` → `LightsService$VintfHalCache.get` → `LightsService.<init>` → `SystemServer.startBootstrapServices`；00:01:50.991 framework Watchdog 明确输出 `WATCHDOG KILLING SYSTEM PROCESS`，00:01:50.993 输出 `GOODBYE`。zygote PID 239 于 00:01:51.112 记录 system_server PID 412 因 signal 9 退出并自行退出，init 再启动 zygote；采集时新 system_server 为 PID 1028。直接 kill 来源已确认为 framework Watchdog，先前 llkd 假设已证伪；llkd PID 328 当时仍在运行且不在 kill 链中。

`aidl/package_native` 持续未注册发生在 system_server 尚未越过 LightsService/bootstrap 阶段时，是 PackageManager 尚未继续初始化的下游结果，不是本轮首因。rebootescrow HAL 同时缺少 `android.hardware.rebootescrow-V1-ndk_platform.so`，但它不是已证明的主阻塞点。

r9、Test8r2 与原厂 `vendor_a` 均为 `BB91A8B7ED4AC0145F434F89FD76865EB4311F234AA46D67C8373A7CD5B4929A`；Lights HAL 和 rebootescrow HAL 二进制逐字节一致。两个缺失库仅存在于 Test8r2/原厂 `system_a` 的 `/system/apex/com.android.vndk.current/lib/`，均为 ARM32、0:0、0644、`system_lib_file`。r9 AOSP 产品配置未设置 `BOARD_VNDK_VERSION`，产品包清单也没有两个接口库；仓库原组合链把该 system 与 stock vendor 合并时没有导入 Test8r2 的 vendor AIDL compatibility payload，因此 r9 中两个文件物理不存在。

匹配 Android 12 host linkerconfig 对 r9 实际 system/vendor/product 输入的离线生成结果不含 `dir.vendor`：r9 同时缺少 `com.android.vndk.v31` APEX，故 `/vendor/bin` 的 linker 配置匹配失败并进入 bionic no-config fallback，ARM32 搜索顺序为 `/system/lib`、`/odm/lib`、`/vendor/lib`。r10 因此不导入整套 VNDK APEX、不修改 linkerconfig 或 vendor，而以单一规则恢复 exact Test8r2 ARM32 vendor AIDL `ndk_platform` 双库到 `/system/lib`。两库来自同一 Test8r2 system 分区、同一版本和同一遗漏链，rebootescrow 因而与 lights 一并纳入；`libaudioroute.so` 等无关缺项未改。

r10 新增文件：

- `/system/lib/android.hardware.light-V1-ndk_platform.so`：`57ED3A999D158EE449D6621897275610B0479B0F06B7EFB1005AF397099BF663`
- `/system/lib/android.hardware.rebootescrow-V1-ndk_platform.so`：`F26AA210060D449AA2D0ED8B7341DB28BA072A6F1DD4AF31BB2005E427636AB0`

r10 `system_a` 为 `99130EDE6615F1C72743D74BDBE7F7FC08B92AA002D146EEB3469600F87E419F`，`super` 为 `E0AB7D19635A559DC505EEAF0FBFD7CACB441950CB6E94EAFBB3990351B3D90A`，`vbmeta_system` 为 `6D65C50C26BD7E6F0BB8CC92D37D146A49AF398386D3DDB1813A0765F5B7611D`。相对 r9，仅 `system_a`、`super.fex`、`Vsuper.fex`、`vbmeta_system.fex`、`Vvbmeta_system.fex` 变化；`vendor_a`、`product_a`、`vendor_dlkm_a`、boot、vendor_boot、顶层 vbmeta 和其余 46 个外层 payload 原字节不变。

## r4-r8 limited startup-chain review

### Log mapping

| Version | Evidence |
|---|---|
| r4 boot | `logs/device/20260801-222006` |
| r5 boot | `logs/device/20260801-224818` |
| r6 boot | `logs/device/20260801-232812` |
| r7 flash / boot | `logs/device/20260804-233745` / `logs/device/20260804-235259` |
| r8 boot | `logs/device/20260805-220923` |
| r8 volatile U-Boot diagnostic | `logs/device/20260805-233154-r8-uboot-diagnostic` |
| r8 volatile fatal-panic diagnostic | `logs/device/20260806-212631-r8-fatal-panic` |
| r8 volatile `/dev/kmsg` diagnostic | `logs/device/20260806-221823-r8-devkmsg-on` |
| Test8r2 normal boot | `logs/device/20260805-223511` |

r7 flash completed with `CARD OK` and `sprite success`; its boot evidence is the separate `20260804-235259` capture.

### Aligned events and first confirmed divergence

| Event | Test8r2 | r4-r8 |
|---|---|---|
| Runtime kernel command line | UART does not print a final command-line line | UART does not print a final command-line line; r8's exact added string is absent |
| Kernel and first-stage source | Stock kernel and stock boot-ramdisk init | Same stock kernel and boot-ramdisk init; stock vendor_boot ramdisk and `fstab.sun50iw9p1` retained |
| `Kernel init done` | 0.800555 s | r4 0.801224; r5 0.812560; r6 0.796053; r7 0.784518; r8 0.796057 s |
| First-stage mount / dynamic partition evidence | Reports invalid `/metadata` ext4 at 0.904080 s, invalid media_data VFAT at 0.942298 s, then `Could not update logical partition` at 1.142640 s and continues | No explicit success/failure marker for dm or `/metadata`, `/oem`, `/system`, `/vendor`, or `/product`; absence is not treated as success |
| switch-root / `selinux_setup` / second stage | No explicit transition marker in the window; later console and Android services prove the normal boot continued | No explicit transition marker before reboot; none of these stages is claimed as reached |
| Termination | No reboot; init continues | Orderly `reboot: Restarting system with command 'bootloader'` at r4 1.105528, r5 1.112778, r6 1.096406, r7 1.096870, r8 1.108413 s |

The first confirmed runtime divergence is therefore the failure action itself: r8 requests an orderly bootloader reboot while Test8r2 continues through later init work. The exact internal step before that request is not observable. Metadata and media_data return differences occur earlier in the normal log, but are intentional filesystem-input differences and do not identify the repeated r4-r8 failure.

The newer volatile U-Boot capture supersedes the original r8 capture for the current boundary. Its runtime kernel command line contains `console=ttyAS0,115200 loglevel=8 ignore_loglevel`; first-stage starts at 3.375881 s, switches to `/first_stage_ramdisk` at 3.400748 s, completes `/metadata` check and mount, mounts `dm-0` at 3.582748 s, requests bootloader restart at 3.605221 s, and reboots at 3.802562 s. LP metadata order plus slot `_a` and the stock fstab identify `dm-0` as `system_a` mounted at `/system`.

The latest fatal-panic capture is now authoritative for the termination path. Its runtime command line contains `console=ttyAS0,115200 loglevel=8 ignore_loglevel androidboot.init_fatal_panic=true`; first-stage starts at 3.400620 s, switches to `/first_stage_ramdisk` at 3.425459 s, completes the `/metadata` check and mount, mounts `system_a` as `dm-0` at 3.656223 s, triggers SysRq `c` at 3.679616 s, and panics at 3.684228 s. PID 1 is `init`; the system reboots after the configured five-second panic timeout. The panic stack is only the kernel SysRq write path, not the initiating userspace stack. The following boot lacks the volatile diagnostic arguments and is not a separate failure.

`20260806-221823-r8-devkmsg-on` 取代上述日志成为根因证据。运行时参数完整包含 `console=ttyAS0,115200 loglevel=8 ignore_loglevel printk.devkmsg=on androidboot.init_fatal_panic=true`。`vendor_a`、`product_a`、`vendor_dlkm_a` 分别创建为 `dm-1`、`dm-2`、`dm-3`；`system_a` 于 3.777677 s 挂载到 `/system`，3.788731 s 执行 `Switching root to '/system'`。随后 3.798753 s 报告 `realpath(/vendor) -> /system/vendor`，3.809241 s 的 `/vendor` 挂载失败，3.815898 s required early partitions 失败，3.824048 s 捕获 signal 6，3.843190 s 触发 crash。根因为 **confirmed**。

### Handoff findings

- The boot-header diagnostic path remains ineffective, but the verified volatile `setargs_mmc` route produces the intended runtime parameters and is now the authoritative r8 diagnostic evidence.
- The first-stage executable is the unchanged stock boot-ramdisk `/system/bin/init` (`SHA-256 2A7D6E125583C79E925B5D916C54C51E4AE8EE145F2D7422B2DD77D0B6C62751`); the stock vendor_boot fstab is also unchanged.
- Matching Android 12 control flow is: mount `/metadata`, create logical devices, mount `system_a` at `/system`, call `SwitchRoot("/system")`, then mount vendor/vendor_dlkm/product and finally exec the new `/system/bin/init selinux_setup`. 最新日志已确认第二次 switch-root 被调用；首个失败分支是随后对 `/vendor` 的 canonical 检查。
- At that switch, the top-level mount targets are `/system/dev`, `/system/proc`, `/system/sys`, `/system/mnt`, `/system/debug_ramdisk`, `/system/second_stage_resources`, and `/system/metadata`. Every target is an actual directory in both r8 and Test8r2 with matching mode, uid, gid, link count, and no symlink; only inode numbers differ. A missing or wrong-type switch-root target is not supported.
- Test8r2 and r8 first differ deterministically at the mounted system handoff: Test8r2 `/system/bin/init` is 1624080 bytes (`382507769EBB4ED0B6853DE73719301716082634F6BF04FF45AD3DB51ED7DF5D`), while r8 is 1622456 bytes (`272FB078122961ADEE30414CE24699A2F2E1A42EE201B1EDE202C6E91E47BC95`). r8 init is a valid executable ARM32 ELF using `/system/bin/bootstrap/linker`; the interpreter and checked key libraries are present. The UART does not prove that switch-root executed this binary.
- The exact r8 system/system_ext plus stock vendor 31.0 CIL inputs compile successfully with the locked Android 12 host `secilc`. A general ELF/interpreter failure and a deterministic split-policy compile incompatibility are not supported.
- The first-stage fatal path is **confirmed**: `/vendor` canonical 检查失败后 required early mounts 返回失败，触发 `LOG(FATAL)`、SIGABRT（signal 6）和 exact init 的 `InitFatalReboot`；watchdog、外部复位和 U-Boot 主动复位均已排除。
- The missing handler output is explained by the first-stage logging path. Android 12 `KernelLogger` keeps one opened `/dev/kmsg` FD; the exact kernel defaults each such FD to ten userspace messages per five seconds. The capture contains exactly ten `init:` records on that FD before silence, and the command line has no `printk.devkmsg` override. The original fatal text, `InitFatalReboot: signal`, unwind frames, and `Trigger crash` are subsequent writes and are rate-limited. Moving `/dev` does not invalidate the open FD; the direct `/proc/sysrq-trigger` write bypasses `/dev/kmsg`. Signal-handler logging and unwinding are also not async-signal-safe, but that is now a secondary fallback explanation rather than the first missing-output mechanism.
- The exact kernel accepts `printk.devkmsg=on`, which disables this userspace `/dev/kmsg` rate limit for one boot. `print-fatal-signals=1` is not equivalent because init installs handlers for the relevant fatal signals, so the kernel's default fatal-signal reporting path is not guaranteed to run.
- The exact stock init supports `androidboot.first_stage_console=1`: the debug product build enables `ALLOW_FIRST_STAGE_CONSOLE`, includes the matching first-stage console implementation, and creates `/dev/console` as major 5 minor 1. The exact boot has `console=ttyAS0,115200`, and the kernel confirms `console [ttyAS0] enabled`. The ramdisk has an executable ARM32 dynamic `/system/bin/sh`, its linker and `libc.so`, and root retains `CAP_SYS_PTRACE` before SELinux policy load; `CONFIG_SECURITY_YAMA` is off.
- The stock ramdisk has no `/first_stage.sh`, `strace`, `gdbserver`, `simpleperf`, `perf`, `debuggerd`, `crash_dump`, or ptrace-capable toybox applet. `toybox`, `toolbox`, `sh`, `setsid`, and `nohup` are present, but the relevant executables are dynamic ARM32 binaries and cannot provide the required signal metadata or syscall ring by themselves.
- LP ordering, top-level AVB flag, missing `/metadata` root directory, HDMI DDC, GPT fallback, invalid init architecture/interpreter, and deterministic CIL compile incompatibility are not current root-cause candidates.

r9 条件已满足。Test8r2 的实际结构为 `/vendor` 实体目录和 `/system/vendor -> /vendor`；r8 的方向相反。AOSP device `BoardConfig.mk` 未声明独立 vendor image，触发 `system/core/rootdir/Android.mk` 的 `/vendor -> /system/vendor` 分支，仓库原 system builder 又保留了该布局。r9 在仓库构建链中加入可复现的 topology 修复；r8d1 保持停放且未构建。

r9 的 `system_a` 为 `64FC2C65894C7EF36781DEDD87E1722A258F06E3361749A3AE274E24C955D851`，`super` 为 `F69E1201B432D9EFD6937B251B9CBE7AE215A0CF738A5D711605CABD6DA28FA4`，`vbmeta_system` 为 `5AA1E40EB8198BE0E6C350FAFED9E95A9F3B9AA93CA637314D0A303CE3C0FFCA`。r8 的 `vendor_a`、`product_a`、`vendor_dlkm_a` 哈希在 r9 中逐字节不变；stock fstab 和 exact first-stage init 所在的 `vendor_boot.fex`、`boot.fex` 也保持原字节。

Raw UART logs and candidate images are intentionally local under ignored `logs/` and `out/` paths. Git retains the concise findings, builders, configs, hashes, and focused validators; it does not pretend a clean clone contains the large artifacts.

## Boundaries

- No physical action was performed during the 2026-08-02 repository cleanup.
- r10 已在实机完成 framework boot；r9 Lights/Watchdog/llkd 方向保持关闭，不再修改。
- r13 是当前 GOLDEN BASELINE；Projectivy、provisioning、遥控和 Power sleep/wake/shutdown 均以实机 UART 为准。
- M8B native rc-core 遥控迁移已在 r5 设备验收并关闭；Mouse mode intentionally dropped，legacy multi_ir 工件保留为 inert reference，后续仅在独立清理候选处理。
- 当前 board、DT 与 runtime 证据识别为 H616。设备运行 64 位 kernel，但没有已证明可用的 AArch64 Android graphics userspace；本轮不扩展到 64 位 userspace。
- `m8b-audio-r1` 只恢复 exact VNDK APEX；未修改 mixer、audio platform XML、DTS、machine driver 或已验收功能。

## Next action

经用户另行授权后刷写 `m8b-audio-r1`。先确认 `com.android.vndk.v31` active、`libaudioroute.so` 可见且旧 `dlopen ... libaudioroute.so not found` 消失，再检查 primary HAL/output 并播放已知 HEVC+AAC；若仍失败，只记录 HAL 成功加载后的新首错，不预改 mixer/ALSA topology。
