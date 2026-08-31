# r7 HEVC ABI compat1 SDR shadow overlay

Experimental repair only; not r8 and not a release. This overlay applies after the exact
diag3a source state. It changes only Skia's ARM64 OpenGL AHardwareBuffer import path.

For the physically proven 1920x1088 SDR YV12, non-AFBC, non-protected Allwinner handle contract,
it copies the complete active 56-byte attribute region from offset 23544 to offset 0x80 in an
independent 0x6000-byte ashmem/memfd shadow. Only a cloned handle presented to Mali receives the
shadow fd. The decoder-owned sidecar and original handle are never written.

The guard additionally requires the observed plane geometry, usage, metadata flags, actual fd2
`fstat` size, active attribute values, and a conflicting non-negative legacy crop interpretation.
The newly created shadow fd is also required to report the exact size before it is mapped. Any
mismatch or allocation/import failure falls back to the unchanged original EGL path and fatal
semantics.

Apply, inspect, or remove it with:

```sh
prepare.sh apply /work/src/ubox10-a16-ceiling
prepare.sh check /work/src/ubox10-a16-ceiling
prepare.sh revert /work/src/ubox10-a16-ceiling
```

Only `surfaceflinger` is rebuilt under `ubox10_ceiling_arm64-bp2a-userdebug`. Existing
`UBOX_R7_DIAG1` and `UBOX_R7_DIAG3` records remain unchanged; the compatibility path uses
`UBOX_R7_COMPAT1`.
