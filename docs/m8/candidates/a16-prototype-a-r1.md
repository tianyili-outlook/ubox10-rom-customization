# Android 16 Prototype A r1 candidate

状态：**PHYSICAL FAIL — BOOTSTRAP APEXD BOUNDARY / NOT ACCEPTED**。用户已另行授权并完成唯一一次 r1 刷写/启动；Gate 2 继续 **CLOSED**。不得再次刷写，不得启动 Prototype B。

## Purpose and provenance

本候选回答一个限定问题：保持 accepted UBOX10/H616 boot、AArch64 5.4.125 kernel、vendor、product、vendor_dlkm、TEE/DRM/graphics/media/audio/wireless 与外层分区依赖不变时，Gate 1 的纯 ARM32 Android 16 system 是否能形成一个离线一致、可回滚、值得进行一次 UART-first boot 的 exact-board image。

Gate 1 source 为 `android-16.0.0_r4` / `BP4A.251205.006`，manifest commit `15128c9e27cfa599c48d294babd39286ee8f1426`，pinned manifest SHA-256 `4E8BEB5D1B590DFF3D631B1DBB957138DBDA4E608A3183C625683DA4BC84918F`。输入 system 为 `/work/src/ubox10-a16-ceiling/out-ceiling/target/product/generic/system.img`，946,765,824 bytes / SHA-256 `FD349F1D8073DFEB71E2CEA28915F1C755FA54E3EBA85616FCAA279063F3EDBE`。

Accepted exact-board 输入为 `m8b-remote-r1`，1,031,723,008 bytes / SHA-256 `F3B09E5565AC4ED4E5EE326D392622E7B036A8519B8444B966E77CC4751B814A`。Test8r2 rollback 为 2,005,954,560 bytes / `6A52F3388E9ABF6AFA8A701CFD7198FE6C0090F16531F6E3BD3949E760892EC8`。两者在 GCP intake 时重新校验；accepted logical、boot/vendor_boot、super 与 AVB payload 从同一外层镜像提取并由 `configs/candidates/a16-prototype-a-r1.json` 锁定。原始镜像为只读，构建前后 hash 一致。

## Bounded integration changes

初始 full exact VINTF 审计确认 accepted vendor 暴露两个 generic A16 matrix 未声明的 device-specific display HAL：

- `vendor.display.config@1.0::IDisplayConfig/default`；
- `vendor.display.output.IDisplayOutputManager/default (@2)`。

`compatibility_matrix.xml` 仅声明这两个 exact HAL。加入后 full VINTF 的唯一剩余错误是 actual kernel `CONFIG_NFS_FS=y`，而 FCM 6 要求 `n`。同一 device-accepted Android 12 FCM 6 matrix 对同一 kernel 也给出该错误；只把 captured config 反事实改为 `n` 时 A16 full exact check PASS。因此它是 inherited BSP conformance deviation，仍记录为 exit 65 / `INCOMPATIBLE`，不是 VINTF PASS，也未通过改 kernel 隐藏。

初始 exact split-SELinux compile 的首错是重复 `genfscon`：A16 platform 为 `fuseblk /` 指定 `fuseblk`，accepted API-31 vendor 对同一 filesystem/path 指定 `vfat`。`0002-sepolicy-defer-fuseblk-label-to-api31-vendor.patch` 仅移除 platform duplicate，保留 device-accepted vendor label。候选 system 相对 Gate 1 filesystem 的完整语义差异严格只有：

- `/system/etc/vintf/compatibility_matrix.device.xml`；
- `/system/etc/selinux/plat_sepolicy.cil`。

两个文件的 uid/gid、mode 与 SELinux xattr 均保持。没有修改 boot/kernel、vendor_boot、vendor/product/vendor_dlkm、zygote architecture、graphics/media/audio/wireless/DRM、TEE、DTBO、GPT 或 partition geometry。

## Artifacts

| 工件 | 大小 | SHA-256 |
|---|---:|---|
| `out/candidates/a16-prototype-a-r1/x12-a16-prototype-a-r1.img` | 1261038592 | `A034C8193236C93746E5962CB3E7F26A1D56CEC1435D5AD9D95F653B60BEBD83` |
| `out/candidates/a16-prototype-a-r1/system_a.img` | 1651167232 | `24CF6C9109CFDBBC8DB3A068E73EB5CD090440F58540AE6D62B8B667DB7DA2B5` |
| `out/candidates/a16-prototype-a-r1/super.fex` | 1081240172 | `DA043A276B28533E41FF17A7425604F1C79F68B2AA572260329EDC80E32F94D6` |
| `out/candidates/a16-prototype-a-r1/vbmeta_system.fex` | 1472 | `91C587E32CCA577F31770F6EE462FFE7F20594BCA6D4F84EB641C019440A21B1` |

Large artifacts and raw logs remain ignored on the GCP VM. The final detached candidate pass took 130 seconds; `/work` free space moved from about 184 GiB to 181 GiB, available RAM remained about 60–61 GiB, and no swap was used. Persistent evidence is under `/work/build-logs/ubox10-a16-prototype-a/20260821T150330Z/`.

## Offline audit result

- ext4: candidate system and preserved vendor/product/vendor_dlkm pass read-only `e2fsck`.
- VINTF: system-side PASS; full exact exit 65 with only the inherited NFS kernel-config deviation above. The two device display HAL omissions are closed.
- linker/ELF: A16 linkerconfig generates vendor/VNDK 31 namespaces and `libaudioroute.so` exposure. Inventory finds 1,769 ELF objects, zero unresolved ELF32/ELF64 names, and no AArch64 userspace ELF.
- SELinux: exact A16 platform/system_ext plus accepted API-31 vendor split policy compiles after the one-rule ownership fix; system file labels remain.
- LP: official `lpdump`/`lpunpack` confirm metadata 10.2, three identical slots, `virtual_ab_device`, unchanged 3,221,225,472-byte super geometry and 1,651,167,232-byte system allocation. Vendor/product/vendor_dlkm and B-slot bytes remain exact.
- AVB: candidate system embedded hashtree and vbmeta_system chain verify with the established project test key. Rollback index `1644019200`, location 1 and accepted top-level `vbmeta.fex` are preserved; FEC remains absent as declared.
- outer container: 46/50 entries are byte-preserved. Only `super.fex` and `vbmeta_system.fex` are replacements; `Vsuper.fex` and `Vvbmeta_system.fex` are regenerated companions. IMAGEWTY verifies all 12 checksummed payloads with zero mismatch.
- validation: candidate SHA256SUMS, four focused tests and all 70 repository tests PASS; 25 skips are expected missing ignored historical fixtures.

## Decision and remaining boundary

离线证据曾支持申请一次 UART-first ARM32 boot；该授权已使用。离线审计仍有效，但实机不接受 r1：白色 UBOX logo 后黑屏并循环重启。

PhoenixCard 日志 `logs/20260822-a-r1/uart-putty.log` 为 44,206 bytes / SHA-256 `C4823F59F09FA2ED60E5F35251641B0B0E9ABFAFEF1318F065DAFBED901E4D0C`，所有 download/MBR payload checksum 与 `CARD OK` 成功。UART `logs/20260822-a-r1/boot.log` 为 78,275 bytes / SHA-256 `18BF7217AFA25CAB2B7443B17A801D8825932FA4EB15ADCFC87D6FE1C3F46C7F`，包含 7 次 kernel start 与 6 个完整周期。每个完整周期证明 accepted 5.4.125 kernel、first-stage init、logical mapping/system mount、vendor/system_ext policy inputs、split SELinux 与 A16 second-stage init，随后在 `exec_start apexd-bootstrap` 边界失败并以 `bootstrap-apexd-failed` 重启。`servicemanager`、`zygote32`、`system_server`、SurfaceFlinger、HWC 均未到达；SELinux 为 permissive，不能声称 enforcing compatibility。

完整源代码和工件复核没有暴露 apexd 内部错误。五个 A16 bootstrap APEX 通过 exact host verifier，payload 为 clean ext4；apexd/bootstrap linker/依赖/labels 存在；exact kernel built-in 支持 loop、DM/verity、ext4、mount namespaces、SELinux、seccomp 与所需 crypto。`Could not update logical partition`、early secilc linkerconfig warning、missing blkio cgroup 和 reboot-path missing misc 分别属于 non-fatal fallback、预期时序 warning、独立 kernel risk 和 secondary noise；均不是已证明首错。

当前证据只支持把问题定为 **exact-board bootstrap APEX integration blocker**；既未证明 bounded fix，也未证明 ARM32 architecture-level blocker，因此不构建 r2。最小下一诊断设计是保持 r1 system/APEX/LP/vendor/kernel/ramdisk 不变，仅给 boot cmdline 追加 `printk.devkmsg=on`，并在另行授权后只采一个 UART 周期以取得 apexd 的内部失败；仍无输出时才给 `apexd-bootstrap` service 增加 `console`。Rollback 资产保持不变。
