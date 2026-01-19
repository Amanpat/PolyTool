# PolyTool

A monorepo for Polymarket reverse-engineering tools and analysis infrastructure.

## Quick Start

```bash
# Copy environment file
cp .env.example .env

# Start infrastructure
docker compose up -d

# Verify services are running
docker compose ps
```

## Services

| Service | URL | Description |
|---------|-----|-------------|
| ClickHouse | http://localhost:18123 | Analytics database (HTTP) |
| ClickHouse | localhost:19000 | Analytics database (Native) |
| Grafana | http://localhost:3000 | Dashboards (admin/admin) |

## Repository Structure

```
.
├── docs/
│   ├── specs/           # Codex specification files
│   └── features/        # Feature documentation
├── infra/
│   ├── clickhouse/      # ClickHouse configuration
│   │   └── initdb/      # Database initialization scripts
│   └── grafana/         # Grafana configuration
│       ├── provisioning/  # Auto-provisioned datasources & dashboards
│       └── dashboards/    # Dashboard JSON files
├── services/
│   ├── api/             # API service (future)
│   └── worker/          # Background workers (future)
├── packages/
│   └── polymarket/      # Shared Polymarket utilities (future)
├── docker-compose.yml   # Local infrastructure
└── .env.example         # Environment template
```

## Verifying the Setup

### ClickHouse

```bash
# HTTP interface (requires auth)
curl "http://localhost:18123/?query=SELECT%201&user=polyttool_admin&password=polyttool_admin"

# Or using clickhouse-client in container
docker compose exec clickhouse clickhouse-client --query "SELECT 1"
```

### Grafana

1. Open http://localhost:3000
2. Login with admin/admin
3. Navigate to Dashboards → "PolyTool - Infra Smoke"
4. Verify the heartbeat panel shows data

## Development

### Stopping Services

```bash
docker compose down
```

### Resetting Data

```bash
docker compose down -v  # Removes volumes
docker compose up -d
```

## Configuration

See `.env.example` for available configuration options. Copy to `.env` and modify as needed.

| Variable | Default | Description |
|----------|---------|-------------|
| `CLICKHOUSE_DB` | polyttool | Default database name |
| `CLICKHOUSE_USER` | polyttool_admin | Admin username |
| `CLICKHOUSE_PASSWORD` | polyttool_admin | Admin password |
| `GRAFANA_ADMIN_USER` | admin | Grafana admin username |
| `GRAFANA_ADMIN_PASSWORD` | admin | Grafana admin password |
