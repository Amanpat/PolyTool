# PolyTool

A monorepo for Polymarket reverse-engineering tools and analysis infrastructure.

## Prerequisites

- Docker and Docker Compose
- curl (for testing)

## Quick Start

```bash
# Clone the repository
git clone <repo-url>
cd PolyTool

# Copy environment file
cp .env.example .env

# Start all services
docker compose up -d --build

# Verify services are running
docker compose ps
```

All services should show as "healthy" after startup.

## Quickstart: Scan a user

```bash
# Start infrastructure (API + ClickHouse + Grafana)
docker compose up -d --build

# Configure env
cp .env.example .env
# Set TARGET_USER in .env (e.g. @432614799197 or 0x...)

# Run the one-shot scan (env-driven, with CLI overrides)
python tools/cli/scan.py
# or
python -m polyttool scan
```

Open Grafana at http://localhost:3000 and view:
- **PolyTool - User Trades**
- **PolyTool - Strategy Detectors**

Port mappings: API `8000`, Grafana `3000`, ClickHouse HTTP `18123`, ClickHouse Native `19000`.

## Services

| Service | URL | Description |
|---------|-----|-------------|
| API | http://localhost:8000 | PolyTool REST API |
| Swagger UI | http://localhost:8000/docs | Interactive API documentation |
| ClickHouse HTTP | http://localhost:18123 | Analytics database (HTTP interface) |
| ClickHouse Native | localhost:19000 | Analytics database (Native protocol) |
| Grafana | http://localhost:3000 | Dashboards (admin/admin) |

## Usage Examples

### 1. Ingest Market Metadata

Fetch market metadata from Polymarket to enable category analysis and outcome mapping:

```bash
curl -X POST http://localhost:8000/api/ingest/markets \
  -H "Content-Type: application/json" \
  -d '{"active_only": true}'
```

Response:
```json
{
  "pages_fetched": 15,
  "markets_total": 1423,
  "market_tokens_written": 2846
}
```

### 2. Resolve User

Resolve a username or wallet address to get profile information:

```bash
# By username
curl -X POST http://localhost:8000/api/resolve \
  -H "Content-Type: application/json" \
  -d '{"input": "@432614799197"}'

# By wallet address
curl -X POST http://localhost:8000/api/resolve \
  -H "Content-Type: application/json" \
  -d '{"input": "0x1234..."}'
```

### 3. Ingest User Trades

Fetch and store trade history for a user:

```bash
curl -X POST http://localhost:8000/api/ingest/trades \
  -H "Content-Type: application/json" \
  -d '{"user": "@432614799197", "max_pages": 20}'
```

Response:
```json
{
  "proxy_wallet": "0x...",
  "pages_fetched": 20,
  "rows_fetched_total": 2000,
  "rows_written": 2000,
  "distinct_trade_uids_total": 1847
}
```

### 4. Run Strategy Detectors

Run all 4 strategy detectors on a user's trade history:

```bash
curl -X POST http://localhost:8000/api/run/detectors \
  -H "Content-Type: application/json" \
  -d '{"user": "@432614799197", "bucket": "day"}'
```

Response:
```json
{
  "proxy_wallet": "0x...",
  "detectors_run": 4,
  "results": [
    {
      "detector": "HOLDING_STYLE",
      "score": 0.85,
      "label": "SCALPER",
      "evidence": {
        "median_hold_minutes": 12.5,
        "matched_trades": 423,
        "hold_distribution": {"<1h": 380, "1h-24h": 35, "1d-7d": 8, ">7d": 0}
      }
    },
    ...
  ],
  "features_computed": true
}
```

### 5. View Results in Grafana

1. Open http://localhost:3000
2. Login with `admin` / `admin`
3. Navigate to **Dashboards**:
   - **PolyTool - User Trades**: Trade history, volume, and token analysis
   - **PolyTool - Strategy Detectors**: Detector scores, labels, and evidence

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/resolve` | POST | Resolve username or wallet to profile |
| `/api/ingest/trades` | POST | Ingest user trade history |
| `/api/ingest/markets` | POST | Ingest market metadata |
| `/api/run/detectors` | POST | Run strategy detectors |
| `/api/users` | GET | List all ingested users |
| `/api/users/{wallet}/trades/stats` | GET | Get user trade statistics |

## Strategy Detectors

PolyTool includes 4 explainable strategy detectors:

### 1. HOLDING_STYLE
Classifies traders based on how long they hold positions.
- **SCALPER**: Median hold time < 1 hour
- **SWING**: Median hold time 1 hour - 7 days
- **HOLDER**: Median hold time > 7 days

Evidence includes hold time percentiles and distribution buckets.

### 2. DCA_LADDERING
Detects systematic dollar-cost averaging or ladder buying patterns.
- **DCA_LIKELY**: >30% of token/side groups show consistent sizing
- **RANDOM**: Trading sizes appear random

Evidence includes size coefficient of variation per token.

### 3. MARKET_SELECTION_BIAS
Measures category concentration using Herfindahl-Hirschman Index (HHI).
- **DIVERSIFIED**: HHI < 0.15 (spread across many categories)
- **MODERATE**: HHI 0.15 - 0.25
- **CONCENTRATED**: HHI > 0.25 (focused on few categories)

Evidence includes top categories and volume percentages.

### 4. COMPLETE_SET_ARBISH
Identifies potential complete-set arbitrage patterns.
- **ARB_LIKELY**: >30% of multi-outcome markets show both-outcome buys within 24h
- **NORMAL**: No significant arb patterns detected

Evidence includes matched arb events and average timing.

## Repository Structure

```
.
├── docs/
│   ├── specs/              # Codex specification files
│   └── features/           # Feature documentation
├── infra/
│   ├── clickhouse/         # ClickHouse configuration
│   │   └── initdb/         # Database initialization scripts
│   └── grafana/            # Grafana configuration
│       ├── provisioning/   # Auto-provisioned datasources & dashboards
│       └── dashboards/     # Dashboard JSON files
├── services/
│   └── api/                # FastAPI service
├── packages/
│   └── polymarket/         # Shared Polymarket API clients
├── docker-compose.yml      # Local infrastructure
└── .env.example            # Environment template
```

## Development

### Verifying ClickHouse

```bash
# HTTP interface (requires auth)
curl "http://localhost:18123/?query=SELECT%201&user=polyttool_admin&password=polyttool_admin"

# Using clickhouse-client in container
docker compose exec clickhouse clickhouse-client --query "SELECT 1"

# Check detector results
docker compose exec clickhouse clickhouse-client \
  --query "SELECT detector_name, score, label FROM polyttool.detector_results LIMIT 10"
```

### Stopping Services

```bash
docker compose down
```

### Resetting Data

```bash
docker compose down -v  # Removes volumes
docker compose up -d --build
```

## Configuration

See `.env.example` for available configuration options.

| Variable | Default | Description |
|----------|---------|-------------|
| `CLICKHOUSE_DB` | polyttool | Default database name |
| `CLICKHOUSE_USER` | polyttool_admin | Admin username |
| `CLICKHOUSE_PASSWORD` | polyttool_admin | Admin password |
| `GRAFANA_ADMIN_USER` | admin | Grafana admin username |
| `GRAFANA_ADMIN_PASSWORD` | admin | Grafana admin password |

## Known Limitations

- Hold time matching uses FIFO approximation (not exact cost-basis)
- Category mapping depends on Gamma API data quality
- COMPLETE_SET_ARBISH accuracy depends on market token mapping coverage
- Bucket support is available for day, hour, and week
