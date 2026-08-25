# A16 Prototype A r3 physical validation evidence

Date: 2026-08-25 (Asia/Singapore)

Candidate: `a16-prototype-a-r3`

Firmware identity: 1,239,738,368 bytes / SHA-256
`FA47939654B4E2A7E14FE963C7819296157338D33355E75D89E8086356071F1B`

Target: physical UBOX10 connected over Ethernet ADB at `192.168.1.9:7896`. This validation did
not flash, reboot, rebuild, repack or modify an image. Stock, Test8r2 and the frozen Android 12
baseline remain rollback references.

## Exact result

The original r3 image reached the graphics boundary with neither `persist.graphics.egl` nor
`ro.hardware.egl` set. The pre-existing field diagnosis recorded SurfaceFlinger failing to select
the vendor driver from `ro.board.platform=apollo`. Before this evidence session, the user had
already applied the runtime override `persist.graphics.egl=mali`; this session did not create that
override. With it present, the device proves Android 16/API 36, ARM32-only `zygote32`, Linux
5.4.302+, boot completion, service managers, system_server, SystemUI, SurfaceFlinger, Mali-G31
GLES 3.2, TV/Leanback launcher and LeanbackIME runtime.

This proves the core Path-A architecture is viable. It does not close the formal candidate:
`ro.hardware.egl=mali` is not integrated into an image, the physical HDMI output is unstable,
the legacy vendor audio HAL crashes on observed HDMI status transitions, Wi-Fi association was
not executable, and enforcing SELinux was not tested. Gate 2 therefore remains open and
Prototype B remains closed.

## Result matrix

| Area | Result | Evidence boundary |
|---|---|---|
| Framework/APEX/zygote32 | **PASS** | `sys.boot_completed=1`; API 36/BP2A; service managers, zygote, system_server and SystemUI running; active runtime/VNDK APEX mounts |
| Path-A kernel config | **PASS** | All six cgroup/netd options are `=y`; old bootstrap/bpfloader fatal filters are empty |
| Graphics composition | **PASS WITH PRE-EXISTING RUNTIME OVERRIDE** | `persist.graphics.egl=mali`; `ro.hardware.egl` absent; Mali-G31 GLES 3.2 and composed layers present |
| HDMI physical stability | **FAIL** | User observed about 1 second of picture followed by about 5 seconds black, repeating; framework/display counters stayed live, while kernel logs also contain HDMI disconnect/connect transitions |
| Ethernet | **PASS** | `eth0` up/carrier, gateway/IP/DNS ping 4/4, stable Ethernet ADB |
| Wi-Fi BSP/framework/scan | **PASS** | AIC modules/wlan0 present; scan returns APs; old 1037/1038 blocker filter empty |
| Wi-Fi OFF→ON reinitialization | **PASS** | Clean fdrv/wlan0 teardown and recreation; new interface instance and post-enable scan |
| Wi-Fi association/DHCP/L3 | **NOT TESTED** | No saved network and no input path for credentials during the session |
| IR Linux events | **PASS** | All requested keys produce DOWN/UP events |
| IR Android mapping | **PARTIAL FAIL** | scanCode 352/KEY_OK becomes Android `KEYCODE_UNKNOWN`; Generic.kl maps 353, not 352, to DPAD_CENTER |
| Volume/mute framework effect | **PASS** | Physical keys changed stream volume and mute state |
| Basic/HDMI audible output | **NOT TESTED** | Attached monitor has no audio output; `tinyplay` execution is transport evidence only, not audible proof |
| Vendor audio HAL stability | **FAIL** | Repeated null-pointer SIGSEGV in HIDL `Device::getAudioPortImpl`; audioserver/HAL restart automatically |
| TV launcher/IME inventory | **PASS** | Leanback/television features, sample Leanback HOME activity and LeanbackIME present/default |

## Evidence index

- `commands.txt`: exact command families used during the session.
- `decisive-excerpts.txt`: short, reviewable excerpts and interpretation boundary.
- `a16-r3-getprop.txt`, `a16-r3-ps.txt`: complete property/process captures.
- `a16-r3-framework-graphics-tv-ime.txt`, `a16-r3-surfaceflinger.txt`: framework, launcher,
  IME and graphics state.
- `a16-r3-apex-validation.txt`, `a16-r3-kernel-cgroup-validation.txt`: runtime APEX and kernel
  contract checks.
- `a16-r3-ethernet-validation.txt`: link and network reachability.
- `a16-r3-wifi-validation.txt`, `a16-r3-wifi-off-on-validation.txt`,
  `a16-r3-dumpsys-wifi.txt`: scan and reinitialization evidence. SSIDs/BSSIDs are redacted.
- `a16-r3-getevent-remote.txt`, `a16-r3-dumpsys-input.txt`,
  `a16-r3-remote-android-mapping.txt`: physical IR events and Android mapping boundary.
- `a16-r3-hdmi-extcon-sampling.txt`, `a16-r3-hdmi-disp-counter-sampling.txt`,
  `a16-r3-hdmi-framework-monitor-summary.txt`: physical HDMI investigation.
- `a16-r3-audio-flinger.txt`, `a16-r3-audio-policy.txt`,
  `a16-r3-audio-query-trigger-isolation.txt`: audio topology, service state and query isolation.
- `a16-r3-crash.txt`, `a16-r3-dmesg.txt`, `a16-r3-logcat-all.txt`: raw crash, kernel and full
  Android log evidence.
- `a16-r3-final-state.txt`: cleanup/final device state.

Network identifiers and netd stable secret values are redacted. No Wi-Fi credential is stored in
this directory.
