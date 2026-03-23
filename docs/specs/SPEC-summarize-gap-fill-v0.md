# SPEC-summarize-gap-fill-v0

## Purpose

Read-only diagnostic tool for `gap_fill_run.json` artifacts produced by
`batch-reconstruct-silver --targets-manifest`. Allows operators to quickly
understand the outcome of a gap-fill batch without touching live data,
ClickHouse, or the filesystem beyond reading the one artifact.

## Scope

- **In scope**: loading, parsing, and printing a `benchmark_gap_fill_run_v1`
  artifact; bucket/outcome breakdown; normalized warning/error grouping;
  success class classification; artifact path reporting; JSON output mode.
- **Out of scope**: any writes, any network access, any ClickHouse queries,
  any modification to the benchmark closure path.

## Command

```
python -m polytool summarize-gap-fill --path <gap_fill_run.json> [--json]
```

### Arguments

| Flag       | Required | Description                                           |
|------------|----------|-------------------------------------------------------|
| `--path`   | yes      | Path to `gap_fill_run.json` artifact                  |
| `--json`   | no       | Emit machine-readable JSON summary instead of text    |

### Exit codes

| Code | Meaning                                              |
|------|------------------------------------------------------|
| 0    | Summary produced successfully                        |
| 1    | File not found, unreadable, or invalid JSON          |

## Input schema

The tool expects a `benchmark_gap_fill_run_v1` JSON object at `--path`.

Required top-level fields:
- `schema_version` (string, must equal `"benchmark_gap_fill_run_v1"`)
- `targets_attempted` (int)
- `tapes_created` (int)
- `failure_count` (int)
- `skip_count` (int)
- `outcomes` (array of outcome objects)

If `schema_version` does not match, a warning is printed to stderr and
processing continues.

Each outcome object is expected to have:
- `bucket` (string): e.g. `"politics"`, `"sports"`, `"crypto"`, `"near_resolution"`, `"new_market"`
- `status` (string): `"success"` | `"failure"` | `"skip"`
- `reconstruction_confidence` (string): `"high"` | `"low"` | `"none"`
- `fill_count` (int)
- `price_2min_count` (int)
- `warnings` (list of strings)
- `error` (string | null)
- `events_path` (string | null)
- `out_dir` (string | null)

## Output sections (human-readable mode)

1. **Header**: run path, schema, batch_run_id, timestamps, dry_run flag.
2. **TOTALS**: targets_attempted / tapes_created / failure_count / skip_count.
3. **BY BUCKET**: per-bucket success / failure / skip counts plus
   confidence tier breakdown.
4. **SUCCESS CLASSES**: normalized label counts grouping outcomes by
   `(confidence, fill_presence)`. Labels: `confidence=<tier>, price_2min_only`,
   `confidence=<tier>, has_fills+price_2min`, etc.
5. **WARNING CLASSES**: normalized warning prefix counts (e.g.
   `pmxt_anchor_missing`, `jon_fills_missing`, `price_2min_missing`).
6. **ERROR CLASSES**: normalized error string counts (first 120 chars, long
   numeric token IDs and ISO timestamps stripped).
7. **METADATA WRITES**: clickhouse / jsonl_fallback / skipped counts.
8. **BENCHMARK REFRESH**: triggered, outcome, paths if present.
9. **ARTIFACT PATHS**: up to 20 `events_path` + `out_dir` values from outcomes.

## Normalization rules

### Warning normalization
- If warning contains `:`, the portion before the first `:` is used as the
  class (e.g. `"pmxt_anchor_missing"`).
- Otherwise, numeric token IDs (≥20 digits) and ISO timestamps are replaced
  with `<TOKEN>` and `<TS>` respectively; result truncated to 80 chars.

### Error normalization
- Numeric token IDs (≥20 digits) replaced with `<TOKEN>`.
- ISO timestamps replaced with `<TS>`.
- Truncated to 120 chars.

## JSON output mode (`--json`)

When `--json` is passed, the command prints a single JSON object to stdout
with the following keys:

```json
{
  "schema_version": "<source schema>",
  "totals": { ... },
  "by_bucket": { "<bucket>": { "success": N, "failure": N, "skip": N, "confidence_breakdown": { ... } } },
  "warning_classes": { "<class>": N, ... },
  "error_classes": { "<class>": N, ... },
  "success_classes": { "<label>": N, ... },
  "metadata_summary": { ... },
  "benchmark_refresh": { ... },
  "artifact_paths": [ ... ]
}
```

## Files

| Path                                       | Role                    |
|--------------------------------------------|-------------------------|
| `tools/cli/summarize_gap_fill.py`          | CLI + summariser logic  |
| `tests/test_summarize_gap_fill.py`         | 35 offline tests        |
| `docs/specs/SPEC-summarize-gap-fill-v0.md` | This spec               |

## Constraints

- No network calls.
- No ClickHouse reads or writes.
- No writes to any file (read-only).
- Does not touch `tools/cli/close_benchmark_v1.py`,
  `tools/cli/batch_reconstruct_silver.py`, or
  `packages/polymarket/silver_reconstructor.py`.
