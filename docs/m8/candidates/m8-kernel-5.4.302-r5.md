# M8 Linux 5.4.302 FMAC address-contract correction r5

Offline date: 2026-08-24
Physical evidence date: 2026-08-25
Status: **PHYSICAL PASS / WI-FI PASS / PRESERVATION CHECKPOINT CLOSED**

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
unchanged. This was a bounded contract correction; the later physical result is recorded below.

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

## Physical validation

The user physically tested r5 and supplied authoritative external ADB evidence. The original raw
captures were not found on the accessible VM, so
`docs/m8/device-tests/20260825-m8-kernel-5.4.302-r5/` preserves the reviewed facts/excerpts and
explicitly does not claim raw-file archival or hashes.

Linux reported:

`Linux localhost 5.4.302+ #1 SMP PREEMPT Thu Aug 13 22:30:00 +08 2026 armv8l`

`sys.boot_completed=1`. System boot, HDMI, Wi-Fi connection, Wi-Fi ADB, physical remote,
Leanback framework, TV input method and launcher all passed. Loaded runtime modules included
`aic8800_fdrv`, `aic8800_btlpm`, `aic8800_bsp` and `sunxi_rfkill`, with BSP referenced by FMAC.
Initial Wi-Fi logs showed the expected 2022-11-08 driver tag, subsystem ON, SDIO probe, 66 MHz
clock, `rwnx_init_aic()` and supplicant startup.

The initial filtered result for `timeout|wifi start fail|reqcfm|1037|1038` was **EMPTY**. This is
negative evidence; there is no non-empty error file to archive or describe.

A physical Wi-Fi OFF → ON cycle then proved clean removal (`wlan0: CLOSE`, interface/SDIO and
bus/thread teardown, subsystem state 0) followed by fresh subsystem state 1, SDIO probe, 66 MHz,
FMAC and supplicant initialization. One `aicsdio: write retry: 20` was observed, but startup
continued to full function; it is a non-fatal transient, not a basis for more generic SDIO work.
The post-cycle filtered result for the same expression was again **EMPTY**.

Android progressed through ASSOCIATING, ASSOCIATED, four-way/group handshake and COMPLETED,
succeeded at DHCP, assigned `192.168.1.8/24` with gateway `192.168.1.254`, entered
`L3ConnectedState`, and reported connected/validated on `wlan0`. Both `8.8.8.8` and
`www.google.com` returned 4/4 packets with 0% loss; the latter also proves DNS resolution.
Wi-Fi ADB reconnected after the cycle.

The r1-r4 `START_APP 1037 -> reqcfm(1038) timeout` did not recur initially or after one physical
reinitialization. Restoring the working BSP's `0x00120000` upload/boot contract after r1-r4's
wrong `0x00110000` guard-selected placement is therefore accepted as the engineering root cause,
with strong single-variable physical corroboration. This does not assert unproven boot-ROM or
firmware internals.

## Decision

**R5 PHYSICAL PASS / WI-FI PASS.** The same-lineage Linux 5.4.302 kernel/wireless preservation
checkpoint is **CLOSED / PASS**. No further SDIO-clock guessing, generic MMC revert, START_APP
instrumentation or r6 kernel diagnostic is justified by current evidence.

This closure removes the kernel/wireless block from Path A but does not itself make Android 16
Gate 2 pass. The separate exact QPR0 source audit governs the next architecture decision.
