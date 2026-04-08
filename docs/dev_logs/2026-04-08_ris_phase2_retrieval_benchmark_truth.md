# Dev Log: RIS Phase 2 Retrieval Benchmark Truth

**Date:** 2026-04-08
**Task:** quick-260408-oz0 — Finish Phase 2 Retrieval Benchmark Truth
**Status:** Complete
**Spec:** SPEC-ris-phase2-operational-contracts.md, Item 7

---

## What Was Built

Extended the existing RAG eval harness to produce Phase 2 segmented retrieval benchmark
metrics by query class. The operator can now see retrieval quality broken down by class
(factual, analytical, exploratory) across all four retrieval modes (vector, lexical, hybrid,
hybrid+rerank).

### Files Modified / Created

| File | Change |
|------|--------|
| `packages/polymarket/rag/eval.py` | Extended with query_class segmentation, baseline artifact metadata, `_build_aggregate()` helper |
| `tools/cli/rag_eval.py` | Extended with per-class breakdown output, `--suite-hash-only` flag |
| `docs/eval/ris_retrieval_benchmark.jsonl` | New Phase 2 benchmark suite (9 cases, 3 classes) |
| `docs/eval/sample_queries.jsonl` | Annotated existing 5 cases with query_class |
| `tests/test_rag_eval.py` | Added QueryClassSegmentationTests and LoadSuiteQueryClassTests (35 tests total) |

---

## Query Classes

Three classes are defined for the Phase 2 benchmark:

| Class | Description | Example |
|-------|-------------|---------|
| `factual` | Direct lookup — specific expected content | "What is the ClickHouse analytics storage schema?" |
| `analytical` | Synthesis across multiple documents | "How does the market maker strategy handle inventory risk?" |
| `exploratory` | Open-ended research | "What strategies exist for prediction market profitability?" |

Queries without a `query_class` field default to `"unclassified"` (backward compatible).

---

## Required Metrics Now Tracked

Every `ModeAggregate` (both overall and per-class) now reports all 8 Phase 2 required metrics:

| Metric | Description |
|--------|-------------|
| `query_count` | Number of cases in this aggregate |
| `mean_recall_at_k` | Mean recall@k across cases |
| `mean_mrr_at_k` | Mean MRR@k across cases |
| `total_scope_violations` | Total count of must_exclude_any matches |
| `queries_with_violations` | Number of cases with at least one violation |
| `mean_latency_ms` | Mean query latency in milliseconds |
| `p50_latency_ms` | Median (P50) query latency |
| `p95_latency_ms` | P95 query latency |

---

## Baseline Artifact Structure

`report.json` now includes three new top-level keys for reproducibility:

```json
{
  "per_class_modes": {
    "factual": {
      "lexical": { "query_count": 3, "mean_recall_at_k": 0.8, ... },
      "vector":  { ... },
      "hybrid":  { ... }
    },
    "analytical": { ... },
    "exploratory": { ... }
  },
  "corpus_hash": "sha256-hex-of-suite-file-bytes",
  "eval_config": {
    "k": 8,
    "top_k_vector": 25,
    "top_k_lexical": 25,
    "rrf_k": 60,
    "rerank_top_n": 50,
    "embedder_model": "...",
    "reranker_model": null,
    "suite_path": "docs/eval/ris_retrieval_benchmark.jsonl"
  }
}
```

`summary.md` now includes a **Per-Query-Class Results** section with a table per class.

---

## How to Run

### Run Phase 2 benchmark eval

```bash
python -m polytool rag-eval --suite docs/eval/ris_retrieval_benchmark.jsonl
```

### Run with reranker

```bash
python -m polytool rag-eval \
  --suite docs/eval/ris_retrieval_benchmark.jsonl \
  --rerank-model cross-encoder/ms-marco-MiniLM-L-6-v2
```

### Verify corpus identity (without running eval)

```bash
python -m polytool rag-eval --suite docs/eval/ris_retrieval_benchmark.jsonl --suite-hash-only
```

This prints the SHA-256 hash of the suite file. Compare against the `corpus_hash` field in
any existing `report.json` to confirm the suite has not changed.

---

## Reproducibility

Same suite hash + same `eval_config` = structurally identical report (same queries, same
metrics, same segmentation). The `corpus_hash` in every `report.json` provides tamper
evidence and allows operators to confirm a baseline was produced from a specific suite version.

---

## Backward Compatibility

- `load_suite()` defaults `query_class` to `"unclassified"` when the field is absent.
  Existing suite files (e.g., `sample_queries.jsonl` before this change) continue to load
  without modification.
- `run_eval()` signature is unchanged. All new parameters use default values.
- `ModeAggregate` now has `query_count`, `p50_latency_ms`, `p95_latency_ms` with defaults
  of `0` / `0.0`, so existing code constructing ModeAggregate directly still works.

---

## Tests

35 tests in `tests/test_rag_eval.py`, all passing. New test classes:

- `QueryClassSegmentationTests` — 11 tests covering field presence, per-class mode population,
  report JSON/markdown output, and integration with a real (fake) index.
- `LoadSuiteQueryClassTests` — 2 tests covering JSONL parsing with and without `query_class`.

---

## Codex Review

Tier: Skip (eval harness + docs, no execution or risk-sensitive paths). No review required.

---

## Open Questions / Next Steps

- Run the benchmark against a live local index to establish actual recall/MRR baselines.
  Current suite queries are designed around known repo docs; the index must be populated
  for meaningful numbers.
- Consider adding per-class recall targets to the Phase 2 spec once baselines are measured.
- `sample_queries.jsonl` now has query_class annotations; its `public_only` filter cases
  require a populated index to produce non-zero recall.
