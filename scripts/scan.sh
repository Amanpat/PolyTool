#!/usr/bin/env bash
# =============================================================================
# scan.sh -- One-command on/off/status toggle for the wallet-discovery day run.
# Work packet: DR-1 (One-Command On/Off Toggle).
#
# Canonical operator interface:
#   bash scripts/scan.sh on        # start clickhouse + api + discovery-scheduler
#   bash scripts/scan.sh off        # stop ONLY discovery-scheduler (data store stays up)
#   bash scripts/scan.sh status     # service state + scan-queue depth + pending count
#
# Windows (PowerShell) usage -- Bash is available in this repo's toolchain:
#   bash scripts/scan.sh on
#   (or run via Git Bash / WSL: ./scripts/scan.sh status)
#
# SAFETY GUARDRAIL (HARD RULE -- DR-1 central safety property):
#   This wrapper NEVER calls `docker compose down` and NEVER passes `-v` /
#   `--volumes`. `down -v` (or `docker volume rm polytool_clickhouse_data`) is
#   the ONLY command that destroys ClickHouse's persistent named volume
#   `clickhouse_data`. Turning scans OFF must NEVER stop ClickHouse or the API
#   and must NEVER remove a volume. Any attempt to pass a teardown token through
#   this wrapper is actively refused below (see refuse_teardown).
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

# The three services this toggle manages. Kept in sync with
# docker-compose.yml and scripts/scan_status.py.
SERVICES=(clickhouse api discovery-scheduler)
SCHEDULER_SERVICE="discovery-scheduler"

usage() {
  cat <<'EOF'
Usage: bash scripts/scan.sh {on|off|status}

  on      Bring up clickhouse + api + discovery-scheduler (idempotent).
            -> docker compose up -d clickhouse api discovery-scheduler
  off     Stop ONLY the discovery-scheduler (ClickHouse + API stay up).
            -> docker compose stop discovery-scheduler
  status  Print service state + scan-queue depth + watchlist pending count.

Guardrail: this wrapper never runs `docker compose down` and never passes
`-v` / `--volumes`. Use `docker compose stop` / `start` to pause/resume;
NEVER `down -v` (that destroys the clickhouse_data volume).
EOF
}

# refuse_teardown: actively block any teardown/volume-destroying token passed
# through this wrapper. This is the enforced half of the HARD RULE above.
refuse_teardown() {
  local arg
  for arg in "$@"; do
    case "$arg" in
      down|-v|--volumes|--remove-orphans|rm|kill)
        echo "REFUSED: '$arg' is a teardown/volume-destroying operation." >&2
        echo "scripts/scan.sh never runs 'docker compose down' or passes '-v'." >&2
        echo "To pause scanning use: bash scripts/scan.sh off" >&2
        echo "ClickHouse data lives on the persistent named volume 'clickhouse_data';" >&2
        echo "only 'docker compose down -v' destroys it and this wrapper forbids that." >&2
        exit 2
        ;;
    esac
  done
}

cmd_on() {
  echo "scan on: bringing up ${SERVICES[*]} (idempotent)..."
  docker compose up -d "${SERVICES[@]}"
  echo ""
  echo "Scanning is ON. Stop with: bash scripts/scan.sh off"
}

cmd_off() {
  echo "scan off: stopping ${SCHEDULER_SERVICE} only (ClickHouse + API stay up)..."
  docker compose stop "${SCHEDULER_SERVICE}"
  echo ""
  echo "Scanning is OFF. ClickHouse + API remain up (Grafana/queries/status keep working)."
  echo "Resume with: bash scripts/scan.sh on"
}

cmd_status() {
  # Prefer python3, fall back to python (Windows).
  if command -v python3 >/dev/null 2>&1; then
    python3 scripts/scan_status.py
  else
    python scripts/scan_status.py
  fi
}

main() {
  if [ "$#" -lt 1 ]; then
    usage
    exit 1
  fi

  local action="$1"
  shift || true

  # Guardrail: refuse forbidden tokens passed as the action OR as extra args.
  refuse_teardown "$action" "$@"

  case "$action" in
    on)     cmd_on ;;
    off)    cmd_off ;;
    status) cmd_status ;;
    -h|--help|help) usage ;;
    *)
      echo "Unknown command: $action" >&2
      usage
      exit 1
      ;;
  esac
}

main "$@"
