# 2026-04-09 Discord Embed Final Polish

## Summary

Applied a final visual polish pass to all 10 Discord embed format nodes in the RIS unified n8n
workflow (`ris-unified-dev.json`). The previous session (2026-04-09_discord_alert_layout_refinement)
converted all nodes from plain-text `content` payloads to structured Discord embeds. This session
eliminates remaining noise: `n/a` placeholders, `none` fallbacks, redundant footer identifiers,
and overly verbose descriptions.

## Files changed

- `infra/n8n/workflows/ris-unified-dev.json` — 10 format nodes patched
- `docs/runbooks/RIS_DISCORD_ALERTS.md` — format reference updated to match new embed style
- `docs/dev_logs/2026-04-09_discord_embed_final_polish.md` — this file

## Design choices

### No n/a or none
Fields that would show `n/a` or `none` are now omitted entirely when the underlying value is
absent. This applies to: health stat fields when stats command fails, pipeline error stderr/stdout
when empty, ingest failure exit code when not present, summary error stderr when empty.

### Conditional fields
All stat and output fields now use truthiness guards before pushing to the `fields` array. Example
(pipeline error): `if (stderrRaw.length > 0) { embed.fields.push(...) }`. This means a clean
run error that produces no stderr shows an embed with only the title and exit code — minimal and
unambiguous.

### Severity in titles
- Ingest failure: `Ingest Failed: {Family}` (family capitalized, e.g. "Blog") — communicates both
  that it failed and which source family
- Pipeline errors: `Pipeline Error: {Section}` with display name (Academic, Reddit, Blog, YouTube,
  GitHub, Freshness) — drops the internal slug (`academic_ingest` → `Academic`)
- Health: `RIS Health: {STATUS}` — unchanged, already communicates severity
- Daily summary: `RIS Daily Summary` — unchanged, digest tone intentional

### Shorter footers
`ris-unified-dev` removed from all footers. It added no operator value since the workflow name
is visible in the n8n UI and the footer label is sufficient for triage:
- `RIS | health`
- `RIS | {section}` (e.g. `RIS | academic`)
- `RIS | ingest`
- `RIS | daily-summary`

### URL truncation in ingest failure
Long URLs (over 60 chars) are truncated to `domain/...last20chars` using `new URL()` parsing.
Short URLs are shown in full. The field was renamed from `URL` (non-inline, full-width) to
`Source` (inline) to reduce visual weight.

### Problem-first descriptions
- Health: description now states the problem (`pipeline_error detected` or `N checks need
  attention`) instead of repeating the run/doc stats that are already in fields.
- Daily summary: description simplified to `Health: {status}` — doc/run counts are in fields.

### Actionable check markers
Health alert check lines now prefix with `[RED]` or `[YLW]` instead of bare status text,
making severity scannable in Discord's mobile rendering.

## Before / after comparison

### Ingest failure

Before:
```
Title:       RIS Ingest Failed
Description: Family: blog | Exit: n/a
Fields:      URL: http://127.0.0.1:9/final-polish-test  (non-inline)
             Error: Unknown error
Footer:      RIS | ris-unified-dev | ingest
```

After:
```
Title:       Ingest Failed: Blog
Description: Family: Blog
Fields:      Source: http://127.0.0.1:9/final-polish-test  (inline, URL truncated if long)
             Detail: Unknown error
Footer:      RIS | ingest
```

### Pipeline error (Academic example)

Before:
```
Title:       RIS Pipeline Error: academic_ingest
Description: Exit code: 1
Fields:      stderr: none    (always present, even when empty)
             stdout (tail): none
Footer:      RIS | ris-unified-dev | academic_ingest
```

After:
```
Title:       Pipeline Error: Academic
Description: Exit 1
Fields:      Error Output: [text]    (omitted when empty)
             Last Output: [text]     (omitted when empty)
Footer:      RIS | academic
```

### Health alert

Before:
```
Title:       RIS Health: RED
Description: 5 runs | n/a docs | 0 ingest errors   (n/a when stats fail)
Fields:      Runs=5 | Docs=n/a | New=n/a | Cached=n/a | Errors=n/a  (all present, n/a filled)
             Actionable Checks: RED pipeline_error: ...
Footer:      RIS | ris-unified-dev
```

After:
```
Title:       RIS Health: RED
Description: pipeline_error detected
Fields:      Runs=5                  (stat fields omitted when stats command failed)
             Actionable Checks: [RED] pipeline_error: ...
Footer:      RIS | health
```

### Daily summary

Before:
```
Title:       RIS Daily Summary
Description: Health: GREEN | 1240 docs | 48 runs
Fields:      Docs=1240 | Runs=48 | New=12 | Ingest Errors=0 | ...
Footer:      RIS | ris-unified-dev | daily-summary
```

After:
```
Title:       RIS Daily Summary
Description: Health: GREEN
Fields:      Docs=1240 | Runs=48 | New=12 | Ingest Errors=0 | ...
Footer:      RIS | daily-summary
```

### Summary error

Before:
```
Fields:      stderr: none    (always present, even when empty)
Footer:      RIS | ris-unified-dev | daily-summary
```

After:
```
Fields:      Error Output: [text]    (omitted when empty)
Footer:      RIS | daily-summary
```

## Commands run and output

### 1. Run patch script

```
python infra/n8n/_patch_polish.py
```

Output:
```
Patching nodes:
  s1-format-alert (Health: Format Alert)
  s2-format-err (Academic: Format Error)
  s3-format-err (Reddit: Format Error)
  s4-format-err (Blog: Format Error)
  s5-format-err (YouTube: Format Error)
  s6-format-err (GitHub: Format Error)
  s7-format-err (Freshness: Format Error)
  s8-parse (Summary: Format Message)
  s8-format-err (Summary: Format Error)
  s9-fmt-err (Ingest: Format Fail)

Wrote D:\Coding Projects\Polymarket\PolyTool\infra\n8n\workflows\ris-unified-dev.json
Total nodes patched: 10
```

Script deleted after use.

### 2. Validate JSON

```
python -m json.tool infra/n8n/workflows/ris-unified-dev.json > /dev/null && echo "JSON valid"
```

Output: `JSON valid`

### 3. Verification grep checks

```
python -c "... check for n/a, none, ris-unified-dev ..."
```

Output: `All checks passed: no n/a, no none fallback, no ris-unified-dev in footers, no Exit: n/a`

### 4. Re-import workflow

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

### 5. Test ingest failure path

```
curl -s -X POST "http://localhost:5678/webhook/ris-ingest" \
  -H "Content-Type: application/json" \
  -d '{"url":"http://127.0.0.1:9/final-polish-test","source_family":"blog"}'
```

Response (formatted):
```json
{
  "status": "failed",
  "url": "http://127.0.0.1:9/final-polish-test",
  "source_family": "blog",
  "error": "Unknown error",
  "timestamp": "2026-04-09T20:57:56.492Z",
  "embeds": [{
    "title": "Ingest Failed: Blog",
    "description": "Family: Blog",
    "color": 16711680,
    "fields": [
      { "name": "Source", "value": "http://127.0.0.1:9/final-polish-test", "inline": true },
      { "name": "Detail", "value": "Unknown error", "inline": false }
    ],
    "footer": { "text": "RIS | ingest" },
    "timestamp": "2026-04-09T20:57:56.492Z"
  }],
  "notifyEnabled": true
}
```

Confirmed:
- Title: `Ingest Failed: Blog` (not `RIS Ingest Failed`)
- Description: `Family: Blog` (no `Exit: n/a` — exitCode was null)
- Source field inline with full URL (short URL, no truncation needed)
- Footer: `RIS | ingest` (not `RIS | ris-unified-dev | ingest`)

## Test results by alert path

| Path | Node | Status | Notes |
|------|------|--------|-------|
| Ingest failure | Ingest: Format Fail | PASS (live curl) | New title/footer confirmed; no n/a in description |
| Health alert | Health: Format Alert | Code verified | Conditional stat fields; [RED]/[YLW] markers; problem-first description |
| Pipeline errors (x6) | Academic/Reddit/Blog/YouTube/GitHub/Freshness: Format Error | Code verified | Conditional stderr/stdout fields; display name titles; short footers |
| Daily summary | Summary: Format Message | Code verified | Simplified description; short footer |
| Summary error | Summary: Format Error | Code verified | Conditional stderr field; renamed label; short footer |

Health, pipeline error, and summary paths require scheduled execution or docker commands to
trigger live. The ingest failure path is the only real-time testable path via webhook and it
confirmed the full embed delivery pipeline is working with the new format.

## Codex review

- Tier: Skip (workflow JSON + docs only, no execution code changes)
