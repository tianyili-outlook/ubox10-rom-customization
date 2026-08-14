# M8B rc-core-r1 candidate

状态：**FAILED — REPEAT/REPRESS LIFECYCLE；NATIVE ARCHITECTURE DEVICE PROVEN**

基线：**m8a-initial-atv-r13 — GOLDEN BASELINE / DEVICE ACCEPTED**

本轮未刷机、未执行设备命令。

## 实机结果

证据为 `logs/device/20260813-m8b-rc-core-r1/uart-coldboot.log` 和 `input-debug.log`。r1 已确认 boot complete、`multi_ir` disabled、物理 `sunxi-ir/event0` 直接产生 `EV_KEY`，独立 UP/OK 均有完整 DOWN→UP，故 native rc-core 架构成立。

r1 未通过 repeat/release：单次 OK 可拆成 DOWN→UP→DOWN→UP；长按 UP 约每 108 ms 重复人工 UP→DOWN。exact source 显示 config-off 路径中的 `key_repeat` 恒为 false，而 `new_event` 无条件检查 `!key_repeat`，从而把每个 NEC repeat frame 当成新按键。后继 r2 只修正这个条件，不回退架构。

## 基线与单变量

r13 实机已确认 boot complete、Projectivy HOME、三个 provisioning flag、基础遥控、短按 Power 休眠、Power 唤醒和长按 Power 关机全部通过。M8B rc-core-r1 的唯一功能变量是把遥控运行路径从 `multi_ir → /dev/uinput` 切换为 kernel native rc-core `EV_KEY`；Mouse mode 明确放弃。

## exact kernel audit

- 平台证据仍为 H616，kernel 为 ARM64 Linux 5.4.125；未把销售标签提升为硬件事实。
- r13 `boot.fex` SHA-256 为 `6492F90E46671DDB10EAE030DF2AFF89FEF2AF821D458E458935F2ABF263D457`；其中 kernel 为 23029768 bytes，SHA-256 `5D21D37115D82346CC1D9545743609CA71EBAF56F0B8FC95FC817E711661E25E`。
- 匹配源码为 Orange Pi `orange-pi-5.4-sun50iw9` 的 `9ab7a758149d3c9b721878a0c18b3f9c5d6c93e6`，编译器为 Android clang r416183b1 12.0.7。
- `sunxi-ir-dev.c` 已通过 `rc_allocate_device()` / `rc_register_device()` 注册 `sunxi-rc-recv`、`sunxi-ir`、`RC_DRIVER_IR_RAW` 和 `RC_MAP_SUNXI`；NEC 解码在 `ir-nec-decoder.c` 完成。
- 原 `rc-sunxi-keymaps.c` 只有占位项 `{ KEY_ESC, KEY_ESC }`。
- r13 开启 `CONFIG_SUNXI_MULTI_IR_SUPPORT=y`。该分支在 `rc-main.c` 把按下/释放编码成 `MSC_SCAN`：按下增加 bit 24，形成 `01ff40xx`；释放清除 bit 24，形成 `00ff40xx`，专供 userspace `multi_ir`，因此 event0 没有标准 `EV_KEY`。
- 同文件的非 multi_ir 分支已具备 `rc_keydown()`、`rc_repeat()` 和 rc-core 原生释放定时；无需重写 NEC decoder、IR driver、DTS 或 wake 配置。

## 实现

1. 从 exact Test8r2 `/system/usr/keylayout/customer_ir_ff40.kl`（SHA-256 `DB54F9843081DDC492F9BDD35E7EE341EBCB4562991513CB5B7A26BBBC74DE39`）生成 48 项 `RC_MAP_SUNXI` 映射。
2. 关闭 `CONFIG_SUNXI_MULTI_IR_SUPPORT`，启用现成的 native rc-core key lifecycle。
3. 生成 device-specific `/system/usr/keylayout/sunxi-ir.kl`，直接把 Linux keycode 映射为当前 Android 语义。
4. 在 `/system/etc/init/multi_ir.rc` 保留原 service 定义并加入 `disabled`；不再创建 `sunxi-ir-uinput`，运行时不依赖 `/dev/uinput`。
5. ff4054 Mouse 不进入 rc-map 或 Android keylayout。

## 49 项映射审计

| ff40 scan | r13 Android 语义 | Linux keycode | flag / 结果 |
|---|---|---|---|
| `00` | `0` | `KEY_0` (11) | WAKE |
| `01` | `1` | `KEY_1` (2) | WAKE |
| `02` | `2` | `KEY_2` (3) | WAKE |
| `03` | `3` | `KEY_3` (4) | WAKE |
| `04` | `4` | `KEY_4` (5) | WAKE |
| `05` | `5` | `KEY_5` (6) | WAKE |
| `06` | `6` | `KEY_6` (7) | WAKE |
| `07` | `7` | `KEY_7` (8) | WAKE |
| `08` | `8` | `KEY_8` (9) | WAKE |
| `09` | `9` | `KEY_9` (10) | WAKE |
| `0b` | `DPAD_UP` | `KEY_UP` (103) | WAKE_DROPPED |
| `0c` | `ZOOM_IN` | `KEY_ZOOMIN` (418) | WAKE |
| `0d` | `DPAD_CENTER` | `KEY_OK` (352) | WAKE_DROPPED |
| `0e` | `DPAD_DOWN` | `KEY_DOWN` (108) | WAKE_DROPPED |
| `0f` | `PERIOD` | `KEY_DOT` (52) | WAKE |
| `10` | `DPAD_LEFT` | `KEY_LEFT` (105) | WAKE_DROPPED |
| `11` | `DPAD_RIGHT` | `KEY_RIGHT` (106) | WAKE_DROPPED |
| `12` | `DEL` | `KEY_BACKSPACE` (14) | WAKE |
| `13` | `MEDIA_STOP` | `KEY_STOPCD` (166) | WAKE |
| `14` | `EXPAND` | `KEY_FULL_SCREEN` (372) | WAKE |
| `15` | `VOLUME_UP` | `KEY_VOLUMEUP` (115) | WAKE |
| `17` | `BROWSER` | `KEY_WWW` (150) | WAKE |
| `1a` | `HOME` | `KEY_HOMEPAGE` (172) | WAKE |
| `1c` | `VOLUME_DOWN` | `KEY_VOLUMEDOWN` (114) | WAKE |
| `1e` | `MEDIA_PREVIOUS` | `KEY_PREVIOUSSONG` (165) | WAKE |
| `1f` | `F7` | `KEY_F7` (65) | WAKE |
| `42` | `BACK` | `KEY_BACK` (158) | WAKE |
| `43` | `VOLUME_MUTE` | `KEY_MUTE` (113) | WAKE |
| `44` | `SETTINGS` | `KEY_CONFIG` (171) | WAKE |
| `45` | `MENU` | `KEY_MENU` (139) | WAKE_DROPPED |
| `47` | `SEARCH` | `KEY_SEARCH` (217) | WAKE_DROPPED |
| `49` | `PROG_YELLOW` | `KEY_YELLOW` (400) | WAKE |
| `4d` | `POWER` | `KEY_POWER` (116) | WAKE |
| `4e` | `PROG_GREEN` | `KEY_GREEN` (399) | WAKE |
| `4f` | `BACK` | `KEY_EXIT` (174) | WAKE_DROPPED |
| `50` | `MEDIA_PLAY_PAUSE` | `KEY_PLAYPAUSE` (164) | WAKE |
| `54` | `MOUSE` | — | intentionally inert |
| `55` | `PROG_RED` | `KEY_RED` (398) | WAKE |
| `59` | `PROG_RED` | `KEY_RED` (398) | WAKE |
| `5a` | `PROG_BLUE` | `KEY_BLUE` (401) | WAKE |
| `5b` | `APPS` | `KEY_APPSELECT` (580) | WAKE |
| `5c` | `MUTE` | `KEY_MICMUTE` (248) | WAKE |
| `61` | `APP_SWITCH` | `KEY_CYCLEWINDOWS` (154) | WAKE |
| `7e` | `SETTINGS` | `KEY_CONFIG` (171) | WAKE |
| `f1` | `F1` | `KEY_F1` (59) | WAKE |
| `f2` | `F2` | `KEY_F2` (60) | WAKE |
| `f3` | `F3` | `KEY_F3` (61) | WAKE |
| `f4` | `F4` | `KEY_F4` (62) | WAKE |
| `f5` | `F5` | `KEY_F5` (63) | WAKE |

48 个 rc-map 条目最终形成 46 个唯一 Linux keycode 的 `.kl` 项；`55/59` 共用 `KEY_RED`，`44/7e` 共用 `KEY_CONFIG`，语义没有丢失。

## legacy 保留状态

以下工件继续保留作回滚/对照，但不参与 rc-core-r1 的运行路径：

- `/system/bin/multi_ir`
- `/system/etc/init/multi_ir.rc`（service 为 `disabled`）
- `/system/usr/keylayout/customer_ir_ff40.kl`
- `/system/usr/keylayout/sunxi-ir-uinput.kl`
- `/system/lib/libmultiirservice.so`
- `/system/lib/libinput.so`（r12 exact Test8r2 版本）

## 候选与 payload

| 工件 | 大小 | SHA-256 |
|---|---:|---|
| `x12-m8b-rc-core-r1.img` | 1007978496 | `E3F40ECFB2FE867EB6C04988E0C3207C49E1B1073AF42A2B41FFF3A7C3DBBCE0` |
| kernel Image | 23029768 | `D5AEED79EF04D3DF838385AD857AC81268C4CACDA986545016F5CEE7E45FE289` |
| `boot.fex` | 67108864 | `08DF01C1E4D66C6081398E6F53F2F1498C4B4718DC6BABC5ADB44D1B63775C0D` |
| `system_a` | 1651167232 | `DC7B9EF4814E04F8EB4671E609D2ACD22CD7CB6218B5443B7D74E28793D0A9C5` |
| `super.img` | 828179824 | `3093AF2DC57BA45C15F0D01F6F7BB6C08A67FAEB75EFF81672D787F67BCCCA0D` |
| `vbmeta_system.fex` | 1472 | `F68247A300DB60E3512BCAF1B2240B43DF92004996D67CDB9FCC2E4AB73B1BFA` |

相对 r13，功能内容仅变更 boot kernel、`/system/etc/init/multi_ir.rc` 和 `/system/usr/keylayout/sunxi-ir.kl`。外层变化为 `boot.fex`、`Vboot.fex`、`super.fex`、`Vsuper.fex`、`vbmeta_system.fex`、`Vvbmeta_system.fex`；其余 44/50 项保留。`vendor_a`、`product_a`、`vendor_dlkm_a` 哈希与 r13 一致；boot ramdisk、vendor_boot、DT/DTBO、持久 bootargs、顶层 vbmeta 均未改。

## 离线验证

- 完整 kernel Image 构建通过；`RC_MAP_SUNXI` 注册、48 个有效 Linux keycode、49 项语义审计和 Mouse 排除检查通过。
- 解包 system 的唯一差异是 disabled `multi_ir.rc` 与新 `sunxi-ir.kl`；legacy 工件、Projectivy、provisioning、Power RRO、r10 兼容库和 canonical `/vendor` topology 保持不变。
- `multi_ir` 不自动启动；native path 不依赖 uinput。
- LP 解包、AVB、system/vendor/product/vendor_dlkm e2fsck、split SELinux compile、ELF/DT_NEEDED、IMAGEWTY 12 项外层校验通过。
- M8B 3 项 focused tests、r12/r13 6 项回归测试通过；`git diff --check` 留在最终工作树检查执行。

## 首次设备验收

刷入后先执行：

```sh
getprop sys.boot_completed
getprop init.svc.multi_ir
cat /proc/bus/input/devices
for e in /sys/class/input/event*; do
    echo "$(basename "$e") : $(cat "$e/device/name")"
done
dumpsys input | grep -A 50 -B 5 'sunxi-ir'
cat /sys/class/rc/rc0/protocols
cat /sys/class/rc/rc0/uevent
```

然后 root：

```sh
su 0 sh -c 'getevent -lt /dev/input/event0'
```

依次验证 UP、DOWN、LEFT、RIGHT、OK、BACK、HOME、VOL+、VOL-、POWER。成功条件是 `sunxi-ir` 直接产生 `EV_KEY`，`init.svc.multi_ir` 不是 running，且没有 `sunxi-ir-uinput`。另需人工验证 DPAD 长按/repeat/release、HOME 到 Projectivy、短按 Power 休眠、Power 唤醒和长按 Power 关机。

## 已知风险与回滚

- 尚未实机确认 native rc-core 的 repeat/release 和休眠后 IR Power 唤醒对等性；这是首测重点。
- 匹配的公开内核树在 `olddefconfig` 后除目标项外还有三项 Kconfig 表示差异：新增 `MOTORCOMM_PHY is not set`，源码树缺少原 config 的 `XR819_WLAN=m` 与 `AW_TSC is not set` 符号。当前 built-in Image 的目标变化仍限定为 rc-core 路径，但应把首次冷启动、网络和 suspend 作为回归观察点。
- 若失败，直接回滚已实机验收的 r13；不要在 rc-core-r1 同时改 DTS、Power policy 或 userspace framework。
