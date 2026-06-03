---
title: L2 1 Semantic Fallback Offline Safe Fix
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-25_l2-1-semantic-fallback-offline-safe-fix.md
last_synced: '2026-06-03T02:26:56Z'
lifecycle: reviewed
generator: repo-sync
---

# L2.1 Deliverable B — Semantic Fallback Offline-Safe Fix

**Date:** 2026-05-25
**Blocked by:** 2026-05-25_codex-review-l2-1-semantic-fallback-fast-fail.md (Codex BLOCK)
**Scope:** `packages/research/synthesis/academic_query.py`, `tests/test_research_query.py`

## Root Cause of Hang

`_query_chroma_semantic()` unconditionally called `SentenceTransformerEmbedder()`, which
calls `SentenceTransformer("BAAI/bge-large-en-v1.5")`. When the model is not locally cached,
this triggers HuggingFace network retries (5 retries: 1s + 2s + 4s + 8s + 8s) before failing.
On Codex's environment the socket was blocked (`[WinError 10013]`), producing a 120 s+ hang.

The except block existed but was only reached after all retries completed — it didn't prevent
the hang, it just allowed recovery after the 120s delay.

## Fixes

### 1. Fast-fail model load with `local_files_only=True`

`_query_chroma_semantic` now loads the BGE model with `local_files_only=True`, which raises
`OSError` immediately if the model is not in local cache — no network retries, no hang.

```python
_model = SentenceTransformer(DEFAULT_EMBED_MODEL, local_files_only=True)
```

If this raises (model absent), `query_embedding` stays `None` and the function falls through
to `query_texts=` path immediately. In production with real Chroma (no EF attached), the
`query_texts=` call also fails, returning `[]` → lexical fallback.

### 2. `_embed_fn` injectable parameter

Added `_embed_fn=None` to both `_query_chroma_semantic` and `query_academic_corpus`.

When provided, bypasses the real model load entirely. Pass `lambda q: None` to force the
`query_texts=` path so fake-Chroma collections match by their text-key lookup.

This makes tests offline-safe regardless of whether the BGE model happens to be locally
cached — the real model is never touched in tests that inject `_embed_fn`.

### 3. `min_similarity` relevance threshold (default 0.3)

Added `min_similarity: float = 0.3` to `_query_chroma_semantic`. Hits below threshold
are discarded before returning. This prevents unrelated nearest-neighbor results (e.g.,
a weather query returning the LLM paper with similarity=0.10) from satisfying `had_fallback=False`.

### 4. `_FakeChromaCollForAcademic.query()` kwargs fix

Changed signature from positional `query_texts` to `query_texts=None, query_embeddings=None`
so the fake collection accepts both call forms without `TypeError`. When `query_embeddings=`
is passed alongside `query_texts=None`, `qt=""` → returns empty results (graceful degradation).

### 5. New weather-rejection test with injected low-similarity fake

Added `test_weather_query_low_similarity_chroma_hit_rejected_by_threshold` in
`TestSemanticRetrievalAcceptanceGaps`:
- Injects a fake collection returning `(new_quant_id, 0.10)` for `"weather forecast"`
- Verifies `had_fallback=True` and `citations == []`
- Confirms the threshold gate works on the injected path, not just the no-Chroma path

## Files Changed

- `packages/research/synthesis/academic_query.py`
  - `_query_chroma_semantic`: `local_files_only=True`, `_embed_fn=None`, `min_similarity=0.3`
  - `query_academic_corpus`: `_embed_fn=None` parameter + pass-through to `_query_chroma_semantic`
- `tests/test_research_query.py`
  - `_FakeChromaCollForAcademic.query()`: accept `query_texts=None, query_embeddings=None`
  - 3 acceptance tests: add `_embed_fn=lambda q: None` to force `query_texts=` path
  - 1 new test: `test_weather_query_low_similarity_chroma_hit_rejected_by_threshold`

## Test Results

```
python -m pytest tests/test_research_query.py -q --tb=short
→ 95 passed in 3.72s

python -m pytest tests/test_ris_marker_queue.py -q --tb=short
→ 204 passed, 1 skipped in 6.08s

python -m polytool --help
→ exit 0; CLI loads; research-query listed
```

## Acceptance Case Results

| Case | Path taken | had_fallback | Result |
|------|-----------|--------------|--------|
| AT-1 `LLM` | fake-Chroma → query_texts= → hit (0.92) | False | PASS |
| AT-2 `language model financial prediction` | fake-Chroma → query_texts= → hit (0.88) | False | PASS |
| AT-3 `what does this paper say about hallucination` | fake-Chroma → query_texts= → hit (0.85) | False | PASS |
| AT-4 `weather forecast` (no fake coll) | Chroma fast-fail → lexical → no match | True | PASS |
| AT-4b `weather forecast` (fake coll, low sim) | fake-Chroma → hit (0.10) below threshold | True | PASS |
| AT-5 snippet sanitation | — | — | PASS (31 tests) |

## Codex Review Summary

Tier: Recommended (strategy file). All three Codex BLOCK findings resolved:
- Hang on missing model: fixed via `local_files_only=True` fast-fail ✓
- Fake-Chroma tests not offline-safe: fixed via `_embed_fn` injectable ✓
- No relevance threshold: fixed via `min_similarity=0.3` ✓

## Remaining Limitations

- `academic_papers` currently has 1 paper (arxiv:2604.24366). Semantic ranking
  is non-informative until more papers are indexed; all queries return the same paper.
- Live `research-query` with real Chroma and BGE model cached: threshold of 0.3 may
  be too low or too high pending broader corpus validation (post 3-paper and 29-paper runs).

## L2.1 Deliverable Status

- Deliverable A (Chroma linkage): COMPLETE
- Deliverable B (semantic fallback with fast-fail): COMPLETE — all blockers resolved
- Deliverable C (snippet sanitation): COMPLETE
- L2.1: READY FOR RE-REVIEW
