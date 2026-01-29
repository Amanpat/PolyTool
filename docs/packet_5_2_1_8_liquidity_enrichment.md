# Packet 5.2.1.8 - Liquidity Snapshot Enrichment

## Why liquidity rows can appear blank

Orderbook snapshots store the raw token id returned by `/api/snapshot/books`. If that
id is an alias (Data API token id) instead of the canonical CLOB token id, the join
into `market_tokens` fails and the liquidity dashboard shows empty market_slug/question.

This can happen even after trades are fully enriched, because snapshotting uses
trade-derived token ids and does not rewrite historical snapshot rows.

## Fix: resolve at query time

`orderbook_snapshots_enriched` now resolves snapshot token ids using `token_aliases`
first, then joins `market_tokens` and `markets_enriched` for market metadata. This
keeps the raw snapshot table unchanged while enabling consistent enrichment.

## How to interpret the dashboard

- **OK / Empty / One-Sided / No Orderbook / Error** rows all share the same enrichment
  logic. Missing market metadata indicates a genuine gap in Gamma coverage, not an
  orderbook fetch issue.
- Closed or inactive markets may still appear with **No Orderbook** even when
  enrichment is present. That’s expected when the CLOB orderbook is disabled.

## Verification

```sql
SELECT countIf(length(market_slug) > 0) AS with_slug, count() AS total
FROM polyttool.orderbook_snapshots_enriched
WHERE snapshot_ts > now() - INTERVAL 30 DAY;
```
