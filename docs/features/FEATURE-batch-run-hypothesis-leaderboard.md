# Feature: Batch-Run Harness + Hypothesis Leaderboard (Roadmap 5.5)

## Summary

`batch-run` lets you run the same PolyTool scan workflow for many users and produce one combined leaderboard that shows which hypothesis segments repeat across users and how strong they are by weighted CLV/beat-close metrics. Outputs are deterministic, explainable, and offline-testable.

## CLI Usage

```bash
python -m polytool batch-run \
  --users users.txt \
  --api-base-url "http://127.0.0.1:8000" \
  --ingest-positions \
  --compute-pnl \
  --enrich-resolutions \
  --warm-clv-cache \
  --compute-clv \
  --debug-export
```

Batch options:

- `--users <path>`: file with one handle per line (required unless `--aggregate-only`)
- `--output-root <path>`: defaults to `artifacts/research/batch_runs`
- `--batch-id <id>`: optional custom batch id (default `uuid4`)
- `--continue-on-error/--no-continue-on-error`: defaults to continue
- `--max-users <N>`: optional safety cap
- `--aggregate-only`: skip scanning, re-aggregate from existing run roots
- `--run-roots <path>`: directory of run roots or file listing them (required with `--aggregate-only`)
- `--workers <N>`: parallel scan threads (default 1, sequential)

Supported scan pass-through flags (reused from `scan` parser):

- `--api-base-url`
- `--ingest-positions`
- `--compute-pnl`
- `--enrich-resolutions`
- `--debug-export`
- `--warm-clv-cache`
- `--compute-clv`

## Aggregate-Only Mode

Re-aggregate an existing set of scan run roots without re-running scans:

```bash
# Point at a directory of run roots
python -m polytool batch-run \
  --aggregate-only \
  --run-roots artifacts/research/batch_runs/2026-02-20/<batch_id>/

# Or point at a file listing run root paths (one per line)
python -m polytool batch-run \
  --aggregate-only \
  --run-roots my_run_roots.txt
```

`--run-roots` accepts:
- A directory: all immediate subdirectories are treated as run roots.
- A file: each non-blank, non-comment line is a path to a run root.

`--users` is not required in aggregate-only mode.

## Parallel Scan Workers

```bash
python -m polytool batch-run \
  --users users.txt \
  --workers 4 \
  --compute-clv
```

`--workers N` runs per-user scans in N parallel threads. Output ordering is always deterministic (matches the order users appear in `--users`). `--continue-on-error` is respected under parallel execution.

## Output Layout

```
artifacts/research/batch_runs/YYYY-MM-DD/<batch_id>/
  batch_manifest.json
  hypothesis_leaderboard.json
  hypothesis_leaderboard.md
  per_user_results.json
```

`batch_manifest.json` is the traceability artifact for the batch run and records output paths plus per-user run roots/status.

## JSON Schema Overview

`hypothesis_leaderboard.json` contains:

- Batch envelope: `batch_id`, `created_at`, attempted/succeeded/failed counts
- `inputs`: `users_file` and scan pass-through flags
- `per_user`: status, run roots, coverage summary, and top candidates per user
- `segments`: aggregated segment rows with
  - persistence (`users_with_segment`)
  - totals (`total_count`, `total_notional_weight_used`)
  - weighted scores:
    - `notional_weighted_avg_clv_pct`
    - `notional_weighted_beat_close_rate`
    - `count_weighted_avg_clv_pct`
    - `count_weighted_beat_close_rate`
  - per-segment examples for explainability
- `top_lists`: deterministic top segment keys by major ranking modes

Aggregation rules:

- Uses `hypothesis_candidates.json` entries from each successful user scan.
- Notional-weighted combines include only entries with `weighting="notional"` and `denominators.weight_used > 0`.
- Count-weighted combines include only entries with `weighting="count"` and `denominators.count_used > 0`.
- Weighted combine formula: `sum(value_i * weight_i) / sum(weight_i)`.

## Deterministic Ordering

- Segment top-lists sort by metric descending, then `segment_key` ascending.
- Persistence list sorts by `users_with_segment` descending, then `segment_key` ascending.
- Segment rows are emitted in stable `segment_key` order.
- No randomness is used in aggregation or ordering.
- Under `--workers N`, results are collected in original `--users` list order, not completion order.

## Offline Safety

- Batch logic is implemented via an injectable `BatchRunner(scan_callable=...)`.
- Tests use fake scan callables and fixture run roots, so they run with no network and no ClickHouse.

## Tests

```bash
pytest tests/test_batch_run.py -q
pytest -q
```

Test functions:

- `test_aggregation_determinism_stable_tie_breaker`: segment ordering is stable across identical runs
- `test_weighted_combine_math_uses_weight_used`: notional-weighted math verified
- `test_count_weighted_fallback_when_no_notional_contributors`: count-weighted fallback path
- `test_continue_on_error_marks_failure_and_still_writes_outputs`: failure recording
- `test_batch_manifest_exists_and_lists_outputs`: manifest structure verification
- `test_build_markdown_includes_robust_clv_stats`: robust CLV stats in markdown output
- `test_aggregate_only_from_run_roots`: aggregate-only mode produces valid leaderboard from existing run roots
- `test_aggregate_only_directory_input`: `_resolve_run_roots()` resolves subdirs from directory
- `test_aggregate_only_file_input`: `_resolve_run_roots()` resolves paths from text file
- `test_workers_ordering_matches_serial`: parallel results preserve original user order
- `test_workers_continue_on_error_parallel`: failures recorded without dropping users under workers>1
