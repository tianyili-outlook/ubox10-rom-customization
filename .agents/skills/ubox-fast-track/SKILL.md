---
name: ubox-fast-track
description: Fast-track M8 work for the UBOX10 Android TV ROM, including planning, documentation, candidate construction, focused offline checks, flash preparation, authorized device testing, and failure diagnosis. Use when practical progress, recoverability, and TV usability matter more than production-grade process completeness.
---

# UBOX10 fast track

## Objective

Optimize for a recoverable, remote-friendly Android TV system with good playback, audio, networking, input, and application usability. Maximize the proven UBOX10 hardware without assuming an unverified SoC sales label.

Do not optimize for certification, exhaustive proof, enterprise governance, perfect documentation, or retention of every experiment.

## Default loop

For reversible work:

1. Read only the current status and task-relevant files.
2. Change one useful variable or a tightly coupled set.
3. Build one candidate.
4. Run one focused structural check.
5. Test on the device only after explicit flash authorization.
6. Record the first reproducible failure and use it to choose the next change.

Do not delay a recoverable experiment to prove every dependency. A boot failure is useful when it narrows the fault.

## Risk boundary

- **Routine:** documentation, parsers, scripts operating on copies, and focused checks. Proceed.
- **Candidate:** rebuilding system/product/super or repackaging IMAGEWTY. Confirm source immutability, partition fit, parseable output, rollback availability, and final filename/hash; then proceed.
- **Recoverable device test:** PhoenixCard testing with verified stock/Test8r2 rollback. Require explicit user authorization before flashing.
- **Elevated:** bootloader, GPT geometry, eFuse/OTP, TEE/security keys, irreversible calibration data, loss of recovery, or changes too broad to diagnose. Stop for explicit approval and targeted investigation.

Never modify original firmware or irreplaceable device evidence. Never flash without explicit authorization.

## Preservation

Preserve currently known-good hardware-facing partitions and dependencies unless the bounded experiment explicitly requires changing them.

Keep original firmware, known-good rollback, the current useful candidate, hashes, minimal provenance, failure-defining logs, and scripts/configs required to recreate the current chain. Remove redundant reports, superseded temporary artifacts, and abandoned outputs when their evidence is already retained or recoverable from Git.

## Documentation

Documentation must follow the simplest possible structure. Do not create a new document when an existing active source can hold the information. Prefer merging, shortening, or deleting over adding files or prose.

Use only these active sources:

- `README.md`: entry point and map;
- `docs/m8/STATUS.md`: facts, candidate history, current artifact, next action;
- `docs/m8/TODO.md`: ordered remaining work;
- `docs/BUILD.md`: architecture, inputs, and build chain;
- `docs/DEVICE_TEST.md`: flash, UART, and rollback;
- one current candidate record.

For progress updates record only: change, artifact/hash, check, observed result, and next action. Put command logs in ignored run/evidence directories. Do not create duplicate status, roadmap, risk, changelog, completion, or archive documents.

Use practical labels: `BUILT`, `OFFLINE CHECKED`, `READY TO FLASH`, `FLASHED`, `BOOTED`, `FAILED - <symptom>`, `ROLLBACK VERIFIED`, and `BLOCKED - <reason>`.

## Delegation and review

Use `scripts/run-luna-agent.ps1` for bounded routine execution. It launches an independent `codex exec` process with GPT-5.6 Luna and maximum reasoning; do not use native Codex subagents or substitute another model. The primary agent must inspect the actual diff and key validation evidence.

One implementation pass and one focused validation pass are normally enough. Add an independent review only for boot/recovery logic, partition geometry, verification/security changes, unusually broad work, or conflicting evidence.

## Final response

Report the result, material files/artifacts, checks, observed blocker if any, and the next action. Keep process narration short.
