# m8a-initial-atv-r12

## 目的

r11 已 boot complete 并正常进入 Projectivy，但物理 `sunxi-ir/event0` 只产生 raw `MSC_SCAN`，没有 Android 可用的 `EV_KEY`。r12 的唯一功能变量是：

> restore the exact Test8r2 Allwinner multi_ir remote-input stack required for this UBOX10 remote, including its working DPAD and mouse-mode behavior.

不实施 rc-core 重构，不改 kernel、DT/DTBO、boot、vendor_boot、vendor、Launcher、provisioning 或其他硬件栈。

## 主证据与输入架构

- r11：`logs/device/20260811-r11/uart-putty_3.log`。RemoteIR_RX IRQ、NEC 和 event0 `MSC_SCAN` 均正常，event0 没有 `EV_KEY`。
- Test8r2 物理对照：`uart-putty_8r2.log`。event0 同样只有 `MSC_SCAN`。
- Test8r2 uinput 对照：`uart-putty_8r2_2.log`。`multi_ir` 同时打开 event0 和 `/dev/uinput`，建立 `sunxi-ir-uinput/event1`；event1 输出 `EV_KEY`和 `EV_REL`，InputReader 将其分类为 KEYBOARD/CURSOR/DPAD。
- Test8r2 工件对照：`uart-putty_8r2_3.log`。运行进程为 root `u:r:multi_ir:s0`，使用 `sunxi-ir-uinput.kl`，并加载 `libmultiirservice.so`。

完整链为：

```text
sunxi-ir/event0 (MSC_SCAN, ff40 factory ID)
  -> /system/bin/multi_ir
  -> customer_ir_ff40.kl + sunxi-ir.kl
  -> /dev/uinput
  -> sunxi-ir-uinput/event1 (EV_KEY + EV_REL)
  -> sunxi-ir-uinput.kl
  -> Android InputReader / KeyEvent
```

## ff40 exact 映射

`/system/usr/keylayout/customer_ir_ff40.kl`：1726 bytes，SHA-256 `DB54F9843081DDC492F9BDD35E7EE341EBCB4562991513CB5B7A26BBBC74DE39`，0:0，0644，`u:object_r:system_file:s0`。它从已锁定的 Test8r2 `system_a` 提取；当前 AOSP checkout 没有 `vendor/aw` 源树，exact `multi_ir` 调试路径指向 `vendor/aw/homlet/hardware/input/multi_ir`，因此 pinned Test8r2 是当前可复现输入。

| scancode | label | flag | scancode | label | flag |
|---:|---|---|---:|---|---|
| 0 | 0 | WAKE | 1 | 1 | WAKE |
| 2 | 2 | WAKE | 3 | 3 | WAKE |
| 4 | 4 | WAKE | 5 | 5 | WAKE |
| 6 | 6 | WAKE | 7 | 7 | WAKE |
| 8 | 8 | WAKE | 9 | 9 | WAKE |
| 11 | DPAD_UP | WAKE_DROPPED | 12 | ZOOM_IN | WAKE |
| 13 | DPAD_CENTER | WAKE_DROPPED | 14 | DPAD_DOWN | WAKE_DROPPED |
| 15 | PERIOD | WAKE | 16 | DPAD_LEFT | WAKE_DROPPED |
| 17 | DPAD_RIGHT | WAKE_DROPPED | 18 | DEL | WAKE |
| 19 | MEDIA_STOP | WAKE | 20 | EXPAND | WAKE |
| 21 | VOLUME_UP | WAKE | 23 | BROWSER | WAKE |
| 26 | HOME | WAKE | 28 | VOLUME_DOWN | WAKE |
| 30 | MEDIA_PREVIOUS | WAKE | 31 | F7 | WAKE |
| 66 | BACK | WAKE | 67 | VOLUME_MUTE | WAKE |
| 68 | SETTINGS | WAKE | 69 | MENU | WAKE_DROPPED |
| 71 | SEARCH | WAKE_DROPPED | 73 | PROG_YELLOW | WAKE |
| 77 | POWER | WAKE | 78 | PROG_GREEN | WAKE |
| 79 | BACK | WAKE_DROPPED | 80 | MEDIA_PLAY_PAUSE | WAKE |
| 84 | MOUSE | WAKE_DROPPED | 85 | PROG_RED | WAKE |
| 89 | PROG_RED | WAKE | 90 | PROG_BLUE | WAKE |
| 91 | APPS | WAKE | 92 | MUTE | WAKE |
| 97 | APP_SWITCH | WAKE | 126 | SETTINGS | WAKE |
| 241 | F1 | WAKE | 242 | F2 | WAKE |
| 243 | F3 | WAKE | 244 | F4 | WAKE |
| 245 | F5 | WAKE |  |  |  |

Power 为 scancode 77，完整 raw 值 `ff404d`；mouse-toggle 为 scancode 84，完整 raw 值 `ff4054`。

## mouse mode 边界

exact `multi_ir` 内含 `setMouseMode`、`ir_key_repeat`、`detect_key_input`、`report_mouse_keyevent`、`create_virtual_mouse_dev` 和 `setup_virtual_input_dev` 符号，并导入 `setitimer/gettimeofday`。mouse-toggle 状态、DPAD 到 pointer 的转换、repeat 时序和指针移动都由 `multi_ir` 维护；它通过 uinput 输出 `EV_REL REL_X/REL_Y` 和 `EV_KEY`。Test8r2 现场确认 CURSOR/DPAD 能力及 1920x1080 pointer range。

r11 `libinput.so` 缺少 Test8r2 keylayout 中 `MOUSE`、`TV_SYSTEM`、`GOTO`、`SUBTITLE`、`AUDIO`、`ZOOM`、`FAVOURITE`、`LOOP`、`EXPAND`、`MOVIE`、`APPS`、`BROWSER`、`SCREENSHOT` 等 Allwinner label；`KeyLayoutMap` 遇到未知 label 会拒绝整份 `.kl`。r12 因此只替换 exact Test8r2 `libinput.so`，不恢复整套旧 framework。

## 实际恢复的最小工件

| 路径 | SHA-256 | 理由 |
|---|---|---|
| `/system/bin/multi_ir` | `2A72F8FBCF29DB3DA9AA29EE61A95380B44B44DAFDF8CADAADB41097262FC687` | 读 raw IR、管理 DPAD/mouse 状态并创建 uinput 设备 |
| `/system/etc/init/multi_ir.rc` | `7016A9C2648C4ECD4AE3977E1169C4CFA394FF6E721664E0A5A1FD128BBB1BBD` | 以 root、`system input uhid`、`multi_ir` 域启动服务 |
| `/system/usr/keylayout/customer_ir_ff40.kl` | `DB54F9843081DDC492F9BDD35E7EE341EBCB4562991513CB5B7A26BBBC74DE39` | 当前 ff40 遥控的 exact raw scancode 映射 |
| `/system/usr/keylayout/sunxi-ir.kl` | `89F237061963CC333E55A3E3451E175BE6144794493FE0315122A7986F77DDDA` | `multi_ir` 使用的 label/keycode 交叉映射，同时覆盖物理设备 |
| `/system/usr/keylayout/sunxi-ir-uinput.kl` | `1B54A9C2B39C8922407F4A806825496AE6E4F0E1C16B394D7C09465AFB58B391` | Android 解析虚拟 `sunxi-ir-uinput` 设备 |
| `/system/lib/libmultiirservice.so` | `02BBB53F33CD0AAC2186A940B6E1B5D92539FADA2A7A07E894DC65E138183A38` | `multi_ir` 的直接 DT_NEEDED |
| `/system/lib/libinput.so` | `764069A044E639A5567803FE530602A525FC66857413C6BC0E4C515040B1F557` | 最小 Allwinner input-label/parser 兼容差异，使完整 uinput `.kl` 可加载 |

未恢复：

- `libmultiir_jni.so`：`multi_ir` 无 DT_NEEDED 边，Test8r2 运行进程也未映射。
- `virtual-remote.kl`：物理 `sunxi-ir` 和虚拟 `sunxi-ir-uinput` 都不选中它。
- `customer_ir_4040.kl`：当前实体遥控 factory ID 为 ff40。

## SELinux、uinput 与 ABI

- r11/Test8r2 `vendor_a` 原字节一致，已有 `multi_ir`、`multi_ir_exec`、`uhid_device`、`input_device`、Binder 和 service_manager 权限。
- `/dev/uinput` 的 ueventd 合同为 `0660 uhid:uhid`，context 为 `u:object_r:uhid_device:s0`。无 policy、ueventd、permissive 或 chmod 变更。
- `multi_ir`：ELF32/ARM PIE，Build ID `1235706c0f69dec7ec1eb8f9ad59ea72`；全部 DT_NEEDED 在 r12 `/system/lib` 可解析。
- `libmultiirservice.so`：ELF32/ARM，SONAME `libmultiirservice.so`，Build ID `d17b5003a68f72dfd750756b28452709`；全部 DT_NEEDED 可解析。
- Test8r2/r11 `libinput.so` 具有相同 SONAME、相同 DT_NEEDED 和相同 undefined-symbol set（SHA-256 `14EAEA9006F7FC198E166542415A85AD6429C852E3C4170EC831CF7CCB9A0341`），替换不引入额外 system 库链。

## 产物与 payload 差异

| 项目 | 大小 | SHA-256 |
|---|---:|---|
| `x12-m8a-initial-atv-r12.img` | 1007925248 | `4A633A34DB1274AC3D943481806A385AFCAC9FEA7181C0251CF25A4D9F37CB7A` |
| `system_a` | 1651167232 | `7ECF3B7891F012D296BC8C0A44684011E1FD83796F33AB01371A9700B89DBDDB` |
| `super.img` | 828126576 | `D08A974C5E9AD646E1B38512A4AA80041D37C37ED043F16509BE1E786639B540` |
| `vbmeta_system.fex` | 1472 | `28D42D0874B5749272C42EC4B42DA9EACE56BC518A314F9952EF06944DD7F924` |
| `Vsuper.fex` | 4 | `CFC29EC4F5E5209E58C111AF9C29DFEE2D4788D98EB27A89429F1F218356162D` |
| `Vvbmeta_system.fex` | 4 | `A7F203306503EA3C9803D3D8CD51A647F9EAF7DA51D45773A6DA95B6CF9E31D8` |

相对 r11，仅 `system_a`、`super.fex`、`Vsuper.fex`、`vbmeta_system.fex`、`Vvbmeta_system.fex` 变化。`vendor_a`、`product_a`、`vendor_dlkm_a`、boot、vendor_boot、顶层 vbmeta 和其他 46 个外层 payload 原字节不变。

## 离线检查

- 解包后 system 差异仅为上述 7 个目标路径，没有意外文件差异；exact Test8r2 SHA、uid/gid、mode 和 SELinux label 全部匹配。
- `multi_ir.rc` 与 ff40/uinput keylayout 语法及 parser 兼容性通过；mouse-toggle 和 exact mouse functions 存在。
- 新增 ELF 均为 ARM32，DT_NEEDED 无缺失；Projectivy 的 ARM32 native 库依赖仍可解析。
- 现有 split SELinux policy 编译通过；`/dev/uinput` 和 `multi_ir` 合同未变。
- Projectivy APK、r10 两个 VNDK 兼容库、canonical `/vendor` topology、stock first-stage init 和 stock fstab 未变。
- LP metadata、AVB、四分区只读 e2fsck、IMAGEWTY 外层校验、focused tests 和 `git diff --check` 通过。

## 首测

```sh
getprop sys.boot_completed
getprop init.svc.multi_ir
ps -AZ | grep multi_ir
ls -lZ /dev/uinput
cat /proc/bus/input/devices
dumpsys input | grep -A 40 -B 5 'sunxi-ir-uinput'
```

成功必须出现 `sys.boot_completed=1`、`multi_ir` running、正常 `/dev/uinput` 权限/context、保留的物理 `sunxi-ir`、新增 `sunxi-ir-uinput` 以及对 `sunxi-ir-uinput.kl` 的加载。

实体遥控顺序验收 UP/DOWN/LEFT/RIGHT、OK、BACK、HOME、VOL+/VOL-、Power 无回归与方向键长按连续导航。mouse mode 另必须验收：正常模式方向键为 DPAD；按 mouse-toggle 后 pointer 启用，方向键移动 pointer，OK 可点击；再按 mouse-toggle 后退出，返回 DPAD 且不残留 pointer 行为。
