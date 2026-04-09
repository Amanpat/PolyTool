# RIS Discord Alert Style Guide and Verification Procedure

**Last verified:** 2026-04-09
**Purpose:** Single reference for RIS Discord alert formats, severity meaning, and exact steps to verify each alert path after a workflow or webhook change.

---

## Prerequisites

- `DISCORD_WEBHOOK_URL` set in repo-root `.env`
- n8n running: `docker compose --profile ris-n8n up -d n8n`
- Workflows imported: `python infra/n8n/import_workflows.py`

For full setup, see [`docs/runbooks/RIS_N8N_OPERATOR_SOP.md`](RIS_N8N_OPERATOR_SOP.md).

---

## Alert Types

| Type | Trigger | Frequency | Format Summary |
|------|---------|-----------|----------------|
| Health alert | Schedule (every 30 min) | RED or actionable YELLOW only | Single-line header + per-check bullet lines |
| Pipeline error | Exit code != 0 from Execute Command node | Per-section run (academic/reddit/blog/youtube/github/freshness) | Bold title + exit code + stderr/stdout blocks |
| Daily summary | Schedule trigger (disabled by default) | 08:00 UTC | Single-line header + actionable + families + prechecks |
| Ingest failure | Webhook POST failure (`/webhook/ris-ingest`) | On-demand, per failed request | Single-line header + url + error |

---

## Message Format Reference

These are the intended formats. If a workflow change produces messages that do not match, the workflow change has a formatting regression.

### Health Alert

```
RIS health RED | runs=5 | docs=312 | claims=48 | new=0 | cached=5 | ingest_errors=2
- RED pipeline_error: Academic ingest failed with exit code 1
- YELLOW no_new_docs_48h: No new documents accepted in 48 hours
families: academic, reddit
```

Fires only when status is RED or there are actionable YELLOW checks. GREEN health never sends.

### Pipeline Error

Format: bold title, exit code, then `**stderr:**` and `**stdout (last 500):**` blocks in triple-backtick fences.

```
**RIS Pipeline Error: academic**

Exit code: 1

**stderr:**
[fenced block with stderr text]

**stdout (last 500):**
[fenced block with last 500 chars of stdout]
```

Section names: `academic`, `reddit`, `blog`, `youtube`, `github`, `freshness`

### Daily Summary

```
RIS daily summary | health=GREEN | runs=48 | docs=1240 | claims=180 | new=12 | cached=36 | ingest_errors=0
actionable: none
families: academic, reddit, github
prechecks: GO=8, CAUTION=2, STOP=0
```

Schedule trigger is disabled by default in the committed workflow JSON.

### Ingest Failure

```
RIS ingest failed | family=blog | exit=n/a
url: http://127.0.0.1:9/unreachable
error: Unknown error
```

Fires when a `/webhook/ris-ingest` POST results in a failure (bad URL, network error, non-zero exit).

---

## Severity Meaning

| Level | Meaning | Sent to Discord? |
|-------|---------|-----------------|
| RED | Operational failure requiring action (pipeline down, all providers failing) | Yes |
| YELLOW | Degraded state, monitor closely (queue growing, accept rate drifting) | Only if actionable |
| GREEN | Healthy | No — health alerts are suppressed when all checks are GREEN |

Pipeline errors and ingest failures have no severity level — they always fire on failure.

---

## Verification Procedure

Run these steps after any workflow or webhook URL change to confirm all alert paths work.

### 1. Ingest failure test (easiest — run this first)

```bash
curl -X POST "http://localhost:5678/webhook/ris-ingest" \
  -H "Content-Type: application/json" \
  -d '{"url":"http://127.0.0.1:9/discord-format-test","source_family":"blog"}'
```

- Hits an unreachable address, forcing the failure path.
- Check Discord for a message matching the **Ingest Failure** format above.
- In n8n UI: verify `Operator: Send Webhook` ran with no `json.error`.

### 2. Health alert test

- Open n8n UI at `http://localhost:5678`
- Find `RIS — Research Intelligence System` workflow
- Click `Health: Schedule` trigger, then "Test workflow"
- GREEN health skips the alert — this is correct, not a bug
- To force an alert: stop ris-scheduler so `no_new_docs_48h` fires YELLOW:
  ```bash
  docker compose stop ris-scheduler
  # Trigger health check, check Discord, then restart
  docker compose start ris-scheduler
  ```

### 3. Daily summary test

- In n8n UI, click `Summary: Schedule` trigger, then "Test workflow"
- Check Discord for a message matching the **Daily Summary** format above

### 4. Pipeline error test

- In n8n UI, click any section trigger (e.g. `Academic: Manual`), then "Test workflow"
- If the CLI command fails (no network, bad config), check Discord for the **Pipeline Error** format

---

## After DISCORD_WEBHOOK_URL Change

The URL is injected at import time, not read at runtime. Re-import after any URL change:

```bash
python infra/n8n/import_workflows.py
# Verify: CLI should print "DISCORD_WEBHOOK_URL: configured (.env)"
```

Then re-run the ingest failure test above to confirm the new URL is live.

---

## Common Failures

- **Alert not sent:** `__RIS_OPERATOR_WEBHOOK_URL__` still in live workflow — re-import.
- **`EAI_AGAIN` in Send Webhook node:** Transient container DNS failure. Retry once; confirmed intermittent in 2026-04-09 debug session.
- **Health alert never fires:** All checks GREEN — correct behavior, not a bug.
- **Message truncated:** Discord 2000-char limit. Workflow pre-truncates stderr/stdout to 500 chars.
- **`notifyEnabled = false`:** Webhook URL failed the `http(s)://` prefix check — re-import.
