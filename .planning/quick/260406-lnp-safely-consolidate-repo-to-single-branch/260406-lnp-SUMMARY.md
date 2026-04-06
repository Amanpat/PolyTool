---
phase: quick-260406-lnp
plan: 01
subsystem: git / repo hygiene
tags: [git, branch-consolidation, cleanup, docs]
dependency_graph:
  requires: []
  provides: [single-branch-main-workflow, safety-tag]
  affects: [CLAUDE.md, docs/CURRENT_STATE.md]
tech_stack:
  added: []
  patterns: [main-only branch workflow]
key_files:
  created:
    - docs/dev_logs/2026-04-06_main_branch_consolidation.md
  modified:
    - claude.md (tracked as claude.md in git, displayed as CLAUDE.md on disk)
    - docs/CURRENT_STATE.md
decisions:
  - Used --force-with-lease with explicit remote hash after git fetch to safely overwrite diverged remote main
  - CLAUDE.md tracked as claude.md (lowercase) in git due to Windows case-insensitive FS -- staged as claude.md
  - Two worktrees (agent-a82e9400, agent-afba9780) had Windows Filename Too Long errors on FS delete but were unregistered from git successfully; removed via PowerShell
metrics:
  duration: 14m 37s
  completed: 2026-04-06T19:53:09Z
  tasks_completed: 3
  files_created: 1
  files_modified: 2
---

# Phase quick-260406-lnp Plan 01: Main Branch Consolidation Summary

**One-liner:** Consolidated 14 regular + 54 worktree-agent local branches and 13 remote branches into a single `main` branch; safety tag created and pushed; CLAUDE.md and CURRENT_STATE.md updated to reflect main-only workflow.

## Objective Achieved

The repo now operates on a single `main` branch. The full working state from `feat/ws-clob-feed` (440 commits ahead of old main) is now `main`. All obsolete branches, worktrees, and stashes have been cleaned up. Safety tag `safety/pre-main-consolidation-20260406` is preserved locally and on remote.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Safety anchors + worktree cleanup + consolidate main | (git refs only) | git tags, branches, worktrees |
| 2+3 | Update docs + final verification + commit | `8cc44d7` | claude.md, docs/CURRENT_STATE.md, docs/dev_logs/2026-04-06_main_branch_consolidation.md |

## Pre/Post State

| Item | Before | After |
|------|--------|-------|
| Local branches | 68 (14 regular + 54 worktree-agent) | 1 (main) |
| Remote branches | 13 + origin/main | 1 (origin/main) |
| Worktrees | 55 (main + 54 agent) | 1 (main) |
| Stashes | 4 | 0 |
| Safety tag | none | safety/pre-main-consolidation-20260406 |
| CLAUDE.md branch policy | "Stay on phase-1 branch" | "Single branch: main" |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] CLAUDE.md tracked as claude.md (lowercase) in git**
- **Found during:** Task 2 (staging)
- **Issue:** On Windows case-insensitive filesystem, the file `CLAUDE.md` on disk is tracked as `claude.md` in the git index. `git add CLAUDE.md` silently did nothing. `git diff CLAUDE.md` showed no output. Required discovering `git ls-files | grep -i "^claude"` to find the lowercase entry and staging via `git add claude.md`.
- **Fix:** Staged `claude.md` (lowercase) instead of `CLAUDE.md`.
- **Files modified:** claude.md (same content, just correct case reference for git)
- **Commit:** 8cc44d7

**2. [Rule 3 - Blocking] Remote main had moved since planning**
- **Found during:** Task 1 Step 4 (push)
- **Issue:** Remote `origin/main` had moved to `dd5dc24` (a PR merge commit) since the planner ran. The planner had recorded it at `7f85bd3`. `--force-with-lease` without specifying the remote hash rejected the push.
- **Fix:** Ran `git fetch origin main` to update tracking info, then used `--force-with-lease=main:dd5dc24...` with the explicit known remote hash.
- **Outcome:** Push succeeded: `+ dd5dc24...16a53f4 main -> main (forced update)`

**3. [Rule 1 - Bug] Two worktrees failed Windows Filename Too Long on FS delete**
- **Found during:** Task 1 Step 2 (worktree removal)
- **Issue:** `agent-a82e9400` and `agent-afba9780` failed `git worktree remove --force` with "Filename too long" during the filesystem delete step. However, git did unregister them from the worktree list.
- **Fix:** Used `powershell Remove-Item -Recurse -Force` to clean up the filesystem remnants. Both directories removed successfully.
- **git worktree list:** Clean after fix.

## Verification Results

```
LOCAL BRANCH COUNT: 1 (main)
REMOTE BRANCH COUNT: 1 (origin/main)
SAFETY TAG COUNT: 1 (safety/pre-main-consolidation-20260406)
HEAD: 8cc44d7c24426f3c06ac4ff509ed793b3004a78c
MAIN: 8cc44d7c24426f3c06ac4ff509ed793b3004a78c (match)

python -m polytool --help: PASS
git worktree list: main working dir only
git stash list: (empty)
grep "Single branch" CLAUDE.md: found at line 270
grep "main-only" docs/CURRENT_STATE.md: found at line 12
```

## Known Stubs

None. This plan only modified git refs and documentation.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes introduced.

## Self-Check: PASSED

- [x] docs/dev_logs/2026-04-06_main_branch_consolidation.md exists
- [x] claude.md branch policy updated (Single branch: main)
- [x] docs/CURRENT_STATE.md has main-only workflow note
- [x] Commit 8cc44d7 exists: `git log --oneline | grep 8cc44d7` -> confirmed
- [x] Safety tag safety/pre-main-consolidation-20260406 exists locally and on remote
- [x] python -m polytool --help passes
- [x] Only `main` local branch, only `origin/main` remote
