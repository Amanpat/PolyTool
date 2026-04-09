# RIS + n8n Operator SOP Cheat Sheet

**Scope:** Scoped to RIS ingestion only per ADR 0013. NOT Phase 3 automation.
**Last verified:** 2026-04-09

---

## Startup

```bash
# 1. Start default stack (APScheduler remains active)
docker compose up -d

# 2. Start n8n sidecar
docker compose --profile ris-n8n up -d n8n

# 3. Verify n8n is up (expect {"status":"ok"})
curl -s http://localhost:5678/healthz
```

- APScheduler and n8n run side-by-side by default.
- Only stop APScheduler if you enable n8n schedule triggers and want n8n to own recurring runs:
  ```bash
  docker compose stop ris-scheduler
  ```
- First-time setup: complete owner wizard at `http://localhost:5678/setup` before using the UI.

---

## Import / Re-import Workflows

```bash
python infra/n8n/import_workflows.py
```

- Imports `ris-unified-dev.json` + `ris-health-webhook.json` via n8n REST API.
- Updates `infra/n8n/workflows/workflow_ids.env` and activates both workflows.
- Requires `N8N_API_KEY` in `.env`.

---

## Health Check

```bash
# Webhook path
curl http://localhost:5678/webhook/ris-health

# CLI paths
python -m polytool research-health
python -m polytool research-stats summary
```

---

## Ingest Test

```bash
curl -X POST "http://localhost:5678/webhook/ris-ingest" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://arxiv.org/abs/2106.01345","source_family":"academic"}'
```

Valid `source_family` values: `academic`, `github`, `blog`, `news`, `book`, `reddit`, `youtube`

---

## Review Queue

```bash
python -m polytool research-review list
python -m polytool research-review accept <doc_id>
python -m polytool research-review reject <doc_id>
python -m polytool research-review defer <doc_id>
```

---

## Monitoring Commands

| Command | Purpose |
|---------|---------|
| `python -m polytool research-health` | Pipeline health snapshot |
| `python -m polytool research-stats summary` | Ingestion metrics |
| `python -m polytool research-scheduler status` | Scheduler job status |
| `http://localhost:5678` | n8n UI (workflow runs, logs, errors) |

---

## Discord Alert Troubleshooting

- Discord alerting is **NOT** wired to the RIS alert sink by default. RIS uses `LogSink`.
- To use Discord: configure `WebhookSink` manually and set `DISCORD_WEBHOOK_URL` in `.env`.
- n8n workflow failure alerts go through n8n's built-in error handling (`settings.errorWorkflow`), not the polytool Discord module.

---

## Common Mistakes

- **Double-scheduling:** Running both APScheduler and n8n schedule triggers causes each RIS job to fire twice. Stop one before enabling the other.
- **Missing N8N_API_KEY:** `import_workflows.py` fails silently or with auth error. Check `.env`.
- **Python in n8n container:** `python -m polytool` inside n8n fails (no Python). All Execute Command nodes must use `docker exec polytool-ris-scheduler python -m polytool ...`.
- **Invalid source_family:** Webhook ingest returns error. Valid values: `academic`, `github`, `blog`, `news`, `book`, `reddit`, `youtube`.
- **n8n not started:** `curl: (7) Failed to connect to localhost port 5678` -- profile not activated. Run `docker compose --profile ris-n8n up -d n8n`.
- **First-time n8n:** Must complete owner setup at `http://localhost:5678/setup` before workflows can be activated.

---

## Related Docs

| Doc | Purpose |
|-----|---------|
| [`docs/RIS_OPERATOR_GUIDE.md`](../RIS_OPERATOR_GUIDE.md) | Full RIS operator guide (890 lines, all details) |
| [`infra/n8n/README.md`](../../infra/n8n/README.md) | n8n infrastructure, image details, MCP setup |
| [`docs/runbooks/RIS_N8N_SMOKE_TEST.md`](RIS_N8N_SMOKE_TEST.md) | Pre-import repo validation runbook |
| [`docs/adr/0013-ris-n8n-pilot-scoped.md`](../adr/0013-ris-n8n-pilot-scoped.md) | ADR: scope boundary decision |
