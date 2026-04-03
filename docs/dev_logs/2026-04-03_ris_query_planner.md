# Dev Log: 2026-04-03 — RIS Query Planner, HyDE, and Combined Retrieval

**Task:** quick-260402-xbj
**Requirement:** RIS_05 (Synthesis Engine — query planning side)
**Branch:** feat/ws-clob-feed

---

## Objective

Complete the query-planning side of the RIS_05 Synthesis Engine by adding:

1. **Query planner** (`query_planner.py`): Topic -> diverse retrieval queries
2. **HyDE expansion** (`hyde.py`): Query -> hypothetical document passage for better retrieval recall
3. **Combined retrieval helper** (`retrieval.py`): Multi-angle retrieval via existing `query_index()` RRF spine

---

## Files Changed

| File | Change |
|------|--------|
| `packages/research/synthesis/query_planner.py` | Created (new) |
| `packages/research/synthesis/hyde.py` | Created (new) |
| `packages/research/synthesis/retrieval.py` | Created (new) |
| `packages/research/synthesis/__init__.py` | Updated exports |
| `tests/test_ris_query_planner.py` | Created (new) — 27 tests |
| `docs/features/FEATURE-ris-query-planner.md` | Created (new) |
| `docs/dev_logs/2026-04-03_ris_query_planner.md` | This file |
| `docs/CURRENT_STATE.md` | Updated |

---

## Key Decisions

1. **Module-level provider imports**: Initial implementation used deferred imports inside
   `plan_queries()` and `expand_hyde()` for both `get_provider` and `EvalDocument`. This
   prevented `patch("...query_planner.get_provider")` from working in tests because
   `unittest.mock.patch` requires the attribute to exist on the target module at patch time.
   Fixed by moving both imports to module level, matching the pattern used in `precheck.py`.

2. **`query_index` wrapper in retrieval.py**: `retrieval.py` defines its own `query_index(**kwargs)`
   wrapper that defers the import of the real `query_index` from `packages.polymarket.rag.query`.
   This avoids Chroma import-time side effects while still allowing `patch("packages.research.synthesis.retrieval.query_index")` to work in tests without a Chroma dependency.

3. **Deterministic mode is not a fallback**: For `provider_name="manual"`, `was_fallback=False`
   since manual is the intended offline path, not a degraded state. `was_fallback=True` only
   fires when an LLM provider was requested but failed or returned garbage.

4. **ANGLE_PREFIXES approach**: Five angle prefixes (`evidence for`, `risks of`,
   `alternatives to`, `recent developments in`, `key assumptions behind`) provide
   systematic multi-angle coverage of any topic. This is deterministic, reproducible,
   and produces semantically diverse queries that map to different retrieval clusters.

5. **HyDE template design**: The deterministic HyDE template references the query text
   directly in the first sentence (`Research indicates that {query}`) so the template
   embedding captures the query's semantic content even without LLM expansion.

6. **Dedup by highest score**: When the same chunk_id appears in multiple query results,
   the highest-scoring entry is kept. This preserves the best signal while eliminating
   duplicates.

---

## Commands Run and Results

```
# TDD RED phase — confirmed all 27 tests failed before implementation
rtk python -m pytest tests/test_ris_query_planner.py -v --tb=short
# 27 failed (ModuleNotFoundError) ✓

# After implementing query_planner.py + hyde.py + retrieval.py
# Fix: moved get_provider imports to module level (deferred import broke mocking)
rtk python -m pytest tests/test_ris_query_planner.py -v --tb=short
# 27 passed in 0.15s ✓

# Full regression suite
rtk python -m pytest tests/ -x -q --tb=short
# 3474 passed, 3 deselected, 25 warnings in 96.04s ✓

# CLI smoke
python -m polytool --help
# CLI loads without errors ✓

# Import smoke
python -c "from packages.research.synthesis import plan_queries, expand_hyde, retrieve_for_research; print('OK')"
# OK ✓
```

---

## Deviations from Plan

1. **[Rule 1 - Bug] Moved provider imports to module level**
   - Found during: Task 1 GREEN phase
   - Issue: `get_provider` and `EvalDocument` imported inside function body prevented
     `unittest.mock.patch` from finding them as module attributes
   - Fix: Moved both imports to module-level in `query_planner.py` and `hyde.py`
   - Files modified: `query_planner.py`, `hyde.py`
   - Impact: None to runtime behavior; test mocking now works correctly

---

## Deferred Items

- Semantic query dedup (cosine similarity pre-filter before issuing retrieval calls)
- Parallel sub-query execution (ThreadPoolExecutor for faster multi-query retrieval)
- Multi-hop reasoning (chain retrieved snippets as follow-up context)
- Cloud LLM providers for HyDE (RIS v2 deliverable)

---

## Codex Review

Tier: Skip (no execution/trading/risk code touched — docs, tests, synthesis library only).

---

## Next Steps

- Wire `retrieve_for_research()` into `ReportSynthesizer` for evidence-backed research briefs
- Implement semantic query dedup as next RIS_05 task
- Consider integrating step-back query into precheck pipeline for broader context gathering
