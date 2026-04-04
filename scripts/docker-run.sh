#!/usr/bin/env bash
# Run a polytool CLI command inside Docker.
# Usage: bash scripts/docker-run.sh <command> [args...]
# Example: bash scripts/docker-run.sh wallet-scan --user @example_user
set -euo pipefail
cd "$(dirname "$0")/.."

if [ $# -eq 0 ]; then
  echo "Usage: bash scripts/docker-run.sh <polytool-command> [args...]"
  echo "Example: bash scripts/docker-run.sh research-health"
  echo "         bash scripts/docker-run.sh wallet-scan --user @example_user"
  exit 1
fi

docker compose run --rm polytool python -m polytool "$@"
