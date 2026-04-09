---
phase: 260409-jfi
plan: 01
subsystem: docs
tags: [ris, docs, phase2, operator-guide, review-queue, evaluation-gate, retrieval-benchmark]
dependency_graph:
  requires: [quick-260408-oyu, quick-260408-oz0]
  provides: [accurate-ris-phase2-operator-docs]
  affects: [docs/RIS_OPERATOR_GUIDE.md, README.md, docs/README.md, docs/CURRENT_STATE.md]
tech_stack:
  added: []
  patterns: [docs-only reconciliation]
key_files:
  created:
    - docs/dev_logs/2026-04-09_ris_phase2_docs_closeout.md
  modified:
    - docs/RIS_OPERATOR_GUIDE.md
    - README.md
    - docs/README.md
    - docs/CURRENT_STATE.md
decisions:
  - Targeted edits only — no narrative rewrites; all existing accurate content preserved
  - Evaluation Gate and Review Queue as new named sections in RIS_OPERATOR_GUIDE.md for discoverability
  - RIS_OPERATOR_GUIDE.md linked in both "Start here" and "Workflows" sections of docs/README.md
metrics:
  duration: ~20 min
  completed: 2026-04-09
  tasks_completed: 3
  files_changed: 4 (+ 1 dev log created)
---

# Phase 260409-jfi Plan 01: Reconcile Repo Docs for Shipped Phase 2 RIS Summary

**One-liner:** Docs-only reconciliation removing stale "v2 deliverable / raises ValueError" cloud provider claims and adding Evaluation Gate, Review Queue, and Retrieval Benchmark sections to operator docs.

## What Was Done

### Task 1: RIS_OPERATOR_GUIDE.md

- Updated last-verified date to 2026-04-09.
- Added `research-review list/accept/reject` to Quick Reference table.
- Added new **Evaluation Gate** section: weighted composite formula, per-dimension floors, priority tier thresholds, provider routing chain, fail-closed behavior, `research-eval eval` CLI example with cloud env var requirements.
- Added new **Review Queue** section: 4-disposition table (accepted/queued_for_review/rejected/blocked), all 5 subcommands (list/inspect/accept/reject/defer), `--db` flag, audit history note.
- Added new **Retrieval Benchmark** section: `rag-eval --suite` command, `--suite-hash-only` flag, 3 query classes, 8 required metrics table, artifact paths.
- Fixed stale "What Does NOT Work Yet" bullet: Gemini and DeepSeek now correctly shown as implemented; OpenAI/Anthropic remain deferred.
- Replaced "Provider gemini is a RIS v2 deliverable" troubleshooting entry with real routing fallback documentation.
- Updated env vars table: `RIS_ENABLE_CLOUD_PROVIDERS` from "No effect" to accurate description; added 7 new cloud-provider env var rows.

### Task 2: README.md, docs/README.md, docs/CURRENT_STATE.md

- README.md "What Is Shipped Today" RIS row: updated to include weighted gate, cloud routing, review queue, retrieval benchmarks.
- README.md CLI table: added `research-review` row.
- docs/README.md: added `RIS_OPERATOR_GUIDE.md` as item 14 in "Start here" list and in Workflows section.
- docs/CURRENT_STATE.md: appended 4 Phase 2 shipped-truth entries (cloud routing, ingest/review integration, monitoring truth, retrieval benchmark truth).

### Task 3: Dev log

- Created `docs/dev_logs/2026-04-09_ris_phase2_docs_closeout.md` with files changed, all edits listed, commands run, test results, remaining caveats, and operator command index.

## Verification Results

| Check | Result |
|-------|--------|
| No stale "v2 deliverable" claims in RIS_OPERATOR_GUIDE.md | PASS |
| `research-review` in README.md and RIS_OPERATOR_GUIDE.md | PASS |
| Weighted composite / fail-closed / evaluation gate documented | PASS |
| Retrieval benchmark command and query classes documented | PASS |
| Only .md files changed across all commits | PASS |
| `python -m polytool --help` loads cleanly | PASS |
| `python -m pytest tests/ -x -q --tb=short` | 3810 passed, 3 deselected |

## Commits

| Hash | Message |
|------|---------|
| 68ec8b7 | docs(260409-jfi-01): fix RIS_OPERATOR_GUIDE stale claims, add evaluation gate, review queue, retrieval benchmark, env vars |
| 8777b0a | docs(260409-jfi-02): update README CLI table, shipped table, docs/README links, CURRENT_STATE Phase 2 entries |
| d268d28 | docs(260409-jfi-03): add Phase 2 docs closeout dev log |

## Deviations from Plan

None — plan executed exactly as written. All 7 must-have truths satisfied.

## Known Stubs

None introduced. All edits reflect shipped, verified behavior.

## Self-Check

- `docs/dev_logs/2026-04-09_ris_phase2_docs_closeout.md` — FOUND
- `docs/RIS_OPERATOR_GUIDE.md` — FOUND, modified
- `README.md` — FOUND, modified
- `docs/README.md` — FOUND, modified
- `docs/CURRENT_STATE.md` — FOUND, modified
- Commit 68ec8b7 — FOUND
- Commit 8777b0a — FOUND
- Commit d268d28 — FOUND

## Self-Check: PASSED
