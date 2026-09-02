# a16-dev-audio-r1 bounded physical validation plan

Status: **EXECUTED / PHYSICAL VALIDATION PASS / P1 ARM32 AUDIO STARTUP CRASH CLOSED**

Use the exact image `out/candidates/a16-dev-audio-r1/x12-a16-dev-audio-r1.img`, size
1,641,830,400 bytes, SHA-256
`270B5D822AB3BB13D8EDCD9BE374DA1D6ED512D6D60063E123046C23B8AF9D62`.

The test is one bounded normal-boot session:

1. Flash only after separate authorization, boot normally, then run the existing Gate3 BootGate
   capture before installing, copying or launching media software.
2. Confirm Android 16/API36, `zygote64_32`, both zygotes, system_server, SurfaceFlinger, ARM32 audio
   service, gralloc and HWC services are alive. Capture boot ID, uptime, crash buffer, tombstones,
   service PIDs and full boot log.
3. Search the full boot window for the historical `android.hardware.audio.service` address-zero
   `SIGSEGV`, `Device::getAudioPortImpl<audio_port_v7>` crash and service restart. Success requires
   no such new tombstone or crash and continuous audio-service PID.
4. Exercise one HDMI availability transition only if it is safely reproducible by the already
   accepted TV/input procedure. Capture audio policy/HIDL/audio HAL logs and service PIDs before and
   after. Do not add delay/retry loops or repeatedly cycle HDMI.
5. Reuse the accepted Gate3 manual playback setup and fixtures: initial AVC + AAC/HDMI audio smoke,
   compat1a SDR HEVC + AAC/HDMI audio smoke, then VP9 + Vorbis/HDMI audio smoke. Playback remains
   manual; do not invent a new media workflow or expand to Main10/HDR/AFBC/protected/4K.
6. Capture a final crash buffer, tombstone listing, boot ID and audio/SurfaceFlinger/zygote/
   system_server PID census.

Physical PASS requires normal boot, no getAudioPort PC-zero crash, continuously alive audio
services, successful bounded HDMI availability handling, audible HDMI audio for all three accepted
media smokes, unchanged compat1a SDR HEVC behavior, and no new SurfaceFlinger/framework crash.

Stop immediately on a new crash, service restart loop, lost HDMI audio, architecture regression or
compat1a media regression. Do not repeat boots to manufacture a pass; no 10x reboot gate applies.

## Result

The authorized session completed on 2026-09-02 in one continuous boot with boot ID
`90882ee3-4884-445c-ae9c-cada3a1a6449`. BootGate passed on Android 16/API36 with `zygote64_32` and
both ABI families. The historical address-zero audio HIDL crash signature was absent and the crash
buffer was empty. An explicit HDMI `disconnect=1024` then `connect=1024` caused AudioFlinger to
reopen `AUDIO_DEVICE_OUT_HDMI`; audioserver PID 534 and ARM32 audio HIDL PID 504 remained unchanged.

Manual AVC+AAC, HEVC+AAC and VP9+Vorbis smokes all had normal picture and HDMI audio. Raw logs
confirm the Allwinner/Cedar hardware paths; HEVC retained the compat1a shadow import path without
EGL/SurfaceFlinger regression. SurfaceFlinger 547 and system_server 787 remained unchanged. The
final census retained the boot ID and all critical PIDs, had an empty crash buffer, no tombstone
delta, AudioFlinger hardware status 0 and output device `0x400` HDMI.

The evidence archive SHA-256 is
`BDB3D13ECF54DF3CD1C7B3F6DC5D160DDF9D43CD51E6F1D66B8DC28910F09064`; all 48 internal manifest
entries passed. Cedar unmap EINVAL, VP9/VLC released-state `BAD_VALUE`, and abandoned
BufferQueue/EGL-window messages occur during teardown and are retained as non-blocking deferred
observations. No runtime, candidate image or helper changed during this governance closure.
