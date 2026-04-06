---
phase: quick-260406-lnp
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - CLAUDE.md
  - docs/CURRENT_STATE.md
  - docs/dev_logs/2026-04-06_main_branch_consolidation.md
autonomous: false
must_haves:
  truths:
    - "Local main branch points to the same commit as feat/ws-clob-feed HEAD (16a53f4)"
    - "origin/main matches local main after push"
    - "All obsolete local branches are deleted (only main remains)"
    - "All obsolete remote branches are deleted (only origin/main remains)"
    - "Safety tag exists preserving pre-consolidation state"
    - "CLAUDE.md branch policy says main-only, not phase-1"
    - "No secrets, .env files, or ignored artifacts were committed"
    - "python -m polytool --help still works"
  artifacts:
    - path: "CLAUDE.md"
      provides: "Updated branch policy (main-only)"
      contains: "single branch `main`"
    - path: "docs/dev_logs/2026-04-06_main_branch_consolidation.md"
      provides: "Dev log of consolidation"
    - path: "docs/CURRENT_STATE.md"
      provides: "Updated workflow note"
  key_links:
    - from: "git tag safety/pre-main-consolidation-*"
      to: "commit 16a53f4"
      via: "annotated tag"
      pattern: "safety/pre-main-consolidation"
---

<objective>
Safely consolidate the repo from its current multi-branch state (feat/ws-clob-feed as active working branch, 440 commits ahead of main, ~14 local branches, ~50 worktrees, ~13 remote branches) to a single-branch main-only workflow.

Purpose: Eliminate branch sprawl that accumulated over months of development. The active working state on feat/ws-clob-feed becomes main. All other branches and worktrees are cleaned up. Docs are updated to reflect the new main-only policy.

Output: main branch = current working state, safety tag preserved, all other branches/worktrees removed, CLAUDE.md + docs updated, dev log written.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@CLAUDE.md
@docs/CURRENT_STATE.md

## Current Repo State (discovered during planning)

- **Current branch:** `feat/ws-clob-feed` at commit `16a53f4`
- **main branch:** at commit `7f85bd3` (440 commits behind feat/ws-clob-feed)
- **Merge base:** `7f85bd3` (main IS the merge base -- feat/ws-clob-feed is a linear descendant)
- **Remote:** `origin` -> `https://github.com/Amanpat/PolyTool.git`
- **Uncommitted changes:** 299 files, almost entirely `.claude/` GSD framework updates (agent files, workflow files, hooks, worktree dirs). These are GSD tooling updates, NOT project source code.
- **Stashes:** 4 stashes (all on old branches -- can be dropped after consolidation)

### Local branches (14 + ~50 worktree branches):
- `feat/ws-clob-feed` (HEAD, active)
- `main`, `phase-1`, `phase-1B`, `simtrader`
- `codex/tracka-adverse-selection-default-wiring`
- `feat/moneyline-default-market-type`, `fix/category-coverage`
- `roadmap1-closeout`, `roadmap2-trust-validation`, `roadmap3`, `roadmap4.6`, `roadmap5`
- `verify/roadmap5-prereqs`
- ~50 `worktree-agent-*` branches

### Remote branches (13):
- `origin/main`, `origin/phase-1`, `origin/phase-1A`, `origin/phase-1B`
- `origin/simtrader`, `origin/roadmap2-trust-validation`, `origin/roadmap3`
- `origin/roadmap4`, `origin/roadmap4.3`, `origin/roadmap4.6`, `origin/roadmap4_2_segment_analysis`
- `origin/roadmap5`, `origin/feat/moneyline-default-market-type`

### Docs with outdated branch policy:
- `CLAUDE.md` lines 268-271: "Stay on the `phase-1` branch until Phase 1 is complete."
- `docs/CURRENT_STATE.md` line 384: reference to `phase-1` branch (historical context, keep as-is)
- Various specs/dev_logs mention `phase-1` branch (historical -- do not rewrite history)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Safety anchors + worktree cleanup + consolidate main</name>
  <files>git refs only (no file modifications)</files>
  <action>
This task handles all git ref manipulation. Execute steps in exact order:

**Step 1 — Safety anchors (before any destructive operation):**
```bash
# Record the exact commit we are preserving
rtk git log --oneline -1

# Create annotated safety tag at current HEAD
git tag -a "safety/pre-main-consolidation-20260406" -m "Safety snapshot before main-only consolidation. Source branch: feat/ws-clob-feed at $(git rev-parse HEAD)"

# Verify tag exists
git tag -l "safety/pre-main-consolidation*"
```

**Step 2 — Remove all worktrees:**
The repo has ~50 worktrees under `.claude/worktrees/`. They must be removed before their branches can be deleted.
```bash
# Remove all worktrees (force because they may have changes)
git worktree list --porcelain | grep "^worktree " | grep -v "$(pwd)$" | sed 's/^worktree //' | while read wt; do
  git worktree remove --force "$wt" 2>/dev/null || echo "WARN: could not remove $wt"
done

# Verify only main worktree remains
git worktree list
```

If the loop approach fails on Windows, fall back to removing each worktree individually:
```bash
git worktree remove --force .claude/worktrees/agent-a000a16c
# ... repeat for each worktree shown in `git worktree list`
```

**Step 3 — Move main to current HEAD:**
```bash
# We are on feat/ws-clob-feed. Update main to point here.
git branch -f main HEAD

# Switch to main
git checkout main

# Verify main is at the right commit
rtk git log --oneline -1
```

**Step 4 — Push main to remote:**
```bash
# Try normal push first
rtk git push -u origin main

# If rejected (diverged history), use force-with-lease:
# rtk git push --force-with-lease -u origin main
```
If push fails for permissions or branch protection, STOP and report to operator.

**Step 5 — Push the safety tag:**
```bash
rtk git push origin "safety/pre-main-consolidation-20260406"
```

**Step 6 — Delete all obsolete local branches:**
Delete every local branch except `main`. This includes all worktree-agent-* branches, feat/*, phase-*, roadmap*, simtrader, codex/*, fix/*, verify/*.
```bash
# List all local branches except main, then delete
git branch | grep -v "^\* main$" | grep -v "^  main$" | xargs git branch -D
```

If xargs approach fails on Windows, delete in batches:
```bash
git branch -D feat/ws-clob-feed phase-1 phase-1B simtrader
git branch -D codex/tracka-adverse-selection-default-wiring feat/moneyline-default-market-type fix/category-coverage
git branch -D roadmap1-closeout roadmap2-trust-validation roadmap3 roadmap4.6 roadmap5 verify/roadmap5-prereqs
# Then delete all worktree-agent-* branches in a loop or batch
git branch | grep "worktree-agent-" | xargs git branch -D
```

**Step 7 — Delete all obsolete remote branches:**
```bash
# Delete each remote branch except origin/main
git push origin --delete phase-1 phase-1A phase-1B simtrader
git push origin --delete roadmap2-trust-validation roadmap3 roadmap4 roadmap4.3 roadmap4.6
git push origin --delete roadmap4_2_segment_analysis roadmap5 feat/moneyline-default-market-type
```

**Step 8 — Drop stale stashes (optional, low-risk):**
All 4 stashes reference branches that no longer exist. Drop them:
```bash
git stash clear
```

**Step 9 — Verify clean state:**
```bash
rtk git branch -vv --all
git worktree list
git stash list
git tag -l "safety/*"
```
Expected: only `main` local branch, only `origin/main` remote, no worktrees except main dir, no stashes, safety tag present.
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && git branch | wc -l | tr -d ' ' && echo "should be 1" && git branch -r | grep -v HEAD | wc -l | tr -d ' ' && echo "should be 1" && git tag -l "safety/pre-main-consolidation*" | wc -l | tr -d ' ' && echo "should be 1" && git rev-parse HEAD && git rev-parse main && echo "should match"</automated>
  </verify>
  <done>
    - Local repo has exactly one branch: main
    - Remote has exactly one branch: origin/main
    - Safety tag safety/pre-main-consolidation-20260406 exists locally and on remote
    - All worktrees removed
    - Stashes cleared
    - HEAD is on main at the former feat/ws-clob-feed tip
  </done>
</task>

<task type="auto">
  <name>Task 2: Update docs to reflect main-only workflow + dev log</name>
  <files>CLAUDE.md, docs/CURRENT_STATE.md, docs/dev_logs/2026-04-06_main_branch_consolidation.md</files>
  <action>
**CLAUDE.md — Update branch policy (lines 268-271):**

Replace:
```markdown
### Branch policy

- Stay on the `phase-1` branch until Phase 1 is complete.
- Do not create new branches unless the user explicitly changes this rule.
```

With:
```markdown
### Branch policy

- Single branch: `main`. Commit and push directly to `main`.
- Do not create routine feature branches unless the operator explicitly requests one.
- Historical note: prior to 2026-04-06 the repo used long-lived feature branches
  (phase-1, simtrader, roadmap*, feat/*). All were consolidated into main.
```

Do NOT change any other part of CLAUDE.md. Do NOT touch the `.env*` or secrets sections.

**docs/CURRENT_STATE.md — Add workflow note:**

Find the top-level section that describes current state (near the top of the file). Add a brief bullet or paragraph:
```markdown
- **Branch workflow:** main-only as of 2026-04-06. All prior feature branches
  (feat/ws-clob-feed, phase-1, simtrader, roadmap*, etc.) consolidated into main.
  Safety tag: `safety/pre-main-consolidation-20260406`.
```

Do NOT rewrite historical references to `phase-1` in the rest of CURRENT_STATE.md or in specs/dev_logs. Those are historical records, not instructions.

**docs/dev_logs/2026-04-06_main_branch_consolidation.md — Create dev log:**

Write a dev log with:
- Date, slug, objective
- Pre-consolidation state: branch count, worktree count, commit delta, stash count
- Actions taken: safety tag SHA, branches deleted (list), remote branches deleted (list), worktrees removed
- Post-consolidation state: single branch main, remote updated, safety tag preserved
- Files modified: CLAUDE.md, docs/CURRENT_STATE.md
- Verification: `python -m polytool --help` result, `git branch -a` result
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && grep -c "Single branch" CLAUDE.md && grep -c "main-only" docs/CURRENT_STATE.md && test -f docs/dev_logs/2026-04-06_main_branch_consolidation.md && echo "all docs present"</automated>
  </verify>
  <done>
    - CLAUDE.md branch policy section says "Single branch: main" (no mention of phase-1 as current policy)
    - docs/CURRENT_STATE.md has main-only workflow note with safety tag reference
    - Dev log exists at docs/dev_logs/2026-04-06_main_branch_consolidation.md with full before/after record
    - No historical references in specs or old dev logs were altered
  </done>
</task>

<task type="auto">
  <name>Task 3: Final verification + commit</name>
  <files>CLAUDE.md, docs/CURRENT_STATE.md, docs/dev_logs/2026-04-06_main_branch_consolidation.md</files>
  <action>
**Step 1 — Smoke test the repo:**
```bash
python -m polytool --help
```
Must succeed (CLI loads, no import errors). Record the output.

**Step 2 — Review what will be committed:**
```bash
rtk git status
rtk git diff --stat
```

Ensure ONLY these files are staged:
- CLAUDE.md (branch policy update)
- docs/CURRENT_STATE.md (workflow note)
- docs/dev_logs/2026-04-06_main_branch_consolidation.md (new dev log)

Do NOT stage any `.env*`, secrets, `.claude/worktrees/*`, or ignored files.
The ~299 uncommitted `.claude/` GSD framework changes are OUTSIDE this task's scope.
Only stage the three doc files listed above.

**Step 3 — Commit and push:**
```bash
rtk git add CLAUDE.md docs/CURRENT_STATE.md docs/dev_logs/2026-04-06_main_branch_consolidation.md
rtk git commit -m "repo: consolidate workflow to main-only branch

- Updated CLAUDE.md branch policy from phase-1 to main-only
- Added main-only workflow note to CURRENT_STATE.md
- Safety tag: safety/pre-main-consolidation-20260406
- Deleted all obsolete local/remote branches and worktrees"

rtk git push origin main
```

**Step 4 — Final state verification:**
```bash
rtk git branch -vv --all
rtk git log --oneline -3
git tag -l "safety/*"
python -m polytool --help
```

Expected: on main, pushed, safety tag visible, CLI works.
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && git rev-parse --abbrev-ref HEAD | grep -x "main" && git log --oneline -1 | grep -q "consolidate" && python -m polytool --help > /dev/null 2>&1 && echo "PASS"</automated>
  </verify>
  <done>
    - On main branch with doc changes committed and pushed
    - python -m polytool --help succeeds
    - git log shows consolidation commit as most recent
    - No secrets or ignored files were committed
    - Safety tag still present
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| local -> remote | Force-push to origin/main changes shared history |
| gitignore boundary | Risk of staging secrets or runtime artifacts |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-lnp-01 | Tampering | git history | mitigate | Safety tag created before any destructive operation; --force-with-lease (not --force) prevents overwriting unknown remote changes |
| T-lnp-02 | Information Disclosure | .env/secrets | mitigate | Explicit instruction to NOT stage .env*, ignored files, or secrets; only stage 3 named doc files |
| T-lnp-03 | Denial of Service | branch deletion | mitigate | Safety tag preserves all commits reachable from feat/ws-clob-feed; tag pushed to remote as second backup |
</threat_model>

<verification>
1. `git branch` shows only `main`
2. `git branch -r` shows only `origin/HEAD -> origin/main` and `origin/main`
3. `git tag -l "safety/*"` shows the safety tag
4. `git worktree list` shows only the main working directory
5. `grep "Single branch" CLAUDE.md` finds the updated policy
6. `grep "main-only" docs/CURRENT_STATE.md` finds the workflow note
7. `python -m polytool --help` succeeds
8. `git log --oneline -1` shows the consolidation commit
</verification>

<success_criteria>
- main branch is the sole branch, pointing to the former feat/ws-clob-feed HEAD
- origin/main updated to match
- All obsolete branches (local and remote) deleted
- All worktrees removed
- Safety tag exists locally and on remote
- CLAUDE.md branch policy updated to main-only
- docs/CURRENT_STATE.md has workflow consolidation note
- Dev log written at docs/dev_logs/2026-04-06_main_branch_consolidation.md
- python -m polytool --help passes
- No secrets, .env files, or ignored artifacts committed
</success_criteria>

<output>
After completion, create `.planning/quick/260406-lnp-safely-consolidate-repo-to-single-branch/260406-lnp-SUMMARY.md`
</output>
