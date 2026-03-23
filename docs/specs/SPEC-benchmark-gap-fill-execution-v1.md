# SPEC: Benchmark Gap-Fill Execution v1

**Version:** 1.0
**Status:** Implemented
**Date:** 2026-03-17

---

## Overview

This spec defines the operator flow for consuming a `benchmark_gap_fill_v1` targets
manifest and batch-generating Silver tapes to close the `benchmark_v1` inventory gaps.
It extends the existing `batch-reconstruct-silver` CLI with a second execution mode.

---

## Problem

`benchmark-manifest` audits local tape inventory and writes a gap report when quotas
cannot be satisfied. `benchmark_gap_fill_planner` discovers reconstruction targets from
local pmxt + Jon-Becker data. This spec closes the loop: given the targets manifest,
execute the Silver batch and optionally re-run benchmark curation.

---

## Inputs

| Artifact | Schema | Description |
|---|---|---|
| `config/benchmark_v1_gap_fill.targets.json` | `benchmark_gap_fill_v1` | Per-target token_id, window, bucket, slug |

### Target record schema

```json
{
  "bucket": "politics",
  "platform": "polymarket",
  "slug": "some-market-slug",
  "market_id": "0x...",
  "token_id": "12345...",
  "window_start": "2026-03-15T10:00:00+00:00",
  "window_end":   "2026-03-15T15:00:00+00:00",
  "priority": 1,
  "selection_reason": "...",
  "price_2min_ready": false
}
```

Required fields for processing: `token_id`, `window_start`, `window_end`.
Optional (preserved in output): `bucket`, `slug`, `priority`.

---

## Execution

### CLI invocation (gap-fill mode)

```bash
python -m polytool batch-reconstruct-silver \
    --targets-manifest config/benchmark_v1_gap_fill.targets.json \
    --pmxt-root /data/raw/pmxt_archive \
    --jon-root  /data/raw/jon_becker \
    --benchmark-refresh \
    --gap-fill-out artifacts/silver/gap_fill_run.json
```

### Per-target processing

1. Parse target record — skip invalid (missing `token_id`, unparseable window, inverted window)
2. Compute canonical output directory: `<out_root>/silver/<token_id[:16]>/<YYYY-MM-DDTHH-MM-SSZ>/`
3. Call `SilverReconstructor.reconstruct()` with target's own window
4. Persist tape metadata to ClickHouse (fallback to JSONL)
5. Record per-target `status`: `success | failure | skip`

Invalid/unavailable targets are skipped with a recorded `skip_reason`; the batch
continues without aborting.

---

## Outputs

### Gap-fill batch result artifact (`benchmark_gap_fill_run_v1`)

Written to `--gap-fill-out` (default: `artifacts/silver/gap_fill_run_<id[:8]>.json`).

```json
{
  "schema_version": "benchmark_gap_fill_run_v1",
  "batch_run_id": "...",
  "started_at": "...",
  "ended_at": "...",
  "dry_run": false,
  "targets_attempted": 120,
  "tapes_created": 39,
  "failure_count": 0,
  "skip_count": 81,
  "metadata_summary": {"clickhouse": 39, "jsonl_fallback": 0, "skipped": 81},
  "out_root": "...",
  "benchmark_refresh": {
    "triggered": true,
    "return_code": 2,
    "manifest_written": false,
    "outcome": "gap_report_updated",
    "gap_report_path": "config/benchmark_v1.gap_report.json"
  },
  "outcomes": [...]
}
```

Each outcome record:

```json
{
  "token_id": "...",
  "bucket": "politics",
  "slug": "...",
  "priority": 1,
  "status": "success | failure | skip",
  "skip_reason": null,
  "reconstruction_confidence": "high | medium | low | none",
  "event_count": 42,
  "fill_count": 5,
  "price_2min_count": 18,
  "warning_count": 0,
  "warnings": [],
  "out_dir": "...",
  "events_path": "...",
  "error": null,
  "metadata_write": "clickhouse | jsonl_fallback | skipped | failed",
  "window_start": "...",
  "window_end": "..."
}
```

### Benchmark refresh (--benchmark-refresh)

When `--benchmark-refresh` is set and the run is not a dry-run, the CLI calls
`tools.cli.benchmark_manifest._run_build()` after the batch completes. This either:

- Writes `config/benchmark_v1.tape_manifest` + audit + lock if quotas are met (exit 0)
- Updates `config/benchmark_v1.gap_report.json` and exits non-zero if still short

The outcome is recorded in `result["benchmark_refresh"]`.

---

## Implementation surface

| File | Change |
|---|---|
| `tools/cli/batch_reconstruct_silver.py` | Added `load_targets_manifest`, `run_batch_from_targets`, `_refresh_benchmark_curation`; extended CLI parser and `main()` |
| `tests/test_batch_silver_gap_fill.py` | New: 40 tests covering all new surfaces |
| `tests/test_batch_silver.py` | Minor: updated `test_missing_window_start` for new optional arg behavior |

---

## Failure modes

| Condition | Behavior |
|---|---|
| Targets manifest not found | Error + exit 1 |
| Wrong `schema_version` | Error + exit 1 |
| Individual target missing `token_id` | Skip with reason, batch continues |
| Individual target has bad/inverted window | Skip with reason, batch continues |
| Silver reconstruction raises exception | Record as `failure`, batch continues |
| All targets failed/skipped, no tapes created | Exit 1 (non-dry-run only) |
| `--benchmark-refresh` with `--dry-run` | Refresh not triggered |

---

## Known limitations

- `new_market` bucket remains INSUFFICIENT: JB snapshot is ~40 days stale, no markets
  created within the required 48h window of 2026-03-15. This cannot be resolved with
  the current local data; requires a fresh JB or live snapshot.
- `price_2min_ready: false` on all targets: `fetch-price-2min` has not been run for
  these token IDs yet. Silver confidence will be `medium` or `low` until price_2min
  data is populated.
