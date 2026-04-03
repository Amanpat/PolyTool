---
phase: quick-260402-xbj
plan: 01
subsystem: research/synthesis
tags: [ris, query-planner, hyde, retrieval, synthesis, offline]
dependency_graph:
  requires:
    - packages/research/evaluation/providers.py (get_provider, EvalProvider)
    - packages/research/evaluation/types.py (EvalDocument)
    - packages/polymarket/rag/query.py (query_index)
  provides:
    - packages/research/synthesis/query_planner.py (QueryPlan, plan_queries)
    - packages/research/synthesis/hyde.py (HydeResult, expand_hyde)
    - packages/research/synthesis/retrieval.py (RetrievalPlan, retrieve_for_research)
  affects:
    - packages/research/synthesis/__init__.py (new exports)
    - docs/CURRENT_STATE.md (new section)
tech_stack:
  added: []
  patterns:
    - TDD red-green cycle with offline monkeypatching
    - Module-level provider imports for test mockability
    - Thin wrapper function for deferred Chroma import
    - Dataclass-per-result pattern (QueryPlan, HydeResult, RetrievalPlan)
    - was_fallback tracking for LLM reliability monitoring
key_files:
  created:
    - packages/research/synthesis/query_planner.py
    - packages/research/synthesis/hyde.py
    - packages/research/synthesis/retrieval.py
    - tests/test_ris_query_planner.py
    - docs/features/FEATURE-ris-query-planner.md
    - docs/dev_logs/2026-04-03_ris_query_planner.md
  modified:
    - packages/research/synthesis/__init__.py
    - docs/CURRENT_STATE.md
decisions:
  - "Module-level provider imports required for unittest.mock.patch to intercept get_provider"
  - "Thin query_index wrapper in retrieval.py defers Chroma import while remaining patchable"
  - "was_fallback=False for manual provider (intended mode, not degraded state)"
  - "ANGLE_PREFIXES approach: 5 deterministic angles cover evidence, risks, alternatives, recency, assumptions"
  - "Dedup by highest score: overlapping chunk_ids across queries keep best signal"
metrics:
  duration: "~35 minutes"
  completed_date: "2026-04-03"
  tasks_completed: 2
  files_created: 7
  files_modified: 2
  tests_added: 27
  tests_total: 3474
---

# Phase quick-260402-xbj Plan 01: RIS Query Planner, HyDE, and Combined Retrieval Summary

## One-liner

Query planner (ANGLE_PREFIXES -> diverse queries), HyDE expansion (template/LLM hypothetical docs), and combined retrieval helper (multi-angle query_index() with dedup) wired into existing RIS synthesis package.

## What Was Built

Three new modules completing the query-planning side of RIS_05 Synthesis Engine:

### query_planner.py — Topic -> Diverse Queries

`plan_queries(topic, provider_name="manual", include_step_back=False, max_queries=5)` returns a `QueryPlan` with 3-5 retrieval queries covering multiple angles of the research topic.

**Deterministic mode** (default): Combines topic with ANGLE_PREFIXES:
- `"evidence for {topic}"`
- `"risks of {topic}"`
- `"alternatives to {topic}"`
- `"recent developments in {topic}"`
- `"key assumptions behind {topic}"`

**LLM mode** (Ollama): Sends a structured prompt requesting a JSON array of queries. Falls back to deterministic on any failure (`was_fallback=True`).

**Step-back support**: `include_step_back=True` adds a broader contextual query.

### hyde.py — Query -> Hypothetical Document

`expand_hyde(query, provider_name="manual")` returns a `HydeResult` with a hypothetical document passage that can be used as a retrieval query. Embedding the hypothetical document typically yields better recall than embedding the query directly (HyDE paper technique).

**Deterministic template**: `"Research indicates that {query}. Key considerations include empirical evidence, domain constraints, and practical implementation factors..."`

### retrieval.py — Multi-angle Retrieval via query_index()

`retrieve_for_research(topic, use_hyde=False, include_step_back=False, query_index_kwargs=None)` runs `query_index()` for each planned query and merges results.

- Deduplicates by `chunk_id` (highest score wins)
- Tracks `result_sources: dict[str, set[str]]` (chunk_id -> which queries found it)
- Graceful fallback: if Chroma unavailable, returns `results=[]` with `query_plan` populated
- `query_index_kwargs` pass-through for `hybrid`, `lexical_only`, `k`, etc.

## Tests

27 offline tests across 4 classes:

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestQueryPlanner` | 10 | Deterministic queries, step-back, max_queries, provider success/fallback/exception |
| `TestHyDE` | 6 | Template output, all HydeResult fields, provider success/fallback |
| `TestCombinedRetrieval` | 8 | RetrievalPlan shape, dedup logic, HyDE wiring, fallback, result_sources, sort order |
| `TestSynthesisModuleExports` | 3 | All new symbols importable from `packages.research.synthesis` |

All tests use monkeypatched providers/query_index — no network, no Chroma, no LLM required.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Moved provider imports to module level for test mockability**
- **Found during:** Task 1 GREEN phase
- **Issue:** `get_provider` and `EvalDocument` were imported inside the function body (`from packages.research.evaluation.providers import get_provider`). `unittest.mock.patch("packages.research.synthesis.query_planner.get_provider")` requires the attribute to exist on the module object at patch time — deferred imports are invisible to the patcher.
- **Fix:** Moved both imports to module level in `query_planner.py` and `hyde.py`.
- **Files modified:** `query_planner.py`, `hyde.py`
- **Commit:** 47c261f

## Known Stubs

None. All modules have deterministic behavior and valid output paths without LLM connectivity.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| `packages/research/synthesis/query_planner.py` | FOUND |
| `packages/research/synthesis/hyde.py` | FOUND |
| `packages/research/synthesis/retrieval.py` | FOUND |
| `tests/test_ris_query_planner.py` | FOUND |
| `docs/features/FEATURE-ris-query-planner.md` | FOUND |
| `docs/dev_logs/2026-04-03_ris_query_planner.md` | FOUND |
| commit 47c261f (Task 1) | FOUND |
| commit 661e66f (Task 2) | FOUND |
