#!/usr/bin/env bash
# Start PolyTool Studio via Docker Compose and print the URL.
# Usage: bash scripts/studio_docker.sh

set -euo pipefail

PORT="${STUDIO_PORT:-8765}"

echo ""
echo "  PolyTool Studio"
echo "  Building and starting containers..."
echo ""

docker compose up --build -d

echo ""
echo "  Studio is running:"
echo "    http://localhost:${PORT}"
echo ""
echo "  Stop with: docker compose down"
echo ""
