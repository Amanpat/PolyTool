---
phase: quick-260406-ido
plan: "01"
subsystem: infra/n8n
tags: [docker, n8n, mcp, upgrade, 2x]
dependency_graph:
  requires: [quick-260405-vbn]
  provides: [n8n-2x-base-image]
  affects: [infra/n8n/Dockerfile, docker-compose.yml, docs]
tech_stack:
  added: []
  patterns: [docker-static-binary, n8n-2x-owner-setup]
key_files:
  created:
    - docs/dev_logs/2026-04-06_n8n_2x_instance_mcp_upgrade.md
  modified:
    - infra/n8n/Dockerfile
    - docker-compose.yml
    - docs/adr/0013-ris-n8n-pilot-scoped.md
    - docs/CURRENT_STATE.md
    - docs/RIS_OPERATOR_GUIDE.md
decisions:
  - "Used n8n 2.14.2 (not 2.15.0) because 2.15.0 was prerelease=True on GitHub per prior dev log"
  - "N8N_RUNNERS_ENABLED replaced by N8N_RUNNERS_MODE=internal; N8N_BASIC_AUTH_* retained as no-op comments for reference"
  - "N8N_MCP_BEARER_TOKEN documented as informational-only in community edition; Enterprise only for backend /mcp-server/http"
  - "Docker static binary pattern for docker-cli unchanged — confirmed compatible with n8n 2.x DHI image"
metrics:
  duration_seconds: 376
  completed_date: "2026-04-06"
  tasks_completed: 3
  tasks_total: 3
  files_changed: 6
---

# Phase quick-260406-ido Plan 01: n8n 2.x Migration Summary

**One-liner:** Upgraded n8n base image from 1.123.28 to 2.14.2 (latest stable 2.x); updated compose env vars for 2.x API; confirmed build/healthz/docker-cli/11-workflow-import all pass; documented MCP as Enterprise-only in community edition.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Discover latest 2.x tag, update Dockerfile and docker-compose.yml | cb65f5c | infra/n8n/Dockerfile, docker-compose.yml |
| 2 | Build, start, verify n8n 2.x container end-to-end | (runtime only, no separate commit) | — |
| 3 | Update docs (ADR-0013, CURRENT_STATE, RIS_OPERATOR_GUIDE, dev log) | dd1fc9a | 4 docs files |

## Decisions Made

1. **2.14.2 over 2.15.0:** The previous dev log (2026-04-05) noted `n8n@2.15.0` was prerelease=True on GitHub. Per plan rule: use the latest NON-prerelease 2.x tag. 2.14.2 is the correct target.

2. **docker-cli install unchanged:** n8n 2.x uses the same node-based DHI structure as 1.123.28. The `wget + tar + mv /usr/local/bin/docker` pattern works without modification. Confirmed via successful build and `docker exec polytool-n8n docker --version` = 29.3.1.

3. **N8N_RUNNERS_MODE=internal:** Replaced the deprecated `N8N_RUNNERS_ENABLED=true` with the 2.x API `N8N_RUNNERS_MODE=internal`. The old boolean var is a no-op in 2.x.

4. **N8N_BASIC_AUTH_* kept as comments:** These vars are removed in n8n 2.x but are silently ignored (no error). Kept in compose for reference with explanatory comments. On fresh `n8n_data` volumes, the first-run setup wizard at `/setup` is required.

5. **N8N_MCP_BEARER_TOKEN is informational:** The `/mcp-server/http` HTTP backend is Enterprise-only. The community edition serves the SPA at that path (200 HTML). `N8N_MCP_BEARER_TOKEN` retained in compose but documented as no-op in community edition.

## Verification Results

| Check | Result |
|-------|--------|
| Dockerfile FROM line: n8nio/n8n:2.14.2 | PASS |
| docker compose config --quiet | PASS |
| docker compose --profile ris-n8n build n8n | PASS (5.7s layer) |
| curl http://localhost:5678/healthz | `{"status":"ok"}` |
| docker exec polytool-n8n docker --version | Docker version 29.3.1, build c2be9cc |
| bash infra/n8n/import-workflows.sh | 11 succeeded, 0 failed |
| MCP endpoint /mcp-server/http | 200 HTML (SPA); backend is Enterprise-only |
| python -m polytool --help | PASS (no import errors) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] N8N_RUNNERS_ENABLED deprecated in n8n 2.x**
- **Found during:** Task 1 (reviewing n8n 2.x config schema)
- **Issue:** `N8N_RUNNERS_ENABLED` is not in the n8n 2.x `TaskRunnersConfig` schema; it was replaced by `N8N_RUNNERS_MODE` enum ('internal' | 'external').
- **Fix:** Updated compose `N8N_RUNNERS_ENABLED=true` -> `N8N_RUNNERS_MODE=internal`.
- **Files modified:** docker-compose.yml
- **Commit:** cb65f5c

### Informational Findings (Not Deviations)

**MCP Enterprise-only finding:** The plan states "N8N_MCP_BEARER_TOKEN becomes operative with 2.x." Investigation revealed this is accurate only for the Enterprise edition. The community edition does not expose the HTTP MCP backend. This is documented in the dev log, the ADR, and the operator guide. `N8N_MCP_BEARER_TOKEN` remains in compose as a placeholder. No code change required.

**v3 binaryData storage warning:** n8n 2.x emits a deprecation warning about the storage directory path during workflow import. This is informational only and does not affect 2.x functionality. Documented in the dev log.

## Known Stubs

None — all plan goals achieved. The MCP backend limitation is an upstream licensing constraint, not a stub.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: mcp-enterprise-locked | docker-compose.yml | N8N_MCP_BEARER_TOKEN is now documented as informational-only in community edition; no new network surface opened |

## Self-Check: PASSED

Files created:
- `docs/dev_logs/2026-04-06_n8n_2x_instance_mcp_upgrade.md` — EXISTS
- `.planning/quick/260406-ido-upgrade-n8n-base-image-from-1-x-to-lates/260406-ido-SUMMARY.md` — EXISTS (this file)

Files modified:
- `infra/n8n/Dockerfile` — FROM n8nio/n8n:2.14.2 confirmed
- `docker-compose.yml` — N8N_RUNNERS_MODE=internal confirmed
- `docs/adr/0013-ris-n8n-pilot-scoped.md` — 2.14.2 references confirmed
- `docs/CURRENT_STATE.md` — 2.x migration section confirmed
- `docs/RIS_OPERATOR_GUIDE.md` — last-verified 2026-04-06 confirmed

Commits:
- cb65f5c — Task 1 (Dockerfile + compose)
- dd1fc9a — Task 3 (docs)
