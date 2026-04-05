#!/usr/bin/env bash
# Import all RIS n8n workflow templates into a running n8n instance.
# Usage: bash infra/n8n/import-workflows.sh [CONTAINER_NAME]
#
# Uses `n8n import:workflow` CLI (no API key required) via docker exec.
# The container must be running: docker compose --profile ris-n8n up -d n8n
#
# Scope: RIS pilot workflows only -- all RIS pilot workflows (11 total).
# Includes: health check, scheduler status, manual acquire, and 8 scheduler job templates
# (academic_ingest, reddit_polymarket, reddit_others, blog_ingest, youtube_ingest,
#  github_ingest, freshness_refresh, weekly_digest).
# See docs/adr/0013-ris-n8n-pilot-scoped.md for allowed workflow scope.
set -euo pipefail

CONTAINER="${1:-polytool-n8n}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKFLOW_DIR="$SCRIPT_DIR/workflows"

if ! docker ps --filter "name=${CONTAINER}" --filter status=running -q | grep -q .; then
  echo "ERROR: Container '${CONTAINER}' is not running." >&2
  echo "       Start it with: docker compose --profile ris-n8n up -d n8n" >&2
  exit 1
fi

echo "Importing n8n workflows from $WORKFLOW_DIR into container '${CONTAINER}' ..."
echo ""

SUCCESS=0
FAIL=0

for wf in "$WORKFLOW_DIR"/*.json; do
  name=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('name','unknown'))" "$wf" 2>/dev/null || basename "$wf" .json)
  dest="/tmp/$(basename "$wf")"
  echo "  Importing: $name ..."
  if docker cp "$wf" "${CONTAINER}:${dest}" 2>/dev/null && \
     MSYS_NO_PATHCONV=1 docker exec "$CONTAINER" n8n import:workflow --input="$dest" 2>/dev/null; then
    echo "    OK"
    SUCCESS=$((SUCCESS + 1))
  else
    echo "    WARN: import failed for $wf"
    FAIL=$((FAIL + 1))
  fi
done

echo ""
echo "Import complete: $SUCCESS succeeded, $FAIL failed."
echo ""
echo "Next steps:"
echo "  1. Log in to http://localhost:5678"
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
