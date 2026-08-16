# M8B system-quality audit — 2026-08-16

Device: `m8b-audio-r2` at `192.168.1.8:7896`

Method: bounded read-only network-ADB inspection; no log clear, reboot, service/process restart, settings/property change, or device mutation.

## Verdict

No P0 issue was found. Core Android/media/graphics processes retained their PIDs across the comparison, the retained log buffer contained no crash/ANR/watchdog/fatal-signal or binder/service-manager failure, and the explicit 62-second interval contained no process/service death or restart.

## Prioritized findings

| Priority | Finding | Evidence and boundary | Confidence / next action |
|---|---|---|---|
| P1 | SELinux is permissive and is not enforcement-ready for several active paths. | In the bounded 28,248-line buffer, 188 AVC-rendered lines included duplicate audit/source renderings. Non-audit traffic was dominated by CEC HAL `sysfs_extcon:dir search` (46 rendered lines), `system_suspend` wakeup sysfs read/open/getattr (84), and audio HAL self `netlink_kobject_uevent_socket read` (4). Audit-generated `shell` denials are excluded from the defect conclusion. Boundary: vendor/platform SELinux labels/rules for CEC, suspend wake sources, and audio uevent handling. | High that policy gaps exist; current functional impact is masked by `permissive=1`. Do not alter the accepted live device. Validate CEC and suspend/resume physically before any isolated enforcement candidate; audio output remains accepted. |
| P1 | Projectivy/HWUI frame-completion telemetry is invalid and reports nearly every frame as janky. | `gfxinfo` rose from 38,518 frames / 38,418 janky to 38,671 / 38,571; 99.74% jank and 38,507 samples at the 4,950 ms histogram ceiling. The 62-second log interval had 31 `Davey!` entries with `FrameCompleted=GpuCompleted=9223372036854775807` and computed durations around `9.22e12 ms`. SurfaceFlinger/HWC/allocator/mapper remained registered and the device load stayed low. Boundary: Projectivy HWUI frame metrics versus Mali/HWC fence/presentation timestamps, not a proven GPU crash. | High that metrics are broken; insufficient remote evidence for visible stutter/artifacts. Correlate with a physical screen and focused frame capture before changing graphics or the launcher. |
| P1 | CPU/thermal policy observability needs a later bounded investigation. | Load was `0.08 0.07 0.07`, yet five 2-second `scaling_cur_freq` samples were all 1,512 MHz (hardware range 480–1,512 MHz). The shell cannot read the active governor or policy max. ThermalService reported `HAL Ready: false`; kernel zones were 60.9–66.3 C and both cooling devices remained state 0. CPU idle counters advanced and 5-minute CPU usage was only 1.5% total, so no runaway or throttling was observed. Boundary: vendor power/cpufreq policy and Android thermal HAL reporting. | Medium; fixed-at-max behavior is observed but its policy cause is not proven. Keep live settings unchanged; investigate in an offline/isolated candidate and require a physical thermal soak before acceptance. |
| P2 | Wi-Fi link-layer statistics fail persistently. | 21 `WifiVendorHal getWifiLinkLayerStats_1_5_Internal ... ERROR_UNKNOWN` messages in 62 seconds, approximately every 3 seconds. Wi-Fi network ADB remained connected throughout and no Wi-Fi process PID changed. | High; diagnostic/statistics path only on current evidence. Do not fix just to clean logs. |
| P2 | Projectivy billing teardown warning repeats. | `BillingClient` logs `Service not registered` during unbind roughly once per minute; it did not crash or restart Projectivy. | High; app/service-integration noise, unrelated to core TV use. |
| P2 | Legacy missing mixer-control warnings are boot-only/inert for accepted output. | Zero matches in the retained 23,153-line buffer and zero in the 62-second interval. Audio HAL PID 243, audioserver PID 262, primary mixer/output, 9,622,080 written frames, and zero normal-mixer partial/empty underruns were healthy. | High for current playback. Retain as historical boot noise; do not modify the accepted audio stack merely for clean logs. |
| INFO | Historical `nano_input_open -3` is not a current loop; microphone/input function remains unverified. | Zero matches in the retained 23,153-line buffer and zero in the 62-second interval. AudioPolicy declares built-in mic and remote-submix inputs, but no input capture was initiated in this read-only audit. | Current output is unaffected; evidence is insufficient to call input PASS or FAIL. Validate only with an explicit physical/input-use case. |

## Healthy/normal observations

- Stability: no crash, ANR, watchdog, fatal signal, tombstone record, binder/service-manager failure, restart loop, or zombie was found. `exit-info` contained only normal empty-process trimming, freezer binder-transaction cleanup, and a prior user-requested VLC stop; `/data/anr` was empty. Shell access to `/data/tombstones` was denied, so absence of tombstone files is not claimed from directory enumeration.
- Memory: 4,003,444 KiB total, 3,135,084 KiB available, 3,002,576 KiB zram swap with 0 KiB used; `oom_kill=0`, no reclaim scans, and ActivityManager LMK kills = 0. No defensible leak/runaway process was seen.
- Graphics/display: ARM Mali-G31, OpenGL ES 3.2, HWC 2.2, allocator 2.0 and mapper 2.1 were registered; SurfaceFlinger reported a 1920x1080@60 display with device composition, secure display, and protected-buffer support. No graphics service retry/crash loop was found. Known visual artifacts were not physically reproduced or claimed.
- Audio: accepted HDMI primary-output state is unchanged. No AudioFlinger/AudioPolicy/HAL retry/error loop, mixer underrun, missing-control warning, or `nano_input_open -3` occurred in the retained/current windows.

All timestamps in excerpts are device GMT.
