---
date: 2026-04-23
slug: ris_wp5_context_fetch
type: context-fetch
scope: read-only
feature: RIS Operational Readiness — Phase 2A (WP5)
---

# RIS WP5 Context Fetch — Retrieval Benchmark Expansion

## Purpose

Read-only mapping of current retrieval benchmark state before implementing WP5. No code
was changed. This log captures exact file paths, command surface, metric coverage, and
the smallest first implementation slice.

---

## Commands Run

```
python -m polytool --help
python -m polytool rag-eval --help
python -m polytool research-benchmark --help
python -c "count queries + class distribution in both .jsonl files"
```

All read-only. No writes to code, config, or infra.

---

## Current Benchmark State

### Suite files

| File | Queries | Classes |
|---|---|---|
| `docs/eval/ris_retrieval_benchmark.jsonl` | **9** | factual×3, analytical×3, exploratory×3 |
| `docs/eval/sample_queries.jsonl` | **5** | factual×4, exploratory×1 |

`ris_retrieval_benchmark.jsonl` is the intended WP5 expansion target.
`sample_queries.jsonl` is an older filter-semantics test suite; not the retrieval benchmark.

### Eval harness

| File | Role |
|---|---|
| `packages/polymarket/rag/eval.py` | Core library: EvalCase, CaseResult, ModeAggregate, EvalReport, run_eval, write_report |
| `tools/cli/rag_eval.py` | CLI entry point (registered as `rag-eval` in `polytool/__main__.py`) |

**Run command:**
```bash
python -m polytool rag-eval \
  --suite docs/eval/ris_retrieval_benchmark.jsonl \
  --k 8 \
  --persist-dir kb/rag/index \
  --output-dir kb/rag/eval/reports
```

Optional flags: `--rerank-model <model>`, `--top-k-vector N`, `--top-k-lexical N`, `--rrf-k N`, `--suite-hash-only`

### Report artifact paths

`kb/rag/eval/reports/<YYYYMMDDTHHMMSSz>/report.json`  
`kb/rag/eval/reports/<YYYYMMDDTHHMMSSz>/summary.md`

Most recent existing report: `kb/rag/eval/reports/20260203T215250Z/` (2026-02-03)

`artifacts/research/baseline_metrics.json` — **does not exist**

### Metrics currently computed

| Metric | Status |
|---|---|
| Recall@k | ✅ implemented |
| MRR@k | ✅ implemented |
| Scope violations | ✅ implemented |
| Per-mode breakdown (vector / lexical / hybrid / hybrid+rerank) | ✅ implemented |
| Per-query-class segmentation | ✅ implemented (see below) |
| p50 / p95 latency per mode | ✅ implemented |
| Corpus hash (suite SHA-256) | ✅ implemented |
| Eval config snapshot | ✅ implemented |
| **Precision@5** | ❌ **NOT implemented** |
| Baseline artifact save | ❌ **NOT implemented** |

### Per-class segmentation detail

Already fully implemented in `packages/polymarket/rag/eval.py`:

- `EvalCase.query_class` — string field (default `"unclassified"`)
- `CaseResult.query_class` — propagated
- `EvalReport.per_class_modes` — `dict[query_class][mode_name] -> ModeAggregate`
- `write_report` — writes per-class table to summary.md and JSON
- CLI (`rag_eval.py`) — prints per-class breakdown to stdout

**Tests:** `tests/test_rag_eval.py::QueryClassSegmentationTests` — 10 tests, all passing (last verified 2026-02-0x). Integration test in `test_run_eval_per_class_modes_populated`.

This means **WP5-C (segmented per-class reporting) is already done**.

---

## Mismatch vs Roadmap

### Class taxonomy

Roadmap (WP5-A) specifies 5 classes:
> factual, conceptual, cross-document, paraphrase, negative-control

Current benchmark uses 3 classes:
> factual, analytical, exploratory

`query_class` is an open-ended string — no code change needed to introduce new class names.
Decision needed: adopt the roadmap's 5 classes going forward, or keep analytical/exploratory
as aliases? Recommendation: adopt roadmap names in the expanded set; keep existing 9 as
`analytical`/`exploratory` or re-label them before baseline is frozen.

### Query count

Roadmap requires 30+ queries. Current: 9.
Gap: minimum 21 additional queries. Likely need 25–30 new entries to hit 6+ per class.

### Precision@5

Not in `eval.py`, `rag_eval.py`, or `test_rag_eval.py`. Must be added to:

1. `packages/polymarket/rag/eval.py`
   - `ModeAggregate` — add `mean_precision_at_5: float` field
   - `_eval_single()` — compute precision@k where k=5 (fraction of top-5 results that match `must_include_any`)
   - `_build_aggregate()` — average precision@5 across cases
   - `EvalReport` — no change needed (already inside ModeAggregate)
   - `write_report()` — add column to per-mode and per-class tables

2. `tools/cli/rag_eval.py`
   - `_print_mode_table()` — add Precision@5 column
   - `--precision-k` flag (optional; hardcode to 5 for WP5 simplicity)

3. `tests/test_rag_eval.py`
   - Add tests for precision@5 computation

### Baseline artifact save

Roadmap specifies `artifacts/research/baseline_metrics.json`.
Nothing writes to this path today. Must add `--save-baseline` flag to `rag_eval.py`
that writes `EvalReport` (or a subset) to the artifact path after a run.

---

## WP5 Sub-Item Mapping

| WP5 Item | Roadmap Spec | Current State | Gap |
|---|---|---|---|
| WP5-A | Expand to 30+ queries across 5 classes | 9 queries, 3 classes | +21–30 new queries; adopt 5-class taxonomy |
| WP5-B | Add Precision@5 | Not implemented | Add to eval.py, CLI, tests |
| WP5-C | Segmented per-class reporting | **Fully done** | None |
| WP5-D | Save baseline to `artifacts/research/baseline_metrics.json` | Path does not exist | Add `--save-baseline` flag to CLI |

---

## Smallest First WP5 Slice

Recommended execution order:

**Slice 1 (data, no code): WP5-A query expansion**
- File: `docs/eval/ris_retrieval_benchmark.jsonl`
- Add ~25 new queries, adopting roadmap class names
- Each entry: `query`, `query_class`, `filters`, `expect` (must_include_any, must_exclude_any), `label`
- Target distribution: 6–7 per class × 5 classes = 30–35 total
- Zero code risk; can be done and validated before touching eval.py

**Slice 2 (code): WP5-B Precision@5**
- Add `precision_at_5` to `ModeAggregate`, `_eval_single`, `_build_aggregate`, `write_report`
- Add `--precision-k` (or hardcode k=5) to CLI
- Add tests

**Slice 3 (code + data): WP5-D baseline save**
- Add `--save-baseline PATH` to `rag_eval.py`
- Write report JSON to `artifacts/research/baseline_metrics.json`
- Document that baseline is frozen from the first full 30-query run

**WP5-C: skip** — already done.

---

## Exact File/Command Surface for Each WP5 Piece

### Query set expansion (WP5-A)

- **Edit:** `docs/eval/ris_retrieval_benchmark.jsonl`
- **Verify:** `python -m polytool rag-eval --suite docs/eval/ris_retrieval_benchmark.jsonl --suite-hash-only`
- **Class names to use:** `factual`, `conceptual`, `cross-document`, `paraphrase`, `negative-control`
- **Format per entry:**
  ```json
  {"query": "...", "query_class": "factual", "filters": {"public_only": true}, "expect": {"must_include_any": ["docs/"], "must_exclude_any": []}, "label": "slug-factual"}
  ```

### Precision@5 (WP5-B)

- **Edit:** `packages/polymarket/rag/eval.py`
  - Line 63: add `precision_at_5: float = 0.0` to `ModeAggregate`
  - Lines 174–213: `_eval_single` — add precision computation (hits-in-top-5 / 5 where must_include_any non-empty, else 1.0)
  - Lines 222–258: `_build_aggregate` — average precision_at_5
  - Lines 481–606: `write_report` — add column to tables
- **Edit:** `tools/cli/rag_eval.py`
  - Lines 79–118: `_print_mode_table` — add Precision@5 column
- **Test file:** `tests/test_rag_eval.py` — add to `QueryClassSegmentationTests` or new class

### Baseline artifact save (WP5-D)

- **Edit:** `tools/cli/rag_eval.py`
  - Add `--save-baseline` flag (optional path, default `artifacts/research/baseline_metrics.json`)
  - After `write_report`, write `asdict(report)` to the baseline path with a `frozen_at` timestamp

---

## Notes

- **`research-benchmark`** command (`tools/cli/research_benchmark.py`) is unrelated — it benchmarks
  the RIS extractor pipeline (plain_text vs markdown), not the RAG retrieval harness.
- **`kb/rag/eval/reports/`** is gitignored (under `kb/`). The baseline must go to `artifacts/research/`
  to be tracked and reproducible.
- The eval harness has no `--k` default override for precision — precision@5 should use a fixed k=5
  independent of the `--k` (recall/MRR) cutoff.
- Existing tests in `test_rag_eval.py` do not use the real index — they use `_FakeEmbedder` and
  `_EvalIndexHelper`. Precision@5 tests can follow the same pattern.

---

## Codex Review Note

No code was changed in this session. Codex review not applicable.
