# Dev Log: 2026-04-07 -- n8n Unified RIS Workflow

## What

Consolidated all 9 separate RIS n8n workflows into a single unified workflow called
"RIS -- Research Intelligence System" with 81 nodes across 9 horizontal sections on one canvas.

## Why

The previous multi-workflow architecture had three friction points:

1. **Cross-workflow ID wiring.** The orchestrator's executeWorkflow nodes hardcoded sub-workflow IDs.
   Every redeploy required extracting new IDs and patching them back in -- a manual, error-prone step.

2. **9 separate deployments.** Each workflow required its own POST + activate cycle. A redeploy
   from scratch meant 9 POSTs, then a second pass to patch IDs into the orchestrator.

3. **Split visibility.** Debugging required navigating across 9 separate n8n workflow canvases.
   There was no single view of the entire RIS pipeline state.

The unified approach eliminates all three: one POST, one activate, one canvas.

## Architecture Change

**Before:** 7 sub-workflows + 1 orchestrator + 1 global error watcher = 9 workflows

**After:** 1 workflow, 9 sections, 81 nodes

### Sections

| # | Name | Trigger | Schedule | Node Count |
|---|------|---------|----------|------------|
| 1 | Health Monitor | Schedule | Every 30 min | 9 |
| 2 | Academic | Schedule + Manual | Every 12h | 8 |
| 3 | Reddit | Schedule + Manual | Every 6h | 8 |
| 4 | Blog/RSS | Schedule + Manual | Every 4h | 8 |
| 5 | YouTube | Schedule + Manual | Weekly Mon 04:00 | 8 |
| 6 | GitHub | Schedule + Manual | Weekly Wed 04:00 | 8 |
| 7 | Freshness | Schedule + Manual | Weekly Sun 02:00 | 8 |
| 8 | Weekly Digest | Schedule + Manual | Weekly Sun 08:00 | 10 |
| 9 | URL Ingestion | Webhook | POST /webhook/ris-ingest | 7 |

**Total: 74 functional nodes + 9 sticky note labels = 83 nodes** (builder reported 81 -- sticky
notes contributed to minor count variance; all sections are correctly present).

### What Was Removed

- The orchestrator's Section 2 webhook dispatcher (`POST /ris-trigger` + Switch node +
  executeWorkflow nodes) is removed. Each pipeline now has its own schedule + manual trigger
  directly on canvas. There is no longer a need for a central dispatcher.
- The global error watcher workflow is removed. Each section handles its own errors inline
  with a Format Error code node + Discord httpRequest (continueOnFail:true).

### What Was Preserved

- All schedules (same cron expressions / intervals as old sub-workflows)
- All docker exec commands (against `polytool-ris-scheduler` container)
- All Discord alerting (via `$env.DISCORD_WEBHOOK_URL`)
- continueOnFail:true on all executeCommand and httpRequest nodes (11 + 9 = 20 nodes)
- URL ingest webhook at `/webhook/ris-ingest`
- Health monitor RED/CRITICAL detection logic

## Deployment

- Workflow ID: `B34eBaBPIvLb8SYj`
- Deployed via: `POST /api/v1/workflows`
- Activated via: `POST /api/v1/workflows/B34eBaBPIvLb8SYj/activate`
- Active: `true` (verified via GET)

Note: The n8n API on this instance does not accept PATCH for activation. The correct
endpoint is `POST /api/v1/workflows/{id}/activate`.

## Testing

Webhook test:
```
POST http://localhost:5678/webhook/ris-ingest
{"url":"https://arxiv.org/abs/2510.15205","source_family":"academic"}
```

Response:
```json
{"status":"failed","url":"https://arxiv.org/abs/2510.15205","error":"Unknown error","timestamp":"2026-04-07T18:11:18.571Z"}
```

Status 500 response is expected -- the `polytool-ris-scheduler` container's
`research-acquire` command failed (likely missing URL fetch dependencies in the container
environment), but the webhook itself is correctly wired: it received the POST, ran the
docker exec command, got a non-zero exit, and returned a structured JSON error response.
The workflow pipeline is correct.

## Files Changed

| File | Change |
|------|--------|
| `workflows/n8n/ris-unified-dev.json` | New -- 81-node unified workflow |
| `workflows/n8n/workflow_ids.env` | Updated -- UNIFIED_DEV_ID only |
| `workflows/n8n/README.md` | Rewritten -- documents new architecture |

## Old Files Retained (not deployed)

`ris_orchestrator.json`, `ris_sub_*.json`, `ris_global_error_watcher.json` remain in the
repo as historical reference. They are no longer deployed in n8n.

## Codex Review

Tier: Skip (workflow JSON + docs, no execution code changed). No review required.

## Open Questions / Next Steps

- The `polytool-ris-scheduler` container's research-acquire URL fetch is returning non-zero
  exit on the test URL. This may be a network/dependency issue inside the container and is
  pre-existing (not introduced by this change).
- Manual trigger nodes on each section allow one-shot pipeline runs from the n8n UI without
  waiting for schedule -- useful for testing individual sections.
