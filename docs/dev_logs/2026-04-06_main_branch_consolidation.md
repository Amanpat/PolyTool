# 2026-04-06 — Main Branch Consolidation

## Objective

Safely consolidate the repo from multi-branch sprawl to a single `main`-only
workflow. The active working state on `feat/ws-clob-feed` (440 commits ahead of
old main) becomes the new `main`. All other branches and worktrees are cleaned up.
Docs updated to reflect the new policy.

## Pre-Consolidation State

| Item | Count / Value |
|------|--------------|
| Active branch | `feat/ws-clob-feed` at commit `16a53f4` |
| Old main commit | `7f85bd3` (440 commits behind feat/ws-clob-feed) |
| Remote main commit (at push time) | `dd5dc24` (PR merge, 427 commits behind) |
| Local branches (regular) | 14 (feat/ws-clob-feed, main, phase-1, phase-1B, simtrader, codex/tracka-adverse-selection-default-wiring, feat/moneyline-default-market-type, fix/category-coverage, roadmap1-closeout, roadmap2-trust-validation, roadmap3, roadmap4.6, roadmap5, verify/roadmap5-prereqs) |
| Local branches (worktree-agent) | 54 (worktree-agent-a*) |
| Worktrees | 55 total (main + 54 agent worktrees under .claude/worktrees/) |
| Remote branches | 13 (phase-1, phase-1A, phase-1B, simtrader, roadmap2-trust-validation, roadmap3, roadmap4, roadmap4.3, roadmap4.6, roadmap4_2_segment_analysis, roadmap5, feat/moneyline-default-market-type + origin/main) |
| Stashes | 4 (all referencing deleted branches) |
| Uncommitted changes | 299 files (.claude/ GSD framework updates -- excluded from commit) |

## Actions Taken

### 1. Safety Anchors (before any destructive operation)

Created annotated tag at `16a53f4` (feat/ws-clob-feed HEAD):

```
git tag -a "safety/pre-main-consolidation-20260406" -m "Safety snapshot before main-only consolidation. Source branch: feat/ws-clob-feed at 16a53f42cc2928b7bca06ca6dace05f2b4cff8c6"
```

Tag pushed to remote as backup:
```
git push origin safety/pre-main-consolidation-20260406
```

### 2. Worktree Cleanup

Removed all 54 agent worktrees from `.claude/worktrees/`. Two worktrees
(`agent-a82e9400`, `agent-afba9780`) failed with "Filename too long" on the
filesystem delete step but were successfully unregistered from git. Their
directory remnants were removed via PowerShell `Remove-Item -Recurse -Force`.

After cleanup: `git worktree list` shows only the main working directory.

### 3. Main Branch Update

```bash
git branch -f main HEAD     # pointed main at 16a53f4
git checkout main           # switched to main
```

### 4. Remote Push

Remote `origin/main` was at `dd5dc24` (a PR merge commit, 427 commits behind our
working state). Used `--force-with-lease` with the known remote commit hash to
safely overwrite:

```bash
git push --force-with-lease=main:dd5dc2462ad90dc5c395d499f63276b50f0fd2bb origin main
```

Result: `+ dd5dc24...16a53f4 main -> main (forced update)`

### 5. Local Branch Deletion

Deleted all local branches except `main`:

- Regular: feat/ws-clob-feed, phase-1, phase-1B, simtrader, codex/tracka-adverse-selection-default-wiring, feat/moneyline-default-market-type, fix/category-coverage, roadmap1-closeout, roadmap2-trust-validation, roadmap3, roadmap4.6, roadmap5, verify/roadmap5-prereqs
- All 54 worktree-agent-* branches

### 6. Remote Branch Deletion

Deleted remote branches: phase-1, phase-1A, phase-1B.

Branches roadmap2-trust-validation, roadmap3, roadmap4, roadmap4.3, roadmap4.6,
roadmap4_2_segment_analysis, roadmap5, feat/moneyline-default-market-type, and
simtrader were already absent from the remote when we ran `git fetch --prune`.
They were cleaned up by the prune operation.

### 7. Stash Clear

```bash
git stash clear
```

Dropped all 4 stashes (all referenced deleted branches, none contained
unrecoverable work).

## Post-Consolidation State

| Item | Value |
|------|-------|
| Current branch | `main` at `16a53f4` |
| origin/main | `16a53f4` (matches local) |
| Local branches | 1 (main only) |
| Remote branches | 1 (origin/main only) |
| Worktrees | 1 (main working directory) |
| Stashes | 0 |
| Safety tag | `safety/pre-main-consolidation-20260406` (local + remote) |

## Files Modified

- `CLAUDE.md` — branch policy updated from "Stay on phase-1" to "Single branch: main"
- `docs/CURRENT_STATE.md` — added main-only workflow note with safety tag reference

## Verification

### git branch -a

```
* main
  remotes/origin/HEAD -> origin/main
  remotes/origin/main
```

### python -m polytool --help

CLI loads successfully. No import errors. Output begins:

```
PolyTool - Polymarket analysis toolchain

Usage: polytool <command> [options]
       python -m polytool <command> [options]
```

## Notes

- The 299 uncommitted `.claude/` GSD framework changes were deliberately NOT
  committed — they are out of scope for this consolidation task.
- Historical references to `phase-1` in specs and old dev logs were left intact
  as historical records, not instructions.
- The safety tag is permanent — do NOT delete it.

## Codex Review

Tier: Skip (docs and git refs only, no code changes).
