---
phase: quick-260404-sb4
plan: "01"
subsystem: ris-n8n-pilot
tags: [ris, n8n, scheduler, workflows, docs]
dependency_graph:
  requires: [quick-260404-rtv]
  provides: [ris-n8n-pilot-complete]
  affects: [docs/RIS_OPERATOR_GUIDE.md, docs/CURRENT_STATE.md, infra/n8n/workflows/]
tech_stack:
  added: []
  patterns: [n8n-execute-command-workflow, research-scheduler-run-job-surface]
key_files:
  created:
    - infra/n8n/workflows/ris_academic_ingest.json
    - infra/n8n/workflows/ris_reddit_polymarket.json
    - infra/n8n/workflows/ris_reddit_others.json
    - infra/n8n/workflows/ris_blog_ingest.json
    - infra/n8n/workflows/ris_youtube_ingest.json
    - infra/n8n/workflows/ris_github_ingest.json
    - infra/n8n/workflows/ris_freshness_refresh.json
    - infra/n8n/workflows/ris_weekly_digest.json
    - docs/dev_logs/2026-04-05_ris_n8n_roadmap_closeout.md
  modified:
    - infra/n8n/import-workflows.sh
    - docs/RIS_OPERATOR_GUIDE.md
    - docs/CURRENT_STATE.md
decisions:
  - All 8 scheduler job workflows use research-scheduler run-job <id> surface (not reconstructed raw research-acquire args) to avoid job logic duplication and ensure single source of truth
  - Interval-based schedules use rule.interval array form; specific-time schedules use rule.cronExpression string form, matching n8n scheduleTrigger typeVersion 1 format
  - Runtime verification explicitly documented as NOT done (template JSON only, not live n8n instance); honest caveat in operator guide and dev log
metrics:
  duration: "~20 minutes"
  completed: "2026-04-05T00:33:25Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 9
  files_modified: 3
---

# Phase quick-260404-sb4 Plan 01: RIS n8n Pilot Roadmap Closeout Summary

**One-liner:** 8 n8n workflow JSON templates covering all JOB_REGISTRY scheduler jobs via `research-scheduler run-job <id>`, completing the RIS n8n pilot to roadmap-complete status.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create 8 workflow JSON templates for scheduler jobs | fa1a5f8 | 8 new workflow JSONs + import-workflows.sh comment |
| 2 | Update operator docs, CURRENT_STATE.md, and write dev log | d0c4e14 | RIS_OPERATOR_GUIDE.md, CURRENT_STATE.md, dev log |

## What Was Built

### 8 New n8n Workflow Templates

All in `infra/n8n/workflows/`, all ship with `"active": false`:

| Job ID | Workflow File | Schedule | Trigger Type |
|--------|--------------|----------|-------------|
| academic_ingest | ris_academic_ingest.json | every 12h | interval |
| reddit_polymarket | ris_reddit_polymarket.json | every 6h | interval |
| reddit_others | ris_reddit_others.json | daily 03:00 | cronExpression |
| blog_ingest | ris_blog_ingest.json | every 4h | interval |
| youtube_ingest | ris_youtube_ingest.json | Mondays 04:00 | cronExpression |
| github_ingest | ris_github_ingest.json | Wednesdays 04:00 | cronExpression |
| freshness_refresh | ris_freshness_refresh.json | Sundays 02:00 | cronExpression |
| weekly_digest | ris_weekly_digest.json | Sundays 08:00 | cronExpression |

Each workflow: Manual Trigger + Schedule Trigger + Execute Command node calling `python -m polytool research-scheduler run-job <job_id>`. Tags include `["ris", "scheduler", "<job_id>"]`. Notes include scope boundary reference (ADR 0013), CLI command, optional dependency caveats, and mutual exclusion reminder.

### import-workflows.sh

Comment on line 8 updated from "health check, scheduler status, manual acquire" to "all RIS pilot workflows (11 total)" listing all 8 scheduler job IDs. No functional logic changed — the existing glob `for wf in "$WORKFLOW_DIR"/*.json` already handles all new files automatically.

### RIS_OPERATOR_GUIDE.md

Added `### Scheduled Job Workflows` subsection between `### Webhook usage` and `### Claude Code MCP connection via n8n`. Contains:
- 8-row job-to-workflow matrix (job ID, file, CLI command, schedule, caveats)
- Scheduler mutual exclusion note (stop APScheduler before activating n8n cron triggers)
- Runtime verification caveat (NOT live-tested; template import only)

### CURRENT_STATE.md

Added `## RIS n8n Pilot Roadmap Complete` section at end of file documenting:
- 11 workflow templates total, all active=false, scoped to RIS ingestion per ADR 0013
- All 8 job IDs with their schedules
- Explicit note that this is NOT Phase 3 automation and that v2 deferred item "n8n migration from APScheduler" refers to the broader Phase 3 item (separate from this scoped pilot)

### Dev Log

`docs/dev_logs/2026-04-05_ris_n8n_roadmap_closeout.md` contains:
- 8-row coverage matrix
- CLI verification commands run and their outputs
- Rationale for using run-job surface over reconstructed raw args
- Honest "NOT runtime-verified" section with exact manual smoke test steps
- Open items (cron parsing validation, optional dep failures, no Grafana panels)

## Key Decisions

1. **Use `research-scheduler run-job <id>` surface** — Avoids duplicating job logic in n8n workflow files. If JOB_REGISTRY job definitions change internally, n8n workflows remain valid. Provides consistent exit codes and a documented interface contract.

2. **Mixed trigger types** — Interval-based (`every Nh`) jobs use `rule.interval` array form. Specific-time jobs (daily 03:00, weekly Mon/Wed/Sun) use `rule.cronExpression` string form. Both are valid for n8n scheduleTrigger typeVersion 1.

3. **Honest runtime verification caveat** — Workflows are template JSON only, not live-tested against a running n8n instance. This is documented explicitly in both the operator guide and dev log. Operators are not misled about test coverage (Threat T-sb4-03 mitigation).

## Deviations from Plan

None — plan executed exactly as written. The additional context specified 7 workflows; the plan frontmatter specified 8 (one per job, separate reddit_polymarket and reddit_others files). The plan's `files_modified` list and `must_haves.artifacts` both specify 8 files, which is what was created.

## CLI Verification

All commands run during task execution:

```
python -m polytool research-scheduler run-job --help  # subcommand exists: job_id positional arg
python -m polytool research-scheduler status           # lists 8 registered jobs
python -m polytool research-report --help              # digest subcommand listed
python -m polytool --help                              # CLI loads, no import errors
```

No regressions. No tests added (docs/config changes only; no code paths changed).

## Known Stubs

None. Workflow templates are complete configuration files, not stub implementations.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes introduced beyond what ADR 0013 already scoped. Execute Command node scope is restricted to `research-scheduler run-job` commands per ADR 0013 (T-sb4-01 accepted). Webhook URL security is unchanged (T-sb4-02 accepted). Runtime caveat documentation satisfies T-sb4-03 mitigation.

## Self-Check

Checking created files exist:

- `infra/n8n/workflows/ris_academic_ingest.json` — FOUND
- `infra/n8n/workflows/ris_reddit_polymarket.json` — FOUND
- `infra/n8n/workflows/ris_reddit_others.json` — FOUND
- `infra/n8n/workflows/ris_blog_ingest.json` — FOUND
- `infra/n8n/workflows/ris_youtube_ingest.json` — FOUND
- `infra/n8n/workflows/ris_github_ingest.json` — FOUND
- `infra/n8n/workflows/ris_freshness_refresh.json` — FOUND
- `infra/n8n/workflows/ris_weekly_digest.json` — FOUND
- `docs/dev_logs/2026-04-05_ris_n8n_roadmap_closeout.md` — FOUND

Checking commits exist:
- `fa1a5f8` (Task 1: 8 workflow templates) — FOUND
- `d0c4e14` (Task 2: operator docs + dev log) — FOUND

Verification commands from plan:
1. `ls infra/n8n/workflows/ | wc -l` → 11 (PASS)
2. `jq '.active'` on ris_academic_ingest.json → false (PASS, confirmed all 8)
3. `jq '.nodes[] | select(.type == "n8n-nodes-base.executeCommand") | .parameters.command'` → contains "research-scheduler run-job" (PASS, confirmed all 8)
4. `python -m polytool research-scheduler status` → exits 0, lists 8 jobs (PASS)
5. `python -m polytool --help` → exits 0, no import errors (PASS)
6. `grep "NOT runtime-verified" dev log` → FOUND (PASS)
7. `grep "Scheduled Job Workflows" RIS_OPERATOR_GUIDE.md` → FOUND (PASS)
8. `grep "n8n pilot complete" CURRENT_STATE.md` → FOUND (PASS)

## Self-Check: PASSED
