#!/usr/bin/env bash
# Start the full PolyTool stack via Docker Compose.
# Usage: bash scripts/docker-start.sh [--with-bots] [--with-n8n]
#
# Scheduler selection:
#   Default: APScheduler runs via ris-scheduler service (always on).
#   --with-n8n: n8n starts instead. You MUST stop the ris-scheduler service
#     (docker compose stop ris-scheduler) to prevent double-scheduling, OR set
#     RIS_SCHEDULER_BACKEND=n8n in .env to document the active selection.
#     Running both simultaneously causes double-scheduling (operator error).
#     See docs/adr/0013-ris-n8n-pilot-scoped.md for scheduler selection guidance.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "ERROR: .env file not found. Copy .env.example to .env and fill in secrets first."
  exit 1
fi

PROFILES=""
WITH_N8N=false

for arg in "$@"; do
  case "$arg" in
    --with-bots) PROFILES="$PROFILES --profile pair-bot" ;;
    --with-n8n)  PROFILES="$PROFILES --profile ris-n8n"; WITH_N8N=true ;;
  esac
done

if [ "$WITH_N8N" = "true" ]; then
  echo "Starting full stack WITH n8n RIS pilot..."
  echo "  WARNING: If ris-scheduler is also running, double-scheduling will occur."
  echo "  To prevent double-scheduling: docker compose stop ris-scheduler"
  echo "  Tip: docker compose stop ris-scheduler  (prevents double-scheduling)"
  echo "  See docs/adr/0013-ris-n8n-pilot-scoped.md for scheduler selection guidance."
else
  echo "Starting full stack (ClickHouse, Grafana, API, RIS scheduler)..."
  echo "  Add --with-n8n to start n8n instead of APScheduler (see ADR 0013)."
  echo "  Add --with-bots to also start pair-bot services."
fi

docker compose $PROFILES up -d --build

echo ""
echo "Services:"
echo "  ClickHouse:  http://localhost:${CLICKHOUSE_HTTP_PORT:-8123}"
echo "  Grafana:     http://localhost:${GRAFANA_PORT:-3000}"
echo "  API:         http://localhost:${API_PORT:-8000}"
if [ "$WITH_N8N" = "true" ]; then
  echo "  n8n:         http://localhost:${N8N_PORT:-5678}"
fi
echo ""
echo "CLI usage:     docker compose run --rm polytool python -m polytool --help"
echo "Stop:          docker compose down"
echo ""
