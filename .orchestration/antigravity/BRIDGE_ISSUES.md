# CLI bridge issues

## 2026-08-04 — isolated checkout and rooted path matching

- Replaced primary-repository `git worktree add` with a disposable `git clone --no-local`; the worker no longer needs access to primary `.git/worktrees`.
- Files generated under allowed `tmp/` are recorded as runtime temporary paths and discarded with the checkout.
- Replaced suffix-style `PurePath.match` behavior with rooted, segment-aware POSIX glob matching. `candidates/**` now matches only the root `candidates/` tree.
- A no-elevation CLI smoke created the isolated checkout successfully, but the outer execution sandbox denied the CLI's own authenticated session/log access. The bridge now returns `BRIDGE_AUTH_FAILED` for that runtime condition; no source checkout or `.git/worktrees` entry changed.

| 时间 / run | 问题 | 证据与处理 |
|---|---|---|
| 20260801T143138Z-m8a-r4-boot-failure-inspect | 只读违约、额外 scratch | inspect 合同明确不写工作树，但 worker 生成 `scratch/vbmeta.img`、`scratch/vbmeta_system.img`、`scratch/vbmeta_vendor.img`；已删除，后续合同限定只写 `tmp/`。 |
| 20260801T151037Z-m8a-r5-no-hdmi-inspect | 认证 / 预检失败 | CLI 访问登录目录和 crash/log 目录被拒绝，且报告未登录；未通过提升权限绕过。 |
| 20260803T163916Z-m8a-r6-first-stage-inspect | 额外 scratch | 合同目标仅为 `tmp/r7-analysis.txt`，CLI 还写入 `tmp/unleash-repo-schema-v1-codeium-language-server.json`；路径仍在允许的 `tmp/` 内，已记录。 |
| 20260803T163916Z 首次启动 | 权限 / 沙箱 | sandbox 无法在主仓库 `.git/worktrees` 创建隔离 worktree；经显式批准以提升权限重试后成功，主工作树未变化。 |
| 20260803 r7 implement 预检 | 合同路径匹配缺陷 | `candidates/**` 被 `PurePath.match` 当作后缀匹配，误拦截 `configs/candidates/...` 与 `out/candidates/...`；返回 `BRIDGE_CONFIGURATION_FAILED`，未启动 worker。Sol 已直接接管 r7。 |

桥接问题不阻塞可逆候选；任何受保护路径写入或主工作树变更仍视为合同违例。
