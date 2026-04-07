# RIS n8n Workflows

Workflow JSON files for the Research Intelligence System (RIS) n8n automation.
As of 2026-04-07, the architecture is a **single unified workflow** with 9 sections on one canvas.

## Current Architecture: Unified Single-Canvas Workflow

**File:** `ris-unified-dev.json`
**n8n Name:** `RIS -- Research Intelligence System`
**Workflow ID:** `B34eBaBPIvLb8SYj`
**Node count:** 81 nodes across 9 sections

### Section Inventory

| # | Name | Trigger Type | Schedule | Nodes | Docker Command |
|---|------|--------------|----------|-------|----------------|
| 1 | Health Monitor | Schedule only | Every 30 min | 9 | `research-health` + `research-stats summary` |
| 2 | Academic | Schedule + Manual | Every 12h | 8 | `research-scheduler run-job academic_ingest` |
| 3 | Reddit | Schedule + Manual | Every 6h | 8 | `research-scheduler run-job reddit_polymarket` |
| 4 | Blog/RSS | Schedule + Manual | Every 4h | 8 | `research-scheduler run-job blog_ingest` |
| 5 | YouTube | Schedule + Manual | Weekly Mon 04:00 UTC | 8 | `research-scheduler run-job youtube_ingest` |
| 6 | GitHub | Schedule + Manual | Weekly Wed 04:00 UTC | 8 | `research-scheduler run-job github_ingest` |
| 7 | Freshness | Schedule + Manual | Weekly Sun 02:00 UTC | 8 | `research-scheduler run-job freshness_refresh` |
| 8 | Weekly Digest | Schedule + Manual | Weekly Sun 08:00 UTC | 10 | `research-report digest --window 7` + `research-stats summary` |
| 9 | URL Ingestion | Webhook | POST /webhook/ris-ingest | 7 | `research-acquire --url ... --source-family ...` |

## Error Handling Pattern

Every pipeline section follows a standard pattern:

1. **Schedule/Manual/Webhook trigger**
2. **Execute Command** -- `continueOnFail: true` -- runs the docker exec command
3. **IF Exit Code == 0** -- branches on success/failure
   - True path: Parse Metrics (code node) -> Done (set node)
   - False path: Format Error (code node) -> Discord Alert (httpRequest, `continueOnFail: true`)

Health Monitor (Section 1) uses a boolean check on `hasRed` instead of exitCode, and sends alert only when RED/CRITICAL is detected in stdout.

Discord alerts use `$env.DISCORD_WEBHOOK_URL` -- never hardcoded.

## Webhook Endpoints

| Endpoint | Method | Body | Response |
|----------|--------|------|----------|
| `/webhook/ris-ingest` | POST | `{"url": "...", "source_family": "academic|github|blog|news|book|reddit|youtube"}` | `{"status":"ingested"|"failed", ...}` |

## Docker Exec Pattern

All commands run against the `polytool-ris-scheduler` container:

```
docker exec polytool-ris-scheduler python -m polytool COMMAND 2>&1
```

## Deployment Instructions (Single POST + activate)

```bash
N8N_API_KEY=$(grep N8N_API_KEY .env | cut -d'=' -f2)

# 1. Deploy
RESULT=$(curl -s -X POST \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  -d @workflows/n8n/ris-unified-dev.json \
  http://localhost:5678/api/v1/workflows)

WF_ID=$(echo "$RESULT" | python -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Deployed ID: $WF_ID"

# 2. Activate
curl -s -X POST \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  http://localhost:5678/api/v1/workflows/$WF_ID/activate

# 3. Update workflow_ids.env
echo "UNIFIED_DEV_ID=$WF_ID" > workflows/n8n/workflow_ids.env
```

## Re-deploying

If you need to redeploy after changes to `ris-unified-dev.json`:

```bash
N8N_API_KEY=$(grep N8N_API_KEY .env | cut -d'=' -f2)
OLD_ID=$(grep UNIFIED_DEV_ID workflows/n8n/workflow_ids.env | cut -d'=' -f2)

# Delete old
curl -s -X DELETE -H "X-N8N-API-KEY: $N8N_API_KEY" http://localhost:5678/api/v1/workflows/$OLD_ID

# Re-deploy and activate (same as above)
```

## Environment Variables Required

- `N8N_API_KEY` -- n8n REST API key (in `.env`)
- `DISCORD_WEBHOOK_URL` -- set as n8n environment variable in n8n Settings > Variables (not in `.env`)

## Historical Files (not deployed, kept for reference)

The following files from the previous multi-workflow architecture are retained as reference:

- `ris_orchestrator.json` -- old orchestrator (health + webhook dispatcher + URL ingest)
- `ris_sub_academic.json`, `ris_sub_reddit.json`, `ris_sub_blog_rss.json`
- `ris_sub_youtube.json`, `ris_sub_github.json`, `ris_sub_freshness_refresh.json`
- `ris_sub_weekly_digest.json`
- `ris_global_error_watcher.json`

## Deployment History

| Date | Action |
|------|--------|
| 2026-04-06 | Initial skeletal deployment (8 workflows, no error handling) |
| 2026-04-07 | Full rebuild -- 9 separate workflows redeployed with proper error handling |
| 2026-04-07 | Architecture change -- unified to single-canvas workflow (81 nodes, 9 sections) |
