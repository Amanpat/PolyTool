# Feature: Category Coverage Fix

Category coverage can now reflect real Polymarket labels in dossier, coverage, and audit outputs instead of defaulting everything to `Unknown`. This keeps segment analysis useful and makes missing metadata visible only when it is actually missing locally.

## Where category comes from

- Source of truth is local ClickHouse token metadata populated from Gamma taxonomy by backfill.
- Tables used by exporter: `polymarket_tokens` and `market_tokens` (schema compatibility).
- Category values are used verbatim as provided by Polymarket metadata.

## How category is joined into lifecycle positions

- Dossier export builds lifecycle rows from `user_trade_lifecycle_enriched` (and fallback `user_trade_lifecycle`).
- Export query appends category with:
  - `COALESCE(mt.category, '') AS category`
  - `LEFT JOIN (...) mt ON l.resolved_token_id = mt.token_id`
- Category table selection is now run-scoped:
  - gather a bounded token sample for the current run (up to 200 unique `resolved_token_id` values),
  - probe `polymarket_tokens` and `market_tokens` for non-empty categories on those token IDs,
  - join the table with higher run-scoped coverage.
- Tie/zero keeps deterministic fallback, with explainability fields recorded in dossier coverage:
  - `category_source`
  - `category_source_table`
  - `category_source_run_non_empty_counts`
  - `category_source_run_probe_token_count`
- Category is present on each position record before metadata-map backfill and before audit/segment processing.

## Operational parity

Run-scoped selection ensures runtime behavior matches local data reality for the
current scan run, not just whichever table has non-empty categories globally.

Verification workflow:

1. Identify the run token IDs (from that run's `dossier.json` or lifecycle rows).
2. Probe both tables for those token IDs:
   - `SELECT countIf(category != '') FROM polymarket_tokens WHERE token_id IN {tokens:Array(String)}`
   - `SELECT countIf(category != '') FROM market_tokens WHERE token_id IN {tokens:Array(String)}`
3. Confirm the run's dossier `coverage` block reports:
   - selected source reason/table (`category_source`, `category_source_table`),
   - run-scoped counts (`category_source_run_non_empty_counts`).
4. Re-run `audit-coverage`; `category_coverage` should become non-zero when either
   table contains categories for those run token IDs.

## Unknown handling (ADR-0009 exact rule)

ADR-0009 defines category key semantics as:

```python
category_key = (category or "").strip()
if not category_key:
    category_key = "Unknown"
```

- No heuristic inference is allowed.
- Empty or missing category remains empty on the raw position and maps to the explicit `Unknown` bucket in reporting.
- `Unknown` is always reported, even when count is zero.
