---
name: antigravity-worker
description: Delegate bounded UBOX10 inspection, implementation, validation, and review to the Antigravity CLI using disposable worktrees and machine-checked JSON contracts. Use for CLI-only external worker tasks that must leave the primary checkout unchanged until Codex Sol reviews a patch.
---

# Antigravity CLI worker

Use `scripts/delegate.py` as the only automated external worker. Codex Sol owns the contract, checks the returned patch and local acceptance result, and decides whether to apply it to the primary checkout.

Create a version-1 JSON contract under `.orchestration/antigravity/contracts/`. List exact repository-relative read paths, writable paths, artifact paths, protected paths, and approved command token arrays. Do not use absolute paths, traversal, or broad wildcards.

The delegate invokes only `agy`; it never reads the Antigravity login directory and never falls back to the SDK or another backend. It caches CLI version and one CLI authentication probe for the session.

Every mode runs in a temporary Git clone outside the primary repository, so the worker never creates entries under the primary `.git/worktrees`. `TEMP`, `TMP`, and `TMPDIR` point to that checkout's `tmp/`. Read-only modes may write only under `tmp/`; extra runtime files there are recorded and discarded. Implement mode returns a patch and artifact list from the disposable checkout; it never applies changes to the primary checkout.

Trust the bridge's post-run manifest and Git diff, not worker self-report. A changed protected or unowned path is `WORKER_CONTRACT_VIOLATION`.
