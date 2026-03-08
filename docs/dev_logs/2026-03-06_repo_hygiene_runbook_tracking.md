# Repo Hygiene: Stage 1 Runbook Tracking

Date: 2026-03-06

## Scope

Clean up repo hygiene after the documentation reconciliation work by deciding
whether `docs/runbooks/LIVE_DEPLOYMENT_STAGE1.md` should be part of the repo and
making the tracking state intentional without modifying Python code.

## Git Status Before

Command run:

```text
git status --short --branch
```

Relevant before-state:

```text
## simtrader...origin/simtrader [ahead 3]
?? docs/runbooks/
```

Notes:

- The worktree already contained many unrelated modified and untracked files
  before this task.
- The repo was treating `docs/runbooks/` as an untracked directory because
  `docs/runbooks/LIVE_DEPLOYMENT_STAGE1.md` had not been added.

## File Decision

Decision: keep `docs/runbooks/LIVE_DEPLOYMENT_STAGE1.md` in the repo and track
it.

Rationale:

- It is already referenced from `docs/INDEX.md` as "Stage 1 Live Deployment."
- It is listed in `docs/CURRENT_STATE.md` as an existing Stage 1 operator
  runbook.
- It is listed in `docs/ROADMAP.md` as a planned/current docs artifact.
- It is linked from `docs/features/FEATURE-trackA-live-clob-wiring.md`.
- The content matches the canonical validation pipeline already reconciled in
  the docs:
  `Gate 1 replay -> Gate 2 sweep -> Gate 3 shadow -> Gate 4 dry run -> Stage 0 72h paper-live -> Stage 1 live capital`.

## File Changes Made

- No content change was required in `docs/runbooks/LIVE_DEPLOYMENT_STAGE1.md`.
- Added this log file:
  `docs/dev_logs/2026-03-06_repo_hygiene_runbook_tracking.md`.
- Planned tracking change:
  add `docs/runbooks/LIVE_DEPLOYMENT_STAGE1.md` to git so it is no longer a
  stray untracked runbook.

## Git Status After

Command run:

```text
git status --short --branch
```

Relevant after-state:

```text
## simtrader...origin/simtrader [ahead 3]
A  docs/dev_logs/2026-03-06_repo_hygiene_runbook_tracking.md
A  docs/runbooks/LIVE_DEPLOYMENT_STAGE1.md
```

## Final Repo Hygiene State

- `docs/runbooks/LIVE_DEPLOYMENT_STAGE1.md` is now an intentional staged repo
  document, not an accidental untracked directory artifact.
- `git status` no longer shows `?? docs/runbooks/`.
- No Python code was modified.
- Unrelated pre-existing working tree changes remain outside the scope of this
  cleanup.
