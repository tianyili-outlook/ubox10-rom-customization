# Android 16 QPR0 Prototype B r1 candidate attempt

Status: **PRE-BUILD BLOCKED / NO CANDIDATE / LOCAL ARM64 MALI INTAKE MISSING**.

Canonical candidate ID: `a16-prototype-b-r1`. Architecture milestone: Prototype B B1.

## Result

The first mandatory B0 gate ran before any expensive build or source integration on 2026-08-26.
The locked local intake path did not exist, and a read-only exact-size search of `/work` found no
18,145,112-byte substitute to validate. The required result is therefore:

**B1 BUILD BLOCKED — LOCAL ARM64 MALI INTAKE MISSING**

Formal task decision: **OFFLINE HOLD — EXACT BOUNDED BLOCKER: LOCAL ARM64 MALI INTAKE MISSING
BEFORE BUILD**.

No Soong/Ninja or kernel command ran, no AOSP/kernel/vendor source was changed, no logical or outer
image was assembled, and no `out/candidates/a16-prototype-b-r1/` artifact was created. This is an
external pre-build prerequisite failure, not an ARM64 architecture contradiction and not a B1
offline acceptance result.

## Verified control and source preflight

| Item | Exact result |
|---|---|
| Repository starting HEAD | `86400020e9fa6da9809ab02410cd54beec321b5b` |
| Frozen r4 image | 1,239,746,560 bytes / `E125DD8FFB9F5B4A7B2B9B86DD8377367409AB00D1B29BE1E719CE25768E2111` — PASS |
| QPR0 source | `android-security-16.0.0_r7`; manifest commit `ebea28d151539ecf0730b1a4ab92ac33edc17ac9` |
| Pinned source manifest | 246,298 bytes / `F52BA4A04957CEC7EEE7C9DCDD1525533156A0B5A1F0ADFC31A8155F48FB087E` — PASS |
| Existing source delta | Only the already accepted one-line platform `fuseblk /` deferral; no new B1 mutation |
| Host at gate | 8 CPUs; 65,841,336 kB RAM; no swap; 14,908,239,872 bytes free on `/work` |
| Physical actions | None; flash not authorized or attempted |

The low free-space value is a capacity warning for the future mixed build, but it was not exercised
because the mandatory proprietary intake gate failed first. The next task must re-check disk before
building and must not delete retained source/build/rollback workspaces merely to make room.

## Exact recovery condition

A user or artifact custodian with a separately established right to use the file must place this
exact regular file outside Git:

| Field | Required value |
|---|---|
| Local path | `/work/local-proprietary/ubox10/prototype-b-b1/libGLES_mali.so` |
| Size | 18,145,112 bytes |
| SHA-256 | `03333D495E3566C7D85CA2E000DA569A16CE8F022EA25C0EA61950C891D5C7F8` |
| ELF | ELF64 / AArch64 |
| SONAME | `libGLES_mali.so` |
| Build ID | `281008657ed1f606be382d076fe69918` |
| Candidate destination | `/vendor/lib64/egl/libGLES_mali.so` |
| Redistribution right | **UNPROVEN**; local experiment only, no Git/evidence-archive blob |

Then run from the repository root:

```sh
python3 scripts/check-a16-prototype-b-r1-mali.py
```

The checker also requires the exact nine-entry DT_NEEDED list pinned in
`configs/candidates/a16-prototype-b-r1.json`; it returns nonzero on a missing, symlinked,
non-regular or identity-mismatched file. A PASS authorizes resuming this same r1 implementation
attempt from the B0 contract; it does not itself authorize a build with insufficient disk, a flash,
or any broadened provider substitution.

## Deferred gates — not run

Build, ARM/ARM64 handle layout, generated mapper/gralloc identity, final ELF census,
linker/`sphal`, full VINTF, partition fit, AVB, LP/super, IMAGEWTY and detached r4 preservation
checks are all **NOT RUN / BLOCKED UPSTREAM**. They must not be reported PASS or FAIL from this
attempt. Gate 2 remains CLOSED and frozen r4 remains the rollback control.
