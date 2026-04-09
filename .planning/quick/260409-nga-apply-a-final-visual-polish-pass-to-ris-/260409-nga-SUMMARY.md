---
phase: quick-260409-nga
plan: 01
subsystem: infra/n8n
tags: [discord, n8n, ris, embed-format, polish]
dependency_graph:
  requires: []
  provides: [polished-discord-embeds-v2]
  affects: [infra/n8n/workflows/ris-unified-dev.json, docs/runbooks/RIS_DISCORD_ALERTS.md]
tech_stack:
  added: []
  patterns: [conditional-embed-fields, problem-first-description, title-cased-section-names]
key_files:
  created:
    - docs/dev_logs/2026-04-09_discord_embed_final_polish.md
  modified:
    - infra/n8n/workflows/ris-unified-dev.json
    - docs/runbooks/RIS_DISCORD_ALERTS.md
decisions:
  - Fields omitted entirely when empty rather than showing n/a or none placeholders
  - Ingest failure title includes source family for immediate context (Ingest Failed: Blog)
  - Pipeline error section names title-cased in title and lower-cased in footer (Pipeline Error: Academic / RIS | academic)
  - Health description uses problem-first language (N checks need attention) rather than stat summary
  - URL truncation uses URL() parsing to extract domain + tail for long URLs
  - ris-unified-dev removed from all footers as it adds no operator triage value
metrics:
  duration: ~20 minutes
  completed: 2026-04-09
  tasks_completed: 2
  files_modified: 3
---

# Phase quick-260409-nga Plan 01: Discord Embed Final Polish Summary

**One-liner:** Final visual polish pass on all 10 RIS Discord embed format nodes — eliminates n/a placeholders, adds conditional fields, severity-prefixed titles, URL truncation, and compact footers.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Polish all embed format nodes in ris-unified-dev.json | c5166c7 | infra/n8n/workflows/ris-unified-dev.json |
| 2 | Re-import workflow + update docs + create dev log | 27825ab | docs/runbooks/RIS_DISCORD_ALERTS.md, docs/dev_logs/2026-04-09_discord_embed_final_polish.md |

## What Was Built

Patched all 10 Discord embed format nodes in the RIS unified n8n workflow via a write-and-delete Python patch script. Changes across node categories:

**Ingest failure (s9-fmt-err):**
- Title: `RIS Ingest Failed` → `Ingest Failed: {Family}` (e.g. "Ingest Failed: Blog")
- Description: `Family: blog | Exit: n/a` → `Family: Blog` (exit code shown only when non-null)
- URL field: non-inline, name "URL" → inline, name "Source", long URLs truncated to `domain/...tail`
- Error field: renamed from "Error" to "Detail"
- Footer: `RIS | ris-unified-dev | ingest` → `RIS | ingest`

**Pipeline errors (6 nodes: s2–s7):**
- Titles: `RIS Pipeline Error: academic_ingest` → `Pipeline Error: Academic` (title-cased display names)
- Description: `Exit code: 1` → `Exit 1`
- stderr/stdout fields: conditional — only added when non-empty (eliminates `none` placeholder)
- Field labels: `stderr` → `Error Output`, `stdout (tail)` → `Last Output`
- Footers: `RIS | ris-unified-dev | academic_ingest` → `RIS | academic`

**Health alert (s1-format-alert):**
- Description: `5 runs | n/a docs | 0 ingest errors` → `pipeline_error detected` (problem-first)
- Stat fields: conditional — omitted when null (no n/a when stats command fails)
- Actionable check markers: bare status → `[RED]` / `[YLW]` prefix
- Footer: `RIS | ris-unified-dev` → `RIS | health`

**Daily summary (s8-parse):**
- Description: `Health: GREEN | 1240 docs | 48 runs` → `Health: GREEN` (counts already in fields)
- Footer: `RIS | ris-unified-dev | daily-summary` → `RIS | daily-summary`

**Summary error (s8-format-err):**
- stderr field: conditional — omitted when empty, renamed to "Error Output"
- Footer: `RIS | ris-unified-dev | daily-summary` → `RIS | daily-summary`

## Verification Results

| Check | Result |
|-------|--------|
| JSON valid | PASS |
| No n/a in field value assignments | PASS |
| No `none` fallback in any node | PASS |
| No `ris-unified-dev` in any footer | PASS |
| No `Exit: n/a` in ingest node | PASS |
| Workflow re-imported (B34eBaBPIvLb8SYj updated) | PASS |
| Curl test: title = "Ingest Failed: Blog" | PASS |
| Curl test: description has no n/a | PASS |
| Curl test: footer = "RIS \| ingest" | PASS |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. All embed changes are complete and confirmed via live curl test.

## Threat Flags

None — cosmetic change only; no new inputs, auth changes, or data flow changes introduced.

## Self-Check: PASSED

- infra/n8n/workflows/ris-unified-dev.json: FOUND
- docs/runbooks/RIS_DISCORD_ALERTS.md: FOUND
- docs/dev_logs/2026-04-09_discord_embed_final_polish.md: FOUND
- Commit c5166c7: FOUND
- Commit 27825ab: FOUND
