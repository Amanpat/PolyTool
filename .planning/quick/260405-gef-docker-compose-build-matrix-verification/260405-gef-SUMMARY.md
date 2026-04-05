---
phase: quick-260405-gef
plan: "01"
subsystem: infrastructure
tags: [docker, compose, safety, build-matrix, pair-bot]
dependency_graph:
  requires: []
  provides: [verified-compose-profile-gates, api-dockerfile-healthcheck]
  affects: [docker-compose.yml, services/api/Dockerfile, docs/CURRENT_STATE.md]
tech_stack:
  added: []
  patterns: [docker-compose-profiles, docker-healthcheck]
key_files:
  created:
    - docs/dev_logs/2026-04-05_docker_build_matrix_closeout.md
  modified:
    - docker-compose.yml
    - services/api/Dockerfile
    - .env.example
    - docs/CURRENT_STATE.md
decisions:
  - "Kept pair-bot-live restart: unless-stopped after profile fix — expected behavior when live creds absent"
  - "curl installed in services/api/Dockerfile via apt-get (not via alternative healthcheck command) to keep compose config unchanged"
metrics:
  duration: "~4 hours (includes Docker Desktop crash recovery x3)"
  completed: "2026-04-05"
---

# Phase quick-260405-gef Plan 01: Docker Build Matrix Verification Summary

One-liner: Fixed pair-bot-live profile gate (live bot was in default stack) and API
healthcheck curl absence, then verified all 5 docker compose profile paths build clean.

## What Was Done

### Task 1 — Fix pair-bot-live Profile Gate

`pair-bot-live` was missing `profiles: ["pair-bot"]` in `docker-compose.yml`. This
caused the live trading bot (`crypto-pair-run --live --confirm CONFIRM`) to start on
every `docker compose up -d --build` — a direct violation of the CLAUDE.md rule that
live capital deployment requires explicit human activation.

Fix: Added `profiles: ["pair-bot"]` to the pair-bot-live service. The service now
requires `docker compose --profile pair-bot up -d` to start.

Also updated `.env.example` with a comment block documenting the pair-bot profile's
purpose, activation method, and Gate 2/3 deployment block.

Commit: `dfbfa88` — `fix(quick-260405-gef-01): gate pair-bot-live behind pair-bot profile`

### Task 2 — Build Matrix + API Dockerfile Fix

During Path 1 execution, the `api` container was reporting `unhealthy` because
`python:3.11-slim` does not include `curl`. The docker-compose.yml healthcheck runs
`curl -f http://localhost:8000/health`. Fixed by adding curl installation to
`services/api/Dockerfile`.

All 5 build matrix paths verified clean:

| Path | Command | Result |
|------|---------|--------|
| 1 — Default stack | `docker compose up -d` | PASS: all services healthy |
| 2 — pair-bot | `docker compose --profile pair-bot up -d` | PASS: both bots start |
| 3 — ris-n8n | `docker compose --profile ris-n8n up -d --build` | PASS: n8n up on :5678 |
| 4 — cli | `docker compose --profile cli run --rm polytool python -m polytool --help` | PASS |
| 5 — full combo | `docker compose --profile pair-bot --profile ris-n8n --profile cli up -d` | PASS |

Python smoke test: 3695 passed, 0 failed.

Commit: `4b61ee5` — `fix(260405-gef): complete docker build matrix verification`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] API container healthcheck failing with curl not found**
- **Found during:** Task 2, Path 1 execution
- **Issue:** `python:3.11-slim` base image lacks `curl`; the compose healthcheck runs
  `curl -f http://localhost:8000/health`, causing perpetual `unhealthy` status even
  though the API was responding correctly
- **Fix:** Added `RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*` to `services/api/Dockerfile`
- **Files modified:** `services/api/Dockerfile`
- **Commit:** `4b61ee5`

### Deferred Items

None. All issues encountered were Docker layer issues (within scope).

## Known Stubs

None. This plan contains only infrastructure changes. No stub values or placeholder
data was introduced.

## Threat Surface Scan

T-quick-01 (pair-bot-live elevation of privilege) — MITIGATED. The `profiles: ["pair-bot"]`
gate is now in place and verified. `docker compose up -d` no longer starts pair-bot-live.

T-quick-02 (n8n docker.sock mount) — ACCEPTED per ADR-0013. No change made.

No new threat surface introduced by this plan.

## Infrastructure Issues During Execution (informational)

Three Docker Desktop WSL2 VHDX unmount crashes occurred during builds. Recovery:
kill Docker processes, `wsl --shutdown`, restart Docker Desktop. One corrupted layer
cache required `docker builder prune -f` to clear. These are Windows 11 / Docker
Desktop environment issues, not codebase issues.

## Self-Check: PASSED

- docs/dev_logs/2026-04-05_docker_build_matrix_closeout.md: FOUND
- services/api/Dockerfile: FOUND
- docker-compose.yml: FOUND
- commit dfbfa88 (Task 1): FOUND
- commit 4b61ee5 (Task 2): FOUND
