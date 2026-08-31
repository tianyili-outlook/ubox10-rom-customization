# r7 compat1a SDR shadow fd correction

This overlay applies only after exact compat1. It replaces the legacy `/dev/ashmem` shadow
allocation with the same sized-memfd sequence used internally by Android libcutils:
`memfd_create(MFD_CLOEXEC|MFD_ALLOW_SEALING)`, `ftruncate(0x6000)`, then
`F_SEAL_GROW|F_SEAL_SHRINK`.

The correction changes no eligibility, metadata contents, 56-byte translation, handle contract,
AHardwareBuffer ownership, EGL behavior, or failure behavior. It is an experimental SDR YV12
compatibility candidate, not r8 and not a release.

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
