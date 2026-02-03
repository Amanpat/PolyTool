---
phase: quick
plan: 001
subsystem: rag
tags: [reranking, cross-encoder, hybrid-retrieval, eval]

requires:
  - Phase 4: Eval harness with hybrid retrieval

provides:
  - BaseReranker interface for pluggable rerankers
  - CrossEncoderReranker using sentence-transformers
  - rerank_results function for post-retrieval reranking
  - hybrid+rerank eval mode for comparing precision gains
  - CLI flags: --rerank, --rerank-top-n, --rerank-model

affects:
  - Future reranker implementations (e.g., Cohere rerank, custom models)
  - RAG precision tuning workflows

tech-stack:
  added:
    - sentence-transformers.CrossEncoder for reranking
  patterns:
    - Abstract BaseReranker interface following BaseEmbedder pattern
    - Environment variable cache control (SENTENCE_TRANSFORMERS_HOME)
    - Opt-in reranking with deterministic test stubs

key-files:
  created:
    - packages/polymarket/rag/reranker.py
    - tests/test_rag_rerank.py
  modified:
    - packages/polymarket/rag/query.py
    - packages/polymarket/rag/eval.py
    - packages/polymarket/rag/__init__.py
    - tools/cli/rag_query.py
    - tools/cli/rag_eval.py
    - tests/test_rag_eval.py
    - docs/LOCAL_RAG_WORKFLOW.md

decisions:
  - model: cross-encoder/ms-marco-MiniLM-L-6-v2 (default, lightweight, proven)
  - cache-strategy: SENTENCE_TRANSFORMERS_HOME env var (CrossEncoder has no cache_folder param)
  - scope: rerank_top_n=50 default (rerank top 50 fused results, return k final)
  - integration: opt-in via --rerank flag (hybrid mode works fine without it)
  - testing: _FakeReranker stub for deterministic CI (no model downloads)

metrics:
  duration: 7min
  completed: 2026-02-03
---

# Quick Task 001: Offline Reranking for Hybrid Retrieval

**One-liner:** Cross-encoder reranking stage added after hybrid fusion using sentence-transformers, fully opt-in with deterministic tests.

## Objective

Add optional cross-encoder rerank stage after hybrid retrieval fusion to improve precision by rescoring top-N results with a more powerful model, while keeping the feature fully opt-in and CI-deterministic via stubs.

## Tasks Completed

### Task 1: Create reranker module (BaseReranker + CrossEncoderReranker + rerank_results)
**Commit:** c87804b

Created `packages/polymarket/rag/reranker.py` with:
- **BaseReranker** abstract interface (mirrors BaseEmbedder pattern)
  - `model_name: str` attribute
  - `score_pairs(query, documents) -> list[float]` method
- **CrossEncoderReranker** implementation
  - Default model: `cross-encoder/ms-marco-MiniLM-L-6-v2`
  - Device selection: auto/cuda/cpu
  - Cache folder: `kb/rag/models/` (managed via SENTENCE_TRANSFORMERS_HOME env var)
- **rerank_results** function
  - Reranks top-N results by cross-encoder score
  - Reassigns `final_rank` after reordering
  - Adds `rerank_score` field to each result
  - Preserves results beyond top_n with `rerank_score: None`

**Files:** 1 created
**Lines:** +132

### Task 2: Wire reranker into query_index and update eval _MODES
**Commit:** 534448f

Updated query and eval pipelines:
- **query.py changes:**
  - Added `reranker` and `rerank_top_n` params to `query_index`
  - Refactored return paths to use `final` variable pattern
  - Apply `rerank_results` when `reranker is not None`
  - Works across all retrieval modes (vector, lexical, hybrid)
- **eval.py changes:**
  - Added `"hybrid+rerank"` to `_MODES` list (4 modes now: vector, lexical, hybrid, hybrid+rerank)
  - Added `reranker` and `rerank_top_n` params to `run_eval`
  - Skip hybrid+rerank mode when `reranker is None` (notes="skipped: no reranker")
  - Pass reranker only to hybrid+rerank mode (other modes use reranker=None)
  - Updated `write_report` to include hybrid+rerank in markdown output
- **__init__.py changes:**
  - Exported BaseReranker, CrossEncoderReranker, rerank_results

**Files:** 3 modified
**Lines:** +58 / -30

### Task 3: Add CLI flags for rag-query and rag-eval
**Commit:** 0f9891b

Updated CLI tools:
- **rag_query.py:**
  - Added `--rerank` flag (boolean, enables reranking)
  - Added `--rerank-top-n` (int, default 50)
  - Added `--rerank-model` (str, default cross-encoder/ms-marco-MiniLM-L-6-v2)
  - Build CrossEncoderReranker when `--rerank` is set
  - Update mode string: `hybrid+rerank` or `vector+rerank`
  - Warning if `--rerank` used without `--hybrid` (still proceeds)
- **rag_eval.py:**
  - Added `--rerank-model` (str, default None — if omitted, hybrid+rerank is skipped)
  - Added `--rerank-top-n` (int, default 50)
  - Build reranker if `--rerank-model` provided
  - Updated console summary to include hybrid+rerank mode (widened column)

**Files:** 2 modified
**Lines:** +41 / -7

### Task 4: Write deterministic rerank tests
**Commit:** 419a55c

Created comprehensive test suites:
- **tests/test_rag_rerank.py:**
  - `_FakeReranker` stub (scores by snippet length for deterministic ordering)
  - `RerankerUnitTests` (5 tests):
    - Reorders by score
    - Reassigns final_rank
    - Handles empty results
    - Limits reranking to top_n
    - Preserves metadata
  - `RerankerIntegrationWithQueryTests` (2 tests):
    - query_index with reranker applies reranking
    - query_index without reranker unchanged
- **tests/test_rag_eval.py updates:**
  - `EvalHybridRerankModeTests` (2 tests):
    - hybrid+rerank mode included when reranker provided
    - hybrid+rerank mode skipped when reranker is None
- **All existing tests pass:** 72 tests in test_rag.py, 22 tests in test_rag_eval.py

**Files:** 2 created/modified
**Lines:** +189
**Tests added:** 9
**Total test suite:** 101 tests passing

### Task 5: Update docs
**Commit:** a567738

Updated `docs/LOCAL_RAG_WORKFLOW.md`:
- Added section "7) Rerank hybrid results (optional)"
- Documented `--rerank` CLI usage with examples
- Explained model caching under `kb/rag/models/`
- Showed how to include reranking in eval runs
- Added cache cleanup note (delete `kb/rag/models/` to force re-download)

**Files:** 1 modified
**Lines:** +24

## Verification

All verification checks passed:
1. ✅ Full test suite: 101 tests passed (7 rerank, 22 eval, 72 rag)
2. ✅ Import check: `from polymarket.rag import BaseReranker, CrossEncoderReranker, rerank_results`
3. ✅ CLI help: `--rerank`, `--rerank-top-n`, `--rerank-model` present in rag-query
4. ✅ CLI help: `--rerank-model`, `--rerank-top-n` present in rag-eval
5. ✅ _MODES check: `["vector", "lexical", "hybrid", "hybrid+rerank"]`

## Deviations from Plan

None — plan executed exactly as written.

## Next Phase Readiness

**Ready for use:**
- Cross-encoder reranking is fully functional and opt-in
- Deterministic tests ensure CI stability (no model downloads needed)
- CLI flags are documented and tested
- Model cache is gitignored and manageable

**No blockers identified.**

## Technical Decisions

1. **CrossEncoder cache strategy:**
   - CrossEncoder does NOT accept `cache_folder` parameter
   - Solution: Set `SENTENCE_TRANSFORMERS_HOME` env var before instantiation
   - Restore original env var after to avoid side effects

2. **Rerank scope (top_n):**
   - Default `top_n=50` reranks the top 50 fused results
   - Final output is still limited by `k` param (e.g., k=8)
   - Results beyond top_n have `rerank_score: None`

3. **Mode naming:**
   - `hybrid+rerank` for eval consistency
   - `vector+rerank` possible but not primary use case

4. **Testing strategy:**
   - `_FakeReranker` scores by snippet length (deterministic)
   - No real model downloads in CI
   - Integration tests mock `_run_vector_query` for isolation

## Performance Notes

- **Model size:** cross-encoder/ms-marco-MiniLM-L-6-v2 is ~80MB
- **Inference:** CPU-friendly, no GPU required (but CUDA works)
- **Cache location:** `kb/rag/models/` (gitignored)
- **First run:** Downloads model (~5-10s depending on connection)
- **Subsequent runs:** Instant (loads from cache)

## Usage Examples

**Basic reranking:**
```bash
python -m polyttool rag-query --question "What strategies did Alice use?" --hybrid --rerank --k 8
```

**Custom model and depth:**
```bash
python -m polyttool rag-query --question "..." --hybrid --rerank \
    --rerank-model cross-encoder/ms-marco-MiniLM-L-12-v2 \
    --rerank-top-n 100 --k 8
```

**Eval with reranking:**
```bash
python -m polyttool rag-eval --suite docs/eval/sample_queries.jsonl \
    --rerank-model cross-encoder/ms-marco-MiniLM-L-6-v2
```

## Files Changed Summary

| File | Type | Lines Changed | Purpose |
|------|------|--------------|---------|
| packages/polymarket/rag/reranker.py | created | +132 | Core reranker module |
| packages/polymarket/rag/query.py | modified | +29 / -15 | Wire reranker into query_index |
| packages/polymarket/rag/eval.py | modified | +24 / -10 | Add hybrid+rerank mode |
| packages/polymarket/rag/__init__.py | modified | +4 / -1 | Export reranker classes |
| tools/cli/rag_query.py | modified | +25 / -4 | Add --rerank flags |
| tools/cli/rag_eval.py | modified | +16 / -3 | Add --rerank-model flag |
| tests/test_rag_rerank.py | created | +230 | Rerank unit + integration tests |
| tests/test_rag_eval.py | modified | +89 | Hybrid+rerank eval tests |
| docs/LOCAL_RAG_WORKFLOW.md | modified | +24 | Document rerank usage |

**Total:** 9 files, 573 lines changed (+491 / -33), 5 commits

## Success Criteria Met

- ✅ reranker.py module exists with BaseReranker, CrossEncoderReranker, rerank_results
- ✅ query_index accepts reranker param, applies after any retrieval mode
- ✅ eval.py has 4 modes: vector, lexical, hybrid, hybrid+rerank
- ✅ CLI flags --rerank, --rerank-top-n, --rerank-model work on rag-query
- ✅ CLI flags --rerank-model, --rerank-top-n work on rag-eval
- ✅ All tests pass deterministically via _FakeReranker (no model download in CI)
- ✅ docs updated with rerank usage and model caching info

## Lessons Learned

1. **CrossEncoder API quirk:** No native `cache_folder` parameter — requires env var approach
2. **Test isolation:** Deterministic stubs (scoring by snippet length) work perfectly for CI
3. **Opt-in design:** Keeping reranking optional avoids breaking existing workflows
4. **Mode consistency:** Using `mode+feature` naming (hybrid+rerank) makes eval reports clear

---

**Generated:** 2026-02-03T18:20:57Z
**Duration:** 7 minutes
**Status:** Complete
