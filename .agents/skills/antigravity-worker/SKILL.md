---
name: antigravity-worker
description: Delegate routine UBOX10 repository investigation, implementation, documentation, builds, validation, and review to Antigravity while Codex remains the primary orchestrator and final reviewer.
---

# Antigravity worker

Use this skill whenever routine UBOX10 repository work can be executed by the project-local Antigravity bridge.

## Orchestrator boundary

Do not spawn native Codex subagents. Codex personally performs only:

- goal interpretation and milestone decomposition;
- approval of a bounded task contract;
- inspection of the worker's compact structured result and the actual final Git diff;
- final acceptance or rejection;
- high-risk architecture and physical-flashing decisions.

Delegate routine repository exploration, documentation updates, implementation, script creation, build execution, log analysis, offline validation, and targeted review.

Create one bounded task at a time by default. Run only one write worker in a checkout. Before launching parallel write workers, create separate Git worktrees and give each worker explicit, non-overlapping file ownership.

## Context contract

Never pass the complete Codex conversation transcript. Give the worker only:

- the objective;
- verified current state;
- relevant paths and required inputs;
- explicit non-goals;
- owned, protected, and immutable files;
- permitted and prohibited operations;
- acceptance criteria and validation commands;
- the required evidence and expected result schema.

Start from [`../../references/task-contract.md`](../../references/task-contract.md), save transient task instances under `.orchestration/antigravity/tasks/`, and invoke [`scripts/delegate.py`](scripts/delegate.py). Use `inspect` for read-only investigation, `implement` for explicitly owned edits, `validate` for bounded validation, and `review` for independent read-only review.

Every non-dry-run delegation must pass the bridge preflight before the real task is
sent to Gemini. Resolve the Git root from the installed delegate and pass it as the
explicit `cwd` of every subprocess. The installed Antigravity CLI selects its
workspace from the host process working directory and does not support a separate
workspace argument. Pass commands as argument lists with `shell=False`.

On Windows, use the repository's trusted non-AppContainer profile: require
`always-proceed`, disable Terminal Sandbox, keep non-workspace access disabled, and
launch the CLI with `--sandbox=false`. First prove that the current process token is
not elevated; never request elevation. Retain the targeted Git, `.git`, `sudo`, and
`runas` deny rules.

The preflight validates settings, Git-root identity, CLI version, authentication,
repository reads, one temporary create/read/delete cycle, and local
`git status --short --branch` and `python --version` commands. If any invariant
fails, stop on `BRIDGE_PREFLIGHT_FAILED` and do not continue the real task.

Repository files use normal workspace access. Do not add repository-relative
`read_file(...)` or `write_file(...)` entries: they are incompatible with sandbox
initialization in this Windows environment. Do not add wildcard command, file, or
unsandboxed or administrator grants.

When a task requires immutable files outside the checkout, stage only the required
inputs under an ignored repository-local input directory and record the original
path, byte size, and SHA-256. Never broaden filesystem permissions or overwrite the
external source. For large firmware images, prepare the manifest first and copy only
as part of an explicitly authorized implementation task.

Read only the compact structured result and final Git diff unless deeper evidence is required. When work is failed or incomplete, continue the same Antigravity conversation with a corrected bounded contract when practical. Keep the primary Codex response concise.

Original firmware images and irreplaceable evidence are immutable. Never authorize destructive Git operations, commit, push, or physical-device flashing. Physical flashing requires explicit user authorization and remains a Codex-level decision.
