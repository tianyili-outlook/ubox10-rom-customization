# Android 16 QPR0 Prototype A r3 candidate

Status: **PHYSICALLY BOOTED WITH PRE-EXISTING RUNTIME EGL OVERRIDE / FORMAL CANDIDATE CLOSURE
PENDING**. The original image's first physical blocker is EGL driver selection: neither
`persist.graphics.egl` nor `ro.hardware.egl` was supplied. With the user's pre-existing runtime
`persist.graphics.egl=mali` override, Android 16/zygote32/system_server/SurfaceFlinger and Mali
GLES are physically proven. This validation did not flash, reboot, rebuild or repack r3.
Prototype B remains closed.

## Exact source and product

The source workspace was reproducibly transitioned from its retained clean r4 checkout to exact
`android-security-16.0.0_r7`. The checked manifest identity is
`ebea28d151539ecf0730b1a4ab92ac33edc17ac9`; the pinned manifest is 246,298 bytes / SHA-256
`F52BA4A04957CEC7EEE7C9DCDD1525533156A0B5A1F0ADFC31A8155F48FB087E`. The built platform
identifies as `BP2A.250805.034`, Android 16, API 36.0, REL and SPL 2025-08-05. The source audit
script passes after the transition and again after the build. Repo status after the build contains
only the deliberate one-line tracked `system/sepolicy` deletion; the unmanaged UBOX product is
byte-equal to its tracked repository inputs.

The historical r4 Prototype A product was ported with the minimum release-native delta:

- lunch changed from `ubox10_ceiling_arm-bp4a-userdebug` to
  `ubox10_ceiling_arm-bp2a-userdebug`;
- build identity changed to `UBOX10_A16_QPR0_R3` on the r7/BP2A release;
- ARMv7-A NEON remains the only Android architecture, with no secondary architecture;
- primary ABI list remains `armeabi-v7a,armeabi`, the 64-bit ABI list is empty, and the accepted
  exact-board property selects `ro.zygote=zygote32`;
- shipping API 31, extra VNDK 31, Android TV/Leanback GSI composition and pKVM-disabled product
  policy remain;
- the device matrix contains only `vendor.display.config@1.0::IDisplayConfig/default` and
  `vendor.display.output.IDisplayOutputManager/default (@2)`;
- the only platform-policy change is removal of platform `genfscon fuseblk /`, leaving the
  accepted API-31 vendor policy as owner of that exact rule.

The retained ARM64 lunch definition is historical source material only. It was not selected or
built, and no mixed-mode work was started.

## Android build

The complete command was run in the native Ubuntu/ext4 workspace with relative
`OUT_DIR=out-ceiling`, unset `SOONG_GOMEMLIMIT`/`GOMEMLIMIT`, and no taskset, cgroup wrapper,
swap or Soong memory patch:

```text
source build/envsetup.sh
lunch ubox10_ceiling_arm-bp2a-userdebug
OUT_DIR=out-ceiling BUILD_NUMBER=UBOX10_A16_QPR0_R3 m -j8 systemimage
```

The build ran from 2026-08-25 02:50:01 UTC through 12:12:31 UTC and returned 0 after all
121,285 actions; the build-reported wall time was 09:22:26. Across 1,123 resource samples,
available RAM bottomed at 11,958,444 KiB, swap remained zero, `/work` available space bottomed
at 39,455,129,600 bytes, and maximum one-minute load was 46.57. The source `system.img` is
931,926,016 bytes / SHA-256
`2963A982345C25F26F3128CC1A40E41B64FB6EBDEA412E89C1EAFE3C258750EC`.

The exact raw build log and resource samples remain outside Git under
`/work/build-logs/ubox10-a16-prototype-a-r3/20260825T024351Z/`. Durable source, command,
time, status, resource extrema and artifact identities are recorded here and in
`configs/candidates/a16-prototype-a-r3.json`.

## Path-A kernel

The kernel was rebuilt from retained integration commit
`027ef79e8facb73cb2419b4a08c0bd3f13a2206e` / tree
`b328c32712d65f8da98e013bc74944d68c05552b` with the tracked Path-A config. The clean
Image/module build completed in 788 seconds with release `5.4.302+`. Image is 23,498,760 bytes /
SHA-256 `287A82F799982FB58D02ADE88150A9EAB22D4C0956BE3CE50765F6FD1DB24F40`;
the exact config SHA-256 is
`2A159B7EAF3ED96988F169A022A927B440A5D786F20C490D7AF004760F4B4F29`.

The effective delta from preservation config is exactly the six selected additions:

| Contract | Options |
|---|---|
| Android cgroup/process groups | `CONFIG_BLK_CGROUP=y`, `CONFIG_CPUSETS=y`, `CONFIG_PROC_PID_CPUSET=y` |
| QPR0 netd rate limiting/release | `CONFIG_NET_CLS_MATCHALL=y`, `CONFIG_NET_ACT_POLICE=y`, `CONFIG_NET_ACT_BPF=y` |

`MEMCG`, BTF, IncFS and the prohibited speculative 5.10-class features remain disabled. All 22
modules were rebuilt as one matched set; module inventory, dependency graph, vermagic,
MODVERSIONS/import CRCs and hardware-critical config close. Generic MMC/SDIO, DT authority,
firmware authority and the 70 MHz AIC functional request remain unchanged. Final
`aic8800_bsp.ko` proves FMAC upload `0x00120000`, patch/read `0x00120180`, and START_APP
`0x00120000`. No `m8-kernel-5.4.302-r6` was created.

## Exact-board integration and artifacts

`scripts/build-a16-prototype-a-r3-candidate.py` used the established AVB, LP, ext4 and
IMAGEWTY tooling. It replaced the r5 system extent with r7, rebuilt boot and the complete
vendor_dlkm module set from the Path-A build, and left the accepted vendor/product and all other
hardware authority unchanged.

| Artifact | Size | SHA-256 |
|---|---:|---|
| `out/candidates/a16-prototype-a-r3/x12-a16-prototype-a-r3.img` | 1,239,738,368 | `FA47939654B4E2A7E14FE963C7819296157338D33355E75D89E8086356071F1B` |
| `system_a.img` | 1,651,167,232 | `0B320FAB8050026BA359CD16E76165ABC2B4D26001805EA62B93958B66138E77` |
| `boot.fex` | 67,108,864 | `527CF878B015CFAE4E8600BD750C7C73F45F4290B5CFEFEDBD1AD9AC347B8063` |
| `vendor_dlkm_a.img` | 6,680,576 | `488EE1E14E7ADEEB198C546325E3AB756025B94BE295EFCAD8089B881ABD4C07` |
| `super.fex` | 1,059,940,312 | `C2C2EC7538225CA5FE40CE65AA7DE84BE5D4BCED166E96868A29BC076F1FCE52` |
| `vbmeta_system.fex` | 1,472 | `90D8025CE7013824A4AAA78DE17D2627AD077C921DAFA6299375526AFF19D92E` |

The machine-readable changed/preserved classification is
`docs/m8/candidates/a16-prototype-a-r3-preservation.json`.

## Full offline audit

- Filesystems: system/vendor/product/vendor_dlkm all pass `e2fsck -fn`. System was minimized to
  850,112,512 filesystem bytes before AVB and has 801,054,720 bytes of allocation headroom.
- AVB: system SHA256_RSA2048 hashtree verifies with no FEC; `vbmeta_system` verifies with rollback
  index 1644019200 at location 1. Changed boot hash footer and vendor_dlkm hashtree/FEC verify.
  The accepted top-level vbmeta and its rollback contract remain byte-preserved.
- LP/super: metadata 10.2, three slots, `virtual_ab_device`, 3,221,225,472-byte geometry,
  partition sizes/extents and empty B slots are exact. Sparse-to-raw round trip is byte-exact;
  every byte outside system_a and vendor_dlkm_a extents is unchanged.
- Outer container: IMAGEWTY verifies all expected checksummed payloads. Exactly six of 50 entries
  change: `boot.fex`, `super.fex`, `vbmeta_system.fex` and their three `V*` checksum companions.
  The other 44 payloads are byte-exact.
- ABI: 1,816 ELF objects were inventoried with zero unresolved ELF32 or ELF64 names. There are no
  AArch64 platform userspace consumers, no secondary ABI, no `app_process64`, no `linker64`, and
  the selected zygote is 32-bit. Fifteen ELF64 objects are Linux BPF bytecode, not AArch64
  userspace. The official ARM CTS shim contains one inactive test-only `arm64-v8a` JNI payload,
  as it did in r1; it cannot be selected by the ARM32-only ABI list and is not an AArch64
  platform consumer. The 22 ELF64 AArch64 objects in vendor_dlkm are kernel modules.
- VNDK/linker: the actual ARM32 `com.android.vndk.v31` APEX contains `libaudioroute.so`.
  Exact r7 host linkerconfig, invoked in offline Treble mode, generates `[vendor]`, the
  `/apex/com.android.vndk.v31/${LIB}` namespace and `default -> vndk` exposure including
  `libaudioroute.so`. Accepted vendor dependency/name closure has no unresolved mandatory name.
- APEX: all 35 installed r7/BP2A APEXes parse with `host_apex_verifier`; `apexd_host` activates all
  35 and produces a consistent apex-info list. Runtime and VNDK31 bootstrap inputs and payload
  filesystems are present. This is offline structure proof, not bootstrap runtime proof.
- SELinux: exact r7 platform/system_ext plus accepted API-31 vendor policy compiles after only the
  one-line `fuseblk` deferral. This does not claim enforcing-runtime compatibility.
- VINTF: system-side `--check-one` returns 0/PASS. Full exact `--check-compat` returns 65 and is
  **INCOMPATIBLE**, solely because inherited `CONFIG_NFS_FS=y` conflicts with the FCM-6 required
  `n`. Both accepted display HALs close and no new incompatibility appears. Full VINTF is not
  represented as PASS, and NFS was not changed to make the report green.
- Kernel: release/config, all six additions, 22-module ABI/CRC closure, r5 FMAC contract,
  hardware config, DT, firmware and generic MMC/SDIO preservation all pass offline checks.

The final offline report is 6,211 bytes / SHA-256
`8D5F1822D67C84F6AB8D46041C95B76D73835916F10E02D4249030A780DEFF51`.
The r3-focused suite passes 5/5, the combined r3/kernel-preservation focus passes 22/22, and the
full repository suite passes all 101 tests with 25 expected skips for absent ignored historical
fixtures. The exact r7 source audit, Python/shell syntax checks and `git diff --check` also pass.

## Physical validation result — 2026-08-25

Evidence: `docs/m8/device-tests/20260825-a16-prototype-a-r3-physical-validation/`.

The Ethernet-ADB validation proved Android 16/API 36/BP2A, ARM32-only `zygote32`, Linux
5.4.302+, all six Path-A kernel options, boot completion, active runtime/VNDK APEX mounts, three
service managers, system_server, SystemUI, TV/Leanback launcher and LeanbackIME. The old
bootstrap/bpfloader fatal filters are empty.

The original r3 graphics state had neither EGL selector. The user-provided pre-validation log
records SurfaceFlinger failing to load drivers from `ro.board.platform=apollo`. Before this
evidence session the user had already set `persist.graphics.egl=mali`; with that override present,
SurfaceFlinger reports ARM Mali-G31 / OpenGL ES 3.2 and composed layers. This is direct proof that
Path A's core ARM32 architecture is viable, but not proof that the unmodified r3 image closes the
graphics contract. The formal next integration direction is `ro.hardware.egl=mali` while
preserving `ro.board.platform=apollo`; it is **NOT IMPLEMENTED / NOT BUILT / NOT PHYSICALLY
VALIDATED** here.

Hardware preservation is mixed:

- Ethernet, gateway/IP/DNS connectivity and Ethernet ADB PASS.
- AIC modules, wlan0, framework enable, active scan and clean Wi-Fi OFF→ON reinitialization PASS;
  association/DHCP/L3/DNS are **NOT TESTED** because no saved network or credential input path
  was available.
- Every requested IR key emits Linux DOWN/UP events. UP/DOWN/LEFT/RIGHT navigation is physically
  accepted, while OK FAILS at Android mapping: scanCode 352 becomes `KEYCODE_UNKNOWN` because
  `Generic.kl` maps only 353 to DPAD_CENTER. The 352 mapping is **NOT IMPLEMENTED**.
- TV/Leanback/launcher/IME inventory and runtime focus PASS. Text entry itself is not claimed.
- Physical HDMI stability FAILS: the monitor repeatedly shows about one second of picture then
  about five seconds black. During bounded sampling SurfaceFlinger/system_server stayed alive,
  extcon remained `HDMI=1`, and the display engine stayed unblanked at 3840x2160 YUV444 mode 34
  with advancing interrupts and no skip/error increment. Kernel history also contains HDMI
  disconnect/connect transitions. The precise physical black-cycle root cause is not proven.
- ALSA/Apollo/AudioFlinger topology reaches `ahubhdmi` / `AUDIO_HDMI`, physical volume and mute
  update framework state, and automatic service recovery works. The legacy HIDL vendor audio HAL
  repeatedly null-dereferences in `Device::getAudioPortImpl`; observed HDMI status transitions
  enter that crashing path. Plain AudioFlinger/AudioPolicy dumps did not independently trigger a
  new crash in the isolation window. HAL stability is FAIL. Basic/HDMI audible output is **NOT
  TESTED** because the attached monitor has no audio output; a completed `tinyplay` call is not
  relabeled as audible proof.

## Decision and boundary

The exact decision is **CORE PATH-A ARCHITECTURE VIABILITY PHYSICALLY PROVEN / FORMAL CANDIDATE
CLOSURE PENDING**. Gate 2 is **NOT CLOSED**: the proof currently depends on a runtime EGL
override, physical HDMI is unstable, the vendor audio HAL is unstable, Wi-Fi association was not
tested, and enforcing SELinux is not proven. Do not represent r3 as an unqualified runtime PASS.

The next GCP image may integrate only evidence-led bounded changes: add
`ro.hardware.egl=mali` without replacing `ro.board.platform=apollo`, map sunxi-ir scanCode 352 to
DPAD_CENTER, and diagnose the observed 4K60 YUV444 HDMI/link plus HIDL `getAudioPort` transition
path before choosing a display/audio change. Wi-Fi BSP/HAL must remain unchanged on this evidence;
association requires a later credential-capable physical validation. Prototype B,
`zygote64_32`, secondary ABI and ARM64 Mali/mapper integration remain closed until a no-runtime-
intervention Prototype A candidate passes the required physical gates.

## Ordered next-step plan

This handover records the plan only; no successor property, keylayout, display, audio or Wi-Fi
change is implemented, built or physically validated.

1. For the next bounded GCP candidate, integrate `ro.hardware.egl=mali`, preserve
   `ro.board.platform=apollo`, and make graphics boot without runtime `setprop` intervention.
2. Map only sunxi-ir scanCode 352 to DPAD_CENTER; preserve every other physically verified key.
3. Starting from the observed 3840x2160 YUV444 mode 34 / 60 Hz state, isolate the HDMI timing,
   link and receiver-lock boundary. Stable framework/display counters do not make the physical
   one-second-picture/five-second-black cycle pass; do not replace the display stack arbitrarily.
4. Trace the HDMI-transition path into the legacy HIDL `getAudioPort` null-pointer SIGSEGV.
   A null callback/function pointer is high-confidence/likely, but the exact source-level cause
   is not proven and no fix may be claimed yet. Later acceptance requires an HDMI sink with
   actual audio output for basic and HDMI audible playback tests.
5. Preserve the current AIC BSP/modules, Wi-Fi HAL and firmware. Use a credential-capable later
   session to test association, DHCP, validated L3 and DNS over Wi-Fi.
6. Accept a successor only when it preserves rollback and an exact artifact hash and passes with
   no runtime EGL intervention, stable physical HDMI, physical remote OK, Wi-Fi association,
   vendor audio HAL stability and real audio-sink playback.
7. Keep Gate 2 not closed and Prototype B, `zygote64_32`, secondary ABI and ARM64 Mali/mapper
   work closed until Prototype A meets that no-intervention acceptance contract.
