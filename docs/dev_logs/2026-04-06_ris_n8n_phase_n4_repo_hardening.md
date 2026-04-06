# 2026-04-06 RIS n8n Phase N4 Repo Hardening

**Quick task:** quick-260406-mno
**Branch:** main
**Date:** 2026-04-06

## Summary

- Fixed the leading `=` prefix bug in `infra/n8n/workflows/ris_manual_acquire.json`
  that would cause n8n Execute Command nodes to interpret the docker exec string as a
  JavaScript expression instead of a shell command.
- Deleted the orphaned `workflows/n8n/` directory (v2 set, 8 JSON files + README.md)
  that referenced a non-existent container name (`polytool-polytool-1`) and contained
  additional CLI bugs. The canonical workflow location is `infra/n8n/workflows/` per
  ADR-0013 and the import script.
- Added scheduler mutual exclusion documentation to `docker-compose.yml`, `.env.example`,
  and `scripts/docker-start.sh` so operators understand the APScheduler-vs-n8n choice.
- Created `scripts/smoke_ris_n8n.py` -- a non-destructive repo-side validation script
  that validates all 11 workflow JSONs, 5 CLI entrypoints, and the compose profile.
- Created `docs/runbooks/RIS_N8N_SMOKE_TEST.md` with complete operator instructions for
  Phase N4 validation and manual follow-up after smoke passes.

---

## Audit Findings

The following 7 gaps were identified during the pre-execution audit (see plan context):

1. **Leading `=` prefix in ris_manual_acquire.json command field (v1)**
   File: `infra/n8n/workflows/ris_manual_acquire.json`
   The `executeCommand` node's `command` started with `=`, making n8n treat it as a JS
   expression. The expression `=docker exec ...` would evaluate and fail at runtime.

2. **Orphaned `workflows/n8n/` directory (v2) with wrong container name**
   All 8 JSON files in `workflows/n8n/` used `polytool-polytool-1` as the exec target.
   No container in `docker-compose.yml` has that name. This directory was created on the
   `feat/ws-clob-feed` branch with stale assumptions about the default compose container name.

3. **v2 ris-manual-ingest.json also had the leading `=` bug**
   Resolved by deleting the entire `workflows/n8n/` directory.

4. **v2 ris-weekly-digest.json used invalid CLI invocation (`research-report --topic`)**
   `research-report` requires a subcommand (save/list/search/digest); `--topic` is not
   a valid standalone invocation. Resolved by deleting the v2 directory.

5. **v2 ris-reddit-ingestion.json only covered `reddit_polymarket`, missing `reddit_others`**
   The v1 set has both `ris_reddit_polymarket.json` and `ris_reddit_others.json`. The v2
   set only had one reddit workflow. Resolved by deleting the v2 directory.

6. **No smoke test script existed**
   There was no automated way to validate workflow JSON correctness, CLI entrypoints, or
   compose profile render in a single offline command. Fixed: `scripts/smoke_ris_n8n.py`.

7. **No operator runbook for Phase N4 validation**
   The existing `infra/n8n/README.md` covered setup but not the Phase N4 validation path.
   Fixed: `docs/runbooks/RIS_N8N_SMOKE_TEST.md`.

---

## Changes Made

| File | Change |
|------|--------|
| `infra/n8n/workflows/ris_manual_acquire.json` | Removed leading `=` from executeCommand `command` field |
| `workflows/n8n/` (8 JSON + README) | Deleted entire orphaned v2 directory |
| `workflows/` | Deleted (now empty after n8n/ removal) |
| `docker-compose.yml` | Added 3-line APScheduler comment block above `ris-scheduler:` service |
| `.env.example` | Added 3-line APScheduler default-on note in the n8n RIS Pilot section |
| `scripts/docker-start.sh` | Added `Tip: docker compose stop ris-scheduler` line in `--with-n8n` branch |
| `scripts/smoke_ris_n8n.py` | Created: non-destructive repo-side validation script |
| `docs/runbooks/RIS_N8N_SMOKE_TEST.md` | Created: operator runbook for Phase N4 validation |

---

## APScheduler Profile Assessment

**Decision: ris-scheduler was NOT moved behind a compose profile. Blocker documented.**

The plan context explicitly forbade adding a `profiles:` key to the `ris-scheduler` service:

> APScheduler (ris-scheduler) CANNOT safely be put behind a profile without risk --
> it has no profile today and adding one would change default-stack behavior for existing
> operators.

Rationale:
- `ris-scheduler` runs in the default stack today (`docker compose up` starts it).
- Adding `profiles: [ris-apscheduler]` would mean `docker compose up` no longer starts
  the scheduler, silently breaking existing operator workflows.
- The correct operator path is documented mutual exclusion: stop `ris-scheduler` when
  switching to n8n, without changing the compose default.
- A future ADR could propose making both schedulers profile-gated (e.g., both behind
  `ris-apscheduler` and `ris-n8n` profiles), but that requires updating all operator docs,
  `docker-start.sh` default behavior, and communicating the breaking change.

**Status: BLOCKER DOCUMENTED. No code change made to ris-scheduler service.**

---

## Test Commands Run

| Command | Result |
|---------|--------|
| `python scripts/smoke_ris_n8n.py` | PASS -- 74 PASS, 0 FAIL, 0 SKIP |
| `python -m polytool --help` | Loads, no import errors |
| `python -m polytool research-health --help` | Exit 0 |
| `python -m polytool research-stats --help` | Exit 0 |
| `python -m polytool research-scheduler --help` | Exit 0 |
| `python -m polytool research-acquire --help` | Exit 0 |
| `python -m polytool research-report --help` | Exit 0 |
| `docker compose --profile ris-n8n config --quiet` | Exit 0 |
| `python -m pytest tests/ -x -q --tb=short` | 3695 passed, 0 failed, 25 warnings |

---

## Remaining Manual UI Steps

These steps require a running n8n instance and cannot be automated from the repo side:

1. Import workflows via `bash infra/n8n/import-workflows.sh`
   (requires n8n container to be running with API access)

2. Complete n8n owner setup wizard at `http://localhost:5678/setup`
   (first-run only; sets owner email and password)

3. Activate desired workflows in n8n UI
   (toggle switch per workflow; health check and scheduler status are good starting points)

4. Configure `DISCORD_WEBHOOK_URL` in n8n Settings > Variables
   (for any future alerting workflows that reference Discord)

5. Optionally register n8n MCP in Claude Code
   (requires n8n 2.14.2+ and the correct bearer token; see
   `docs/dev_logs/2026-04-06_n8n_instance_mcp_connection_debug.md` for connection steps)

---

## Codex Review

Skip (infra config, workflow JSON, docs, smoke script -- no strategy, execution, or risk
code changed in this session).
