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
- Category table selection now prefers the first existing table with non-empty category rows, preventing false joins to empty legacy tables.
- Category is present on each position record before metadata-map backfill and before audit/segment processing.

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
