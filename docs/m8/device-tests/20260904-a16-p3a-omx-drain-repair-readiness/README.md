# P3-A RC-A: Allwinner OMX drain repair readiness

Date: 2026-09-04

Status: **READY_FOR_NARROW_BINARY_PATCH — DESIGN ONLY / NO FIX APPLIED**

This closes the offline source-archaeology and state-machine study for RC-A only. It does not
implement or build a repair. RC-B/compat1b is deliberately deferred, P3-B Main10 remains **NOT
AUTHORIZED**, and `r8` remains **NOT AUTHORIZED / NOT BUILT**.

## Scope and evidence base

The starting repository revision is
`df096873df46a5966b6e75b6c3c854a0dd271489` (`m8: analyze P3-A 4k30 failure`). The
canonical preceding forensic report is
[`../20260903-a16-p3a-4k30-failure-forensics/README.md`](../20260903-a16-p3a-4k30-failure-forensics/README.md).
No ADB or device command was run for this study. No runtime source, vendor ELF, candidate image,
kernel, Skia, gralloc or Mali file was changed.

The exact physical runtime object remains:

| Property | Exact value |
|---|---|
| Installed path | `/vendor/lib/libOmxVdec.so` |
| ELF | ELF32 little-endian ARM |
| Size | 83,780 bytes |
| SHA-256 | `29f500e3089651c41a4c2a88c1f82b99ee389af7a83101ce929516018d5cea87` |
| Build ID | `2042d7e0112320dc855cccee324af569` |
| Symbol | local mini-debug symbol `_ZL9__anDrainP10OmxDecoder` |
| Thumb range | `0xdc7c..0xf724` (entry symbol value `0xdc7d`, size 6,824) |
| Crash | `0xe138`, `__anDrain(OmxDecoder*)+1212` |

## Source archaeology

All local `/work/src`, project reconstruction material, build logs and retained BSP/vendor trees
were searched using function names, distinctive strings, typo-preserved log text and helper-call
sequences. No source file was found that reproduces the exact runtime line numbering and merged
`__anDrain` body. Four public/localized source candidates materially constrain the intended state
machine:

| Candidate | Revision and source | File SHA-256 | Classification | Match assessment |
|---|---|---|---|---|
| CalvinXu17 `libcedarc` (A133/Android Q generation) | [`e68d4a727085d02d4622d85b5234304349d4e448/openmax/vdec/src/omx_vdec_aw_decoder_android.cpp`](https://github.com/CalvinXu17/libcedarc/blob/e68d4a727085d02d4622d85b5234304349d4e448/openmax/vdec/src/omx_vdec_aw_decoder_android.cpp) | `d5098faf491bdae0ee31dfa3dbe2aed7cdc97822bc9b912d1b3ed134f72e8204` | **NEAR-EXACT SAME STATE MACHINE** | Split copy/zero-copy drain, `anCheckResolutionChange`, color-aspect helpers, FBM ownership, exact NULL log typo and return lifecycle all match. Exact binary has later additions and moved color-aspect work. |
| `tina_multimedia` | [`63344eadfbab18195046678079d2f3d32d0c61cc/libcedarc/openmax/vdec/src/omx_vdec_aw_decoder_android.cpp`](https://github.com/jeasonzs/tina_multimedia/blob/63344eadfbab18195046678079d2f3d32d0c61cc/libcedarc/openmax/vdec/src/omx_vdec_aw_decoder_android.cpp) | `0a1c891ae0366b02de1b8573179cf9a074d73cc5c92ded829b28e6e9ffaa3421` | **NEAR-EXACT SAME STATE MACHINE** | Independently preserves the same peek/request/return split and copy drain shape. Its FBM implementation exposes the queue semantics used below. |
| aodzip `libcedarc` (V536-derived) | [`e4246be521203adb2d93d52482239044a7f9b6fe/openmax/vdec/src/omx_vdec_aw_decoder_android.cpp`](https://github.com/aodzip/libcedarc/blob/e4246be521203adb2d93d52482239044a7f9b6fe/openmax/vdec/src/omx_vdec_aw_decoder_android.cpp) | `09d2dd267594ccaebd1b08c62d15d066ed6ba404ce2684ce843612262f2d6a40` | **OLDER RELATED SOURCE** | Same state-machine family, but farther from the runtime generation. |
| allwinner-zh `media-codec` | [`a912bbe300d522e199001bd903bab22e54eff37b/sunxi-cedarx/SOURCE/omxil/omx_vdec.cpp`](https://github.com/allwinner-zh/media-codec/blob/a912bbe300d522e199001bd903bab22e54eff37b/sunxi-cedarx/SOURCE/omxil/omx_vdec.cpp) | `0b643d5d38b80957a21fe5a6c5e56c0551ec208e3e00525076361bd6896aa090` | **OLDER RELATED SOURCE** | Confirms the older `NextPictureInfo` then `RequestPicture` design, but lacks the newer context, zero-copy split and color-aspect logic. |

No candidate is labelled exact merely because it contains `__anDrain`. The strongest candidate is
the CalvinXu17 file: function shape, helper order, field lifecycle and distinctive strings agree,
while source line numbers and the location of color-aspect processing do not. That difference is
central: the published copy path evaluates color aspects after `RequestPicture`; the exact binary
has moved an equivalent evaluation into its pre-acquisition resolution/port-settings path.

## Exact binary state-machine reconstruction

Names below are semantic names. Addresses and offsets are exact binary facts; names marked
"inferred" are correlated with the near-exact source and imported helper behavior.

| Address/range | Exact operation | Semantic interpretation | Confidence |
|---|---|---|---|
| `0xdc98` | call through decoder ops; compare result with zero | `ValidPictureNum(decoder, 0)`, wait/return when no valid picture | High |
| `0xdcb4..0xdcd2` | load `OmxDecoder+0x58bc`; branch to `0xde58` when zero | `bUseZeroCopyBuffer`; zero selects the copy/non-zero-copy path | High |
| `0xde5e..0xde76` | lock, load decoder, call helper, save result in `r6`, unlock | `picture = NextPictureInfo(decoder, 0)`; `picture` is a non-owning queue peek | High |
| `0xde7a` | `cmp r6, #0`; exit when zero | explicit peek NULL check | Exact |
| `0xde96..0xdeae` | read `picture+0x18..+0x24` and `+0x0c/+0x10` | crop/visible rectangle and coded geometry | High |
| `0xdf06..0xdf1a`, `0xe08c..0xe11e` | compare picture geometry with output-port geometry, including alignment-equivalent branch | decide whether an output-port/settings change is required | High |
| `0xdea0` | `mov r12, r6` | retain the already-checked `NextPictureInfo` pointer across the comparisons | Exact |
| `0xe120..0xe130` | compute `OmxDecoder+0x58e0`, then load that slot into `r0` | load `pCtx->pPicture`, the currently owned display picture | High |
| `0xe138..0xe150` | read `r0+0x9c`, `+0xa4`, `+0xa8`; call `adapteColorAspects` | evaluate transfer/matrix/full-range/primaries, but from the wrong object | High |
| `0xe166..0xe19a` | compare and update context color aspects | record a changed color-aspect contract | High |
| `0xe1b0` onward | test codec value `0x116` (H.265); callback/exit on relevant change | emit port/settings change without dequeuing the peeked frame | High |
| `0xe402` | request an OMX output-port buffer | `doRequestPortBuffer` equivalent | High |
| `0xe41c..0xe432` | lock; `RequestPicture(decoder, 0)`; store to `OmxDecoder+0x58e0`; unlock | dequeue the frame and acquire FBM render ownership | High |
| `0xe460` | explicit NULL check | safe handling exists for the *later* acquisition | Exact |
| later copy/FBD path | populate output; return output header to caller | copy/deliver the acquired decoded picture | Source-correlated high |
| `__anReturnBuffer+...` (`0xfa74`, `0xfa8e`, `0xfa98`, `0xfaa4`, `0xfaaa`) | locate/check slot; lock; `ReturnPicture`; clear slot; unlock | release FBM ownership after FBD and restore the slot to NULL | High |

Relevant pseudocode, preserving the exact ordering, is:

```c
if (ValidPictureNum(decoder, 0) <= 0) {
    wait_or_return();
    return NULL;
}

if (ctx->bUseZeroCopyBuffer) {
    return drainZeroCopy(ctx);
}

lock(ctx->decoder_lock);
VideoPicture *picture = NextPictureInfo(decoder, 0);  // peek; no ownership
unlock(ctx->decoder_lock);
if (picture == NULL) return NULL;

Geometry next = geometry_from(picture);
if (geometry_requires_port_change(ctx, next)) {
    update_port_definition_and_notify(ctx, next);
    return NULL;                                      // picture remains queued
}

// Exact faulty binary behavior:
VideoPicture *wrong = ctx->pPicture;                  // +0x58e0, normally NULL
ColorAspects nextColor = adapteColorAspects(
    wrong->transfer_characteristics,                  // +0x9c, crash at 0xe138
    wrong->matrix_coeffs,                             // +0xa0
    wrong->video_full_range_flag,                     // +0xa4
    wrong->colour_primaries);                         // +0xa8
if (hevc_color_change_requires_notification(ctx, nextColor)) {
    update_color_and_notify_port_change(ctx, nextColor);
    return NULL;                                      // still no ownership transfer
}

OMX_BUFFERHEADERTYPE *out = doRequestPortBuffer(ctx->output_port);
if (out == NULL) return NULL;

lock(ctx->decoder_lock);
ctx->pPicture = RequestPicture(decoder, 0);            // dequeue; take ownership
unlock(ctx->decoder_lock);
if (ctx->pPicture == NULL) return NULL;

copy_or_fill_output(out, ctx->pPicture);
return out;                                           // caller issues FBD

// Same drain thread, after FBD:
lock(ctx->decoder_lock);
ReturnPicture(decoder, ctx->pPicture);
ctx->pPicture = NULL;
unlock(ctx->decoder_lock);
```

## The two-picture question

The functions have different ownership contracts:

- `NextPictureInfo` reaches `FbmNextPictureInfo`, reads the head of
  `pValidPictureQueue`, and does not dequeue it or change render ownership. It is a non-owning peek.
- `RequestPicture` reaches `FbmRequestPicture`, dequeues from `pValidPictureQueue`, adjusts valid/
  waiting counts, marks render use and returns the owned picture.
- `ReturnPicture` reaches `FbmReturnPicture` and releases/recycles that owned picture.

The option assessment is therefore:

| Option | Finding | Ownership/state consequence |
|---|---|---|
| **A — read color aspects from the peeked `picture`** | **Correct.** The exact function already checked and retained this pointer in `r12`; geometry is read from it immediately before the bad block. | No dequeue, count change, FBD, leak or extra return. A port-change exit leaves the frame queued exactly as intended. |
| B — move the block after `RequestPicture` | Rejected. Published older code did this, but the exact newer binary intentionally moved HEVC color evaluation before output-buffer acquisition. | A color-induced port change would occur after ownership transfer and require a new return/rollback path; moving it risks a held frame or invalid FBD ordering. |
| C — require an older current `pPicture` | Rejected. `calloc` initializes the slot to NULL and the same drain thread returns and clears it after the previous FBD. | Treating a stale owned frame as the next frame would violate the lifecycle. |
| D — skip while reconfiguration is pending | Rejected as the repair. The drain loop already gates active port reconfiguration, and this block can itself discover the color change that must trigger notification. | Skipping it loses a legitimate HEVC port/color update. |
| E — simple `if (!ctx->pPicture) return` | Rejected. It prevents the crash but silently suppresses color evaluation on the normal copy path. | Can starve/drift the state machine and is not a semantic repair. |

## Why P3-A reaches the block

The exact reachable-condition chain is:

1. `ValidPictureNum(decoder, 0) > 0`;
2. `OmxDecoder+0x58bc == 0`, therefore this invocation uses the copy/non-zero-copy path;
3. `NextPictureInfo(decoder, 0) != NULL`;
4. the visible/coded geometry comparison is equal or alignment-equivalent, so no geometry port-change
   exit is taken;
5. control reaches the pre-acquisition color-aspect block;
6. `OmxDecoder+0x58e0 == NULL`, as expected before `RequestPicture`, and `0xe138` dereferences it.

These predicates are binary-proven. The P3-A logs prove the 3840x2160 HEVC/Cedar path and the exact
crash, but do not preserve the output-port old/new geometry, alignment values, or the reason that this
invocation selected copy mode. Those runtime values remain unknown.

This is consequently **not classified as a 4K-only defect**. It is a generic copy-path lifecycle/
ordering bug reachable when a valid peeked frame has stable or alignment-equivalent geometry. The
accepted 1080p path used registered native/zero-copy buffers (`SetVideoFbmBufAddress` evidence), while
the failing invocation followed the binary's non-zero-copy branch. Four-kilopixel playback exposed the
branch, but resolution alone is not the repair predicate.

## Integer, ABI and concurrency checks

- The directly demonstrated cause is a NULL `VideoPicture*`, not an integer overflow. 3840x2160 and
  its normal YUV size arithmetic fit signed and unsigned 32-bit ranges.
- The read offsets correlate consistently with the same `VideoPicture` color fields in the exact
  binary's earlier peek path and in the public source. There is no positive evidence of a
  `VideoPicture` ABI/version mismatch, fixed 1080-sized array, or width truncation at this fault.
- `drainThreadEntry` calls drain, performs the FBD callback when an output header is returned, and
  invokes the return-buffer operation sequentially on the same drain thread. Normal writes and clears
  of `OmxDecoder+0x58e0` therefore belong to that serialized lifecycle.
- The OMX message/callback side queues output buffers; it does not normally clear this slot. Flush and
  state transitions suspend/gate drain work and use decoder synchronization before reset.
- The exact return helper checks the pointer before taking the lock, which is not ideal as a general
  concurrency pattern, but no evidence shows concurrent clearing caused this crash. Here the pointer
  is deterministically read before its first `RequestPicture` assignment.

The study therefore rules out a demonstrated asynchronous-clear race, double return or stale-pointer
fault for this event. It does not claim a formal proof that every teardown path is race-free.

## Repair-readiness decision

**RC-A = READY_FOR_NARROW_BINARY_PATCH.**

No exact buildable runtime source generation was recovered, so rebuilding a proprietary wrapper from
one of the near-exact trees would introduce a far broader and less auditable ABI/code-generation
delta. Nevertheless, correct behavior is independently established strongly enough for a narrow
operand correction in the exact ELF:

- **Logical target:** the exact newer equivalent of
  `anCheckResolutionChange(OmxDecoder *ctx, VideoPicture *picture)`, specifically its color-aspect
  input selection.
- **Before:** load `ctx->pPicture` from `OmxDecoder+0x58e0`, then read `+0x9c/+0xa0/+0xa4/+0xa8`.
- **After:** read those same four fields from the already validated, live `picture` returned by
  `NextPictureInfo` and retained in the function (`r12`/saved peek operand).
- **Do not add:** a NULL-only early return, dequeue, extra `RequestPicture`, extra `ReturnPicture`,
  retry, frame drop, resolution check or 4K predicate.

This is a lifecycle correction rather than an exception handler. It preserves the pre-acquisition
color/port notification, keeps the frame in the FBM valid queue until the existing `RequestPicture`,
and leaves FBD/return ordering unchanged. The exact future binary edit must be independently decoded
and mechanically proven against this precise Build ID before use; only the operand-producing
instruction(s), plus unavoidable integrity/signature/container consequences, may differ. This report
does **not** specify unchecked patch bytes and does not apply a patch.

Expected 1080p behavior is unchanged because its zero-copy branch does not execute this copy-path
block. The fix is generic to the malformed copy-path ordering and by itself neither enables nor claims
4K, Main10, HDR, AFBC or protected playback.

### Risks that remain for implementation review

- The peek remains non-owning. Existing source intentionally reads its geometry outside the outer
  wrapper mutex, so the proposed color reads follow the same established lifetime assumption; a
  future patch audit must ensure no extra call/yield is inserted between peek and read.
- Any instruction rewrite must preserve Thumb instruction boundaries, register liveness, stack state,
  unwind metadata and branch targets.
- The future candidate must prove one semantic runtime-file delta and retain exact ELF identity guards.
- Fixing RC-A will only expose the next boundary. It does not repair or prejudge RC-B's 4K graphics
  import failure.

## Minimum future RC-A retest evidence contract

A later, separately authorized candidate/test must use one manual, bounded HEVC Main 8-bit SDR 4K30
attempt. Before playback, preserve the fixture independently:

- filename, exact byte size and SHA-256;
- complete `ffprobe` transcript;
- 3840x2160 dimensions and exact frame-rate rational;
- HEVC profile and level, pixel format, BT.709 color tags;
- audio codec and exact duration.

Capture live PC-side logs before playback so the pre-graphics interval survives any restart. Required
markers/evidence are:

- exact SPS/coded/visible geometry and port-settings-change sequence;
- whether copy or zero-copy mode is selected and why, if observable;
- output format, usage, stride, aligned height and planes when available;
- `NextPictureInfo` pointer/geometry/color fields;
- current `OmxDecoder+0x58e0` before the corrected block;
- later `RequestPicture` result, slot store, FBD, `ReturnPicture` and slot clear;
- OMX service PID before/during/after, plus exact death/restart census;
- boot ID and critical framework/service PID continuity;
- crash buffer and tombstone delta.

Success for RC-A requires no drain SIGSEGV, continued `RequestPicture`/FBD/return progression and OMX
PID continuity. The same run must continue collecting the exact 4K handle/metadata/EGL contract if it
reaches graphics, because RC-B remains unresolved. A later graphics failure is not an RC-A failure if
the codec lifecycle criteria have already passed.

## Governance

- P3-A remains **PHYSICAL FAIL / FORENSICS COMPLETE**.
- RC-A is **READY_FOR_NARROW_BINARY_PATCH**, but **NO OMX FIX IS APPLIED**.
- RC-B/compat1b is deferred and unchanged; this task performs no Skia, metadata, gralloc or Mali work.
- P3-B Main10 remains **NOT AUTHORIZED**.
- The authorized 1080p compat1a proof is unchanged.
- Audio startup P1 remains **CLOSED**; P2 remains **COMPLETE**.
- No physical retest occurred and no Android image or candidate was built.
- `r8` remains **NOT AUTHORIZED / NOT BUILT**.
