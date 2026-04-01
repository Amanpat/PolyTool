---
phase: quick
plan: 260401-n1s
subsystem: research
tags: [ris, precheck, knowledge-store, freshness, ledger, tdd]
dependency_graph:
  requires: [260401-m8y]
  provides: [ris-precheck-wiring, precheck-ledger-v1]
  affects: [packages/research/synthesis/precheck.py, packages/research/synthesis/precheck_ledger.py]
tech_stack:
  added: []
  patterns: [TYPE_CHECKING guard for optional imports, backward-compat default=None kwargs, append-only JSONL schema bump]
key_files:
  created:
    - tests/test_ris_precheck_wiring.py
    - docs/features/FEATURE-ris-v1-evaluation-gate.md
    - docs/dev_logs/2026-04-01_ris_v1_precheck_wiring.md
  modified:
    - packages/research/synthesis/precheck.py
    - packages/research/synthesis/precheck_ledger.py
    - tools/cli/research_precheck.py
decisions:
  - "No semantic filtering in find_contradictions(): returns all CONTRADICTS-related claims as broad candidates; LLM evaluates relevance in prompt"
  - "ks._conn direct access for source_documents query: acceptable internal coupling for v1; document for future cleanup"
  - "TYPE_CHECKING guard for KnowledgeStore import: avoids circular import risk, duck-typing at runtime"
  - "Lifecycle fields deferred: was_overridden/override_reason/outcome_label/outcome_date require operator workflow; no prechecks exist yet to track"
metrics:
  duration: "~45 minutes"
  completed: "2026-04-01T20:51:37Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 3
---

# Phase quick Plan 260401-n1s: RIS v1 Precheck Wiring Summary

**One-liner:** Wired `find_contradictions()` and `check_stale_evidence()` stubs to KnowledgeStore + freshness decay; bumped precheck ledger to v1 schema with 4 enriched fields; 35 new offline TDD tests.

## What Was Built

Two stub functions in `packages/research/synthesis/precheck.py` were wired to real infrastructure that already existed in the codebase but was not yet connected:

**`find_contradictions(idea, knowledge_store=None)`**
- Returns `[]` when no KnowledgeStore provided (backward compat preserved)
- When a store is provided: queries all active claims via `ks.query_claims(apply_freshness=False)`, checks each for CONTRADICTS relations via `ks.get_relations(claim_id, relation_type="CONTRADICTS")`, returns `claim_text` strings for any claim involved in a CONTRADICTS relation
- Intentionally broad (no semantic filtering): idea text is not used for filtering; all CONTRADICTS-related claims are returned as candidates for the LLM to evaluate

**`check_stale_evidence(result, knowledge_store=None)`**
- Returns `result` unchanged when no KnowledgeStore provided (backward compat)
- When a store is provided: queries source_documents, computes `compute_freshness_modifier(source_family, published_at)` for each
- Sets `stale_warning=True` when ALL source docs have modifier < 0.5 (one full half-life)
- Returns result unchanged when no source documents exist (no data = no penalty)

**`run_precheck()` wiring:**
- Accepts `knowledge_store=None` kwarg
- Merges KS contradictions into `result.contradicting_evidence` with deduplication
- Passes knowledge_store to both stub functions

**Precheck ledger v1 schema:**
- `LEDGER_SCHEMA_VERSION` bumped from `precheck_ledger_v0` to `precheck_ledger_v1`
- `PrecheckResult` gains 4 new fields (all default `""`): `precheck_id`, `reason_code`, `evidence_gap`, `review_horizon`
- `run_precheck()` populates: `precheck_id=sha256[:12](idea)`, `reason_code` from recommendation, `evidence_gap` when no contradictions + rec != GO, `review_horizon` 7d/30d/""
- `append_precheck()` serializes all 4 new fields; `list_prechecks()` returns raw dicts (v0 entries naturally lack new fields — callers use `.get()`)

## Commits

| Hash | Message |
|------|---------|
| `802737f` | feat(quick-260401-n1s): wire find_contradictions and check_stale_evidence to KnowledgeStore and freshness; enrich precheck ledger schema to v1 |

(Feature doc and dev log committed as part of final metadata commit)

## Test Results

```
tests/test_ris_precheck_wiring.py  35 passed  (new file)
tests/test_ris_precheck.py         25 passed  (no regressions)
tests/test_ris_evaluation.py       37 passed  (no regressions)
Total: 97 passed, 0 failed, 0 skipped
```

All tests offline/deterministic. KnowledgeStore uses `:memory:` SQLite. No network, no LLM.

## Deviations from Plan

None — plan executed exactly as written.

## Deferred Items

**Lifecycle fields (documented in dev log and feature doc):**
- `was_overridden`, `override_reason`, `outcome_label`, `outcome_date` — require operator workflow for marking prechecks as resolved and recording actual outcomes. Deferred to a future "precheck lifecycle" task.

**Semantic contradiction filtering:**
- `find_contradictions()` currently returns ALL claims with CONTRADICTS relations. Embedding-based relevance filtering deferred to a future RIS task when the knowledge base has sufficient content.

**Cloud LLM providers:**
- Gemini, DeepSeek, etc. deferred to RIS v2 (RIS_03 spec). Calling `get_provider("gemini")` raises `ValueError` pointing to RIS_03.

## Known Stubs

None — all stubs from m8y that were in scope for this plan are now wired.

## Self-Check: PASSED

Files verified:
- `packages/research/synthesis/precheck.py` — FOUND (contains KnowledgeStore, compute_freshness_modifier wiring)
- `packages/research/synthesis/precheck_ledger.py` — FOUND (LEDGER_SCHEMA_VERSION = precheck_ledger_v1)
- `tests/test_ris_precheck_wiring.py` — FOUND (35 tests)
- `docs/features/FEATURE-ris-v1-evaluation-gate.md` — FOUND
- `docs/dev_logs/2026-04-01_ris_v1_precheck_wiring.md` — FOUND
- Commit `802737f` — VERIFIED (in git log)
