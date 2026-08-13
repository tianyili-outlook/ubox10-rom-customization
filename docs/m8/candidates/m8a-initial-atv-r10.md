# m8a-initial-atv-r10

状态：已构建，待首次设备测试。

## 单一变量

以 r9 为基线，把 Test8r2 的 exact ARM32 vendor AIDL `ndk_platform` 双库恢复到 r9 实际 linker fallback 搜索路径 `/system/lib`：

- `android.hardware.light-V1-ndk_platform.so`：`57ED3A999D158EE449D6621897275610B0479B0F06B7EFB1005AF397099BF663`
- `android.hardware.rebootescrow-V1-ndk_platform.so`：`F26AA210060D449AA2D0ED8B7341DB28BA072A6F1DD4AF31BB2005E427636AB0`

两库均为 ELF32 ARM、0:0、0644、`u:object_r:system_lib_file:s0`，文件内容与 Test8r2 完全一致。未修改 LightsService、Watchdog、llkd、VINTF、vendor HAL、linkerconfig、SELinux policy 或其他 HAL。

## 产物

| 项目 | 值 |
|---|---|
| 镜像 | `out/candidates/m8a-initial-atv-r10/x12-m8a-initial-atv-r10.img` |
| 大小 | 996566016 bytes |
| SHA-256 | `3A88AE6E4436AC27E94505B805DB62CDCA81144FC312DD79FB4DB97870BAA91C` |
| system_a | `99130EDE6615F1C72743D74BDBE7F7FC08B92AA002D146EEB3469600F87E419F` |
| super | `E0AB7D19635A559DC505EEAF0FBFD7CACB441950CB6E94EAFBB3990351B3D90A` |
| vbmeta_system | `6D65C50C26BD7E6F0BB8CC92D37D146A49AF398386D3DDB1813A0765F5B7611D` |

相对 r9，仅 `system_a`、`super.fex`、`Vsuper.fex`、`vbmeta_system.fex`、`Vvbmeta_system.fex` 变化。`vendor_a`、`product_a`、`vendor_dlkm_a`、boot、vendor_boot、顶层 vbmeta 和其余 46 个外层 payload 原字节不变。

## 离线结果

- 解包后仅新增上述两库，SHA-256、SONAME、ARM32 架构、build-id、uid/gid/mode 和 SELinux label 与锁定值一致。
- Lights HAL 与 rebootescrow HAL 的全部 `DT_NEEDED` 均可解析；未新增传递依赖缺项。
- r9 canonical `/vendor` topology、VINTF、init rc、stock fstab、exact first-stage init 和 SELinux policy 未变。
- LP metadata、AVB、四个 ext4 文件系统、SELinux policy 编译、IMAGEWTY companion 校验通过。

## 首次测试

```text
setenv console ttyAS0,115200
setenv loglevel 1
run setargs_mmc
printenv bootargs
run boot_normal
```

不要执行 `saveenv`。确认 Lights HAL 不再出现 `CANNOT LINK EXECUTABLE`，`android.hardware.light.ILights/default` 注册，system_server PID 稳定，`package_native` 注册，`sys.boot_completed=1`，bootanimation 停止；否则记录首个确定性错误。
