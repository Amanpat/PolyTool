---
phase: 260409-jfm
plan: "01"
subsystem: research-intelligence-system
tags: [ris, phase2, acceptance, closeout, documentation]
dependency_graph:
  requires: []
  provides: [phase2-closeout]
  affects: [docs/features, docs/roadmaps, docs/dev_logs]
tech_stack:
  added: []
  patterns: [acceptance-matrix, evidence-backed-closeout]
key_files:
  created:
    - docs/features/FEATURE-ris-phase2-closeout.md
    - docs/dev_logs/2026-04-09_ris_phase2_acceptance_closeout.md
  modified:
    - docs/roadmaps/RIS_PHASE2_evaluation_gate_monitoring_rag_testing_v1_1.md
decisions:
  - "CONDITIONAL CLOSE: Items 1,2,3,4-storage,6,7,8 PASS; Item 9 N/A (SQLite not ClickHouse); Items 5 and 10 deferred"
  - "Item 9 (ClickHouse idempotency) is N/A - RIS uses SQLite via KnowledgeStore with doc_id uniqueness"
  - "Item 5 (budget caps) deferred to Phase 3 - config schema present, no enforcement code"
  - "Item 10 (posture statement) partial - present in research-review CLI, absent from 4 other CLI module docstrings"
metrics:
  duration: "~15 minutes"
  completed: "2026-04-09"
  tasks_completed: 2
  files_changed: 3
---

# Phase 260409-jfm Plan 01: RIS Phase 2 Acceptance Sweep and Closeout Summary

**One-liner:** Evidence-backed acceptance sweep of all 10 RIS Phase 2 contract items with CONDITIONAL CLOSE recommendation, roadmap checkboxes updated to match verified evidence.

## What Was Done

Ran targeted verification commands against all 10 Phase 2 contract items from `docs/roadmaps/RIS_PHASE2_evaluation_gate_monitoring_rag_testing_v1_1.md`. Collected evidence from test counts, grep results, and CLI smoke runs. Produced a dev log with exact command output, a closeout artifact with a per-item acceptance matrix, and updated roadmap checkboxes to reflect verified dispositions only.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | Run verification commands and write dev log | 3393241 | docs/dev_logs/2026-04-09_ris_phase2_acceptance_closeout.md |
| 2 | Write closeout artifact and update roadmap | 4844e2c | docs/features/FEATURE-ris-phase2-closeout.md, docs/roadmaps/RIS_PHASE2_evaluation_gate_monitoring_rag_testing_v1_1.md |

## Acceptance Matrix Summary

| Item | Description | Status |
|------|-------------|--------|
| 1 | Fail-closed evaluation | PASS |
| 2 | Weighted composite gate | PASS |
| 3 | Novelty/dedup detection | PASS |
| 4 | Review queue contract | PASS with caveat (72h auto-expiry not implemented) |
| 5 | Per-source daily budget caps | NOT IMPLEMENTED |
| 6 | Per-priority acceptance gates | PASS |
| 7 | Segmented benchmark metrics | PASS |
| 8 | Env-var-primary n8n config | PASS |
| 9 | Dual-layer ClickHouse idempotency | N/A (RIS uses SQLite) |
| 10 | Research-only posture statement | PARTIAL |

## Evidence Summary

- 307 Phase 2 tests pass across 10 test files
- `config/ris_eval_config.json` valid JSON with weights, floors, thresholds, budget schema
- `docs/eval/ris_retrieval_benchmark.jsonl` valid JSONL, 9 cases, 3 query classes
- `packages/research/evaluation/dedup.py` exists with `check_near_duplicate()`
- `tools/cli/research_review.py` has posture statement; other 4 CLIs do not
- No enforcement code found for budget caps in ingestion/evaluation/scheduling
- No `ris_events` table or `ReplacingMergeTree` in RIS codebase (SQLite only)

## Recommendation

**CONDITIONAL CLOSE** — 7 core contract items (1, 2, 3, 4-storage, 6, 7, 8) pass with full test coverage. Item 9 is N/A with architectural rationale. Items 5 (budget caps), Item 4 (72h auto-expiry), and Item 10 (posture statement gap) are deferred to Phase 3.

## Deviations from Plan

None — plan executed exactly as written. Verification commands matched expected findings from prior dev logs. Roadmap checkboxes updated for passing items only per plan instructions; Status line left as "Pending Implementation" because Items 5 and 10 remain incomplete.

## Known Stubs

- `rejection_audit_disagreement` health check returns stub (GREEN hardcoded). Tracked in dev log and closeout artifact. Phase 3 / RIS v2 deliverable.
- Item 5 enforcement: budget schema in `config/ris_eval_config.json` has `budget` key but no enforcement code in ingestion pipeline.

## Threat Flags

None — this plan was read-only verification and documentation. No code files modified.

## Self-Check

- [x] `docs/features/FEATURE-ris-phase2-closeout.md` - EXISTS
- [x] `docs/dev_logs/2026-04-09_ris_phase2_acceptance_closeout.md` - EXISTS  
- [x] Commit `3393241` - Task 1 (dev log)
- [x] Commit `4844e2c` - Task 2 (closeout artifact + roadmap)
- [x] Roadmap checkboxes match evidence (items 1-4,6-9 checked; 5,10 unchecked)
- [x] No code files modified

## Self-Check: PASSED
