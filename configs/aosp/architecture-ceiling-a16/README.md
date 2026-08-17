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
builds only `systemimage`, and gives a 7 GiB swapfile inside that bounded image
priority over WSL's host-backed swap. The build subprocess runs in a transient
cgroup with 9.5 GiB `memory.high`, 10 GiB `memory.max`, and 7 GiB
`memory.swap.max`, and defaults to CPUs 0-7 so Soong graph generation cannot
fan out across the entire host. This bounds host memory and paging pressure.
Its paths can be overridden with `CEILING_AOSP_ROOT`, `CEILING_OUT_IMAGE`,
`CEILING_MOUNT_DIR`, and `CEILING_CPUSET`.

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

Study outcome on 2026-08-17: Prototype A reached product discovery and Soong
host bootstrap, then entered Android.bp graph analysis, but no product Ninja
graph or `system.img` completed. The final CPU/swap profile above is syntax-checked but
was not rerun after the user directed that no further disposable build occur.
Prototype B remains configuration only. These files must not be described as a
successful build or a flashable image.
