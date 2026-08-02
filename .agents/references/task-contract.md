# Antigravity task contract

Use this template for one bounded worker task at a time.

## Task identity

- **Task ID:** `<unique-task-id>`
- **Role:** `<inspect | implement | validate | review>`
- **Objective:** `<one bounded outcome>`

## Verified baseline

- **Repository root:** `<absolute or repository-relative path>`
- **Branch and HEAD:** `<branch> @ <commit>`
- **Working-tree state:** `<verified summary; identify pre-existing changes>`
- **Current milestone:** `<verified milestone if relevant>`

## Scope and inputs

- **Relevant paths:** `<exact files or directories>`
- **Required inputs:** `<facts, artifacts, or commands required>`
- **Explicit non-goals:** `<work that must not be attempted>`
- **File ownership:** `<files the worker may edit; empty for read-only modes>`
- **Protected and immutable files:**
  - all original firmware images and source captures;
  - irreplaceable device evidence;
  - `<additional protected paths>`.

## Operations

- **Permitted operations:** `<bounded reads, edits, builds, or tests>`
- **Prohibited operations:**
  - destructive Git commands, reset, clean, stash, discard, force-checkout, merge, commit, or push;
  - physical-device flashing or other physical-device mutation;
  - modifying original firmware images or irreplaceable evidence;
  - unsupported broad redesign or edits outside explicit file ownership;
  - accessing, printing, or storing credentials.

## Acceptance

- **Acceptance criteria:**
  1. `<observable criterion>`
  2. `<observable criterion>`
- **Validation commands:** `<exact approved commands, or "none">`
- **Required evidence:** `<paths, command results, diffs, or findings>`
- **Expected final response:** Return one JSON object conforming to `.agents/references/result-schema.json`. Be concise and report uncertainty rather than guessing.

## Stop conditions

Stop and return a structured incomplete or failed result if:

- a required input is missing or contradictory;
- the requested operation exceeds file ownership or permitted operations;
- a validation step would modify protected evidence or requires unsupported privileges;
- authentication, environment, tool, or device-only limitations prevent reliable completion;
- physical-device access or flashing would be required.

## Physical-device boundary

No physical-device action is authorized. Do not connect to, reboot, unlock, erase, partition, write, or flash the UBOX10. Set `physical_device_actions_performed` to `false`. Physical flashing may proceed only after explicit user authorization and a final Codex decision.
