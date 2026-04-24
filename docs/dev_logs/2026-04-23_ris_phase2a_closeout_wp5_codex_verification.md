---
date: 2026-04-23
slug: ris_phase2a_closeout_wp5_codex_verification
type: verification
scope: read-only
---

# RIS Phase 2A Closeout + WP5 Codex Verification

## Verdict

- Lane 1 is mostly truthful on closeout status: `docs/CURRENT_DEVELOPMENT.md` now reflects WP1-WP4 as complete, Hermes remains out of scope, and no code/config/infra edits were made by that lane.
- Lane 1 is not fully narrow/truth-synced in its WP5 handoff text: it still carries WP5-C as future work and mixes in stale benchmark-path guidance.
- Lane 2 is materially accurate and grounded in current repo surfaces. No blocking drift found in the WP5 harness mapping.

## Files inspected

- `docs/CURRENT_DEVELOPMENT.md`
- `docs/dev_logs/2026-04-23_ris_phase2a_closeout_readiness.md`
- `docs/dev_logs/2026-04-23_ris_wp5_context_fetch.md`
- `docs/eval/ris_retrieval_benchmark.jsonl`
- `docs/eval/sample_queries.jsonl`
- `packages/polymarket/rag/eval.py`
- `tools/cli/rag_eval.py`
- `tests/test_rag_eval.py`
- `tools/cli/research_benchmark.py`
- `polytool/__main__.py`
- `infra/clickhouse/initdb/28_n8n_execution_metrics.sql`
- `infra/n8n/workflows/ris-n8n-metrics-collector.json`
- `infra/grafana/dashboards/ris-pipeline-health.json`
- `infra/grafana/provisioning/alerting/ris-stale-pipeline.yaml`

## Commands run + exact results

- `git status --short`
  Result: dirty tree. Relevant verification lines were `M docs/CURRENT_DEVELOPMENT.md`, `?? docs/dev_logs/2026-04-23_ris_phase2a_closeout_readiness.md`, and `?? docs/dev_logs/2026-04-23_ris_wp5_context_fetch.md`. Concurrent unrelated lane changes were also present under `infra/` and other paths.
- `git log --oneline -5`
  Result:
  `d9e9f8b feat(ris): WP3-E - daily digest path at 09:00 UTC with WP3-C structured embed`
  `b2ad984 feat(ris): WP4-B -- hourly n8n execution metrics collector workflow`
  `2eaefd8 feat(ris): WP3-D - Discord embed enrichment with per-pipeline fields`
  `129d376 RIS improvement`
  `a610f18 Hermes Agent containerization`
- `python -m polytool --help`
  Result: exit 0. CLI loaded and listed both `rag-eval` and `research-benchmark`.
- `python -m polytool rag-eval --help`
  Result: exit 0. CLI exposes `--suite`, `--k`, `--output-dir`, and `--suite-hash-only`. No `--save-baseline` flag exists today.
- `python -m polytool research-benchmark --help`
  Result: exit 0. This command is the extractor benchmark harness with `--fixtures-dir`, `--extractors`, `--output-dir`, and `--json`.
- Query-count checks on the JSONL suites
  Result for `docs/eval/ris_retrieval_benchmark.jsonl`: `9` total queries with `analytical:3`, `exploratory:3`, `factual:3`.
  Result for `docs/eval/sample_queries.jsonl`: `5` total queries with `exploratory:1`, `factual:4`.
- `if (Test-Path artifacts/research/baseline_metrics.json) { 'exists' } else { 'missing' }`
  Result: `missing`
- `Get-ChildItem kb/rag/eval/reports | Sort-Object Name | Select-Object -Last 5 -ExpandProperty Name`
  Result: existing report dirs were `20260203T193827Z` and `20260203T215250Z`.
- Benchmark-path existence check
  Result: `packages/research=True`, `packages/research/rag=False`, `packages/research/evaluation=True`, `config/ris_eval_config.json=True`, `kb/rag/knowledge/knowledge.sqlite3=True`, `packages/polymarket/rag/eval.py=True`, `tools/cli/rag_eval.py=True`, `tools/cli/research_benchmark.py=True`.
- Query-class test count check inside `tests/test_rag_eval.py`
  Result: `QueryClassSegmentationTests` currently contains `11` `test_` methods.

## Lane 1 findings

### Blocking

- None.

### Non-blocking

- `docs/CURRENT_DEVELOPMENT.md:66` says the next WP5 step is to "add Precision@5, per-class reporting, and save `artifacts/research/baseline_metrics.json`." That overstates remaining work. Per-class segmentation/reporting is already implemented in `packages/polymarket/rag/eval.py` and surfaced by `tools/cli/rag_eval.py`, so WP5-C should not be carried forward as pending scope.
- `docs/dev_logs/2026-04-23_ris_phase2a_closeout_readiness.md:114-122` maps the retrieval benchmark to `packages/research/` and specifically cites `packages/research/rag/`, which does not exist. The live harness surface for WP5 work is `packages/polymarket/rag/eval.py` plus `tools/cli/rag_eval.py`. This is prose-level scope creep in the handoff section, not file-level scope creep in the landed changes.
- File-scope check: no unrelated file churn was introduced by lane 1 itself. Its landed footprint is the `docs/CURRENT_DEVELOPMENT.md` update plus the closeout dev log.

## Lane 2 findings

### Blocking

- None.

### Non-blocking

- `docs/dev_logs/2026-04-23_ris_wp5_context_fetch.md:96` says `tests/test_rag_eval.py::QueryClassSegmentationTests` has 10 tests. The current file has 11 `test_` methods in that class. This does not change the harness mapping, but the count should be corrected if the log is reused as implementation context.

## Recommendation on the first WP5 implementation prompt

- Use lane 2, not lane 1's handoff prose, as the source of truth for WP5 prompting.
- Treat WP5-C as already done. The first prompt should be limited to WP5-A only: expand `docs/eval/ris_retrieval_benchmark.jsonl` from 9 cases to 30+ cases using the roadmap taxonomy `factual`, `conceptual`, `cross-document`, `paraphrase`, and `negative-control`.
- Keep that first slice data-only. Verify the suite shape with `python -m polytool rag-eval --suite docs/eval/ris_retrieval_benchmark.jsonl --suite-hash-only`.
- Explicitly exclude `research-benchmark`, provider-routing work, infra, and monitoring from the first prompt.
- After the suite expansion lands, do a second WP5 prompt for WP5-B (`Precision@5`) and WP5-D (baseline artifact save to `artifacts/research/baseline_metrics.json`).
