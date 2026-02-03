# PolyTool

A monorepo for Polymarket reverse-engineering tools and analysis infrastructure.

## Prerequisites

- Docker and Docker Compose
- curl (for testing)

## Documentation index

See [docs/README.md](docs/README.md) for the documentation index.

## Knowledge base conventions

See [docs/KNOWLEDGE_BASE_CONVENTIONS.md](docs/KNOWLEDGE_BASE_CONVENTIONS.md) for the
public/private boundary and the required Agent Run Log in `kb/devlog/` for every agent run.

## CLI overview

PolyTool ships a local CLI with these commands (matches `python -m polyttool --help`):

```
python -m polyttool scan
python -m polyttool export-dossier
python -m polyttool export-clickhouse
python -m polyttool rag-index
python -m polyttool rag-query
python -m polyttool rag-eval
```

Run `python -m polyttool <command> --help` for command-specific flags.

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

## Safety check before pushing

```powershell
python tools/guard/pre_push_guard.py
```

## Quickstart: Scan a user

```bash
# Start infrastructure (API + ClickHouse + Grafana)
docker compose up -d --build

# Configure env
cp .env.example .env
# Set TARGET_USER in .env (e.g. @432614799197 or 0x...)

# Run the one-shot scan (env-driven, with CLI overrides)
python -m polyttool scan

# Legacy wrapper (same behavior)
python tools/cli/scan.py

# Optional: include activity + positions snapshots and compute PnL
python -m polyttool scan --ingest-activity --ingest-positions --compute-pnl
```

Scan flags can also be set via `SCAN_INGEST_ACTIVITY=true`, `SCAN_INGEST_POSITIONS=true`, and `SCAN_COMPUTE_PNL=true`.

Open Grafana at http://localhost:3000 and view:
- **PolyTool - User Trades**
- **PolyTool - Strategy Detectors**
- **PolyTool - PnL**

Port mappings: API `8000`, Grafana `3000`, ClickHouse HTTP `18123`, ClickHouse Native `19000`.

## Local RAG workflow (end-to-end)

See [docs/LOCAL_RAG_WORKFLOW.md](docs/LOCAL_RAG_WORKFLOW.md) for the full local-first workflow and scoping details.
Short version:

```bash
python -m polyttool scan
python -m polyttool export-dossier --user "@Pimping"
python -m polyttool export-clickhouse --user "@Pimping"
python -m polyttool rag-index --roots "kb,artifacts" --rebuild
python -m polyttool rag-query --question "Most recent evidence" --hybrid --rerank --k 8
```

For the Opus 4.5 evidence bundle template, see [docs/OPUS_BUNDLE_WORKFLOW.md](docs/OPUS_BUNDLE_WORKFLOW.md).

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

### 4. Ingest User Activity

Fetch public activity events for a user:

```bash
curl -X POST http://localhost:8000/api/ingest/activity \
  -H "Content-Type: application/json" \
  -d '{"user": "@432614799197", "max_pages": 20}'
```

Response:
```json
{
  "proxy_wallet": "0x...",
  "pages_fetched": 10,
  "rows_fetched_total": 500,
  "rows_written": 500,
  "distinct_activity_uids_total": 480
}
```

### 5. Ingest User Positions (Snapshot)

Capture the latest positions snapshot for a user:

```bash
curl -X POST http://localhost:8000/api/ingest/positions \
  -H "Content-Type: application/json" \
  -d '{"user": "@432614799197"}'
```

Response:
```json
{
  "proxy_wallet": "0x...",
  "snapshot_ts": "2026-01-19T22:15:03.123456",
  "rows_written": 42
}
```

### 6. Run Strategy Detectors

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

### 7. Compute PnL (Realized + MTM)

Compute realized PnL (FIFO) and conservative MTM PnL using CLOB best bid/ask:

```bash
curl -X POST http://localhost:8000/api/compute/pnl \
  -H "Content-Type: application/json" \
  -d '{"user": "@432614799197", "bucket": "day"}'
```

Response:
```json
{
  "proxy_wallet": "0x...",
  "bucket_type": "day",
  "buckets_written": 30,
  "tokens_priced": 18,
  "tokens_skipped_missing_orderbook": [],
  "tokens_skipped_limit": [],
  "latest_bucket": {
    "bucket_start": "2026-01-19T00:00:00",
    "realized_pnl": 12.34,
    "mtm_pnl_estimate": -1.92,
    "exposure_notional_estimate": 104.2,
    "open_position_tokens": 3
  }
}
```

PnL notes:
- Realized PnL uses FIFO matching of buys and sells per token (approximate).
- MTM PnL values longs at current best bid and shorts at current best ask.
- Exposure notional uses mid price: `(bestBid + bestAsk) / 2`.
- Positions snapshots are preferred within a bucket; otherwise net shares are derived from trades.

### 8. Compute Arb Feasibility

Analyze arb-like activity with dynamic fee rates and slippage estimates:

```bash
curl -X POST http://localhost:8000/api/compute/arb_feasibility \
  -H "Content-Type: application/json" \
  -d '{"user": "@432614799197", "bucket": "day"}'
```

Response:
```json
{
  "proxy_wallet": "0x...",
  "bucket_type": "day",
  "buckets_computed": 5,
  "fee_rates_fetched": 10,
  "slippage_estimates": 8,
  "markets_analyzed": 12,
  "tokens_skipped_limit": [],
  "tokens_skipped_missing_book": [],
  "latest_buckets": [
    {
      "bucket_start": "2026-01-15T00:00:00",
      "condition_id": "0x...",
      "total_fees_est_usdc": 0.025,
      "total_slippage_est_usdc": 0.12,
      "break_even_notional_usd": 14.5,
      "confidence": "high"
    }
  ]
}
```

### 9. View Results in Grafana

1. Open http://localhost:3000
2. Login with `admin` / `admin`
3. Navigate to **Dashboards**:
   - **PolyTool - User Trades**: Trade history, activity volume, positions, and market tables
   - **PolyTool - Strategy Detectors**: Detector scores, labels, and evidence
   - **PolyTool - PnL**: Realized PnL, conservative MTM PnL, and exposure over time
   - **PolyTool - Arb Feasibility**: Fee and slippage costs, break-even analysis

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/resolve` | POST | Resolve username or wallet to profile |
| `/api/ingest/trades` | POST | Ingest user trade history |
| `/api/ingest/activity` | POST | Ingest user activity feed |
| `/api/ingest/positions` | POST | Ingest user positions snapshot |
| `/api/ingest/markets` | POST | Ingest market metadata |
| `/api/run/detectors` | POST | Run strategy detectors |
| `/api/compute/pnl` | POST | Compute realized + MTM PnL buckets |
| `/api/compute/arb_feasibility` | POST | Compute arb feasibility with dynamic fees + slippage |
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

## Arb Feasibility Methodology

The `/api/compute/arb_feasibility` endpoint provides realistic cost estimates for arb-like activity.

### Fee Computation

Taker fees are computed using Polymarket's fee curve formula:

```
fee_usdc = shares * price * (fee_rate_bps / 10000) * (price * (1 - price))^2
```

- **fee_rate_bps**: Fetched dynamically per token from `GET /fee-rate?token_id=...`
- **Exponent**: 2.0 (quadratic curve) - fees are lower at extreme prices (near 0 or 1)
- **At price=0.5**: Maximum curve factor (0.0625)
- **At price=0.1 or 0.9**: Lower curve factor (0.0081)

**Note**: The fee curve parameters are subject to change by Polymarket. The live `/fee-rate` endpoint is always used for current rates.

### Slippage Estimation

Slippage is estimated by simulating execution through the live orderbook:

1. Fetch orderbook via `GET /book?token_id=...`
2. For BUY orders: walk asks from best (lowest) to worst until size is filled
3. For SELL orders: walk bids from best (highest) to worst until size is filled
4. Compute VWAP (volume-weighted average price) of simulated fills
5. Calculate slippage vs mid-price: `slippage_bps = (VWAP - mid) / mid * 10000`

**Confidence Levels**:
- **high**: Full size simulated through orderbook
- **medium**: Partial fill simulated, remaining extrapolated
- **low**: Insufficient depth - marked with "insufficient depth"

### Break-Even Notional

The break-even notional estimates how much notional value is needed to cover costs:

```
break_even_notional = total_costs / assumed_edge_rate
```

A conservative 1% edge rate assumption is used. Actual break-even depends on the realized edge, which varies by market conditions.

### Evidence JSON

Each arb bucket includes detailed evidence:
- `fee_rate_bps_values`: Fee rates fetched per token
- `slippage_bps_values`: Slippage estimates per token/side
- `book_timestamps`: When orderbook data was fetched
- `total_notional_usd`: Approximate notional of the arb event
- `time_span_hours`: Time between first and last trade

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

### Smoke contract check

Prerequisites:
- Stack is running (`docker compose up -d --build`)

Run:
```powershell
tools/run_smoke.ps1
```
or
```bash
python tools/smoke/smoke_api_contract.py
```

Success looks like:
- `/health` returns 200
- `/api/compute/pnl` returns 200 (or a 4xx for invalid user input, but not 500)
- `/api/compute/arb_feasibility` returns 200 (or a 4xx for invalid user input, but not 500)

### Troubleshooting: No Data / Duplicates

- No activity/positions data: run `/api/ingest/activity` and `/api/ingest/positions`, then refresh Grafana.
- Missing market names: run `/api/ingest/markets` or enable `--ingest-markets` in the scan CLI.
- Duplicate detector or bucket rows: Grafana panels now dedupe via `argMax(...)`; if needed, run `OPTIMIZE TABLE detector_results FINAL`.
- PnL pricing and snapshot fallback details: see [docs/archive/TROUBLESHOOTING_PNL.md](docs/archive/TROUBLESHOOTING_PNL.md).

### Stopping Services

```bash
docker compose down
```

### Schema Migrations

When you pull updates that add new ClickHouse tables, views, or grants, you may need to apply schema migrations to an existing database volume. The `migrate` service runs all SQL files from `infra/clickhouse/initdb/` in order.

**When to run migrations:**
- After pulling updates that introduce new tables or views
- If you see "missing table" errors (e.g., `user_pnl_bucket`)
- After adding new schema files to `infra/clickhouse/initdb/`

**Run migrations:**
```bash
docker compose run --rm migrate
```

**Verify migrations:**
```bash
# Check that all tables exist
docker compose exec -T clickhouse clickhouse-client \
  --query "SHOW TABLES FROM polyttool"
```

All SQL files are idempotent (use `IF NOT EXISTS`, `CREATE OR REPLACE`, etc.), so you can safely run migrations multiple times.

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
| `CLOB_API_BASE` | https://clob.polymarket.com | CLOB API base URL |
| `PNL_BUCKET_DEFAULT` | day | Default PnL bucket type |
| `PNL_ORDERBOOK_CACHE_SECONDS` | 30 | CLOB orderbook cache TTL |
| `PNL_MAX_TOKENS_PER_RUN` | 200 | Safety cap on tokens priced |
| `PNL_HTTP_TIMEOUT_SECONDS` | 20 | CLOB request timeout |
| `SCAN_COMPUTE_PNL` | false | Run PnL compute after scan |
| `ARB_CACHE_SECONDS` | 30 | Fee/book cache TTL for arb computation |
| `ARB_MAX_TOKENS_PER_RUN` | 200 | Safety cap on tokens for arb analysis |

## Known Limitations

- Hold time matching uses FIFO approximation (not exact cost-basis)
- Category mapping depends on Gamma API data quality
- COMPLETE_SET_ARBISH accuracy depends on market token mapping coverage
- Bucket support is available for day, hour, and week
- Positions are point-in-time snapshots (frequency depends on ingestion cadence)
- Market tagging heuristics are best-effort (keyword-based)
- MTM and exposure use current CLOB best bid/ask (orderbook freshness and rate limits apply)
- Slippage is estimated from current orderbook, not historical depth at trade time
- Fee curve parameters (exponent) may change; always use live /fee-rate endpoint for rates
- Break-even notional uses a 1% assumed edge rate which may differ from actual edges
