#!/usr/bin/env bash
# Import all RIS n8n workflow templates into a running n8n instance.
# Usage: bash infra/n8n/import-workflows.sh [N8N_URL] [N8N_USER] [N8N_PASS]
#
# Requires: curl, jq
# n8n must be running: bash scripts/docker-start.sh --with-n8n
#
# Scope: RIS pilot workflows only (health check, scheduler status, manual acquire).
# See docs/adr/0013-ris-n8n-pilot-scoped.md for allowed workflow scope.
set -euo pipefail

N8N_URL="${1:-http://localhost:5678}"
N8N_USER="${2:-${N8N_BASIC_AUTH_USER:-admin}}"
N8N_PASS="${3:-${N8N_BASIC_AUTH_PASSWORD:-changeme}}"
WORKFLOW_DIR="$(dirname "$0")/workflows"

if ! command -v curl &>/dev/null; then
  echo "ERROR: curl is required." >&2
  exit 1
fi
if ! command -v jq &>/dev/null; then
  echo "ERROR: jq is required." >&2
  exit 1
fi

echo "Importing n8n workflows from $WORKFLOW_DIR into $N8N_URL ..."
echo ""

SUCCESS=0
FAIL=0

for wf in "$WORKFLOW_DIR"/*.json; do
  name=$(jq -r '.name' "$wf")
  echo "  Importing: $name ($wf) ..."
  response=$(curl -s -w "\n%{http_code}" \
    -u "$N8N_USER:$N8N_PASS" \
    -X POST "$N8N_URL/api/v1/workflows" \
    -H "Content-Type: application/json" \
    -d @"$wf")
  http_code=$(echo "$response" | tail -1)
  body=$(echo "$response" | head -n -1)
  if [[ "$http_code" == "200" || "$http_code" == "201" ]]; then
    echo "    OK (HTTP $http_code)"
    SUCCESS=$((SUCCESS + 1))
  else
    echo "    WARN: HTTP $http_code -- $body"
    FAIL=$((FAIL + 1))
  fi
done

echo ""
echo "Import complete: $SUCCESS succeeded, $FAIL failed."
echo ""
echo "Next steps:"
echo "  1. Log in to $N8N_URL (user: $N8N_USER)"
echo "  2. Review each imported workflow in the n8n UI."
echo "  3. Activate only the workflows you want running (all ship with active=false)."
echo "  4. For the webhook workflow, copy the webhook URL and treat it as a secret."
echo "  5. For cron triggers: confirm trigger times do not overlap with APScheduler runs."
echo ""
echo "IMPORTANT: Do NOT activate automated triggers while APScheduler (ris-scheduler)"
echo "  is also running -- this causes double-scheduling."
echo "  To switch: docker compose stop ris-scheduler"
echo "  See docs/adr/0013-ris-n8n-pilot-scoped.md for scheduler selection guidance."
echo ""
