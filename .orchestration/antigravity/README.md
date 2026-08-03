# Antigravity CLI bridge

The CLI is the only automated external worker. Codex Sol creates the contract, reviews the result and patch, and alone decides whether to apply a patch to the primary checkout.

```powershell
python .agents/skills/antigravity-worker/scripts/delegate.py `
  .orchestration/antigravity/contracts/<task>.json --mode inspect
```

Contracts are JSON and declare read paths, writable paths, artifact paths, protected paths, and approved commands. Each run uses a disposable worktree and `tmp/`; the primary checkout is never a CLI working directory. `implement` writes only the disposable worktree and returns a patch. Results are `TASK_COMPLETED`, `TASK_FAILED`, `WORKER_CONTRACT_VIOLATION`, `BRIDGE_AUTH_FAILED`, or `BRIDGE_CONFIGURATION_FAILED`.
