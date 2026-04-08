---
phase: quick-260408-oz0
plan: 01
subsystem: rag-eval
tags: [rag, eval, phase2, retrieval-benchmark, query-class]
key-files:
  created:
    - docs/eval/ris_retrieval_benchmark.jsonl
    - docs/dev_logs/2026-04-08_ris_phase2_retrieval_benchmark_truth.md
  modified:
    - packages/polymarket/rag/eval.py
    - tools/cli/rag_eval.py
    - docs/eval/sample_queries.jsonl
    - tests/test_rag_eval.py
decisions:
  - "Use query_class field with default 'unclassified' for full backward compatibility with existing suites"
  - "Extract _build_aggregate() helper to share aggregation logic between overall and per-class modes"
  - "corpus_hash is SHA-256 of raw suite file bytes; empty string if suite_path is not a real file (e.g. test runs)"
  - "Per-class modes structured as per_class_modes[query_class][mode_name] for O(1) lookup by operators"
metrics:
  duration_minutes: 25
  completed_date: "2026-04-08"
  tasks_completed: 2
  files_modified: 6
---

# Phase quick-260408-oz0 Plan 01: Phase 2 Retrieval Benchmark Truth Summary

**One-liner:** Per-query-class (factual/analytical/exploratory) RAG eval segmentation with corpus_hash and eval_config baseline metadata in report.json and summary.md.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Extend eval harness with query_class segmentation and baseline metadata | 4dcc05a | packages/polymarket/rag/eval.py, tests/test_rag_eval.py |
| 2 | Create Phase 2 benchmark suite, extend CLI output, write dev log | 0c1e56a | docs/eval/ris_retrieval_benchmark.jsonl, docs/eval/sample_queries.jsonl, tools/cli/rag_eval.py, docs/dev_logs/2026-04-08_ris_phase2_retrieval_benchmark_truth.md |

---

## What Was Built

### Task 1: eval.py extension

Extended `packages/polymarket/rag/eval.py` with:

- `EvalCase.query_class: str = "unclassified"` — parsed from JSONL `query_class` field
- `CaseResult.query_class: str = "unclassified"` — propagated from EvalCase in run_eval()
- `ModeAggregate` — added `query_count`, `p50_latency_ms`, `p95_latency_ms` (all 8 Phase 2 required metrics now present)
- `EvalReport` — added `per_class_modes`, `corpus_hash`, `eval_config`
- `_build_aggregate(case_list)` helper — shared aggregation for overall and per-class modes
- `load_suite()` — parses `query_class` from JSONL with default fallback
- `run_eval()` — builds per-class aggregates, computes corpus_hash from file bytes, builds eval_config
- `write_report()` — JSON includes per_class_modes/corpus_hash/eval_config; markdown adds "Per-Query-Class Results" section

### Task 2: benchmark suite and CLI

- `docs/eval/ris_retrieval_benchmark.jsonl` — 9 cases: 3 factual, 3 analytical, 3 exploratory
- `docs/eval/sample_queries.jsonl` — existing 5 cases annotated with query_class
- `tools/cli/rag_eval.py` — per-class breakdown printed after overall table; `--suite-hash-only` flag; corpus_hash and eval_config footer
- `docs/dev_logs/2026-04-08_ris_phase2_retrieval_benchmark_truth.md` — full operator guide

---

## Verification

- `python -m polytool --help` — CLI loads cleanly
- `python -m pytest tests/test_rag_eval.py -x -q` — 35 passed, 0 failed
- Benchmark JSONL verified: 9 cases across {analytical, exploratory, factual}
- Pre-existing flaky test `test_ris_monitoring.py::TestMetricsPhase2::test_provider_route_distribution` fails only in full-suite ordering — passes in isolation — unrelated to this task

---

## Deviations from Plan

None. Plan executed exactly as written.

---

## Known Stubs

None. The eval harness produces real metrics from a real index. The benchmark suite queries
reference `docs/` path patterns that only produce non-zero recall when a populated local
index exists — this is expected and documented in the dev log.

---

## Threat Flags

None. No new network endpoints, auth paths, or trust-boundary crossings introduced.
Corpus hash in report.json provides tamper evidence for JSONL suite files (T-oz0-01, accepted).

---

## Self-Check: PASSED

Files exist:
- packages/polymarket/rag/eval.py — FOUND
- tools/cli/rag_eval.py — FOUND
- docs/eval/ris_retrieval_benchmark.jsonl — FOUND
- docs/eval/sample_queries.jsonl — FOUND
- tests/test_rag_eval.py — FOUND
- docs/dev_logs/2026-04-08_ris_phase2_retrieval_benchmark_truth.md — FOUND

Commits exist:
- 4dcc05a — FOUND (Task 1)
- 0c1e56a — FOUND (Task 2)
