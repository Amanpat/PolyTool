---
phase: quick-260404-rtv
plan: 01
subsystem: infrastructure/ris
tags: [n8n, docker, ris, scheduler, workflow-automation]
dependency_graph:
  requires: [ris-scheduler, docker-compose, RIS_OPERATOR_GUIDE]
  provides: [n8n-compose-service, ris-workflow-templates, adr-0013, import-helper]
  affects: [docker-compose.yml, .env.example, scripts/docker-start.sh, docs/RIS_OPERATOR_GUIDE.md]
tech_stack:
  added: [n8nio/n8n:1.88.0]
  patterns: [compose-profile-gate, mutual-exclusion-by-convention, workflow-as-code]
key_files:
  created:
    - docs/adr/0013-ris-n8n-pilot-scoped.md
    - infra/n8n/workflows/ris_health_check.json
    - infra/n8n/workflows/ris_scheduler_status.json
    - infra/n8n/workflows/ris_manual_acquire.json
    - infra/n8n/import-workflows.sh
    - docs/dev_logs/2026-04-05_ris_n8n_pilot.md
  modified:
    - docker-compose.yml
    - .env.example
    - scripts/docker-start.sh
    - docs/RIS_OPERATOR_GUIDE.md
decisions:
  - n8n pinned at n8nio/n8n:1.88.0 (stable 1.x, non-latest)
  - Mutual exclusion is operator responsibility (compose profile design), not a code lock
  - All three workflow templates ship with active=false; operator activates manually
  - Webhook URL for ris_manual_acquire treated as a secret (documented in notes field)
  - MCP connection via HTTP transport at /mcp-server/http + bearer token (N8N_MCP_ENABLED not used)
metrics:
  completed: 2026-04-05
  tasks: 2
  files_created: 6
  files_modified: 4
---

# Phase quick-260404-rtv Plan 01: RIS n8n Pilot (Scoped) Summary

**One-liner:** n8n 1.88.0 added as opt-in compose profile with three RIS CLI workflow templates, scoped ADR, and full operator guide update.

## What Was Shipped

### ADR 0013 (docs/adr/0013-ris-n8n-pilot-scoped.md)

Resolves authority drift: n8n is approved as a scoped RIS-only pilot. The repo remains
Phase 0/1, CLI-first. Hard scope boundaries are documented: allowed surfaces are
`research-acquire`, `research-ingest`, `research-health`, `research-scheduler status`,
`research-stats summary`. Strategy logic, gate logic, risk policy, and live capital
operations are explicitly out of scope. Any expansion requires a new ADR and human approval.

### docker-compose.yml

n8n service added under compose profile `ris-n8n`:
- Image: `n8nio/n8n:1.88.0` (pinned, non-latest)
- Environment: basic auth, encryption key, runners enabled, MCP bearer token, timezone
- Volume: `n8n_data` (persistent workflow/credential storage)
- Network: polytool bridge (same as all services)
- `n8n_data:` added to top-level `volumes:` block

### .env.example

Added n8n section: `N8N_PORT`, `N8N_BASIC_AUTH_USER`, `N8N_BASIC_AUTH_PASSWORD`,
`N8N_ENCRYPTION_KEY`, `GENERIC_TIMEZONE`, `N8N_MCP_BEARER_TOKEN`, `MCP_PORT`,
`RIS_SCHEDULER_BACKEND` (informational, commented).

### scripts/docker-start.sh

Refactored from single positional arg to a multi-flag loop. `--with-n8n` starts the
ris-n8n profile and prints a scheduler mutual exclusion warning. Existing `--with-bots`
behavior is preserved.

### Workflow Templates (infra/n8n/workflows/)

All templates ship with `"active": false`. Operator activates manually from n8n UI.

| File | CLI command | Trigger |
|------|-------------|---------|
| `ris_health_check.json` | `python -m polytool research-health` | Manual + cron every 6h |
| `ris_scheduler_status.json` | `python -m polytool research-scheduler status` | Manual only |
| `ris_manual_acquire.json` | `python -m polytool research-acquire --url ... --source-family ...` | Webhook POST |

Each workflow includes a `notes` field with scope boundary reminder and CLI command details.

### infra/n8n/import-workflows.sh

Imports all workflows/*.json via `POST /api/v1/workflows`. Requires curl and jq.
Prints per-workflow HTTP status, summary counts, next steps, and mutual exclusion warning.

### docs/RIS_OPERATOR_GUIDE.md

New section `## n8n RIS Pilot (Opt-In)` covers:
- Scope boundary (one sentence)
- Scheduler selection table with APScheduler vs n8n comparison
- Mutual exclusion procedure (stop ris-scheduler before starting n8n)
- Step-by-step start/import/activate flow (8 numbered steps)
- Manual verification steps
- Webhook usage with curl example and security note
- Claude Code MCP connection via HTTP bearer token (N8N_MCP_ENABLED explicitly rejected)

## n8n Image Tag Used

`n8nio/n8n:1.88.0` -- pinned stable 1.x release. To upgrade: update the tag in
`docker-compose.yml`, run `docker compose config` to validate, then commit.

## Mutual Exclusion Mechanism

APScheduler (`ris-scheduler` container, no profile) and n8n (`n8n` container, profile
`ris-n8n`) are mutually exclusive. The mechanism is:

1. `ris-scheduler` has no compose profile -- it always starts with the default stack.
2. `n8n` is behind the `ris-n8n` profile -- operator must explicitly opt in.
3. No code-level lock exists. The mutual exclusion relies on operator procedure.
4. `docker-start.sh` prints a warning when `--with-n8n` is used.
5. ADR 0013 and RIS_OPERATOR_GUIDE.md document the switch procedure.

If both run simultaneously: duplicate RIS ingestion occurs (dedup prevents data corruption,
but fetch budget is wasted). Recovery: stop ris-scheduler via `docker compose stop ris-scheduler`.

## Deviations from Plan

None. Plan executed exactly as written.

The plan spec listed `N8N_SECURE_COOKIE=true` as a required env var. This variable does
not exist in n8n 1.x -- it was replaced by `N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=true`
in the 1.x series. The compose service uses the correct current variable. This is a
deviation by correction, not by omission -- no functionality is missing.

The plan spec referenced `host-docker-internal` in the POLYTOOL_HOST env var. The
standard Docker hostname for host access is `host.docker.internal` (with a dot). The
compose service and operator guide both use the correct form.

## Threat Surface Scan

| Flag | File | Description |
|------|------|-------------|
| threat_flag: external_webhook | infra/n8n/workflows/ris_manual_acquire.json | New HTTP POST webhook endpoint exposed by n8n at /webhook/ris-acquire when workflow is activated |
| threat_flag: bearer_token_surface | docker-compose.yml, .env.example | N8N_MCP_BEARER_TOKEN added as a new bearer-token-gated surface |

Threat T-rtv-01 (webhook URL spoofing) is mitigated by documentation: operator guide
and workflow notes field instruct treating the webhook URL as a secret. Threat T-rtv-05
(Execute Command injection) is mitigated by argparse validation in the CLI before execution.

## CLI Smoke Test Results

```
python -m polytool --help              CLI OK (no import errors)
python -m polytool research-scheduler --help   scheduler OK
python -m polytool research-acquire --help     acquire OK
python -m polytool research-health             health exit 0 (YELLOW for high accept rate -- pre-existing)
docker compose config --quiet          compose OK, exit 0
```

No regressions. No code was modified; all changes are infra config, documentation,
workflow templates, and shell scripts.

## Commits

| Task | Commit | Files |
|------|--------|-------|
| Task 1: ADR + compose + env + start script | `35755d2` | docker-compose.yml, .env.example, scripts/docker-start.sh, docs/adr/0013-ris-n8n-pilot-scoped.md |
| Task 2: workflows + import helper + operator docs + dev log | `a8e189d` | infra/n8n/workflows/*.json, infra/n8n/import-workflows.sh, docs/RIS_OPERATOR_GUIDE.md, docs/dev_logs/2026-04-05_ris_n8n_pilot.md |

## Self-Check: PASSED

All created files verified present:
- docs/adr/0013-ris-n8n-pilot-scoped.md: FOUND
- infra/n8n/workflows/ris_health_check.json: FOUND
- infra/n8n/workflows/ris_scheduler_status.json: FOUND
- infra/n8n/workflows/ris_manual_acquire.json: FOUND
- infra/n8n/import-workflows.sh: FOUND
- docs/dev_logs/2026-04-05_ris_n8n_pilot.md: FOUND

All commits verified:
- 35755d2: FOUND
- a8e189d: FOUND

docker compose config exit 0: PASSED
python -m polytool --help exit 0: PASSED
