# RIS n8n Pilot -- Smoke Test Runbook

## Purpose

This runbook validates the repo-side n8n pilot assets for the RIS (Research Intelligence
System) n8n pilot (Phase N4). It ensures workflow JSON files are internally consistent,
CLI entrypoints are reachable, and the Docker Compose profile renders correctly -- all
without starting containers or modifying any live system.

Run this runbook before importing workflows into n8n or after making changes to
`infra/n8n/workflows/`.

---

## Prerequisites

- Python 3.11+ (same virtualenv or environment used for `python -m polytool`)
- Docker (optional -- only required for compose profile render check; SKIP if absent)
- Run from the repo root (`D:/Coding Projects/Polymarket/PolyTool` or equivalent)

---

## Quick Start

```bash
python scripts/smoke_ris_n8n.py
```

Expected output: all checks PASS or SKIP (exit code 0).

---

## What the Smoke Script Checks

### 1. Workflow JSON Validation (`infra/n8n/workflows/*.json`)

- All active workflow JSON files parse as valid JSON
- Each file has a `name` field and a `nodes` array
- Each `executeCommand` node's `command` field does NOT start with `=`
  (the `=` prefix is an n8n expression prefix that breaks docker exec invocations)
- Each `executeCommand` node's `command` references `polytool-ris-scheduler`
  (the correct container name as defined in docker-compose.yml)
- Each `python -m polytool <subcommand>` uses a known-good subcommand from the set:
  `{research-health, research-acquire, research-scheduler, research-report, research-stats}`
- No JSON files remain in `workflows/n8n/` (only stub README should be present)

### 2. CLI Entrypoint `--help` Verification

Verifies the following subcommands exit 0 when called with `--help`:

- `python -m polytool research-health --help`
- `python -m polytool research-stats --help`
- `python -m polytool research-scheduler --help`
- `python -m polytool research-acquire --help`
- `python -m polytool research-report --help`

### 3. Docker Compose Profile Render

Runs `docker compose --profile ris-n8n config --quiet` and checks exit 0.
If Docker is not available, this check is reported as SKIP (not FAIL).

---

## Manual Follow-Up Steps

After the smoke script passes, follow these steps to bring up n8n and test workflows:

1. **Start n8n:**
   ```bash
   docker compose --profile ris-n8n up -d n8n
   ```

2. **Import workflows:**
   ```bash
   python infra/n8n/import_workflows.py
   ```
   This imports `infra/n8n/workflows/ris-unified-dev.json` and
   `infra/n8n/workflows/ris-health-webhook.json` via the n8n REST API,
   updates `infra/n8n/workflows/workflow_ids.env`, and activates both workflows.
   Requires `N8N_API_KEY` in `.env` or the shell environment.

3. **Complete owner setup (first run only):**
   Open `http://localhost:5678/setup` in a browser and follow the wizard.
   Set a secure owner password.

4. **Activate desired workflows:**
   In the n8n UI, open each workflow and click "Activate" (toggle switch).
   Recommended starting point: `RIS -- Research Intelligence System` and
   `RIS -- Health Webhook`.

5. **Stop APScheduler to avoid double-scheduling:**
   The `ris-scheduler` container runs by default in `docker compose up`.
   If you want n8n to be the sole scheduler, stop it:
   ```bash
   docker compose stop ris-scheduler
   ```
   Running both simultaneously causes double-scheduling (wasteful, not harmful).
   See `docs/adr/0013-ris-n8n-pilot-scoped.md` for scheduler selection policy.

6. **Test health webhook:**
   ```bash
   curl http://localhost:5678/webhook/ris-health
   ```
   Expected: HTTP 200 JSON response from `RIS -- Health Webhook`.

7. **Test ingest webhook with curl:**
   ```bash
   curl -X POST http://localhost:5678/webhook/ris-ingest \
     -H "Content-Type: application/json" \
     -d '{"url": "https://arxiv.org/abs/2301.00001", "source_family": "academic"}'
   ```
   Valid `source_family` values: `academic`, `github`, `blog`, `news`, `book`, `reddit`, `youtube`.

   **Security:** The webhook URL contains an n8n-generated auth token. Treat it as a secret.
   Do not log or share the full webhook URL in plain text.

---

## Troubleshooting

### Docker not running
```
SKIP: docker command not found or timed out
```
Start Docker Desktop and retry, or ignore the SKIP if you only need workflow validation.

### Compose profile not found
```
FAIL: docker compose config failed: ...
```
Ensure you are running from the repo root and `docker-compose.yml` is present.
Run `docker compose --profile ris-n8n config` manually to see the full error.

### n8n container not started
```
curl: (7) Failed to connect to localhost port 5678
```
The smoke script does NOT start n8n. Start it with:
```bash
docker compose --profile ris-n8n up -d n8n
```

### Double-scheduling symptoms
Both APScheduler (`ris-scheduler`) and n8n are running, so each job fires twice.
Stop one:
```bash
docker compose stop ris-scheduler   # if using n8n as primary
```

### Workflow has wrong container name
```
FAIL: correct-container:ris-unified-dev.json:<node>: Expected 'polytool-ris-scheduler' in command
```
Edit the workflow JSON in `infra/n8n/workflows/` to use `polytool-ris-scheduler`.

### CLI entrypoint fails --help
```
FAIL: cli-help:research-acquire: exit 1: ...
```
Activate the correct virtual environment and ensure polytool is installed:
```bash
pip install -e ".[all]"
python -m polytool --help
```

---

## Related Documentation

- `docs/adr/0013-ris-n8n-pilot-scoped.md` -- ADR for n8n pilot scope and scheduler selection
- `docs/runbooks/RIS_OPERATOR_GUIDE.md` -- Full RIS operator guide
- `infra/n8n/README.md` -- n8n service setup and import instructions
- `docs/runbooks/RIS_N8N_OPERATOR_SOP.md` -- Compact operator SOP cheat sheet
- `docs/dev_logs/2026-04-06_ris_n8n_phase_n4_repo_hardening.md` -- Audit trail for Phase N4 changes
