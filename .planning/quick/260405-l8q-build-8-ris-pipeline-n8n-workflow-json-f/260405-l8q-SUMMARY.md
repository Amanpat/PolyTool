---
phase: quick-260405-l8q
plan: "01"
subsystem: ris-pipeline
tags: [n8n, ris, workflows, discord, automation]
dependency_graph:
  requires: []
  provides: [workflows/n8n/*.json, workflows/n8n/README.md]
  affects: [docs/dev_logs]
tech_stack:
  added: []
  patterns: [n8n-workflow-json, schedule-trigger, webhook-respond-pattern, discord-alerting]
key_files:
  created:
    - workflows/n8n/ris-academic-ingestion.json
    - workflows/n8n/ris-reddit-ingestion.json
    - workflows/n8n/ris-blog-ingestion.json
    - workflows/n8n/ris-youtube-ingestion.json
    - workflows/n8n/ris-github-ingestion.json
    - workflows/n8n/ris-health-monitor.json
    - workflows/n8n/ris-weekly-digest.json
    - workflows/n8n/ris-manual-ingest.json
    - workflows/n8n/README.md
    - docs/dev_logs/2026-04-05_n8n-workflows.md
  modified: []
decisions:
  - "Container name polytool-polytool-1 (not deprecated polytool-ris-scheduler from v1)"
  - "active: true by default so workflows are operational after import without extra toggle"
  - "No tags array to avoid n8n import compatibility issues (confirmed from quick-260404-t5l)"
  - "IF node true branch = exitCode!=0 failure, routes to Discord alert; false branch silent"
  - "Health monitor Code node uses toUpperCase().includes('RED') for case-insensitive detection"
  - "Weekly digest chains two Execute Commands sequentially before combining in Code node"
  - "Manual ingest uses responseMode: responseNode so Respond to Webhook controls HTTP response"
metrics:
  duration: "~3 minutes"
  completed: "2026-04-05"
  tasks_completed: 3
  files_created: 10
---

# Phase quick-260405-l8q Plan 01: Build 8 RIS Pipeline n8n Workflows Summary

**One-liner:** 8 v2 n8n workflow JSON files with Discord failure alerting, health RED parsing, and webhook response replacing the minimal v1 pilot templates in infra/n8n/workflows/.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create 5 interval/cron ingestion workflows | 4975b98 | ris-academic, ris-reddit, ris-blog, ris-youtube, ris-github |
| 2 | Create health-monitor, weekly-digest, manual-ingest | 599eafd | ris-health-monitor, ris-weekly-digest, ris-manual-ingest |
| 3 | Create README and dev log | b7e59b4 | workflows/n8n/README.md, docs/dev_logs/2026-04-05_n8n-workflows.md |

## What Was Built

### 5 Ingestion Workflows (Schedule -> Execute -> IF -> Discord)

All follow the same pattern: Schedule Trigger fires, Execute Command runs the docker exec,
IF node checks exitCode != 0, true branch sends Discord alert, false branch is silent (success).

| Workflow | Schedule | Job |
|----------|----------|-----|
| ris-academic-ingestion.json | Every 12h | academic_ingest |
| ris-reddit-ingestion.json | Every 6h | reddit_polymarket |
| ris-blog-ingestion.json | Every 4h | blog_ingest |
| ris-youtube-ingestion.json | Weekly Mon 04:00 | youtube_ingest |
| ris-github-ingestion.json | Weekly Wed 04:00 | github_ingest |

### Health Monitor (ris-health-monitor.json)

Schedule (30min) -> Execute research-health -> Code node parses stdout for "RED" (case-insensitive),
also triggers on exitCode != 0 -> IF hasRed -> Discord alert. All-GREEN runs are silent.
Output truncated to 1500 chars in Discord embed to stay within Discord limits.

### Weekly Digest (ris-weekly-digest.json)

Schedule (Sunday 08:00) -> Execute research-report -> Execute research-stats -> Code node
combines both outputs -> HTTP Request sends combined digest to Discord (blue embeds, color 3447003).
Always sends (not conditional on failure).

### Manual Ingest (ris-manual-ingest.json)

Webhook Trigger (POST /webhook/ris-ingest) with responseMode: responseNode -> Execute
research-acquire with url and source_family from webhook body -> Respond to Webhook with
JSON result including success, result, exit_code, stderr fields.

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None. All workflows are fully wired with real node connections and correct node types.
Discord alert nodes reference `$env.DISCORD_WEBHOOK_URL` which is operator-configured
(not hardcoded) - this is by design, not a stub.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| T-quick-02 mitigated | ris-health-monitor.json | stdout truncated to 1500 chars, stderr to 500 chars in Discord embed |
| T-quick-04 mitigated | ris-manual-ingest.json | url/source_family passed as quoted shell arguments; polytool CLI validates source_family server-side |

## Self-Check: PASSED

Files verified:
- workflows/n8n/ris-academic-ingestion.json: FOUND, valid JSON, active: true, no tags
- workflows/n8n/ris-reddit-ingestion.json: FOUND, valid JSON, active: true, no tags
- workflows/n8n/ris-blog-ingestion.json: FOUND, valid JSON, active: true, no tags
- workflows/n8n/ris-youtube-ingestion.json: FOUND, valid JSON, active: true, no tags
- workflows/n8n/ris-github-ingestion.json: FOUND, valid JSON, active: true, no tags
- workflows/n8n/ris-health-monitor.json: FOUND, valid JSON, active: true, no tags
- workflows/n8n/ris-weekly-digest.json: FOUND, valid JSON, active: true, no tags
- workflows/n8n/ris-manual-ingest.json: FOUND, valid JSON, active: true, no tags
- workflows/n8n/README.md: FOUND, 3404 chars
- docs/dev_logs/2026-04-05_n8n-workflows.md: FOUND, 4636 chars

Commits verified: 4975b98, 599eafd, b7e59b4 all present in git log.
