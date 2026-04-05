# RIS Pipeline n8n Workflows

## Overview

8 workflow JSON files for RIS (Research Intelligence System) pipeline automation via n8n.
These are v2 enhanced workflows with Discord failure alerting, health status parsing,
and webhook response. They replace the minimal v1 pilot templates in `infra/n8n/workflows/`.

## Prerequisites

- n8n running at http://localhost:5678 — start with:
  ```
  docker compose --profile ris-n8n up -d
  ```
- `DISCORD_WEBHOOK_URL` environment variable configured in n8n (see Environment Variables section)
- The main polytool container `polytool-polytool-1` running

## Import Instructions

1. Open n8n at http://localhost:5678
2. Click your user icon (bottom-left) then **Import from File**
3. Select the workflow JSON file from this directory
4. Click **Save** then toggle the workflow to **Active**
5. Repeat for all 8 workflows

## Workflow Matrix

| File | Schedule | Job | Discord Alert |
|------|----------|-----|---------------|
| ris-academic-ingestion.json | Every 12h | academic_ingest | On failure |
| ris-reddit-ingestion.json | Every 6h | reddit_polymarket | On failure |
| ris-blog-ingestion.json | Every 4h | blog_ingest | On failure |
| ris-youtube-ingestion.json | Weekly Mon 04:00 | youtube_ingest | On failure |
| ris-github-ingestion.json | Weekly Wed 04:00 | github_ingest | On failure |
| ris-health-monitor.json | Every 30min | research-health | On RED status only |
| ris-weekly-digest.json | Weekly Sun 08:00 | research-report + research-stats | Always (digest) |
| ris-manual-ingest.json | Webhook POST | research-acquire | N/A (webhook response) |

## Environment Variables

`DISCORD_WEBHOOK_URL` must be configured in n8n before any Discord alert node fires.
Set it via:

- **n8n Settings > Variables** (recommended): add `DISCORD_WEBHOOK_URL` as a variable.
- **Docker environment**: pass `-e DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...`
  to the n8n container in `docker-compose.yml` or `.env`.

If `DISCORD_WEBHOOK_URL` is not set, Discord alert nodes will silently fail. The ingestion
commands themselves will still run.

## Mutual Exclusion Note

If APScheduler (`ris-scheduler` container) is also running, **do NOT activate the cron/interval
triggers** for the ingestion workflows. Running both causes double-scheduling of research jobs.

Stop APScheduler first:

```
docker compose stop ris-scheduler
```

The health monitor and manual ingest webhook are safe to run alongside APScheduler.

## Manual Ingest Usage

POST to the webhook to trigger a one-off research acquisition:

```bash
curl -X POST http://localhost:5678/webhook/ris-ingest \
  -H "Content-Type: application/json" \
  -d '{"url": "https://arxiv.org/abs/2312.00001", "source_family": "academic"}'
```

Valid `source_family` values: `academic`, `github`, `blog`, `news`, `book`, `reddit`, `youtube`

The webhook responds with JSON: `{"success": true, "result": "...", "exit_code": 0, "stderr": ""}`.

## Relationship to infra/n8n/workflows/

`infra/n8n/workflows/` contains the original v1 pilot templates with these limitations:
- No error handling or Discord alerting
- No IF nodes or Code nodes
- Container name `polytool-ris-scheduler` (deprecated)
- `active: false` by default

This directory (`workflows/n8n/`) contains the v2 production workflows. The v1 templates
are preserved for reference only. Import from this directory for any new deployments.
