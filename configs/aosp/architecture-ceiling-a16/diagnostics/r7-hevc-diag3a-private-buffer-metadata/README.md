# r7 diag3a instrumentation-transparency overlay

This overlay is **DIAGNOSTIC ONLY / INSTRUMENTATION TRANSPARENCY CORRECTION / NOT r8 / NOT A
RELEASE**. Apply it after the exact diag1, diag1a, diag2, and diag3 overlays.

It changes only the FNV-1a multiplication in the ARM64 libstagefright copy of
`UBOXR7Diag3PrivateHandle.h`. `__builtin_mul_overflow` returns the same modulo-2^64 product as the
original unsigned multiplication, but makes the intentional wrap explicit and therefore does not
invoke libstagefright's non-recovering unsigned-integer-overflow UBSan handler. No sanitizer is
disabled, and all five diag3 observation boundaries and record formats remain unchanged.

```bash
prepare.sh check /work/src/ubox10-a16-ceiling
prepare.sh apply /work/src/ubox10-a16-ceiling
prepare.sh revert /work/src/ubox10-a16-ceiling
```

The only required build target is `libstagefright` under the frozen
`ubox10_ceiling_arm64-bp2a-userdebug` product. SurfaceFlinger and both gralloc libraries remain
byte-identical to diag3.
