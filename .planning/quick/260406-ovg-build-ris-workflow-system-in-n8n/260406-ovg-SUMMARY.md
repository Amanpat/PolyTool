---
phase: quick-260406-ovg
plan: 01
subsystem: ris-n8n
tags: [n8n, workflows, ris, orchestration]
dependency_graph:
  requires: [n8n running at localhost:5678, polytool-ris-scheduler container, DISCORD_WEBHOOK_URL env var for alerts]
  provides: [8 deployed n8n RIS workflows, health monitoring, webhook triggers, URL ingest]
  affects: [workflows/n8n/, docker-compose.yml, docs/dev_logs/]
tech_stack:
  added: [n8n ScheduleTrigger 6-field cron, n8n Switch V2 dynamic routing, executeCommand re-enabled via NODES_EXCLUDE=[]]
  patterns: [sub-workflow + orchestrator pattern, webhook-triggered pipeline dispatch, Discord alerting via HTTP request node]
key_files:
  created:
    - workflows/n8n/ris_orchestrator.json
    - workflows/n8n/ris_sub_academic.json
    - workflows/n8n/ris_sub_reddit.json
    - workflows/n8n/ris_sub_blog_rss.json
    - workflows/n8n/ris_sub_youtube.json
    - workflows/n8n/ris_sub_github.json
    - workflows/n8n/ris_sub_weekly_digest.json
    - workflows/n8n/ris_sub_freshness_refresh.json
    - workflows/n8n/workflow_ids.env
    - workflows/n8n/README.md
    - docs/dev_logs/2026-04-06_ris_n8n_workflow_system.md
  modified:
    - docker-compose.yml
decisions:
  - Switch V2 required for 7-output routing (V1 hardcodes 4 outputs)
  - NODES_EXCLUDE=[] required to re-enable executeCommand in n8n 2.x
  - 6-field cron format required by n8n 2.x ScheduleTrigger
metrics:
  duration: ~3 hours (across 2 sessions due to context limit)
  completed: 2026-04-06
  tasks_completed: 2/2
  files_created: 11
  files_modified: 1
---

# Phase quick-260406-ovg Plan 01: Build RIS n8n Workflow System Summary

8-workflow n8n orchestration system deployed: 7 scheduled sub-workflows for RIS ingestion jobs + 1 orchestrator with health monitoring, webhook pipeline dispatch, and URL ingest paths — all activated with routing verified.

## What Was Built

| Workflow | n8n ID | Schedule | Command |
|----------|--------|----------|---------|
| RIS Sub: Academic | `wGZFmbBk5TuKeiu4` | Daily 03:00 UTC | `research-scheduler run-job academic_ingest` |
| RIS Sub: Reddit | `66DODhOnrEdqc0Tk` | Daily 05:00 UTC | `research-scheduler run-job reddit_polymarket` |
| RIS Sub: Blog/RSS | `xhv5Dnru2nW7TchB` | Daily 06:00 UTC | `research-scheduler run-job blog_ingest` |
| RIS Sub: YouTube | `e6P3lkcJdwlRPgfj` | Mondays 04:00 UTC | `research-scheduler run-job youtube_ingest` |
| RIS Sub: GitHub | `ZJFoRcDFNdgzKP7m` | Wednesdays 04:00 UTC | `research-scheduler run-job github_ingest` |
| RIS Sub: Weekly Digest | `Nes9RKXadMsYcHE8` | Sundays 08:00 UTC | `research-report digest --window 7` + Discord |
| RIS Sub: Freshness Refresh | `SrEdvxt5sRFRQYrV` | Sundays 02:00 UTC | `research-scheduler run-job freshness_refresh` |
| RIS Orchestrator | `pvoP1evtPWTp5LPh` | 30min + 2 webhooks | 3-path health/trigger/ingest |

All 8 workflows deployed via n8n REST API, tagged `RIS` (tag ID `lsdE5zgirb6IHxH5`), and activated.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] n8n 2.x executeCommand disabled by default**
- **Found during:** Task 1 (workflow activation)
- **Issue:** `n8n-nodes-base.executeCommand` is in the default `NODES_EXCLUDE` list in n8n 2.x. Any workflow using this node type fails activation with "Unrecognized node type".
- **Fix:** Added `NODES_EXCLUDE=[]` to docker-compose.yml n8n service environment. Container recreated with `docker compose --profile ris-n8n up -d n8n` (restart alone does not pick up new env vars).
- **Files modified:** `docker-compose.yml`
- **Commit:** 0d078fb

**2. [Rule 1 - Bug] ScheduleTrigger cron format incompatibility**
- **Found during:** Task 1 (cron workflow activation)
- **Issue:** n8n 2.x ScheduleTrigger requires 6-field cron format `[Second Minute Hour DoM Month DoW]`. JSON was using 5-field format (`"0 4 * * 1"`) and wrong parameter key (`rule.cronExpression` instead of `rule.interval[{field:"cronExpression", expression:"0 0 4 * * 1"}]`). Caused "Could not find property option" error on activation.
- **Fix:** Updated all 4 cron-based sub-workflows (youtube, github, weekly_digest, freshness_refresh) with correct 6-field format and interval[] structure.
- **Files modified:** `ris_sub_youtube.json`, `ris_sub_github.json`, `ris_sub_weekly_digest.json`, `ris_sub_freshness_refresh.json`
- **Commit:** 18532dc

**3. [Rule 1 - Bug] Switch V1 4-output limit breaks 7-pipeline routing**
- **Found during:** Task 2 (Path B routing verification)
- **Issue:** Switch node V1 (`typeVersion: 1`) hardcodes `returnData = [[], [], [], []]` — exactly 4 outputs. With 7 routing rules, indices 4-6 overflowed into branch 0 (Academic). Every pipeline except `academic`, `reddit`, `blog`, `youtube` incorrectly routed to Exec Academic.
- **Fix:** Upgraded Switch node to V2 (`typeVersion: 2`) with `"mode": "rules"`, `outputKey` on each rule, and `"fallbackOutput": -1`. V2 uses dynamic output count based on rules.
- **Files modified:** `ris_orchestrator.json`
- **Commit:** 0d078fb

**4. [Rule 1 - Bug] executeCommand expression not interpolated**
- **Found during:** Task 2 (Path C URL ingest testing)
- **Issue:** n8n executeCommand `command` field requires `=` prefix to be evaluated as an expression. Without it, `{{ $json.body.url }}` is passed as a literal string.
- **Fix:** Added `=` prefix: `"=docker exec polytool-ris-scheduler python -m polytool research-acquire --url \"{{ $json.body.url }}\" ..."`.
- **Files modified:** `ris_orchestrator.json`
- **Commit:** 0d078fb

**5. [Rule 3 - Blocking] PUT API rejects read-only/disallowed fields**
- **Found during:** Task 2 (workflow update via PUT)
- **Issue:** n8n 2.x `PUT /api/v1/workflows/{id}` returns 400 for `notes`, `meta`, `tags`, `triggerCount`, and `active` fields.
- **Fix:** Stripped disallowed fields before PUT. Tags managed via `PUT /api/v1/workflows/{id}/tags`. Active state via `POST /api/v1/workflows/{id}/activate`.
- **Commit:** 0d078fb

## Routing Verification

Path B routing confirmed correct after Switch V2 upgrade:

| Execution | Pipeline Input | Routed To | Status |
|-----------|----------------|-----------|--------|
| 13 | reddit | Exec Reddit | error* |
| 15 | github | Exec GitHub | error* |
| 17 | freshness | Exec Freshness | success |
| 19 | academic | Exec Academic | success |

*Execution errors from numpy missing in polytool-ris-scheduler container — not a workflow issue. Routing is correct.

## Known Issues (Out of Scope)

- `ModuleNotFoundError: numpy` in `polytool-ris-scheduler` container causes some `research-acquire` and `research-scheduler run-job` commands to fail. Container image rebuild required — tracked as separate work.
- `DISCORD_WEBHOOK_URL` not set in current n8n deployment. Path A alerts and weekly digest will not reach Discord until this env var is configured.
- Path A (30min health monitor) not directly tested — schedule-triggered. Verify via n8n execution history or Discord after next 30-min window.

## Commits

| Hash | Message | Files |
|------|---------|-------|
| 18532dc | feat(quick-260406-ovg): deploy 7 RIS sub-workflows to n8n | 7 sub-workflow JSONs + workflow_ids.env |
| 0d078fb | feat(quick-260406-ovg): deploy RIS orchestrator and activate all workflows | ris_orchestrator.json + docker-compose.yml |

## Self-Check: PASSED

Files verified to exist:
- workflows/n8n/ris_orchestrator.json: FOUND
- workflows/n8n/ris_sub_academic.json: FOUND
- workflows/n8n/ris_sub_reddit.json: FOUND
- workflows/n8n/ris_sub_blog_rss.json: FOUND
- workflows/n8n/ris_sub_youtube.json: FOUND
- workflows/n8n/ris_sub_github.json: FOUND
- workflows/n8n/ris_sub_weekly_digest.json: FOUND
- workflows/n8n/ris_sub_freshness_refresh.json: FOUND
- workflows/n8n/workflow_ids.env: FOUND
- workflows/n8n/README.md: FOUND
- docs/dev_logs/2026-04-06_ris_n8n_workflow_system.md: FOUND

Commits verified: 18532dc and 0d078fb present in git log.
