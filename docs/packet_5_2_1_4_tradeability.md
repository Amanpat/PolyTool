# Packet 5.2.1.4 Tradeability Notes

## Why 404 is normal
The CLOB `/book` endpoint can return HTTP 404 with:
`{"error":"No orderbook exists for the requested token id"}`
This happens for inactive or closed markets and is not an error state for snapshotting.
We classify this as `no_orderbook` instead of `error`.

## MIN_OK_TARGET selection
`/api/snapshot/books` builds candidate tokens in priority order (positions, then recent trades)
and attempts snapshots until one of the following occurs:
- `BOOK_SNAPSHOT_MIN_OK_TARGET` OK snapshots are captured
- `BOOK_SNAPSHOT_MAX_PREFLIGHT` (or request `max_tokens`) attempts are reached
- candidates are exhausted

This ensures we focus effort on tradeable markets without overfetching.

## TTL skip behavior
To avoid repeatedly probing tokens that recently returned `no_orderbook`, the snapshotter
queries ClickHouse for tokens whose latest status in the last
`BOOK_SNAPSHOT_404_TTL_HOURS` is `no_orderbook`. Those tokens are skipped and counted
as `tokens_skipped_no_orderbook_ttl` for the run.

## Troubleshooting with curl
You can manually check CLOB tradeability:

```bash
curl -i "https://clob.polymarket.com/book?token_id=<clob_token_id>"
```

Expected outcomes:
- `200 OK` with `bids`/`asks` arrays: tradeable book
- `404 Not Found` with `No orderbook exists...`: normal for inactive markets
- `429` or `5xx`: transient CLOB/API errors
