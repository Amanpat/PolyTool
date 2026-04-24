---
date: 2026-04-23
slug: ris_wp5b_codex_verification
type: verification
scope: packages/polymarket/rag/eval.py, tools/cli/rag_eval.py, tests/test_rag_eval.py, docs/dev_logs/2026-04-23_ris_wp5b_precision_at_5.md
feature: RIS Phase 2A - WP5-B Precision@5 verification
---

# RIS WP5-B Codex Verification

## Verdict

WP5-B is **not ready to sign off**.

Precision@5 is wired into the aggregate report surfaces, per-class report surfaces, and CLI output, and I found no WP5-D baseline-save scope in the inspected files. But there is one blocking correctness issue: the harness claims P@5 is independent of `--k`, while `run_eval()` still retrieves only `k` results. For `--k` values below 5, the harness cannot compute a true Precision@5.

## Files Inspected

- `packages/polymarket/rag/eval.py`
- `tools/cli/rag_eval.py`
- `tests/test_rag_eval.py`
- `docs/dev_logs/2026-04-23_ris_wp5b_precision_at_5.md`
- `packages/polymarket/rag/query.py` (inspected to verify whether retrieval depth actually supports fixed P@5)

## What Verified Cleanly

- `packages/polymarket/rag/eval.py` adds `precision_at_5` on `CaseResult` and `mean_precision_at_5` on `ModeAggregate`.
- Aggregate markdown reporting includes `P@5` in the per-mode summary table.
- Per-class markdown reporting includes `P@5` when `per_class_modes` is present.
- Per-case markdown detail includes `p@5=...`.
- `tools/cli/rag_eval.py` adds `P@5` to `_print_mode_table()`, and the same helper is used for both overall and per-class CLI output.
- No WP5-D baseline-save scope was found in the inspected WP5-B files.

## Commands Run And Exact Results

```powershell
git status --short
```

```text
 M .env.example
 M docker-compose.yml
 M docs/CURRENT_DEVELOPMENT.md
 M docs/INDEX.md
MM docs/dev_logs/2026-04-22_hermes-vera-agent.md
 M docs/eval/ris_retrieval_benchmark.jsonl
 M docs/obsidian-vault/.obsidian/workspace.json
 M docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
 M infra/n8n/import_workflows.py
 M packages/polymarket/rag/eval.py
 M tests/test_rag_eval.py
 M tools/cli/rag_eval.py
?? docs/dev_logs/2026-04-23_operator-hermes-baseline.md
?? docs/dev_logs/2026-04-23_polytool-dev-logs-skill.md
?? docs/dev_logs/2026-04-23_polytool-status-skill.md
?? docs/dev_logs/2026-04-23_ris_parallel_wp3d_wp4a_codex_verification.md
?? docs/dev_logs/2026-04-23_ris_parallel_wp3e_wp4b_codex_verification.md
?? docs/dev_logs/2026-04-23_ris_parallel_wp4c_wp4bactivate_codex_verification.md
?? docs/dev_logs/2026-04-23_ris_parallel_wp4d_truthsync_codex_verification.md
?? docs/dev_logs/2026-04-23_ris_parallel_wp4d_truthsync_fix_codex_verification.md
?? docs/dev_logs/2026-04-23_ris_phase2a_closeout_readiness.md
?? docs/dev_logs/2026-04-23_ris_phase2a_closeout_wp5_codex_verification.md
?? docs/dev_logs/2026-04-23_ris_wp4_monitoring_truth_sync.md
?? docs/dev_logs/2026-04-23_ris_wp4a_clickhouse_ddl.md
?? docs/dev_logs/2026-04-23_ris_wp4b_activation_plumbing.md
?? docs/dev_logs/2026-04-23_ris_wp4c_grafana_dashboard.md
?? docs/dev_logs/2026-04-23_ris_wp4d_scope_fix.md
?? docs/dev_logs/2026-04-23_ris_wp4d_scope_fix_codex_verification.md
?? docs/dev_logs/2026-04-23_ris_wp4d_stale_pipeline_alert.md
?? docs/dev_logs/2026-04-23_ris_wp5_context_fetch.md
?? docs/dev_logs/2026-04-23_ris_wp5a_codex_verification.md
?? docs/dev_logs/2026-04-23_ris_wp5a_queryset_expansion.md
?? docs/dev_logs/2026-04-23_ris_wp5b_precision_at_5.md
?? docs/features/polytool_dev_logs_skill.md
?? docs/features/polytool_status_skill.md
?? docs/features/vera_hermes_operator_baseline.md
?? infra/clickhouse/initdb/28_n8n_execution_metrics.sql
?? infra/grafana/dashboards/ris-pipeline-health.json
?? infra/grafana/provisioning/alerting/
?? scripts/test_vera_dev_logs_commands.sh
?? scripts/test_vera_status_commands.sh
?? scripts/vera_hermes_healthcheck.sh
?? skills/
```

```powershell
git log --oneline -5
```

```text
d9e9f8b feat(ris): WP3-E - daily digest path at 09:00 UTC with WP3-C structured embed
b2ad984 feat(ris): WP4-B -- hourly n8n execution metrics collector workflow
2eaefd8 feat(ris): WP3-D - Discord embed enrichment with per-pipeline fields
129d376 RIS improvement
a610f18 Hermes Agent containerization
```

```powershell
python -m polytool --help
```

```text
Exit 0. CLI loads and lists the `rag-eval` command.
```

```powershell
python -m pytest tests/test_rag_eval.py::PrecisionAt5UnitTests -q --tb=short
```

```text
collected 16 items
tests\test_rag_eval.py ................                                  [100%]
16 passed in 0.40s
```

```powershell
$matches = Select-String -Path tools\cli\rag_eval.py,packages\polymarket\rag\eval.py,tests\test_rag_eval.py -Pattern "save-baseline|baseline_metrics|frozen_at"; if ($matches) { $matches | ForEach-Object { "{0}:{1}:{2}" -f $_.Path, $_.LineNumber, $_.Line.Trim() } } else { "NO_MATCHES" }
```

```text
NO_MATCHES
```

```powershell
@'
import os, sys
sys.path.insert(0, os.path.join(os.getcwd(), 'packages'))
from polymarket.rag.eval import EvalCase, run_eval
import polymarket.rag.eval as eval_mod

calls = []

def fake_query_index(**kwargs):
    k = kwargs["k"]
    calls.append(k)
    return [
        {
            "file_path": "alice/doc.md",
            "chunk_id": "a" * 64,
            "doc_id": "b" * 64,
            "score": 1.0,
            "snippet": "x",
            "metadata": {},
        }
        for _ in range(k)
    ]

eval_mod.query_index = fake_query_index
report = run_eval(
    [EvalCase(query="q", filters={}, must_include_any=["alice"], must_exclude_any=[])],
    k=3,
    embedder=object(),
    reranker=object(),
)
agg = report.modes["vector"]
print(f"called_k={calls[0]}")
print(f"p5={agg.case_results[0].precision_at_5:.3f}")
print(f"results={agg.case_results[0].result_count}")
'@ | python -
```

```text
called_k=3
p5=0.600
results=3
```

## Blocking Issues

1. `packages/polymarket/rag/eval.py` documents Precision@5 as a fixed cutoff independent of `k` (`_PRECISION_K = 5`, comment at line 187, slice at lines 220-227), but `run_eval()` still passes the user-supplied `k` directly into `query_index()` at line 369.
2. `packages/polymarket/rag/query.py` then truncates retrieval depth to `k` (`output_limit=k` at line 294 and `final = fused[:k]` at line 347), so any run with `--k < 5` under-fetches and cannot produce a true Precision@5.
3. The current WP5-B tests do not cover this edge. The new precision tests call `_eval_single(..., 8)` repeatedly (for example at `tests/test_rag_eval.py` lines 952, 964, 976, 988, 1000, and 1015), so the under-fetch bug passes the current test slice unnoticed.

## Non-Blocking Issues

- None.

## Recommendation

WP5-D is **not** the next correct work unit yet.

The next correct work unit is a small WP5-B follow-up to make P@5 actually independent of `--k`, then retest. The cheapest acceptable fix is one of:

- Enforce `--k >= 5` in the CLI and document that contract explicitly, or
- Retrieve `max(k, 5)` results inside the eval harness, then compute Recall/MRR on the top `k` subset and Precision on the top 5 subset.

After that fix lands and the edge is covered by tests, WP5-D baseline-save is the next correct work unit.
