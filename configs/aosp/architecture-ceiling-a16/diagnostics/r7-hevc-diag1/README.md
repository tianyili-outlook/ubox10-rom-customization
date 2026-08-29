# r7 HEVC diag1 source overlay

This directory is **INSTRUMENTATION ONLY / NOT A REPAIR / NOT r8 / NOT A RELEASE**.
It is deliberately outside the canonical
`configs/aosp/architecture-ceiling-a16/patches/` series, so rebuilding frozen
`a16-prototype-b-r7` does not apply these patches.

The four patches trace RenderEngine/AHardwareBuffer state, Skia EGL/GL import,
MediaCodec/native-window state, and the open-source dual-ABI gralloc private
contract. They add only conditional `UBOX_R7_DIAG1` logging. The existing
RenderEngine fatal and all format, usage, allocation, codec-ranking, and HWC
decisions remain unchanged.

Apply or verify the overlay explicitly:

```bash
configs/aosp/architecture-ceiling-a16/diagnostics/r7-hevc-diag1/prepare.sh check
configs/aosp/architecture-ceiling-a16/diagnostics/r7-hevc-diag1/prepare.sh apply
```

Build the four runtime payloads from exact BP2A.250805.034/API 36 source:

```bash
cd /work/src/ubox10-a16-ceiling
export OUT_DIR=out-ceiling-b1
export BUILD_NUMBER=DISPOSABLE_CEILING_R4
source build/envsetup.sh
lunch ubox10_ceiling_arm64-bp2a-userdebug
m -j16 surfaceflinger libstagefright gralloc.apollo
```

The candidate packages only ARM64 `/system/bin/surfaceflinger`, ARM64
`/system/lib64/libstagefright.so`, and both gralloc architectures. The ARM32
gralloc is required because the retained allocator service is ELF32; the ARM64
copy provides the SurfaceFlinger-side import observation. `libstagefright.so`
already contains the instrumented `SurfaceUtils.cpp`, so the separately built
`libstagefright_surface_utils.so` files are not part of the candidate delta.

`prepare.sh revert` mechanically removes only this overlay from an exactly
patched source tree.
