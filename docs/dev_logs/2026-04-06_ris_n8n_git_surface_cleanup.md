# RIS n8n Git Surface Cleanup -- 2026-04-06

**Quick task:** quick-260406-nbe
**Branch:** main

## Purpose

Resolve the three categories of git-surface blockers that Codex flagged during Phase N4
sign-off review. All changes in this commit were already on disk from prior sessions --
this task stages, commits, and documents them.

## Blockers Found and Actions Taken

### A. `workflows/n8n/*` -- 9 tracked deletions (unstaged)

| File | Action | Why Safe |
|------|--------|----------|
| workflows/n8n/README.md | Staged deletion | Orphaned v2 dir, deleted by quick-260406-mno |
| workflows/n8n/ris-academic-ingestion.json | Staged deletion | Same -- wrong container name |
| workflows/n8n/ris-blog-ingestion.json | Staged deletion | Same |
| workflows/n8n/ris-github-ingestion.json | Staged deletion | Same |
| workflows/n8n/ris-health-monitor.json | Staged deletion | Same |
| workflows/n8n/ris-manual-ingest.json | Staged deletion | Same |
| workflows/n8n/ris-reddit-ingestion.json | Staged deletion | Same |
| workflows/n8n/ris-weekly-digest.json | Staged deletion | Same |
| workflows/n8n/ris-youtube-ingestion.json | Staged deletion | Same |

Canonical location: `infra/n8n/workflows/` (per ADR-0013).
Smoke script already asserts absence: `scripts/smoke_ris_n8n.py:189`.

**Reference repair:** Added SUPERSEDED header to
`docs/dev_logs/2026-04-05_n8n-workflows.md` (after header, before `## What`) which
previously claimed `workflows/n8n/` was the canonical location. No other live references found.

### B. `claude.md` -- modified (unstaged)

| File | Action | Why Safe |
|------|--------|----------|
| claude.md (line 38) | Staged modification | Intentional N4 n8n pilot qualification (quick-260406-mnu) |
| claude.md (line 116) | Staged modification | Same session, APScheduler default + pilot note |

Note: Git tracks as lowercase `claude.md` (original commit case). On-disk file is
`CLAUDE.md`. This is a pre-existing Windows case-insensitive FS artifact. NOT fixed
in this task -- renaming via git on case-insensitive FS is fragile and out of scope.

### C. `.planning/quick/26040*` -- 8 untracked PLAN.md files (8 files)

The SUMMARY.md files for these 8 directories were already committed in prior sessions.
Only the PLAN.md files were never tracked.

| Directory | Contents Added | Action | Why Safe |
|-----------|----------------|--------|----------|
| 260401-o1q-... | PLAN.md | Tracked (git add) | Follows existing convention |
| 260402-rm1-... | PLAN.md | Tracked (git add) | Same |
| 260404-rtv-... | 260404-rtv-PLAN.md | Tracked (git add) | Same |
| 260404-sb4-... | 260404-sb4-PLAN.md | Tracked (git add) | Same |
| 260404-t5l-... | 260404-t5l-PLAN.md | Tracked (git add) | Same |
| 260404-uav-... | PLAN.md | Tracked (git add) | Same |
| 260405-jyv-... | 260405-jyv-PLAN.md | Tracked (git add) | Same |
| 260405-kpg-... | 260405-kpg-PLAN.md | Tracked (git add) | Same |

50+ other `.planning/quick/` directories are already tracked. These 8 PLAN.md files
were simply never git-added after their sessions completed.

## Reference Search for `workflows/n8n`

Searched all committed files (excluding `.planning/`, `.claude/`, `.claude/worktrees/`)
for references to `workflows/n8n/`:

| File | Line | Type | Action |
|------|------|------|--------|
| scripts/smoke_ris_n8n.py | 189 | Asserts absence | None needed |
| docs/runbooks/RIS_N8N_SMOKE_TEST.md | 45 | Asserts absence | None needed |
| docs/dev_logs/2026-04-06_ris_n8n_phase_n4_repo_hardening.md | 12,34,35,40,65 | Historical audit | None needed |
| docs/dev_logs/2026-04-05_n8n-workflows.md | 10,42-50,55 | Historical but claimed canonical | Added SUPERSEDED note |

## Remaining Non-N4 Dirt

The `.claude/*` directory has ~150+ modified/deleted/untracked entries from a GSD
framework update. These are OUTSIDE SCOPE per task constraints ("Do not touch .claude/*").
They will be addressed separately.

## Verification Commands

```
git status --short -- claude.md workflows/ ".planning/quick/26040*"
# Expected: only staged (A/D/M in col 1) entries, no unstaged or untracked
```

## Codex Review

Tier: Skip (git staging, dev log, no strategy/execution/risk code changed).
