# a16-dev-audio-r1 source overlay

This mechanically removable overlay adds one compatibility guard to Android 16 HIDL audio 7.0
`Device::getAudioPort`. The retained ARM32 Apollo HAL reports API `0x0700` but leaves the mandatory
`get_audio_port_v7` callback null. Only that malformed `>= 3.2` case completes the HIDL callback
with `Result::NOT_SUPPORTED`; the valid v7 path and pre-3.2 legacy path are unchanged.

Classification: **DEVELOPMENT AUDIO COMPATIBILITY CANDIDATE / NOT r8 / NOT RELEASE / PHYSICAL
VALIDATION REQUIRED**. This does not alter the proprietary HAL, its reported version, port
capabilities, HDMI routes, AudioPolicyManager, ARM64 audioserver, compat1a SurfaceFlinger, kernel,
or any other vendor HAL.

Pinned source:

- manifest: `android-security-16.0.0_r7`, manifest commit
  `ebea28d151539ecf0730b1a4ab92ac33edc17ac9`;
- `hardware/interfaces`: `b553275c84253b074a8532a6ff0f4406c43e606e`;
- `Device.cpp` before: `b5cc6e454fad055414d2a1ef8dc87dc125cc1bd282a6eafdbdee37d36cf23349`;
- `Device.cpp` after: `3ec13324bf1c99b7bc2a6cb2fc0a6d4a4ad4310bfab2136c4ee078eb005b9d72`.

The physically proven vendor payload was built from the retained Android 12 HIDL-wrapper source
generation. `prepare.sh` therefore projects only the listed wrapper implementation files from
`4a8246e3757732cb787327c3f8ad5cbacf910d1e` and the matching FMQ ABI header from
`8dd3bc99a159970f44298bb8e3d83366aac63273`, then applies the small tracked patch. This is build
provenance, not additional runtime behavior: the only behavioral delta in the patch is the null-v7
callback guard. Two `.string()` to `.c_str()` spelling updates and the already-established VNDK31
libc++ diagnostic back-deploy are compile-compatibility boundaries.

Use `./prepare.sh check|apply|revert /work/src/ubox10-a16-ceiling`. Build only
`android.hardware.audio@7.0-impl_32`; the unqualified target also builds an unused ARM64 variant and
is deliberately not used.
