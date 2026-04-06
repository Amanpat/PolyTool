---
phase: quick-260406-mno
plan: 01
subsystem: infra
tags: [n8n, ris, docker-compose, smoke-test, workflow-json]

requires: []
provides:
  - Fixed ris_manual_acquire.json leading = prefix bug
  - Removed orphaned workflows/n8n/ v2 directory
  - smoke_ris_n8n.py: non-destructive repo-side validation (74 checks)
  - RIS_N8N_SMOKE_TEST.md: operator runbook for Phase N4
  - Scheduler mutual exclusion documentation in docker-compose.yml, .env.example, docker-start.sh
affects: [260404-rtv, 260404-sb4, 260405-l8q]

tech-stack:
  added: []
  patterns:
    - "n8n executeCommand command fields must not start with = (JS expression prefix)"
    - "Canonical n8n workflow location: infra/n8n/workflows/ (not workflows/n8n/)"
    - "APScheduler ris-scheduler always-on in default stack; mutual exclusion via stop, not profiles"

key-files:
  created:
    - scripts/smoke_ris_n8n.py
    - docs/runbooks/RIS_N8N_SMOKE_TEST.md
    - docs/dev_logs/2026-04-06_ris_n8n_phase_n4_repo_hardening.md
  modified:
    - infra/n8n/workflows/ris_manual_acquire.json
    - docker-compose.yml
    - .env.example
    - scripts/docker-start.sh
  deleted:
    - workflows/n8n/ (entire v2 directory, 8 JSON + README)

key-decisions:
  - "Do not add compose profile to ris-scheduler -- breaking change to default stack; document mutual exclusion instead"
  - "Delete v2 workflows/n8n/ entirely -- wrong container name, CLI bugs, not the canonical location per ADR-0013"

requirements-completed: []

duration: 25min
completed: 2026-04-06
---

# quick-260406-mno: RIS n8n Phase N4 Repo Hardening Summary

**Fixed leading = prefix bug in ris_manual_acquire.json, removed orphaned v2 workflow directory, and shipped smoke_ris_n8n.py with 74 automated checks (74 PASS, 0 FAIL)**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-04-06T~15:00Z
- **Completed:** 2026-04-06T~15:25Z
- **Tasks:** 3 of 3
- **Files modified:** 8 (including 1 deleted directory tree)

## Accomplishments

- Removed the `=` prefix from the `executeCommand` command field in `ris_manual_acquire.json` that would have caused every webhook-triggered acquire to fail with a JS evaluation error
- Deleted the orphaned `workflows/n8n/` directory (8 files) that referenced container `polytool-polytool-1` (does not exist) and contained two additional CLI bugs
- Added scheduler mutual exclusion documentation to `docker-compose.yml`, `.env.example`, and `scripts/docker-start.sh` so operators understand double-scheduling risk
- Created `scripts/smoke_ris_n8n.py` with 74 automated checks covering all 11 workflow JSONs, 5 CLI entrypoints, and docker compose profile -- exits 0 in a fresh run
- Created `docs/runbooks/RIS_N8N_SMOKE_TEST.md` with quick start, check descriptions, manual follow-up steps, and troubleshooting for Phase N4

## Task Commits

1. **Task 1: Fix workflow drift and remove orphaned v2 directory** - `11ad1ff` (fix)
2. **Task 2: Create smoke script and operator runbook** - `429fb3d` (feat)
3. **Task 3: Write dev log documenting all changes** - `9c4213e` (docs)

**Plan metadata:** (see below -- final metadata commit)

## Files Created/Modified

- `infra/n8n/workflows/ris_manual_acquire.json` - Removed leading `=` from executeCommand command field
- `workflows/n8n/` - Deleted (entire orphaned v2 directory: 8 JSON + README)
- `docker-compose.yml` - Added 3-line APScheduler mutual exclusion comment above `ris-scheduler:`
- `.env.example` - Added APScheduler default-on note in n8n RIS Pilot section
- `scripts/docker-start.sh` - Added double-scheduling tip in `--with-n8n` branch output
- `scripts/smoke_ris_n8n.py` - Created: 74-check non-destructive repo-side validation script
- `docs/runbooks/RIS_N8N_SMOKE_TEST.md` - Created: operator runbook for Phase N4 validation
- `docs/dev_logs/2026-04-06_ris_n8n_phase_n4_repo_hardening.md` - Created: full audit trail

## Decisions Made

- **APScheduler profile blocker:** Did NOT add a `profiles:` key to `ris-scheduler`. Adding one
  would break the default stack for existing operators (they would need `--profile ris-apscheduler`
  to get the scheduler). The safe path is documented mutual exclusion: stop `ris-scheduler` when
  switching to n8n. A future ADR could propose making both schedulers profile-gated.

- **Delete v2 directory entirely:** `workflows/n8n/` was not fixable in place -- the container name
  bug, CLI invocation bugs, and incomplete job coverage all point to it being a dead-end from a
  stale feature branch. The canonical v1 set in `infra/n8n/workflows/` is complete and correct.

## Deviations from Plan

None -- plan executed exactly as written.

## Issues Encountered

None. All workflow JSONs (v1) were structurally correct except the `=` prefix; smoke script
passed on first run with 74 PASS, 0 FAIL, 0 SKIP. Regression suite: 3695 passed, 0 failed.

## Known Stubs

None. This plan is docs + infra config; no UI stubs or data source wiring involved.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: info_disclosure | docs/runbooks/RIS_N8N_SMOKE_TEST.md | Runbook documents that webhook URLs contain auth tokens and must be treated as secrets; this is a mitigation note, not a new surface |

No new network endpoints, auth paths, or schema changes introduced.

## Next Phase Readiness

- Repo-side RIS n8n assets are now internally consistent and validated
- Operator can run `python scripts/smoke_ris_n8n.py` to verify at any time
- Phase N5 (manual UI steps) requires a running n8n instance: import workflows, complete setup wizard, activate workflows
- APScheduler vs n8n scheduler selection remains a manual operator decision

---

## Self-Check

Files created:
- `scripts/smoke_ris_n8n.py` -- EXISTS (confirmed, ran successfully)
- `docs/runbooks/RIS_N8N_SMOKE_TEST.md` -- EXISTS (confirmed)
- `docs/dev_logs/2026-04-06_ris_n8n_phase_n4_repo_hardening.md` -- EXISTS (confirmed)

Commits:
- `11ad1ff` -- fix(quick-260406-mno): fix ris_manual_acquire.json = prefix and remove orphaned v2 workflows
- `429fb3d` -- feat(quick-260406-mno): add smoke_ris_n8n.py and RIS_N8N_SMOKE_TEST.md runbook
- `9c4213e` -- docs(quick-260406-mno): write dev log for Phase N4 repo hardening

## Self-Check: PASSED

---
*Phase: quick-260406-mno*
*Completed: 2026-04-06*
