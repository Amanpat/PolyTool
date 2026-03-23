# 2026-03-21 — Benchmark Curation Bucket Fix

## Objective

Fix the classification blocker that prevented newly created Silver tapes from
satisfying the politics/sports/crypto bucket quotas in `benchmark-manifest`.
After the 2026-03-20 full-target Silver gap-fill, all 120 tapes existed on disk
but `benchmark-manifest` still reported shortages of `politics=9`, `sports=11`,
`crypto=10`, `near_resolution=9`, and `new_market=5`.

## Root Cause

`silver_meta.json` contains no market text — only token IDs, timestamps, event
counts, and reconstruction confidence metadata. Without a slug, category, or
title, `_classify_candidate()` in `benchmark_manifest.py` could not assign
politics/sports/crypto labels to any Silver tape. The `near_resolution`
bucket recovered on its own (it uses price-tail inference, not keyword
classification), but all three keyword-driven buckets remained at zero
candidates despite 120 Silver tapes on disk.

## Fix

### New file: `market_meta.json`

A companion file written alongside Silver tapes containing the classification
fields the curation step needs:

```json
{
  "schema_version": "silver_market_meta_v1",
  "slug": "<market-slug>",
  "category": "<politics|sports|crypto|...>",
  "market_id": "<0x...>",
  "platform": "polymarket",
  "token_id": "<token_id>",
  "benchmark_bucket": "<politics|sports|crypto|near_resolution|new_market>"
}
```

`category` is set from the gap-fill target's `bucket` field (already present in
`config/benchmark_v1_gap_fill.targets.json`).

### Changes to `tools/cli/batch_reconstruct_silver.py`

1. **`write_market_meta(target, tape_dir) -> bool`**: writes `market_meta.json`
   to a tape dir from a gap-fill target entry.

2. **`backfill_market_meta_from_targets(targets, *, out_root) -> dict`**: writes
   `market_meta.json` to existing Silver tape dirs without re-running
   reconstruction. Returns `{written, missing, skipped, errors}` counts.

3. **`--backfill-market-meta` CLI flag**: triggers backfill mode — scans
   existing tape dirs and writes `market_meta.json` entries without touching
   reconstruction or ClickHouse. Skips credential check.

4. **`run_batch_from_targets()`**: now writes `market_meta.json` alongside
   Silver tape output after each successful reconstruction run.

5. **Credential check**: now also bypassed for `--dry-run` (in addition to
   `--backfill-market-meta`) since dry-run never writes to ClickHouse.

### Changes to `packages/polymarket/benchmark_manifest.py`

`_load_metadata()` now reads `market_meta.json` first (before `watch_meta.json`)
as its primary metadata source. The `category` field maps directly to the bucket
keyword classifier, guaranteeing that Silver tapes produced from a gap-fill
targets manifest are immediately classifiable.

## Execution

Backfill command run against existing 120 Silver tape dirs:

```
python -m polytool batch-reconstruct-silver \
    --targets-manifest config/benchmark_v1_gap_fill.targets.json \
    --backfill-market-meta \
    --out-root artifacts
```

Result:
```
[batch-reconstruct-silver] [BACKFILL] writing market_meta.json to existing tapes
  manifest: config\benchmark_v1_gap_fill.targets.json  targets=120
  out-root: D:\Coding Projects\Polymarket\PolyTool\artifacts

[batch-reconstruct-silver] backfill complete
  written: 120
  missing: 0  (tape dir not found)
  skipped: 0  (invalid targets)
  errors:  0
```

## Verification

```
python -m polytool benchmark-manifest --root artifacts
```

Result (gap report `config/benchmark_v1.gap_report.json` generated
`2026-03-21T19:42:42+00:00`):

```
shortages_by_bucket:
  politics:       0   (quota 10, candidates 33, selected 10)
  sports:         0   (quota 15, candidates 38, selected 15)
  crypto:         0   (quota 10, candidates 60, selected 10)
  near_resolution: 0  (quota 10, candidates 81, selected 10)
  new_market:     5   (quota 5,  candidates 0,  selected 0)

inventory_by_tier: gold=13, silver=118
selected_total: 45 / 50 required
```

Only `new_market=5` remains. `config/benchmark_v1.tape_manifest` is still not
written (blocked by `new_market` shortage), but all four classifiable buckets
are now at quota.

## Tests

### `tests/test_batch_silver.py` — 16 new tests in 4 classes

- `TestWriteMarketMeta` (5): file written, correct fields, `category==bucket`,
  returns False on bad dir, empty target writes empty fields.
- `TestBackfillMarketMeta` (5): writes to existing tape, skips missing tape,
  skips invalid target, multiple targets, content correct.
- `TestRunBatchFromTargetsMarketMeta` (3): market_meta written on success, not
  written on dry-run, not written on failure.
- `TestBackfillMarketMetaCLI` (3): backfill exits zero, does not require
  ClickHouse password, writes market_meta.

Also updated:
- `test_missing_password_returns_1` and `test_empty_string_password_returns_1`:
  removed `--dry-run` flag (dry-run no longer requires credentials; these tests
  now cover the non-dry-run path where credentials are required).
- `test_targets_manifest_dry_run_exits_zero`: already uses `--dry-run`, still
  exits zero without credentials (correct).

### `tests/test_benchmark_manifest.py` — 3 new classification regression tests

- `test_silver_tape_with_market_meta_classified_into_politics`
- `test_silver_tape_with_market_meta_classified_into_sports`
- `test_silver_tape_with_market_meta_classified_into_crypto`

Each creates a Silver tape with only `market_meta.json` + `silver_meta.json` +
`silver_events.jsonl` (no `watch_meta.json`) and asserts that
`discover_inventory([root])` returns a candidate with the expected bucket.

### `tests/test_batch_silver_gap_fill.py` — 2 tests fixed

Added `--clickhouse-password testpass` to `test_targets_manifest_writes_gap_fill_result`
and `test_targets_manifest_benchmark_refresh_flag` — these non-dry-run tests
were implicitly relying on the old `"polytool_admin"` fallback that was removed
in the 2026-03-19 auth fix.

## Full test suite

```
2286 passed, 8 failed (all pre-existing in unchanged test files)
```

Pre-existing failures:
- `test_gate2_eligible_tape_acquisition.py` — `ResolvedWatch` has no `regime` attribute
- `test_new_market_capture.py` — live Gamma API returning 0 candidates

No regressions introduced.

## Open questions / next steps

- `new_market=5` shortage remains. This requires live Gold tape capture via
  `capture-new-market-tapes` against recently listed Polymarket markets.
  Prerequisite: live WS connectivity + real Gamma API candidates.
- Once `new_market` is satisfied, `benchmark-manifest` will write
  `config/benchmark_v1.tape_manifest` and Gate 2 scenario sweeps can begin.
- The `config/benchmark_v1.tape_manifest` file does not exist yet.
