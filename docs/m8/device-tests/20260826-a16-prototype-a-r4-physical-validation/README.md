# Android 16 Prototype A r4 physical validation

Date: 2026-08-26

Candidate: `a16-prototype-a-r4`

Image: `out/candidates/a16-prototype-a-r4/x12-a16-prototype-a-r4.img`

Image size: 1,239,746,560 bytes

Image SHA-256: `E125DD8FFB9F5B4A7B2B9B86DD8377367409AB00D1B29BE1E719CE25768E2111`

Result: **PHYSICAL VALIDATION COMPLETE / FUNCTIONAL PATH PASS / GATE 2 HOLD ON
VENDOR AUDIO HAL STABILITY**.

## Evidence boundary

The user physically flashed and exercised the exact hash-pinned r4 candidate. The physical
observations and reviewed runtime excerpts were supplied externally and are authoritative for this
record. The likely raw filenames were searched in the repository, ignored logs/build outputs and
persistent work areas, but no r4 raw ADB/log captures were present on this VM. Therefore this
directory contains a reviewed, redacted result record and evidence manifest only: it does not
pretend that the original captures are archived in Git, and it assigns no invented hashes to them.

No device command, flash, reboot, build, image mutation or runtime experiment was performed while
creating this record. The Wi-Fi SSID/BSSID and credentials are intentionally absent.

## Strict result matrix

| Area | Result | Evidence and boundary |
|---|---|---|
| Exact candidate | **PASS** | User reports flashing the exact r4 candidate; repository identity is the size/SHA-256 above and commit `db5712b7aed1ec72c071e67b4d93556a15826184`. |
| Android 16 cold boot | **PASS** | Android 16/API 36, incremental `UBOX10_A16_QPR0_R4`, Linux `5.4.302+`, `zygote32`, core framework services running and `sys.boot_completed=1`. |
| No UART/manual bootargs | **PASS** | Fresh r4 boot reached the normal Android UI without intervention. |
| No runtime EGL intervention | **PASS** | No runtime `setprop` and no r3-style `persist.graphics.egl` workaround were used. |
| `persist.graphics.egl` | **PASS** | Runtime value is empty. |
| `ro.hardware.egl` | **PASS** | Runtime value is `mali`, proving the r4 source-level selector is active. |
| `ro.board.platform` | **PASS** | Runtime value remains `apollo`; the board/gralloc/HWC identity was not replaced. |
| Mali-G31 / SurfaceFlinger / UI | **PASS** | Mali-G31 composition, SurfaceFlinger and the continuously visible Android UI work physically. |
| HDMI picture | **PASS / STABLE IN THIS VALIDATION** | HDMI extcon was connected while SurfaceFlinger and `system_server` remained alive and the normal UI remained visible; r3's roughly 1-second picture / 5-second black cycle was **NOT REPRODUCED**. r4 made no display implementation change, so the old transient's root cause remains **NOT PROVEN** and is not claimed fixed by r4. |
| `sunxi-ir` input selection | **PASS** | Runtime InputManager identifies `/dev/input/event0` as `sunxi-ir` and selects `/system/usr/keylayout/sunxi-ir.kl`. |
| Remote OK mapping | **PASS / PHYSICALLY PROVEN** | Installed layout contains `key 352 DPAD_CENTER`; runtime dispatch is `scanCode=352`, `keyCode=DPAD_CENTER(23)` and Linux `KEY_OK` DOWN/UP remains correct. |
| Physical remote navigation | **PASS** | UP, DOWN, LEFT, RIGHT, OK, BACK and HOME pass; user reports remaining normal remote operation works. |
| Wi-Fi BSP/module and `wlan0` | **PASS** | AIC modules are loaded and `wlan0` operates. No r4 Wi-Fi implementation was changed. |
| Wi-Fi scan / association | **PASS** | Scan and association pass; WPA state reaches `COMPLETED`. |
| DHCP / IPv4 / DNS | **PASS** | DHCP, IPv4 and DNS all pass. |
| Android L3 | **PASS** | Android reports `INTERNET`, `VALIDATED` and `TRUSTED`; real-world Wi-Fi use is stable. |
| Wi-Fi OFF→ON reconnect | **NOT COMPLETED IN THIS SESSION** | The script disconnected its own Wi-Fi ADB transport. This is not a Wi-Fi failure. The separate same-lineage kernel-r5 record already proves one physical OFF→ON reinitialization. |
| Ethernet current session | **NOT RETESTED / NO ACTIVE CARRIER** | The session used Wi-Fi and the later sample had no carrier. r4 byte-preserved Ethernet authority; prior physical Ethernet PASS remains the preservation reference, not a new-session result. |
| Direct ALSA HDMI audio | **PASS / PHYSICALLY AUDIBLE** | ALSA enumerates card 3 `ahubhdmi`; `tinyplay` completed a real 48 kHz, 16-bit, stereo WAV and the user heard the tone through the attached HDMI TV speakers. |
| Android application video | **PASS** | ARM32 VLC played a valid H.264/AAC-style MP4; picture was normal and no playback instability was observed. |
| Android application audio | **PASS / PHYSICALLY AUDIBLE** | The same VLC playback produced audible HDMI TV audio through App→AudioTrack→AudioFlinger→vendor HIDL HAL→ALSA→HDMI. |
| AudioFlinger activity | **PASS** | VLC process/session, actual writes and frames written were present. |
| Playback service stability | **PASS FOR CLEAN PLAYBACK INTERVAL** | `audioserver` PID 1230 and `android.hardware.audio.service` PID 1232 matched before/after playback. After logcat was cleared, the crash buffer remained empty and no new fatal signal/SIGSEGV occurred during valid playback. |
| Known boot-time audio defect | **KNOWN OPEN / REPRODUCED / AUTO-RECOVERED** | Before the clean playback interval, `/vendor/bin/hw/android.hardware.audio.service` reproduced a null-address SIGSEGV in `android.hardware.audio@7.0-impl.so` `Device::getAudioPortImpl<audio_port_v7>` → `Device::getAudioPort` → `PrimaryDevice::getAudioPort`. The service recovered and later playback worked. Exact source-level cause is **NOT PROVEN**; a null callback/function pointer remains **HIGH CONFIDENCE / LIKELY**. |
| Boot-crash playback impact | **NOT OBSERVED** | The recovered steady-state path played real media successfully; this does not erase or classify the boot-time crash as fixed. |

## Gate 2 adjudication

The no-runtime-intervention EGL gate, Remote OK, stable physical HDMI, Wi-Fi
association/DHCP/validated L3 and real audible application-media gates pass. Current-session
Ethernet is not a regression failure because r4 preserved its bytes and the accepted prior physical
PASS remains the control. Enforcing SELinux is a later release-hardening requirement; the inherited
full-VINTF `CONFIG_NFS_FS=y` versus FCM-6 `n` exit-65 result remains an explicit non-boot-causal
exception and is not relabeled PASS.

The pre-existing Gate 2 acceptance contract also explicitly requires **vendor audio HAL
stability**. Because the boot-time `getAudioPort` SIGSEGV reproduced, that exact criterion is not
met even though auto-recovery and steady-state real media playback pass. The formal result is:

**GATE 2 HOLD — SINGLE MINIMUM REMAINING GATE: BOOT-TIME VENDOR AUDIO HAL STABILITY.**

This is not a Path-A architecture contradiction and therefore is not NO-GO. It also does not
authorize a broad r5 cleanup or any Prototype B build.

## Provenance

- Candidate build/offline evidence:
  `docs/m8/candidates/a16-prototype-a-r4.md` and
  `docs/m8/candidates/a16-prototype-a-r4-preservation.json`.
- Historical r3 physical boundary:
  `docs/m8/device-tests/20260825-a16-prototype-a-r3-physical-validation/`.
- External physical evidence classification and local-presence result:
  `evidence-manifest.txt` in this directory.
