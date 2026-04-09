---
phase: quick-260409-mik
plan: 01
subsystem: infra/n8n
tags: [discord, n8n, notifications, embed, ris]
dependency_graph:
  requires: []
  provides: [embed-format Discord alerts for all 9 RIS notification paths]
  affects: [infra/n8n/workflows/ris-unified-dev.json]
tech_stack:
  added: []
  patterns: [Discord embed format, severity-aware color coding, structured fields]
key_files:
  created:
    - docs/dev_logs/2026-04-09_discord_alert_layout_refinement.md
  modified:
    - infra/n8n/workflows/ris-unified-dev.json
decisions:
  - "Use decimal color integers in embed objects (16711680=RED, 16744448=YELLOW, 3066993=GREEN)"
  - "Cap field values at 300 chars to stay within Discord limits and keep mobile-readable"
  - "Ingest: Format Fail spreads statusPayload alongside embeds to preserve Respond 500 downstream contract"
  - "No markdown code blocks in embed fields — render poorly on mobile"
metrics:
  duration: ~20 minutes
  completed: "2026-04-09"
  tasks_completed: 2
  files_modified: 2
---

# Quick 260409-mik: Refine Discord Notifications to Embed Format Summary

**One-liner:** Converted all 9 Discord notification nodes in ris-unified-dev.json from plain-text `{ content: "..." }` to structured Discord embeds with severity-aware colors (RED/YELLOW/GREEN), inline metric fields, and footer metadata.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Convert all format nodes and sender to Discord embed payloads | 7009460 | infra/n8n/workflows/ris-unified-dev.json |
| 2 | Re-import workflow and write dev log | 275a91f | docs/dev_logs/2026-04-09_discord_alert_layout_refinement.md |

## What Was Built

All 9 format nodes in the unified RIS n8n workflow now produce Discord embed objects instead of plain-text `content` strings:

### Node changes

| Node ID | Node Name | Embed Title | Color |
|---------|-----------|-------------|-------|
| s1-format-alert | Health: Format Alert | RIS Health: {overallStatus} | RED or YELLOW |
| s2-format-err | Academic: Format Error | RIS Pipeline Error: academic_ingest | RED |
| s3-format-err | Reddit: Format Error | RIS Pipeline Error: reddit_polymarket | RED |
| s4-format-err | Blog: Format Error | RIS Pipeline Error: blog_ingest | RED |
| s5-format-err | YouTube: Format Error | RIS Pipeline Error: youtube_ingest | RED |
| s6-format-err | GitHub: Format Error | RIS Pipeline Error: github_ingest | RED |
| s7-format-err | Freshness: Format Error | RIS Pipeline Error: freshness_refresh | RED |
| s8-parse | Summary: Format Message | RIS Daily Summary (or RIS Daily Summary Error) | GREEN/YELLOW/RED |
| s8-format-err | Summary: Format Error | RIS Summary Error | YELLOW |
| s9-fmt-err | Ingest: Format Fail | RIS Ingest Failed | RED |

Sender node (operator-notify-send) updated: `jsonBody` changed from
`={{ JSON.stringify({ content: $json.content }) }}` to
`={{ JSON.stringify({ embeds: $json.embeds }) }}`

### Design system

- **Colors**: RED (16711680) for failures/errors, YELLOW (16744448) for warnings, GREEN (3066993) for healthy summaries
- **Fields**: inline for numeric metrics (Runs, Docs, New, Cached, Errors), non-inline for text content
- **Footer**: `RIS | ris-unified-dev` base, with section context appended for pipeline errors and summary
- **Truncation**: stderr ≤ 300 chars, stdout tail ≤ 200 chars, field values ≤ 300 chars
- **No markdown code blocks**: Discord renders them poorly on mobile

## Verification

- JSON validates: `python -m json.tool infra/n8n/workflows/ris-unified-dev.json` - PASS
- Re-import: `python infra/n8n/import_workflows.py` - PASS, `DISCORD_WEBHOOK_URL: configured`
- Ingest failure path confirmed: `curl POST /webhook/ris-ingest` returned embed object with RED color, URL/Error fields, footer, `notifyEnabled: true`

## Deviations from Plan

None — plan executed exactly as written.

## Threat Flags

None — this change modifies only notification formatting inside n8n workflow JSON.
No new network endpoints, auth paths, or schema changes introduced.

## Known Stubs

None — all format nodes produce complete embed payloads. The `Ingest: Format Fail` node
preserves the `statusPayload` spread required by the `Ingest: Respond 500` downstream node.

## Self-Check

- [x] infra/n8n/workflows/ris-unified-dev.json modified
- [x] docs/dev_logs/2026-04-09_discord_alert_layout_refinement.md created
- [x] Task 1 commit: 7009460
- [x] Task 2 commit: 275a91f
- [x] JSON validates
- [x] Workflow re-imported successfully
- [x] Ingest failure embed delivery confirmed

## Self-Check: PASSED
