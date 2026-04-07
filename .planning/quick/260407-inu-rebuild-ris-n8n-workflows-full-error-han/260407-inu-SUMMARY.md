---
phase: quick
plan: 260407-inu
subsystem: ris-n8n
tags: [n8n, ris, workflows, error-handling, discord, orchestration]
dependency_graph:
  requires: [260406-ovg-build-ris-workflow-system-in-n8n]
  provides: [ris-n8n-production-error-handling]
  affects: [ris-pipeline-observability, discord-alerting]
tech_stack:
  added: []
  patterns: [continueOnFail-pattern, exit-code-IF-branch, minimal-PUT-body, errorWorkflow-catch-all]
key_files:
  created:
    - workflows/n8n/ris_global_error_watcher.json
    - docs/dev_logs/2026-04-07_n8n-workflow-rebuild.md
  modified:
    - workflows/n8n/ris_sub_academic.json
    - workflows/n8n/ris_sub_reddit.json
    - workflows/n8n/ris_sub_blog_rss.json
    - workflows/n8n/ris_sub_youtube.json
    - workflows/n8n/ris_sub_github.json
    - workflows/n8n/ris_sub_weekly_digest.json
    - workflows/n8n/ris_sub_freshness_refresh.json
    - workflows/n8n/ris_orchestrator.json
    - workflows/n8n/workflow_ids.env
    - workflows/n8n/README.md
decisions:
  - Use minimal PUT body (6 fields only) for all n8n workflow updates — n8n API rejects additional properties
  - Global Error Watcher as catch-all via settings.errorWorkflow — covers node-level failures that bypass continueOnFail
  - Weekly Digest always sends Discord regardless of exit code — operator visibility guaranteed even on partial failure
metrics:
  duration: ~90min
  completed: 2026-04-07
  tasks_completed: 2
  files_changed: 10
---

# Quick 260407-inu: RIS n8n Workflow Full Rebuild Summary

Rebuilt all 8 skeletal RIS n8n workflows from scratch with proper error handling — exit code IF branches, continueOnFail on all Execute Command and HTTP nodes, Discord alerts on failure, stdout metrics parsing on success — plus a new 9th Global Error Watcher workflow set as catch-all error handler on all 8 others.

## What Was Done

### Task 1: Rebuild All 9 Workflow JSON Files

Deleted the 8 original skeletal workflows (which had no error handling) and rebuilt them:

**Standard sub-workflow pattern (6 of 7 subs):**
```
Trigger → Execute Command [continueOnFail] → IF exitCode==0
  TRUE  → Parse Metrics (code) → Success (noOp)
  FALSE → Format Error (code) → Discord Alert [continueOnFail]
```

**Weekly Digest special flow:**
Always sends Discord digest regardless of outcome. Conditionally sends a second
error-detail alert if either `research-report digest` or `research-stats summary` failed.

**Orchestrator (3 sections):**
- Health Monitor: 30-min schedule → research-health + research-stats → parse for RED/CRITICAL/FAIL → Discord alert only on issues
- Webhook Dispatcher: POST /ris-trigger → Switch (7 pipelines) → Execute Workflow → respondToWebhook 200/400
- URL Ingest: POST /ris-ingest → research-acquire → IF exitCode → 200 or 500 + Discord

**Global Error Watcher (new):**
Error trigger → format context (workflow name, node, execution ID, error message) → Discord alert.

### Task 2: Deploy, Configure, Activate

All 9 workflows deployed to n8n:

| Workflow | ID |
|---|---|
| RIS Sub: Academic | yDBfhk9tJQlAWJbz |
| RIS Sub: Reddit | 34EhYveCbJie5hub |
| RIS Sub: Blog/RSS | fi2iglrNXcK9qXEg |
| RIS Sub: YouTube | rHdYkf3Q6EgUC6KQ |
| RIS Sub: GitHub | 3rk0GiZM6GHJWq4z |
| RIS Sub: Weekly Digest | 5wGKoPm7eJ3K2eIE |
| RIS Sub: Freshness Refresh | vAiyicAFlnfq2RDh |
| RIS Global Error Watcher | WFvBwCepYu8JzKDs |
| RIS Orchestrator | PEX5vHCexProT2sC |

- `settings.errorWorkflow: "WFvBwCepYu8JzKDs"` applied to all 8 non-error-watcher workflows
- All 9 tagged with RIS tag `lsdE5zgirb6IHxH5`
- All 9 activated (verified `active: true`)
- `workflow_ids.env` updated with new IDs

## Deviations from Plan

### Auto-fixed Issues

None beyond the plan scope.

### Deployment Discoveries

**1. [Rule 3 - Blocking] n8n API rejects `active` field on POST**
- **Found during:** Task 2 initial deployment
- **Issue:** POST body with `active: false` returns "request/body/active is read-only"
- **Fix:** Removed `active` from all 9 workflow JSON files
- **Files modified:** All 9 workflow JSON files (ecd3e45)

**2. [Rule 3 - Blocking] n8n PUT accepts only 6 specific fields**
- **Found during:** Task 2 errorWorkflow patching
- **Issue:** PUT `/workflows/{id}` returns "must NOT have additional properties" for any field
  not in: `name`, `nodes`, `connections`, `settings`, `staticData`, `pinData`
- **Fix:** Fetch GET response, rebuild minimal body with only those 6 fields, inject errorWorkflow
  into settings before PUT
- **Files modified:** Applied via API calls only

## Commits

- `ecd3e45`: feat(quick-260407-inu): rebuild 9 RIS n8n workflows with full error handling
- `3b04c6a`: feat(quick-260407-inu): deploy 9 RIS workflows with full error handling

## Known Stubs

None. All 9 workflows are fully wired with real IDs and active schedules.

## Threat Flags

None. No new network endpoints or auth paths introduced in the Python codebase.
The n8n orchestrator webhook endpoints (/ris-trigger, /ris-ingest) were planned
and are protected by the n8n instance's existing auth model.

## Self-Check: PASSED

- workflows/n8n/ris_global_error_watcher.json: FOUND
- workflows/n8n/workflow_ids.env: FOUND
- workflows/n8n/README.md: FOUND
- docs/dev_logs/2026-04-07_n8n-workflow-rebuild.md: FOUND
- 260407-inu-SUMMARY.md: FOUND
- commit ecd3e45: FOUND
- commit 3b04c6a: FOUND
- All 9 n8n workflows: active=True verified
