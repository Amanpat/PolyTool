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
