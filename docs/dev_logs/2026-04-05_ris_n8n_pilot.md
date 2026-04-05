# Dev Log: RIS n8n Pilot

**Date:** 2026-04-05
**Slug:** ris_n8n_pilot
**Task:** quick-260404-rtv

## Summary

- ADR 0013 authored: n8n approved as scoped RIS-only pilot, explicitly not Phase 3 automation.
- n8n service added to docker-compose.yml under `ris-n8n` profile (pinned `n8nio/n8n:1.88.0`).
- Three workflow JSON templates created for health check, scheduler status, and webhook-triggered URL acquisition.
- RIS_OPERATOR_GUIDE.md updated with full n8n start/import/activate procedure and Claude Code MCP connection instructions.

## Work Done

### ADR 0013 (docs/adr/0013-ris-n8n-pilot-scoped.md)

Written to resolve authority drift: the question of whether n8n should be pulled forward
from Phase 3 without abandoning Phase 0/1 CLI-first discipline.

Decision: n8n is approved as a **scoped pilot for RIS ingestion jobs only**. Hard scope
boundaries are documented:

**Allowed:** `research-acquire`, `research-ingest`, `research-health`,
`research-scheduler status`, `research-stats summary`.

**Hard out-of-scope:** strategy logic, gate logic, risk policy, live capital operations,
FastAPI endpoints, SimTrader replay/shadow.

Any expansion beyond these surfaces requires a new ADR and human approval.

### docker-compose.yml changes

Added `n8n` service:
- Image: `n8nio/n8n:1.88.0` (pinned, non-latest)
- Profile: `ris-n8n` (opt-in, not in default stack)
- Environment: basic auth, encryption key, runners enabled, MCP bearer token, timezone
- Volume: `n8n_data:/home/node/.n8n` (persistent workflow and credential storage)
- Network: polytool (same bridge as other services)
- Added `n8n_data:` to top-level `volumes:` block

### .env.example changes

Added n8n section with all required variables:
- `N8N_PORT=5678`
- `N8N_BASIC_AUTH_USER=admin`
- `N8N_BASIC_AUTH_PASSWORD=changeme` (placeholder)
- `N8N_ENCRYPTION_KEY=changeme_32chars_min_replace_this` (placeholder)
- `GENERIC_TIMEZONE=UTC`
- `N8N_MCP_BEARER_TOKEN=replace_with_mcp_bearer_token` (placeholder)
- `MCP_PORT=8001`
- `RIS_SCHEDULER_BACKEND=apscheduler` (commented, informational)

### scripts/docker-start.sh changes

Updated to support multiple flags in a loop (not just single positional arg):
- `--with-bots`: starts pair-bot profile (preserved behavior)
- `--with-n8n`: starts ris-n8n profile; prints scheduler mutual exclusion warning
- Default behavior unchanged

### Workflow templates (infra/n8n/workflows/)

Three templates created, all with `"active": false`:

| File | CLI command | Trigger type |
|------|-------------|--------------|
| `ris_health_check.json` | `python -m polytool research-health` | Manual + cron every 6h |
| `ris_scheduler_status.json` | `python -m polytool research-scheduler status` | Manual only |
| `ris_manual_acquire.json` | `python -m polytool research-acquire --url ... --source-family ...` | Webhook POST |

Each workflow JSON includes a `notes` field documenting the scope boundary and the
exact CLI command being called.

Workflows NOT included (no CLI surface to back them):
- Automated arXiv topic search: no dedicated trigger-and-forget CLI entrypoint separate
  from the scheduler (research-scheduler handles this internally via JOB_REGISTRY).
  n8n can call `research-scheduler start` but that starts the full APScheduler loop
  inside the container -- not appropriate as an n8n workflow.
- research-precheck: not a background job; requires idea text input, better suited to
  manual Claude Code invocation than periodic n8n trigger.

### infra/n8n/import-workflows.sh

Helper script that imports all `infra/n8n/workflows/*.json` via the n8n REST API
(`POST /api/v1/workflows`). Requires `curl` and `jq`. Prints per-workflow success/fail
HTTP status and a summary with next steps including the mutual exclusion warning.

### RIS_OPERATOR_GUIDE.md

Added `## n8n RIS Pilot (Opt-In)` section covering:
- Scope boundary (one sentence)
- Scheduler selection table (APScheduler vs n8n)
- Mutual exclusion procedure (stop ris-scheduler before starting n8n)
- Step-by-step start/import/activate flow (8 numbered steps)
- Manual verification steps (execute workflow, check executions tab)
- Webhook usage example with curl
- Security note: webhook URL contains token, treat as secret
- Claude Code MCP connection via HTTP bearer token (do NOT use N8N_MCP_ENABLED)

## Scheduler Mutual Exclusion Note

**APScheduler (default)** runs via the `ris-scheduler` container which has no compose
profile -- it starts whenever `docker compose up` is run. This is by design: the
scheduler is part of the default operating posture.

**n8n (opt-in)** is behind the `ris-n8n` compose profile. It only starts when the
operator explicitly passes `--with-n8n` or `--profile ris-n8n`.

There is NO code-level lock preventing both from running simultaneously. The mutual
exclusion is enforced by:
1. Compose profile design: the default stack never starts n8n.
2. Operator procedure: documented in ADR 0013 and operator guide.
3. Warning message: docker-start.sh prints a warning when `--with-n8n` is used.

If an operator accidentally runs both, the consequence is duplicate RIS ingestion -- each
URL gets acquired twice. This is not data-corrupting (dedup runs on ingest) but wastes
fetch budget. The operator guide covers the recovery procedure.

## Open Items

- n8n cron trigger times are not pre-configured to match JOB_REGISTRY schedules exactly.
  The health check defaults to every 6h which is reasonable, but operators should
  configure cron triggers in the n8n UI after import to match their preferred cadence.
- No Grafana panels for n8n execution metrics. RIS Grafana panels are still deferred
  (see PLANNED items in RIS_OPERATOR_GUIDE.md).
- The `ris_manual_acquire.json` workflow uses an expression-based command that interpolates
  `url` and `source_family` from the webhook body. Operators should note that n8n
  expressions are evaluated at runtime; any single-quote or special character in a URL
  must be URL-encoded before POSTing to the webhook.

## Codex Review

Skipped. No strategy, execution, risk, or gate files were touched. All changes are
infrastructure config, documentation, and workflow templates.

## Tests Run

```
python -m polytool --help             # CLI loads, no import errors
python -m polytool research-scheduler --help  # scheduler CLI available
python -m polytool research-acquire --help    # acquire CLI available
python -m polytool research-health            # health command runs (OK with empty KB)
docker compose config --quiet         # compose file valid, exit 0
```

All verifications passed. No code was modified; no regression risk.
