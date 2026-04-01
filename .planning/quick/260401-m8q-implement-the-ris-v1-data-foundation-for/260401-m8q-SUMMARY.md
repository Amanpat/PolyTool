---
phase: quick-055
plan: "01"
subsystem: rag
tags: [knowledge-store, freshness, sqlite, ris-v1, external-knowledge]
dependency_graph:
  requires: []
  provides: [knowledge-store-persistence, freshness-decay-computation]
  affects: [packages/polymarket/rag/]
tech_stack:
  added: []
  patterns: [sqlite3-stdlib, sha256-deterministic-ids, lru-cache-config, exponential-decay]
key_files:
  created:
    - packages/polymarket/rag/knowledge_store.py
    - packages/polymarket/rag/freshness.py
    - config/freshness_decay.json
    - tests/test_knowledge_store.py
    - docs/features/FEATURE-ris-v1-data-foundation.md
    - docs/dev_logs/2026-04-01_ris_v1_data_foundation.md
  modified:
    - docs/CURRENT_STATE.md
decisions:
  - "SQLite stdlib over ORM -- consistent with existing lexical.py pattern"
  - "_llm_provider=None by default -- cloud LLM disabled pending Roadmap v5.1/PLAN_OF_RECORD authority sync"
  - "No Chroma wiring in this task -- data plane only, retrieval integration deferred"
  - "Contradiction penalty 0.5x multiplier -- contradicted claims sorted lower but not hidden"
  - "Freshness floor 0.3 -- old content gets some value rather than zero"
metrics:
  duration_seconds: 564
  completed_date: "2026-04-01"
  tasks_completed: 2
  tasks_total: 2
  files_created: 6
  files_modified: 1
  tests_added: 38
  tests_total_after: 2825
---

# Phase quick-055 Plan 01: RIS v1 Data Foundation Summary

**One-liner:** SQLite-backed knowledge store for external_knowledge partition with 4-table schema, freshness decay (exponential, configurable half-lives), and query-time contradiction downranking.

## What Was Built

### Task 1: Knowledge store persistence layer + freshness config (TDD)

**packages/polymarket/rag/knowledge_store.py**
- `KnowledgeStore` class backed by SQLite (stdlib `sqlite3` only, no ORM)
- Follows pattern from `lexical.py` (existing RAG SQLite usage)
- 4-table schema: `source_documents`, `derived_claims`, `claim_evidence`, `claim_relations`
- Deterministic SHA-256 IDs following `metadata.py` pattern
- CRUD: `add_source_document`, `add_claim`, `add_evidence`, `add_relation`
- Query: `get_claim`, `get_source_document`, `get_provenance`, `get_relations`, `query_claims`
- `query_claims` defaults: exclude archived, exclude superseded, apply freshness, downrank contradicted
- `effective_score = freshness_modifier * confidence * contradiction_penalty`
- `_llm_provider = None` (cloud LLM disabled; authority conflict documented)

**packages/polymarket/rag/freshness.py**
- `load_freshness_config(config_path=None)` -- loads `config/freshness_decay.json`, `lru_cache` on resolved path
- `compute_freshness_modifier(source_family, published_at, config=None)` -- exponential decay, floor=0.3
- Pure function: never mutates stored records
- Formula: `max(floor, 2^(-age_months / half_life_months))`
- `None` half-life (timeless families) always returns 1.0
- `None` published_at returns 1.0 (unknown age = no penalty)

**config/freshness_decay.json**
- 11 source families: `academic_foundational`, `book_foundational` (null=timeless), `academic_empirical` (18mo), `preprint` (12mo), `github` (12mo), `blog` (9mo), `reddit` (6mo), `twitter` (6mo), `youtube` (6mo), `wallet_analysis` (6mo), `news` (3mo)

**tests/test_knowledge_store.py**
- 38 tests in 8 test classes
- All use `:memory:` SQLite -- no network, no disk
- TDD cycle: RED (import error) -> 3 fixes -> GREEN (38 passed)

### Task 2: Documentation

- `docs/features/FEATURE-ris-v1-data-foundation.md`: full schema reference, freshness decay table, retrieval behavior, deliberate simplifications, authority conflict writeup, next steps
- `docs/dev_logs/2026-04-01_ris_v1_data_foundation.md`: commands run, test results, decisions, open questions, Codex review tier (skip)
- `docs/CURRENT_STATE.md`: appended RIS v1 section with authority conflict callout

## Test Results

| Suite | Before | After | Delta |
|-------|--------|-------|-------|
| test_knowledge_store.py | 0 (module missing) | 38 passed | +38 |
| Full suite | 2787 passed | 2825 passed | +38 |

**No regressions.** 2825 passed, 0 failed, 25 warnings (pre-existing deprecations).

## Commits

| Task | Commit | Message |
|------|--------|---------|
| Task 1 | 4fa347f | feat(quick-055): implement RIS v1 knowledge store persistence layer |
| Task 2 | 2ee1c82 | docs(quick-055): add RIS v1 feature doc, dev log, CURRENT_STATE authority conflict note |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] sqlite_sequence internal table counted in table-count assertion**
- **Found during:** Task 1, GREEN phase
- **Issue:** `_list_tables()` returned 5 results (4 app tables + sqlite_sequence); test expected exactly 4
- **Fix:** Filter `sqlite_` prefix tables in both `_list_tables()` and the test assertion
- **Files modified:** `packages/polymarket/rag/knowledge_store.py`, `tests/test_knowledge_store.py`
- **Commit:** 4fa347f (incorporated into GREEN fixes before commit)

**2. [Rule 1 - Bug] Borderline freshness threshold in test_recent_news_high_modifier**
- **Found during:** Task 1, GREEN phase
- **Issue:** At 30-day age, news modifier (half-life=3mo) = 0.796; test asserted > 0.8; borderline false failure
- **Fix:** Changed test window to 14 days where modifier = ~0.89 > 0.8 definitively
- **Files modified:** `tests/test_knowledge_store.py`
- **Commit:** 4fa347f (incorporated into GREEN fixes before commit)

**3. [Rule 1 - Bug] Deterministic ID collision between two source docs with same URL/hash**
- **Found during:** Task 1, GREEN phase
- **Issue:** `test_provenance_returns_source_docs_for_claim` created two docs with identical `_source_doc()` defaults (same source_url + content_hash = same SHA-256 ID); second insert was OR IGNORE no-op
- **Fix:** Test fixture uses distinct `source_url` and `content_hash` for each doc
- **Files modified:** `tests/test_knowledge_store.py`
- **Commit:** 4fa347f (incorporated into GREEN fixes before commit)

## Authority Conflict Documented

Per plan requirement, the LLM policy conflict is surfaced (not silently resolved):
- **Roadmap v5.1:** Tier 1 free cloud APIs (DeepSeek V3/R1, Gemini 2.5 Flash) allowed
- **PLAN_OF_RECORD:** No external LLM API calls
- **Code:** `_llm_provider = None` (disabled by default); abstraction point present
- **Documented in:** `knowledge_store.py` docstring, `FEATURE-ris-v1-data-foundation.md`, `dev_logs/2026-04-01_ris_v1_data_foundation.md`, `CURRENT_STATE.md`

## Known Stubs

None. The knowledge store is fully functional as a data plane. No UI rendering, no
empty/mock data sources flowing to output. The `_llm_provider=None` is intentional
policy (not a stub) and is documented as such.

## Scope Boundaries Respected

- No execution/, simtrader/strategies/, OMS, risk manager, ClickHouse write paths touched
- No benchmark manifests (config/benchmark_v1.*) touched
- No gate files touched
- Cloud LLM APIs NOT enabled by default
- New modules NOT added to `packages/polymarket/rag/__init__.py` exports (per plan instruction)

## Self-Check: PASSED

Files exist:
- packages/polymarket/rag/knowledge_store.py: EXISTS
- packages/polymarket/rag/freshness.py: EXISTS
- config/freshness_decay.json: EXISTS
- tests/test_knowledge_store.py: EXISTS
- docs/features/FEATURE-ris-v1-data-foundation.md: EXISTS
- docs/dev_logs/2026-04-01_ris_v1_data_foundation.md: EXISTS

Commits exist:
- 4fa347f: EXISTS
- 2ee1c82: EXISTS

Test counts: 38 new tests added; 2825 total passing; 0 regressions.
