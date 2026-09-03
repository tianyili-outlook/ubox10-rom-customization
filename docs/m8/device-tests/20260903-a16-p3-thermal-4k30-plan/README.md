# Android 16 P3-0 thermal observability and HEVC 4K30 plan

Status: **P3-0 RESEARCH / TOOLING PREPARED; P3-A PHYSICAL CAPTURE PENDING; P3-B NOT AUTHORIZED**.
This is an offline test contract, not physical evidence, a runtime change, a candidate, r8, or a release
qualification. Canonical r7 remains frozen; Gate 3 and P2 remain closed; the audio P1 remains closed.
`r8` remains **NOT AUTHORIZED / NOT BUILT**.

## Inputs and bottom line

The audit used the exact P2 result, the physically proven compat1a reports and patches, the retained
5.4.302 kernel/config/device tree, the exact `a16-dev-audio-r1` vendor codec XML and closed decoder
ELFs, the retained Allwinner/Mali gralloc source, and Android 16 ACodec/OMX sources. No device command
was run and no image/source was modified.

The thermal verdict is **PARTIAL OBSERVABILITY — SHORT SMOKE ONLY**. The retained kernel has four
H616/sun50iw9p1 THS sensors, CPU and GPU cooling integration, and source-backed CPU trip points. It
therefore has materially more protection/telemetry than Android's absent Thermal HAL suggests. What
offline work cannot prove is that the exact device's calibration data is valid or that normal ADB shell
can read the sysfs attributes. P3-A may proceed only after a read-only discovery capture proves a
plausible CPU temperature plus CPU-frequency visibility. Until then, sustained/looped/qualification
load remains blocked.

For 8-bit HEVC, the vendor declaration accepts the dimensions and the decoder publishes Main through
Level 5.2, while the measured-performance XML contains a 4096x2048 HEVC 20–90 fps entry. However,
the same codec XML limits throughput to 489,600 16x16 blocks/s, whereas 3840x2160 at 30 fps requires
972,000 blocks/s. The active contract therefore does **not** cleanly advertise 4K30. P3-A is a bounded
layer-localization experiment, not confirmation of vendor capability.

## Source and artifact provenance

| Input | Exact identity / relevant content |
|---|---|
| P2 result | `docs/m8/device-tests/20260903-a16-p2-boot-runtime-audit/README.md`; P2-001, P2-007/008/009/011/014 |
| Kernel config | `configs/kernel/m8-kernel-5.4.302/path-a-5.4.302.config`, SHA-256 `2a159b7eaf3ed96988f169a022a927b440a5d786f20c490d7af004760f4b4f29` |
| Exact retained DTB | `/work/build-logs/a16-prototype-b-fstab-audit-20260827/r4-vendor_boot/dtb`, 68,228 bytes, SHA-256 `24928802b99da546338141e4fc6f3dedf9e7de6fbe29306af4d038d838092f72`; documented byte-preserved through Prototype B |
| Decompiled matching DTS | `/work/src/ubox10-kernel-5.4.302-common/arch/arm64/boot/dts/sunxi/sun50i-h616-orangepi-zero3.dts` |
| THS driver | `/work/src/ubox10-kernel-5.4.302-common/drivers/thermal/sunxi_thermal.c` |
| Mali devfreq driver | `/work/src/ubox10-kernel-5.4.302-common/modules/gpu/mali-bifrost/driver/drivers/gpu/arm/midgard/backend/gpu/mali_kbase_devfreq.c` |
| Cedar driver | `/work/src/ubox10-kernel-5.4.302-common/drivers/media/cedar-ve/cedar_ve.c` |
| Vendor codec declaration | exact audio-r1 `/vendor/etc/media_codecs.xml`, SHA-256 `92db5dab000c0899352084fcc3d6e7cd4b55bd20be3947888d41c494e451c83f` |
| Vendor performance declaration | exact audio-r1 `/vendor/etc/media_codecs_performance.xml`, SHA-256 `e6beb24a74fd410b8ebad9de897a7bc0456e56169deaa11a9a8ad8816f8222ea` |
| Inactive HAL-era thermal config | exact audio-r1 `/vendor/etc/thermal_info_config.json`, SHA-256 `87db936f3518ffc90289c1535f2c84bb5a8b69a77f6992eadd9cd4547b54c131` |
| Active HEVC wrapper | exact audio-r1 `/vendor/lib/libOmxVdec.so`, ELF32 ARM, exported HEVC profile table inspected directly |
| Closed HEVC decoder | exact audio-r1 `/vendor/lib/libawh265.so`, ELF32 ARM, strings/symbols inspected directly |
| Gralloc formats | `configs/aosp/architecture-ceiling-a16/hardware/aw/gpu/include/hardware/graphics-sunxi.h` and `hardware/aw/gpu/mali-bifrost/gralloc/src/` |
| Compat1a boundary | `configs/aosp/architecture-ceiling-a16/diagnostics/r7-hevc-abi-compat1-sdr-shadow/patches/0001-skia-mali-sdr-metadata-shadow.patch` plus compat1a sized-memfd patch |

The platform naming in this report follows checked-in H616 evidence. The Allwinner `sun50iw9p1`
source name does not promote an H618 sales label into a confirmed chip fact.

## Thermal observability map

The active config enables `CONFIG_THERMAL`, OF thermal zones, thermal statistics, step-wise and power-
allocator governors, CPU thermal cooling, devfreq thermal cooling, `CONFIG_SUNXI_THERMAL`, CPUfreq,
devfreq, and the simple-ondemand devfreq governor. CPUfreq time/stat accounting is not enabled.

The exact retained DTB contains an enabled `allwinner,sun50iw9p1-ths` controller at `0x05070400`
with four sensor indices and an NVMEM calibration cell:

| Sensor index / expected type | Kernel registration | Polling / trips / cooling | Offline status |
|---|---|---|---|
| 0 `gpu_thermal_zone` | THS + DT | 1000 ms normal, 500 ms passive; no zone-local trip; referenced by CPU 90°C cooling map | PROVEN FROM SOURCE |
| 1 `ve_thermal_zone` | THS + DT | no periodic polling/trips in DT | PROVEN FROM SOURCE |
| 2 `cpu_thermal_zone` | THS + DT | 70,000 m°C passive; 90,000 m°C passive with CPU+GPU cooling; 115,000 m°C critical; 1000/500 ms polling | PROVEN FROM SOURCE |
| 3 `ddr_thermal_zone` | THS + DT | no periodic polling/trips in DT | PROVEN FROM SOURCE |

The THS driver explicitly returns **millidegrees Celsius**. It reads the `calibration` NVMEM cell and
applies the H616 calibration algorithm/offset when valid. The DT wiring is proven; actual per-device
calibration validity and plausible readings require a physical read-only probe. The vendor JSON's
0.001 multiplier and 75/85/110°C values are corroborating legacy HAL configuration only: because the
Android Thermal HAL is absent, they are not treated as the active kernel trip contract.

| Observation | Expected node/meaning | Classification before physical probe |
|---|---|---|
| Thermal zones | dynamic `/sys/class/thermal/thermal_zone*`; `type`, `temp`, trip attributes | LIKELY FROM SOURCE; normal-shell DAC/SELinux readability REQUIRES PHYSICAL READ-ONLY PROBE |
| Cooling devices | dynamic `/sys/class/thermal/cooling_device*`; type/current/max state | LIKELY FROM SOURCE; exact numbering/readability requires probe |
| CPU frequency | dynamic `/sys/devices/system/cpu/cpufreq/policy*`; current/min/max/governor/affected CPUs | PROVEN framework/config; exact runtime policies/readability requires probe |
| GPU frequency/load | Mali registers devfreq with `get_cur_freq`, busy/total status, 100 ms polling, simple-ondemand and devfreq cooling; dynamic `/sys/class/devfreq/*` | LIKELY FROM SOURCE; exact node name and shell-readable attributes require probe |
| VE temperature | `ve_thermal_zone` | PROVEN FROM SOURCE; live reads require probe |
| Cedar state | Cedar exposes read-only `ve_info`; driver logs clock rate around open/config | PARTIAL: debug/channel state may be readable, but no stable source-proven continuous VE frequency/load interface |
| VPU clock/load | possible read-only clock/debug nodes discovered dynamically | REQUIRES PHYSICAL READ-ONLY PROBE; NOT AVAILABLE as a guaranteed interface |
| Throttling inference | CPU/GPU frequency, cooling-device state, thermal log and temperature trend | LIKELY when the above nodes are readable; Android ThermalService cache remains unavailable |

`getenforce` was permissive in P2, but that does not bypass DAC and is not proof that any sysfs/debugfs
node is readable. `PERMISSION_DENIED`, `NOT_AVAILABLE`, empty nodes, and implausible values are evidence,
not reasons to elevate privileges.

## Read-only thermal observer

`scripts/collect-a16-p3-thermal-observability.ps1` has two modes:

- `Discovery` dynamically enumerates all visible thermal zones/trips, cooling devices, CPUfreq
  policies, devfreq nodes and bounded Cedar/GPU/VE read-only candidates, plus boot ID, critical PIDs
  and thermal-related log lines.
- `Sample` first performs the same discovery and then issues host-timed read-only snapshots every
  1–5 seconds for a bounded 5–120 seconds (defaults: 2 seconds / 60 seconds). Nothing is installed or
  left running on Android. Playback remains manual and external.

Every command records stdout, stderr, exit code, timing, timeout and a result class. Expected grep
zero-match is `EMPTY_SUCCESS`; actual permission/not-found/nonzero failures remain visible. Output is
host-side under `$HOME\Downloads\UBOX10-A16-P3-THERMAL-<timestamp>` with a JSON command manifest and
SHA-256 manifest.

Future discovery invocation (do not run until physical authorization):

```powershell
.\scripts\collect-a16-p3-thermal-observability.ps1 `
  -AdbPath 'C:\platform-tools\adb.exe' `
  -Endpoint '<current-device-LAN-IP>:7896' `
  -Mode Discovery
```

Future bounded sampling, started immediately before manual playback:

```powershell
.\scripts\collect-a16-p3-thermal-observability.ps1 `
  -AdbPath 'C:\platform-tools\adb.exe' `
  -Endpoint '<current-device-LAN-IP>:7896' `
  -Mode Sample `
  -SampleIntervalSeconds 2 `
  -DurationSeconds 60
```

The observer does not root/reboot/remount, write properties/settings/sysfs/procfs, alter CPU/GPU
governors or limits, start/stop processes, change network/HDMI/power, inject input, play media, run a
stress workload, clear logs, or take automatic shutdown/reboot action.

## HEVC 4K30 path and capability assessment

The path under test is Android/VLC → MediaCodec/ACodec → OMX Store →
`OMX.allwinner.video.decoder.hevc` → ARM32 Cedar/VE → native-window YUV buffers → retained Allwinner
gralloc/mapper → BufferQueue → ARM64 SurfaceFlinger/Skia → Mali EGL and/or HWC → HDMI. Successful codec
configuration is only the first layer, not a playback PASS.

| Scope | Static evidence | Current conclusion |
|---|---|---|
| HEVC Main 8-bit SDR 1920x1080 | OMX Main; physical Allwinner/Cedar/YV12 + compat1a evidence | PHYSICAL PASS for exact authorized 1080p scope |
| HEVC Main 8-bit SDR 3840x2160@30 | size max 6144x3160; Main Level 5.2; 4096x2048 measured 20–90 fps; but 489,600 blocks/s is below required 972,000 | DIMENSION/PERFORMANCE EVIDENCE MIXED; P3-A PHYSICAL CAPTURE PENDING |
| HEVC Main10 SDR 3840x2160@30 | closed decoder contains Main10/10→8/lower-bit paths and gralloc has 10-bit formats; public OMX table lacks Main10 | P3-B RESEARCH ONLY / NOT AUTHORIZED |
| HDR10/HLG/Dolby Vision | no validated end-to-end contract | OUT OF SCOPE |
| AFBC | active physical path and compat1a scope are non-AFBC | OUT OF SCOPE |
| protected/secure/DRM | no authorized validation and compat1a excludes protected usage | OUT OF SCOPE |

The ELF profile table exported by `libOmxVdec.so` is `{Main=0x1, MainTierLevel5.2=0x40000,
sentinel}`. It does not advertise Main10 (`0x2`). ACodec checks Main10 support when the input profile is
present, so Main10 may be rejected before decoder configuration despite the closed `libawh265.so`
containing latent Main10 and 10-to-8 code. Main10 is not synonymous with HDR; an eventual SDR Main10
test would still need separate authorization.

For Main 8-bit, the proven 1080 path emits linear YV12 and no static resolution-dependent output-format
switch was found, so YV12 is the leading 4K expectation. This is **LIKELY**, not proven: vendor NV12,
NV21, or another private format remains possible after port settings change. For Main10 the output is
unknown. Gralloc source defines Allwinner NV12/NV21/YV12 10-bit wrappers and P010 variants, and the
decoder mentions lower-two-bit buffers and 10→8 conversion; none proves which route is negotiated or
that old Mali/HWC imports it correctly.

### Compat1a at 4K

Compat1a deliberately requires the exact public and private 1920x1088 YV12, stride/plane, usage
`0x402d00`, non-AFBC, non-protected contract. A 3840x2160 buffer fails that predicate and goes to the
original AHardwareBuffer/Mali import path. It receives no shadow translation. If HEVC initializes the
same extended Allwinner metadata at 4K, Mali r20p0 can again misread legacy attribute offsets and fail
with `EGL_BAD_ALLOC`. Eager RenderEngine import occurs before final HWC composition choice, so a possible
HWC overlay is not accepted as protection from this boundary.

Predicted first boundaries, in order to discriminate rather than assume:

| Candidate first boundary | Why plausible | Required evidence |
|---|---|---|
| BITSTREAM / PROFILE REJECTION | XML throughput limit contradicts 4K30 even though size/level permit it | input format/profile/level and configure result |
| OMX / CODEC CONFIG | legacy component may reject blocks/rate or choose a different output format | selected component, port definitions/settings changes |
| CEDAR / VPU DECODE | closed decoder claims broad paths but exact 3840x2160@30 hardware behavior is unproven | Cedar/VE init, FBM, FBD and advancing timestamps |
| OUTPUT PIXEL FORMAT / BUFFER ALLOCATION | 4K stride/plane/count and memory pressure differ; format may cease to be YV12 | native-window/gralloc format, usage, dimensions, allocation result |
| SKIA / EGL | compat1a is inactive; known extended/legacy metadata collision may recur | AHB/native buffer, EGL result/error, BackendTexture validity |
| HWC / SURFACEFLINGER | 4K scanout/composition capacity and stability unproven | HWC/SF state, composition and PID continuity |
| HDMI / DISPLAY | physical mode may be 4K while Android logical UI remains 1080; correct full-frame scaling is separate | visible geometry and display dumps |
| THERMAL | short load can expose temperature/frequency collapse despite kernel protection | observer samples and thermal log |

For Main10, public profile rejection is the leading first boundary. If configuration succeeds anyway,
output-format/allocation and old Mali/EGL/HWC support become the next high-risk boundaries. No current
evidence supports expanding compat1a or declaring P010 display support.

## Reproducible P3-A fixture contract

Do not reuse an unknown HDR/Main10 clip. A future fixture should be short, exact 3840x2160, 30 fps,
HEVC Main 8-bit `yuv420p`, non-HDR SDR BT.709, non-protected, with optional AAC stereo. Record the exact
ffmpeg version and the final SHA-256 because encoder output can differ across builds. One example recipe
for a 30-second synthetic fixture is:

```text
ffmpeg -f lavfi -i "testsrc2=size=3840x2160:rate=30" \
  -f lavfi -i "sine=frequency=1000:sample_rate=48000" -t 30 \
  -c:v libx265 -pix_fmt yuv420p -profile:v main -level:v 5.1 \
  -x265-params "repeat-headers=1:colorprim=bt709:transfer=bt709:colormatrix=bt709" \
  -tag:v hvc1 -c:a aac -b:a 192k -ac 2 -ar 48000 \
  ubox10-hevc-main8-sdr-3840x2160p30-aac.mp4
```

Before transfer, `ffprobe` must report width 3840, height 2160, `30/1`, profile Main, `yuv420p`, BT.709
primaries/transfer/matrix, no HDR mastering/content-light/HDR10+ side data, and AAC stereo if audio is
present. Record size and `sha256sum`. This task generated neither fixture nor physical evidence.

## Future P3-A physical protocol

P3-A is one short diagnostic on the already-installed exact `a16-dev-audio-r1`; no cold boot or Gate 3
rerun is required unless separately justified.

1. Leave the box at a stable launcher. Capture boot ID, critical PID/PPID/name, crash/tombstone baseline,
   and run `Discovery`.
2. **Precondition:** identify `cpu_thermal_zone` with a plausible millidegree value, its 70/90/115°C
   trips, and at least one CPUfreq policy. If CPU temperature or CPUfreq is unreadable/implausible, STOP;
   do not turn P3-A into an unobserved sustained load.
3. Confirm no critical service is already restarting. Copy/verify the accepted fixture using the existing
   manual media workflow; do not autoplay it.
4. Start the host `Sample` mode for 60 seconds. Manually start the fixture once; no loop, seek, stress,
   Wi-Fi/HDMI toggle, or automatic player control.
5. Observe at most the single 30-second fixture. Manually stop/back. Let sampling finish, then collect the
   targeted codec/RenderEngine/HWC log window, final thermal/frequency snapshot, critical PIDs, crash
   buffer and tombstone census.
6. Report picture, motion, full-frame geometry, color, and HDMI audio. Preserve evidence and stop. A
   failure is not permission to alter compat1a.

### Human abort rules

The first active CPU trip is source-backed at 70,000 m°C; the initial smoke uses it as a conservative
operational stop boundary, not a claim that lower values are universally safe. Abort manually at or
above 70,000 m°C, or if a rising CPU trend reaches within 5,000 m°C of that trip before the fixture's
midpoint. GPU/VE/DDR have no source-backed local trip in this DT, so no invented numeric threshold is
assigned to them. Also abort on a kernel thermal warning, cooling/frequency state indicating a sharp
unexplained collapse, abnormal enclosure behavior, UI/display corruption, freeze, decoder stall, audio
collapse, SurfaceFlinger/HWC crash/restart, or any critical PID change. Do not automatically power off
or reboot; stop playback and preserve evidence.

### Layered acceptance contract

P3-A passes only if all layers are established:

1. bitstream accepted as Main 8-bit SDR 3840x2160@30;
2. `OMX.allwinner.video.decoder.hevc` and Cedar/VE hardware path instantiated, with no software fallback;
3. decoded frames and advancing timestamps/FBD observed;
4. output format/dimensions/usage and buffers delivered;
5. allocation, mapper/gralloc and EGL import succeed;
6. SurfaceFlinger/HWC stay alive and stable;
7. picture is present, correctly full-frame, not quarter-screen/cropped, and not green/purple;
8. motion advances normally without sustained stall;
9. AAC/HDMI audio is normal when present;
10. boot ID and critical PID/PPID/name are unchanged, crash buffer empty, no new tombstone, audio HIDL
    and audioserver alive;
11. valid observational thermal/frequency data exists and no abort condition occurs in the bounded window.

Failure must be assigned to the earliest supported class: `BITSTREAM / PROFILE REJECTION`,
`OMX / CODEC CONFIG`, `CEDAR / VPU DECODE`, `OUTPUT PIXEL FORMAT`, `BUFFER ALLOCATION`,
`GRALLOC / MAPPER IMPORT`, `SKIA / EGL`, `HWC / SURFACEFLINGER`, `HDMI / DISPLAY`, `AUDIO`,
`THERMAL`, or `UNKNOWN / NEEDS MORE EVIDENCE`.

## Governance outcome

- P3-0: **RESEARCH / TOOLING PREPARED**.
- P3-A: **HEVC MAIN 8-BIT SDR 4K30 PHYSICAL CAPTURE PENDING**, conditional on the discovery gate and
  short-smoke limits above.
- P3-B: **HEVC MAIN10 SDR 4K30 RESEARCH ONLY / NOT AUTHORIZED**.
- HDR, AFBC, protected/secure playback and 4K qualification/soak remain out of scope.
- The absent Thermal HAL remains P2 active debt; this task did not repair it or prove Android thermal
  framework integration.
- P2 remains **COMPLETE**, the audio P1 remains **CLOSED**, and no frozen architecture/candidate status changed.
