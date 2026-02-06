# Packet 5.2.1.5 - Snapshot/books metadata refresh after backfill

## Bug
The `/api/snapshot/books` handler performed the market metadata join before running
backfill. If backfill inserted new `market_tokens` or `markets_enriched` rows, the
request still used the pre-backfill join results. That caused
`tokens_with_market_metadata`, `tokens_after_active_filter`, and
`tokens_selected_total` to remain at 0 even after successful backfill, which in
turn made liquidity snapshots appear empty.

## Fix
- Run the metadata join for candidate tokens first to identify missing tokens.
- Run backfill for missing tokens.
- Re-run the metadata join after backfill and apply the active-market filter to
  the refreshed results.
- Surface a specific diagnostic if backfill inserts tokens but the metadata join
  still returns 0.

## What tokens_with_market_metadata means
The number of candidate tokens that have matching market metadata rows from the
`market_tokens` join to `markets_enriched` for the request. It is computed after
backfill so it reflects the latest metadata available to the handler.

## How to verify
Run the standard ingestion + snapshot workflow, then confirm that the snapshot
diagnostics show non-zero metadata counts after backfill when markets exist.

```bash
docker compose up -d --build
docker compose run --rm migrate
curl -X POST "http://localhost:8000/api/ingest/markets" -H "Content-Type: application/json" -d '{"max_pages":200}'
python -m polyttool scan --user "@example" --bucket day --ingest-activity --ingest-positions
curl -X POST "http://localhost:8000/api/snapshot/books" -H "Content-Type: application/json" -d '{"user":"@example","max_tokens":50}'
```

```sql
SELECT status, count()
FROM polyttool.token_orderbook_snapshots
WHERE snapshot_ts > now() - INTERVAL 30 DAY
GROUP BY status;
```
