# Android 16 Prototype B r7 physical architecture validation

Date: 2026-08-29

Candidate: `a16-prototype-b-r7`

Image: `out/candidates/a16-prototype-b-r7/x12-a16-prototype-b-r7.img`

Image size: 1,641,773,056 bytes

Image SHA-256: `A1F58668AEFFC9DC83CFFD8A49A309839332B6616C02153DCC00A71136A7AA27`

Result: **PHYSICAL ARCHITECTURE PASS / ACCEPTED ANDROID 16 ARM64 MIXED-ARCHITECTURE
ARCHITECTURE BASELINE / PENDING GATE 3 FUNCTIONAL PRESERVATION**.

## Evidence boundary

The user physically exercised the exact hash-pinned r7 candidate. The physical ADB/runtime
observations and decisive excerpts were supplied externally and are authoritative for this record.
The full raw device capture remains outside this repository and was not present on this VM. Tracked
evidence therefore contains reviewed, sanitized decisive excerpts only; it does not fabricate a raw
path or SHA-256. Device LAN address, SSID, BSSID, MAC address and credentials are not retained.

No flash, reboot, runtime mutation, image build or physical-device command was performed while
creating this record.

## Strict result matrix

| Area | Result | Evidence and boundary |
|---|---|---|
| Candidate identity | **PASS** | Exact r7 image size and SHA-256 are locked above; runtime is Android 16/API 36, `BP2A.250805.034`. |
| Global mixed ABI | **PHYSICAL PASS** | `ro.zygote=zygote64_32`; global ABI list is `arm64-v8a,armeabi-v7a,armeabi`, with canonical 64-bit and 32-bit subsets. The old empty `ro.product.cpu.abilist64` blocker stays closed. |
| Boot completion | **PHYSICAL PASS** | `sys.boot_completed=1` and `dev.bootcomplete=1`. |
| Dual zygote | **PHYSICAL PASS** | Primary `zygote64` PID 494 and secondary `zygote` PID 496 are alive. |
| `system_server` | **PHYSICAL PASS** | PID 786 is alive with PPID 494, proving spawn from the primary ARM64 zygote path. |
| SurfaceFlinger | **PHYSICAL PASS** | PID 541 and `init.svc.surfaceflinger=running`; the r6 crash-health action no longer prevents architecture boot. |
| Mapper/gralloc closure | **PHYSICAL PASS / BLOCKER CLOSED** | Crash-buffer filtering found no recurrence of `gralloc-mapper is missing`; real gralloc allocation records include 1920x1080 buffers. |
| Mali/GLES/UI | **PHYSICAL PASS** | `ro.hardware.egl=mali`, `ro.board.platform=apollo`; SurfaceFlinger reports ARM Mali-G31 and OpenGL ES 3.2, with working UI composition. This does not prove Vulkan, HDR, 4K60, every HWC/media buffer path or protected playback. |
| Wi-Fi basic path | **PHYSICAL PASS** | Driver status is OK, `wlan0` is up, association and IPv4/DHCP are present, IP and DNS pings each return 4/4 with 0% loss. |
| Network ADB | **PHYSICAL PASS** | The sanitized endpoint remained in ADB `device` state. |
| Wi-Fi OFF→ON lifecycle | **NOT TESTED — GATE 3** | This validation did not execute the final mixed-architecture lifecycle cycle. Basic Wi-Fi PASS is not promoted to lifecycle PASS. |
| Basic remote/input | **PHYSICAL PASS — BOUNDED** | Physical events reached Android as DPAD_DOWN/108, DPAD_CENTER/352 and BACK/158; the queue remained responsive. |
| Full TV remote matrix | **NOT TESTED — GATE 3** | UP/DOWN/LEFT/RIGHT/OK/BACK/HOME/MENU/VOL±/POWER still require one ordered preservation run. |
| Audio startup | **KNOWN / UNFIXED / POST-ARCHITECTURE P1** | r7 records a null-address SIGSEGV in the legacy vendor audio service and audioserver restart activity. AudioFlinger later remains alive. The supplied r7 excerpt does not independently prove the exact sub-cause; the defect is not called fixed. |
| Full VINTF | **INHERITED EXCEPTION / EXIT 65 / NOT PASS** | `CONFIG_NFS_FS=y` still conflicts with FCM-6 `n`. No kernel change is authorized here. |

## Architecture decision

R7 physically closes all three sequential Prototype B architecture blockers: the global mixed-ABI
property contract, the vendor BoringSSL64 execution gap, and the ARM64 mapper/gralloc instantiation
failure. Android 16/API36 now boots with dual zygotes, ARM64-parented `system_server`, stable ARM64
SurfaceFlinger, real gralloc allocation and Mali-G31 GLES/UI composition.

The architecture-ceiling conclusion is therefore:

**ANDROID 16 ARM64 MIXED ARCHITECTURE ON THE RETAINED 5.4.302 BSP IS PROVEN VIABLE.**

Exact r7 is frozen against further architecture changes. This is not a daily-use release or final
functional freeze: retained ARM32 media/audio/input/network/storage paths must pass the exact-r7
Gate 3 functional-preservation matrix first.

## Freeze hierarchy and next gate

- Android 12 daily-use rollback: `m8b-remote-r1` — **FROZEN**.
- Android 16 ARM32 architecture control: `a16-prototype-a-r4` — **FROZEN**.
- Android 16 ARM64 mixed-architecture control: `a16-prototype-b-r7` — **PHYSICAL ARCHITECTURE PASS /
  FROZEN AGAINST ARCHITECTURE CHANGES / PENDING GATE 3**.

Gate 3 must use this exact r7 image without rebuild or r8. Its formal procedure is in
`docs/DEVICE_TEST.md`. Only after Gate 3 PASS may the project freeze an Android 16 functional
baseline and create the intended `codex/m8-a16-development` branch; that branch does not yet exist.

Machine result: `docs/m8/candidates/a16-prototype-b-r7-physical-result.json`.
