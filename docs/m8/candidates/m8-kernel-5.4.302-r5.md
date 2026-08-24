# M8 Linux 5.4.302 FMAC address-contract correction r5

Date: 2026-08-24
Status: **OFFLINE CHECKED / PHYSICAL VALIDATION REQUIRED / GATE 2 CLOSED**

## Change

r5 starts from the r4 functional and diagnostic state and changes one source line in
`aic_bsp_8800d.c`: the `RAM_FMAC_FW_ADDR` guard now tests the build's actual
`AICWF_SDIO_SUPPORT` define instead of the absent `CONFIG_AIC_INTF_SDIO` preprocessor symbol.
The patch is `configs/kernel/m8-kernel-5.4.302/aic8800d-fmac-address-contract.patch`, SHA-256
`10BE1AE58CB900DBD8B5250960B2FBA3846CC29DFFF676DAE5D87D17EBCADBD3`. Before commit its diff
context was serialized without a blank context line so `git diff --check` remains clean; applying
either serialization yields the exact same one-line source tree, and the final-module audit was
rerun against the tracked form.

The r3 START_APP trace and r4 post-timeout CCCR instrumentation remain unchanged. Firmware,
patch/config files, 70 MHz request, MMC/SUNXI code, timeout/retry behavior, DT and userspace are
unchanged. This is a bounded contract correction, not a physical Wi-Fi result.

## Build and final-ELF proof

The clean build used integration commit `027ef79e8facb73cb2419b4a08c0bd3f13a2206e`, AOSP
clang-r416183b1 / clang 12.0.7, the exact r1 config, then the unchanged r3 and r4 patches followed
by the one-line r5 patch. It completed in 451 seconds with all 22 modules. Eight resource samples
show minimum available memory 63,060,996 KiB, minimum `/work` availability 63,248,040 KiB and
maximum load1 10.13; no swap, OOM or I/O failure occurred. Evidence is under ignored
`/work/build-logs/m8-kernel-5.4.302-r5/20260824T-r5-final/`.

Clean ThinLTO Image and several unrelated raw build modules retain the already documented
build-path/private-ID byte nondeterminism and are not candidate inputs. As in r2-r4, the candidate
reuses the exact r1/r4 Image and 21-module set, then replaces only the final audited BSP. This is
why the final candidate preservation result, rather than raw clean-build hashes, is authoritative.

The final packaged `aic8800_bsp.ko` is 129,976 bytes / SHA-256
`2BF0F46C69968408544D8F1B344C0999C6B2E69E03C7E24A5EB8D2A23133D03A`. Direct disassembly of
`aicbsp_8800d_fw_init` proves:

| Final module | FMAC upload | patch/read | START_APP |
|---|---:|---:|---:|
| r4 | `0x00110000` | `0x00110180` | `0x00110000` |
| r5 packaged BSP | `0x00120000` | `0x00120180` | `0x00120000` |
| accepted working 5.4.125 BSP | `0x00120000` | `0x00120180` | `0x00120000` |

The machine audit result is `PASS_R5_FMAC_ADDRESS_CONTRACT_ONLY`. r4→r5 source delta is exactly
the guard line; the r4 trace/CCCR strings remain in the final module; imports, exports, AIC symbol
CRCs, dependencies and `5.4.302+ SMP preempt mod_unload modversions aarch64` vermagic remain
valid. The candidate module root differs from r4 only at `aic8800_bsp.ko`; the other 21 modules
are byte-identical.

## Candidate and preservation

| Artifact | Size | SHA-256 |
|---|---:|---|
| `out/candidates/m8-kernel-5.4.302-r5/x12-m8-kernel-5.4.302-r5.img` | 1,031,739,392 | `A185B0A3C7516FBC9D34F61B3218171F07BDA00B84903A644D2D71FBB1DCC28F` |
| `aic8800_bsp.ko` | 129,976 | `2BF0F46C69968408544D8F1B344C0999C6B2E69E03C7E24A5EB8D2A23133D03A` |
| `boot.fex` | 67,108,864 | `338CB4048796E213698585E035D8807D84381324163C19AA939BD8D6BFDDCD2C` |
| `super.fex` | 851,940,812 | `EBF481D7229AC148A4FE252CB6B74DE5F747AE5C85E4C99948BE312CE9BAF008` |
| `vendor_dlkm_a.img` | 6,680,576 | `5B5AFE9B92FE07DE7423D81431B33D419549AFC2EE66467D4D59B4BC060C7D21` |

Relative to r4, outer changes are exactly `super.fex` and its `Vsuper.fex` checksum companion.
Boot/Image/ramdisk, DT/DTBO and the other 48/50 outer payloads are byte-identical. System,
vendor, product, firmware and Android userspace are byte-identical; LP metadata and bytes outside
the vendor_dlkm extent are exact. Exact U04 firmware identities remain:

- `fmacfw.bin`: 260,984 bytes / `FC3BC7865CBB01560E706E87FEA23F07CBF86B0E9F76649381D553FE8E781904`;
- `fw_adid_u03.bin`: 1,208 bytes / `6C7CC9D899D2A4E5B91B0F009AA6679498131ADC27D220B96EC162536370A190`;
- `fw_patch_u03.bin`: 64,204 bytes / `4B97D0F7C41F29EDB4B9082F0FB3B920770A8EF9C3F7E8D93C062AEDD9E778CD`;
- `fw_patch_table_u03.bin`: 1,336 bytes / `9EC1A1CC6A6249E3EE8302DC952D71C9F494FEC2A1A16499FFB72893C0A475ED`.

Vendor_dlkm ext4/e2fsck, AVB hashtree/FEC, sparse round trip, LP geometry, IMAGEWTY, candidate
SHA256SUMS and the focused r3/r4/r5 tests pass. The full repository suite reports 96 tests
passing with 25 expected local-fixture skips. Test8r2 rollback remains 2,005,954,560 bytes /
SHA-256 `6A52F3388E9ABF6AFA8A701CFD7198FE6C0090F16531F6E3BD3949E760892EC8`.

## Decision

**R5 OFFLINE PASS / PHYSICAL VALIDATION REQUIRED.** No physical UBOX action was performed or is
authorized by this record. Gate 2 remains **CLOSED**. r5 does not prove that Wi-Fi is fixed; only a
separately authorized UART-first physical test can determine whether corrected placement reaches
1038 and a working wireless runtime.
