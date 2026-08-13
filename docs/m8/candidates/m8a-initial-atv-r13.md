# m8a-initial-atv-r13

## 目的

r13 以 r12 为基线，只收尾两个已复现的 TV 日常使用问题：

- 用正式 provisioning 组件稳定写入三个 setup flag，使 HOME 不再被 setup policy 拦截；
- 把短按 Power 从 NOTHING 改为 GO_TO_SLEEP，同时保持长按关机。

不修改遥控栈、mouse mode、Launcher、Lights/VNDK、kernel、DT、boot、vendor_boot 或 vendor。Mouse mode 保持 deferred；M8B rc-core modernization 保持 future exploration only。

## 现场根因

### HOME / provisioning

r12 已确认 Android 收到 `KEYCODE_HOME`，HOME resolver 指向 Projectivy，但 WindowManager 输出 `Not going home because user setup is in progress`。`device_provisioned=1`、`user_setup_complete=1` 重启后仍被拦截；`tv_user_setup_complete` 为 null。运行时写入 `secure tv_user_setup_complete=1` 后无需重启即可进入 Projectivy。因此根因为 TV 专用 setup flag 缺失，不是遥控、Projectivy 或 HOME resolver。

### Power

r12 的 Linux `KEY_POWER`、Android `KEYCODE_POWER=26` 和 PhoneWindowManager 输入路径正常。资源链为：

| 来源 | 静态优先级 | 短按值 | 长按值 |
|---|---:|---:|---:|
| framework 默认 | base | 1 | 5 |
| product `TvFrameworkOverlay.apk` | -1 | 未定义 | 3 |
| vendor auto-generated RRO | 0 | 0 | 3 |
| r13 `M8TvPowerPolicyOverlay.apk` | 1 | 1 | 未定义 |

vendor RRO 把短按覆盖为 `SHORT_PRESS_POWER_NOTHING`。当前 Android 12 PhoneWindowManager 在初始化时读取资源，因此 `settings put global power_button_short_press 1` 即使持久化也不改变当前 policy。

## 实际修改

构建来源：

- `configs/candidates/m8a-initial-atv-r13.json`
- `configs/candidates/m8a-initial-atv-r13-overlay/AndroidManifest.xml`
- `configs/candidates/m8a-initial-atv-r13-overlay/res/values/config.xml`
- `scripts/install-m8-r13-tv-policy.sh`
- `scripts/build-m8a-r13-candidate.py`
- `tests/test_m8a_r13_tv_policy.py`

system_a 新增：

| 路径 | 大小 | SHA-256 | 来源 |
|---|---:|---|---|
| `/system_ext/priv-app/AwTvProvision/AwTvProvision.apk` | 20894 | `D74DF03C4BBAB8ADCFC543D9F34D98C87178A63D15F66785B1EE3D286EDB68D8` | exact Test8r2 system_a |
| `/system_ext/etc/permissions/provision-permissions.xml` | 1146 | `98C3C29A10F4956BBAB65F74E405E7B3F8DF20C262A22FF7FCC755C0F92F7E6A` | exact Test8r2 system_a |
| `/system_ext/overlay/M8TvPowerPolicyOverlay.apk` | 8538 | `B695200E1153F750B3BF1CD92228EE6E360BA7B12608CB56019D316017481C91` | r13 源码 + 固定 AOSP 工具链 + platform key |

AwTvProvision 是 direct-boot-aware 的 HOME/DEFAULT/SETUP_WIZARD 组件，优先级 1。其固定 DEX 控制流在首次 HOME 时写入：

```text
device_provisioned=1
user_setup_complete=1
tv_user_setup_complete=1
```

完成后组件禁用自身，Projectivy 保持真实 HOME。未加入完整 SetupWizard，未使用 shell hack。Power RRO 只定义 `config_shortPressOnPowerBehavior=1`；没有定义长按资源。

## 冻结项

以下内容按解包 SHA-256 和元数据确认不变：Projectivy APK、`multi_ir`、`multi_ir.rc`、`customer_ir_ff40.kl`、`sunxi-ir.kl`、`sunxi-ir-uinput.kl`、`libmultiirservice.so`、r12 `libinput.so`、r10 两个 AIDL compatibility library、canonical `/vendor`。`vendor_a`、`product_a`、`vendor_dlkm_a` 和其余 46 个外层 payload 原字节不变。

## 候选与 payload

| 项目 | 大小 | SHA-256 |
|---|---:|---|
| `x12-m8a-initial-atv-r13.img` | 1007978496 | `1D367F7091A7BD6A0791B2CFE45E7AAB551E0312D8C68136548A4927354A8E06` |
| `system_a` | 1651167232 | `28118A3316F1845A174667B527125C0FA750A719EFA0CF94FB88DC197FAE2055` |
| `super.img` | 828179824 | `FFAC0283599D9FE44383642843EA5A4645E09C140FD53CCB769196EA05A57200` |
| `vbmeta_system.fex` | 1472 | `2A2AAA0F67BA2729834FC26B735AC8B5E0445EE88623C1758FCD99C62FB609BB` |
| `Vsuper.fex` | 4 | `C0EA5C82E54E8BB7CFB06A9F7014BF9235F9D4566AE147B8A06C747FB1A36333` |
| `Vvbmeta_system.fex` | 4 | `FC85C934E6D54D36CDD0E451C41B9AB00E8AB1D98FC52018A9644FD897F4204B` |

相对 r12，仅 `system_a`、`super.fex`、`Vsuper.fex`、`vbmeta_system.fex`、`Vvbmeta_system.fex` 变化。

## 离线检查

- r13 system_a 解包差异仅为 3 个文件、2 个新目录及必要父目录 link-count 变化，无意外文件差异。
- AwTvProvision APK、allowlist 与 Test8r2 SHA-256 完全一致；manifest、privapp 权限和三个最终 flag 控制流匹配。
- Power RRO 为 platform-signed ARM-independent resource APK，优先级 1，只包含短按值 1；静态优先级解析结果为短按 GO_TO_SLEEP、长按仍 SHUT_OFF_NO_CONFIRM。
- 冻结文件逐字节不变；remote ELF/DT_NEEDED、Projectivy ARM32 native 依赖、split SELinux policy 均通过。
- LP metadata、AVB、四个 logical partition 的只读 e2fsck、canonical `/vendor`、IMAGEWTY 外层校验、focused tests 和 `git diff --check` 通过。
- 本轮未刷机、未执行设备命令。

## 首次设备验收

```sh
getprop sys.boot_completed
settings get global device_provisioned
settings get secure user_setup_complete
settings get secure tv_user_setup_complete
cmd package resolve-activity --brief --user 0 -a android.intent.action.MAIN -c android.intent.category.HOME
dumpsys window policy | grep -i -E 'mShortPressOnPowerBehavior|mLongPressOnPowerBehavior'
```

成功条件：`sys.boot_completed=1`；三个 setup flag 均为 `1`；HOME 解析到 `com.spocky.projengmenu/.ui.home.MainActivity`；短按为 `SHORT_PRESS_POWER_GO_TO_SLEEP`；长按仍为 `LONG_PRESS_POWER_SHUT_OFF_NO_CONFIRM`。

随后人工验证：从 Settings/其他应用按 HOME 返回 Projectivy；DPAD/OK/BACK/Volume 无回归；短按 Power 进入 sleep/standby；再次按 Power 尝试唤醒；长按 Power 仍关机。若 sleep 成功但 IR 无法 wake，下一轮只处理 wake path，不在 r13 扩大到 kernel/DT。
