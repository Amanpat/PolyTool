# PnL Troubleshooting

## How pricing works

PnL is computed from two inputs:
- Trades and position snapshots in ClickHouse
- Prices for open positions (best bid/ask)

Pricing sources are selected in this order:
1) Recent orderbook snapshots in ClickHouse (`token_orderbook_snapshots`) if a ClickHouse client is available.
2) Live CLOB best bid/ask if snapshots are missing or too old.

If no valid price is found for a token, it is skipped and reported in the response.

## Snapshot vs live pricing

- Snapshot pricing is preferred when snapshots are present and within `ORDERBOOK_SNAPSHOT_MAX_AGE_SECONDS`.
- Missing or stale snapshots fall back to live CLOB best bid/ask.
- If the CLOB has no orderbook for a token, pricing for that token is skipped.

## Compute PnL via API

```bash
curl -X POST http://localhost:8000/api/compute/pnl \
  -H "Content-Type: application/json" \
  -d "{\"user\":\"@432614799197\",\"bucket\":\"day\"}"
```

## Tips

- To populate snapshots first, run `/api/snapshot/books` for the user.
- Check `ORDERBOOK_SNAPSHOT_MAX_AGE_SECONDS` if snapshots appear stale.
- Inspect `token_orderbook_snapshots` for recent rows with `status = 'ok'`.
