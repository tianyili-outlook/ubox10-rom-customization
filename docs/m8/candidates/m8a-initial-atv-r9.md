# M8A initial ATV r9

状态：**待首次设备验证**

| 项目 | 值 |
|---|---|
| 镜像 | `out/candidates/m8a-initial-atv-r9/x12-m8a-initial-atv-r9.img` |
| 大小 | 996512768 bytes |
| SHA-256 | `6CB59E0A9A77AB83E11063EAB67762BA3FC1A8C17AD5E75E8A16278056A09E62` |
| system_a | `64FC2C65894C7EF36781DEDD87E1722A258F06E3361749A3AE274E24C955D851` |
| super | `F69E1201B432D9EFD6937B251B9CBE7AE215A0CF738A5D711605CABD6DA28FA4` |
| vbmeta_system | `5AA1E40EB8198BE0E6C350FAFED9E95A9F3B9AA93CA637314D0A303CE3C0FFCA` |

## 首次 UART 诊断启动

1. 刷入 r9 后进入 U-Boot。
2. 逐条执行：

```text
setenv console ttyAS0,115200
setenv loglevel 8
run setargs_mmc
setenv bootargs ${bootargs} ignore_loglevel printk.devkmsg=on androidboot.init_fatal_panic=true
printenv bootargs
run boot_normal
```

3. 采集从运行时 kernel command line 到 `selinux_setup`、second stage 或下一处 fatal 的完整 UART。
4. 核对日志不再出现 `mount point is not canonical: realpath(/vendor) -> /system/vendor`。
5. 核对 `vendor_a` 挂载到 `/vendor`，并继续处理 `vendor_dlkm_a`、`product_a` 和 `/oem`。
