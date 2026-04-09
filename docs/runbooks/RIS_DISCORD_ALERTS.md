# RIS Discord Alert Style Guide and Verification Procedure

**Last verified:** 2026-04-09 (polish pass — embed format v2)
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

Embed fields: Docs, Runs, New, Cached, Errors (all inline, only shown when non-null). Top Families and Actionable Checks as full-width fields when present.

```
Title:       RIS Health: RED
Description: pipeline_error detected   (or "N checks need attention" for multiple)
Fields:      Docs=312 | Runs=5 | New=0 | Cached=5 | Errors=2
             Top Families: academic=280, reddit=32
             Actionable Checks:
               [RED] pipeline_error: Academic ingest failed with exit code 1
               [YLW] no_new_docs_48h: No new documents accepted in 48 hours
Footer:      RIS | health
```

Severity markers in Actionable Checks use `[RED]` / `[YLW]`. Stat fields are omitted entirely when the stats command fails (no `n/a` shown). Fires only when RED or actionable YELLOW. GREEN health never sends.

### Pipeline Error

Embed with conditional fields: Error Output (stderr) and Last Output (stdout tail) are omitted when empty — no `none` placeholder.

```
Title:       Pipeline Error: Academic
Description: Exit 1
Fields:      Error Output: [stderr text, up to 300 chars]
             Last Output: [last 200 chars of stdout, if non-empty]
Footer:      RIS | academic
```

Section display names: `Academic`, `Reddit`, `Blog`, `YouTube`, `GitHub`, `Freshness` (title-cased). Footer uses lower-cased display name.

### Daily Summary

```
Title:       RIS Daily Summary
Description: Health: GREEN
Fields:      Docs=1240 | Runs=48 | New=12 | Ingest Errors=0
             Top Families: academic=900, reddit=340
             Prechecks: GO=8, CAUTION=2, STOP=0
Footer:      RIS | daily-summary
```

Description simplified to health status only (doc/run counts moved to fields). Schedule trigger is disabled by default in the committed workflow JSON.

### Ingest Failure

```
Title:       Ingest Failed: Blog
Description: Family: Blog                          (when no exit code)
             Exit 1 | Family: Blog                 (when exit code present)
Fields:      Source: http://127.0.0.1:9/unreachable  (inline; long URLs truncated to domain+...+tail)
             Detail: Unknown error
Footer:      RIS | ingest
```

Exit code shown only when present (non-null). `n/a` never appears. Source field is inline; long URLs truncated to `domain/...last20chars`. Fires when a `/webhook/ris-ingest` POST results in a failure (bad URL, network error, non-zero exit).

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

## Footer Pattern Reference

All footers were shortened in the 2026-04-09 polish pass — `ris-unified-dev` was dropped from every footer:

| Alert type | Footer text |
|------------|-------------|
| Health alert | `RIS \| health` |
| Pipeline error | `RIS \| {section}` (e.g. `RIS \| academic`) |
| Ingest failure | `RIS \| ingest` |
| Daily summary | `RIS \| daily-summary` |
| Summary error | `RIS \| daily-summary` |

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
