# RIS n8n Workflows

Workflow JSON files for the Research Intelligence System (RIS) n8n automation.
As of 2026-04-07, the architecture is a **single unified workflow** with 9 sections on one canvas.

## Canonical Source

`workflows/n8n/ris-unified-dev.json` is the main RIS pilot workflow source in this repo.
`workflows/n8n/ris-health-webhook.json` is the dedicated operator/smoke health-check
workflow. `python infra/n8n/import_workflows.py` imports both by default.

`infra/n8n/` remains the Docker/image/tooling location only. The older JSON files in
`infra/n8n/workflows/` are legacy/reference-only, and the other JSON files in this
directory are historical multi-workflow artifacts that are not imported by default.

This remains a scoped RIS pilot only. It is not broad n8n orchestration for the repo.

## Current Architecture: Unified Single-Canvas Workflow

**File:** `ris-unified-dev.json`
**n8n Name:** `RIS -- Research Intelligence System`
**Workflow ID:** `B34eBaBPIvLb8SYj`
**Node count:** 82 nodes across 9 sections

By default, the schedule trigger nodes are disabled in the committed JSON so the
workflow can be safely activated for manual runs and the ingest webhook without
double-scheduling alongside APScheduler. If an operator chooses n8n scheduling
later, they must explicitly enable the relevant schedule nodes in the UI.

### Section Inventory

| # | Name | Trigger Type | Schedule | Nodes | Docker Command |
|---|------|--------------|----------|-------|----------------|
| 1 | Health Monitor | Manual + Schedule | Every 30 min | 10 | `research-health` + `research-stats summary` |
| 2 | Academic | Manual + Schedule | Every 12h | 8 | `research-scheduler run-job academic_ingest` |
| 3 | Reddit | Manual + Schedule | Every 6h | 8 | `research-scheduler run-job reddit_polymarket` |
| 4 | Blog/RSS | Manual + Schedule | Every 4h | 8 | `research-scheduler run-job blog_ingest` |
| 5 | YouTube | Manual + Schedule | Weekly Mon 04:00 UTC | 8 | `research-scheduler run-job youtube_ingest` |
| 6 | GitHub | Manual + Schedule | Weekly Wed 04:00 UTC | 8 | `research-scheduler run-job github_ingest` |
| 7 | Freshness | Manual + Schedule | Weekly Sun 02:00 UTC | 8 | `research-scheduler run-job freshness_refresh` |
| 8 | Weekly Digest | Manual + Schedule | Weekly Sun 08:00 UTC | 10 | `research-report digest --window 7` + `research-stats summary` |
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
| `/webhook/ris-health` | GET | none | `{"command":"research-health","status":"ok"|"alert",...}` |
| `/webhook/ris-ingest` | POST | `{"url": "...", "source_family": "academic|github|blog|news|book|reddit|youtube"}` | `{"status":"ingested"|"failed", ...}` |

## Docker Exec Pattern

All commands run against the `polytool-ris-scheduler` container:

```
docker exec polytool-ris-scheduler python -m polytool COMMAND 2>&1
```

## Default CLI Import

```bash
python infra/n8n/import_workflows.py
```

This imports the canonical workflow JSON, `workflows/n8n/ris-unified-dev.json`, via the
n8n REST API, updates `workflows/n8n/workflow_ids.env`, and activates the workflows.

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

## Historical Files (not imported by default, kept for reference)

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
