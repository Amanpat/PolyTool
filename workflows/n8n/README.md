# RIS n8n Workflows

Workflow JSON files for the Research Intelligence System (RIS) n8n automation pilot.
All workflows are tagged `RIS` and use `settings.errorWorkflow` pointing to the Global Error Watcher.

## Workflow Inventory (as of 2026-04-07)

| File | n8n Workflow Name | ID | Schedule | Purpose |
|---|---|---|---|---|
| ris_sub_academic.json | RIS Sub: Academic | yDBfhk9tJQlAWJbz | Every 12h | arxiv/semantic scholar ingest |
| ris_sub_reddit.json | RIS Sub: Reddit | 34EhYveCbJie5hub | Every 6h | reddit_polymarket ingest |
| ris_sub_blog_rss.json | RIS Sub: Blog/RSS | fi2iglrNXcK9qXEg | Every 4h | blog_ingest |
| ris_sub_youtube.json | RIS Sub: YouTube | rHdYkf3Q6EgUC6KQ | Weekly Mon 04:00 UTC | youtube_ingest |
| ris_sub_github.json | RIS Sub: GitHub | 3rk0GiZM6GHJWq4z | Weekly Wed 04:00 UTC | github_ingest |
| ris_sub_weekly_digest.json | RIS Sub: Weekly Digest | 5wGKoPm7eJ3K2eIE | Weekly Sun 08:00 UTC | research-report digest + stats |
| ris_sub_freshness_refresh.json | RIS Sub: Freshness Refresh | vAiyicAFlnfq2RDh | Weekly Sun 02:00 UTC | freshness_refresh |
| ris_global_error_watcher.json | RIS Global Error Watcher | WFvBwCepYu8JzKDs | Error trigger | catch-all error handler for all 8 RIS workflows |
| ris_orchestrator.json | RIS Orchestrator | PEX5vHCexProT2sC | Every 30min + webhooks | health monitor, webhook dispatcher, URL ingest |

## Error Handling Pattern

Every sub-workflow follows a standard pattern:

1. **Execute Command** — `continueOnFail: true` — runs the docker exec command
2. **IF Exit Code OK** — branches on `exitCode == 0`
   - True path: Parse Metrics (code node) → Success (noOp)
   - False path: Format Error (code node) → Discord Alert (httpRequest, `continueOnFail: true`)
3. **settings.errorWorkflow** — set to Global Error Watcher ID on all 8 non-error-watcher workflows

Discord alerts use `$env.DISCORD_WEBHOOK_URL` — never hardcoded.

## Weekly Digest Special Flow

The digest workflow always sends a Discord message (success or partial failure) then conditionally sends a second error-detail alert if either command failed (non-zero exit code).

## Orchestrator Sections

**Section 1 — Health Monitor (every 30 min):**
Runs `research-health` + `research-stats summary`, parses stdout for RED/CRITICAL/FAIL/ERROR indicators, sends Discord alert only on detected issues.

**Section 2 — Webhook Dispatcher (POST /ris-trigger):**
Accepts `{"pipeline": "academic"}` etc., dispatches to the appropriate sub-workflow via Execute Workflow node, responds 200/400.

**Section 3 — URL Ingest (POST /ris-ingest):**
Accepts `{"url": "..."}`, runs `research-acquire`, responds 200 on success or 500 with Discord alert on failure.

## Global Error Watcher

`ris_global_error_watcher.json` — set as `settings.errorWorkflow` on all 8 other RIS workflows.
Catches unhandled errors, formats context (workflow name, node, execution ID, error message), sends Discord alert.

## Deployment History

| Date | Action |
|---|---|
| 2026-04-06 | Initial skeletal deployment (8 workflows, no error handling) |
| 2026-04-07 | Full rebuild — all 9 workflows redeployed with proper error handling, exit code checks, Discord alerting, continueOnFail, and Global Error Watcher |

## Re-deploying

All 9 JSON files are the canonical source. To redeploy:

1. POST each sub-workflow JSON to `/api/v1/workflows` (sub-workflows first, orchestrator last)
2. Inject real sub-workflow IDs into orchestrator's Execute Workflow nodes
3. PUT `settings.errorWorkflow` on all 8 non-error-watcher workflows
4. PUT tags: `[{"id": "lsdE5zgirb6IHxH5"}]` on all 9
5. POST `/api/v1/workflows/{id}/activate` on all 9
6. Update `workflow_ids.env`

## Environment Variables Required

- `N8N_API_KEY` — n8n REST API key
- `DISCORD_WEBHOOK_URL` — set as n8n environment variable in n8n settings (not in .env)
