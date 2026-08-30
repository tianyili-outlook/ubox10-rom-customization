# r7 HEVC diag1a ARM32 gralloc compatibility overlay

This directory is **INSTRUMENTATION ONLY / BOOT-COMPATIBILITY CORRECTION /
NOT AN HEVC REPAIR / NOT r8 / NOT A RELEASE**.

Apply it only after the separate `r7-hevc-diag1` instrumentation overlay. It
reuses r7's libc++-documented `_LIBCPP_VERBOSE_ABORT` preinclude for the ARM32
diagnostic gralloc build, preserving `__builtin_abort()` fatal semantics while
avoiding a runtime import absent from the retained VNDK31 `libc++.so`.

Canonical r7 remains unchanged: this overlay is outside the canonical patch
series. Diag1 instrumentation source and all format, usage, allocation, plane,
AFBC, native-window, codec, RenderEngine, EGL/GL, HWC, and fatal decisions are
unchanged.

Use the mechanically checked wrapper:

```bash
configs/aosp/architecture-ceiling-a16/diagnostics/r7-hevc-diag1a/prepare.sh check
configs/aosp/architecture-ceiling-a16/diagnostics/r7-hevc-diag1a/prepare.sh apply
configs/aosp/architecture-ceiling-a16/diagnostics/r7-hevc-diag1a/prepare.sh revert
```

The narrow ARM32-only build target is:

```bash
cd /work/src/ubox10-a16-ceiling
export OUT_DIR=out-ceiling-b1
export BUILD_NUMBER=DISPOSABLE_CEILING_R4
source build/envsetup.sh
lunch ubox10_ceiling_arm64-bp2a-userdebug
m -j16 device_gralloc.apollo_32_all_targets
```
