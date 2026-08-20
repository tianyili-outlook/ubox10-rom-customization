# Android 16 architecture prototype products

These files define the two research-only UBOX10 Architecture Ceiling Study
products. Copy the `device` directory into a clean `android-16.0.0_r4` tree,
then select either `ubox10_ceiling_arm-bp4a-userdebug` or
`ubox10_ceiling_arm64-bp4a-userdebug`.

Both products inherit the official Android TV GSI base, retain only VNDK 31,
identify the device as an Android 12 field upgrade, and build no boot, vendor,
super, userdata, or pKVM image. They contain no Allwinner or donor binaries and
are not flashable firmware. Every output is a DISPOSABLE ARCHITECTURE PROTOTYPE.

`run-disposable-build.sh` is an optional low-disk build wrapper for the Study
host. Run it as the WSL root user so one process can mount a pre-created ext4
loop image over `out-ceiling`, build as the owner of the AOSP tree, and unmount
on exit. The wrapper accepts only `arm32` or `mixed`, defaults to one build job,
and builds only `systemimage`. The build subprocess runs in a transient cgroup
with 10 GiB `memory.high`, 10752 MiB `memory.max`, and 7 GiB
`memory.swap.max`, and defaults to CPUs 0-7 so Soong graph generation cannot
fan out across the entire host. This bounds host memory and paging pressure.

The bounded image retains a 7 GiB fallback swapfile, but it is not activated by
default. Measurement on the removable E: host showed that high-priority output-image
swap caused severe late-graph I/O stalls. The default therefore uses WSL's host-backed
swap within the same 7 GiB cgroup limit; set `CEILING_USE_OUTPUT_SWAP=1` only for a
host where the output image is on suitably fast storage. Paths and limits can be
overridden with `CEILING_AOSP_ROOT`, `CEILING_OUT_IMAGE`, `CEILING_MOUNT_DIR`,
`CEILING_CPUSET`, and the `CEILING_MEMORY_*` variables.

The wrapper deliberately exports `OUT_DIR=out-ceiling` relative to the AOSP
root while mounting that same directory by absolute path. Android 16's Soong
`test_package` host-output exclusion recognizes an `out...`-relative path but
misclassifies the equivalent absolute path as a source outside the module.

The Study host has less memory than Android 16's documented build minimum.
Apply `patches/0001-soong-forward-gomemlimit.patch` once to the disposable
Android 16 tree. It forwards `SOONG_GOMEMLIMIT` only to the cleared
`soong_build` environment; the wrapper defaults that limit to 6 GiB. This is a
host-build accommodation and does not change target artifacts or Android
runtime behavior.

The wrapper records 10-second cgroup samples beside the build log and emits a
summary containing wall time, CPU time, memory/swap peaks, pressure and cgroup
events. This is host evidence only and does not alter target inputs.

Study outcome on 2026-08-21: Prototype A completed the Soong product Ninja graph.
`build.ubox10_ceiling_arm.ninja` is 357,271,614 bytes with SHA-256
`e51e518d18add7033c15269b7879064daa0431d6b7e2f264917839e7d34c4b9d`.
The target Ninja build then reached action 452 of 122,523 before the user stopped
the work. No genuine target/product error and no `system.img` were produced; the
reported final failures are cancellation fallout. Prototype B remains
configuration only. These files must not be described as a successful image
build or flashable firmware.
