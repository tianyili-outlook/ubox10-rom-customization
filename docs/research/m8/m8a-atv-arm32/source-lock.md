# M8A.1 Android 12 ATV source-lock

状态：`LOCKED`

| 项目 | 锁定值 |
|---|---|
| 上游 | <https://android.googlesource.com/device/google/atv> |
| 分支 | `android12-release` |
| commit | `3ce48358b7e06ab1f1a1b713fb0f285aaa0983ca` |
| commit 时间 | `2021-07-31T03:01:28Z` |
| 许可证 | Apache-2.0 |
| 本地副本 | `work/m8/source-lock/device-google-atv/`，已忽略 |

完整 Android 12 platform 同步入口也已锁定：

| 项目 | 锁定值 |
|---|---|
| manifest | `platform/manifest` `android12-release` @ `8e7a52179c1704bc445f83efde08a6025acbf358` |
| superproject | `platform/superproject` @ `51d9636ffdf52084355cc4dc3641ff9b0790c678` |
| ATV gitlink | `3ce48358b7e06ab1f1a1b713fb0f285aaa0983ca` |
| 本地元数据 | `work/m8/source-lock/platform-{manifest,superproject}/`，已忽略 |

`aosp_tv_arm` 明确面向 ARM32 用户空间、64 位 Binder 和 VNDK enforcement。
它依次组合：

- `atv_generic_system.mk`、`atv_system_ext.mk`、`atv_product.mk`；
- emulator vendor、goldfish ARM32 vendor、generic_x86 device；
- GSI release 配置。

UBOX10 只采用前三个 ATV 产品层作为参考。emulator、goldfish、generic_x86
vendor、分区和硬件配置均不进入设备树。

superproject 的 ATV gitlink与独立 source-lock 完全一致。完整 AOSP 尚未下载；
后续不直接跟随 `main` 或未固定的 manifest。
