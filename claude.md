# Claude Code Guidelines for PolyTool

## Project Overview

PolyTool is a monorepo for Polymarket reverse-engineering tools and analysis infrastructure. It uses:

- **ClickHouse** for analytics storage
- **Grafana** for visualization
- **Python** for services (future)

## Repository Structure

- `/docs/specs/` - Codex specification files (DO NOT overwrite)
- `/docs/features/` - Feature documentation
- `/infra/` - Docker and infrastructure configuration
- `/services/` - Backend services (API, workers)
- `/packages/` - Shared libraries

## Key Rules

1. **Never commit secrets** - Use `.env` files (gitignored), only commit `.env.example`
2. **Specs are read-only** - Files in `/docs/specs/` should not be modified
3. **Local-first** - All infrastructure runs locally via Docker Compose
4. **No Kafka** - Out of scope until explicitly added

## Infrastructure

```bash
# Start all services
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f [service]

# Stop services
docker compose down
```

## Database Access

- **Admin**: `polyttool_admin` / `polyttool_admin` (full access)
- **Grafana**: `grafana_ro` / `grafana_readonly_local` (SELECT only)

## When Adding Features

1. Check `/docs/specs/` for relevant Codex specifications
2. Add new services under `/services/`
3. Add shared code under `/packages/`
4. Update Grafana dashboards in `/infra/grafana/dashboards/`
5. Add ClickHouse migrations in `/infra/clickhouse/initdb/` (prefix with number for ordering)

## Testing Infrastructure Changes

Always verify after infrastructure changes:

```bash
docker compose down -v && docker compose up -d
docker compose ps  # All services should be healthy
curl "http://localhost:8123/?query=SELECT%201"  # ClickHouse responds
# Check Grafana at http://localhost:3000
```
