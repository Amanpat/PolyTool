# n8n v2 Workflow Templates

**Date:** 2026-04-05
**Quick task:** quick-260405-l8q
**Branch:** feat/ws-clob-feed

> **SUPERSEDED:** The `workflows/n8n/` directory described below was deleted on 2026-04-06
> (quick-260406-mno). The canonical workflow location is `infra/n8n/workflows/`.
> See `docs/dev_logs/2026-04-06_ris_n8n_phase_n4_repo_hardening.md`.

## What

8 enhanced RIS pipeline n8n workflow JSON files, importable at localhost:5678.
Files live in `workflows/n8n/` (new canonical location for importable workflows).

## Why

Upgrade from v1 pilot templates in `infra/n8n/workflows/` which had no error handling,
no Discord alerting, and used a deprecated container name (`polytool-ris-scheduler`).
The v2 templates add production-level observability: Discord failure alerts on all
ingestion jobs, health RED detection, and a webhook-with-response for manual acquisitions.

## Key Decisions

- **Container name: `polytool-polytool-1`** (main app container, not the old ris-scheduler).
  The ris-scheduler container was part of the pilot; the main polytool container runs all
  CLI commands in the current stack.
- **`active: true` by default** so workflows become operational immediately after import,
  without a manual toggle step (operator can deactivate before saving if not ready).
- **No `tags` array** — empty tags arrays caused import compatibility issues in quick-260404-t5l
  testing. Removed entirely from all v2 templates.
- **`DISCORD_WEBHOOK_URL` via n8n env expression** (`={{ $env.DISCORD_WEBHOOK_URL }}`).
  Not hardcoded; operator sets it once in n8n Settings > Variables.
- **IF node branches**: true branch = failure condition (exitCode != 0) -> Discord alert.
  False branch left empty = silent success. This follows n8n's "true = condition met" logic.
- **Health monitor**: parses stdout for "RED" string (case-insensitive) in a Code node.
  Also triggers on exitCode != 0. Silent on all-GREEN output. Truncates output to 1500
  chars to avoid Discord embed length limit (2000 chars per embed field).
- **Weekly digest**: chains two Execute Command nodes sequentially before combining output
  in a Code node. Both research-report and research-stats must complete before sending.
- **Manual ingest**: uses `responseMode: "responseNode"` on the Webhook node so the
  Respond to Webhook node controls the HTTP response. Returns JSON with success/result/exit_code.

## Files Created

- `workflows/n8n/ris-academic-ingestion.json` — Schedule (12h) + Discord on failure
- `workflows/n8n/ris-reddit-ingestion.json` — Schedule (6h) + Discord on failure
- `workflows/n8n/ris-blog-ingestion.json` — Schedule (4h) + Discord on failure
- `workflows/n8n/ris-youtube-ingestion.json` — Schedule (Mon 04:00 cron) + Discord on failure
- `workflows/n8n/ris-github-ingestion.json` — Schedule (Wed 04:00 cron) + Discord on failure
- `workflows/n8n/ris-health-monitor.json` — Schedule (30min), Code node RED parse, Discord on RED
- `workflows/n8n/ris-weekly-digest.json` — Schedule (Sun 08:00), 2x Execute + combine, always Discord
- `workflows/n8n/ris-manual-ingest.json` — Webhook POST + Execute + respondToWebhook
- `workflows/n8n/README.md` — Import instructions, workflow matrix, env var setup
- `docs/dev_logs/2026-04-05_n8n-workflows.md` — This file

## What Changed vs v1

| Aspect | v1 (infra/n8n/workflows/) | v2 (workflows/n8n/) |
|--------|--------------------------|---------------------|
| Container | polytool-ris-scheduler | polytool-polytool-1 |
| active | false | true |
| Error handling | None | IF node + Discord HTTP Request |
| Health parsing | Basic schedule + exec | Code node with RED detection |
| Manual ingest | Execute only | Webhook + Execute + Respond |
| Weekly digest | Single exec | 2 exec + Code combine + Discord |
| tags field | Present (empty array) | Absent (import compat) |
| typeVersion for IF | N/A | 2 |
| HTTP Request typeVersion | N/A | 4.2 |

## Testing

- JSON validity: verified via `python -c "import json; json.load(open(...))"` for all 8 files
- Node type presence: automated check confirmed all required node types present per workflow
- Container name: automated check confirmed `polytool-polytool-1` in all executeCommand nodes
- Tags absence: automated check confirmed no `tags` key in any workflow
- Runtime import: **not runtime-verified** — requires live n8n at localhost:5678
- Discord delivery: **not verified** — requires DISCORD_WEBHOOK_URL configured in n8n

## Open Items

- Runtime import into n8n pending (operator step: import via UI)
- `DISCORD_WEBHOOK_URL` must be configured in n8n Settings > Variables before alert nodes fire
- If APScheduler (ris-scheduler container) is running, deactivate ingestion cron triggers to
  avoid double-scheduling. See README.md for mutual exclusion note.

## Codex Review

- Tier: Skip (workflow JSON config, no execution logic changes)
