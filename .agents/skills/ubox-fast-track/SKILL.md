---
name: ubox-fast-track
description: Fast-track UBOX10 M8 Android TV ROM work, diagnosis, build/repack, offline validation, flash preparation, authorized device testing, and failure analysis. Use when practical progress, recoverability, and TV usability matter more than exhaustive process or documentation.
---

# UBOX10 fast track

## Goal

Build a recoverable, remote-friendly Android TV system with reliable playback, audio, networking, input, and apps. Use verified hardware evidence, not unverified SoC labels. Favor practical progress over certification, exhaustive proof, governance, or exhaustive documentation.

## Execution

Start from current status and relevant files; expand investigation when evidence requires it. Prefer the smallest change that advances the current hypothesis, grouping tightly coupled changes when useful. Validate in proportion to risk and change size; broaden or repeat checks only after failures, new evidence, or higher-risk changes. Use reproducible failures to guide the next step.

Parallelize independent inspection, log analysis, or validation with subagents when it saves time or improves quality.

## Boundaries

Builds, repacking, documentation, scripts on copies, and offline checks may proceed autonomously while originals and rollback are protected.

Before marking a candidate READY TO FLASH, verify source immutability, partition fit, parseable output, rollback availability, and final filename/hash.

## Records

Keep only what is needed to reproduce or recover the current chain: original firmware, verified rollback, current useful candidate, hashes, minimal provenance, failure-defining logs, and required scripts/configs.

Update existing sources instead of creating parallel documentation:

README.md: entry point;
docs/m8/STATUS.md: facts, candidate history, current artifact, next action;
docs/m8/TODO.md: ordered remaining work;
docs/BUILD.md: architecture, inputs, build chain;
docs/DEVICE_TEST.md: flash, UART, rollback;
one current candidate record.

Progress entries contain only change, artifact/hash, validation result, and next action. Keep raw logs in ignored run/evidence directories. Remove redundant outputs when their evidence is retained or reproducible from Git.

Use status labels when useful: BUILT, OFFLINE CHECKED, READY TO FLASH, FLASHED, BOOTED, FAILED - <symptom>, ROLLBACK VERIFIED, BLOCKED - <reason>.

## Completion

Inspect the actual diff and material validation evidence. Add independent review only when risk, breadth, or conflicting evidence justifies it.

Report the result, material files/artifacts, checks, blocker if any, and next action. Keep process narration concise.
