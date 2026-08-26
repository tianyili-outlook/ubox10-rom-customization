# Android 16 QPR0 Prototype A r4 candidate

Status: **OFFLINE CHECKED / READY TO REQUEST PHYSICAL VALIDATION**.

`a16-prototype-a-r4` is a strict successor to physically exercised r3. Its only authorized
functional deltas are:

1. persist the EGL driver suffix as `ro.hardware.egl=mali` while preserving
   `ro.board.platform=apollo`;
2. map physical `sunxi-ir` Linux scanCode 352 to Android `DPAD_CENTER` / keyCode 23.

HDMI, audio, Wi-Fi, Ethernet, kernel, DT/DTBO and all other hardware authority are explicitly
out of scope and must remain unchanged. No physical action is authorized by this build task.

## Pre-build source-level causal closure

### EGL

The original r3 image has no `persist.graphics.egl` or `ro.hardware.egl`; accepted
`vendor_a/build.prop` supplies `ro.board.platform=apollo`. Physical evidence records the original
SurfaceFlinger failure when Loader tried suffix `apollo`, followed by Mali-G31/GLES 3.2,
SurfaceFlinger display connection, boot animation and `sys.boot_completed=1` after the field-only
`persist.graphics.egl=mali` override. Evidence is under
`docs/m8/device-tests/20260825-a16-prototype-a-r3-physical-validation/`.

Exact r7 `frameworks/native/opengl/libs/EGL/Loader.cpp` probes suffix properties in this order:
`persist.graphics.egl`, `ro.hardware.egl`, then `ro.board.platform`; the suffix selects
`/vendor/lib/egl/libGLES_<suffix>.so` (or the split equivalents). The source-native r4 integration
therefore adds only:

```make
PRODUCT_SYSTEM_PROPERTIES += \
    ro.hardware.egl=mali
```

to `device/ubox/ceiling/ubox10_ceiling_arm.mk`. This generates a read-only system property and
does not configure the diagnostic `persist.graphics.egl`. On fresh data, Loader sees
`ro.hardware.egl=mali` before the preserved board fallback. `ro.board.platform=apollo` remains in
the accepted vendor image and continues to name `gralloc.apollo.so` and `hwcomposer.apollo.so`;
the r4 change targets only the EGL suffix.

### sunxi-ir Remote OK

Physical evidence identifies `/dev/input/event0` as `sunxi-ir`, bus/vendor/product/version
`0019/0001/0001/0100`. Linux emits `MSC_SCAN 00ff400d`, `KEY_OK` DOWN/UP, scanCode 352. Android
r3 loads `/system/usr/keylayout/Generic.kl`; that file comments 352 and maps 353 to
`DPAD_CENTER`, so InputDispatcher records `UNKNOWN(0), scanCode=352`.

Exact r7 `frameworks/native/libs/input/InputDevice.cpp` probes, in order, an exact
vendor/product/version layout, a vendor/product layout, then the canonical device name. The
canonical name of `sunxi-ir` is unchanged, so `/system/usr/keylayout/sunxi-ir.kl` is the correct
device-specific fallback before `Generic.kl`. Because Android does not merge a device `.kl` with
`Generic.kl`, a one-line-only file would break the already working keys. The r4 file is therefore
byte/line-equivalent to the exact r7 Generic layout used by r3 except for one line:

```text
# key 352 "KEY_OK"        ->        key 352   DPAD_CENTER
```

All mappings for UP/DOWN/LEFT/RIGHT/BACK/HOME/volume/mute/power/menu and every other existing
scanCode remain identical. The exact source file is
`device/ubox/ceiling/sunxi-ir.kl`, installed by `PRODUCT_COPY_FILES` only for the `sunxi-ir`
lookup path.

## Build and audit result

The exact source remains `android-security-16.0.0_r7`, manifest
`ebea28d151539ecf0730b1a4ab92ac33edc17ac9`, BP2A.250805.034/API 36/SPL 2025-08-05. The
246,298-byte pinned manifest hashes to
`F52BA4A04957CEC7EEE7C9DCDD1525533156A0B5A1F0ADFC31A8155F48FB087E`. The existing source
audit passed before the build. Product identity remains ARMv7-A NEON, `armeabi-v7a,armeabi`, no
secondary architecture or 64-bit ABI, `zygote32`, shipping API 31, VNDK31 and pKVM disabled.

The exact successful build command was:

```sh
OUT_DIR=out-ceiling BUILD_NUMBER=UBOX10_A16_QPR0_R4 m -j8 systemimage
```

It ran on native Ubuntu/ext4 with 8 vCPU, about 62 GiB RAM and no swap from
2026-08-26 07:35:29 UTC to 07:39:29 UTC. The wrapper returned 0 after 240 seconds; Ninja
completed 43/43 actions and reported 3:37. Eight resource samples show minimum available memory
53,410,400 KiB, zero swap, minimum `/work` free 25,236,140,032 bytes and maximum load1 2.67.
The source output `system.img` is 931,934,208 bytes / SHA-256
`471C20FC1C925F24C6A7990FA6904E78A769F2B9E02EED2C45E3F0873B43BB07` and passed
`e2fsck -fn`.

The first build attempt stopped before compilation at the inherited ATV system-artifact path
enforcement because the new device layout path was not declared. The bounded harness correction
added only `system/usr/keylayout/sunxi-ir.kl` to
`PRODUCT_ARTIFACT_PATH_REQUIREMENT_ALLOWED_LIST`; no product composition or subsystem scope was
broadened. The complete raw log, first-failure record, pinned manifest and resource samples are
outside Git under
`/work/build-logs/ubox10-a16-prototype-a-r4/20260826T072627Z/`.

### Exact artifacts

| Artifact | Size (bytes) | SHA-256 |
|---|---:|---|
| `out/candidates/a16-prototype-a-r4/x12-a16-prototype-a-r4.img` | 1239746560 | `E125DD8FFB9F5B4A7B2B9B86DD8377367409AB00D1B29BE1E719CE25768E2111` |
| candidate `system_a.img` | 1651167232 | `F6437E0F7EDBAACF10B316A4DFCFEF916570766F9B0AAA4E72421C10C10D9001` |
| `super.fex` | 1059948504 | `02C9DCDF8E1E03EBC2639B652F39B21A1A39305F2767DC29E85EEE6C822461BA` |
| `vbmeta_system.fex` | 1472 | `755A8901BBBD0BECCF30D758607825E2422DB2B4D78D1A28FDF7183CAD4D633F` |
| byte-preserved `boot.fex` | 67108864 | `527CF878B015CFAE4E8600BD750C7C73F45F4290B5CFEFEDBD1AD9AC347B8063` |
| byte-preserved `vendor_dlkm_a.img` | 6680576 | `488EE1E14E7ADEEB198C546325E3AB756025B94BE295EFCAD8089B881ABD4C07` |

### Offline closure

The final image contains exactly `ro.hardware.egl=mali`, retains
`ro.board.platform=apollo`, contains no default `persist.graphics.egl`, and retains the exact
accepted ARM32 `libGLES_mali.so`, `gralloc.apollo.so` and `hwcomposer.apollo.so`. The installed
`/system/usr/keylayout/sunxi-ir.kl` is byte-identical to the tracked source and differs from exact
r7 `Generic.kl` only at line 311: scanCode 352 is `DPAD_CENTER` / Android keyCode 23. It is not
`UNKNOWN`, `BUTTON_SELECT` or `ENTER`; every other keylayout line is unchanged.

The r3-to-r4 system content/type inventory has no removals. It adds only
`system/usr/keylayout/sunxi-ir.kl`; four files change:

- `system/build.prop`: r4 build-generated identity plus `ro.hardware.egl=mali`;
- product and system_ext `build.prop`: r4 number/date/fingerprint only;
- `system/etc/NOTICE.xml.gz`: only the generated notice association for `sunxi-ir.kl`.

There is no unrelated functional filesystem delta. The machine-readable audit is embedded in
the local candidate as `offline-audit/system-tree-delta.json`; its durable classification is in
`a16-prototype-a-r4-preservation.json`.

All four ext4 images pass `e2fsck -fn`. System AVB/hashtree, `vbmeta_system`, rollback
index/location, LP 10.2 geometry, three metadata slots, empty B slots, sparse/raw round trip and
IMAGEWTY verify pass. The outer image still contains 50 payloads; only `super.fex`,
`vbmeta_system.fex`, `Vsuper.fex` and `Vvbmeta_system.fex` change, while 46 are byte-exact r3.
Accepted vendor/product, boot/kernel/ramdisk/boot AVB, vendor_dlkm and all 22 modules,
vendor_boot, DT/DTBO, TEE, DRM, factory/security, bootloader, top-level vbmeta,
rollback/recovery and unrelated hardware payloads are preserved. The kernel was not rebuilt:
it remains `5.4.302+`, Image SHA-256
`287A82F799982FB58D02ADE88150A9EAB22D4C0956BE3CE50765F6FD1DB24F40`, exact Path-A six-config
contract and accepted AIC FMAC upload/patch-read/START_APP addresses
`0x00120000`/`0x00120180`/`0x00120000`.

All 35 installed APEXes parse and activate offline; runtime and VNDK31 bootstrap inputs and ARM32
`libaudioroute.so` are present. Generated linkerconfig exposes the vendor VNDK31 namespace and
required library set. The 1,816-ELF inventory has no AArch64 userspace consumer or unresolved
ELF32/ELF64 name; ELF64 BPF objects remain classified as bytecode. Exact split SELinux compiles
offline without a new delta, which is not an enforcing-runtime claim. System-only VINTF passes;
full VINTF returns 65 / INCOMPATIBLE solely for the inherited `CONFIG_NFS_FS=y` versus FCM-6
required `n`. No unexpected VINTF incompatibility appears and full VINTF is not called PASS.

HDMI is **UNCHANGED / OPEN**. Audio is **UNCHANGED / OPEN**. Wi-Fi is **UNCHANGED** and
association/DHCP/L3/DNS still require physical validation. Ethernet is **UNCHANGED / preservation
expected**. No r4 physical action occurred, so EGL and Remote OK are not claimed as physical
passes. Gate 2 is **NOT CLOSED / PENDING r4 PHYSICAL VALIDATION**; Prototype B remains closed.

Focused r4 tests pass 5/5 against the actual local candidate. r3 contract regression passes 5/5;
kernel checkpoint/r5/outer-packer preservation tests pass 11/11. The full repository suite passes
106/106 with 25 expected skips for absent ignored historical fixtures. Python syntax compilation,
post-build exact r7 source audit and `git diff --check` pass. No physical-action command exists in
the build or audit paths.

## Physical validation contract

Any later test requires separate authorization. Flash r4 as a fresh candidate, then make no UART
intervention, `setprop` or property edit. The first boot must automatically reach Android 16 UI,
Mali-G31, stable SurfaceFlinger and `sys.boot_completed=1`. The minimal property checks are:

```sh
adb shell getprop persist.graphics.egl
adb shell getprop ro.hardware.egl
adb shell getprop ro.board.platform
adb shell getprop sys.boot_completed
```

Expected values are empty, `mali`, `apollo`, and `1`, respectively. Validate the real remote in
this order: UP, DOWN, LEFT, RIGHT, OK, BACK, HOME. Then retain `adb shell dumpsys input` evidence
that `sunxi-ir` scanCode 352 resolves to `DPAD_CENTER` / keyCode 23.

Separately regression-check HDMI, audio, Wi-Fi and Ethernet. Classify those as preservation or
known-open results: r4 did not attempt to fix any of them. HDMI stability and the legacy audio HAL
remain open; Wi-Fi association/DHCP/L3/DNS remains untested; Ethernet preservation is expected.
