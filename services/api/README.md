# PolyTool API Service

FastAPI service for Polymarket data ingestion and analysis.

## Endpoints

### Health Check
```
GET /health
```
Returns service health status.

### Resolve User
```
POST /api/resolve
Content-Type: application/json

{
  "input": "@username" | "0x..."
}
```
Resolves a Polymarket username or wallet address to a profile.

### Ingest Trades
```
POST /api/ingest/trades
Content-Type: application/json

{
  "user": "@username" | "0x...",
  "max_pages": 50
}
```
Fetches and stores trade history for a user. Idempotent - reruns won't duplicate data.

### List Users
```
GET /api/users
```
Lists all users with ingested data.

### Get Trade Stats
```
GET /api/users/{proxy_wallet}/trades/stats
```
Returns trade statistics for a specific user.

### Snapshot Orderbooks
```
POST /api/snapshot/books
Content-Type: application/json

{
  "user": "@username" | "0x...",
  "max_tokens": 200,
  "lookback_days": 90,
  "require_active_market": true,
  "include_inactive": false
}
```
Captures point-in-time orderbook metrics for tokens the user has traded. Metrics include:
- Best bid/ask and spread (bps)
- Depth within 50bps band of mid price
- Slippage estimates for $100 and $500 notional

**Parameters:**
- `require_active_market` (default: true) - Only snapshot tokens from active markets (not closed/ended). Requires market metadata to be ingested via `/api/ingest/markets`.
- `include_inactive` (default: false) - Fall back to historical/inactive tokens if no active tokens found. Use this to diagnose old tokens.
The endpoint attempts a bounded backfill of missing market metadata using trade/position slugs before applying the active market filter.

**Token Selection Priority:**
1. Tokens from latest positions snapshot (highest priority - open positions)
2. Tokens from recent trades (within lookback_days window)
3. Active market filter: keeps only tokens with market metadata where market is active and not closed
4. Fallback: if no active tokens and `include_inactive=true`, uses last 50 distinct tokens from all trades

**Response Diagnostics:**
- `tokens_candidates_before_filter` - Total candidate tokens before active market filter
- `tokens_with_market_metadata` - Tokens that have market metadata in DB
- `tokens_after_active_filter` - Tokens remaining after active market filter
- `tokens_selected_total` - Final tokens selected for snapshotting
- `tokens_no_orderbook` - Tokens where the CLOB returned "No orderbook exists" (normal for inactive markets)
- `tokens_skipped_no_orderbook_ttl` - Tokens skipped due to recent no_orderbook status (TTL cache)
- `tokens_http_429` - Tokens that hit HTTP 429 from the CLOB
- `tokens_http_5xx` - Tokens that hit HTTP 5xx from the CLOB
- `no_ok_reason` - Diagnostic string explaining why no OK snapshots were produced

The snapshots are stored in `token_orderbook_snapshots` and can be used by PnL and arb feasibility computations as a pricing source instead of live API calls.

**Important:** Snapshots are only meaningful for active markets. If you see many `no_orderbook` statuses, the tokens are from closed markets. Use `include_inactive=true` to diagnose historical tokens, or run `/api/ingest/markets` to populate market metadata for active market filtering. The snapshotter will stop early once it reaches the configured OK target.

## Configuration

Environment variables:
- `GAMMA_API_BASE` - Gamma API URL (default: https://gamma-api.polymarket.com)
- `DATA_API_BASE` - Data API URL (default: https://data-api.polymarket.com)
- `INGEST_MAX_PAGES_DEFAULT` - Default max pages to fetch (default: 50)
- `HTTP_TIMEOUT_SECONDS` - Request timeout (default: 20)
- `CLICKHOUSE_HOST` - ClickHouse host (default: clickhouse)
- `CLICKHOUSE_PORT` - ClickHouse HTTP port (default: 8123)
- `CLICKHOUSE_USER` - ClickHouse username
- `CLICKHOUSE_PASSWORD` - ClickHouse password
- `CLICKHOUSE_DATABASE` - ClickHouse database (default: polyttool)

### Orderbook Snapshot Configuration
- `BOOK_SNAPSHOT_DEPTH_BAND_BPS` - Band for depth calculation (default: 50)
- `BOOK_SNAPSHOT_NOTIONALS` - Notional sizes for slippage, comma-separated (default: 100,500)
- `BOOK_SNAPSHOT_MAX_TOKENS` - Max tokens per snapshot run (default: 200)
- `BOOK_SNAPSHOT_MIN_OK_TARGET` - Stop once this many OK snapshots are captured (default: 5)
- `BOOK_SNAPSHOT_404_TTL_HOURS` - TTL window for skipping repeat no_orderbook checks (default: 24)
- `BOOK_SNAPSHOT_MAX_PREFLIGHT` - Max tokens to attempt per run (default: 200)
- `ORDERBOOK_SNAPSHOT_MAX_AGE_SECONDS` - Max snapshot age for PnL/arb pricing (default: 3600)

## Development

```bash
# Run locally (requires ClickHouse running)
pip install -r requirements.txt
python main.py

# Run with Docker Compose (recommended)
docker compose up -d api
```

## Trade UID Computation

Trade UIDs are computed to ensure idempotent ingestion:
1. Use the `id` field from the API response if present
2. Otherwise: `sha256(proxy_wallet + ts + token_id + side + size + price + transaction_hash + outcome + condition_id)`

This ensures the same trade always gets the same UID, preventing duplicates on reingestion.
