# r7 diag2 HEVC visible-crop overlay

This is a mechanically removable, single-variable diagnostic overlay on exact
`a16-prototype-b-r7-diag1a`. It is not r8, not a release, and does not claim an
HEVC repair.

The sole source assignment restores the initial 1920x1080 visible crop only
when `OMX.allwinner.video.decoder.hevc` changes an exact YV12 output port from
1920x1080/full-visible to 1920x1088/full-coded. Coded/allocation dimensions,
format, usage, plane layout, AFBC, native-window allocation, RenderEngine and
the fatal path are untouched. All `UBOX_R7_DIAG1` instrumentation remains.

```sh
prepare.sh check /work/src/ubox10-a16-ceiling
prepare.sh apply /work/src/ubox10-a16-ceiling
prepare.sh revert /work/src/ubox10-a16-ceiling
```
