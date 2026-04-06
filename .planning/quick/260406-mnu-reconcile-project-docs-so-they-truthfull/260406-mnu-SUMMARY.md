---
phase: quick-260406-mnu
plan: "01"
subsystem: docs
tags: [docs, n8n, ris, reconciliation, truth]
dependency_graph:
  requires: []
  provides: [accurate-n8n-state-in-all-docs]
  affects: [CLAUDE.md, docs/ARCHITECTURE.md, docs/PLAN_OF_RECORD.md, docs/CURRENT_STATE.md, README.md, docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md]
tech_stack:
  added: []
  patterns: []
key_files:
  modified:
    - CLAUDE.md
    - docs/ARCHITECTURE.md
    - docs/PLAN_OF_RECORD.md
    - docs/CURRENT_STATE.md
    - README.md
    - docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md
  created:
    - docs/dev_logs/2026-04-06_ris_n8n_truth_docs_closeout.md
decisions:
  - "Qualify n8n references with scoped/pilot/opt-in language everywhere rather than removing Phase 3 n8n content"
  - "Add footnote to roadmap v5.1 rather than restructuring the Phase 3 section"
  - "Use 'broad n8n orchestration layer' wording in CURRENT_STATE.md to preserve accuracy while acknowledging the pilot"
metrics:
  duration: "~10 minutes"
  completed: "2026-04-06"
  tasks_completed: 2
  files_modified: 7
---

# Phase quick-260406-mnu Plan 01: RIS n8n Truth Docs Closeout Summary

**One-liner:** Qualified all blanket "no n8n" statements across 6 high-authority docs to acknowledge the shipped scoped RIS n8n pilot (ADR 0013, n8n 2.14.2) while preserving Phase 3 as the target for broad orchestration.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Fix all n8n contradiction statements across 6 docs | 3433ef5 | CLAUDE.md, docs/ARCHITECTURE.md, docs/PLAN_OF_RECORD.md, docs/CURRENT_STATE.md, README.md, docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md |
| 2 | Create closeout dev log documenting contradictions and final truth | 3109220 | docs/dev_logs/2026-04-06_ris_n8n_truth_docs_closeout.md |

## What Was Done

### Task 1: Fix 6 docs

Seven targeted edits across 6 files removed or qualified stale n8n statements:

1. **CLAUDE.md line 41**: "No n8n orchestration until Phase 3" replaced with qualified statement acknowledging the scoped RIS pilot.
2. **CLAUDE.md line 119**: Scheduling layer roles updated -- APScheduler documented as default, scoped n8n pilot acknowledged for RIS, broad n8n kept as Phase 3 target.
3. **docs/ARCHITECTURE.md**: Control plane row now mentions RIS n8n pilot (ADR 0013, n8n 2.14.2) via `--profile ris-n8n`, while preserving "broad v4 control plane is not current truth."
4. **docs/PLAN_OF_RECORD.md**: Automation/hosting row now acknowledges RIS pilot for RIS ingestion workflows only; broader stack still not truth.
5. **docs/CURRENT_STATE.md**: "no n8n orchestration layer" qualified to "no broad n8n orchestration layer" with parenthetical RIS pilot exception.
6. **README.md**: Removed dead `simtrader` branch checkout (Step 1.2); replaced with main-only note.
7. **docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md**: Added blockquote footnote after line 679 under Phase 3 n8n section acknowledging shipped pilot.

### Task 2: Dev log

Created `docs/dev_logs/2026-04-06_ris_n8n_truth_docs_closeout.md` with:
- Contradiction table (7 rows, all files/lines/old/new/problem documented)
- Final truth statement for RIS n8n pilot status
- Files changed list
- Verification commands and results
- What was not changed (ADR 0013, RIS_OPERATOR_GUIDE, code files)

## Verification Results

Stale phrases confirmed gone:
- `grep -c "No n8n orchestration until Phase 3" CLAUDE.md` -> 0
- `grep -c "Phase 3 may add n8n" CLAUDE.md` -> 0
- `grep -c "git checkout simtrader" README.md` -> 0

Qualified phrases confirmed present:
- `grep -c "scoped RIS n8n pilot" CLAUDE.md docs/ARCHITECTURE.md docs/PLAN_OF_RECORD.md docs/CURRENT_STATE.md` -> 4 matches (1 each)
- `grep -c "ADR 0013" CLAUDE.md docs/ARCHITECTURE.md` -> 3 matches (2 in CLAUDE.md, 1 in ARCHITECTURE.md)

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None. This is a docs-only change; no data stubs introduced.

## Threat Flags

None. Docs-only change with no runtime, authentication, or data-handling impact.

## Self-Check: PASSED

- Commit 3433ef5 confirmed in git log
- Commit 3109220 confirmed in git log
- dev log exists at `docs/dev_logs/2026-04-06_ris_n8n_truth_docs_closeout.md`
- All 6 target docs modified per plan specification
- Zero stale phrases remain; all qualified phrases present
