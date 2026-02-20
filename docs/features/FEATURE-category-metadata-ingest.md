# Feature: Category Metadata Ingest

This change ensures category labels stop disappearing at runtime: when Polymarket provides category data, PolyTool now stores it locally and reuses it offline for dossier joins and coverage reporting.

## Source of truth

- Category and subcategory come from the Polymarket Gamma `/markets` payload.
- Mapping is field-based and direct:
  - `category` <- `category` (fallback keys: `marketCategory`, `market_category`)
  - `subcategory` <- `subcategory` (fallback keys: `subCategory`, `sub_category`)
- Values are preserved verbatim except for trimming surrounding whitespace.

## Offline storage

- Canonical table for dossier lifecycle joins: `polyttool.market_tokens`.
- Stored columns:
  - `category String`
  - `subcategory String`
- Backfill writer path:
  - parse metadata in `packages/polymarket/gamma.py`
  - persist rows in `packages/polymarket/backfill.py`
- Additive migration:
  - `infra/clickhouse/initdb/18_category_subcategory_metadata.sql`

## Write policy (non-overwrite)

- Existing non-empty category/subcategory values in `market_tokens` are treated as authoritative.
- Backfill only fills empty fields; it does not overwrite previously ingested non-empty taxonomy values.
- This prevents newer partial payloads from clobbering existing taxonomy coverage.

## How to verify

```sql
SELECT
    count() AS total_rows,
    countIf(category != '') AS category_non_empty_rows,
    countIf(subcategory != '') AS subcategory_non_empty_rows
FROM market_tokens;
```

For a specific run, probe only that run's token IDs:

```sql
SELECT countIf(category != '') AS category_non_empty_for_run
FROM market_tokens
WHERE token_id IN {tokens:Array(String)};
```

If upstream metadata includes taxonomy for those tokens, both counts should become non-zero after backfill/ingest.
