---
quick_id: 260407-jfu
title: Build Unified RIS n8n Development Workflow
status: complete
completed_date: 2026-04-07
duration_minutes: 25
tasks_completed: 4
tasks_total: 4
files_created:
  - workflows/n8n/ris-unified-dev.json
  - docs/dev_logs/2026-04-07_n8n-unified-workflow.md
files_modified:
  - workflows/n8n/workflow_ids.env
  - workflows/n8n/README.md
key_decisions:
  - Used POST /activate endpoint (PATCH rejected by this n8n instance)
  - Removed webhook dispatcher section -- each pipeline has direct schedule+manual triggers
  - Removed global error watcher -- inline error handling per section instead
---

# Quick Task 260407-jfu Summary: Build Unified RIS n8n Development Workflow

## One-liner

Replaced 9-workflow RIS n8n architecture with a single 81-node unified canvas workflow
deployed and activated at ID B34eBaBPIvLb8SYj.

## Tasks Completed

| Task | Name | Commit | Result |
|------|------|--------|--------|
| 1 | Environment discovery + delete existing RIS workflows | 65b8671 (partial) | 9 workflows deleted, 0 remain |
| 2 | Build unified workflow JSON | 65b8671 | ris-unified-dev.json: 81 nodes, 9 sections, all validated |
| 3 | Deploy, activate, update tracking files | 7fd4a04 | Active=True, webhook responding |
| 4 | Dev log + SUMMARY | (this commit) | Dev log written |

## Workflow Details

- **n8n Workflow ID:** `B34eBaBPIvLb8SYj`
- **Name:** `RIS -- Research Intelligence System`
- **Node count:** 81 (9 sticky labels + 72 functional nodes)
- **Active:** true
- **Webhook:** POST /webhook/ris-ingest -- confirmed responding

## Sections Built

1. Health Monitor (9 nodes) -- every 30 min, RED/CRITICAL detection
2. Academic (8 nodes) -- every 12h
3. Reddit (8 nodes) -- every 6h
4. Blog/RSS (8 nodes) -- every 4h
5. YouTube (8 nodes) -- weekly Mon 04:00 UTC
6. GitHub (8 nodes) -- weekly Wed 04:00 UTC
7. Freshness (8 nodes) -- weekly Sun 02:00 UTC
8. Weekly Digest (10 nodes) -- weekly Sun 08:00 UTC
9. URL Ingestion (7 nodes) -- webhook POST /webhook/ris-ingest

## Deviations from Plan

**1. [Rule 3 - Blocking Issue] PATCH /activate rejected, used POST instead**
- Found during: Task 3
- Issue: `PATCH /api/v1/workflows/{id}` returned "PATCH method not allowed" on this n8n instance
- Fix: Used `POST /api/v1/workflows/{id}/activate` which succeeded
- Impact: None on outcome -- workflow activated successfully

**2. Minor node count variance: 81 vs ~87 spec**
- The task spec estimated ~87 nodes. The actual build produced 81.
- Variance comes from the spec including some intermediate nodes that were consolidated
  (e.g., Health section uses Format Alert code node before Discord, but spec's "Health: 🔴 Alert"
  counted the httpRequest separately from a format node that was merged in).
- All 9 sections are present and complete. Validation passed.

## Files Created / Modified

- `workflows/n8n/ris-unified-dev.json` -- new unified workflow (2110 lines)
- `workflows/n8n/workflow_ids.env` -- updated to UNIFIED_DEV_ID=B34eBaBPIvLb8SYj
- `workflows/n8n/README.md` -- rewritten for new architecture
- `docs/dev_logs/2026-04-07_n8n-unified-workflow.md` -- new dev log

## Commits

- `65b8671` -- feat(quick-260407-jfu): build unified RIS workflow JSON (81 nodes, 9 sections)
- `7fd4a04` -- feat(quick-260407-jfu): deploy unified RIS workflow, update tracking files

## Self-Check

- [x] workflows/n8n/ris-unified-dev.json exists and is valid JSON
- [x] 81 unique-named nodes, 0 duplicate IDs
- [x] All 11 executeCommand nodes have continueOnFail:true
- [x] All 9 httpRequest nodes have continueOnFail:true
- [x] All connection references resolve to existing node names
- [x] Workflow deployed to n8n, active=True
- [x] Exactly 1 RIS workflow in n8n
- [x] Webhook /webhook/ris-ingest responds to POST
- [x] workflow_ids.env has UNIFIED_DEV_ID
- [x] Dev log written
