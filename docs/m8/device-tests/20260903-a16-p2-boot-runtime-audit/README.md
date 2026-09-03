# Android 16 P2 one-shot boot/runtime system audit result

Status: **PHYSICAL CAPTURE ANALYZED / NO NEW P1 BLOCKER / ACTIVE DEBT RECORDED**

This is a read-only evidence result for the already installed `a16-dev-audio-r1`. It does not
change the candidate, reopen the closed ARM32 audio startup P1, authorize r8, or begin P3.

## Evidence integrity and scope

- External archive: `/work/physical-evidence/ubox10/a16-p2-audit/UBOX10-A16-P2-AUDIT-20260903-205909.zip`
- Archive SHA-256: `c3aca6ace9e84477d2fa2c47a419bc19b6887a2b2dd9616e54ce2446e6389428`
- The adjacent user-provided `.sha256` matches the archive.
- `META/SHA256SUMS.txt`: **105/105 OK, 0 failures** after extraction outside Git.
- Passive UART: `00-Host/UART-passive.log`, 16,301 bytes,
  SHA-256 `09a7494f9f4f084e7e3121db847af3d1aed7e2e7815a1c3bc5accb06b9e49928`;
  `UART-METADATA.txt` records `commands_entered=false`.
- T0, T1 and B0 are present. The summary text
  `no_automated_pass_fail=truefinalized_uart_included=true` is only the known missing-newline
  host formatting defect; actual UART presence and integrity are independently proven above.
- No media playback, Wi-Fi/HDMI transition, suspend, input matrix or Gate 3 rerun was performed.
  Previously accepted functional evidence is not reclassified by this idle audit.

## Continuity and top-level verdict

T0 and T1 share boot ID `1f47a2b3-2618-44ec-866a-566c14ded851`. The raw critical-state rows are
identical: `zygote64` 489/1, `zygote` 490/1, ARM32 audio HIDL 501/1, `audioserver` 527/1,
`surfaceflinger` 535/1 and `system_server` 778/489. The finalized comparison is empty for exactly
that boot ID plus PID/PPID/name set. Both crash buffers are zero bytes; tombstone and ANR listings
remain empty and unchanged. There is no `Fatal signal`, `SIGSEGV`, `SIGABRT`, `SEGV_MAPERR`, fatal
exception, ANR, critical watchdog action, kernel panic/oops, critical OOM kill, or framework/HAL
restart in the evidence. The historical `getAudioPortImpl`/PC-zero signature is absent.

Verdict: **P2 ONE-SHOT AUDIT COMPLETE / NO NEW P1 BLOCKER / NO CRITICAL RESTART / NO PERSISTENT
FATAL LOOP**. The ARM32 audio startup P1 remains **CLOSED**. A bounded P3 experiment is reasonable,
but the missing Thermal HAL is the first active debt to address or explicitly monitor before
long-duration/high-load 4K or Main10 qualification. This does not itself start or pass P3.

## Canonical issue matrix

Counts below are clustered signatures, not raw-line severity. Logcat often renders the same SELinux
event through both `auditd` and the originating process; collector-created shell denials are called
out separately rather than attributed to normal device activity.

| ID | Subsystem | Classification | Signature / finding | Evidence file(s) | First timestamp | Last timestamp | Count/frequency | Boot-only vs persistent | PID/service | Known vs new | User-visible/functional impact | Likely layer/root cause | Confidence | Recommended priority | Recommended next action |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P2-001 | Thermal | P2 / ACTIVE DEBT | Thermal HAL 2.0/1.1/1.0 unavailable; `HAL Ready: false`, no cached temperatures | `B0-Final/logcat-all.stdout.txt`; `80-Power-Thermal/thermal.stdout.txt` | 08-27 08:52:52.532 | T0 snapshot | 4 boot messages; state persists | Persistent capability absence, not retry loop | `system_server` 778 / ThermalManagerService | Known lead, now reconfirmed | No idle failure; weak protection/observability under sustained load | Retained BSP has no registered Thermal HAL | High | First P2 engineering priority | Audit thermal zones/vendor power implementation; require bounded temperature/load observation before prolonged 4K/Main10 qualification |
| P2-002 | Security / KeyMint | P2 / ACTIVE DEBT | KeyMint `getHardwareInfo` takes 1.58 s; `earlyBootEnded` returns `UNKNOWN_ERROR` / vold `-1000` | `B0-Final/logcat-all.stdout.txt`; `00-Host/UART-passive.log` | 01-01 00:00:10.551 | 01-01 00:00:12.162 | One watchdog completion; one failed lifecycle call rendered by keystore/vold | Boot-only | `keystore2` 292, vold 279, KeyMint HAL | New P2 audit finding | Boot/storage still complete; possible key lifecycle/security maturity risk | Legacy KeyMint implementation accepts basic connection but rejects newer lifecycle call | High | P2, after thermal | Static ABI/version audit plus one targeted read-only keystore lifecycle capture; do not redesign TEE from this log alone |
| P2-003 | Resource control | P2 / ACTIVE DEBT | cgroup2 rejects `memory_recursiveprot`; `+memory` activation fails for system/app UID cgroups | `00-Host/UART-passive.log`; `B0-Final/logcat-all.stdout.txt`; `20-System/dmesg.stdout.txt` | kernel +5.945 s | 09-03 12:56:09.427 | 1 mount-option error + 23 launch-time activation failures | Boot/process-start only; absent after T0 | init, zygote64 and launched apps | Known architecture/BSP compatibility debt | No observed kill or instability; memory-accounting/policy semantics are degraded | A16 cgroup setup exceeds retained 5.4/BSP controller behavior | High | P2 | Map requested controller operations to enabled kernel/cgroup features before any bounded config change |
| P2-004 | RTC / time | P2 / ACTIVE DEBT | RTC reset-control acquisition fails and kernel initializes wall clock to 1970 before later time corrections | `00-Host/UART-passive.log`; `B0-Final/logcat-all.stdout.txt` | kernel +0.410 s | 09-03 12:56:08 | One probe failure; wall-clock epochs advance 1970→stored date→network date | Boot-only, condition may recur each cold boot | `sunxi-rtc`, time detector/network | New explicit classification | Networked device recovers; offline time/certificate behavior may be wrong | Retained RTC DT/driver reset contract | Medium-high | P2 daily-use maturity | Verify RTC persistence in a future authorized cold-boot observation; then audit DT/driver contract if reproducible |
| P2-005 | SELinux | KNOWN INHERITED DEBT | Device is permissive; active paths include CEC→`sysfs_extcon`, audio uevent/property, HWC property and system_server capability denials | `40-SELinux/selinux-state.stdout.txt`; `40-SELinux/selinux-logcat-avc.stdout.txt`; `B0-Final/logcat-all.stdout.txt` | 01-01 00:00:15.396 | 09-03 12:59:10.721 | CEC 37, audio 30, HWC 13, system_server 7 raw logcat records; duplicates present | Boot and active runtime; no enforcing test | corresponding HAL domains/system_server | Known | Permissive masks release behavior; no failure in this audit | Policy gaps in retained vendor/A16 integration | High | Release hardening, not P3 blocker | Build a deduplicated allow/deny inventory before any enforcing experiment; do not call enforcing compatible |
| P2-006 | VINTF / kernel FCM | KNOWN INHERITED DEBT | Offline full VINTF remains exit 65: `CONFIG_NFS_FS=y` versus FCM-6 `n` | Existing candidate/offline reports; runtime `30-HAL-VINTF/*` only confirms service visibility | N/A | N/A | One inherited exception | Persistent contract debt | VINTF/kernel | Known | No runtime outage shown | Frozen retained kernel config versus framework matrix | High | Deferred governance debt | Preserve NOT PASS; resolve only in an explicitly authorized kernel/VINTF task |
| P2-007 | Display architecture | KNOWN INHERITED DEBT | Android/SF logical 1920x1080 while retained HWC/HDMI may output 3840x2160@60 | `50-Display/display.stdout.txt`; `50-Display/wm-state.stdout.txt`; `50-Display/surfaceflinger.stdout.txt` | T0 snapshot | T1 snapshot | Stable state | Persistent by architecture | SurfaceFlinger 535 / HWC 512 | Known/frozen ceiling | Normal UI in this run; related recovery scaling debt remains separate | Retained display pipeline and logical framebuffer ceiling | High | Deferred | Preserve architecture conclusion; revisit only for separately authorized display/recovery work |
| P2-008 | HDMI / display boot | P3 / NON-BLOCKING NOISE | `DVI mode selected` + `set vsif failed` negotiation burst, then stable connected HDMI/audio | `20-System/dmesg.stdout.txt`; `B0-Final/logcat-all.stdout.txt` | kernel +31.363 s | kernel +47.789 s | 45 paired messages | Boot-only | HDMI driver/HWC | Known vendor noise | Display reaches stable ON state; no SF/HWC restart | Legacy HDMI mode/VSIF probing | High | Defer | Revisit only if a visible hotplug/mode symptom recurs |
| P2-009 | Media codec discovery | P3 / NON-BLOCKING NOISE | Allwinner OMX rejects optional describeColorFormat/port queries; invalid zero pthread joins during codec enumeration | `B0-Final/logcat-all.stdout.txt`; `60-Audio-Media/media-codec.stdout.txt` | 08-27 08:52:59.005 | 08-27 08:52:59.911 | 149 query pairs; 18 pthread warnings | Boot-only enumeration | OMX service 594 | Known legacy vendor noise | Codec services remain alive; no playback occurred; prior Gate 3 codecs pass | New framework probing legacy OMX implementation | High | Defer | Track only if a future codec-specific regression correlates with it |
| P2-010 | Wi-Fi diagnostics | P3 / NON-BLOCKING NOISE | Legacy driver omits AKM-suite/debug packet-fate interfaces and tracefs last-mile hooks | `B0-Final/logcat-all.stdout.txt`; `70-Network/wifi.stdout.txt`; `20-System/dmesg.stdout.txt` | 08-27 08:52:53.323 | 09-03 12:59:11.660 | 30 AKM warnings; one packet-fate query set; trace hook warnings | Startup plus collector-triggered dumpsys; not a retry loop | Wi-Fi HAL 1016, wificond/system_server | Known-style BSP gap | Wi-Fi is connected/validated with IPv4/IPv6/routes/DNS; no supplicant crash | Modern diagnostic API versus legacy AIC driver | High | Defer | Keep as telemetry limitation; no network toggle/retest from this evidence |
| P2-011 | Power telemetry | P3 / NON-BLOCKING NOISE | `android.hardware.power.stats` absent from manifest; stats pull/logger reports unavailable | `B0-Final/logcat-all.stdout.txt`; `30-HAL-VINTF/lshal.stdout.txt` | 01-01 00:00:22.187 | 08-27 08:52:57.295 | One startup cluster | Boot-only capability absence | system_server/statsd | New explicit classification | No power-manager failure; energy telemetry unavailable | Optional HAL omitted by retained TV BSP | High | Defer | Consider only for release telemetry/power maturity |
| P2-012 | AppSearch | P3 / NON-BLOCKING NOISE | Dirty/invalid derived Icing index detected and regenerated | `B0-Final/logcat-all.stdout.txt` | 08-27 08:52:59.262 | 08-27 08:52:59.683 | 8 related messages | Boot-only self-recovery | system_server AppSearch | New | No package/storage failure observed | Stale derived index across image/data evolution | High | Defer | Observe natural use; investigate only if recurrence or search failure appears |
| P2-013 | Framework flags | P3 / NON-BLOCKING NOISE | Aconfig attempts to load absent `android.xr` package | `B0-Final/logcat-all.stdout.txt` | 01-01 00:00:23.515 | 01-01 00:00:23.522 | 13 calls with stack noise | Boot-only | system_server package parsing | New | No XR feature is intended; boot continues | Generic A16 package parser probes unavailable optional flag package | High | Defer | Optional packaging cleanup only; no runtime fix required now |
| P2-014 | Audio teardown | P3 / NON-BLOCKING NOISE | Two transient direct AC3 output `exit(): -61` results during HDMI startup; primary PCM HDMI remains healthy | `B0-Final/logcat-all.stdout.txt`; `60-Audio-Media/audio-flinger.stdout.txt` | 09-03 12:56:23.634 | 09-03 12:56:29.096 | 2 | Boot/HDMI setup only | audioserver 527 / AudioFlinger | New but compatible with prior teardown noise | `Hardware status: 0`, output device HDMI; no PID change/crash | Legacy direct-output negotiation/teardown | High | Defer | Correlate only if passthrough user-visible failure is later reported |
| P2-015 | Incremental FS | P3 / NON-BLOCKING NOISE | IncrementalFS module/features absent; framework explicitly falls back to unavailable/none | `00-Host/UART-passive.log`; `B0-Final/logcat-all.stdout.txt` | kernel +7.429 s | 01-01 00:00:10.530 | Two repeated probe pairs | Boot-only | vold/incfs | Known legacy-kernel gap | Package/storage census remains responsive | Optional A16 feature unavailable on retained kernel | High | Defer | No action unless incremental-install functionality enters scope |
| P2-016 | Framework service discovery | P3 / NON-BLOCKING NOISE | Six `aidl/activity` lazy-start misses and one `sensor_privacy` miss, then system_server completes boot | `00-Host/UART-passive.log`; `B0-Final/logcat-all.stdout.txt` | kernel +16.482 s | kernel +22.078 s | 7 | Boot-only | servicemanager/init | New explicit classification | No service outage or restart observed | Framework probes optional/not separately declared AIDL interfaces | Medium-high | Defer | Revisit only with a concrete missing-feature symptom |
| P2-017 | Collector side effects in logs | P3 / NON-BLOCKING NOISE | Read-only `service`/`dumpsys`/`lshal` generate Parcel-null, cutils-trace, shell AVC and Wi-Fi packet-fate diagnostics | `B0-Final/logcat-all.stdout.txt`; `META/COMMAND-STATUS.json` | 09-03 12:59:05.761 | 09-03 13:02:16.515 | Two command rounds; e.g. 19 Parcel lines/round and 117 shell-domain AVC records overall | Collector-correlated, not autonomous persistence | temporary shell command PIDs | New provenance finding | No device-state mutation or critical impact | Introspection of legacy services under permissive policy/debugfs limitations | High | Defer | Exclude from autonomous retry-loop counts; preserve as collector provenance |
| P2-018 | DRM / TEE | EXPECTED / BY DESIGN | Widevine HIDL registers; missing `liboemcrypto.so` falls back to working L3; no L1 certification | `00-Host/UART-passive.log`; `30-HAL-VINTF/lshal.stdout.txt`; `B0-Final/logcat-all.stdout.txt` | bootloader +1.148 s | 09-03 12:56:09.082 | One initialization/provisioning cluster | Boot/lazy-init only | Widevine HAL 1818 / OP-TEE | Known | L3 only; no regression from established capability | Non-certified retained security stack lacks OEMCrypto L1 | High | None now | Preserve explicit L3 boundary; do not claim L1 |
| P2-019 | HAL generation | EXPECTED / BY DESIGN | Modern AIDL probes may miss while declared retained HIDL audio/graphics/boot/DRM/Wi-Fi services register and remain alive | `30-HAL-VINTF/lshal.stdout.txt`; `20-System/service-list.stdout.txt`; `A0-SteadyState-T1/lshal.stdout.txt` | Boot | T1 | Stable service census | Persistent intentional mixed-generation architecture | HIDL services listed above | Known/frozen | Required active services available | Intentional A16 framework plus retained vendor/HIDL generation | High | None | Preserve; missing optional AIDL interface alone is not a defect |
| P2-020 | Fixed-power health | EXPECTED / BY DESIGN | Battery reports `present:false`, level 0 while PowerManager is powered/stay-on/awake | `80-Power-Thermal/battery.stdout.txt`; `80-Power-Thermal/power.stdout.txt` | T0 snapshot | T0 snapshot | One snapshot | Persistent TV design | health HAL 517 / PowerManager | Known platform behavior | None for mains-powered TV | Batteryless set-top-box hardware | High | None | Do not treat absent battery as failure |
| P2-021 | Storage | EXPECTED / BY DESIGN | Immutable image-backed mounts can show 100%; writable `/data` has about 50 GiB free and mounted storage is responsive | `90-Storage-Packages/filesystems.stdout.txt`; `90-Storage-Packages/storage.stdout.txt`; `90-Storage-Packages/packages.stdout.txt` | T0 snapshot | T0 snapshot | One full census | Stable | vold/package manager | Known layout | No filesystem/I/O/data-space failure | Read-only partition image sizing plus healthy F2FS data | High | None | Continue normal capacity monitoring; no cleanup indicated |
| P2-022 | Data-at-rest security | NEEDS MORE EVIDENCE | `ro.crypto.state=unsupported` while F2FS/CE-DE structures exist; one-shot shell evidence cannot establish effective encryption posture | `20-System/properties.stdout.txt`; `90-Storage-Packages/filesystems.stdout.txt`; `90-Storage-Packages/storage.stdout.txt` | T0 snapshot | T0 snapshot | One property/filesystem census | Unknown | vold/fscrypt/property contract | New question | Security/release impact possible; no current storage failure | Mixed legacy product property and A16 userspace | Medium | Later security audit | Perform source/config plus non-mutating on-disk policy audit; do not infer encrypted or unencrypted here |
| P2-023 | Suspend / wake | NEEDS MORE EVIDENCE | Neither debugfs `wakeup_sources` nor `/proc/wakelocks` is exposed; no suspend/resume was performed | `80-Power-Thermal/wakeup-sources.stderr.txt`; `80-Power-Thermal/power.stdout.txt` | T0 snapshot | T0 snapshot | Two absent optional paths | Collection limitation | kernel/PowerManager | Known untested scope | No idle impact shown; suspend reliability remains untested in P2 | Kernel interface exposure, not proof of suspend failure | High | Deferred | Use prior accepted behavior; authorize a separate bounded suspend capture only if needed |
| P2-024 | Evidence collector | EXPECTED / BY DESIGN | Four non-success specs are access/empty/multi-path semantics, not device defects | `META/COMMAND-STATUS.json`; corresponding stdout/stderr | 12:59 collection | 12:59 collection | 1 permission, 1 command-failed, 2 not-available | Collection-only | normal shell | Known collector limitation | None | `/proc/cmdline` denied; empty pstore loop exit 1; absent product VINTF path; absent wakeup files | High | None | Preserve raw exit/stderr; do not relabel as subsystem failures |

## Subsystem disposition

- Architecture/core health: Android 16/API36, `zygote64_32`, mixed ABI, Mali, mapper/gralloc,
  SurfaceFlinger and system_server remain intact. No finding threatens frozen r7.
- Audio/media: both audio processes are continuous; AudioFlinger reports `Hardware status: 0` and
  `AUDIO_DEVICE_OUT_HDMI`. No media was played, and the closed PC-zero audio P1 did not recur.
- Network: Wi-Fi is associated, supplicant `COMPLETED`, the default network is `VALIDATED`, and
  IPv4/IPv6, default routes and DNS are populated. Diagnostic API gaps are non-blocking.
- Storage/packages: no filesystem error, read-only regression, data-space problem, vold failure or
  package-manager failure was found.
- Graphics/display: no SurfaceFlinger, HWC, mapper/gralloc or Mali fatal/restart was found.
- Security: permissive SELinux and full-VINTF exit 65 remain explicit inherited debt; Widevine is
  intentionally bounded to L3. Encryption posture and suspend remain unproven by this collection.

## Decision

1. New P1 blocker: **none**.
2. Critical T0/T1 restart: **none**.
3. Closed ARM32 audio P1 recurrence: **none; remains CLOSED**.
4. Persistent fatal/restart/retry loop: **none found**. SELinux active-path denials and absent HAL
   capabilities are debt, not crash loops; collector-triggered introspection noise is excluded.
5. Work before high-load maturity: prioritize Thermal HAL/thermal observability; then KeyMint,
   cgroup controller compatibility and RTC. None overturns architecture or Gate 3 closure.
6. Safe deferrals: HDMI negotiation, OMX discovery, Wi-Fi diagnostic APIs, PowerStats, AppSearch,
   Aconfig XR, IncFS and direct-output teardown noise until a functional symptom appears.
7. P3 readiness: a bounded HEVC 4K30/Main10 study is reasonable after this governance closure,
   with explicit thermal duration/observation guardrails. This document neither starts P3 nor
   expands compat1a's proven SDR 1080p YV12 scope.

Canonical r7 remains **PASS / FROZEN / UNCHANGED**. Gate 3 remains
**`PASS_WITH_EXPLICIT_USER_WAIVER` / CLOSED**. `a16-dev-audio-r1` remains a development candidate,
not a release. r8 remains **NOT AUTHORIZED / NOT BUILT**.
