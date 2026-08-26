# Android 16 architecture prototype products

These files preserve the UBOX10 Architecture Ceiling Study products and their reproducible source
integration. Historical Prototype A selected the ARM32 product; exact
`android-security-16.0.0_r7` / `bp2a` r4 is now the physically accepted ARM32 control. Prototype B
r1 uses `ubox10_ceiling_arm64-bp2a-userdebug`: ARM64 primary, ARM secondary, Apollo board platform,
and the exact accepted r4 display/EGL/keylayout composition.

The tracked `hardware/aw/gpu` subtree is public Apache-2.0 gralloc source pinned from BPI commit
`316cd80ca43fa17b0385eacd7f6f3652bbd66b2a`; it contains no proprietary Mali binary. The B1 build
uses only its gralloc-1.x path plus the exact r7 AOSP passthrough mapper. Its two Android 16 source
compatibility changes are documented in `docs/m8/candidates/a16-prototype-b-r1.md`.

Both products inherit the official Android TV GSI base, retain only VNDK 31,
identify the device as an Android 12 field upgrade, and build no boot, vendor,
super, userdata, or pKVM image. They contain no proprietary Allwinner or donor binaries and
are not flashable firmware. Every output is a DISPOSABLE ARCHITECTURE PROTOTYPE.

Prototype A was verified on native Ubuntu 24.04 with 62.8 GiB RAM by exporting
relative `OUT_DIR=out-ceiling`, setting `BUILD_NUMBER=DISPOSABLE_CEILING_R4`,
unsetting `SOONG_GOMEMLIMIT GOMEMLIMIT`, selecting
`ubox10_ceiling_arm-bp4a-userdebug`, and running `m -j8 systemimage`. The exact
procedure is recorded in `docs/BUILD.md`.

`run-disposable-build.sh` is the retained optional low-disk wrapper for the
original WSL Study host. Run it as the WSL root user so one process can mount a pre-created ext4
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

The original WSL Study host has less memory than Android 16's documented build
minimum. On that host only, apply
`patches/0001-soong-forward-gomemlimit.patch` once to the disposable Android 16
tree. It forwards `SOONG_GOMEMLIMIT` only to the cleared
`soong_build` environment; the wrapper defaults that limit to 6 GiB. This is a
host-build accommodation and does not change target artifacts or Android
runtime behavior. Do not apply it on the verified 62.8 GiB native GCP host.

The wrapper records 10-second cgroup samples beside the build log and emits a
summary containing wall time, CPU time, memory/swap peaks, pressure and cgroup
events. This is host evidence only and does not alter target inputs.

Study outcome on 2026-08-21: native GCP Prototype A completed all 123,197 target
actions. `system.img` is 946,765,824 bytes with SHA-256
`fd349f1d8073dfeb71e2cea28915f1c755fa54e3eba85616fcaa279063f3edbe`.
It passed the focused filesystem, AVB, ARM32 ABI, APEX/VNDK 31, system-side
VINTF, linkerconfig and SELinux offline checks recorded in the active M8 status
and Architecture Ceiling Study. That accepted Gate 1 artifact remains unchanged
and was not rebuilt.

The subsequent exact-board audit found two bounded source integrations. The
Prototype A product now includes `device/ubox/ceiling/compatibility_matrix.xml`,
which declares only the two display HALs exposed by the accepted vendor. Apply
`patches/0002-sepolicy-defer-fuseblk-label-to-api31-vendor.patch` to an exact clean
A16 sepolicy tree for a future integrated source rebuild; it removes the one
platform `fuseblk /` genfscon that conflicts with the retained API-31 vendor
rule. The accepted Gate 1 output was instead consumed hash-locked by
`scripts/build-a16-prototype-a-r1-candidate.py`, which materializes those same
two changes in a staging image and rejects any other filesystem delta.

`a16-prototype-a-r1` completed exact system/vendor/product checks, LP/AVB/outer
preservation and split SELinux/linker/ELF closure. Full VINTF deliberately
remains exit 65 only for the inherited `CONFIG_NFS_FS=y` versus FCM-6 `n`
deviation that also exists against the device-accepted Android 12 matrix; it is
not reported as a pass. The later r5 physical kernel/wireless checkpoint, exact QPR0 r7 source
audit and r4 physical pass closed Gate 2. B0 then authorized one bounded Prototype B build. The same
canonical B1 has passed Mali/provider/handle gates but is currently **OFFLINE HOLD / PARTITION FIT
BLOCKER**: minimum staged vendor ext4 exceeds the frozen region by 18,165,760 bytes before AVB/FEC.
No B1 candidate or physical action exists.
