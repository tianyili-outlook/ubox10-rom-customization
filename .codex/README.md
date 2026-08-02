# Codex multi-agent workflow

## Architecture

- Primary thread: GPT-5.6 Sol, with Max selected in the Codex desktop model picker.
- Child agents: GPT-5.6 Terra with high reasoning.
- Concurrency: at most four child agents may remain open at once, excluding the primary thread.
- Runtime availability: GPT-5.6 Luna is not currently available; the role names and workflow remain unchanged.

## Roles

- `ubox_explorer`: read-only investigation of repository code, firmware, evidence, documentation, dependencies, and execution paths.
- `ubox_implementer`: narrowly scoped changes to scripts, product configuration, overlays, documentation, and image assembly.
- `ubox_validator`: build checks, partition audits, ELF and dependency checks, image inspection, and targeted smoke tests.
- `ubox_reviewer`: independent read-only review for architecture, regressions, boot risk, compatibility, documentation consistency, and missing validation.

## Recommended workflow

Investigate → plan → assign non-overlapping implementation → validate → independently review → targeted correction → Sol final integration.

Sol owns architecture, task decomposition, file-ownership boundaries, integration, conflict resolution, final diff inspection, and acceptance. Worker reports are evidence for Sol to verify, not automatic proof of completion.

## Reload after configuration changes

Start a new Codex thread or reload the project after changing these files so Codex discovers the updated project configuration and custom agents.

## Smoke-test prompt

> Spawn one `ubox_explorer` subagent in read-only mode. Inspect `docs/FILE_MAP.md` and report the current M8 phase, the next documented action, and the exact source paths. Do not modify any files.

## Parallel implementation example

Sol may spawn two `ubox_implementer` instances only after assigning explicit, non-overlapping ownership. For example:

> Spawn two `ubox_implementer` subagents. Implementer A owns only `scripts/example-a.ps1` and `tests/test_example_a.py`. Implementer B owns only `docs/example-b.md`. Neither agent may edit files owned by the other; both must report validation and return any scope expansion to Sol.
