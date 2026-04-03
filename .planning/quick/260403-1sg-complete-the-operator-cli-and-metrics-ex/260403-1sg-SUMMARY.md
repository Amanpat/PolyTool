---
phase: quick-260403-1sg
plan: "01"
subsystem: research-ris
tags: [ris, operator-cli, metrics, local-first]
dependency_graph:
  requires:
    - packages/research/evaluation/artifacts.py
    - packages/research/ingestion/acquisition_review.py
    - packages/polymarket/rag/knowledge_store.py
    - packages/research/synthesis/precheck_ledger.py
    - packages/research/synthesis/report_ledger.py
  provides:
    - packages/research/metrics.py
    - tools/cli/research_stats.py
    - research-stats CLI command
  affects:
    - polytool/__main__.py
    - docs/CURRENT_STATE.md
tech_stack:
  added: []
  patterns:
    - local-first JSONL aggregation
    - inline _iter_jsonl() helper to avoid circular imports
    - argparse subcommand pattern (matching research_report.py)
key_files:
  created:
    - packages/research/metrics.py
    - tools/cli/research_stats.py
    - tests/test_ris_ops_metrics.py
    - docs/features/FEATURE-ris-ops-cli-and-metrics.md
    - docs/dev_logs/2026-04-03_ris_r4_ops_cli_and_metrics.md
  modified:
    - polytool/__main__.py
    - docs/CURRENT_STATE.md
decisions:
  - "Inline _iter_jsonl() in metrics.py to avoid circular imports through synthesis package"
  - "Acquisition errors are counted exclusively (not in new/cached) for clean operator semantics"
  - "Handle both event_type='precheck_run' (real ledger) and 'precheck' (plan spec) for robustness"
  - "ClickHouse write path deferred to RIS_06 v2 per plan"
metrics:
  duration: "~20 minutes"
  completed_date: "2026-04-03"
  tasks_completed: 2
  files_created: 5
  files_modified: 2
  tests_added: 15
---

# Phase quick-260403-1sg Plan 01: RIS Operator CLI and Metrics Export Summary

**One-liner:** Local-first RIS metrics aggregator with `research-stats summary/export` CLI reading from KS SQLite, eval_artifacts, precheck_ledger, report_index, and acquisition_review JSONL.

## Tasks Completed

| Task | Name | Commit | Files |
|---|---|---|---|
| 1 | Build RisMetricsSnapshot aggregation module | f81fd06 | packages/research/metrics.py, tests/test_ris_ops_metrics.py |
| 2 | research-stats CLI, __main__ wiring, feature doc, dev log, CURRENT_STATE | 0841b8e | tools/cli/research_stats.py, polytool/__main__.py, docs/features/FEATURE-ris-ops-cli-and-metrics.md, docs/dev_logs/2026-04-03_ris_r4_ops_cli_and_metrics.md, docs/CURRENT_STATE.md |

## What Was Built

### `packages/research/metrics.py`
- `RisMetricsSnapshot` dataclass with 12 fields (all int/str/dict, JSON-serializable)
- `collect_ris_metrics(*, db_path, eval_artifacts_dir, precheck_ledger_path, report_dir, acquisition_review_dir)` -- all paths injectable for testing
- `format_metrics_summary(snapshot)` -- multi-section human-readable string
- Inline `_iter_jsonl()` helper (avoids circular imports)
- Reads: KS SQLite via stdlib sqlite3, eval artifacts via `load_eval_artifacts()`, precheck/report/acquisition via JSONL iteration

### `tools/cli/research_stats.py`
- `research-stats summary` -- human-readable or `--json` output
- `research-stats export` -- writes `artifacts/research/metrics_snapshot.json`
- Both subcommands accept 5 path override flags
- `main(argv) -> int` following established research_report.py pattern

### `polytool/__main__.py` (3-point edit)
1. `research_stats_main = _command_entrypoint("tools.cli.research_stats")`
2. `"research-stats": "research_stats_main"` in `_COMMAND_HANDLER_NAMES`
3. Usage line in RIS section of `print_usage()`

## Verification Results

```
python -m polytool research-stats summary
# -> Prints full 5-section snapshot, exit 0

python -m polytool research-stats summary --json
# -> Valid JSON with all 12 keys

python -m polytool research-stats export --out artifacts/research/metrics_snapshot.json
# -> "Metrics exported to: artifacts\research\metrics_snapshot.json"

python -m polytool --help | grep research-stats
# -> "  research-stats            Operator metrics snapshot and local-first export for RIS pipeline"

python -m pytest tests/test_ris_ops_metrics.py -v
# -> 15 passed in 0.72s

python -m pytest tests/ -q --tb=line | tail -3
# -> 8 failed, 3549 passed (8 pre-existing failures unrelated to this work)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed acquisition_new double-counting on errored records**
- **Found during:** Task 1 GREEN phase, test_acquisition_review_counts
- **Issue:** Records with `error != None` were counted in both `acquisition_errors` AND `acquisition_new`/`acquisition_cached`, causing acquisition_new=4 when test expected 3.
- **Fix:** Error check is now exclusive -- errored records go only to `acquisition_errors`, not to new/cached counts.
- **Files modified:** packages/research/metrics.py
- **Commit:** f81fd06

**2. [Rule 1 - Robustness] Handle both "precheck_run" and "precheck" event_type values**
- **Found during:** Task 1 implementation -- plan said `event_type == "precheck"` but actual ledger writes `"precheck_run"`
- **Fix:** Metrics module accepts both values. Tests use `"precheck_run"` (the real format).
- **Files modified:** packages/research/metrics.py
- **Commit:** f81fd06

## Known Stubs

None. All fields in `RisMetricsSnapshot` are wired to real data sources. The "zeros" visible in a fresh environment reflect genuinely empty artifact directories, not placeholder stubs.

## Self-Check: PASSED

- [x] packages/research/metrics.py exists and imports cleanly
- [x] tools/cli/research_stats.py exists
- [x] tests/test_ris_ops_metrics.py exists -- 15 tests pass
- [x] docs/features/FEATURE-ris-ops-cli-and-metrics.md exists
- [x] docs/dev_logs/2026-04-03_ris_r4_ops_cli_and_metrics.md exists
- [x] Commits f81fd06 and 0841b8e exist in git log
- [x] `python -m polytool research-stats summary` exits 0 with output
- [x] `python -m polytool --help | grep research-stats` returns the usage line
- [x] Full suite: 3549 passed, 0 new failures introduced
