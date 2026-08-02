# UBOX10 M8

This worktree is the M8 ARM32 Android TV path. The goal is a usable, recoverable Android TV experience while preserving the stock device-specific boot, kernel, vendor, vendor_dlkm, TEE, DRM, media, graphics, and wireless stack.

## Current state

- M8A.2a: COMPLETE - VERIFIED OFFLINE. Locked ARM32 Android 12 ATV system, product, and system_ext were built.
- Documentation reconciliation: COMPLETE.
- M8A.2b: COMPLETE - VERIFIED OFFLINE. Candidate `m8a-initial-atv-r1` was assembled and validated offline.
- M8A.2c: PENDING explicit physical authorization for boot, init, framework, ADB, and HDMI observation.
- M8A.2d: PENDING TV UI validation after M8A.2c.
- No flash, media preparation, or device operation occurred.

Candidate: [m8a-initial-atv-r1](docs/m8/candidates/m8a-initial-atv-r1.md). It is built and not boot-tested; documentation makes no bootability or promotion claim.

Start with [the active file map](docs/FILE_MAP.md), [status](docs/m8/STATUS.md), [candidate index](docs/m8/CANDIDATES.md), and [recovery readiness](docs/RECOVERY_RUNBOOK.md). Historical archives, CHANGELOG, and DISCOVERIES are not active status sources.
