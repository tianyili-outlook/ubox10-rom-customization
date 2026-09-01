# r7 compat1a SDR shadow fd correction

This overlay applies only after exact compat1. It replaces the legacy `/dev/ashmem` shadow
allocation with the same sized-memfd sequence used internally by Android libcutils:
`memfd_create(MFD_CLOEXEC|MFD_ALLOW_SEALING)`, `ftruncate(0x6000)`, then
`F_SEAL_GROW|F_SEAL_SHRINK`.

The correction changes no eligibility, metadata contents, 56-byte translation, handle contract,
AHardwareBuffer ownership, EGL behavior, or failure behavior. It is an experimental SDR YV12
compatibility candidate, not r8 and not a release.

Physical status (2026-08-31): **PASS for the authorized SDR 1080p YV12 scope only**. Both the
primary HEVC run and the interaction run repeatedly reached sized memfd creation, exact 56-byte
translation, CLONE view creation, successful EGL import and valid backend texture without changing
the original sidecar. Formal AVC control and regression stayed on the original view and passed.
Main10, HDR, AFBC, protected content and 4K remain unvalidated. A later, separately recorded Gate 3
session closed overall governance as `PASS_WITH_EXPLICIT_USER_WAIVER` (POWER current-session
revalidation only); it does not broaden this repair's scope. Canonical r7 remains frozen and r8
remains unauthorized.

Apply with:

```sh
./prepare.sh apply /work/src/ubox10-a16-ceiling
```

Use `check` to verify exact pre/post hashes and `revert` to mechanically remove only compat1a.

Physical validation is strictly staged: flash, normal boot, **BootGate first**, review BootGate,
then and only then install/verify VLC, create and populate the test-media directory, verify both
fixtures, first-launch VLC and finish onboarding/permissions/media scan. Formal AVCPre/AVCLive/
AVCPost begins only after that setup. Review AVC before one manual HEVC run; review HEVC before
interaction and AVC regression. The tracked PowerShell helper enforces these state gates. It never
automates playback, reboot, player input, or HEVC repetition.

The formal helper writes an explicit `crash-buffer.txt` even when the crash buffer is empty. Fixture
transfer verification is host/device file-size equality, not SHA-256 or byte-for-byte verification.
