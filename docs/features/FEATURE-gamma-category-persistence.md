# FEATURE: Gamma Category Persistence

Category labels are now persisted directly with token-level market metadata during ingest/backfill, and scan debug mode writes a compact raw Gamma sample so operators can quickly see whether upstream payloads actually contain category/subcategory values.

## Storage grain

- Storage target: `market_tokens` (token-level grain used by coverage joins).
- Each `token_id` row can now carry:
  - `category`
  - `subcategory`
  - `category_source`
  - `subcategory_source`

This keeps taxonomy at the same grain already used for run-scoped category coverage checks.

## Mapping rules

- Trim-only, verbatim labels (no normalization/guessing).
- `category_source`:
  - `market` when top-level market category is present.
  - `event` when category is filled from event payload.
  - `none` when category is unavailable.
- `subcategory_source`:
  - `event` when event subcategory is present.
  - `none` when unavailable.
- Non-overwrite policy is preserved: existing non-empty taxonomy values in `market_tokens` are kept; ingest/backfill only fills empty fields.

## Fallback behavior

When top-level market taxonomy is empty:

1. Use embedded market event data (`events[0].category/subcategory`) if present.
2. Otherwise perform bounded `/events` lookups by referenced event ids/slugs and fill only empty taxonomy fields when event taxonomy exists.

## Debug artifact

When scan runs with `--debug-export` and `--ingest-markets`, run root now includes:

- `gamma_markets_sample.json`

The file contains:

- exact `/markets` request URL + query params
- first 10 raw market samples with selected taxonomy-related fields

This is the primary artifact for diagnosing whether empty local categories are caused by ingest mapping vs. upstream payload content.
