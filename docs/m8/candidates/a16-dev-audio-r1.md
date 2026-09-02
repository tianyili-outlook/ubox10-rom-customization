# a16-dev-audio-r1

Status: **PHYSICAL VALIDATION PASS / P1 ARM32 AUDIO STARTUP CRASH CLOSED / DEVELOPMENT AUDIO
COMPATIBILITY CANDIDATE / NOT r8 / NOT RELEASE**

This is the first post-Gate3 development candidate. It is composed from exact physically proven
`a16-prototype-b-r7-hevc-abi-compat1a-sdr-shadow-fd` (1,641,822,208 bytes,
`9E9592BF...F75722`). Canonical r7 remains frozen, Gate 3 remains closed as
`PASS_WITH_EXPLICIT_USER_WAIVER`, and the compat1a SurfaceFlinger repair remains byte-identical.

## Root cause and bounded correction

The retained ELF32 Apollo HAL allocates `audio_hw_device`, reports `common.version=0x0700`, but
leaves both `get_audio_port` and mandatory `get_audio_port_v7` null. HIDL audio 7.0 selected the v7
entry for API >=3.2 and ultimately executed `blx r2` with `r2=0`, producing the one-shot startup
`SIGSEGV/SEGV_MAPERR` at PC zero. This is a malformed legacy HAL API/function-table contract, not a
direct ARM32/ARM64 `audio_port_v7` layout mismatch.

`Device::getAudioPort` now checks only the malformed >=3.2 case. A null v7 callback completes the
HIDL callback with `Result::NOT_SUPPORTED` and the unchanged input `AudioPort`; a valid v7 callback
continues through the existing implementation. The pre-3.2 legacy path remains unchanged. There is
no fallback to `get_audio_port`, capability fabrication, version rewriting, HDMI-route change,
delay, retry, service restart or proprietary binary patch.

The reproducible overlay is
`configs/aosp/architecture-ceiling-a16/development/audio-r1/`. The installed baseline wrapper is
from the retained Android 12 source generation, so the overlay projects that pinned implementation
and matching FMQ ABI header before applying the one behavioral guard. The `.string()` spelling
updates and narrow VNDK31 libc++ diagnostic back-deploy are compile compatibility only. The build
target is exactly `android.hardware.audio@7.0-impl_32`; no broad Android build was performed.

## ELF and disassembly proof

| Field | exact compat1a | audio-r1 |
|---|---:|---:|
| path | `/vendor/lib/hw/android.hardware.audio@7.0-impl.so` | same |
| size | 161,516 | 170,476 |
| SHA-256 | `87D7690E...A919A` | `E2F3D49D...062ED` |
| Build ID | `24bb9072069ca0c589325285f4aa7ca6` | `19c6cc53af86cf7482c266ffa0350777` |
| ELF / machine | ELF32 / ARM | ELF32 / ARM |
| SONAME / DT_NEEDED | retained | exact same 18 entries |

All required HIDL entry points, including `HIDL_FETCH_IDevicesFactory`, `Device::getAudioPort` and
`PrimaryDevice::getAudioPort`, remain exported. Current-toolchain template instantiation details
change the full incidental dynamic-symbol set (350→340 exports and 269→261 imports); this is
recorded rather than mislabeled byte-for-byte ABI identity. Every one of the 261 candidate strong
imports resolves in the exact retained ARM32 vendor/VNDK31 provider namespace, with no
`__libcpp_verbose_abort` import and no new DT_NEEDED.

The accepted pre-physical reconstruction control used the same projected wrapper/FMQ sources,
Android.bp, VNDK31 input, current toolchain, Soong target and build environment, but omitted the
null-v7 guard. It is 170,448 bytes / `F7CC10B...922A6`, Build ID
`75c52bc5102f9b09f8be859ec6a29d58`, with 261 strong imports and 340 dynamic exports. Thus the full
269→261 import and 350→340 export drift already occurs from compat1a to the unguarded control;
control and guarded audio-r1 have exactly identical dynamic import/export sets. Object/section
comparison found only `Device::getAudioPort` materially changed in executable code. A reverse scan
of 2,474 exact compat1a vendor/system/activated-APEX ELFs found no vendor consumer requiring any
removed export. Verdict: **`OFFLINE_RECONSTRUCTION_ABI_PASS` /
`READY_FOR_PHYSICAL_VALIDATION`**. The temporary control remains outside Git and was not packaged.

Thumb disassembly at `Device::getAudioPort` proves:

- compare against `0x0302`;
- load callback from `audio_hw_device + 0xa4`;
- `cbz` branches before helper invocation;
- null branch passes result value `4` (`NOT_SUPPORTED`) to the HIDL callback;
- valid >=3.2 branch still loads `+0xa4` and enters `getAudioPortImpl`;
- only the existing <3.2 branch reads `+0x94` (`get_audio_port`).

## Exact runtime and container delta

The signed-filesystem comparison from compat1a is exactly:

```text
system: added=[] removed=[] changed=[]
vendor: added=[] removed=[] changed=[lib/hw/android.hardware.audio@7.0-impl.so]
```

`/system/bin/surfaceflinger` remains 8,577,592 bytes / SHA-256
`06C960E6...CD0A5`. `libstagefright.so`, ARM32/ARM64 gralloc, mapper/Mali, OMX/Cedar, proprietary
Apollo HAL, HWC/display, Wi-Fi, product, boot, kernel and vendor_dlkm remain unchanged. Only
`super.fex`, `vbmeta_vendor.fex` and their outer companion payloads change mechanically because
the one vendor file was replaced and re-signed.

## Candidate and offline result

- image: `out/candidates/a16-dev-audio-r1/x12-a16-dev-audio-r1.img`
- size: **1,641,830,400 bytes**
- SHA-256: **`270B5D822AB3BB13D8EDCD9BE374DA1D6ED512D6D60063E123046C23B8AF9D62`**
- physical status: **PASS**

Read-only `e2fsck` passes for system/vendor/product/vendor_dlkm. System/vendor/vbmeta AVB, exact
compat1a LP metadata/extents, sparse→raw byte identity and IMAGEWTY outer verification pass.
System-side VINTF passes. Full VINTF remains **exit 65 / inherited `CONFIG_NFS_FS=y` versus FCM-6
`n` / NOT PASS**. Candidate construction and offline review issued no device command; the later
separately authorized physical session is recorded below and did not alter the image.

## Physical validation closure

The 2026-09-02 user-supplied evidence archive is retained outside Git at
`/work/physical-evidence/ubox10/a16-dev-audio-r1/20260902-214327/UBOX10-A16-DEV-AUDIO-R1-20260902-214327.zip`.
Its SHA-256 is `BDB3D13ECF54DF3CD1C7B3F6DC5D160DDF9D43CD51E6F1D66B8DC28910F09064`;
the outer checksum and all 48 internal manifest entries verify.

One continuous boot (`90882ee3-4884-445c-ae9c-cada3a1a6449`) passed BootGate, an explicit HDMI
disconnect/connect transition, AVC+AAC, compat1a HEVC+AAC, VP9+Vorbis, and the final census.
`audioserver` 534, ARM32 audio HIDL 504, SurfaceFlinger 547, system_server 787, zygote64 492 and
zygote32 493 remained continuous. The historical PC-zero `getAudioPortImpl` SIGSEGV is absent;
the HDMI transition reopened `AUDIO_DEVICE_OUT_HDMI` without an audio-service death or restart.
Final AudioFlinger reports hardware status 0 and output device `0x400` HDMI. Operator observations
record normal picture and HDMI audio for all three media smokes; raw logs independently confirm
Allwinner/Cedar AVC, HEVC and VP9 paths, successful compat1a HEVC imports, empty crash buffers and
no tombstone delta. The recorded VP9 fixture SHA-256 is
`FDED11EFF810E815C45F6E571952FF50644D0A4E1DB72B89C4D47370D62BD1ED`.

The Cedar `CdcIonUnmap`/`CdcIonMunmap` EINVAL messages, VP9/VLC `BAD_VALUE` and output-buffer calls
after Released state, and abandoned BufferQueue/EGL-window messages occur in player/activity
teardown after visible playback. With continuous critical PIDs, empty crash buffers and no new
tombstone, they remain **NON-BLOCKING / DEFERRED OBSERVATIONS**. This closure does not make the
candidate a release or r8 and does not expand Main10/HDR/AFBC/protected/4K scope. The executed plan
and evidence interpretation are recorded in
`docs/m8/device-tests/a16-dev-audio-r1-physical-plan.md`.
