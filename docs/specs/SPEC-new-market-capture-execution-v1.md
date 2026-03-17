# SPEC: New-Market Capture Execution v1

**Version:** 1.0
**Status:** Implemented
**Date:** 2026-03-17

---

## Overview

This spec defines the operator flow for consuming a `benchmark_new_market_capture_v1`
targets manifest and batch-recording Gold tapes for the `benchmark_v1` `new_market` bucket.

It introduces `capture-new-market-tapes`, a new CLI that wraps the existing `TapeRecorder`
recording surface and bridges the new-market planner → tape inventory → benchmark curation
lifecycle.

---

## Problem

`new-market-capture` (planner) discovers newly listed Polymarket markets and writes a
recording plan.  This spec closes the execution half of that loop: given the plan, record
the Gold tapes and trigger benchmark curation.

---

## Inputs

| Artifact | Schema | Description |
|---|---|---|
| `config/benchmark_v1_new_market_capture.targets.json` | `benchmark_new_market_capture_v1` | Per-target slug, token_id, listed_at, age_hours, record_duration_seconds |

### Target record schema

```json
{
  "bucket": "new_market",
  "slug": "some-new-market-slug",
  "market_id": "123456",
  "token_id": "0x...",
  "listed_at": "2026-03-17T10:00:00Z",
  "age_hours": 5.25,
  "priority": 1,
  "record_duration_seconds": 1800,
  "selection_reason": "..."
}
```

Required for processing: `slug`, `record_duration_seconds`.
`token_id` is advisory — the CLI re-resolves both YES and NO token IDs via
`MarketPicker.resolve_slug()` at execution time.

---

## Execution

### CLI invocation

```bash
# Plan first (produces the targets manifest)
python -m polytool new-market-capture

# Execute — record Gold tapes + benchmark refresh
python -m polytool capture-new-market-tapes \
    --targets-manifest config/benchmark_v1_new_market_capture.targets.json \
    --benchmark-refresh \
    --result-out artifacts/benchmark_capture/run.json

# Dry run (resolves slugs but does not record)
python -m polytool capture-new-market-tapes --dry-run
```

### Per-target processing

1. Validate target dict — skip if not a dict or missing `slug`
2. Resolve YES + NO token IDs via `MarketPicker.resolve_slug(slug)` — skip on failure
3. Create canonical tape directory: `<out_root>/<slug>/`
4. Write `watch_meta.json` with `market_slug`, `yes_asset_id`, `no_asset_id`,
   `recorded_at`, `bucket="new_market"`, `listed_at`, `age_hours`, `regime="new_market"`,
   `threshold_source="new_market_capture_plan"`
5. Call `TapeRecorder(tape_dir, asset_ids=[yes_id, no_id]).record(duration_seconds=record_duration_seconds)`
6. Read `event_count` from `meta.json` written by `TapeRecorder`
7. Persist tape metadata to ClickHouse (fallback to JSONL) using `TapeMetadataRow(tier="gold")`
8. Record per-target `status`: `success | failure | skip`

Invalid/unresolvable targets are skipped with a recorded `skip_reason`; the batch
continues without aborting.

---

## Outputs

### Canonical tape directory

```
artifacts/simtrader/tapes/new_market_capture/<slug>/
├── watch_meta.json     — market slug, YES/NO token IDs, bucket, listed_at, regime
├── raw_ws.jsonl        — raw WebSocket frames (written by TapeRecorder)
├── events.jsonl        — normalized tape events (Gold tape)
└── meta.json           — TapeRecorder metadata: event_count, frame_count, reconnects
```

### `watch_meta.json` contract

```json
{
  "market_slug": "...",
  "yes_asset_id": "0x...",
  "no_asset_id": "0x...",
  "recorded_at": "2026-03-17T12:00:00+00:00",
  "bucket": "new_market",
  "listed_at": "2026-03-17T10:00:00Z",
  "age_hours": 5.25,
  "regime": "new_market",
  "threshold_source": "new_market_capture_plan"
}
```

`tape_manifest.py` reads `watch_meta.json` for regime detection (`regime="new_market"`) and
slug/token resolution.

### Batch result artifact (`benchmark_new_market_capture_run_v1`)

Written to `--result-out` (default: `<out_root>/capture_run_<id[:8]>.json`).

```json
{
  "schema_version": "benchmark_new_market_capture_run_v1",
  "batch_run_id": "...",
  "started_at": "...",
  "ended_at": "...",
  "dry_run": false,
  "targets_attempted": 5,
  "tapes_created": 5,
  "failure_count": 0,
  "skip_count": 0,
  "metadata_summary": {"clickhouse": 5, "jsonl_fallback": 0, "skipped": 0},
  "out_root": "artifacts/simtrader/tapes/new_market_capture",
  "benchmark_refresh": {
    "triggered": true,
    "return_code": 0,
    "manifest_written": true,
    "outcome": "manifest_written",
    "manifest_path": "config/benchmark_v1.tape_manifest"
  },
  "outcomes": [
    {
      "token_id": "0xYES...",
      "slug": "some-new-market",
      "bucket": "new_market",
      "priority": 1,
      "status": "success",
      "skip_reason": null,
      "tape_dir": "artifacts/simtrader/tapes/new_market_capture/some-new-market",
      "events_path": "artifacts/simtrader/tapes/new_market_capture/some-new-market/events.jsonl",
      "event_count": 423,
      "listed_at": "2026-03-17T10:00:00Z",
      "age_hours": 5.25,
      "record_duration_seconds": 1800,
      "error": null,
      "metadata_write": "clickhouse"
    }
  ]
}
```

### Tape metadata (`tape_metadata` ClickHouse table)

Reuses the Silver tape metadata table (`polytool.tape_metadata`) with `tier="gold"`.
Fields adapted for live Gold tapes:

| Field | Value |
|---|---|
| `tier` | `"gold"` |
| `token_id` | YES token ID |
| `window_start` | `recorded_at` (ISO8601) |
| `window_end` | `recorded_at + record_duration_seconds` |
| `reconstruction_confidence` | `"gold"` |
| `source_inputs_json` | `{"slug": ..., "bucket": "new_market", "listed_at": ..., "age_hours": ..., "recorded_from_live_ws": true}` |

### Benchmark refresh (`--benchmark-refresh`)

When `--benchmark-refresh` is set and the run is not a dry-run, the CLI calls
`tools.cli.benchmark_manifest._run_build()` after the batch completes.  This either:

- Writes `config/benchmark_v1.tape_manifest` + audit + lock if quotas are met (exit 0)
- Updates `config/benchmark_v1.gap_report.json` and exits non-zero if still short

The outcome is recorded in `result["benchmark_refresh"]`.

---

## Implementation surface

| File | Change |
|---|---|
| `tools/cli/capture_new_market_tapes.py` | New: CLI for Gold tape batch capture |
| `polytool/__main__.py` | Register `capture-new-market-tapes` command |
| `tests/test_capture_new_market_tapes.py` | New: focused offline tests |

---

## Failure modes

| Condition | Behavior |
|---|---|
| Targets manifest not found | Error + exit 1 |
| Wrong `schema_version` | Error + exit 1 |
| Target missing `slug` | Skip with reason, batch continues |
| `resolve_slug` fails (API/network) | Skip with reason, batch continues |
| `TapeRecorder.record()` raises | Record as `failure`, batch continues |
| All targets failed/skipped, no tapes created | Exit 1 (non-dry-run only) |
| `--benchmark-refresh` with `--dry-run` | Refresh not triggered |

---

## Known limitations

- `new_market` bucket still requires live Gamma API access to discover targets (planner step)
  and live WS access to record tapes (capture step).
- If < 5 new-market candidates exist at recording time, the `new_market` quota remains
  unsatisfied and `config/benchmark_v1.tape_manifest` is not created.
- Tapes are recorded sequentially (one market at a time); no parallel recording.
- `TapeRecorder` blocks for `record_duration_seconds` per target.

---

## Operator workflow (end-to-end)

```bash
# Step 1: Discover new-market candidates (planner)
python -m polytool new-market-capture

# Step 2: Record Gold tapes for all targets
python -m polytool capture-new-market-tapes \
    --targets-manifest config/benchmark_v1_new_market_capture.targets.json \
    --benchmark-refresh

# If benchmark_v1.tape_manifest was created:
#   Proceed to Gate 2 scenario sweep
# Otherwise:
#   Check config/benchmark_v1.gap_report.json for remaining shortages
```
