# Packet 5.2.1.6 - Token Resolution for Metadata Joins

## Why token ids differ

Polymarket surfaces multiple token id namespaces:

- **Gamma / markets** returns `clobTokenIds` (CLOB orderbook token ids).
- **Data API / trades, positions, activity** often returns `asset` / `tokenId` values that
  do **not** always match `clobTokenIds`.

When these ids differ, joins on `token_id` fail and market metadata (slug/question/outcome)
falls back to raw identifiers.

## Resolution strategy

Token resolution is now standardized in ClickHouse and used by snapshots and dashboards.
The effective token id for joins is resolved in this order:

1. **Direct match**: `user_trades.token_id = market_tokens.token_id`
2. **Alias match**: `token_aliases.alias_token_id -> canonical_clob_token_id`
3. **Condition + outcome fallback**: normalize `condition_id`, find outcome index in
   `markets.outcomes`, then map to `markets.clob_token_ids`

Condition ids are normalized to lowercase and forced to a `0x` prefix during ingestion
and in join logic to prevent casing or prefix mismatches.

## ClickHouse objects

- **Table**: `polyttool.token_aliases`
  - Source of truth for alias -> canonical mappings.
- **Views**:
  - `polyttool.user_trades_resolved`
  - `polyttool.user_positions_resolved`
  - `polyttool.user_activity_resolved`
  - `polyttool.orderbook_snapshots_enriched` (updated to use aliases)

These views expose `resolved_token_id`, `resolved_condition_id`, and enriched metadata
fields (`market_slug`, `question`, `category`, `resolved_outcome_name`).

## Snapshot/books usage

`/api/snapshot/books` now resolves candidate tokens before filtering by active markets.
This ensures:

- `tokens_with_market_metadata` reflects post-resolution tokens
- snapshots are taken using canonical CLOB token ids
- market metadata joins succeed for dashboards and diagnostics

## Dashboard usage

Plays and User Overview panels now query `user_trades_resolved` (and related resolved
views) so market_slug/question/outcome populate reliably even when Data API token ids
are aliases.

## Troubleshooting

- If metadata is still missing:
  - Run `/api/ingest/markets` and/or trigger backfill
  - Confirm `token_aliases` has rows for the alias token ids
  - Verify `condition_id` normalization (lowercase + `0x` prefix)
