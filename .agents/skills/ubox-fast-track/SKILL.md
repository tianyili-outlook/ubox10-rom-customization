---
name: ubox-fast-track
description: Fast-track execution policy for the UBOX10 Android TV ROM project. Use for M8 planning, firmware construction, candidate assembly, documentation updates, offline checks, flashing preparation, real-device testing, and fault diagnosis when the goal is rapid practical progress rather than production-grade process completeness.
---

# UBOX10 Fast-Track Execution

## Mission

Optimize for:

1. A system that boots reliably enough for daily use.
2. A clean, remote-friendly Android TV experience.
3. Good video playback, audio, network, remote, and application usability.
4. Easy recovery to a known-good stock image.
5. Fast learning through real candidate testing.
6. Maximum practical use of the Allwinner H618 hardware.

Do not optimize for:

- production certification;
- enterprise release governance;
- exhaustive proof before testing;
- perfect documentation;
- complete automation of every one-off operation;
- retaining every intermediate experiment;
- eliminating every theoretical risk before producing a candidate.

## Default working posture

Default to action.

When the likely failure is reversible:

- inspect only the information needed to choose the next step;
- make a bounded change;
- build the candidate;
- perform a small number of high-value offline checks;
- test it;
- use the first reproducible failure to guide the next investigation.

Do not turn a practical milestone into a general audit.

Do not repeatedly reread the whole repository when the relevant files and current state are already known.

Do not block progress merely because some non-critical detail is uncertain.

Make a reasonable assumption, state it briefly, and proceed when:

- rollback remains available;
- original material remains protected;
- the uncertainty does not create a meaningful brick risk;
- a failed test will still provide useful diagnostic information.

## Risk-based execution levels

Classify the next action internally. Do not create a separate risk document.

### Level 0 - routine and reversible

Examples:

- documentation corrections;
- scripts that operate on copies;
- rebuilding product partitions;
- inspecting images;
- changing overlays or packages;
- generating manifests;
- testing build commands.

Action: proceed immediately with only task-relevant checks.

### Level 1 - candidate construction

Examples:

- rebuilding `system`, `product`, or `system_ext`;
- reconstructing `super` using a previously understood layout;
- repackaging an IMAGEWTY or PhoenixCard candidate;
- replacing approved logical partitions while preserving hardware-facing partitions.

Minimum checks:

- source images are not overwritten;
- target partitions fit;
- output can be parsed or unpacked;
- a known-good rollback image exists;
- the resulting candidate has a recorded filename and hash.

After these checks, proceed.

Do not require a comprehensive framework/vendor compatibility proof before the first device test.

### Level 2 - recoverable device test

Examples:

- writing an approved candidate to an SD card;
- booting through a known PhoenixCard recovery route;
- cold-boot testing a candidate where stock restoration is already proven.

Minimum checks:

- stock rollback image is available and readable;
- recovery procedure is known;
- candidate and rollback files are clearly distinguishable;
- the action does not alter bootloader, partition table, secure keys, or irreversible fuses;
- the test changes a sufficiently understandable set of variables.

After these checks, physical testing may proceed when the user has explicitly authorized the flashing step.

Do not add production-grade release gates.

### Level 3 - elevated caution

Stop and obtain explicit user approval before actions involving:

- bootloader replacement;
- partition-table changes;
- eFuse or OTP writes;
- TEE keys or security material;
- AVB keys or signing secrets;
- destructive writes to unique calibration data;
- loss of the established recovery route;
- overwriting the only known-good firmware;
- irreversible hardware operations;
- changes so broad that a failure would provide no useful attribution.

For Level 3 only, perform additional investigation and document the specific risk.

Do not apply Level 3 caution to ordinary candidate assembly.

## Build-first diagnostic strategy

Prefer this loop:

1. Define one practical candidate.
2. Make the smallest useful change set.
3. Build it.
4. Run essential structural checks.
5. Test it on the device when authorized.
6. Record the first reproducible failure.
7. Investigate that failure.
8. Produce the next candidate.

Avoid this loop:

1. Attempt to prove every dependency correct.
2. Create extensive plans and risk matrices.
3. Expand the scope into a general architecture audit.
4. Produce multiple speculative reports.
5. Delay device testing indefinitely.

A candidate does not need to be theoretically perfect to be useful.

A recoverable boot failure is an acceptable experiment when it isolates or meaningfully narrows the next issue.

## Check budget

Use the minimum checks capable of detecting:

- source-image destruction;
- partition overflow;
- malformed image packaging;
- loss of rollback;
- obvious architecture mismatch;
- an error that would make the test meaningless.

Normally limit pre-device validation to one focused validation pass.

Run a second pass only after fixing a concrete defect found in the first pass.

Do not repeatedly run overlapping validators or independent reviewers merely for reassurance.

Do not perform exhaustive checks unless:

- the user requests them;
- the candidate touches a Level 3 area;
- an earlier failure indicates that the additional check is directly relevant.

Passing more checks is not itself project progress.

## Scope and variable control

Prefer one major experimental variable per candidate, but do not interpret this mechanically.

It is acceptable to combine tightly coupled changes when:

- testing them separately would not be meaningful;
- the original architecture requires them together;
- rollback remains straightforward;
- a failure can still be diagnosed from UART, recovery behavior, logs, or partition comparison.

Do not split work into artificial micro-milestones solely to make the process appear rigorous.

Do not block a candidate because several known-required components must move together.

## Documentation policy

Documentation is a tool for continuity, not a deliverable in itself.

Maintain only the minimum active source of truth.

Normally update:

- `docs/m8/STATUS.md`;
- `docs/m8/TODO.md`;
- the active file map only when paths or authoritative artifacts change;
- one candidate record or manifest when an image is generated.

For ordinary progress, record only:

1. What changed.
2. What was produced.
3. What was tested.
4. What happened.
5. What remains next.

Keep milestone updates short.

Prefer tables, checkboxes, hashes, exact paths, and concise result lines.

Do not write:

- repeated project background;
- broad risk discussions for reversible work;
- long narratives of commands already preserved in logs;
- duplicate status documents;
- detailed justifications for settled decisions;
- extensive "not yet validated" boilerplate;
- production-style sign-off sections;
- exhaustive lists of unchanged components;
- speculative future plans beyond the next useful milestone.

Do not update historical or archived documents merely to make their old wording current.

Mark an old document superseded only when users could otherwise mistake it for the active source of truth.

Command logs belong in run logs or evidence directories, not in status documents.

## Status language

Use clear practical labels:

- `BUILT`
- `OFFLINE CHECKED`
- `READY TO FLASH`
- `FLASHED`
- `BOOTED`
- `FAILED - <short symptom>`
- `ROLLBACK VERIFIED`
- `BLOCKED - <specific blocker>`

Avoid ambiguous or inflated labels such as:

- fully validated;
- production ready;
- completely safe;
- comprehensive verification complete.

Also avoid repeatedly emphasizing that every offline result is not a physical test. State the boundary once in the relevant status section.

## Planning policy

For a normal milestone, use a short execution plan of no more than:

- objective;
- changes;
- essential checks;
- stop condition.

Do not create a large plan document unless the task changes the overall project architecture.

Do not ask the user to approve routine reversible implementation steps.

Proceed using reasonable assumptions.

Ask the user only when:

- a required physical action needs authorization;
- alternatives materially affect the intended user experience;
- the next step enters Level 3;
- a required fact cannot be obtained from the repository or device evidence.

## Review policy

The primary agent must inspect the actual diff and key artifacts.

One implementation pass plus one focused validation pass is normally enough.

An independent review is optional, not mandatory.

Use a reviewer when:

- boot or recovery logic changes;
- dynamic-partition geometry changes;
- security or verification handling changes;
- the implementation is unusually broad;
- the worker result conflicts with repository evidence.

Do not use reviewers for routine documentation updates, simple scripts, or repeated confirmation of already verified facts.

Review findings must focus on defects that can change the outcome.

Ignore cosmetic findings and theoretical edge cases that do not affect the current candidate.

## Handling failures

Treat failure as evidence.

On failure:

1. Capture the first stable symptom.
2. Preserve the relevant log.
3. Identify the earliest known failure stage.
4. Compare it with the last known-good candidate.
5. Form the smallest plausible explanation.
6. Make the next targeted change.

Do not immediately launch a full repository or architecture audit.

Do not generate long postmortems for routine failed candidates.

Record a failure in this compact form:

- candidate;
- symptom;
- evidence path;
- likely layer;
- next experiment.

## Artifact retention

Keep:

- original firmware;
- known-good rollback image;
- latest useful candidate;
- hashes and minimal provenance;
- logs that explain a reproducible failure;
- scripts required to recreate the current candidate.

Remove or archive, when safe:

- superseded temporary images;
- duplicate extracted trees;
- abandoned candidate outputs;
- transient logs with no diagnostic value;
- redundant reports;
- obsolete generated manifests.

Never delete irreplaceable device evidence or the only copy of an image.

## Agent and delegation behavior

The primary agent owns:

- milestone selection;
- high-risk decisions;
- final diff inspection;
- physical flashing authorization boundary;
- acceptance of the result.

Execution workers should:

- perform the assigned work rather than redesign the process;
- avoid expanding the task into a broad audit;
- return concise results;
- flag only material blockers;
- avoid asking questions that repository inspection can answer;
- avoid repeating unchanged project context.

When the project provides an external execution worker such as Antigravity, delegate routine exploration, implementation, building, and checking to it.

Do not create multiple agents whose only purpose is to independently repeat the same checks.

Use parallelism only for truly independent work.

## Response style

During execution, report only material progress:

- candidate produced;
- meaningful blocker found;
- test result;
- decision needed.

Final reports should normally contain:

- result;
- artifacts or changed files;
- checks performed;
- observed failure, if any;
- next action.

Do not include a long account of the reasoning process.

Do not include lengthy safety disclaimers for reversible operations.

## Conflict resolution

When this skill conflicts with generic production-engineering habits, this skill controls the working style for UBOX10.

It does not override:

- explicit user instructions;
- system safety requirements;
- protection of original firmware and security material;
- the requirement for explicit authorization before physical flashing.

When uncertain whether more process is necessary, choose the lighter process unless the uncertainty falls under Level 3.

## Definition of sufficient progress

A milestone is sufficiently complete when it produces one of:

- a usable image;
- a flashable candidate;
- a reproducible failure;
- a verified rollback;
- a concrete blocker with a targeted next experiment.

Do not delay these outcomes to improve process completeness.
