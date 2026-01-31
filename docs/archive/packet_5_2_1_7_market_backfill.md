# Packet 5.2.1.7 - Targeted Market Metadata Backfill

## Problem

Global `/api/ingest/markets` is top-N and can miss historical markets a user traded.
When those markets are missing, `user_trades_resolved` cannot enrich trades and
`/api/snapshot/books` reports zero metadata coverage.

## Solution

A targeted backfill is now triggered during snapshot/books (and can be reused by
other workflows). It fetches only the markets needed by a user’s trades/positions.

### What gets fetched

1. **condition_id(s)** from `user_trades` where no market metadata is present
2. **token_id(s)** from `user_trades` as `clob_token_ids` (fallback when condition_id missing)
3. **slug(s)** extracted from trade `raw_json` (optional)

If Gamma returns no markets for the identifiers, a second attempt is made with
`closed=true` to include historical/resolved markets.

### Tradeable filtering

When `require_active_market=true`, snapshot/books now uses `enableOrderBook`
(and optionally `acceptingOrders`) from Gamma to filter tradeable markets, falling
back to `active` + close_date when those flags are unavailable.

## ClickHouse changes

- `market_tokens` now stores `enable_order_book` and `accepting_orders` (nullable)
- `token_aliases` provides alias -> canonical token mapping
- Resolved views (`user_trades_resolved`, `user_positions_resolved`, `user_activity_resolved`) are used by dashboards

## Verification

1. Run migrations
2. Run `/api/snapshot/books` for a user with missing metadata
3. Confirm metadata coverage:

```sql
SELECT countIf(length(market_slug) > 0) AS with_slug, count() AS total
FROM polyttool.user_trades_resolved
WHERE proxy_wallet = '<wallet>';
```
