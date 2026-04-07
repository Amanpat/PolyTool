# 2026-04-07: RIS n8n Workflow Full Rebuild

## Task

Quick task 260407-inu. Deleted and rebuilt all 8 existing skeletal RIS n8n workflows from
scratch with proper error handling, then added a 9th Global Error Watcher workflow.

## Motivation

The original 8 workflows deployed on 2026-04-06 were skeletal placeholders — they ran
commands but had no exit code checks, no error branches, no Discord alerting on failure,
and no `continueOnFail` safety on Execute Command and HTTP nodes. A single node failure
would silently halt execution with no visibility.

## What Was Built

### 9 Workflow Files (all in `workflows/n8n/`)

| Workflow | ID | Schedule |
|---|---|---|
| RIS Sub: Academic | yDBfhk9tJQlAWJbz | Every 12h |
| RIS Sub: Reddit | 34EhYveCbJie5hub | Every 6h |
| RIS Sub: Blog/RSS | fi2iglrNXcK9qXEg | Every 4h |
| RIS Sub: YouTube | rHdYkf3Q6EgUC6KQ | Weekly Mon 04:00 UTC |
| RIS Sub: GitHub | 3rk0GiZM6GHJWq4z | Weekly Wed 04:00 UTC |
| RIS Sub: Weekly Digest | 5wGKoPm7eJ3K2eIE | Weekly Sun 08:00 UTC |
| RIS Sub: Freshness Refresh | vAiyicAFlnfq2RDh | Weekly Sun 02:00 UTC |
| RIS Global Error Watcher | WFvBwCepYu8JzKDs | Error trigger |
| RIS Orchestrator | PEX5vHCexProT2sC | Every 30min + webhooks |

### Standard Sub-Workflow Pattern

Every sub-workflow (except digest) follows:

```
Trigger → Execute Command [continueOnFail] → IF exitCode==0
  TRUE  → Parse Metrics (code) → Success (noOp)
  FALSE → Format Error (code) → Discord Alert [continueOnFail]
```

### Weekly Digest Special Flow

Always sends a Discord message regardless of outcome. Then conditionally sends a
second error-detail alert if either `research-report digest` or `research-stats summary`
returned non-zero exit code.

### Orchestrator Three-Section Layout

- **Health Monitor**: 30-min schedule → research-health + research-stats → parse stdout
  for RED/CRITICAL/FAIL keywords → Discord alert only on detected issues
- **Webhook Dispatcher**: POST /ris-trigger → Switch (7 pipelines) → Execute Workflow
  → respondToWebhook 200 or 400
- **URL Ingest**: POST /ris-ingest → research-acquire → IF exitCode → 200 or 500 + Discord

### Global Error Watcher

New catch-all: error trigger → format context (workflow name, node, execution ID,
error message) → Discord alert. Set as `settings.errorWorkflow` on all 8 other
RIS workflows.

## Deployment Steps

1. Deleted old 8 workflow IDs (kept files as reference, then rewrote from scratch)
2. Created all 9 JSON files with correct node schemas
3. Validated node schemas against live n8n instance using 5 test workflows
4. POSTed all 9 to n8n API (sub-workflows first, orchestrator last with injected IDs)
5. Applied `settings.errorWorkflow: "WFvBwCepYu8JzKDs"` to all 8 non-error-watcher
   workflows via minimal PUT body (name, nodes, connections, settings, staticData, pinData)
6. Tagged all 9 with RIS tag `lsdE5zgirb6IHxH5` via PUT /workflows/{id}/tags
7. Activated all 9 via POST /workflows/{id}/activate
8. Updated `workflows/n8n/workflow_ids.env` with new IDs
9. Updated `workflows/n8n/README.md`

## Technical Issues Resolved

### n8n API: `active` field is read-only
POST body cannot include `active: false`. Removed from all workflow JSONs before
deploying. API returns "request/body/active is read-only" otherwise.

### n8n API: PUT body "must NOT have additional properties"
The PUT `/workflows/{id}` endpoint only accepts exactly these fields:
`name`, `nodes`, `connections`, `settings`, `staticData`, `pinData`.
Any other field (tags, triggerCount, versionId, shared, isArchived, etc.) causes a 400.
Resolved by fetching the workflow GET response and rebuilding a minimal body with only
those 6 fields.

### n8n IF node v2 conditions format
IF node typeVersion 2 requires conditions wrapped in an object with `options`,
`conditions` array, and `combinator` — not the flat array format from v1.
Boolean operator for `hasError` check: `{type: "boolean", operation: "true"}`.

### n8n Switch node v2 fallback
Switch v2 fallback output index is 7 (one after the last rule at index 6) when
7 rules are defined. The fallback connects to the "Respond Unknown Pipeline" node.

### executeWorkflow node parameter format
```json
{
  "workflowId": {
    "__rl": true,
    "value": "WORKFLOW_ID",
    "mode": "id"
  }
}
```

## Codex Review

Tier: Skip (workflow JSON files, no executable business logic). No review required per
CLAUDE.md codex review policy.

## Files Changed

- `workflows/n8n/ris_sub_academic.json` — full rebuild
- `workflows/n8n/ris_sub_reddit.json` — full rebuild
- `workflows/n8n/ris_sub_blog_rss.json` — full rebuild
- `workflows/n8n/ris_sub_youtube.json` — full rebuild
- `workflows/n8n/ris_sub_github.json` — full rebuild
- `workflows/n8n/ris_sub_weekly_digest.json` — full rebuild
- `workflows/n8n/ris_sub_freshness_refresh.json` — full rebuild
- `workflows/n8n/ris_orchestrator.json` — full rebuild
- `workflows/n8n/ris_global_error_watcher.json` — NEW
- `workflows/n8n/workflow_ids.env` — updated with 9 new IDs
- `workflows/n8n/README.md` — updated with full inventory and error handling docs

## Open Items

None. All 9 workflows are deployed, tagged, and active.
