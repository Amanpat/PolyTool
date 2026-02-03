---
phase: quick
plan: 001
type: execute
wave: 1
depends_on: []
autonomous: true
files_modified:
  - packages/polymarket/rag/reranker.py
  - packages/polymarket/rag/query.py
  - packages/polymarket/rag/eval.py
  - packages/polymarket/rag/__init__.py
  - tools/cli/rag_query.py
  - tools/cli/rag_eval.py
  - tests/test_rag_rerank.py
  - tests/test_rag_eval.py
  - docs/LOCAL_RAG_WORKFLOW.md

must_haves:
  truths:
    - "rag-query --hybrid --rerank produces results with rerank_score and correct final ordering"
    - "Reranking only operates on post-fusion results (never on raw vector/lexical lists)"
    - "Model files are cached under kb/rag/models/ via cache_folder parameter"
    - "rag-eval compares all 4 modes: vector, lexical, hybrid, hybrid+rerank"
    - "All tests pass deterministically using _FakeReranker stub (no real model needed)"
  artifacts:
    - path: "packages/polymarket/rag/reranker.py"
      provides: "BaseReranker, CrossEncoderReranker, rerank_results"
    - path: "tests/test_rag_rerank.py"
      provides: "Deterministic rerank tests via _FakeReranker"
  key_links:
    - from: "packages/polymarket/rag/query.py"
      to: "packages/polymarket/rag/reranker.py"
      via: "rerank_results called after hybrid fusion in query_index"
      pattern: "rerank_results"
    - from: "packages/polymarket/rag/eval.py"
      to: "packages/polymarket/rag/query.py"
      via: "hybrid+rerank mode passes reranker to query_index"
      pattern: "hybrid\\+rerank"
---

<objective>
Add optional cross-encoder rerank stage after hybrid retrieval fusion.

Purpose: Improve retrieval precision by reranking the top-N fused results with a cross-encoder model, while keeping the feature fully opt-in and CI-deterministic via stubs.

Output: reranker.py module, updated query/eval pipelines, CLI flags, tests, docs.
</objective>

<context>
@packages/polymarket/rag/query.py
@packages/polymarket/rag/embedder.py
@packages/polymarket/rag/eval.py
@packages/polymarket/rag/__init__.py
@packages/polymarket/rag/lexical.py
@tools/cli/rag_query.py
@tools/cli/rag_eval.py
@tests/test_rag.py
@tests/test_rag_eval.py
@docs/LOCAL_RAG_WORKFLOW.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create reranker module (BaseReranker + CrossEncoderReranker + rerank_results)</name>
  <files>packages/polymarket/rag/reranker.py</files>
  <action>
Create `packages/polymarket/rag/reranker.py` following the BaseEmbedder pattern from `embedder.py`:

1. **`BaseReranker` class** (abstract interface, mirrors BaseEmbedder pattern):
   - `model_name: str` attribute
   - `def score_pairs(self, query: str, documents: list[str]) -> list[float]` — raises NotImplementedError
   - Single method interface; keep it minimal like BaseEmbedder

2. **`CrossEncoderReranker(BaseReranker)` class**:
   - `__init__(self, model_name: str = DEFAULT_RERANK_MODEL, device: str = "auto", cache_folder: str = "kb/rag/models")`
   - Set `DEFAULT_RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"` as module-level constant
   - Import `sentence_transformers.CrossEncoder` inside __init__ (lazy, same pattern as SentenceTransformerEmbedder)
   - Raise RuntimeError with helpful message if sentence-transformers not installed
   - Resolve device: if "auto", use cuda if torch.cuda.is_available() else "cpu"
   - Resolve cache_folder to absolute path: `Path(cache_folder)` — if not absolute, resolve relative to `Path.cwd()`
   - Store the CrossEncoder instance: `self.model = CrossEncoder(model_name, device=resolved_device)` — NOTE: CrossEncoder does NOT have a native `cache_folder` param. Instead, set `os.environ["SENTENCE_TRANSFORMERS_HOME"]` to the cache_folder BEFORE instantiating. Restore env after. Or alternatively use `huggingface_hub` cache via `os.environ["HF_HOME"]`. Check sentence-transformers docs — the simplest approach is `CrossEncoder(model_name, cache_folder=str(cache_path))` if supported in recent versions, otherwise set env var.
   - `def score_pairs(self, query: str, documents: list[str]) -> list[float]`: Call `self.model.predict([(query, doc) for doc in documents])`, return as list of floats. Handle empty documents list (return []).

3. **`rerank_results(results: list[dict], query: str, reranker: BaseReranker, top_n: int = 50) -> list[dict]`** function:
   - Takes the post-fusion results list, extracts snippets, scores via reranker
   - `top_n` controls how many of the input results to rerank (default 50). If len(results) < top_n, rerank all.
   - Extract `documents = [r["snippet"] for r in candidates]` where candidates = results[:top_n]
   - Call `scores = reranker.score_pairs(query, documents)`
   - For each candidate, add `"rerank_score": score` to the result dict
   - Sort candidates by rerank_score descending
   - Re-assign `"final_rank"` to 1-based sequential after re-sort
   - Append any results beyond top_n (unranked) at the end, with `"rerank_score": None`
   - Return the reranked list

Include `from __future__ import annotations` at top. Type hints throughout.
  </action>
  <verify>
`python -c "from polymarket.rag.reranker import BaseReranker, CrossEncoderReranker, rerank_results; print('OK')"` succeeds (import check only, no model download).
  </verify>
  <done>reranker.py exists with BaseReranker, CrossEncoderReranker, rerank_results. Imports succeed.</done>
</task>

<task type="auto">
  <name>Task 2: Wire reranker into query_index and update eval _MODES</name>
  <files>
    packages/polymarket/rag/query.py
    packages/polymarket/rag/eval.py
    packages/polymarket/rag/__init__.py
  </files>
  <action>
**query.py changes:**

Add reranker params to `query_index` signature, after the hybrid retrieval block:

```python
from .reranker import BaseReranker, rerank_results
```

Add these params to `query_index()`:
- `reranker: Optional[BaseReranker] = None`
- `rerank_top_n: int = 50`

Logic change — at the END of `query_index`, right before `return`, add reranking:
- Only apply if `reranker is not None`
- Only apply on hybrid mode (when `hybrid=True`). If reranker is passed with non-hybrid mode, still apply it (rerank is valid on vector-only too), but the primary use case is hybrid.
- Call `rerank_results(results_to_return, query=question, reranker=reranker, top_n=rerank_top_n)` where `results_to_return` is whatever the current return value would be (the fused[:k] for hybrid, or vector results, etc.)
- Return the reranked list instead

Implementation approach — refactor the return path:
1. At the end of the hybrid block (line ~314), instead of `return fused[:k]`, store in `final = fused[:k]`
2. Same for vector block: store `final = _run_vector_query(...)`
3. Same for lexical block: store `final = _run_lexical_query(...)`
4. After all mode branches, add:
```python
if reranker is not None and final:
    final = rerank_results(final, query=question, reranker=reranker, top_n=rerank_top_n)
return final
```

This is cleaner than inserting rerank in each branch. Restructure the function so all paths assign to `final` and the rerank + return happens once at the end.

**eval.py changes:**

1. Import `BaseReranker` from `.reranker`
2. Add `"hybrid+rerank"` to `_MODES`:
```python
_MODES = [
    ("vector", {"hybrid": False, "lexical_only": False}),
    ("lexical", {"hybrid": False, "lexical_only": True}),
    ("hybrid", {"hybrid": True, "lexical_only": False}),
    ("hybrid+rerank", {"hybrid": True, "lexical_only": False}),
]
```
3. Add `reranker: Optional[BaseReranker] = None` and `rerank_top_n: int = 50` params to `run_eval()`
4. In the `run_eval` loop, when `mode_name == "hybrid+rerank"`:
   - Skip if `reranker is None` (same pattern as skipping vector modes when embedder is None — add notes="skipped: no reranker")
   - Pass `reranker=reranker, rerank_top_n=rerank_top_n` to `query_index()`
5. For all other modes, pass `reranker=None` to query_index so reranking is not applied
6. Update `write_report` to include "hybrid+rerank" in the mode iteration lists (lines ~382, ~399). Change the hardcoded `("vector", "lexical", "hybrid")` tuples to iterate over `report.modes.keys()` or add `"hybrid+rerank"` to the tuples.

**__init__.py changes:**

Add exports:
```python
from .reranker import BaseReranker, CrossEncoderReranker, rerank_results
```

Add to `__all__`:
- `"BaseReranker"`
- `"CrossEncoderReranker"`
- `"rerank_results"`
  </action>
  <verify>
`python -c "from polymarket.rag import BaseReranker, CrossEncoderReranker, rerank_results; print('OK')"` succeeds.
`python -c "from polymarket.rag.eval import _MODES; assert any(m[0] == 'hybrid+rerank' for m in _MODES); print('OK')"` succeeds.
  </verify>
  <done>query_index accepts reranker param and applies reranking after fusion. eval.py has 4 modes. __init__.py exports reranker classes.</done>
</task>

<task type="auto">
  <name>Task 3: Add CLI flags for rag-query and rag-eval</name>
  <files>
    tools/cli/rag_query.py
    tools/cli/rag_eval.py
  </files>
  <action>
**tools/cli/rag_query.py changes:**

1. Add import: `from polymarket.rag.reranker import CrossEncoderReranker, DEFAULT_RERANK_MODEL`
2. In `build_parser()`, add these arguments (after the --rrf-k argument):
   ```python
   parser.add_argument(
       "--rerank",
       action="store_true",
       default=False,
       help="Apply cross-encoder reranking after retrieval (requires --hybrid).",
   )
   parser.add_argument(
       "--rerank-top-n",
       type=int,
       default=50,
       help="Number of fused results to rerank (default 50).",
   )
   parser.add_argument(
       "--rerank-model",
       default=DEFAULT_RERANK_MODEL,
       help="Cross-encoder model name for reranking.",
   )
   ```
3. In `main()`:
   - After building the embedder, build the reranker conditionally:
     ```python
     reranker = None
     if args.rerank:
         if not args.hybrid:
             print("Warning: --rerank is most useful with --hybrid. Proceeding anyway.")
         reranker = CrossEncoderReranker(
             model_name=args.rerank_model,
             device=args.device,
             cache_folder="kb/rag/models",
         )
     ```
   - Pass `reranker=reranker, rerank_top_n=args.rerank_top_n` to `query_index()`
   - Update the mode string: if args.rerank, set mode to `"hybrid+rerank"` (or `"vector+rerank"` if not hybrid)
   - The JSON payload already includes `"mode"` — this will now reflect the rerank mode

**tools/cli/rag_eval.py changes:**

1. Add import: `from polymarket.rag.reranker import CrossEncoderReranker, DEFAULT_RERANK_MODEL`
2. In `build_parser()`, add:
   ```python
   parser.add_argument(
       "--rerank-model",
       default=None,
       help="Cross-encoder model for hybrid+rerank mode. If omitted, hybrid+rerank is skipped.",
   )
   parser.add_argument(
       "--rerank-top-n",
       type=int,
       default=50,
       help="Number of fused results to rerank in eval (default 50).",
   )
   ```
3. In `main()`:
   - After building the embedder, build the reranker:
     ```python
     reranker = None
     if args.rerank_model:
         try:
             reranker = CrossEncoderReranker(
                 model_name=args.rerank_model,
                 device=args.device,
                 cache_folder="kb/rag/models",
             )
         except RuntimeError as exc:
             print(f"Warning: Could not load reranker ({exc}). hybrid+rerank mode will be skipped.")
     ```
   - Pass `reranker=reranker, rerank_top_n=args.rerank_top_n` to `run_eval()`
   - Update the console summary mode iteration: change `("vector", "lexical", "hybrid")` to `("vector", "lexical", "hybrid", "hybrid+rerank")` — only print if mode exists in report.modes
  </action>
  <verify>
`python -m polyttool rag-query --help` shows --rerank, --rerank-top-n, --rerank-model flags.
`python -m polyttool rag-eval --help` shows --rerank-model, --rerank-top-n flags.
  </verify>
  <done>Both CLI tools accept rerank flags. rag-query --rerank triggers cross-encoder reranking. rag-eval --rerank-model enables hybrid+rerank eval mode.</done>
</task>

<task type="auto">
  <name>Task 4: Write deterministic rerank tests</name>
  <files>
    tests/test_rag_rerank.py
    tests/test_rag_eval.py
  </files>
  <action>
**Create tests/test_rag_rerank.py** — follow the exact patterns from test_rag.py:

```python
"""Tests for the reranking module (packages/polymarket/rag/reranker.py)."""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages"))

from polymarket.rag.reranker import BaseReranker, rerank_results
```

1. **`_FakeReranker(BaseReranker)` class** — deterministic scoring:
   - `model_name = "fake-reranker"`
   - `score_pairs(self, query, documents)`: return `[1.0 / (i + 1) for i in range(len(documents))]` — this gives descending scores [1.0, 0.5, 0.333...] based on original position. OR, for more interesting tests, score by `len(doc)` so longer snippets rank higher: `[float(len(doc)) for doc in documents]`. Use the length-based approach since it produces a non-trivial reordering.

2. **`RerankerUnitTests` class:**
   - `test_rerank_reorders_by_score`: Create 3 fake results with snippets of different lengths (short, long, medium). Call `rerank_results` with _FakeReranker. Assert the result order matches score-descending (longest snippet first). Assert each result has `rerank_score` key.
   - `test_rerank_final_rank_reassigned`: After reranking, verify `final_rank` is sequential 1, 2, 3...
   - `test_rerank_empty_results`: `rerank_results([], "q", _FakeReranker())` returns `[]`
   - `test_rerank_top_n_limits_reranking`: Create 5 results, rerank with top_n=3. First 3 should be reranked (have rerank_score != None), last 2 should have rerank_score=None.
   - `test_rerank_preserves_metadata`: Verify all original fields (file_path, chunk_id, metadata, etc.) are preserved after reranking.

3. **`RerankerIntegrationWithQueryTests` class:**
   - `test_query_index_with_reranker`: Patch `_run_vector_query` to return 3 stubbed results. Call `query_index` with `reranker=_FakeReranker()`. Assert results have `rerank_score` and are reordered by score.
   - `test_query_index_without_reranker_unchanged`: Call `query_index` with `reranker=None` (same stub). Assert results do NOT have `rerank_score` key.

Use the same `_make_result` helper pattern from RRFFusionTests in test_rag.py for building test result dicts.

**Append to tests/test_rag_eval.py:**

Add a new test class `EvalHybridRerankModeTests`:
- `test_eval_includes_hybrid_rerank_mode`: Create _FakeReranker and _FakeEmbedder, run `run_eval` with `reranker=fake_reranker`. Assert `"hybrid+rerank"` is in `report.modes`. Assert it has case_results.
- `test_eval_skips_hybrid_rerank_without_reranker`: Run `run_eval` with `reranker=None`. Assert `"hybrid+rerank"` mode exists in report.modes but its case_results have notes="skipped: no reranker".

Import `_FakeReranker` pattern: define it locally in the test file (same as _FakeEmbedder is defined locally in test_rag_eval.py rather than imported).
  </action>
  <verify>
`python -m pytest tests/test_rag_rerank.py -v` — all tests pass.
`python -m pytest tests/test_rag_eval.py -v` — all tests pass (including new hybrid+rerank tests).
`python -m pytest tests/test_rag.py -v` — existing tests still pass (no regressions).
  </verify>
  <done>All rerank tests pass deterministically. No real model downloads required. Existing test suite unbroken.</done>
</task>

<task type="auto">
  <name>Task 5: Update docs</name>
  <files>docs/LOCAL_RAG_WORKFLOW.md</files>
  <action>
Add a new section to `docs/LOCAL_RAG_WORKFLOW.md` after the existing "6) Evaluate retrieval quality" section (before "## Notes"):

```markdown
7) Rerank hybrid results (optional)

Cross-encoder reranking improves precision by rescoring the top-N fused results with a more powerful model. This is opt-in and runs fully offline.

```
python -m polyttool rag-query --question "What strategies did Alice use?" --hybrid --rerank --k 8
```

Specify a custom reranker model or rerank depth:
```
python -m polyttool rag-query --question "..." --hybrid --rerank \
    --rerank-model cross-encoder/ms-marco-MiniLM-L-6-v2 \
    --rerank-top-n 50 --k 8
```

Model files are cached under `kb/rag/models/` (gitignored). First run downloads the model; subsequent runs load from cache.

To include reranking in eval:
```
python -m polyttool rag-eval --suite docs/eval/sample_queries.jsonl \
    --rerank-model cross-encoder/ms-marco-MiniLM-L-6-v2
```

This adds a `hybrid+rerank` column to the eval report alongside vector, lexical, and hybrid.
```

Also update the "## Notes" section to add:
- `- Cross-encoder model cache lives in `kb/rag/models/` (gitignored). Delete this directory to force re-download.`
  </action>
  <verify>
Read `docs/LOCAL_RAG_WORKFLOW.md` and confirm the rerank section is present with correct CLI examples.
  </verify>
  <done>LOCAL_RAG_WORKFLOW.md documents rerank usage, model caching, and eval integration.</done>
</task>

</tasks>

<verification>
1. `python -m pytest tests/test_rag_rerank.py tests/test_rag_eval.py tests/test_rag.py -v` — all pass
2. `python -c "from polymarket.rag import BaseReranker, CrossEncoderReranker, rerank_results"` — imports succeed
3. `python -m polyttool rag-query --help` — shows --rerank, --rerank-top-n, --rerank-model
4. `python -m polyttool rag-eval --help` — shows --rerank-model, --rerank-top-n
5. `python -c "from polymarket.rag.eval import _MODES; modes = [m[0] for m in _MODES]; assert modes == ['vector', 'lexical', 'hybrid', 'hybrid+rerank']"` — 4 eval modes
</verification>

<success_criteria>
- reranker.py module exists with BaseReranker, CrossEncoderReranker, rerank_results
- query_index accepts reranker param, applies after any retrieval mode
- eval.py has 4 modes: vector, lexical, hybrid, hybrid+rerank
- CLI flags --rerank, --rerank-top-n, --rerank-model work on rag-query
- CLI flags --rerank-model, --rerank-top-n work on rag-eval
- All tests pass deterministically via _FakeReranker (no model download in CI)
- docs updated with rerank usage and model caching info
</success_criteria>
