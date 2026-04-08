# 2026-04-08 n8n Runtime Debug and Smoke

## Files changed and why

| File | Why |
|------|-----|
| `docker-compose.yml` | Added an n8n Docker healthcheck so the container can reach a real `healthy` state. |
| `packages/polymarket/rag/__init__.py` | Replaced eager imports with lazy exports so `research-acquire` no longer fails on optional RAG deps during basic ingestion paths. |
| `infra/n8n/import_workflows.py` | Added a cross-platform importer that uses the n8n REST API and updates `workflows/n8n/workflow_ids.env`. |
| `infra/n8n/import-workflows.sh` | Converted the shell helper into a thin wrapper around the new Python importer. |
| `workflows/n8n/ris-unified-dev.json` | Disabled all schedule triggers by default, added a manual health trigger, and kept the production ingest webhook active/safe alongside APScheduler. |
| `workflows/n8n/ris-health-webhook.json` | Added a dedicated health-check webhook workflow for repeatable operator smoke and public-HTTP health execution. |
| `workflows/n8n/README.md` | Updated workflow docs to reflect the new import helper, disabled-by-default schedules, and health webhook. |
| `infra/n8n/README.md` | Updated runtime docs to reflect the API importer and the health support workflow. |
| `workflows/n8n/workflow_ids.env` | Refreshed the deployed workflow IDs after import. |

## Commands run and output

### Runtime inspection

```powershell
docker ps --format "table {{.Names}}`t{{.Status}}`t{{.Ports}}"
```

Result:

```text
polytool-ris-scheduler   Up ...
polytool-n8n            Up ...
polytool-clickhouse     Up ... (healthy)
```

```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:5678/healthz
```

Result:

```json
{"status":"ok"}
```

### Failures found during debugging

```powershell
bash infra/n8n/import-workflows.sh
```

Result:

```text
/bin/bash not found on this Windows host
```

```powershell
docker cp workflows\n8n\ris-unified-dev.json polytool-n8n:/tmp/ris-unified-dev.json
docker exec polytool-n8n n8n import:workflow --input=/tmp/ris-unified-dev.json
```

Result:

```text
SQLITE_CONSTRAINT: NOT NULL constraint failed: workflow_entity.id
```

```powershell
docker exec polytool-ris-scheduler python -m polytool research-acquire --url https://github.com/polymarket/py-clob-client --source-family github --no-eval --json
```

Initial result before the Python-side fix:

```text
ModuleNotFoundError: No module named 'numpy'
```

After switching workflow commands to an env-driven n8n expression, the live webhook failed with:

```text
access to env vars denied
```

That change was reverted. Commands now target `polytool-ris-scheduler` directly again.

### Rebuild and restart

```powershell
docker compose build ris-scheduler
docker compose up -d ris-scheduler
docker compose --profile ris-n8n build n8n
docker compose --profile ris-n8n up -d n8n
```

Result:

```text
polytool-ris-scheduler  Built / Started
polytool-n8n            Built / Started
```

### Health state

```powershell
docker inspect --format='{{json .State.Health}}' polytool-n8n
```

Result:

```json
{"Status":"healthy","FailingStreak":0,...}
```

### Canonical import

```powershell
python infra\n8n\import_workflows.py
```

Result:

```text
Importing canonical workflows into http://localhost:5678 ...
  ris-unified-dev.json: B34eBaBPIvLb8SYj (updated + already-active)
  ris-health-webhook.json: MJo9jcBCfxmyMwcc (created + activated)
Import complete.
```

### Direct ingest bridge verification

```powershell
docker exec polytool-ris-scheduler python -m polytool research-acquire --url https://github.com/openai/openai-python --source-family github --no-eval --json
```

Result:

```json
{
  "source_url": "https://github.com/openai/openai-python",
  "source_family": "github",
  "doc_id": "5d50cb42ea47df84793fa2c0f466553e55077048220029066d54f8c0e9ccd7c6",
  "chunk_count": 10,
  "rejected": false
}
```

### Health workflow smoke

```powershell
Invoke-RestMethod -Uri 'http://localhost:5678/webhook/ris-health' -Method GET
```

Result:

```json
{
  "command": "research-health",
  "status": "alert",
  "healthExitCode": 0,
  "statsExitCode": 0,
  "timestamp": "2026-04-08T18:32:17.621Z"
}
```

Notes:
- The workflow execution succeeded.
- The returned status is `alert` because the actual RIS health report is currently RED due `reddit_polymarket` pipeline failure.
- This is live operator data, not an n8n runtime failure.

### Ingest/webhook smoke

```powershell
Invoke-RestMethod -ContentType 'application/json' `
  -Uri 'http://localhost:5678/webhook/ris-ingest' `
  -Method POST `
  -Body '{"url":"https://github.com/openai/openai-python","source_family":"github"}'
```

Result:

```json
{
  "status": "ingested",
  "url": "https://github.com/openai/openai-python",
  "source_family": "github",
  "output": "Acquired: The official Python library for the OpenAI API | family=github | source_id=7870f4db5f1e1f1d | doc_id=5d50cb42ea47... | chunks=10 | dedup=cached",
  "timestamp": "2026-04-08T18:32:18.284Z"
}
```

## Test and smoke results

| Check | Result |
|------|--------|
| `docker compose --profile ris-n8n build n8n` | PASS |
| `docker compose --profile ris-n8n up -d n8n` | PASS |
| n8n container reaches Docker `healthy` | PASS |
| Canonical workflow import | PASS |
| Health workflow execution | PASS via `RIS -- Health Webhook` (`/webhook/ris-health`) |
| Production ingest webhook | PASS via `/webhook/ris-ingest` |
| Direct `research-acquire` bridge execution | PASS |

## Exact operator commands

### Start the stack

```powershell
docker compose up -d clickhouse ris-scheduler
docker compose --profile ris-n8n up -d n8n
```

### Import workflows

```powershell
python infra\n8n\import_workflows.py
```

### Verify health

```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:5678/healthz
Invoke-RestMethod -Uri 'http://localhost:5678/webhook/ris-health' -Method GET
```

### Hit the ingest path

```powershell
Invoke-RestMethod -ContentType 'application/json' `
  -Uri 'http://localhost:5678/webhook/ris-ingest' `
  -Method POST `
  -Body '{"url":"https://github.com/openai/openai-python","source_family":"github"}'
```

## Remaining blockers ranked by severity

1. Medium: n8n schedule takeover is still not the default-ready path.
   The unified workflow now ships with schedule triggers disabled on purpose so activation is safe while APScheduler remains the default scheduler. If an operator wants n8n to own scheduling, they must explicitly enable the relevant schedule nodes in the UI and review scheduler mutual-exclusion policy first.

2. Medium: the exec bridge still targets `polytool-ris-scheduler`.
   Manual runs and webhooks are usable today because that container stays up and serves as the Docker exec target. If an operator stops `ris-scheduler`, n8n Execute Command nodes will fail until a dedicated idle exec-bridge container is introduced.

3. Low: n8n logs a Python task-runner warning on startup.
   The current workflows use JS code nodes and Execute Command nodes; the warning did not block health or ingest smoke.

4. Low: `/webhook/ris-health` currently returns `status: "alert"`.
   This reflects a real RIS health condition (`reddit_polymarket` pipeline failure), not an n8n runtime problem.

## Recommendation

**Safe to start using now: yes**, for immediate operator/manual and webhook-driven RIS testing.

Why:
- The n8n container is healthy.
- Canonical import is repeatable from this Windows repo.
- Health and ingest both execute end to end through live n8n webhooks.
- Schedule triggers are disabled by default, which avoids accidental double-scheduling while APScheduler remains the default scheduler.

Current boundary:
- Use n8n now for operator-triggered health checks and URL ingestion.
- Do not treat this as a complete n8n scheduler handoff yet without an explicit exec-bridge/scheduler policy follow-up.
