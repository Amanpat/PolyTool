# SPEC: Benchmark Gap-Fill Planner v1

**Status:** Implemented — 2026-03-17
**Branch:** `phase-1`
**Authority:** `docs/archive/reference/POLYTOOL_MASTER_ROADMAP_v4.2.md` (superseded; retained for historical context)

---

## 1. Purpose

The gap-fill planner discovers Silver reconstruction targets from local
`pmxt_archive` + Jon-Becker Parquet datasets to fill the shortage buckets
reported in `config/benchmark_v1.gap_report.json`.

It does **not** generate tapes.  It produces a deterministic JSON target
manifest that downstream steps can consume to drive `batch-reconstruct-silver`.

---

## 2. Data Sources

| Source | Path | Role |
|--------|------|------|
| pmxt_archive | `D:\Coding Projects\Polymarket\PolyToolData\raw\pmxt_archive\Polymarket\*.parquet` | L2 snapshot condition_ids + capture windows |
| jon_becker markets | `.../data/polymarket/markets/*.parquet` | Market metadata: slug, question, clob_token_ids, end_date, created_at |

The join key is `pmxt.market_id == jb_markets.condition_id` (both 0x hex strings).

The YES token ID is taken from `jb_markets.clob_token_ids[0]` (first element).

---

## 3. Classification Rules

Conservative — mirrors `benchmark_manifest.py` keyword lists.

| Bucket | Rule |
|--------|------|
| `sports` | question+slug contains a sports keyword (nba, nhl, nfl, mlb, soccer, etc.) |
| `politics` | question+slug contains a politics keyword (election, trump, senate, etc.) |
| `crypto` | question+slug contains a crypto keyword (bitcoin, eth, solana, etc.) |
| `near_resolution` | `end_date` within 48h of reference_time (2026-03-15T10:00Z) |
| `new_market` | `created_at` within 48h before reference_time |

A market may qualify for multiple buckets simultaneously.

---

## 4. Output Files

### `config/benchmark_v1_gap_fill.targets.json`

Written when any valid targets exist.

```json
{
  "schema_version": "benchmark_gap_fill_v1",
  "generated_at": "<ISO UTC>",
  "source_roots": {"pmxt_root": "...", "jon_root": "..."},
  "bucket_summary": {
    "<bucket>": {
      "shortage": <N>,
      "candidates_found": <M>,
      "targets_selected": <K>,
      "insufficient": <bool>,
      "insufficiency_reason": "..."
    }
  },
  "targets": [
    {
      "bucket": "<bucket>",
      "platform": "polymarket",
      "slug": "...",
      "market_id": "0x...",
      "token_id": "<decimal YES token>",
      "window_start": "<ISO UTC>",
      "window_end": "<ISO UTC>",
      "priority": 1,
      "selection_reason": "...",
      "price_2min_ready": false
    }
  ]
}
```

Priority 1 = fills the exact shortage count.  Priority 2 = overflow.

`price_2min_ready` is always `false` — `fetch-price-2min` must be run
per token before Silver reconstruction to populate ClickHouse.

### `config/benchmark_v1_gap_fill.insufficiency.json`

Written whenever any bucket remains below its shortage quota.

---

## 5. Real-Data Coverage (2026-03-17)

| Bucket | Shortage | Candidates Found | Status |
|--------|----------|-----------------|--------|
| politics | 9 | 2,052 | **OK** |
| sports | 11 | 2,049 | **OK** |
| crypto | 10 | 279 | **OK** |
| near_resolution | 9 | 272 | **OK** |
| new_market | 5 | 0 | **INSUFFICIENT** |

**new_market root cause:** The Jon-Becker dataset was snapshotted ~2026-02-03.
No markets created after that date appear in the dataset.  The new_market
bucket requires markets created within 48h of 2026-03-15.  This cannot be
filled from current local data.

---

## 6. Module

`packages/polymarket/benchmark_gap_fill_planner.py`

Public API:

- `GapFillPlanner(pmxt_root, jon_root, shortages, *, reference_time, ...)` — planner class
- `classify_market(question, slug, end_date, created_at, reference_time)` — pure classification helper
- `run(pmxt_root, jon_root, gap_report, *, out_path, insufficiency_path, ...)` — convenience wrapper

All DuckDB calls are injectable for offline testing via `_pmxt_fetch_fn` and
`_jon_markets_fetch_fn` constructor arguments.

---

## 7. Next Steps

1. Run `fetch-price-2min --token-id <ID>` for each priority-1 target token.
2. Run `batch-reconstruct-silver` for each target (using the `window_start`
   and `window_end` from the targets file).
3. Re-run `benchmark-manifest` — Silver tapes will be discovered and should
   fill the politics, sports, crypto, near_resolution shortages.
4. For `new_market`: requires a fresher Jon-Becker snapshot or live shadow
   recordings of newly listed markets.
