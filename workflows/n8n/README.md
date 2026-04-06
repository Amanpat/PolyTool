# RIS n8n Workflow System

Research Intelligence System (RIS) automation via n8n. Part of the scoped RIS n8n pilot
defined in `docs/adr/0013-ris-n8n-pilot-scoped.md`.

## Workflow Files

| File | n8n ID | Purpose |
|------|--------|---------|
| `ris_orchestrator.json` | `pvoP1evtPWTp5LPh` | 3-path orchestrator (health, trigger, ingest) |
| `ris_sub_academic.json` | `wGZFmbBk5TuKeiu4` | Daily academic ingest at 03:00 UTC |
| `ris_sub_reddit.json` | `66DODhOnrEdqc0Tk` | Daily reddit ingest at 05:00 UTC |
| `ris_sub_blog_rss.json` | `xhv5Dnru2nW7TchB` | Daily blog RSS ingest at 06:00 UTC |
| `ris_sub_youtube.json` | `e6P3lkcJdwlRPgfj` | Weekly youtube ingest Mondays 04:00 UTC |
| `ris_sub_github.json` | `ZJFoRcDFNdgzKP7m` | Weekly github ingest Wednesdays 04:00 UTC |
| `ris_sub_weekly_digest.json` | `Nes9RKXadMsYcHE8` | Weekly digest + Discord report Sundays 08:00 UTC |
| `ris_sub_freshness_refresh.json` | `SrEdvxt5sRFRQYrV` | Weekly freshness refresh Sundays 02:00 UTC |

Workflow IDs are also stored in `workflow_ids.env` for scripting.

## Architecture

### Path A: Health Monitor (Autonomous)

```
Every 30 Minutes -> Run research-health -> Run research-stats -> Parse Output -> IF Alert -> Discord Alert
```

Runs every 30 minutes. Sends Discord alert (via `DISCORD_WEBHOOK_URL` env var) if health
output contains `RED`, `CRITICAL`, `FAIL`, `pipeline_failed`, or `ERROR`.

### Path B: Manual Pipeline Trigger

```
POST /webhook/ris-trigger {"pipeline": "<name>"} -> Switch -> Exec Sub-Workflow
```

Accepts `pipeline` values: `academic`, `reddit`, `blog`, `youtube`, `github`, `digest`, `freshness`.
Routes to the corresponding sub-workflow. Falls through to n8n fallback if unknown pipeline.

Example:
```bash
curl -X POST http://localhost:5678/webhook/ris-trigger \
  -H "Content-Type: application/json" \
  -d '{"pipeline": "academic"}'
```

### Path C: URL Ingest

```
POST /webhook/ris-ingest {"url": "...", "source_family": "..."} -> research-acquire
```

Runs `research-acquire --url URL --source-family FAMILY --no-eval` in the ris-scheduler container.
Returns stdout/exit_code/url_ingested/source_family.

Example:
```bash
curl -X POST http://localhost:5678/webhook/ris-ingest \
  -H "Content-Type: application/json" \
  -d '{"url": "https://arxiv.org/abs/2301.00001", "source_family": "academic"}'
```

## Environment Variables Required

| Variable | Where | Purpose |
|----------|-------|---------|
| `DISCORD_WEBHOOK_URL` | n8n container env | Discord alerts for Path A and weekly digest |
| `NODES_EXCLUDE` | n8n container env | Must be `[]` to enable executeCommand node |

Both are set in `docker-compose.yml` under the `n8n` service.

## n8n 2.x Compatibility Notes

Several n8n 2.x behaviors required fixes during initial deployment:

1. **executeCommand disabled by default**: n8n 2.x excludes `n8n-nodes-base.executeCommand`
   in its default node exclusion list. Fixed by setting `NODES_EXCLUDE=[]` in docker-compose.yml.
   Container must be recreated (not just restarted) with `docker compose up -d n8n` for this to take effect.

2. **6-field cron format**: n8n 2.x ScheduleTrigger requires 6-field cron format
   `[Second] [Minute] [Hour] [Day of Month] [Month] [Day of Week]`, e.g., `0 0 4 * * 1` (not `0 4 * * 1`).
   The parameter structure is `rule.interval[{field: "cronExpression", expression: "0 0 4 * * 1"}]`.

3. **Switch node V2 for >4 outputs**: Switch V1 (`typeVersion: 1`) hardcodes 4 outputs.
   Switch V2 (`typeVersion: 2`) supports dynamic outputs via `outputKey` per rule and
   `"mode": "rules"` in parameters.

4. **Expression prefix**: executeCommand fields that interpolate `{{ }}` variables require
   the `=` prefix: `"=docker exec ... {{ $json.body.url }}"`.

5. **PUT API field restrictions**: `PUT /api/v1/workflows/{id}` rejects `notes`, `meta`,
   `tags`, `triggerCount`, and `active` as read-only or disallowed fields. Strip them before PUT.
   Tags are managed via `PUT /api/v1/workflows/{id}/tags`.

## Mutual Exclusion

These n8n workflows MUST NOT be activated while the APScheduler `polytool-ris-scheduler`
container is running its own schedules. The sub-workflows call the same jobs via
`research-scheduler run-job <name>`, which would cause double-execution.

The n8n pilot is activated via `--profile ris-n8n`. Default deployments use APScheduler only.

## Exec Container

All `executeCommand` nodes target `polytool-ris-scheduler`. This container must be running
for workflows to execute successfully. Verify:

```bash
docker ps | grep polytool-ris-scheduler
```

## Redeployment

To redeploy all workflows after JSON changes:

```bash
# Load workflow IDs
source workflows/n8n/workflow_ids.env

# PUT each workflow (strip active/notes/meta/tags/triggerCount before PUT)
# Then re-activate each workflow:
# POST /api/v1/workflows/{id}/activate

# Assign RIS tag (ID: lsdE5zgirb6IHxH5):
# PUT /api/v1/workflows/{id}/tags [{"id": "lsdE5zgirb6IHxH5"}]
```
