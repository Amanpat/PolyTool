---
phase: quick-260403-jyg
plan: 01
subsystem: research-integration
tags: [ris, simtrader-bridge, hypothesis-registry, knowledge-store, validation-feedback]
dependency_graph:
  requires:
    - packages/research/hypotheses/registry.py (append_event)
    - packages/research/synthesis/report.py (ResearchBrief, EnhancedPrecheck, CitedEvidence)
    - packages/polymarket/rag/knowledge_store.py (KnowledgeStore, add_claim, get_claim)
  provides:
    - packages/research/integration/ (new module)
    - KnowledgeStore.update_claim_validation_status()
    - brief_to_candidate(), precheck_to_candidate(), register_research_hypothesis(), record_validation_outcome()
  affects:
    - docs/CURRENT_STATE.md
    - docs/features/FEATURE-ris-simtrader-bridge-v1.md
tech_stack:
  added:
    - packages/research/integration/ (new package)
  patterns:
    - Append-only JSONL registry event pattern (matching existing registry.py)
    - SHA-256 deterministic ID computation (matching existing knowledge_store.py pattern)
    - sqlite3 UPDATE with validation via VALID_VALIDATION_STATUSES constant
key_files:
  created:
    - packages/research/integration/__init__.py
    - packages/research/integration/hypothesis_bridge.py
    - packages/research/integration/validation_feedback.py
    - tests/test_ris_simtrader_bridge.py
    - docs/features/FEATURE-ris-simtrader-bridge-v1.md
    - docs/dev_logs/2026-04-03_ris_r5_simtrader_bridge.md
  modified:
    - packages/polymarket/rag/knowledge_store.py
    - docs/CURRENT_STATE.md
decisions:
  - Did not reuse stable_hypothesis_id() from registry.py -- that function expects dimension_key/segment_key shapes; research candidates use name-based identity; computed sha256 inline
  - Validation statuses align with RIS_07 Section 3 language (CONSISTENT_WITH_RESULTS=KEEP, CONTRADICTED=AUTO_DISABLE)
  - record_validation_outcome() is operator-triggered, not automatic; no auto-loop shipped at v1
  - evidence_doc_ids flow through the full chain (brief.cited_sources -> candidate -> registry event source field)
metrics:
  duration: "~18 minutes"
  completed: "2026-04-03T18:35:00Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 6
  files_modified: 2
  tests_added: 37
  tests_total_passing: 3644
---

# Phase quick-260403-jyg Plan 01: RIS SimTrader Bridge v1 Summary

**One-liner:** SHA-256-keyed research bridge (brief/precheck -> hypothesis registry) + SQLite validation feedback hook (confirmed/contradicted/inconclusive -> CONSISTENT_WITH_RESULTS/CONTRADICTED/INCONCLUSIVE) with 37 deterministic offline tests.

---

## What Was Built

The RIS SimTrader Bridge v1 closes the research-to-validation loop described in
RIS_07 Section 3 at the practical / v1 level. Before this plan, ResearchBrief
and EnhancedPrecheck were dead-end dataclasses -- rich cited evidence with no
path forward. Now:

1. **Research finding -> hypothesis registry**: `brief_to_candidate()` and
   `precheck_to_candidate()` convert research outputs to candidate dicts.
   `register_research_hypothesis()` writes a JSONL event with
   `source.origin="research_bridge"` and full `evidence_doc_ids` provenance.

2. **Validation outcome -> KnowledgeStore feedback**: `record_validation_outcome()`
   maps `confirmed/contradicted/inconclusive` to
   `CONSISTENT_WITH_RESULTS/CONTRADICTED/INCONCLUSIVE` and updates all specified
   claim rows in the KnowledgeStore SQLite database.

3. **KnowledgeStore.update_claim_validation_status()**: New method with validation
   against `VALID_VALIDATION_STATUSES` constant, raises `ValueError` for unknown
   claim_id or invalid status, updates `updated_at` timestamp on every write.

---

## Task Results

| Task | Name | Commit | Files | Status |
|------|------|--------|-------|--------|
| 1 | KnowledgeStore update method + hypothesis bridge + validation feedback | edccc70 | packages/polymarket/rag/knowledge_store.py, packages/research/integration/{__init__.py, hypothesis_bridge.py, validation_feedback.py}, tests/test_ris_simtrader_bridge.py | 37/37 tests passed |
| 2 | Regression + docs + dev log | 00cd65c | docs/features/FEATURE-ris-simtrader-bridge-v1.md, docs/dev_logs/2026-04-03_ris_r5_simtrader_bridge.md, docs/CURRENT_STATE.md | Full regression: 3644 passed, 0 new failures |

---

## Verification Results

1. `python -m pytest tests/test_ris_simtrader_bridge.py -x -v --tb=short` -- 37 passed
2. `python -m pytest tests/ -q --tb=line` -- 3644 passed, 0 new failures from bridge work (6 pre-existing failures in test_ris_dossier_extractor.py from parallel agent jy8)
3. `python -c "from packages.research.integration import brief_to_candidate, register_research_hypothesis, record_validation_outcome; print('OK')"` -- OK
4. `python -m polytool --help` -- CLI loads without import errors

---

## Deviations from Plan

None in implementation. One notable parallel-agent interaction:

**Parallel agent (jy8) modified packages/research/integration/__init__.py on disk** after my Task 1 commit, adding `dossier_extractor` imports that don't exist yet (jy8 is the dossier pipeline plan). This caused 6 test failures in `test_ris_dossier_extractor.py` that are NOT from my bridge work. Per CLAUDE.md multi-agent rules, I did not revert the parallel agent's changes. My 37 bridge tests pass in isolation and the import smoke test passes.

---

## Known Stubs

None. All bridge functions are fully wired:
- `brief_to_candidate()` reads from real ResearchBrief fields
- `precheck_to_candidate()` reads from real EnhancedPrecheck fields
- `register_research_hypothesis()` writes to a real JSONL file via `append_event()`
- `record_validation_outcome()` calls `update_claim_validation_status()` which executes a real SQLite UPDATE

---

## What Is Shipped (v1 practical bridge) vs Deferred (R5/v2)

**Shipped:**
- Manual bridge functions (operator-triggered, not automatic)
- Deterministic, offline, no network calls, no LLM calls
- Evidence provenance chain: brief.cited_sources -> candidate.evidence_doc_ids -> registry event source.evidence_doc_ids
- 37 deterministic tests exercising end-to-end function chains

**Explicitly deferred to R5/v2:**
- Auto-test orchestration loop (no automated "register -> run SimTrader -> record feedback" cycle)
- Auto-hypothesis promotion on Gate 2 pass
- Discord approval integration for feedback loop
- Scheduled re-validation cron job
- LLM-enhanced hypothesis generation (DeepSeek V3, deferred per PLAN_OF_RECORD no-external-LLM policy)

## Self-Check: PASSED

Files created exist:
- packages/research/integration/__init__.py: FOUND
- packages/research/integration/hypothesis_bridge.py: FOUND
- packages/research/integration/validation_feedback.py: FOUND
- tests/test_ris_simtrader_bridge.py: FOUND
- docs/features/FEATURE-ris-simtrader-bridge-v1.md: FOUND
- docs/dev_logs/2026-04-03_ris_r5_simtrader_bridge.md: FOUND

Commits exist:
- edccc70: FOUND (feat(quick-260403-jyg-01): RIS SimTrader bridge v1)
- 00cd65c: FOUND (feat(quick-260403-jyg-02): regression clean + feature doc + dev log)
