# 2026-04-09 Discord Alert Layout Refinement

## Summary

Converted all 9 Discord notification format nodes in the unified RIS n8n workflow
from plain-text `{ content: "..." }` payloads to structured Discord embed format.
The sender node was also updated to post `{ embeds: $json.embeds }` instead of
`{ content: $json.content }`.

## Files changed

- `infra/n8n/workflows/ris-unified-dev.json`
  - 9 format nodes: jsCode replaced with embed-producing logic
  - 1 sender node (Operator: Send Webhook): jsonBody expression updated
- `docs/dev_logs/2026-04-09_discord_alert_layout_refinement.md`
  - This file

No changes to `infra/n8n/import_workflows.py` — it already handles placeholder
injection and the embed payload structure is purely in the workflow JSON.

## Before / After payload shape

### Before (all 9 format nodes)

```json
{ "content": "RIS ingest failed | family=blog | exit=n/a\nurl: ...\nerror: Unknown error" }
```

Sender jsonBody expression:
```
={{ JSON.stringify({ content: $json.content }) }}
```

### After

Each format node now returns:

```json
{
  "embeds": [{
    "title": "RIS Ingest Failed",
    "description": "Family: blog | Exit: n/a",
    "color": 16711680,
    "fields": [
      { "name": "URL", "value": "http://127.0.0.1:9/embed-test", "inline": false },
      { "name": "Error", "value": "Unknown error", "inline": false }
    ],
    "footer": { "text": "RIS | ris-unified-dev | ingest" },
    "timestamp": "2026-04-09T20:19:12.748Z"
  }],
  "webhookUrl": "https://discord.com/api/webhooks/...",
  "notifyEnabled": true
}
```

Sender jsonBody expression:
```
={{ JSON.stringify({ embeds: $json.embeds }) }}
```

## Design choices

### Color coding

| Color | Decimal | Hex | Use case |
|-------|---------|-----|----------|
| RED | 16711680 | 0xFF0000 | Pipeline errors, ingest failures, RED health, stats error |
| YELLOW | 16744448 | 0xFFA500 | Warnings (YELLOW health), summary with actionable checks, summary command error |
| GREEN | 3066993 | 0x2ECC71 | Healthy daily summary (no actionable checks) |
| BLUE | 3447003 | 0x3498DB | (reserved, not used in current nodes) |

### Field layout

- **Inline fields**: numeric metrics (Runs, Docs, New, Cached, Errors) — renders as a compact grid
- **Non-inline fields**: text content (stderr, stdout tail, Top Families, Prechecks, Actionable Checks) — full-width

### Footer

- Standard nodes: `RIS | ris-unified-dev`
- Section pipeline errors: `RIS | ris-unified-dev | {section_name}` (e.g., `academic_ingest`)
- Ingest failures: `RIS | ris-unified-dev | ingest`
- Summary nodes: `RIS | ris-unified-dev | daily-summary`

### Truncation

- stderr: capped at 300 chars
- stdout tail: last 200 chars
- URL in ingest fail: 200 chars
- Error text in ingest fail: 300 chars
- Individual field values: kept under 300 chars (well within Discord's 1024-char limit)
- No markdown code blocks in fields (render poorly on mobile)

### Ingest: Format Fail special handling

This node also feeds the `Ingest: Respond 500` node downstream, which echoes the
JSON body back as the HTTP response. The statusPayload fields (status, url,
source_family, error, exitCode, timestamp) are preserved via `...statusPayload`
spread alongside the new `embeds` array.

## Commands run and output

### 1. Run the patch script

Script written to `infra/n8n/_patch_embeds.py` (deleted after use):

```
python infra/n8n/_patch_embeds.py
```

Output:
```
Patched nodes:
  format node: s1-format-alert (Health: Format Alert)
  format node: s2-format-err (Academic: Format Error)
  format node: s3-format-err (Reddit: Format Error)
  format node: s4-format-err (Blog: Format Error)
  format node: s5-format-err (YouTube: Format Error)
  format node: s6-format-err (GitHub: Format Error)
  format node: s7-format-err (Freshness: Format Error)
  format node: s8-parse (Summary: Format Message)
  format node: s8-format-err (Summary: Format Error)
  format node: s9-fmt-err (Ingest: Format Fail)
  sender node: operator-notify-send (Operator: Send Webhook)

Wrote infra/n8n/workflows/ris-unified-dev.json
```

### 2. Validate JSON

```
python -m json.tool infra/n8n/workflows/ris-unified-dev.json > /dev/null && echo "JSON valid"
```

Output: `JSON valid`

### 3. Re-import workflow

```
python infra/n8n/import_workflows.py
```

Output:
```
Importing canonical workflows into http://localhost:5678 ...
  DISCORD_WEBHOOK_URL: configured (.env)
  ris-unified-dev.json: B34eBaBPIvLb8SYj (updated + already-active)
  ris-health-webhook.json: MJo9jcBCfxmyMwcc (updated + already-active)
Import complete.
```

### 4. Test ingest failure path (embed delivery test)

```
curl -s -X POST "http://localhost:5678/webhook/ris-ingest" \
  -H "Content-Type: application/json" \
  -d '{"url":"http://127.0.0.1:9/embed-test","source_family":"blog"}'
```

Response (webhook response body from n8n):

```json
{
  "status": "failed",
  "url": "http://127.0.0.1:9/embed-test",
  "source_family": "blog",
  "error": "Unknown error",
  "timestamp": "2026-04-09T20:19:12.748Z",
  "embeds": [
    {
      "title": "RIS Ingest Failed",
      "description": "Family: blog | Exit: n/a",
      "color": 16711680,
      "fields": [
        { "name": "URL", "value": "http://127.0.0.1:9/embed-test", "inline": false },
        { "name": "Error", "value": "Unknown error", "inline": false }
      ],
      "footer": { "text": "RIS | ris-unified-dev | ingest" },
      "timestamp": "2026-04-09T20:19:12.748Z"
    }
  ],
  "webhookUrl": "https://discord.com/api/webhooks/...[REDACTED]",
  "notifyEnabled": true
}
```

Confirmed: `embeds` array in output, `notifyEnabled: true`, `Operator: Send Webhook`
fired with `{ embeds: $json.embeds }` payload.

## Test results by alert path

| Path | Node | Status | Notes |
|------|------|--------|-------|
| Ingest failure | Ingest: Format Fail | PASS | Response body shows correct embed structure with RED color, URL+Error fields |
| Health alert | Health: Format Alert | Code verified | Produces RED/YELLOW embed with Runs/Docs/Errors inline fields, Actionable Checks |
| Section pipeline error | Academic/Reddit/Blog/YouTube/GitHub/Freshness: Format Error | Code verified | All 6 use identical pattern with section-specific title and footer |
| Daily summary | Summary: Format Message | Code verified | GREEN/YELLOW/RED based on actionable checks; stats fields + Prechecks |
| Summary error | Summary: Format Error | Code verified | YELLOW embed with stderr field |

Health, section error, and summary paths were not triggered manually since they
require docker container commands or scheduled execution. The ingest failure path
is the only real-time testable path via webhook and it confirmed the full embed
delivery pipeline is working.

## Notes

- `infra/n8n/_patch_embeds.py` was used as a build tool and removed after the patch was applied. It should not be committed to the repo.
- The `content` field is no longer produced or consumed by any notification node. Downstream nodes (Ingest: Respond 500) continue to receive `status`, `url`, `source_family`, `error`, `exitCode`, `timestamp` via the statusPayload spread in `Ingest: Format Fail`.
- Notification delivery remains optional: all format nodes continue to check for a valid `http://` or `https://` URL in `__RIS_OPERATOR_WEBHOOK_URL__`, and `Operator: Notify Enabled?` gates on `notifyEnabled === true`.

## Codex review

- Tier: Skip (workflow JSON + dev log; no execution code changes)
