# r7 diag3 private-buffer metadata overlay

This overlay is **DIAGNOSTIC ONLY / OBSERVATION ONLY / NOT r8 / NOT A RELEASE**. Apply it after the
exact diag1, diag1a and diag2 overlays. It adds bounded `UBOX_R7_DIAG3` read-only snapshots at
allocation, remote import, immediately before OMX registration, first decoder fill-buffer-done, and
immediately before EGL import.

The shared private sidecar is mapped `PROT_READ | MAP_SHARED`, hashed and decoded at source-proven
offsets, then unmapped. No handle or sidecar field is written. No format, usage, crop, allocation,
plane, AFBC, codec, EGL/GL, HWC or fatal decision changes.

```bash
prepare.sh check /work/src/ubox10-a16-ceiling
prepare.sh apply /work/src/ubox10-a16-ceiling
prepare.sh revert /work/src/ubox10-a16-ceiling
```

The narrow build targets are `surfaceflinger`, `libstagefright`, and both architectures of
`gralloc.apollo` under the frozen `ubox10_ceiling_arm64-bp2a-userdebug` product.
