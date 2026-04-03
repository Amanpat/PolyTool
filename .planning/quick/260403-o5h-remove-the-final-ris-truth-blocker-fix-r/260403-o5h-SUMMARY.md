---
phase: quick-260403-o5h
plan: 01
subsystem: docs/ris
tags: [ris, docs, truth-cleanup, rag-query]
dependency_graph:
  requires: []
  provides: [accurate-rag-query-operator-examples]
  affects: [docs/dev_logs/2026-04-03_ris_final_dossier_operationalization.md]
tech_stack:
  added: []
  patterns: []
key_files:
  modified:
    - docs/dev_logs/2026-04-03_ris_final_dossier_operationalization.md
  created:
    - docs/dev_logs/2026-04-03_ris_final_one_line_truth_cleanup.md
decisions:
  - "Left historical 'old text (broken at runtime)' sections in other dev logs untouched per plan constraints"
metrics:
  duration: "< 5 minutes"
  completed: "2026-04-03"
  tasks_completed: 1
  tasks_total: 1
  files_modified: 2
---

# Phase quick-260403-o5h Plan 01: Remove Final RIS Truth Blocker Summary

**One-liner:** Added `--hybrid` to the single remaining stale `rag-query --knowledge-store` operator example in the dossier operationalization dev log.

## Objective

Fix the last known stale operator-facing `rag-query` example in the RIS dev logs: line 167 of
`2026-04-03_ris_final_dossier_operationalization.md` used `--knowledge-store default` without
`--hybrid`, which fails at runtime with `Error: --knowledge-store requires --hybrid mode.`

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Fix stale rag-query example and write dev log | 3857827 | docs/dev_logs/2026-04-03_ris_final_dossier_operationalization.md, docs/dev_logs/2026-04-03_ris_final_one_line_truth_cleanup.md |

## What Was Done

### Task 1

1. Located the stale example at line 167 of `2026-04-03_ris_final_dossier_operationalization.md`
   inside the "What the first-class dossier flow now looks like" > "Operator flow" code block.

2. Changed:
   ```bash
   python -m polytool rag-query --question "MOMENTUM strategy wallets" --knowledge-store default
   ```
   to:
   ```bash
   python -m polytool rag-query --question "MOMENTUM strategy wallets" --hybrid --knowledge-store default
   ```

3. Did NOT touch historical "old text (broken at runtime)" sections in other dev logs — those
   are intentionally preserved as historical record.

4. Created `docs/dev_logs/2026-04-03_ris_final_one_line_truth_cleanup.md` documenting the fix
   with full context (what changed, why, scan confirmation).

## Verification Results

```
grep output: 167:python -m polytool rag-query ... --hybrid --knowledge-store default
knowledge-store count: 1
stale check: ALL CLEAR: every --knowledge-store usage includes --hybrid
```

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED

- `docs/dev_logs/2026-04-03_ris_final_dossier_operationalization.md` — FOUND, line 167 corrected
- `docs/dev_logs/2026-04-03_ris_final_one_line_truth_cleanup.md` — FOUND, 49 lines
- Commit `3857827` — FOUND
