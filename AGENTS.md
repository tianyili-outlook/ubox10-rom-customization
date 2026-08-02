## Codex multi-agent operating model

- The primary thread is responsible for architecture, task decomposition, integration, conflict resolution, and final acceptance.
- Routine exploration, implementation, testing, and review should be delegated to the relevant custom agents.
- No more than four subagents may remain concurrently open.
- Parallel implementation requires explicit and non-overlapping file ownership.
- Exploration should normally precede implementation.
- Worker reports are evidence, not automatic proof of completion.
- Sol must inspect the final diff and validation evidence itself.
- Original firmware images and irreplaceable device evidence must remain immutable.
- No agent may flash the physical UBOX10 unless the user explicitly requests a flashing step.
- Candidate testing should remain practical and experience-oriented rather than certification-level, consistent with this personal-interest project.
- The project goal remains maximizing the available H618 hardware while moving toward a clean, remote-friendly, modern Android TV experience.
- Existing boot, kernel, vendor, vendor_dlkm, TEE, DRM, media, graphics, wireless, and partition dependencies must not be casually removed.

## External Antigravity execution model

- Codex is the project orchestrator and final reviewer; routine execution should use the `antigravity-worker` skill.
- Native Codex subagents should not be used unless the user explicitly requests them.
- Antigravity runs use Gemini 3.6 Flash with high reasoning effort by default.
- Use one write worker at a time. Parallel writers require isolated Git worktrees with non-overlapping ownership.
- Sol must inspect the actual Git diff and validation evidence rather than trust the worker report.
- Original firmware images and irreplaceable evidence remain immutable.
- Physical flashing always requires explicit user authorization.
- The worker must return concise structured evidence so the primary model consumes minimal context and tokens.

## UBOX10 execution philosophy

Use the `ubox-fast-track` skill for M8 implementation, candidate construction, testing, and fault diagnosis. This is a personal-interest project optimized for a usable, recoverable Android TV system and rapid practical progress, not production-grade process completeness. For reversible work, build and test after minimal high-value checks, then diagnose the first reproducible failure. Increase caution only for brick risk, loss of recovery, security-material damage, destruction of irreplaceable evidence, or changes that make failure attribution impractical. Keep active documentation concise and limited to current status, essential artifacts, results, and the next action.
