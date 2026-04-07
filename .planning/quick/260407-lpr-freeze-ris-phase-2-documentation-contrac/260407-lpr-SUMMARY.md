---
phase: quick-260407-lpr
plan: "01"
subsystem: ris-documentation
tags: [ris, documentation, contract-freeze, v1.1]
dependency_graph:
  requires: []
  provides: [ris-phase2-contract-frozen]
  affects: [docs/reference/RAGfiles/RIS_OVERVIEW.md, docs/reference/RAGfiles/RIS_03_EVALUATION_GATE.md, docs/reference/RAGfiles/RIS_06_INFRASTRUCTURE.md, docs/PLAN_OF_RECORD.md]
tech_stack:
  added: []
  patterns: [append-only doc editing, canonical-ID dedup, weighted composite gate, fail-closed evaluation]
key_files:
  created:
    - docs/dev_logs/2026-04-07_ris_phase2_doc_reconciliation.md
  modified:
    - docs/reference/RAGfiles/RIS_OVERVIEW.md
    - docs/reference/RAGfiles/RIS_03_EVALUATION_GATE.md
    - docs/reference/RAGfiles/RIS_06_INFRASTRUCTURE.md
    - docs/PLAN_OF_RECORD.md
decisions:
  - "Narrow LLM policy exception: Tier 1 free APIs authorized for RIS evaluation gate only, not for signals or trading outputs"
  - "Weighted composite gate (dimension weights) replaces simple sum as canonical decision gate; simple sum retained as diagnostic metric"
  - "Fail-closed rule: scorer failure defaults to REJECT, never silent pass-through"
  - "Review queue uses SQLite pending_review table in existing KnowledgeStore DB"
  - "Budget controls: global cap 200/day, manual reserve 10 slots that automated ingestion cannot consume"
  - "ClickHouse idempotency dual-layer: ReplacingMergeTree storage + code-level prefilter before INSERT"
metrics:
  duration: "~25 minutes"
  completed_date: "2026-04-07"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 5
---

# Phase quick-260407-lpr Plan 01: Freeze RIS Phase 2 Documentation Contract Summary

**One-liner:** Bumped RIS roadmap suite from v1.0 to v1.1, locking ten Director-accepted Phase 2 additions (fail-closed gate, weighted composite, dedup pre-step, review queue, budget controls, per-priority thresholds, ClickHouse idempotency, n8n env-var config) into canonical spec documents before implementation begins.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Reconcile PLAN_OF_RECORD + bump RIS_OVERVIEW to v1.1 | 191c261 | docs/PLAN_OF_RECORD.md, docs/reference/RAGfiles/RIS_OVERVIEW.md |
| 2 | Update RIS_03 and RIS_06 with contract specifics | 6774e2b | docs/reference/RAGfiles/RIS_03_EVALUATION_GATE.md, docs/reference/RAGfiles/RIS_06_INFRASTRUCTURE.md |
| 3 | Write mandatory dev log | 448fb76 | docs/dev_logs/2026-04-07_ris_phase2_doc_reconciliation.md |

## What Was Built

**PLAN_OF_RECORD.md** — LLM/signals row updated with a narrow exception authorizing Tier 1 free cloud APIs (Gemini Flash, DeepSeek V3) for RIS evaluation gate scoring only. Scoped explicitly to prevent broadening to signals or trading recommendations.

**RIS_OVERVIEW.md (v1.1)** — Version bumped to 1.1, date updated to April 2026. Added:
- Changelog section listing all 10 Director-accepted additions with RIS companion file cross-references
- Posture Statement section making the research-only, no-trading-recommendations constraint explicit
- v1.1 note after Phase R1 in Development Phases listing the deliverables now included
- Footer updated to v1.1

**RIS_03_EVALUATION_GATE.md** — Five additions, all append/insert, no existing content removed:
1. Fail-Closed Rule subsection after the Architecture section
2. Weighted composite gate definition with dimension weights (relevance=0.30, novelty=0.25, actionability=0.25, credibility=0.20), acceptance threshold >= 3.0, and per-dimension floors (relevance >= 2, credibility >= 2)
3. Per-Priority Acceptance Gates table (Critical >= 2.5, High >= 3.0, Medium >= 3.2, Low >= 3.5)
4. Canonical-ID dedup pre-step at the top of the Deduplication section
5. Review Queue Contract section with SQLite pending_review schema and research-review CLI contract

**RIS_06_INFRASTRUCTURE.md** — Three additions, all append/insert, no existing content removed:
1. Ingestion Budget Controls section (global daily cap 200, per-source defaults, manual reserve 10 slots)
2. n8n Configuration Hierarchy subsection (env-vars primary, n8n Variables optional convenience)
3. ClickHouse Write Idempotency section (execution_id + ReplacingMergeTree + code-level prefilter)

**Dev log** — `docs/dev_logs/2026-04-07_ris_phase2_doc_reconciliation.md` documents all files edited, all 10 additions, the PLAN_OF_RECORD reconciliation rationale, cross-reference conflict check, and explicit list of what was NOT done.

## Decisions Made

1. **Narrow LLM policy exception** — The PLAN_OF_RECORD "no external LLM API calls" constraint had a latent conflict with the Master Roadmap v5.1 which explicitly authorizes Tier 1 free APIs for automated evaluation. Resolution: append a single-sentence exception scoped to RIS evaluation gate scoring only.

2. **Weighted composite replaces simple sum as gate** — The four-dimension 1-5 scores are now combined with weights rather than summed; the /20 simple sum is retained as a diagnostic metric in evaluation output but is NOT the decision gate.

3. **Review queue lives in existing SQLite DB** — The pending_review table is added to `kb/rag/knowledge/knowledge.sqlite3` (the existing KnowledgeStore database) rather than a separate store, keeping the storage footprint minimal.

4. **Dual-layer ClickHouse idempotency** — ReplacingMergeTree handles eventual dedup at storage level; code-level prefilter prevents accumulation before merges complete. Same pattern as existing trade_uid dedup pipeline.

5. **Item 7 (segmented retrieval benchmark) deferred to RIS_05** — The detailed spec for query-class-segmented benchmark metrics belongs in RIS_05_SYNTHESIS_ENGINE.md, not RIS_03 or RIS_06. Noted in the v1.1 changelog; RIS_05 update deferred to synthesis engine implementation planning.

## Deviations from Plan

None — plan executed exactly as written. All edits were append/insert only; no existing content was removed from any file.

## Known Stubs

None. This is a documentation-only change set. No code was written.

## Threat Flags

None. No runtime trust boundaries, network endpoints, auth paths, or schema changes introduced. The LLM policy exception is scoped to existing evaluation tooling; no new surface area created.

## Self-Check: PASSED

Files created/modified:
- FOUND: docs/reference/RAGfiles/RIS_OVERVIEW.md (Version 1.1 present)
- FOUND: docs/reference/RAGfiles/RIS_03_EVALUATION_GATE.md (fail-closed, weighted composite, pending_review, Per-Priority all present)
- FOUND: docs/reference/RAGfiles/RIS_06_INFRASTRUCTURE.md (execution_id, daily_cap, env-var primary all present)
- FOUND: docs/PLAN_OF_RECORD.md (Tier 1 RIS exception present)
- FOUND: docs/dev_logs/2026-04-07_ris_phase2_doc_reconciliation.md

Commits verified:
- FOUND: 191c261 (Task 1)
- FOUND: 6774e2b (Task 2)
- FOUND: 448fb76 (Task 3)
