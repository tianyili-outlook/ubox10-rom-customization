# Antigravity orchestration bridge

This directory holds transient task contracts and run evidence for the project-local `antigravity-worker` skill. Codex remains the orchestrator and final reviewer; Antigravity performs bounded routine execution.

## Verified defaults

- Antigravity CLI: `agy` 1.1.9 or compatible
- Model: `gemini-3.6-flash-high`
- Effort: `high`
- Output: JSON constrained by the project result schema
- Write concurrency: one worker per checkout

The delegate resolves `agy` from `PATH`, then checks the standard Windows installation at `%LOCALAPPDATA%\agy\bin\agy.exe`. It never adds `--dangerously-skip-permissions`.

The trusted Windows CLI profile uses `always-proceed`, keeps artifact review on `always-proceed`, disables the incompatible AppContainer Terminal Sandbox, disables non-workspace access, and retains explicit protective deny rules. Repository files use normal workspace access; do not add granular repository-relative `read_file(...)` or `write_file(...)` entries. Deny rules take precedence. Do not add wildcard, unsandboxed, elevation, or administrator grants.

The launcher resolves the real Git root from its own installed path and supplies it as the explicit operating-system working directory for every subprocess. Antigravity selects the active workspace from that process working directory; the installed CLI has no separate workspace-directory option. Commands are argument lists executed with `shell=False`.

A non-dry-run invocation first validates the effective settings, non-elevated Windows token, Git-root identity, CLI version, authentication, repository reads, safe local commands, and one temporary create/read/delete cycle. Failure returns `BRIDGE_PREFLIGHT_FAILED` with the exact check, command, path or rule and does not invoke the requested worker task. Headless workers are launched with `--sandbox=false`.

If the launching process has an elevated Administrator token, the bridge stops before invoking Antigravity and instructs the user to restart Codex normally.

## Workflow

1. Copy `.agents/references/task-contract.md` into `tasks/` and reduce it to one bounded task.
2. Verify the baseline, paths, ownership, non-goals, protected files, acceptance criteria, and commands.
3. Dry-run the invocation:

   ```powershell
   python .agents/skills/antigravity-worker/scripts/delegate.py .orchestration/antigravity/tasks/example.md --mode inspect --dry-run
   ```

   To test only the bridge and its single smoke contract, use `--preflight-only`.

4. Execute it:

   ```powershell
   python .agents/skills/antigravity-worker/scripts/delegate.py .orchestration/antigravity/tasks/example.md --mode inspect
   ```

5. Read the printed compact summary and the timestamped `runs/` result. Inspect the actual Git diff before accepting work.
6. For correction, reuse the reported conversation ID with `--conversation-id <id>` and a corrected bounded task.

`inspect` and `review` are strictly read-only. `validate` is read-only by preference and may create only contract-approved temporary outputs. `implement` may edit only explicitly owned files. Original firmware and irreplaceable device evidence are immutable in every mode. No mode authorizes destructive Git operations, commit, push, or physical flashing.

The `tasks/`, `runs/`, and `conversations/` contents are ignored because they may contain transient prompts, responses, logs, conversation state, and token-usage records. Their `.gitkeep` files retain the directory layout; stable policy and schemas remain tracked.

## 已知桥接问题（2026-08-01）

这些问题单独记录，不阻塞可逆的 UBOX10 候选主线：

| 问题 | 已见证据 | 状态 |
|---|---|---|
| 只读 worker 修改工作树 | `20260801T143138Z-20260801-m8a-r4-boot-failure-inspect-5f768373` 的 inspect 合同明确禁止写入，但 worker 创建了 `scratch/vbmeta.img`、`scratch/vbmeta_system.img`、`scratch/vbmeta_vendor.img` | 开放；主线程已核对并删除当次多余文件 |
| 生成多余 scratch 文件 | r2/r3 worker 的结构化命令记录包含 `scratch/` 解包脚本和中间镜像；这些内容超出只读或最小证据合同 | 开放；后续合同继续明确禁止 scratch，主线程检查实际工作树 |
| 登录目录或预检访问失败 | `20260801T144028Z-20260801-m8a-r5-avb-bypass-implement-5b93b077` 与 `20260801T151037Z-20260801-m8a-r5-no-hdmi-inspect-eca6e2e5` 均在预检访问 `%USERPROFILE%\.gemini\antigravity-cli` 时出现 `Access is denied`，并同时报告未登录 | 开放；不提权、不绕过预检，主线本地继续 |
| 权限、沙箱和合同违例 | 多个 smoke/implement 运行出现 `headless permission was auto-denied`；CLI 还尝试访问受限 Playwright/日志/崩溃目录。成功的 inspect worker 仍执行了合同禁止的写入与解包 | 开放；保留精确权限白名单和 deny 规则，不授予 wildcard、unsandboxed 或管理员权限 |
