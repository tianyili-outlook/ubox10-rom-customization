# Antigravity bridge

This ignored workspace stores bounded task contracts and run evidence for `.agents/skills/antigravity-worker/`. Codex remains the orchestrator and final reviewer.

```powershell
python .agents/skills/antigravity-worker/scripts/delegate.py `
  .orchestration/antigravity/tasks/<task>.md --mode inspect --dry-run

python .agents/skills/antigravity-worker/scripts/delegate.py `
  .orchestration/antigravity/tasks/<task>.md --mode inspect
```

Modes are `inspect`, `implement`, `validate`, and `review`. Non-dry runs perform the bridge preflight first. Use one write worker per checkout, give it explicit file ownership, and inspect the resulting Git diff. No mode authorizes commit, push, destructive Git operations, credential access, or physical flashing.
