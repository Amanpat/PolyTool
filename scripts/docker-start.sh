#!/usr/bin/env bash
# Start the full PolyTool stack via Docker Compose.
# Usage: bash scripts/docker-start.sh [--with-bots]
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "ERROR: .env file not found. Copy .env.example to .env and fill in secrets first."
  exit 1
fi

PROFILES=""
if [[ "${1:-}" == "--with-bots" ]]; then
  PROFILES="--profile pair-bot"
  echo "Starting full stack with pair bots..."
else
  echo "Starting full stack (ClickHouse, Grafana, API, RIS scheduler)..."
  echo "  Add --with-bots to also start pair-bot services."
fi

docker compose $PROFILES up -d --build

echo ""
echo "Services:"
echo "  ClickHouse:  http://localhost:${CLICKHOUSE_HTTP_PORT:-8123}"
echo "  Grafana:     http://localhost:${GRAFANA_PORT:-3000}"
echo "  API:         http://localhost:${API_PORT:-8000}"
echo ""
echo "CLI usage:     docker compose run --rm polytool python -m polytool --help"
echo "Stop:          docker compose down"
echo ""
